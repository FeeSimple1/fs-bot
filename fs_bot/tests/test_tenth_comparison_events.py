"""A51 and A69 printed prerequisites and §8.2.3 troop ownership."""

from copy import deepcopy

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces, get_available, place_piece
from fs_bot.bots.bot_common import should_decline_event
from fs_bot.bots.bot_dispatch import dispatch_bot_turn
from fs_bot.cards.card_effects import _ally_tribe, _unally_tribe
from fs_bot.cards.event_eval import is_event_effective
from fs_bot.cli.dispatcher import _translate_bot_action
from fs_bot.engine.execute import execute_decision
from fs_bot.engine.game_engine import ACTION_EVENT, get_first_eligible_options, get_sop_factions
from fs_bot.state.serialize import encode
from fs_bot.state.setup import _set_tribe_dispersed, _set_tribe_dispersed_gathering, setup_scenario
from fs_bot.state.state_schema import check_structural_integrity, validate_state


def check(state):
    assert validate_state(state) == check_structural_integrity(state) == []


def position(card, scenario=rc.SCENARIO_ARIOVISTUS):
    state = setup_scenario(scenario, seed=1)
    state.update(current_card=card, current_card_id=card, can_play_event=True,
                 non_player_factions=set(get_sop_factions(state)))
    return state


def assert_declines(state, faction):
    check(state)
    before = encode(state)
    assert should_decline_event(state, state['current_card'], faction)
    assert encode(state) == before

    control = deepcopy(state)
    control['can_play_event'] = False
    plan = dispatch_bot_turn(state, faction)
    assert plan['command'] != rc.FIRST_DID_EVENT
    assert plan == dispatch_bot_turn(control, faction)
    return plan


def play_bot(state, faction, plan):
    result = execute_decision(state, faction, {
        'action': _translate_bot_action(plan, get_first_eligible_options()),
        'bot_action': plan,
    })
    assert result['executed'] and not result.get('errors'), result
    check(state)
    return result


def play_bot_event(state, faction, *, shaded=False):
    check(state)
    plan = dispatch_bot_turn(state, faction)
    assert plan['command'] == rc.FIRST_DID_EVENT, plan
    result = play_bot(state, faction, plan)
    assert result['shaded'] is shaded
    return result


@pytest.mark.parametrize('scenario', rc.ARIOVISTUS_SCENARIOS)
@pytest.mark.parametrize('card,faction,tribe,owner', [
    ('A69', rc.BELGAE, rc.TRIBE_BELLOVACI, None),
    ('A69', rc.BELGAE, rc.TRIBE_BELLOVACI, rc.AEDUI),
    ('A51', rc.ROMANS, rc.TRIBE_REMI, rc.BELGAE),
    ('A51', rc.AEDUI, rc.TRIBE_REMI, rc.BELGAE),
])
def test_bot_continues_flowchart_when_event_tribe_condition_fails(scenario, card, faction, tribe, owner):
    state = position(card, scenario)
    _unally_tribe(state, tribe)
    if owner is not None:
        assert _ally_tribe(state, tribe, owner)
    plan = assert_declines(state, faction)
    assert not is_event_effective(state, card, shaded=card == 'A69')
    play_bot(state, faction, plan)


@pytest.mark.parametrize('disperse', [_set_tribe_dispersed, _set_tribe_dispersed_gathering])
def test_dispersed_remi_does_not_count_as_subdued(disperse):
    state = position('A51')
    _unally_tribe(state, rc.TRIBE_REMI)
    disperse(state, rc.TRIBE_REMI)
    assert_declines(state, rc.AEDUI)


@pytest.mark.parametrize('scenario', rc.ARIOVISTUS_SCENARIOS)
def test_belgic_bellovaci_places_warbands_and_ambushes(scenario):
    state = position('A69', scenario)
    before = count_pieces(state, rc.ATREBATES, rc.BELGAE, rc.WARBAND)
    result = play_bot_event(state, rc.BELGAE, shaded=True)
    assert count_pieces(state, rc.ATREBATES, rc.BELGAE, rc.WARBAND) == before + 6
    assert any(action['free_action'] == 'ambush' and action['result']['battle_sa_executed']
               for action in result['free_actions'])


def test_bellovaci_has_no_placement_or_ambush_without_available_warbands():
    state = position('A69')
    place_piece(state, rc.MORINI, rc.BELGAE, rc.WARBAND,
                get_available(state, rc.BELGAE, rc.WARBAND))
    assert_declines(state, rc.BELGAE)


def assert_bibrax_placements(state, faction, *, auxilia, warbands):
    troops = ((rc.ROMANS, rc.AUXILIA, auxilia), (rc.AEDUI, rc.WARBAND, warbands),
              (rc.ROMANS, rc.FORT, 1))
    expected = [(owner, piece, count_pieces(state, rc.ATREBATES, owner, piece) + delta)
                for owner, piece, delta in troops]
    play_bot_event(state, faction)
    for owner, piece, count in expected:
        assert count_pieces(state, rc.ATREBATES, owner, piece) == count
    assert count_pieces(state, rc.ATREBATES, rc.BELGAE, rc.WARBAND) == 0


@pytest.mark.parametrize('scenario', rc.ARIOVISTUS_SCENARIOS)
@pytest.mark.parametrize('faction,roman_bot,auxilia,warbands', [
    (rc.AEDUI, True, 0, 4),
    (rc.AEDUI, False, 0, 4),
    (rc.ROMANS, True, 4, 0),
])
def test_bibrax_bot_places_its_own_troops_and_the_roman_fort(scenario, faction, roman_bot, auxilia, warbands):
    state = position('A51', scenario)
    if not roman_bot:
        state['non_player_factions'].remove(rc.ROMANS)
    assert_bibrax_placements(state, faction, auxilia=auxilia, warbands=warbands)


@pytest.mark.parametrize('faction,piece,region,remi_owner,auxilia,warbands', [
    (rc.AEDUI, rc.WARBAND, rc.AEDUI_REGION, None, 0, 2),
    (rc.ROMANS, rc.AUXILIA, rc.PROVINCIA, rc.AEDUI, 2, 0),
])
def test_bibrax_can_place_fewer_own_troops_with_subdued_or_aedui_remi(
        faction, piece, region, remi_owner, auxilia, warbands):
    state = position('A51')
    _unally_tribe(state, rc.TRIBE_REMI)
    if remi_owner is not None:
        assert _ally_tribe(state, rc.TRIBE_REMI, remi_owner)
    place_piece(state, region, faction, piece, get_available(state, faction, piece) - 2)
    assert_bibrax_placements(state, faction, auxilia=auxilia, warbands=warbands)


@pytest.mark.parametrize('faction,piece,region,other,other_piece', [
    (rc.AEDUI, rc.WARBAND, rc.AEDUI_REGION, rc.ROMANS, rc.AUXILIA),
    (rc.ROMANS, rc.AUXILIA, rc.PROVINCIA, rc.AEDUI, rc.WARBAND),
])
def test_bibrax_bot_needs_own_troops_but_human_can_choose_other_faction(faction, piece, region, other, other_piece):
    state = position('A51')
    place_piece(state, region, faction, piece, get_available(state, faction, piece))
    human = deepcopy(state)
    assert_declines(state, faction)

    human['non_player_factions'].remove(faction)
    before_troops = count_pieces(human, rc.ATREBATES, other, other_piece)
    before_belgae = count_pieces(human, rc.ATREBATES, rc.BELGAE, rc.WARBAND)
    result = execute_decision(human, faction, {'action': ACTION_EVENT, 'player_action': {
        'command': rc.FIRST_DID_EVENT, 'details': {
            'card_id': 'A51', 'text_preference': rc.EVENT_UNSHADED,
            'event_params': {'piece_type': other_piece, 'warband_removals': []},
        },
    }})
    assert result['executed'] and not result.get('errors'), result
    assert count_pieces(human, rc.ATREBATES, other, other_piece) == before_troops + 4
    assert count_pieces(human, rc.ATREBATES, rc.BELGAE, rc.WARBAND) == before_belgae
    check(human)
