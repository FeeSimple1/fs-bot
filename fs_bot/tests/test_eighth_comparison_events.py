"""Legiones, Pompey, Gallia Togata and Forced Marches bot regressions."""

from copy import deepcopy

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import (
    _count_on_legions_track, count_pieces, count_pieces_by_state,
    get_leader_in_region, place_piece,
)
from fs_bot.bots.bot_common import should_decline_event
from fs_bot.bots.bot_dispatch import dispatch_bot_turn
from fs_bot.cards.capabilities import activate_capability
from fs_bot.cards.card_effects import _ally_tribe, execute_card_5
from fs_bot.cards.event_eval import is_event_effective
from fs_bot.engine.execute import _derive_event_params, execute_decision
from fs_bot.engine.game_engine import ACTION_EVENT, get_sop_factions
from fs_bot.state.serialize import encode
from fs_bot.state.setup import setup_scenario
from fs_bot.state.state_schema import (
    build_initial_state, check_structural_integrity, validate_state,
)


def _ready(state, card):
    state.update(current_card=card, current_card_id=card, can_play_event=True,
                 non_player_factions=set(get_sop_factions(state)))
    return state


def _position(card, scenario=rc.SCENARIO_GREAT_REVOLT):
    state = _ready(build_initial_state(scenario, seed=1), card)
    place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.FORT)
    state['resources'].update({faction: 10 for faction in get_sop_factions(state)})
    return state


def _roman_pieces(state, region, piece, count=1, **options):
    place_piece(state, region, rc.ROMANS, piece, count,
                from_legions_track=piece == rc.LEGION, **options)


def _check(state):
    assert validate_state(state) == check_structural_integrity(state) == []


def _assert_declines(state, faction):
    before = encode(state)
    assert should_decline_event(state, state['current_card'], faction)
    assert encode(state) == before
    control = deepcopy(state)
    control['can_play_event'] = False
    actual = dispatch_bot_turn(state, faction)
    assert actual == dispatch_bot_turn(control, faction)
    assert actual['command'] != rc.FIRST_DID_EVENT


def _play(state, faction, action=None):
    _check(state)
    action = action if action is not None else dispatch_bot_turn(state, faction)
    assert action['command'] == rc.FIRST_DID_EVENT, action
    result = execute_decision(state, faction, {'action': ACTION_EVENT, 'bot_action': action})
    assert result['executed'] and not result.get('errors'), result
    _check(state)
    return result


@pytest.mark.parametrize('scenario', [rc.SCENARIO_GREAT_REVOLT, rc.SCENARIO_ARIOVISTUS])
@pytest.mark.parametrize('remote_legion', [False, True])
def test_belgae_decline_legiones_without_a_local_legion(scenario, remote_legion):
    state = _position(2, scenario)
    place_piece(state, rc.CARNUTES, rc.BELGAE, rc.WARBAND, 2)
    _roman_pieces(state, rc.CARNUTES, rc.AUXILIA)
    if remote_legion:
        _roman_pieces(state, rc.SEQUANI, rc.LEGION)
    _check(state)
    positive = deepcopy(state)
    _assert_declines(state, rc.BELGAE)

    _roman_pieces(positive, rc.CARNUTES, rc.LEGION)
    result = _play(positive, rc.BELGAE)
    attack = result['free_actions'][0]['result']['attack']
    assert attack['auto_legion_removed'] == 1
    assert count_pieces(positive, rc.CARNUTES, rc.ROMANS, rc.LEGION) == 0
    assert count_pieces(positive, rc.CARNUTES, rc.ROMANS, rc.AUXILIA) == 1


def test_belgae_decline_legiones_when_the_attack_cannot_cause_a_loss():
    state = _position(2)
    place_piece(state, rc.CARNUTES, rc.BELGAE, rc.WARBAND)
    _roman_pieces(state, rc.CARNUTES, rc.LEGION)
    _check(state)
    _assert_declines(state, rc.BELGAE)


def test_legiones_availability_includes_slingers_before_the_attack():
    state = _position(2)
    place_piece(state, rc.CARNUTES, rc.BELGAE, rc.WARBAND, 2)
    _roman_pieces(state, rc.CARNUTES, rc.LEGION)
    _roman_pieces(state, rc.CARNUTES, rc.AUXILIA, 2)
    activate_capability(state, 13, rc.EVENT_UNSHADED)
    _check(state)
    _assert_declines(state, rc.BELGAE)


def test_legiones_bot_targets_the_larger_legion_loss_over_more_roman_pieces():
    state = _position(2)
    place_piece(state, rc.CARNUTES, rc.BELGAE, rc.WARBAND, 4)
    _roman_pieces(state, rc.CARNUTES, rc.LEGION)
    _roman_pieces(state, rc.CARNUTES, rc.AUXILIA, 5)
    # Eight Warbands force two Losses even if the Roman bot Retreats.
    place_piece(state, rc.SEQUANI, rc.BELGAE, rc.WARBAND, 8)
    _roman_pieces(state, rc.SEQUANI, rc.LEGION, 3)
    action = {'command': rc.FIRST_DID_EVENT, 'details': {'text_preference': rc.EVENT_SHADED}}
    result = _play(state, rc.BELGAE, action)
    assert result['free_actions'][0]['region'] == rc.SEQUANI
    battle = result['free_actions'][0]['result']
    assert battle['defender_retreated']
    assert battle['attack']['auto_legion_removed'] == 1
    assert battle['attack']['losses_requested'] == 1
    assert count_pieces(state, rc.CARNUTES, rc.ROMANS, rc.LEGION) == 1


def test_human_legiones_can_battle_an_auxilia_without_a_legion():
    state = _position(2)
    state['non_player_factions'].discard(rc.BELGAE)
    place_piece(state, rc.CARNUTES, rc.BELGAE, rc.WARBAND, 2)
    _roman_pieces(state, rc.CARNUTES, rc.AUXILIA)
    result = execute_decision(state, rc.BELGAE, {'action': ACTION_EVENT, 'player_action': {
        'command': rc.FIRST_DID_EVENT, 'details': {'text_preference': rc.EVENT_SHADED,
                                                 'event_params': {'battle_region': rc.CARNUTES}}}})
    assert result['executed']
    assert count_pieces(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA) == 0
    _check(state)


@pytest.mark.parametrize('card', [3, 5], ids=['pompey', 'gallia-togata'])
def test_arverni_decline_roman_removals_until_the_printed_condition_is_met(card):
    state = _position(card)
    track = 5 if card == 3 else 10
    _roman_pieces(state, rc.PROVINCIA, rc.LEGION, _count_on_legions_track(state) - track)
    _roman_pieces(state, rc.PROVINCIA, rc.AUXILIA, 2)
    state['senate']['position'] = rc.ADULATION
    _check(state)
    positive = deepcopy(state)

    assert not is_event_effective(state, card, shaded=True)
    _assert_declines(state, rc.ARVERNI)
    if card == 3:
        _roman_pieces(positive, rc.PROVINCIA, rc.LEGION)
        assert _count_on_legions_track(positive) == 4
    else:
        positive['senate']['position'] = rc.INTRIGUE
    _play(positive, rc.ARVERNI)
    assert _count_on_legions_track(positive) == (6 if card == 3 else 11)
    assert count_pieces(positive, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA) == (2 if card == 3 else 0)


@pytest.mark.parametrize('card,scenario', [(5, rc.SCENARIO_GREAT_REVOLT), ('A5', rc.SCENARIO_ARIOVISTUS)])
def test_gallia_togata_is_effective_with_only_one_removable_auxilia(card, scenario):
    state = _position(card, scenario)
    state['senate']['position'] = rc.INTRIGUE
    assert not is_event_effective(state, card, shaded=True)
    _roman_pieces(state, rc.PROVINCIA, rc.AUXILIA)
    assert is_event_effective(state, card, shaded=True)
    assert is_event_effective(state, card, shaded=False)


@pytest.mark.parametrize('shaded', [False, True])
def test_roman_forced_marches_relocates_original_pieces_and_hides_moved_auxilia(shaded):
    state = _position(32)
    _roman_pieces(state, rc.PROVINCIA, rc.LEADER, leader_name=rc.CAESAR)
    _roman_pieces(state, rc.PROVINCIA, rc.LEGION, 2)
    _roman_pieces(state, rc.PROVINCIA, rc.AUXILIA, 5)
    _roman_pieces(state, rc.PROVINCIA, rc.AUXILIA, 13, piece_state=rc.REVEALED)
    assert _ally_tribe(state, rc.TRIBE_BITURIGES, rc.ARVERNI)
    state['resources'][rc.ROMANS] = 0
    state['frost'] = True
    before = encode(state)
    state['decision_agent'] = lambda *_: pytest.fail('Event preview asked a live agent')
    assert not should_decline_event(state, 32, rc.ROMANS)
    assert encode({k: v for k, v in state.items() if k != 'decision_agent'}) == before
    state.pop('decision_agent')
    action = dispatch_bot_turn(state, rc.ROMANS)
    if shaded:
        action['details']['text_preference'] = rc.EVENT_SHADED
    result = _play(state, rc.ROMANS, action)

    assert get_leader_in_region(state, rc.BITURIGES, rc.ROMANS) == rc.CAESAR
    assert count_pieces(state, rc.BITURIGES, rc.ROMANS, rc.LEGION) == 2
    assert count_pieces_by_state(state, rc.BITURIGES, rc.ROMANS, rc.AUXILIA, rc.HIDDEN) == 18
    assert count_pieces(state, rc.PROVINCIA, rc.ROMANS) == 1
    assert state['resources'][rc.ROMANS] == 0
    assert not result.get('free_actions')


def test_roman_forced_marches_uses_pax_setup_and_keeps_britannia_pieces():
    state = _ready(setup_scenario(rc.SCENARIO_PAX_GALLICA, seed=1), 32)
    assert get_leader_in_region(state, rc.BRITANNIA, rc.ROMANS) == rc.CAESAR
    before = deepcopy(state['spaces'][rc.BRITANNIA])
    mainland = deepcopy(state['spaces'])
    _play(state, rc.ROMANS)
    assert state['spaces'][rc.BRITANNIA] == before
    assert any(state['spaces'][r] != mainland[r] for r in mainland if r != rc.BRITANNIA)


def test_roman_forced_marches_declines_when_only_britannia_has_mobile_romans():
    state = _position(32)
    _roman_pieces(state, rc.BRITANNIA, rc.LEADER, leader_name=rc.CAESAR)
    _roman_pieces(state, rc.BRITANNIA, rc.AUXILIA, 3)
    assert _ally_tribe(state, rc.TRIBE_BITURIGES, rc.ARVERNI)
    _check(state)
    _assert_declines(state, rc.ROMANS)


def test_roman_forced_marches_selects_a_legal_cisalpina_origin():
    state = _position(32)
    execute_card_5(state)
    _roman_pieces(state, rc.CISALPINA, rc.LEGION, 2)
    _roman_pieces(state, rc.CISALPINA, rc.LEADER, leader_name=rc.CAESAR)
    assert _ally_tribe(state, rc.TRIBE_BITURIGES, rc.ARVERNI)
    assert _ally_tribe(state, rc.TRIBE_CATUVELLAUNI, rc.BELGAE)
    plan = _derive_event_params(state, rc.ROMANS, 32, False)
    assert plan and plan['moves']
    assert {(row['from_region'], row['to_region']) for row in plan['moves']} == {
        (rc.CISALPINA, rc.BITURIGES)}
    _play(state, rc.ROMANS)
    assert count_pieces(state, rc.BITURIGES, rc.ROMANS, rc.LEGION) == 2


def test_roman_forced_marches_ties_only_advance_rng_during_live_planning():
    destinations = set()
    for seed in range(12):
        state = _ready(build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=seed), 32)
        place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.FORT)
        _roman_pieces(state, rc.PROVINCIA, rc.AUXILIA, 13)
        _roman_pieces(state, rc.PROVINCIA, rc.LEGION, 2)
        assert _ally_tribe(state, rc.TRIBE_BITURIGES, rc.ARVERNI)
        assert _ally_tribe(state, rc.TRIBE_CARNUTES, rc.ARVERNI)
        before = encode(state)
        assert not should_decline_event(state, 32, rc.ROMANS)
        assert encode(state) == before
        plan = _derive_event_params(state, rc.ROMANS, 32, False)
        destinations.add(plan['moves'][0]['to_region'])
        assert encode(state)['rng'] != before['rng']
    assert destinations == {rc.CARNUTES, rc.BITURIGES}
