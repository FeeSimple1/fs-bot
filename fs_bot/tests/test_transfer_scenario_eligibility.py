"""WS-F07: Resource holders/recipients follow §§1.5.2/1.8 and A1.5.2/A1.8."""

import copy
import io

import pytest

from fs_bot import rules_consts as rc
from fs_bot.cards.capabilities import activate_capability
from fs_bot.cli import human_plan
from fs_bot.cli.display import HumanTurnDisplay
from fs_bot.commands.common import CommandError
from fs_bot.commands.transfer import transfer_resources
from fs_bot.engine.execute import execute_decision
from fs_bot.engine.game_engine import (
    ACTION_COMMAND, ACTION_EVENT, _action_transaction,
)
from fs_bot.engine.interlude import run_interlude
from fs_bot.state.serialize import encode, load_game, save_game
from fs_bot.state.setup import setup_scenario
from fs_bot.tools.seat_session import DecisionPending, SeatSession, board_copy


@pytest.mark.parametrize('scenario', rc.ALL_SCENARIOS)
@pytest.mark.parametrize('giving', [False, True])
def test_game_run_faction_cannot_give_or_receive(scenario, giving):
    """§1.8 excludes base Germans; A1.5.2/A1.8 exclude expansion Arverni."""
    state = setup_scenario(scenario, seed=4)
    game_run = rc.GERMANS if scenario in rc.BASE_SCENARIOS else rc.ARVERNI
    giver, receiver = (game_run, rc.AEDUI) if giving else (rc.AEDUI, game_run)
    # An erroneous saved stock must not make a faction without a track legal.
    state['resources'][giver] = 10
    before = encode(board_copy(state))
    with pytest.raises(CommandError, match=game_run):
        transfer_resources(state, giver, receiver, 3)
    assert encode(board_copy(state)) == before


@pytest.mark.parametrize('scenario', rc.ALL_SCENARIOS)
@pytest.mark.parametrize('giving', [False, True])
def test_player_arverni_or_germans_can_give_and_receive(scenario, giving):
    """Base Arverni have Resources; A1.5.2 gives Germans ordinary transfers."""
    state = setup_scenario(scenario, seed=4)
    participant = rc.ARVERNI if scenario in rc.BASE_SCENARIOS else rc.GERMANS
    giver, receiver = (participant, rc.AEDUI) if giving else (rc.AEDUI, participant)
    state['resources'][giver] = 10
    state['resources'][receiver] = 4
    assert transfer_resources(state, giver, receiver, 3)['given'] == 3
    assert state['resources'][giver] == state['resources'][receiver] == 7


def test_interlude_switches_transfer_participants_with_resource_cylinder():
    """Gallic War Interlude: replace German Resource cylinder with Arverni's;
    Second Half: 'Original Falling Sky rules are in effect.'
    """
    state = setup_scenario(rc.SCENARIO_GALLIC_WAR, seed=4)
    run_interlude(state, britannia_decision=False)
    assert state['interlude_completed']
    assert state['scenario_phase'] == 'second_half'
    assert state['scenario'] == rc.SCENARIO_PAX_GALLICA
    state['resources'][rc.AEDUI] = 10
    state['resources'][rc.ARVERNI] = 4
    transfer_resources(state, rc.AEDUI, rc.ARVERNI, 3)
    transfer_resources(state, rc.ARVERNI, rc.AEDUI, 2)
    assert state['resources'][rc.AEDUI] == 9
    assert state['resources'][rc.ARVERNI] == 5
    for giver, receiver in ((rc.AEDUI, rc.GERMANS), (rc.GERMANS, rc.AEDUI)):
        before = encode(board_copy(state))
        with pytest.raises(CommandError, match=rc.GERMANS):
            transfer_resources(state, giver, receiver, 1)
        assert encode(board_copy(state)) == before


@pytest.mark.parametrize('scenario', rc.ARIOVISTUS_SCENARIOS)
def test_raw_executor_reports_forbidden_arverni_gift_without_receiving_it(scenario):
    """A1.5.2 applies even to the raw executor's report-and-continue path."""
    state = setup_scenario(scenario, seed=4)
    state['non_player_factions'] = set()
    state['resources'][rc.AEDUI] = 10
    before = dict(state['resources'])
    action = {'command': rc.CMD_RALLY, 'sa': 'No SA', 'details': {
        'rally_plan': {'warbands': [rc.AEDUI_REGION]},
        'transfers': [{'to': rc.GERMANS, 'amount': 2},
                      {'to': rc.ARVERNI, 'amount': 3}],
    }}
    result = execute_decision(state, rc.AEDUI, {'player_action': action})
    assert result['executed']
    assert result['transfers'][0]['given'] == 2
    assert rc.ARVERNI in result['transfers'][1]['error']
    assert state['resources'][rc.ARVERNI] == before[rc.ARVERNI]
    assert state['resources'][rc.GERMANS] == before[rc.GERMANS] + 2


@pytest.mark.parametrize('scenario,recipients', [
    (rc.SCENARIO_GREAT_REVOLT, {rc.ROMANS, rc.ARVERNI, rc.BELGAE}),
    (rc.SCENARIO_ARIOVISTUS, {rc.ROMANS, rc.GERMANS, rc.BELGAE}),
    (rc.SCENARIO_GALLIC_WAR, {rc.ROMANS, rc.GERMANS, rc.BELGAE}),
])
def test_cli_recipient_menu_matches_scenario_resource_holders(monkeypatch, scenario, recipients):
    state = setup_scenario(scenario, seed=4)
    state['resources'][rc.AEDUI] = 10
    before = encode(board_copy(state))
    menus = []

    def choose(stdin, stdout, title, options):
        menus.append(options)
        return options[0][1]

    monkeypatch.setattr(human_plan, 'prompt_yes_no', lambda *args, **kwargs: True)
    monkeypatch.setattr(human_plan, 'prompt_choice', choose)
    action = human_plan._maybe_collect_transfer(
        state, rc.AEDUI, {}, io.StringIO(), io.StringIO())
    assert {value for _, value in menus[0]} == recipients
    assert action['details']['transfers'][0]['to'] in recipients
    assert encode(board_copy(state)) == before


@pytest.mark.parametrize('scenario,giver', [
    (rc.SCENARIO_GREAT_REVOLT, rc.GERMANS),
    (rc.SCENARIO_ARIOVISTUS, rc.ARVERNI),
])
def test_cli_does_not_offer_gifts_from_faction_without_resource_track(monkeypatch, scenario, giver):
    state = setup_scenario(scenario, seed=4)
    state['resources'][giver] = 10

    def unexpected_prompt(*args, **kwargs):
        pytest.fail('A faction without a Resource track must not offer a gift')

    monkeypatch.setattr(human_plan, 'prompt_yes_no', unexpected_prompt)
    action = {}
    assert human_plan._maybe_collect_transfer(
        state, giver, action, io.StringIO(), io.StringIO()) is action
    assert action == {}


def test_cli_card_38_shaded_omits_prohibited_roman_recipient(monkeypatch):
    """Card 38 shaded: Romans and Aedui may not transfer to one another."""
    state = setup_scenario(rc.SCENARIO_GREAT_REVOLT, seed=4)
    state['resources'][rc.AEDUI] = 10
    activate_capability(state, 38, rc.EVENT_SHADED)
    menus = []

    def choose(stdin, stdout, title, options):
        menus.append(options)
        return options[0][1]

    monkeypatch.setattr(human_plan, 'prompt_yes_no', lambda *args, **kwargs: True)
    monkeypatch.setattr(human_plan, 'prompt_choice', choose)
    human_plan._maybe_collect_transfer(state, rc.AEDUI, {}, io.StringIO(), io.StringIO())
    assert {value for _, value in menus[0]} == {rc.ARVERNI, rc.BELGAE}


def _driver(session):
    def driver(*args):
        pass
    driver.transaction_checkpoint = session.checkpoint
    driver.transaction_restore = session.restore
    return driver


@pytest.mark.parametrize('scenario', rc.ARIOVISTUS_SCENARIOS)
@pytest.mark.parametrize('command,action_type', [
    (rc.CMD_RALLY, ACTION_COMMAND), ('Event', ACTION_EVENT),
])
def test_durable_forbidden_transfer_stays_pending_through_save_load(
        tmp_path, scenario, command, action_type):
    """A1.5.2's forbidden gift cannot consume a typed turn or mutate board/RNG."""
    state = setup_scenario(scenario, seed=4)
    state['resources'][rc.AEDUI] = 10
    meta = {'seat': rc.AEDUI, 'scenario': scenario, 'seed': 4}
    session = SeatSession(state, meta, [], HumanTurnDisplay(io.StringIO()))
    request = {'kind': 'turn', 'options': [action_type], 'position': 'first'}
    response = {'action': action_type, 'player_action': {
        'command': command, 'sa': 'No SA', 'details': {
            'rally_plan': {'warbands': [rc.AEDUI_REGION]},
            'transfers': [{'to': rc.ARVERNI, 'amount': 3}],
        },
    }}
    before = encode(board_copy(state))
    with pytest.raises(DecisionPending):
        with _action_transaction(state, _driver(session)):
            session.ask(state, rc.AEDUI, request)
    pending = copy.deepcopy(session.data['pending'])
    payload = {'decision_id': pending['id'], 'response': response}
    session.import_inbox(payload)

    for attempt in range(2):
        with pytest.raises(DecisionPending):
            with _action_transaction(state, _driver(session)):
                session.ask(state, rc.AEDUI, request)
        assert rc.ARVERNI in session.error
        assert session.data['pending'] == pending
        assert session.data['queue'] == [payload]
        assert session.data['journal'] == session.log == []
        assert encode(board_copy(state)) == before
        if attempt == 0:
            path = tmp_path / 'forbidden_transfer.json'
            save_game(state, path, meta=session.meta, log=session.log)
            state, meta, log = load_game(path)
            session = SeatSession(state, meta, log, HumanTurnDisplay(io.StringIO()))

    corrected = copy.deepcopy(response)
    corrected['player_action']['details']['transfers'][0]['to'] = rc.GERMANS
    session.import_inbox({'decision_id': pending['id'], 'response': corrected})
    with _action_transaction(state, _driver(session)):
        assert session.ask(state, rc.AEDUI, request) == corrected
    session.finish()
    assert session.data['pending'] is None
    assert session.data['queue'] == []
    assert len(session.log) == 1
    assert encode(board_copy(state)) == before
