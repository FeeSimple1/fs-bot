"""Card 38 / A1.4: agreements change acting type, not physical colour."""
from copy import deepcopy

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import (place_piece, count_pieces, count_pieces_by_state,
    remove_piece, get_available, flip_piece, move_piece, get_leader_in_region)
from fs_bot.board.control import calculate_control
from fs_bot.cards.card_effects import execute_event
from fs_bot.engine.diviciacus import (KEY, eligible_regions, force_scope,
    placement_available)
from fs_bot.engine.execute import execute_decision, _march_with_harassment
from fs_bot.battle.losses import calculate_losses, resolve_losses
from fs_bot.state.state_schema import build_initial_state, validate_state
from fs_bot.state.serialize import encode


def board(*, leader=False, region=rc.CARNUTES):
    state = build_initial_state(rc.SCENARIO_ARIOVISTUS if leader else rc.SCENARIO_GREAT_REVOLT, seed=11)
    state['non_player_factions'] = set()
    state['resources'][rc.ROMANS] = state['resources'][rc.AEDUI] = 20
    place_piece(state, region, rc.ROMANS, rc.AUXILIA)
    place_piece(state, region, rc.AEDUI, rc.WARBAND, 2)
    if leader:
        place_piece(state, region, rc.AEDUI, rc.LEADER, leader_name=rc.DIVICIACUS)
    else:
        execute_event(state, 38)
    state['decision_agent'] = lambda s, f, r: True if r['kind'] == 'agreement' else None
    return state


def physical(state):
    return encode({k: v for k, v in state.items() if k != 'decision_agent'})


@pytest.mark.parametrize('actor,piece,lender,loan', [
    (rc.ROMANS, rc.AUXILIA, rc.AEDUI, rc.WARBAND),
    (rc.AEDUI, rc.WARBAND, rc.ROMANS, rc.AUXILIA),
])
def test_force_view_converts_type_and_preserves_control_inventory(actor, piece, lender, loan):
    state = board()
    snapshot = physical(state)
    control = calculate_control(state, rc.CARNUTES)
    with force_scope(state, actor, [rc.CARNUTES]):
        assert count_pieces(state, rc.CARNUTES, actor, piece) == 3
        assert count_pieces(state, rc.CARNUTES, lender, loan) == 0
        assert calculate_control(state, rc.CARNUTES) == control
        assert validate_state(state) == []
    assert physical(state) == snapshot


def test_card38_excludes_sa_but_leader_includes_nearby_sa():
    state = board()
    assert rc.CARNUTES in eligible_regions(state, rc.ROMANS)
    assert not eligible_regions(state, rc.ROMANS, 'special_ability')
    state = board(leader=True)
    assert rc.CARNUTES in eligible_regions(state, rc.ROMANS, 'special_ability')
    place_piece(state, rc.NERVII, rc.ROMANS, rc.AUXILIA)
    place_piece(state, rc.NERVII, rc.AEDUI, rc.WARBAND)
    assert rc.NERVII not in eligible_regions(state, rc.ROMANS)
    remove_piece(state, rc.CARNUTES, rc.AEDUI, rc.LEADER)
    assert not eligible_regions(state, rc.ROMANS)


def test_borrowed_warbands_get_auxilia_modifier_and_return_to_aedui_pool():
    state = board()
    before = get_available(state, rc.AEDUI, rc.WARBAND)
    with force_scope(state, rc.ROMANS, [rc.CARNUTES]):
        assert calculate_losses(state, rc.CARNUTES, rc.ROMANS, rc.BELGAE, double_auxilia=True) == 3
        resolve_losses(state, rc.CARNUTES, rc.ROMANS, 2)
    assert count_pieces(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA) == 1
    assert count_pieces(state, rc.CARNUTES, rc.AEDUI, rc.WARBAND) == 0
    assert get_available(state, rc.AEDUI, rc.WARBAND) == before + 2
    assert validate_state(state) == []


def test_human_loss_choice_preserves_partner_pieces():
    state = board()
    def choose(s, faction, request):
        if request['kind'] == 'loss_order':
            assert (rc.AUXILIA, rc.HIDDEN, rc.AEDUI) in request['pieces']
            return [(rc.AUXILIA, rc.HIDDEN, rc.ROMANS)]
    state['decision_agent'] = choose
    with force_scope(state, rc.ROMANS, [rc.CARNUTES]):
        resolve_losses(state, rc.CARNUTES, rc.ROMANS, 1)
    assert count_pieces(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA) == 0
    assert count_pieces(state, rc.CARNUTES, rc.AEDUI, rc.WARBAND) == 2


def test_refused_human_command_rolls_back_and_does_not_charge():
    state = board()
    state['decision_agent'] = lambda *args: False
    before = physical(state)
    result = execute_decision(state, rc.ROMANS, {'player_action': {
        'command': 'March', 'sa': 'No SA', 'details': {
            'diviciacus_regions': [rc.CARNUTES], 'origins': [rc.CARNUTES],
            'destinations': [rc.MANDUBII], 'routes': {rc.CARNUTES: [rc.MANDUBII]},
            'groups': {rc.CARNUTES: {rc.AUXILIA: 3}}}}})
    assert not result['executed'] and result['rolled_back']
    assert physical(state) == before


def test_interrupted_agreement_leaves_no_force_context():
    state = board()
    def pause(*args):
        raise EOFError
    state['decision_agent'] = pause
    before = physical(state)
    with pytest.raises(EOFError):
        execute_decision(state, rc.ROMANS, {'player_action': {
            'command': 'Seize', 'sa': 'No SA',
            'details': {'diviciacus_regions': [rc.CARNUTES]}}})
    assert KEY not in state and physical(state) == before


@pytest.mark.parametrize('loss,drop', [(True, False), (False, True)])
def test_march_keeps_arriving_owner_after_partner_loss_or_dropoff(loss, drop):
    state = board(region=rc.MORINI)
    # Both physical colours are resident in the transit Region, so that
    # Region also lends a cohort. Residents must never replace a casualty.
    place_piece(state, rc.NERVII, rc.ROMANS, rc.AUXILIA)
    place_piece(state, rc.NERVII, rc.AEDUI, rc.WARBAND)
    # Choose one native Auxilia and one blue borrowed Warband at formation.
    def choose(s, f, req):
        if req['kind'] == 'diviciacus_pieces':
            return {'counts': {rc.ROMANS: 1, rc.AEDUI: 1}} if req['phase'] == 'formation' else {'counts': {rc.AEDUI: 1}}
        return None
    state['decision_agent'] = choose
    with force_scope(state, rc.ROMANS, [rc.MORINI, rc.NERVII]):
        final = _march_with_harassment(state, rc.ROMANS, rc.MORINI,
            [rc.NERVII, rc.ATREBATES], group_cap={rc.AUXILIA: 2},
            harassers_by_region={rc.NERVII: [(rc.BELGAE, 3)] if loss else []},
            dropoffs_by_region={rc.NERVII: {rc.AUXILIA: 1}} if drop else {})
        assert final == rc.ATREBATES
    assert count_pieces(state, rc.ATREBATES, rc.ROMANS, rc.AUXILIA) == 1
    assert count_pieces(state, rc.ATREBATES, rc.AEDUI, rc.WARBAND) == 0
    assert count_pieces(state, rc.NERVII, rc.ROMANS, rc.AUXILIA) == 1
    assert count_pieces(state, rc.NERVII, rc.AEDUI, rc.WARBAND) == (2 if drop else 1)
    assert validate_state(state) == []


def test_borrowed_march_keeps_roman_distance_after_leaving_diviciacus_range():
    state = board(leader=True, region=rc.MORINI)
    with force_scope(state, rc.ROMANS, [rc.MORINI]):
        assert _march_with_harassment(state, rc.ROMANS, rc.MORINI,
            [rc.NERVII, rc.ATREBATES], group_cap={rc.AUXILIA: 3},
            harassers_by_region={rc.NERVII: []}) == rc.ATREBATES
    assert count_pieces(state, rc.ATREBATES, rc.AEDUI, rc.WARBAND) == 2
    assert count_pieces(state, rc.ATREBATES, rc.ROMANS, rc.AUXILIA) == 1
    assert validate_state(state) == []


@pytest.mark.parametrize('leader', [False, True])
def test_native_only_group_can_continue_after_leaving_cooperation_origin(leader):
    # §3.2.2 allows any group from the origin, including only native pieces.
    state = board(leader=leader, region=rc.MORINI)
    state['decision_agent'] = lambda s, f, request: (
        {'counts': {rc.ROMANS: 1}}
        if request['kind'] == 'diviciacus_pieces' else None)
    with force_scope(state, rc.ROMANS, [rc.MORINI]):
        final = _march_with_harassment(state, rc.ROMANS, rc.MORINI,
            [rc.NERVII, rc.ATREBATES], group_cap={rc.AUXILIA: 1},
            harassers_by_region={rc.NERVII: []})
    assert final == rc.ATREBATES
    assert count_pieces(state, rc.ATREBATES, rc.ROMANS, rc.AUXILIA) == 1
    assert count_pieces(state, rc.MORINI, rc.AEDUI, rc.WARBAND) == 2
    assert count_pieces(state, rc.ATREBATES, rc.AEDUI, rc.WARBAND) == 0
    assert KEY not in state and validate_state(state) == []


@pytest.mark.parametrize('leader', [False, True])
@pytest.mark.parametrize('drop', [False, True])
def test_native_survivors_continue_three_steps_after_last_borrowed_piece_leaves(leader, drop):
    # Card 38/A1.4 changes acting type, not ownership. §3.2.2 permits the
    # surviving group with Caesar to continue after a loss or dropoff.
    state = board(leader=leader, region=rc.MORINI)
    place_piece(state, rc.MORINI, rc.ROMANS, rc.LEADER, leader_name=rc.CAESAR)
    # A new transit Region contains both colours, but its residents were
    # never selected at the origin and must not join the moving group.
    place_piece(state, rc.ATREBATES, rc.ROMANS, rc.AUXILIA, 2)
    place_piece(state, rc.ATREBATES, rc.AEDUI, rc.WARBAND, 2)
    def choose(s, f, request):
        if request['kind'] == 'diviciacus_pieces':
            return {'counts': {rc.ROMANS: 1, rc.AEDUI: 1}} if request['phase'] == 'formation' else {'counts': {rc.AEDUI: 1}}
        return None
    state['decision_agent'] = choose
    with force_scope(state, rc.ROMANS, [rc.MORINI]):
        final = _march_with_harassment(state, rc.ROMANS, rc.MORINI,
            [rc.NERVII, rc.ATREBATES, rc.CARNUTES],
            group_cap={rc.AUXILIA: 2, rc.LEADER: rc.CAESAR},
            harassers_by_region={rc.NERVII: [] if drop else [(rc.BELGAE, 3)],
                                rc.ATREBATES: []},
            dropoffs_by_region={rc.NERVII: {rc.AUXILIA: 1}} if drop else {})
    assert final == rc.CARNUTES
    assert get_leader_in_region(state, rc.CARNUTES, rc.ROMANS) == rc.CAESAR
    assert count_pieces(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA) == 1
    assert count_pieces(state, rc.CARNUTES, rc.AEDUI, rc.WARBAND) == 0
    assert count_pieces(state, rc.ATREBATES, rc.ROMANS, rc.AUXILIA) == 2
    assert count_pieces(state, rc.ATREBATES, rc.AEDUI, rc.WARBAND) == 2
    assert count_pieces(state, rc.NERVII, rc.AEDUI, rc.WARBAND) == int(drop)
    assert KEY not in state and validate_state(state) == []


@pytest.mark.parametrize('actor,piece,other,otherpiece', [
    (rc.ROMANS, rc.AUXILIA, rc.AEDUI, rc.WARBAND),
    (rc.AEDUI, rc.WARBAND, rc.ROMANS, rc.AUXILIA),
])
def test_human_placement_uses_selected_physical_pool(actor, piece, other, otherpiece):
    state = board()
    before = deepcopy(state['available'])
    state['decision_agent'] = lambda s, f, r: {'counts': {other: r['count']}}
    with force_scope(state, actor, [rc.CARNUTES]):
        place_piece(state, rc.CARNUTES, actor, piece, 2)
    assert get_available(state, actor, piece) == before[actor][piece]
    assert get_available(state, other, otherpiece) == before[other][otherpiece] - 2
    assert validate_state(state) == []


def test_nonplayer_placement_respects_original_pool_restrictions():
    state = board()
    state['non_player_factions'] = {rc.ROMANS, rc.AEDUI}
    with force_scope(state, rc.ROMANS, [rc.CARNUTES]):
        assert placement_available(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA, 0) == 0
    with force_scope(state, rc.AEDUI, [rc.CARNUTES]):
        assert placement_available(state, rc.CARNUTES, rc.AEDUI, rc.WARBAND, 1) == 1
        assert placement_available(state, rc.CARNUTES, rc.AEDUI, rc.WARBAND, 0) == state['available'][rc.ROMANS][rc.AUXILIA]
    state['non_player_factions'] = {rc.AEDUI}
    with force_scope(state, rc.AEDUI, [rc.CARNUTES]):
        assert placement_available(state, rc.CARNUTES, rc.AEDUI, rc.WARBAND, 0) == 0


def test_a28_combined_force_and_diviciacus_do_not_double_count_or_lose_allies():
    from fs_bot.battle.combined import combined_force
    state = board(leader=True)
    place_piece(state, rc.CARNUTES, rc.ARVERNI, rc.WARBAND, 4)
    pools = deepcopy(state['available'])
    with combined_force(state, rc.AEDUI, {rc.CARNUTES: [rc.ROMANS, rc.ARVERNI]}):
        with force_scope(state, rc.AEDUI, [rc.CARNUTES]):
            assert count_pieces(state, rc.CARNUTES, rc.AEDUI, rc.WARBAND) == 7
            assert count_pieces(state, rc.CARNUTES, rc.AEDUI, rc.AUXILIA) == 0
            assert count_pieces(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA) == 0
            state['decision_agent'] = lambda s, f, r: [(rc.WARBAND, rc.HIDDEN, rc.ARVERNI)] if r['kind'] == 'loss_order' else None
            resolve_losses(state, rc.CARNUTES, rc.AEDUI, 1)
    assert count_pieces(state, rc.CARNUTES, rc.ARVERNI, rc.WARBAND) == 3
    assert get_available(state, rc.ARVERNI, rc.WARBAND) == pools[rc.ARVERNI][rc.WARBAND] + 1
    assert validate_state(state) == []


def test_leader_allows_converted_special_ability_placement():
    from fs_bot.commands.sa_suborn import suborn
    state = board(leader=True)
    before = deepcopy(state['available'])
    state['decision_agent'] = lambda s, f, r: {'counts': {rc.ROMANS: r['count']}} if r['kind'] == 'diviciacus_pieces' else None
    with force_scope(state, rc.AEDUI, [rc.CARNUTES], 'special_ability'):
        result = suborn(state, rc.CARNUTES, [{'action': 'place', 'faction': rc.AEDUI, 'piece_type': rc.WARBAND}])
    assert result['cost'] == 1
    assert get_available(state, rc.AEDUI, rc.WARBAND) == before[rc.AEDUI][rc.WARBAND]
    assert get_available(state, rc.ROMANS, rc.AUXILIA) == before[rc.ROMANS][rc.AUXILIA] - 1
    assert validate_state(state) == []


def test_mechanical_march_group_tracks_physical_colour_without_engine_wrapper():
    from fs_bot.commands.march import march_from_origin
    state = board(region=rc.MORINI)
    place_piece(state, rc.NERVII, rc.ROMANS, rc.AUXILIA)
    place_piece(state, rc.NERVII, rc.AEDUI, rc.WARBAND)
    with force_scope(state, rc.ROMANS, [rc.MORINI, rc.NERVII]):
        march_from_origin(state, rc.ROMANS, rc.MORINI,
            [({rc.AUXILIA: 3}, [rc.NERVII, rc.ATREBATES])])
    assert count_pieces(state, rc.NERVII, rc.AEDUI, rc.WARBAND) == 1
    assert count_pieces(state, rc.NERVII, rc.ROMANS, rc.AUXILIA) == 1
    assert count_pieces(state, rc.ATREBATES, rc.AEDUI, rc.WARBAND) == 2
    assert count_pieces(state, rc.ATREBATES, rc.ROMANS, rc.AUXILIA) == 1
    assert validate_state(state) == []


def test_defensive_agreement_can_block_ambush_as_a_legal_reaction():
    state = board(leader=True, region=rc.NERVII)
    place_piece(state, rc.NERVII, rc.BELGAE, rc.LEADER, leader_name=rc.BODUOGNATUS)
    place_piece(state, rc.NERVII, rc.BELGAE, rc.WARBAND, 3)
    state['resources'][rc.BELGAE] = 10
    result = execute_decision(state, rc.BELGAE, {'player_action': {
        'command': 'Battle', 'sa': 'Ambush', 'sa_regions': [rc.NERVII],
        'details': {'battle_plan': [{'region': rc.NERVII, 'target': rc.ROMANS}]}}})
    assert result['executed'] and not result['errors']
    assert result['ambush_blocked_by_diviciacus'] == [rc.NERVII]
    assert not result['battle_sa_executed']
    assert KEY not in state
    assert validate_state(state) == []


def test_post_command_sa_losing_cooperation_declines_without_losing_march():
    # A1.4's enhanced scope is checked when the SA actually occurs. March
    # can separate the two physical colours that were together at planning.
    state = board(leader=True, region=rc.CARNUTES)
    action = {'command': 'March', 'sa': 'Scout', 'sa_timing': 'after',
        'sa_regions': [rc.CARNUTES], 'details': {
        'diviciacus_regions': [], 'diviciacus_sa_regions': [rc.CARNUTES],
        'origins': [rc.CARNUTES], 'destinations': [rc.MANDUBII],
        'routes': {rc.CARNUTES: [rc.MANDUBII]},
        'groups': {rc.CARNUTES: {rc.AUXILIA: 1}},
        'scout_plan': {'movements': []}}}
    result = execute_decision(state, rc.ROMANS, {'player_action': action})
    assert result['executed'] and not result['errors']
    assert result['sa_execution']['declined_no_effect']
    assert count_pieces(state, rc.MANDUBII, rc.ROMANS, rc.AUXILIA) == 1
    assert KEY not in state
