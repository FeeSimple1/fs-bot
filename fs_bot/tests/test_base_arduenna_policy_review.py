"""Independent positions for the owner-adopted PR-11 Arduenna forecast.

These assertions use printed Loss arithmetic and observable board changes,
not the optimizer's enumeration, scoring, or cache implementation.
"""
from copy import deepcopy
from random import Random

import pytest

from fs_bot import rules_consts as rc
from fs_bot.battle.losses import calculate_losses
from fs_bot.board.pieces import count_pieces, place_piece
from fs_bot.cards import arduenna
from fs_bot.engine.free_actions import execute_free_action_plan
from fs_bot.engine.victory import calculate_victory_margin
from fs_bot.state.serialize import encode
from fs_bot.state.state_schema import build_initial_state, validate_state


def position(*, roman_bot=True):
    state = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=411)
    state.update(current_card=67, next_card=3,
                 non_player_factions={rc.ARVERNI, rc.AEDUI, rc.BELGAE})
    if roman_bot:
        state['non_player_factions'].add(rc.ROMANS)
    return state


def battle_position(*, roman_bot=True, retreat=True, legions=3):
    state = position(roman_bot=roman_bot)
    place_piece(state, rc.NERVII, rc.ARVERNI, rc.WARBAND, 4)
    place_piece(state, rc.NERVII, rc.ROMANS, rc.LEGION, legions,
                from_legions_track=True)
    if retreat:
        place_piece(state, rc.MORINI, rc.ROMANS, rc.AUXILIA)
    assert validate_state(state) == []
    return state


@pytest.mark.parametrize('roman_bot', [False, True], ids=['protective-human', 'printed-roman-bot'])
def test_retreat_forecast_uses_one_legion_loss_instead_of_two(roman_bot):
    from fs_bot.cards import base_arduenna_np as policy
    state = battle_position(roman_bot=roman_bot)
    before = encode(state)
    # Four Warbands inflict two Losses when the Romans stand, one if they
    # Retreat to Roman-controlled Morini. No Auxilia absorb either amount.
    assert calculate_losses(state, rc.NERVII, rc.ARVERNI, rc.ROMANS) == 2
    assert calculate_losses(state, rc.NERVII, rc.ARVERNI, rc.ROMANS,
                            is_retreat=True) == 1
    assert policy.predicted_legion_losses(state, rc.NERVII) == 1
    assert encode(state) == before


def test_roman_bot_without_a_safe_retreat_keeps_standing_forecast():
    from fs_bot.cards import base_arduenna_np as policy
    state = battle_position(retreat=False)
    assert policy.predicted_legion_losses(state, rc.NERVII) == 2


def test_best_defender_roll_convention_counts_two_losses_not_one_expected_death():
    from fs_bot.cards import base_arduenna_np as policy
    state = battle_position(retreat=False, legions=2)
    before = encode(state)
    # Each of the two Legion-directed Losses counts under the adopted
    # favorable-Defender-roll convention; neither is discounted to 50%.
    assert policy.predicted_legion_losses(state, rc.NERVII) == 2
    assert encode(state) == before


def test_vercingetorix_route_cannot_rely_on_a_lucky_harassment_save():
    from fs_bot.cards import base_arduenna_np as policy
    state = position()
    place_piece(state, rc.VENETI, rc.ARVERNI, rc.LEADER,
                leader_name=rc.VERCINGETORIX)
    place_piece(state, rc.VENETI, rc.ARVERNI, rc.WARBAND, 2)
    place_piece(state, rc.NERVII, rc.ROMANS, rc.LEGION,
                from_legions_track=True)
    assert policy.available(state)
    # The only profitable two-step route crosses Atrebates. Three German
    # Harassment Losses exhaust the two Warbands and force a Vercingetorix
    # roll; §8.7.1 forbids that risk even though a lucky survivor could hit
    # the isolated Legion. Germans cannot promise to waive Harassment.
    place_piece(state, rc.ATREBATES, rc.GERMANS, rc.WARBAND, 9)
    before = encode(state)
    assert not policy.available(state)
    assert policy.plan(state) is None
    assert encode(state) == before and validate_state(state) == []


class NoPredictionRolls(Random):
    """Fail even on a copied RNG: a prediction cannot inspect future dice."""

    def random(self):
        pytest.fail('Arduenna prediction sampled future random outcomes')

    def getrandbits(self, _bits):
        pytest.fail('Arduenna prediction sampled future random outcomes')


def test_scoring_availability_and_deterministic_planning_never_roll_or_ask_players():
    from fs_bot.cards import base_arduenna_np as policy
    state = battle_position(roman_bot=False)
    safe_rng = NoPredictionRolls()
    safe_rng.setstate(state['rng'].getstate())
    state['rng'] = safe_rng
    calls = []

    def forbid_input(*args):
        calls.append(args)
        pytest.fail('Arduenna prediction consumed a live human response')

    state['decision_agent'] = forbid_input
    before = encode({key: value for key, value in state.items() if key != 'decision_agent'})
    assert policy.predicted_legion_losses(state, rc.NERVII) == 1
    assert policy.available(state)
    assert policy.plan(state, choose=False) is not None
    assert not calls
    assert encode({key: value for key, value in state.items() if key != 'decision_agent'}) == before


def test_real_sequence_keeps_human_standing_choice_and_real_successful_saves():
    from fs_bot.cards import base_arduenna_np as policy
    from fs_bot.engine.agent import RETREAT
    state = battle_position(roman_bot=False)
    choices, rolls = [], []

    class SuccessfulSaves(Random):
        def randint(self, low, high):
            rolls.append((low, high))
            return high

    def human(board, faction, request):
        if request.get('kind') == RETREAT:
            assert faction == rc.ROMANS and rc.MORINI in request['legal_regions']
            choices.append('stand')
            return {'retreat': False}
        return None

    state['rng'] = SuccessfulSaves(411)
    state['decision_agent'] = human
    assert policy.predicted_legion_losses(state, rc.NERVII) == 1
    assert not choices and not rolls
    results = policy.default_sequence(state)
    assert results and choices == ['stand']
    # The forecast considered protective Retreat and favorable Defender
    # removals. Actual human play and two successful saves override neither:
    # Romans stand, lose no Legion, and Counterattack with all three Legions.
    assert rolls == [(1, 6), (1, 6)]
    assert state['fallen_legions'] == 0
    assert count_pieces(state, rc.NERVII, rc.ROMANS, rc.LEGION) == 3
    assert count_pieces(state, rc.MORINI, rc.ROMANS, rc.LEGION) == 0
    assert count_pieces(state, rc.NERVII, rc.ARVERNI, rc.WARBAND) == 1
    assert state['resources'][rc.ARVERNI] == 0
    assert validate_state(state) == []


def march_from(origin):
    return {'command': rc.CMD_MARCH, 'regions': [origin], 'sa': 'No SA',
            'sa_regions': [], 'details': {'march_plan': {
                'origins': [origin], 'destinations': [rc.TREVERI],
                'routes': {origin: [rc.TREVERI]},
                'groups': {origin: {rc.WARBAND: 2}}}}}


def after_march(state, action):
    board = deepcopy(state)
    result = execute_free_action_plan(board, rc.ARVERNI,
                                     arduenna.march_request(67), action)
    assert result['executed'] and validate_state(board) == []
    return board


def test_frost_distinguishes_departure_control_despite_identical_arrivals():
    from fs_bot.cards import base_arduenna_np as policy
    state = position()
    state['next_card'] = rc.WINTER_CARD
    state['non_player_factions'] = {rc.ARVERNI, rc.AEDUI, rc.ROMANS}
    # Fifteen Control points: the human Belgae are exactly at their threshold.
    for region in (rc.MORINI, rc.CARNUTES, rc.VENETI, rc.PICTONES,
                   rc.BITURIGES, rc.ARVERNI_REGION, rc.BRITANNIA,
                   rc.PROVINCIA, rc.AEDUI_REGION):
        place_piece(state, region, rc.BELGAE, rc.WARBAND)
    place_piece(state, rc.ATREBATES, rc.BELGAE, rc.WARBAND)
    for origin in (rc.ATREBATES, rc.SEQUANI):
        place_piece(state, origin, rc.ARVERNI, rc.WARBAND, 2)
    place_piece(state, rc.TREVERI, rc.ROMANS, rc.LEGION,
                from_legions_track=True)
    assert calculate_victory_margin(state, rc.BELGAE) == 0
    before = encode(state)
    unsafe = after_march(state, march_from(rc.ATREBATES))
    safe = after_march(state, march_from(rc.SEQUANI))
    assert count_pieces(unsafe, rc.TREVERI, rc.ARVERNI, rc.WARBAND) == 2
    assert count_pieces(safe, rc.TREVERI, rc.ARVERNI, rc.WARBAND) == 2
    assert calculate_victory_margin(unsafe, rc.BELGAE) == 3
    assert calculate_victory_margin(safe, rc.BELGAE) == 0
    # The useful safe option must survive optimization, and its selected
    # departure must not give the human Belgae victory by Control alone.
    assert policy.available(state)
    selected = policy.plan(state, choose=False)
    assert selected is not None and selected['march'] is not None
    assert selected['predicted_legion_losses'] > 0
    actual = after_march(state, selected['march'])
    assert calculate_victory_margin(actual, rc.BELGAE) == 0
    assert encode(state) == before


def test_frost_checks_real_roll_branches_beyond_favorable_battle_forecast():
    from fs_bot.battle.resolve import resolve_battle
    from fs_bot.cards import base_arduenna_np as policy
    from fs_bot.cards.card_effects import _ally_tribe
    state = position()
    state['non_player_factions'] = {rc.ARVERNI, rc.ROMANS, rc.BELGAE}
    place_piece(state, rc.NERVII, rc.ARVERNI, rc.LEADER,
                leader_name=rc.VERCINGETORIX)
    place_piece(state, rc.NERVII, rc.ARVERNI, rc.WARBAND, 4)
    place_piece(state, rc.NERVII, rc.ROMANS, rc.LEGION, 6,
                from_legions_track=True)
    assert _ally_tribe(state, rc.TRIBE_NERVII, rc.ARVERNI)
    assert _ally_tribe(state, rc.TRIBE_AEDUI, rc.AEDUI)
    assert calculate_victory_margin(state, rc.AEDUI) == 0
    # Favorable Defender rolls remove three Legions; the remaining three
    # merely remove Warbands in Counterattack, leaving the Ally untouched.
    assert policy.predicted_legion_losses(state, rc.NERVII) == 3
    assert policy.available(state)

    class Rolls:
        def __init__(self):
            self.values = iter([6, 6, 6, 1])

        def randint(self, low, high):
            return next(self.values)

    actual = deepcopy(state)
    actual['rng'] = Rolls()
    resolve_battle(actual, rc.NERVII, rc.ARVERNI, rc.ROMANS)
    # Three successful Roman saves leave all six Legions to Counterattack.
    # Four Warbands, a failed Leader save, then the Ally are removed: human
    # Aedui acquire a winning margin through the Arverni action alone.
    assert count_pieces(actual, rc.NERVII, rc.ARVERNI, rc.ALLY) == 0
    assert calculate_victory_margin(actual, rc.AEDUI) == 1
    assert validate_state(actual) == []
    state['next_card'] = rc.WINTER_CARD
    before = encode(state)
    assert not policy.available(state)
    assert policy.plan(state, choose=False) is None
    assert encode(state) == before
