"""Named Event choices belong to their human seat, including durable retries."""
from copy import deepcopy
from io import StringIO

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces, place_piece, remove_piece
from fs_bot.cards.card_effects import _ally_tribe
from fs_bot.cli.display import HumanTurnDisplay
from fs_bot.engine.execute import _execute_event
from fs_bot.engine.game_engine import _action_transaction
from fs_bot.state.serialize import decode, encode, load_game, save_game
from fs_bot.state.state_schema import build_initial_state, validate_state
from fs_bot.tools.seat_session import DecisionPending, SeatSession, board_copy


def position(card, edition='original'):
    state = build_initial_state(
        rc.SCENARIO_ARIOVISTUS if card == 'A18' else rc.SCENARIO_GREAT_REVOLT,
        seed=614)
    state['card_edition'] = edition
    state['current_card'], state['next_card'] = card, 35
    state['executing_faction'] = rc.BELGAE
    state['event_params'] = None
    state['non_player_factions'] = {rc.BELGAE, rc.AEDUI}
    state['resources'].update({rc.ROMANS: 10, rc.ARVERNI: 10})
    state['senate'] = {'position': rc.INTRIGUE, 'firm': False}
    if card == 2:
        place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.LEGION,
                    from_legions_track=True)
        remove_piece(state, rc.PROVINCIA, rc.ROMANS, rc.LEGION, to_fallen=True)
    elif card in (18, 'A18'):
        place_piece(state, rc.SUGAMBRI, rc.ROMANS, rc.AUXILIA,
                    7 if card == 'A18' else 5)
        for visibility in (rc.HIDDEN, rc.REVEALED, rc.SCOUTED):
            place_piece(state, rc.SUGAMBRI, rc.GERMANS, rc.WARBAND,
                        piece_state=visibility)
        assert _ally_tribe(state, rc.TRIBE_SUGAMBRI, rc.GERMANS)
        if card == 'A18':
            place_piece(state, rc.SUGAMBRI, rc.GERMANS, rc.SETTLEMENT)
            place_piece(state, rc.SUGAMBRI, rc.GERMANS, rc.LEADER,
                        leader_name=rc.SUCCESSOR)
    elif card == 23:
        place_piece(state, rc.ARVERNI_REGION, rc.ROMANS, rc.AUXILIA, 2)
        assert _ally_tribe(state, rc.TRIBE_ARVERNI, rc.ARVERNI)
    else:
        place_piece(state, rc.ARVERNI_REGION, rc.ARVERNI, rc.LEADER,
                    leader_name=rc.VERCINGETORIX)
        assert _ally_tribe(state, rc.TRIBE_CADURCI, rc.AEDUI)
        assert _ally_tribe(state, rc.TRIBE_VOLCAE, rc.BELGAE)
    assert validate_state(state) == []
    return state


def owner(card):
    return rc.ARVERNI if card == 26 else rc.ROMANS


def event(state, card):
    action = {'command': rc.FIRST_DID_EVENT, 'regions': [], 'sa': 'No SA',
              'sa_regions': [], 'details': {
                  'card_id': card,
                  'text_preference': rc.EVENT_SHADED if card == 26 else rc.EVENT_UNSHADED,
                  'event_params': {},
              }}
    return _execute_event(state, rc.BELGAE, action, human=True)


def session(state, card, meta=None, log=None):
    output = StringIO()
    view = HumanTurnDisplay(output)
    ses = SeatSession(state, meta or {'seat': owner(card)},
                      [] if log is None else log, view)
    state['decision_agent'] = ses.reactive
    ses.output = output
    return ses


def step(ses, card):
    def driver(*args):
        pass
    driver.transaction_checkpoint = ses.checkpoint
    driver.transaction_restore = ses.restore
    with _action_transaction(ses.state, driver):
        return event(ses.state, card)


def submit(ses, response):
    ses.import_inbox({'decision_id': ses.data['pending']['id'], 'response': response})


def selected(card):
    return {
        2: {'legions_from_track': 1, 'legions_from_fallen': 1},
        18: {'target_region': rc.SUGAMBRI},
        'A18': {'target_region': rc.SUGAMBRI},
        23: {'target_city': rc.CITY_GERGOVIA},
        26: {'ally_removals': [rc.TRIBE_CADURCI],
             'ally_placements': [rc.TRIBE_CADURCI]},
    }[card]


def assert_effect(state, card):
    if card == 2:
        assert state['senate'] == {'position': rc.UPROAR, 'firm': False}
        assert state['fallen_legions'] == 0
        assert count_pieces(state, rc.PROVINCIA, rc.ROMANS, rc.LEGION) == 2
    elif card in (18, 'A18'):
        assert count_pieces(state, rc.SUGAMBRI, rc.GERMANS) == 0
        assert count_pieces(state, rc.SUGAMBRI, rc.ROMANS, rc.AUXILIA) == (7 if card == 'A18' else 5)
        assert state['tribes'][rc.TRIBE_SUGAMBRI]['allied_faction'] is None
    elif card == 23:
        assert state['tribes'][rc.TRIBE_ARVERNI]['allied_faction'] is None
        assert state['tribes'][rc.TRIBE_ARVERNI]['status'] == rc.MARKER_RAZED
        assert state['resources'][rc.ROMANS] == 18
        assert count_pieces(state, rc.ARVERNI_REGION, rc.ARVERNI, rc.ALLY) == 0
    assert validate_state(state) == []


def replay(initial, card, log):
    expected = [decode(entry['assistant_request']) for entry in log]
    answers = [decode(entry['assistant_response']) for entry in log]

    def respond(state, faction, request):
        assert dict(request, faction=faction) == expected.pop(0)
        return answers.pop(0)

    initial['decision_agent'] = respond
    result = event(initial, card)
    assert not expected and not answers
    return result


@pytest.mark.parametrize('card', [2, 18, 23, 26, 'A18'])
def test_named_owner_invalid_answers_keep_decision_board_rng_and_journal(card):
    state = position(card)
    ses = session(state, card)
    ses.display.remember(state, [owner(card)])
    state['resources'][owner(card)] += 1
    before = encode(board_copy(state))
    with pytest.raises(DecisionPending):
        step(ses, card)
    context = ses.output.getvalue()
    assert 'changes since your last decision' in context
    assert f'{owner(card)} Resources: 10 -> 11' in context
    assert rc.CARD_NAMES_BASE[35] in context
    assert (rc.CARD_NAMES_ARIOVISTUS[card] if card == 'A18'
            else rc.CARD_NAMES_BASE[card]) in context
    pending = deepcopy(ses.data['pending'])
    request = decode(pending['request'])
    assert request['kind'] == 'free_action'
    assert request['request_type'] == 'named_event_effect'
    assert request['faction'] == request['acting_faction'] == owner(card)
    assert request['card_id'] == card
    assert ses.data['journal'] == [] and ses.log == []
    bad_target = {
        2: {'legions_from_track': 3, 'legions_from_fallen': 0},
        18: {'target_region': rc.PROVINCIA},
        'A18': {'target_region': rc.PROVINCIA},
        23: {'target_city': rc.CITY_BIBRACTE},
        26: {'ally_removals': [rc.TRIBE_SEQUANI], 'ally_placements': []},
    }[card]
    for response in (None, {'use_default': 1}, dict(selected(card), acting_faction=rc.BELGAE), bad_target):
        submit(ses, response)
        with pytest.raises(DecisionPending):
            step(ses, card)
        assert ses.error
        assert ses.data['pending']['id'] == pending['id']
        assert ses.data['pending']['request'] == pending['request']
        assert ses.data['pending']['board'] == pending['board']
        assert encode(board_copy(state)) == before
        assert ses.data['journal'] == [] and ses.log == []


@pytest.mark.parametrize('edition', ['original', 'second-edition'])
@pytest.mark.parametrize('card', [2, 18, 23, 'A18'])
def test_roman_owner_acceptance_save_load_and_exact_replay(tmp_path, edition, card):
    state = position(card, edition)
    initial = deepcopy(state)
    ses = session(state, card)
    before = encode(board_copy(state))
    with pytest.raises(DecisionPending):
        step(ses, card)
    assert encode(board_copy(state)) == before
    submit(ses, selected(card))
    path = tmp_path / 'named-effect.json'
    save_game(state, path, meta=ses.meta, log=ses.log)
    restored, meta, log = load_game(path)
    resumed = session(restored, card, meta, log)
    result = step(resumed, card)
    resumed.finish()
    assert result['executed'] and len(log) == 1
    assert decode(log[0]['assistant_response']) == selected(card)
    assert_effect(restored, card)
    assert replay(initial, card, log) == result
    assert encode(board_copy(initial)) == encode(board_copy(restored))


@pytest.mark.parametrize('card', [2, 18, 23, 26, 'A18'])
def test_named_owner_can_decline_the_whole_optional_effect_without_mutation(card):
    state = position(card)
    ses = session(state, card)
    before = encode(board_copy(state))
    with pytest.raises(DecisionPending):
        step(ses, card)
    submit(ses, {'decline': True})
    result = step(ses, card)
    ses.finish()
    assert result['executed']
    # Event bookkeeping is outside the optional effect; physical facts and
    # the random stream are unchanged by a declined owner's benefit.
    after = encode(board_copy(state))
    for key in ('spaces', 'tribes', 'available', 'resources', 'senate',
                'legions_track', 'fallen_legions', 'rng', 'eligibility'):
        assert after[key] == before[key], key
    assert len(ses.log) == 1
    assert decode(ses.log[0]['assistant_response']) == {'decline': True}


@pytest.mark.parametrize('card', [2, 18, 23, 'A18'])
def test_explicit_default_is_recorded_as_a_choice_instead_of_missing_input(card):
    state = position(card)
    ses = session(state, card)
    before = encode(board_copy(state))
    with pytest.raises(DecisionPending):
        step(ses, card)
    assert encode(board_copy(state)) == before
    submit(ses, {'use_default': True})
    result = step(ses, card)
    ses.finish()
    assert result['executed']
    assert len(ses.log) == 1
    assert decode(ses.log[0]['assistant_response']) == {'use_default': True}
    assert validate_state(state) == []


@pytest.mark.parametrize('rearrange', ['empty', 'selected', 'default'])
def test_arverni_rearrangement_and_later_rally_are_distinct_saved_owner_choices(tmp_path, rearrange):
    state = position(26)
    initial = deepcopy(state)
    ses = session(state, 26)
    before = encode(board_copy(state))
    with pytest.raises(DecisionPending):
        step(ses, 26)
    first_id = ses.data['pending']['id']
    response = {'empty': {'ally_removals': [], 'ally_placements': []},
                'selected': selected(26), 'default': {'use_default': True}}[rearrange]
    submit(ses, response)
    with pytest.raises(DecisionPending):
        step(ses, 26)
    pending = deepcopy(ses.data['pending'])
    request = decode(pending['request'])
    assert request['request_type'] == 'event_rally'
    assert request['faction'] == rc.ARVERNI
    assert rc.ARVERNI_REGION in request['allowed_regions']
    assert rc.SUGAMBRI not in request['allowed_regions']
    assert pending['id'] != first_id
    assert len(ses.data['journal']) == 1 and ses.log == []
    assert decode(ses.data['journal'][0]['assistant_response']) == response
    preview = decode(pending['board'])
    assert preview['tribes'][rc.TRIBE_CADURCI]['allied_faction'] == (
        rc.AEDUI if rearrange == 'empty' else rc.ARVERNI)
    assert preview['tribes'][rc.TRIBE_VOLCAE]['allied_faction'] == (
        rc.ARVERNI if rearrange == 'default' else rc.BELGAE)
    assert encode(board_copy(state)) == before
    journal = deepcopy(ses.data['journal'])
    invalid = {'command': rc.CMD_RALLY, 'regions': [rc.SUGAMBRI], 'sa': 'No SA',
               'sa_regions': [], 'details': {'rally_plan': {'steps': [
                   {'region': rc.SUGAMBRI, 'action': 'place_warbands', 'count': 1}]}}}
    submit(ses, invalid)
    with pytest.raises(DecisionPending):
        step(ses, 26)
    assert ses.error and ses.data['pending']['id'] == pending['id']
    assert ses.data['journal'] == journal and encode(board_copy(state)) == before
    rally = {'command': rc.CMD_RALLY, 'regions': [rc.ARVERNI_REGION], 'sa': 'No SA',
             'sa_regions': [], 'details': {'rally_plan': {'steps': [
                 {'region': rc.ARVERNI_REGION, 'action': 'place_warbands', 'count': 1}]}}}
    submit(ses, rally)
    path = tmp_path / 'gobannitio-rally-pending.json'
    save_game(state, path, meta=ses.meta, log=ses.log)
    restored, meta, log = load_game(path)
    resumed = session(restored, 26, meta, log)
    result = step(resumed, 26)
    resumed.finish()
    assert result['executed'] and len(log) == 2
    assert count_pieces(restored, rc.ARVERNI_REGION, rc.ARVERNI, rc.WARBAND) == 1
    assert restored['resources'][rc.ARVERNI] == 10
    assert restored['tribes'][rc.TRIBE_CADURCI]['allied_faction'] == (
        rc.AEDUI if rearrange == 'empty' else rc.ARVERNI)
    assert validate_state(restored) == []
    assert replay(initial, 26, log) == result
    assert encode(board_copy(initial)) == encode(board_copy(restored))
