"""Card 71 creates a real Tribe for Commands, SAs, Events and victory (§7.2)."""
from copy import deepcopy
from io import StringIO

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces, get_available, place_piece
from fs_bot.cards.card_effects import _ally_tribe, _unally_tribe
from fs_bot.cli.human_plan import _subdued_tribes, _enemy_ally_tribes
from fs_bot.commands.common import CommandError
from fs_bot.commands.sa_build import build_place_ally, build_subdue
from fs_bot.commands.sa_entreat import entreat_replace_ally
from fs_bot.commands.sa_trade import trade
from fs_bot.commands.seize import calculate_forage, get_dispersible_tribes, seize_plan_error
from fs_bot.engine.execute import execute_decision
from fs_bot.engine.victory import calculate_victory_score
from fs_bot.state.serialize import encode, decode
from fs_bot.state.state_schema import build_initial_state, validate_state, check_structural_integrity
from fs_bot.tools.seat_session import board_copy


def board(scenario=rc.SCENARIO_GREAT_REVOLT):
    state = build_initial_state(scenario, seed=317)
    state.update(non_player_factions=set(), current_card=1, next_card=4)
    state['resources'].update({f: 30 for f in rc.FACTIONS})
    return state


def clean(state):
    assert validate_state(state) == []
    assert check_structural_integrity(state) == []


def play(state, card, actor, params=None, *, shaded=False, reject=False):
    state['current_card'] = card
    clean(state)
    before = encode(state)
    result = execute_decision(state, actor, {'action': 'event', 'player_action': {
        'command': rc.FIRST_DID_EVENT, 'regions': [], 'sa': 'No SA', 'sa_regions': [],
        'details': {'card_id': card,
                    'text_preference': rc.EVENT_SHADED if shaded else rc.EVENT_UNSHADED,
                    'event_params': params or {}}}})
    if reject:
        assert result['rejected'] and not result['executed'], result
        assert encode(state) == before
    else:
        assert result['executed'] and not result.get('errors'), result
        clean(state)
    return result


def colony(state, region, owner=rc.ROMANS, *, subdued=False):
    # A custom name must retain its recorded Region; no name parsing is legal.
    name = 'Settlers at ' + region
    play(state, 71, owner, {'region': region, 'colony_tribe_name': name})
    if subdued:
        assert _unally_tribe(state, name) == owner
    clean(state)
    return name


def seize(region, tribes):
    return {'action': 'command', 'player_action': {
        'command': rc.CMD_SEIZE, 'regions': [region], 'sa': 'No SA', 'sa_regions': [],
        'details': {'disperse_tribes': {region: tribes}}}}


@pytest.mark.parametrize('scenario', rc.ALL_SCENARIOS)
@pytest.mark.parametrize('status', ['roman', 'subdued', 'enemy', rc.DISPERSED, rc.DISPERSED_GATHERING])
def test_colony_forage_uses_the_same_status_rules_as_a_printed_tribe(scenario, status):
    state = board(scenario)
    baseline = calculate_forage(state, rc.MANDUBII, [])
    name = colony(state, rc.MANDUBII,
                  rc.AEDUI if status == 'enemy' else rc.ROMANS,
                  subdued=status not in ('roman', 'enemy'))
    if status in (rc.DISPERSED, rc.DISPERSED_GATHERING):
        state['tribes'][name]['status'] = status
    assert calculate_forage(state, rc.MANDUBII, []) == baseline + (
        2 if status in ('roman', 'subdued') else 0)
    clean(state)


@pytest.mark.parametrize('scenario', rc.ALL_SCENARIOS)
def test_full_authored_seize_can_disperse_a_colony_and_roundtrip(scenario):
    state = board(scenario)
    name = colony(state, rc.MANDUBII, subdued=True)
    place_piece(state, rc.MANDUBII, rc.ROMANS, rc.AUXILIA, 4)
    state['decision_agent'] = lambda _s, _f, req: (
        {'decline': True} if req['kind'] == 'free_action' else None)
    assert name in get_dispersible_tribes(state, rc.MANDUBII, limit_to_markers=False)
    assert name in _subdued_tribes(state, rc.MANDUBII)
    decision = seize(rc.MANDUBII, [name])
    assert seize_plan_error(decision['player_action'], require_exact=True, state=state) is None
    result = execute_decision(state, rc.ROMANS, decision)
    assert result['executed'] and not result['errors'], result
    assert result['forage_resources_total'] == 12  # three ordinary circles + new dispersal
    assert state['tribes'][name]['status'] == rc.DISPERSED
    clean(state)
    restored = decode(encode(board_copy(state)))
    assert restored['tribes'][name] == state['tribes'][name]
    assert calculate_forage(restored, rc.MANDUBII, []) == 6


def test_colony_cannot_be_selected_in_a_foreign_seize_region():
    state = board()
    name = colony(state, rc.MANDUBII, subdued=True)
    place_piece(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA)
    before = encode(state)
    result = execute_decision(state, rc.ROMANS, seize(rc.CARNUTES, [name]))
    assert result['rejected'] and not result['executed']
    assert encode(state) == before


@pytest.mark.parametrize('scenario,name', [
    (rc.SCENARIO_GREAT_REVOLT, rc.TRIBE_NORI),
    (rc.SCENARIO_ARIOVISTUS, rc.TRIBE_CATUVELLAUNI),
])
def test_colony_can_reuse_a_tribe_name_absent_from_this_scenario(scenario, name):
    state = board(scenario)
    assert name not in state['tribes']
    baseline = calculate_forage(state, rc.MANDUBII, [])
    play(state, 71, rc.ROMANS, {'region': rc.MANDUBII, 'colony_tribe_name': name})
    assert calculate_forage(state, rc.MANDUBII, []) == baseline + 2
    assert _unally_tribe(state, name) == rc.ROMANS
    assert name in _subdued_tribes(state, rc.MANDUBII)
    clean(state)


@pytest.mark.parametrize('scenario', rc.ALL_SCENARIOS)
def test_build_can_place_and_subdue_colony_discs(scenario):
    state = board(scenario)
    name = colony(state, rc.MANDUBII, subdued=True)
    place_piece(state, rc.MANDUBII, rc.ROMANS, rc.AUXILIA, 4)
    start = state['resources'][rc.ROMANS]
    result = build_place_ally(state, rc.MANDUBII, name)
    assert result == {'placed_ally_at': name, 'cost': 2}
    assert state['resources'][rc.ROMANS] == start - 2
    assert _unally_tribe(state, name) == rc.ROMANS
    assert _ally_tribe(state, name, rc.AEDUI)
    result = build_subdue(state, rc.MANDUBII, name, rc.AEDUI)
    assert result['subdued'] == name and result['cost'] == 2
    assert state['tribes'][name]['allied_faction'] is None
    assert state['resources'][rc.ROMANS] == start - 4
    clean(state)


@pytest.mark.parametrize('operation', ['build_place', 'build_subdue', 'entreat'])
def test_colony_ally_operations_reject_the_wrong_region_before_payment(operation):
    state = board()
    name = colony(state, rc.MANDUBII, rc.AEDUI, subdued=operation == 'build_place')
    place_piece(state, rc.CARNUTES, rc.ROMANS if operation != 'entreat' else rc.ARVERNI,
                rc.AUXILIA if operation != 'entreat' else rc.WARBAND, 4)
    before = encode(state)
    with pytest.raises(CommandError, match='not in'):
        if operation == 'build_place':
            build_place_ally(state, rc.CARNUTES, name)
        elif operation == 'build_subdue':
            build_subdue(state, rc.CARNUTES, name, rc.AEDUI)
        else:
            entreat_replace_ally(state, rc.CARNUTES, rc.AEDUI, name)
    assert encode(state) == before


def test_entreat_replaces_the_selected_colony_and_offers_its_identity():
    state = board()
    name = colony(state, rc.BITURIGES, rc.AEDUI)
    place_piece(state, rc.BITURIGES, rc.ARVERNI, rc.WARBAND, 4)
    assert (name, rc.AEDUI) in _enemy_ally_tribes(state, rc.BITURIGES, rc.ARVERNI)
    result = entreat_replace_ally(state, rc.BITURIGES, rc.AEDUI, name)
    assert result['arverni_placed'] and result['cost'] == 1
    assert state['tribes'][name]['allied_faction'] == rc.ARVERNI
    clean(state)


@pytest.mark.parametrize('owner', [None, rc.ROMANS, rc.AEDUI, rc.BELGAE])
@pytest.mark.parametrize('agreed', [False, True])
def test_trade_counts_colony_by_owner_control_and_roman_agreement(owner, agreed):
    state = board()
    place_piece(state, rc.AEDUI_REGION, rc.AEDUI, rc.WARBAND, 4)
    agreements = {f: True for f in rc.FACTIONS}
    baseline = trade(deepcopy(state), agreements, roman_agreed=agreed)['resources_gained']
    colony(state, rc.AEDUI_REGION, rc.AEDUI, subdued=True)
    if owner is not None:
        assert _ally_tribe(state, 'Settlers at ' + rc.AEDUI_REGION, owner)
    result = trade(state, agreements, roman_agreed=agreed)
    value = 2 if agreed else 1
    extra = value if owner in (None, rc.AEDUI) or (owner == rc.ROMANS and agreed) else 0
    assert result['resources_gained'] == baseline + extra
    clean(state)


@pytest.mark.parametrize('scenario', rc.ALL_SCENARIOS)
@pytest.mark.parametrize('status', [rc.DISPERSED, rc.DISPERSED_GATHERING])
def test_dispersed_colony_reduces_belgic_control_value(scenario, status):
    state = board(scenario)
    name = colony(state, rc.MORINI, rc.BELGAE, subdued=True)
    place_piece(state, rc.MORINI, rc.BELGAE, rc.WARBAND, 4)
    before = calculate_victory_score(state, rc.BELGAE)
    state['tribes'][name]['status'] = status
    assert calculate_victory_score(state, rc.BELGAE) == before - 1
    # A Colony outside Belgic Control never changes their score.
    for _ in range(5):
        place_piece(state, rc.MORINI, rc.ROMANS, rc.AUXILIA)
    score = calculate_victory_score(state, rc.BELGAE)
    state['tribes'][name]['status'] = None
    assert calculate_victory_score(state, rc.BELGAE) == score
    clean(state)


@pytest.mark.parametrize('region', [rc.CARNUTES, rc.MANDUBII, rc.PICTONES])
def test_acco_includes_colony_allies_only_in_its_two_regions(region):
    state = board()
    name = colony(state, region, rc.AEDUI)
    play(state, 34, rc.BELGAE, shaded=True)
    assert state['tribes'][name]['allied_faction'] == (
        rc.ARVERNI if region in (rc.CARNUTES, rc.MANDUBII) else rc.AEDUI)


@pytest.mark.parametrize('scenario', rc.ARIOVISTUS_SCENARIOS)
@pytest.mark.parametrize('region', [rc.SEQUANI, rc.MANDUBII])
def test_procillus_replaces_colony_within_one_of_caesar(scenario, region):
    state = board(scenario)
    name = colony(state, region, rc.GERMANS)
    place_piece(state, rc.SEQUANI, rc.ROMANS, rc.LEADER, leader_name=rc.CAESAR)
    play(state, 'A19', rc.BELGAE, {'replacements': [{'tribe': name}]})
    assert state['tribes'][name]['allied_faction'] == rc.ROMANS


def test_procillus_does_not_replace_a_colony_outside_caesars_range():
    state = board(rc.SCENARIO_ARIOVISTUS)
    name = colony(state, rc.MORINI, rc.GERMANS)
    place_piece(state, rc.SEQUANI, rc.ROMANS, rc.LEADER, leader_name=rc.CAESAR)
    assert _ally_tribe(state, rc.TRIBE_SEQUANI, rc.GERMANS)
    play(state, 'A19', rc.BELGAE, {'replacements': [{'tribe': name}]})
    assert state['tribes'][name]['allied_faction'] == rc.GERMANS
    assert state['tribes'][rc.TRIBE_SEQUANI]['allied_faction'] == rc.GERMANS


def test_terminal_seize_offers_colony_without_mutating_the_live_board():
    from fs_bot.cli.human_plan import _collect_seize
    state = board()
    name = colony(state, rc.MANDUBII, subdued=True)
    place_piece(state, rc.MANDUBII, rc.ROMANS, rc.AUXILIA, 4)
    before = encode(state)
    stream = StringIO(f'{rc.MANDUBII}\n{name}\nFinish Dispersal (Forage still occurs)\n')
    result = _collect_seize(state, rc.ROMANS, stream, StringIO(), True)
    assert result['disperse_tribes'] == {rc.MANDUBII: [name]}
    assert stream.read() == '' and encode(state) == before


def test_terminal_build_can_select_the_colony_and_execute_its_exact_plan(monkeypatch):
    from fs_bot.cli import roman_timing, human_plan
    from fs_bot.engine.execute import _execute_build
    state = board()
    name = colony(state, rc.MANDUBII, subdued=True)
    place_piece(state, rc.MANDUBII, rc.ROMANS, rc.LEADER, leader_name=rc.CAESAR)
    place_piece(state, rc.MANDUBII, rc.ROMANS, rc.AUXILIA, 4)
    before = encode(state)
    monkeypatch.setattr(human_plan, '_pick_regions', lambda *a, **k: [rc.MANDUBII])
    monkeypatch.setattr(roman_timing, 'prompt_choice', lambda _i, _o, _p, options:
                        next((v for _, v in options if v == name), None))
    regions, extra = roman_timing.collect_build(state, rc.ROMANS, StringIO(), StringIO())
    assert regions == [rc.MANDUBII] and encode(state) == before
    assert extra['build_plan']['allies'] == [{'region': rc.MANDUBII, 'tribe': name}]
    result = _execute_build(state, rc.ROMANS, {'sa': rc.SA_BUILD, 'details': extra})
    assert result['executed'] and not result['errors'], result
    assert state['tribes'][name]['allied_faction'] == rc.ROMANS
    clean(state)


def test_roman_bot_build_includes_an_unrestricted_colony():
    from fs_bot.bots.roman_bot import node_r_build
    state = board()
    name = colony(state, rc.MANDUBII, subdued=True)
    for tribe in (rc.TRIBE_MANDUBII, rc.TRIBE_SENONES, rc.TRIBE_LINGONES):
        assert _ally_tribe(state, tribe, rc.ROMANS)
    place_piece(state, rc.MANDUBII, rc.ROMANS, rc.LEADER, leader_name=rc.CAESAR)
    place_piece(state, rc.MANDUBII, rc.ROMANS, rc.AUXILIA, 4)
    plan = node_r_build(state, allowed_regions={rc.MANDUBII})
    assert {'region': rc.MANDUBII, 'tribe': name} in plan['allies']
    clean(state)


def test_arverni_bot_entreat_includes_the_colony_disc():
    from fs_bot.bots.arverni_bot import _check_entreat
    state = board()
    name = colony(state, rc.BITURIGES, rc.AEDUI)
    place_piece(state, rc.BITURIGES, rc.ARVERNI, rc.LEADER, leader_name=rc.VERCINGETORIX)
    place_piece(state, rc.BITURIGES, rc.ARVERNI, rc.WARBAND, 4)
    actions = _check_entreat(state, state['scenario'], allowed_regions={rc.BITURIGES})
    assert any(entry.get('tribe') == name and entry['action'] == 'replace_ally'
               for entry in actions)
    clean(state)


def test_accepted_colony_seize_survives_pause_save_resume_and_replay(tmp_path):
    from fs_bot.cli.display import HumanTurnDisplay
    from fs_bot.engine.game_engine import _action_transaction
    from fs_bot.state.serialize import save_game, load_game
    from fs_bot.tests.test_raid_intimidate_decisions import _driver
    from fs_bot.tools.seat_session import SeatSession
    state = board()
    name = colony(state, rc.MANDUBII, subdued=True)
    place_piece(state, rc.MANDUBII, rc.ROMANS, rc.AUXILIA, 4)
    decision = seize(rc.MANDUBII, [name])
    request = {'kind': 'turn', 'options': ['command'], 'position': '1st_eligible'}
    initial = deepcopy(state)
    session = SeatSession(state, {'seat': rc.ROMANS}, [], HumanTurnDisplay(StringIO()))
    session.import_inbox([{'response': decision}])

    def step(current, pause=False):
        def agent(live, faction, req):
            if req.get('source') == 'seize':
                if pause:
                    raise EOFError('pause after the Colony marker and first Rally roll')
                return {'decline': True}
            return current.reactive(live, faction, req)
        current.state['decision_agent'] = agent
        with _action_transaction(current.state, _driver(current)):
            accepted = current.ask(current.state, rc.ROMANS, request)
            return execute_decision(current.state, rc.ROMANS, accepted)

    # Seed 317 offers Rally in this fixture after the first or second roll.
    before = encode(board_copy(state))
    with pytest.raises(EOFError):
        step(session, pause=True)
    assert encode(board_copy(state)) == before
    path = tmp_path / 'colony.json'
    save_game(state, path, meta=session.meta, log=session.log)
    restored, meta, log = load_game(path, validate=True)
    resumed = SeatSession(restored, meta, log, HumanTurnDisplay(StringIO()))
    assert step(resumed)['executed']
    resumed.finish()
    assert restored['tribes'][name]['status'] == rc.DISPERSED
    assert decode(log[0]['assistant_response']) == decision
    replayed = SeatSession(initial, {'seat': rc.ROMANS}, [], HumanTurnDisplay(StringIO()))
    replayed.import_inbox([{'response': decode(log[0]['assistant_response'])}])
    assert step(replayed)['executed']
    replayed.finish()
    assert replayed.log == log
    assert encode(board_copy(initial)) == encode(board_copy(restored))
    clean(restored)
