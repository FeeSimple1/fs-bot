"""Printed Belgic Litaviccus targeting, with owner-adopted PR-12 responses."""
from copy import deepcopy

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.control import refresh_all_control
from fs_bot.board.pieces import count_pieces, place_piece
from fs_bot.cards.event_conditions import np_event_available
from fs_bot.engine import execute as ex
from fs_bot.state.serialize import encode
from fs_bot.state.state_schema import build_initial_state, validate_state


def board(*, humans=(), seed=1, scenario=rc.SCENARIO_GREAT_REVOLT):
    state = build_initial_state(scenario, seed=seed)
    state['non_player_factions'] = {rc.ROMANS, rc.ARVERNI, rc.AEDUI, rc.BELGAE} - set(humans)
    return state


def forces(state, region, *, belgae=0, aedui=0, auxilia=0, legions=0):
    for faction, piece, number in ((rc.BELGAE, rc.WARBAND, belgae),
                                   (rc.AEDUI, rc.WARBAND, aedui),
                                   (rc.ROMANS, rc.AUXILIA, auxilia)):
        if number:
            place_piece(state, region, faction, piece, number)
    if legions:
        place_piece(state, region, rc.ROMANS, rc.LEGION, legions, from_legions_track=True)
    refresh_all_control(state)


def physical(state):
    return encode({key: value for key, value in state.items() if key != 'decision_agent'})


def plan(state, **kwargs):
    from fs_bot.cards.litaviccus_np import plan as choose_plan
    return choose_plan(state, **kwargs)


def predicted_legion_losses(state, region):
    from fs_bot.cards.litaviccus_np import predicted_legion_losses as forecast
    return forecast(state, region)


def test_npc_targets_legion_losses_instead_of_largest_roman_stack():
    state = board()
    forces(state, rc.MANDUBII, belgae=4, auxilia=8, legions=1)
    forces(state, rc.CARNUTES, belgae=8, auxilia=1, legions=2)
    before = deepcopy(state)
    result = ex._resolve_card45_battle(state, rc.BELGAE)[0]
    assert result['region'] == rc.CARNUTES
    assert plan(before)['region'] == rc.CARNUTES
    assert np_event_available(before, 45, rc.BELGAE, True)
    assert count_pieces(state, rc.MANDUBII, rc.ROMANS, rc.AUXILIA) == 8
    assert validate_state(state) == []


def test_no_legion_losses_is_no_belgae_even_with_an_auxilia_target():
    from fs_bot.bots.bot_common import should_decline_event
    state = board()
    forces(state, rc.CARNUTES, aedui=4, auxilia=2)
    assert not np_event_available(state, 45, rc.BELGAE, True)
    assert should_decline_event(state, 45, rc.BELGAE)
    before = physical(state)
    result = ex._resolve_card45_battle(state, rc.BELGAE)[0]
    assert result['declined_no_effect']
    assert physical(state) == before


def test_small_combined_force_can_qualify_without_normal_threat_trigger():
    state = board()
    forces(state, rc.CARNUTES, aedui=2, legions=1)
    assert predicted_legion_losses(state, rc.CARNUTES) == 1
    assert plan(state) == {'region': rc.CARNUTES, 'predicted_legion_losses': 1}


def test_mandatory_ambush_counts_aedui_hidden_but_keeps_belgic_leader_range():
    state = board(humans=(rc.ROMANS,))
    forces(state, rc.CARNUTES, belgae=1, aedui=3, auxilia=1, legions=2)
    forces(state, rc.ATREBATES, auxilia=1)
    # Without a Belgic Leader in range, Romans can Retreat to shield Legions.
    no_leader = predicted_legion_losses(state, rc.CARNUTES)
    place_piece(state, rc.ATREBATES, rc.BELGAE, rc.LEADER, leader_name=rc.AMBIORIX)
    # Three borrowed Hidden Warbands plus one native beat one Hidden Auxilia.
    with_leader = predicted_legion_losses(state, rc.CARNUTES)
    assert no_leader == 0
    assert with_leader == 1


def test_preview_leaves_live_board_rng_and_human_input_untouched():
    state = board(humans=(rc.ROMANS,))
    forces(state, rc.CARNUTES, belgae=8, legions=2)
    forces(state, rc.ATREBATES, auxilia=2)
    state['decision_agent'] = lambda *args: pytest.fail('Preview consumed live input')
    before = physical(state)
    assert predicted_legion_losses(state, rc.CARNUTES) > 0
    assert plan(state)
    assert np_event_available(state, 45, rc.BELGAE, True)
    assert physical(state) == before


def test_equal_scoring_regions_use_seeded_tie_only_on_live_selection():
    state = board()
    forces(state, rc.CARNUTES, belgae=6, legions=1)
    forces(state, rc.PICTONES, belgae=6, legions=1)
    before = state['rng'].getstate()
    assert plan(state)['region'] == sorted((rc.CARNUTES, rc.PICTONES))[0]
    assert state['rng'].getstate() == before
    same = deepcopy(state)
    chosen = plan(state, choose=True)
    assert chosen == plan(same, choose=True)
    assert state['rng'].getstate() != before


def test_human_belgae_remain_free_to_battle_without_forcing_legion_losses():
    state = board(humans=(rc.BELGAE,))
    forces(state, rc.CARNUTES, belgae=4, auxilia=2)
    requests = []
    def agent(current, actor, request):
        if request.get('request_type') == 'fixed_event_battle':
            requests.append(request)
            return {'region': rc.CARNUTES, 'defender': rc.ROMANS}
        return None
    state['decision_agent'] = agent
    result = ex._resolve_card45_battle(state, rc.BELGAE)[0]
    assert requests
    assert result['result']['executed']


@pytest.mark.parametrize('edition', ['legacy', 'original', 'second-edition'])
def test_numeric45_target_policy_is_the_same_in_all_base_card_editions(edition):
    state = board()
    state['card_edition'] = edition
    forces(state, rc.CARNUTES, belgae=4, legions=1)
    assert plan(state)['region'] == rc.CARNUTES


def test_numeric45_policy_does_not_bleed_into_ariovistus_a45():
    state = board(scenario=rc.SCENARIO_ARIOVISTUS)
    forces(state, rc.CARNUTES, belgae=6, legions=1)
    assert plan(state) is None
    assert np_event_available(state, 'A45', rc.ROMANS, True) is None


def test_positive_legion_score_still_requires_inflicting_more_losses_than_suffering():
    state = board()
    forces(state, rc.CARNUTES, belgae=2, legions=4)
    assert predicted_legion_losses(state, rc.CARNUTES) == 1
    assert plan(state) is None
    assert not np_event_available(state, 45, rc.BELGAE, True)


def test_ambiorix_must_not_face_a_loss_even_when_attack_outscores_counterattack():
    from fs_bot.cards.capabilities import activate_capability, set_capability_owner
    from fs_bot.board.pieces import flip_piece
    state = board()
    forces(state, rc.CARNUTES, belgae=1, legions=6)
    flip_piece(state, rc.CARNUTES, rc.BELGAE, rc.WARBAND, 1,
               from_state=rc.HIDDEN, to_state=rc.REVEALED)
    place_piece(state, rc.CARNUTES, rc.BELGAE, rc.LEADER, leader_name=rc.AMBIORIX)
    activate_capability(state, 59, rc.EVENT_SHADED)
    set_capability_owner(state, 59, rc.BELGAE)
    # Furious Horse doubles two Attack Losses to four. The two surviving
    # Legions force a Warband Loss and then a Loss on Ambiorix.
    assert predicted_legion_losses(state, rc.CARNUTES) == 4
    assert plan(state) is None


def test_ambush_abatis_halves_losses_before_the_legion_forecast():
    state = board()
    forces(state, rc.CARNUTES, belgae=6, legions=2)
    place_piece(state, rc.ATREBATES, rc.BELGAE, rc.LEADER, leader_name=rc.AMBIORIX)
    state['markers'].setdefault(rc.CARNUTES, {})[rc.MARKER_ABATIS] = rc.ROMANS
    # Abatis halves six Warbands to one Loss. With no Retreat or Auxilia,
    # the two Legions absorb first, so the single forecast Loss removes one.
    assert predicted_legion_losses(state, rc.CARNUTES) == 1


def test_caesar_ambush_defense_roll_is_branched_separately_from_defender_saves():
    from fs_bot.cards.litaviccus_np import _outcomes
    state = board()
    forces(state, rc.CARNUTES, belgae=3, legions=2)
    place_piece(state, rc.ATREBATES, rc.BELGAE, rc.LEADER, leader_name=rc.AMBIORIX)
    place_piece(state, rc.CARNUTES, rc.ROMANS, rc.LEADER, leader_name=rc.CAESAR)
    # On escape Caesar's Counterattack makes the one-Legion Battle unsafe;
    # the other branch has no Counterattack. The planning must see both.
    outcomes = list(_outcomes(state, rc.CARNUTES))
    assert {safe for _, safe, _ in outcomes} == {False, True}
    assert predicted_legion_losses(state, rc.CARNUTES) == 1
    assert plan(state) is None


def test_frost_considers_npc_ties_between_native_and_borrowed_ally_casualties():
    from fs_bot.cards.capabilities import activate_capability, set_capability_owner
    from fs_bot.cards.litaviccus_np import _outcomes
    from fs_bot.engine.victory import calculate_victory_margin
    state = board(humans=(rc.AEDUI,))
    forces(state, rc.PICTONES, belgae=1, aedui=1, legions=3)
    for faction, tribe in ((rc.BELGAE, rc.TRIBE_PICTONES),
                           (rc.AEDUI, rc.TRIBE_SANTONES)):
        place_piece(state, rc.PICTONES, faction, rc.ALLY)
        state['tribes'][tribe]['allied_faction'] = faction
    activate_capability(state, 59, rc.EVENT_SHADED)
    set_capability_owner(state, 59, rc.BELGAE)
    refresh_all_control(state)
    assert calculate_victory_margin(state, rc.AEDUI) == 0
    assert plan(state)['predicted_legion_losses'] == 2
    state['frost'] = True
    before = physical(state)
    outcomes = list(_outcomes(state, rc.PICTONES, frost=True))
    # If all three Legions survive, Counterattack removes both Warbands
    # and an Ally. Removing the Belgic disc raises human Aedui above zero;
    # removing the equally prioritized Aedui disc does not.
    assert {permitted for _, _, permitted in outcomes} == {False, True}
    assert plan(state) is None
    assert physical(state) == before
    assert validate_state(state) == []


def test_safety_compares_requested_counterattack_losses_even_after_force_runs_out():
    from fs_bot.cards.capabilities import activate_capability, set_capability_owner
    from fs_bot.cards.litaviccus_np import _outcomes
    from fs_bot.tests.test_diviciacus_option import place_diviciacus
    state = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=1, diviciacus_option=True)
    state['non_player_factions'] = {rc.BELGAE, rc.AEDUI, rc.ROMANS, rc.ARVERNI}
    place_diviciacus(state)
    forces(state, rc.CARNUTES, aedui=1, legions=9)
    activate_capability(state, 59, rc.EVENT_SHADED)
    set_capability_owner(state, 59, rc.BELGAE)
    # The borrowed Warband + Diviciacus inflict three Losses; six surviving
    # Legions cause six Counterattack Losses even when their two targets
    # disappear after only two actual removals. Every die branch is unsafe.
    outcomes = list(_outcomes(state, rc.CARNUTES))
    assert {score for score, _, _ in outcomes} == {3}
    assert {safe for _, safe, _ in outcomes} == {False}
    assert plan(state) is None
