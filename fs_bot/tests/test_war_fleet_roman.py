"""Card62/§8.8.1 Roman priorities use direct coastal relocation."""
from copy import deepcopy

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import place_piece, count_pieces, count_pieces_by_state
from fs_bot.board.control import refresh_all_control
from fs_bot.cards.war_fleet import _copy, _apply, coastal_regions
from fs_bot.cards.war_fleet_roman import (
    roman_moves, _destinations, _origin_options, _can_consolidate, _two_destinations,
)
from fs_bot.state.state_schema import build_initial_state
from fs_bot.state.serialize import encode


def board(seed=7, scenario=rc.SCENARIO_PAX_GALLICA):
    state = build_initial_state(scenario, seed=seed)
    state['non_player_factions'] = {rc.ROMANS, rc.ARVERNI, rc.AEDUI, rc.BELGAE, rc.GERMANS}
    return state


def army(state, region, legions=0, auxilia=0, leader=False):
    if legions:
        place_piece(state, region, rc.ROMANS, rc.LEGION, legions, from_legions_track=True)
    if auxilia:
        place_piece(state, region, rc.ROMANS, rc.AUXILIA, auxilia)
    if leader:
        place_piece(state, region, rc.ROMANS, rc.LEADER, leader_name=rc.CAESAR)


def base(state, region, faction=rc.ARVERNI):
    from fs_bot.map.map_data import get_tribes_in_region
    place_piece(state, region, faction, rc.ALLY)
    tribe = next(t for t in get_tribes_in_region(region, state['scenario'])
                 if state['tribes'][t].get('allied_faction') is None)
    state['tribes'][tribe]['allied_faction'] = faction


def physical(state):
    return encode({key: value for key, value in state.items() if key != 'rng'})


def test_coastal_relocation_has_no_distance_cost_harassment_or_visibility_flip():
    state = board()
    army(state, rc.ARVERNI_REGION, 2, 4, True)
    place_piece(state, rc.ARVERNI_REGION, rc.ROMANS, rc.AUXILIA, 3, piece_state=rc.REVEALED)
    base(state, rc.MORINI)
    place_piece(state, rc.MORINI, rc.BELGAE, rc.WARBAND, 8)
    before, rng = physical(state), state['rng'].getstate()
    moves = roman_moves(state, coastal_regions(state, rc.ROMANS))
    assert moves and {m['from_region'] for m in moves} == {rc.ARVERNI_REGION}
    assert {m['to_region'] for m in moves} == {rc.MORINI}
    assert physical(state) == before
    _apply(state, rc.ROMANS, moves)
    assert state['resources'][rc.ROMANS] == 0
    assert count_pieces(state, rc.MORINI, rc.ROMANS, rc.LEGION) == 2
    assert count_pieces_by_state(state, rc.MORINI, rc.ROMANS, rc.AUXILIA, rc.HIDDEN) == 4
    assert count_pieces_by_state(state, rc.MORINI, rc.ROMANS, rc.AUXILIA, rc.REVEALED) == 2
    assert count_pieces_by_state(state, rc.ARVERNI_REGION, rc.ROMANS, rc.AUXILIA, rc.REVEALED) == 1


def test_six_legions_rule_requires_every_global_legion_and_leader_to_reach():
    state = board()
    army(state, rc.PICTONES, 2, 6, True)
    army(state, rc.MORINI, 1)
    groups = {rc.PICTONES: {rc.LEGION: 2, rc.AUXILIA: 5, rc.LEADER: True}}
    assert _can_consolidate(state, groups, rc.MORINI)
    army(state, rc.AEDUI_REGION, 1)
    assert not _can_consolidate(state, groups, rc.MORINI)
    # A fourth unselected coastal origin also cannot be silently counted.
    state = board()
    for region in (rc.PICTONES, rc.VENETI, rc.ATREBATES, rc.BRITANNIA):
        army(state, region, 1)
    selected = {region: {rc.LEGION: 1} for region in (rc.PICTONES, rc.VENETI, rc.ATREBATES)}
    assert not _can_consolidate(state, selected, rc.MORINI)


def test_more_than_six_legions_move_to_two_enemy_base_regions():
    state = board()
    army(state, rc.ARVERNI_REGION, 7, 8, True)
    base(state, rc.MORINI)
    base(state, rc.ATREBATES)
    moves = roman_moves(state, coastal_regions(state, rc.ROMANS))
    assert {m['to_region'] for m in moves} == {rc.MORINI, rc.ATREBATES}
    assert len({m['from_region'] for m in moves}) == 1
    _apply(state, rc.ROMANS, moves)
    leader = next(r for r in (rc.MORINI, rc.ATREBATES) if count_pieces(state, r, rc.ROMANS, rc.LEADER))
    other = rc.ATREBATES if leader == rc.MORINI else rc.MORINI
    assert count_pieces(state, leader, rc.ROMANS, rc.LEGION) > count_pieces(state, other, rc.ROMANS, rc.LEGION)
    assert count_pieces(state, leader, rc.ROMANS, rc.AUXILIA) > count_pieces(state, other, rc.ROMANS, rc.AUXILIA)
    assert count_pieces(state, leader, rc.ROMANS, rc.AUXILIA) >= 4


def test_final_per_type_majorities_include_destination_residents():
    state = board()
    army(state, rc.PICTONES, 6, 10, True)
    army(state, rc.ATREBATES, 3, 3)
    groups = {rc.PICTONES: {rc.LEGION: 6, rc.AUXILIA: 10, rc.LEADER: True}}
    moves = _two_destinations(state, groups, [rc.MORINI, rc.ATREBATES])
    _apply(state, rc.ROMANS, moves)
    for piece in (rc.LEADER, rc.LEGION, rc.AUXILIA):
        assert count_pieces(state, rc.MORINI, rc.ROMANS, piece) > count_pieces(state, rc.ATREBATES, rc.ROMANS, piece)
    assert {m['to_region'] for m in moves} == {rc.MORINI, rc.ATREBATES}


def test_specific_first_auxilia_majority_precedes_general_second_leader_escort():
    state = board()
    army(state, rc.PICTONES, auxilia=6)
    army(state, rc.ATREBATES, leader=True)
    moves = _two_destinations(state, {rc.PICTONES: {rc.AUXILIA: 6}}, [rc.MORINI, rc.ATREBATES])
    _apply(state, rc.ROMANS, moves)
    assert count_pieces(state, rc.MORINI, rc.ROMANS, rc.AUXILIA) == 4
    assert count_pieces(state, rc.ATREBATES, rc.ROMANS, rc.AUXILIA) == 2


def test_origins_follow_two_threats_then_one_clean_leader_region():
    state = board()
    for region in (rc.PICTONES, rc.VENETI, rc.ATREBATES):
        army(state, region, 1, 2)
        base(state, region)
    army(state, rc.BRITANNIA, 1, 4, True)
    army(state, rc.ARVERNI_REGION, 2, 2)
    # Static-only Roman Regions are never selected as the clean mobile origin.
    place_piece(state, rc.MORINI, rc.ROMANS, rc.FORT)
    options = _origin_options(state, coastal_regions(state, rc.ROMANS), [rc.ATREBATES, rc.MORINI])
    assert options
    for groups in options:
        origins = list(groups)
        assert len(origins) == 3 and origins[-1] == rc.BRITANNIA
        assert set(origins[:2]) <= {rc.PICTONES, rc.VENETI, rc.ATREBATES}
        assert rc.MORINI not in groups
    assert len({next(iter(option)) for option in options}) == 3


def test_second_threat_origin_cannot_be_first_group_destination():
    state = board()
    for region in (rc.PICTONES, rc.VENETI, rc.MORINI):
        army(state, region, 1)
        base(state, region)
    options = _origin_options(state, [rc.PICTONES, rc.VENETI, rc.MORINI], [rc.MORINI, rc.ATREBATES])
    for groups in options:
        origins = list(groups)
        if origins[0] != rc.MORINI:
            assert rc.MORINI not in origins[1:]


def test_event_destination_ties_ignore_warband_visibility_and_use_seeded_choices():
    seen = set()
    for seed in range(12):
        first = board(seed)
        for region in (rc.MORINI, rc.ATREBATES):
            base(first, region)
            place_piece(first, region, rc.BELGAE, rc.WARBAND, 2)
        second = _copy(first)
        from fs_bot.board.pieces import flip_piece
        flip_piece(second, rc.MORINI, rc.BELGAE, rc.WARBAND, count=2,
                   from_state=rc.HIDDEN, to_state=rc.REVEALED)
        a = _destinations(first, [rc.MORINI, rc.ATREBATES])
        b = _destinations(second, [rc.MORINI, rc.ATREBATES])
        assert a == b
        seen.add(a[0])
    assert seen == {rc.MORINI, rc.ATREBATES}


def test_no_effect_does_not_mutate_board_or_rng_or_consult_agent():
    state = board()
    base(state, rc.MORINI)
    state['decision_agent'] = lambda *_: (_ for _ in ()).throw(AssertionError('human consulted'))
    before = encode({k: v for k, v in state.items() if k != 'decision_agent'})
    assert roman_moves(state, coastal_regions(state, rc.ROMANS)) == []
    assert encode({k: v for k, v in state.items() if k != 'decision_agent'}) == before


def test_ariovistus_destination_priority_uses_arverni_bases_not_german_settlements():
    state = board(seed=1, scenario=rc.SCENARIO_ARIOVISTUS)  # first die = 2
    base(state, rc.MORINI)
    base(state, rc.ATREBATES)
    place_piece(state, rc.VENETI, rc.GERMANS, rc.SETTLEMENT)
    base(state, rc.VENETI, rc.GERMANS)
    ranked = _destinations(state, [rc.MORINI, rc.ATREBATES, rc.VENETI])
    assert ranked[0] in (rc.MORINI, rc.ATREBATES)
    army(state, rc.ARVERNI_REGION, 2, 4, True)
    moves = roman_moves(state, coastal_regions(state, rc.ROMANS))
    assert moves and all(rc.BRITANNIA not in (m['from_region'], m['to_region']) for m in moves)


def test_frost_checks_real_control_gained_at_origin_and_allows_same_np_position():
    from fs_bot.map.map_data import get_playable_regions_for_state
    from fs_bot.engine.victory import calculate_victory_margin
    state = board()
    coast = coastal_regions(state, rc.ROMANS)
    for region in sorted(set(get_playable_regions_for_state(state)) - set(coast) - {rc.PROVINCIA}):
        base(state, region, rc.BELGAE)
    army(state, rc.PICTONES, 1, 1)
    place_piece(state, rc.PICTONES, rc.BELGAE, rc.LEADER, leader_name=rc.AMBIORIX)
    base(state, rc.MORINI)
    refresh_all_control(state)
    assert calculate_victory_margin(state, rc.BELGAE) >= 0
    state['non_player_factions'].remove(rc.BELGAE)
    state['frost'] = True
    before = encode(state)
    assert roman_moves(state, coast) == []
    assert encode(state) == before
    state['non_player_factions'].add(rc.BELGAE)
    moves = roman_moves(state, coast)
    assert moves and {m['from_region'] for m in moves} == {rc.PICTONES}


def test_germanic_horse_capability_counts_in_worst_possible_enemy_battle():
    from fs_bot.cards.capabilities import activate_capability, set_capability_owner
    state = board(seed=5)
    base(state, rc.MORINI, rc.ARVERNI)
    place_piece(state, rc.MORINI, rc.ARVERNI, rc.WARBAND, 3)
    base(state, rc.ATREBATES, rc.BELGAE)
    place_piece(state, rc.ATREBATES, rc.BELGAE, rc.WARBAND, 4)
    activate_capability(state, 59, rc.EVENT_SHADED)
    set_capability_owner(state, 59, rc.ARVERNI)
    before = physical(state)
    assert _destinations(state, [rc.MORINI, rc.ATREBATES])[0] == rc.ATREBATES
    assert physical(state) == before


def test_winning_destination_consolidation_does_not_roll_lower_priority_die(monkeypatch):
    from fs_bot.map.map_data import get_playable_regions_for_state
    from fs_bot.engine.victory import calculate_victory_margin
    state = board()
    coast = coastal_regions(state)
    for region in sorted(set(get_playable_regions_for_state(state)) - set(coast) - {rc.PROVINCIA}):
        base(state, region, rc.BELGAE)
    base(state, rc.MORINI, rc.BELGAE)
    base(state, rc.ATREBATES, rc.ARVERNI)
    army(state, rc.PICTONES, 1, 4, True)
    refresh_all_control(state)
    assert calculate_victory_margin(state, rc.BELGAE) >= 0
    def unexpected_die(*args):
        raise AssertionError('Lower-priority destination die was not needed')
    monkeypatch.setattr('fs_bot.cards.war_fleet_roman.roll_die', unexpected_die)
    moves = roman_moves(state, coast)
    assert moves and {move['to_region'] for move in moves} == {rc.MORINI}


def test_actual_split_never_moves_first_group_into_second_threat_origin():
    state = board()
    army(state, rc.PICTONES, 5, 6, True)
    army(state, rc.ATREBATES, 2, 2)
    for region in (rc.PICTONES, rc.ATREBATES, rc.MORINI):
        base(state, region)
    groups = next(option for option in _origin_options(
        state, [rc.PICTONES, rc.ATREBATES, rc.MORINI], [rc.MORINI, rc.ATREBATES])
        if list(option) == [rc.PICTONES, rc.ATREBATES])
    moves = _two_destinations(state, groups, [rc.MORINI, rc.ATREBATES])
    assert not any(move['from_region'] == rc.PICTONES and move['to_region'] == rc.ATREBATES
                   for move in moves)


def test_phase_only_factions_do_not_count_as_players_for_destination_priority():
    for scenario, phase_faction in ((rc.SCENARIO_PAX_GALLICA, rc.GERMANS),
                                    (rc.SCENARIO_ARIOVISTUS, rc.ARVERNI)):
        state = board(seed=7, scenario=scenario)  # first die = 3
        state['non_player_factions'] = {rc.ROMANS, rc.BELGAE,
            rc.ARVERNI if scenario == rc.SCENARIO_PAX_GALLICA else rc.GERMANS}
        base(state, rc.MORINI, phase_faction)
        base(state, rc.VENETI, phase_faction)
        base(state, rc.ATREBATES, rc.AEDUI)
        assert _destinations(state, [rc.MORINI, rc.VENETI, rc.ATREBATES])[0] == rc.ATREBATES


def test_equal_destination_regions_each_have_one_chance_even_with_multiple_enemies():
    from fs_bot.cards.war_fleet_roman import _random_order
    class RecordRoll:
        def randint(self, low, high):
            assert (low, high) == (0, 1)
            return 1
    state = board()
    state['rng'] = RecordRoll()
    candidates = [
        {'region': rc.MORINI, 'enemy': rc.ARVERNI},
        {'region': rc.MORINI, 'enemy': rc.BELGAE},
        {'region': rc.VENETI, 'enemy': rc.AEDUI},
    ]
    assert list(_random_order(state, candidates, lambda _: 0)) == [rc.VENETI, rc.MORINI]
