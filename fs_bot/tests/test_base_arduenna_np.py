"""PR-11 exact March cohorts, published modifiers, and live continuation."""
from copy import deepcopy

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces, count_pieces_by_state, place_piece
from fs_bot.cards import base_arduenna_np as policy
from fs_bot.cards.arduenna import march_request
from fs_bot.cards.capabilities import activate_capability, set_capability_owner
from fs_bot.engine.free_actions import execute_free_action_plan
from fs_bot.state.serialize import encode
from fs_bot.state.state_schema import build_initial_state, validate_state


def board():
    state = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=67)
    state.update(current_card=67, next_card=3, executing_faction=rc.ROMANS,
                 non_player_factions={rc.ROMANS, rc.ARVERNI, rc.AEDUI, rc.BELGAE})
    return state


def romans(state, region, legions=3, auxilia=0):
    place_piece(state, region, rc.ROMANS, rc.LEGION, legions, from_legions_track=True)
    if auxilia:
        place_piece(state, region, rc.ROMANS, rc.AUXILIA, auxilia)


@pytest.mark.parametrize('card,side,expected', [
    (None, None, 1), (13, rc.EVENT_UNSHADED, 0),
    (27, rc.EVENT_SHADED, 2), (59, rc.EVENT_SHADED, 3),
])
def test_canonical_prefire_and_once_command_capabilities_change_legion_forecast(card, side, expected):
    state = board()
    place_piece(state, rc.NERVII, rc.ARVERNI, rc.WARBAND, 6)
    romans(state, rc.NERVII, auxilia=2)
    if card:
        activate_capability(state, card, side)
        set_capability_owner(state, card, rc.ARVERNI)
    before = encode(state)
    assert policy.predicted_legion_losses(state, rc.NERVII) == expected
    assert encode(state) == before


def test_fort_halving_and_mobile_absorbers_are_both_used():
    state = board()
    place_piece(state, rc.NERVII, rc.ARVERNI, rc.WARBAND, 8)
    romans(state, rc.NERVII, auxilia=2)
    assert policy.predicted_legion_losses(state, rc.NERVII) == 2
    place_piece(state, rc.NERVII, rc.ROMANS, rc.FORT)
    assert policy.predicted_legion_losses(state, rc.NERVII) == 0


def test_prefire_cannot_be_evaluated_after_the_arverni_attack():
    state = board()
    place_piece(state, rc.NERVII, rc.ARVERNI, rc.LEADER, leader_name=rc.VERCINGETORIX)
    romans(state, rc.NERVII, legions=1, auxilia=2)
    activate_capability(state, 13, rc.EVENT_UNSHADED)
    assert policy.predicted_legion_losses(state, rc.NERVII) == 0
    assert not policy.available(state)


@pytest.mark.parametrize('reverse', [False, True])
@pytest.mark.parametrize('scouted', [0, 2, 4])
def test_detached_frozen_visibility_preview_matches_canonical_initial_cohort_executor(reverse, scouted):
    state = board()
    place_piece(state, rc.ATREBATES, rc.ARVERNI, rc.WARBAND, 6 - scouted)
    place_piece(state, rc.ATREBATES, rc.ARVERNI, rc.WARBAND, scouted, piece_state=rc.SCOUTED)
    place_piece(state, rc.NERVII, rc.ARVERNI, rc.WARBAND, 2, piece_state=rc.SCOUTED)
    moves = [
        {'origin': rc.ATREBATES, 'route': [rc.NERVII], 'group': {rc.WARBAND: 3}},
        {'origin': rc.ATREBATES, 'route': [rc.TREVERI], 'group': {rc.WARBAND: 3}},
        {'origin': rc.NERVII, 'route': [rc.TREVERI], 'group': {rc.WARBAND: 1}},
    ]
    if reverse:
        moves.reverse()
    actual = deepcopy(state)
    assert execute_free_action_plan(actual, rc.ARVERNI, march_request(67), policy._action(moves))['executed']
    forecast = policy._preview_moves(state, moves, {})
    forecast.pop('_diviciacus_preview')
    assert encode(forecast) == encode(actual)
    assert validate_state(actual) == []


def test_two_step_leader_preview_preserves_exact_survivors_and_scouted_origin():
    state = board()
    place_piece(state, rc.VENETI, rc.ARVERNI, rc.LEADER, leader_name=rc.VERCINGETORIX)
    place_piece(state, rc.VENETI, rc.ARVERNI, rc.WARBAND, 2)
    place_piece(state, rc.VENETI, rc.ARVERNI, rc.WARBAND, 3, piece_state=rc.SCOUTED)
    place_piece(state, rc.ATREBATES, rc.GERMANS, rc.WARBAND, 3)
    moves = [{'origin': rc.VENETI, 'route': [rc.ATREBATES, rc.NERVII],
              'group': {rc.WARBAND: 4, rc.LEADER: rc.VERCINGETORIX}}]
    agreements = {rc.ATREBATES: [(rc.GERMANS, 3)]}
    actual = deepcopy(state)
    policy._march(actual, policy._action(moves), agreements)
    forecast = policy._preview_moves(state, moves, agreements)
    forecast.pop('_diviciacus_preview')
    assert encode(forecast) == encode(actual)
    assert count_pieces(actual, rc.NERVII, rc.ARVERNI, rc.WARBAND) == 3
    assert count_pieces_by_state(actual, rc.VENETI, rc.ARVERNI, rc.WARBAND, rc.REVEALED) == 1
    assert validate_state(actual) == []


def test_binding_human_no_harassment_is_asked_once_and_honored_in_real_march():
    state = board()
    state['non_player_factions'].remove(rc.ROMANS)
    place_piece(state, rc.VENETI, rc.ARVERNI, rc.LEADER, leader_name=rc.VERCINGETORIX)
    place_piece(state, rc.VENETI, rc.ARVERNI, rc.WARBAND, 2)
    place_piece(state, rc.ATREBATES, rc.ROMANS, rc.AUXILIA, 9)
    romans(state, rc.NERVII, legions=1)
    calls = []
    def agent(current, faction, request):
        if request.get('request_type') == 'harassment':
            calls.append((faction, request['context']['region']))
            return False
        return None
    state['decision_agent'] = agent
    assert policy.available(state) and not calls
    selected = policy.plan(state, choose=True)
    assert selected is not None and calls == [(rc.ROMANS, rc.ATREBATES)]
    assert policy._march(state, selected['march'], selected['_harassers'])['executed']
    assert calls == [(rc.ROMANS, rc.ATREBATES)]
    assert count_pieces(state, rc.NERVII, rc.ARVERNI, rc.WARBAND) == 2
    assert validate_state(state) == []


def test_ineligible_no_legion_effect_declines_without_hiding_or_consuming_rng():
    state = board()
    place_piece(state, rc.NERVII, rc.ARVERNI, rc.WARBAND, 4, piece_state=rc.SCOUTED)
    before = encode(state)
    assert policy.default_sequence(state) == []
    assert encode(state) == before


def test_maximum_requires_multiple_origins_and_split_target_groups():
    state = board()
    place_piece(state, rc.ATREBATES, rc.ARVERNI, rc.WARBAND, 6)
    place_piece(state, rc.SEQUANI, rc.ARVERNI, rc.WARBAND, 2)
    romans(state, rc.NERVII, legions=2)
    romans(state, rc.TREVERI, legions=2)
    chosen = policy.plan(state)
    assert chosen['predicted_legion_losses'] == 4
    assert set(chosen['march']['regions']) == {rc.ATREBATES, rc.SEQUANI}
    assert chosen['march']['details']['march_plan']['extra_groups']
    assert set(chosen['battle_regions']) == set(policy.TARGETS)


def test_seeded_complete_plan_ties_repeat_exactly_and_allow_both_destinations():
    state = board()
    place_piece(state, rc.ATREBATES, rc.ARVERNI, rc.WARBAND, 2)
    romans(state, rc.NERVII, legions=1)
    romans(state, rc.TREVERI, legions=1)
    # With one target's entire Roman group removed, Retreat to the other
    # would halve the only Loss to zero; prevent that route with Arverni
    # residents. Either direction remains an equal useful reinforcement.
    place_piece(state, rc.NERVII, rc.ARVERNI, rc.WARBAND, 1)
    place_piece(state, rc.TREVERI, rc.ARVERNI, rc.WARBAND, 1)
    twin = deepcopy(state)
    seen = set()
    for _ in range(8):
        chosen = policy.plan(state, choose=True)
        assert chosen == policy.plan(twin, choose=True)
        seen.add(tuple(chosen['battle_regions']))
    assert len(seen) > 1


def test_first_roman_retreat_can_supply_second_targets_initially_absent_defender():
    state = board()
    place_piece(state, rc.NERVII, rc.ARVERNI, rc.WARBAND, 4)
    place_piece(state, rc.TREVERI, rc.ARVERNI, rc.WARBAND, 10)
    place_piece(state, rc.TREVERI, rc.AEDUI, rc.WARBAND, 11)
    romans(state, rc.NERVII, legions=4)
    assert policy.predicted_legion_losses(state, [rc.NERVII, rc.TREVERI]) == 4
    selected = policy.plan(state)
    assert selected['predicted_legion_losses'] == 4
    assert selected['battle_regions'] == [rc.NERVII, rc.TREVERI]


def test_human_removal_only_retreat_can_leave_the_second_target_empty():
    state = board()
    state['non_player_factions'].remove(rc.ROMANS)
    place_piece(state, rc.NERVII, rc.ARVERNI, rc.WARBAND, 4)
    place_piece(state, rc.TREVERI, rc.ARVERNI, rc.WARBAND, 10)
    place_piece(state, rc.TREVERI, rc.AEDUI, rc.WARBAND, 11)
    romans(state, rc.NERVII, legions=4)
    # Standing exposes two Legions. Declaring Retreat exposes one, then the
    # other three can be removed without creating a second Battle. Those
    # removals are Step 6 dispositions, not Attack Loss rolls.
    assert policy.predicted_legion_losses(state, [rc.NERVII, rc.TREVERI]) == 1


def test_abatis_saved_roll_consumes_a_loss_even_when_it_changes_no_board_piece():
    state = board()
    place_piece(state, rc.NERVII, rc.ARVERNI, rc.WARBAND, 8)
    romans(state, rc.NERVII, legions=2)
    place_piece(state, rc.MORINI, rc.ROMANS, rc.AUXILIA)
    state['markers'][rc.NERVII] = {rc.MARKER_ABATIS: rc.ROMANS}
    assert policy.predicted_legion_losses(state, rc.NERVII) == 1
    # Retreat puts Abatis first. It may absorb both Losses by saving twice,
    # or be removed and expose one Legion: both branches must survive memoization.
    outcomes = list(policy._outcomes(state, [rc.NERVII], frost=True, before=state))
    assert {score for score, _, _ in outcomes} == {0, 1}


def test_skipped_prospective_region_does_not_spend_once_command_capability():
    state = board()
    place_piece(state, rc.NERVII, rc.ARVERNI, rc.WARBAND, 4)
    place_piece(state, rc.TREVERI, rc.ARVERNI, rc.WARBAND, 2)
    romans(state, rc.TREVERI, legions=2)
    activate_capability(state, 59, rc.EVENT_SHADED)
    set_capability_owner(state, 59, rc.ARVERNI)
    assert policy.predicted_legion_losses(state, [rc.NERVII, rc.TREVERI]) == 2


def test_first_applicable_horse_bonus_waits_until_after_a_protected_battle():
    state = board()
    for region in policy.TARGETS:
        place_piece(state, region, rc.ARVERNI, rc.WARBAND, 4)
    romans(state, rc.NERVII, legions=2)
    place_piece(state, rc.NERVII, rc.ROMANS, rc.FORT)
    romans(state, rc.TREVERI, legions=3)
    activate_capability(state, 59, rc.EVENT_SHADED)
    set_capability_owner(state, 59, rc.ARVERNI)
    assert policy.predicted_legion_losses(state, [rc.NERVII, rc.TREVERI]) == 4


@pytest.mark.parametrize('frost', [False, True])
def test_diviciacus_defender_and_lender_may_decline_during_detached_forecast(frost):
    state = board()
    state['non_player_factions'] = {rc.ARVERNI, rc.BELGAE}
    place_piece(state, rc.NERVII, rc.ARVERNI, rc.WARBAND, 6)
    romans(state, rc.NERVII, legions=2, auxilia=1)
    place_piece(state, rc.NERVII, rc.AEDUI, rc.WARBAND, 2)
    activate_capability(state, 38, rc.EVENT_UNSHADED)
    before = encode(state)
    outcomes = list(policy._outcomes(state, [rc.NERVII], frost=frost, before=state))
    # If both humans agree the borrowed Warbands shield the Legions; either
    # may refuse. Inspect all responses because the minimum alone hides a
    # forecast which incorrectly forces consent.
    scores = {score for score, _, _ in outcomes}
    assert 0 in scores and 2 in scores
    assert encode(state) == before


def test_prefire_wipe_is_a_completed_battle_for_frost_before_the_next_region(monkeypatch):
    from fs_bot.cards import migration
    from fs_bot.engine.victory import calculate_victory_margin
    state = board()
    state['next_card'] = rc.WINTER_CARD
    state['non_player_factions'].remove(rc.BELGAE)
    for region in (rc.MORINI, rc.CARNUTES, rc.VENETI, rc.PICTONES,
                   rc.BITURIGES, rc.ARVERNI_REGION, rc.BRITANNIA,
                   rc.PROVINCIA, rc.AEDUI_REGION):
        place_piece(state, region, rc.BELGAE, rc.WARBAND)
    place_piece(state, rc.NERVII, rc.BELGAE, rc.WARBAND, 7)
    place_piece(state, rc.NERVII, rc.ARVERNI, rc.WARBAND, 6)
    place_piece(state, rc.TREVERI, rc.ARVERNI, rc.WARBAND, 4)
    romans(state, rc.NERVII, legions=1)
    romans(state, rc.TREVERI, legions=4)
    activate_capability(state, 27, rc.EVENT_SHADED)
    assert calculate_victory_margin(state, rc.BELGAE) == 0
    checked_intermediate = []
    original = migration._frost_ok

    def observe(before, after):
        if (count_pieces(after, rc.NERVII, rc.ROMANS, rc.LEGION) == 0
                and count_pieces(after, rc.TREVERI, rc.ROMANS, rc.LEGION) == 4
                and count_pieces(after, rc.TREVERI, rc.ARVERNI, rc.WARBAND) == 4):
            checked_intermediate.append(calculate_victory_margin(after, rc.BELGAE))
        return original(before, after)

    monkeypatch.setattr(migration, '_frost_ok', observe)
    list(policy._outcomes(state, policy.TARGETS, frost=True, before=state))
    # Card27 may remove the sole first defender before resolve_battle. That
    # completed Battle gives the human Belgae victory even if a later Roman
    # Retreat back into Nervii would take the new Control away again.
    assert 2 in checked_intermediate
