"""Explicit troop quantities honor §§3.2.1/3.3.1 and compulsory additions."""

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces, count_pieces_by_state, get_available, place_piece
from fs_bot.cards.capabilities import activate_capability, set_capability_owner
from fs_bot.cards.card_effects import _ally_tribe
from fs_bot.commands.common import CommandError
from fs_bot.commands.rally import (
    recruit_count_limits, recruit_in_region, rally_count_limits, rally_in_region,
)
from fs_bot.commands.sa_enlist import begin_borrow, end_borrow, BORROW_KEY
from fs_bot.state.serialize import encode
from fs_bot.state.state_schema import build_initial_state, check_structural_integrity


def state(scenario=rc.SCENARIO_GREAT_REVOLT):
    board = build_initial_state(scenario, seed=7)
    board['resources'] = {faction: 20 for faction in rc.FACTIONS}
    return board


def roman_base():
    board = state()
    place_piece(board, rc.SEQUANI, rc.ROMANS, rc.FORT)
    place_piece(board, rc.SEQUANI, rc.ROMANS, rc.LEADER, leader_name=rc.CAESAR)
    assert _ally_tribe(board, rc.TRIBE_SEQUANI, rc.ROMANS)
    # Card 13 preserves the valid Supply Line but makes the selected Region
    # cost two, allowing zero/lower selections to prove payment behavior.
    activate_capability(board, 13, rc.EVENT_SHADED)
    return board


def gallic_base():
    board = state()
    assert _ally_tribe(board, rc.TRIBE_MANDUBII, rc.AEDUI)
    assert _ally_tribe(board, rc.TRIBE_SENONES, rc.AEDUI)
    return board


def assert_unchanged_failure(board, call):
    before = encode(board)
    with pytest.raises(CommandError):
        call()
    assert encode(board) == before


@pytest.mark.parametrize('count', [0, 1, 2, 3, None])
def test_recruit_exact_optional_quantity_or_legacy_maximum_and_cost(count):
    board = roman_base()
    available = get_available(board, rc.ROMANS, rc.AUXILIA)
    result = recruit_in_region(board, rc.SEQUANI, 'place_auxilia', count=count)
    expected = 3 if count is None else count
    assert result['pieces_placed'][rc.AUXILIA] == expected
    assert count_pieces_by_state(board, rc.SEQUANI, rc.ROMANS, rc.AUXILIA, rc.HIDDEN) == expected
    assert get_available(board, rc.ROMANS, rc.AUXILIA) == available - expected
    assert result['cost'] == 2 and board['resources'][rc.ROMANS] == 18
    assert check_structural_integrity(board) == []


@pytest.mark.parametrize('count', [0, 1, 2, None])
def test_rally_exact_optional_quantity_or_legacy_maximum_and_cost(count):
    board = gallic_base()
    available = get_available(board, rc.AEDUI, rc.WARBAND)
    result = rally_in_region(board, rc.MANDUBII, rc.AEDUI, 'place_warbands', count=count)
    expected = 2 if count is None else count
    assert result['pieces_placed'][rc.WARBAND] == expected
    assert count_pieces_by_state(board, rc.MANDUBII, rc.AEDUI, rc.WARBAND, rc.HIDDEN) == expected
    assert get_available(board, rc.AEDUI, rc.WARBAND) == available - expected
    assert result['cost'] == 1 and board['resources'][rc.AEDUI] == 19
    assert check_structural_integrity(board) == []


@pytest.mark.parametrize('bad', [True, False, 1.0, -1, 99, '1', [], {}])
def test_bad_recruit_count_is_rejected_before_resources_or_pieces_change(bad):
    board = roman_base()
    assert_unchanged_failure(board, lambda: recruit_in_region(
        board, rc.SEQUANI, 'place_auxilia', count=bad))


@pytest.mark.parametrize('bad', [True, False, 1.0, -1, 99, '1', [], {}])
def test_bad_rally_count_is_rejected_before_resources_or_pieces_change(bad):
    board = gallic_base()
    assert_unchanged_failure(board, lambda: rally_in_region(
        board, rc.MANDUBII, rc.AEDUI, 'place_warbands', count=bad))


@pytest.mark.parametrize('action,tribe', [
    ('place_ally', rc.TRIBE_LINGONES), ('place_citadel', rc.TRIBE_MANDUBII)])
def test_static_rally_option_rejects_even_zero_count(action, tribe):
    board = gallic_base()
    assert_unchanged_failure(board, lambda: rally_in_region(
        board, rc.MANDUBII, rc.AEDUI, action, tribe=tribe, count=0))


def test_static_recruit_option_rejects_even_zero_count():
    board = roman_base()
    assert_unchanged_failure(board, lambda: recruit_in_region(
        board, rc.SEQUANI, 'place_ally', tribe=rc.TRIBE_HELVETII, count=0))


def test_count_and_enlist_mix_cannot_both_be_supplied():
    board = state()
    assert_unchanged_failure(board, lambda: rally_in_region(board, rc.MORINI, rc.BELGAE,
        'place_warbands', count=1, warband_mix={rc.BELGAE: 1, rc.GERMANS: 0}))


def test_limit_helpers_are_pure_and_bound_pool_separately_from_rule_cap():
    roman, gaul = roman_base(), gallic_base()
    place_piece(roman, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA,
                get_available(roman, rc.ROMANS, rc.AUXILIA) - 1)
    place_piece(gaul, rc.AEDUI_REGION, rc.AEDUI, rc.WARBAND,
                get_available(gaul, rc.AEDUI, rc.WARBAND) - 1)
    before = encode(roman), encode(gaul)
    assert recruit_count_limits(roman, rc.SEQUANI) == {'min': 0, 'max': 1, 'cap': 3}
    assert rally_count_limits(gaul, rc.MANDUBII, rc.AEDUI) == {'min': 0, 'max': 1, 'cap': 2}
    assert (encode(roman), encode(gaul)) == before
    assert_unchanged_failure(roman, lambda: recruit_in_region(
        roman, rc.SEQUANI, 'place_auxilia', count=2))
    assert_unchanged_failure(gaul, lambda: rally_in_region(
        gaul, rc.MANDUBII, rc.AEDUI, 'place_warbands', count=2))


def test_provincia_extra_is_optional_and_commius_adds_virtual_ally():
    board = state()
    place_piece(board, rc.PROVINCIA, rc.ROMANS, rc.FORT)
    assert recruit_count_limits(board, rc.PROVINCIA) == {'min': 0, 'max': 2, 'cap': 2}
    recruit_in_region(board, rc.PROVINCIA, 'place_auxilia', count=1)
    assert count_pieces(board, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA) == 1
    activate_capability(board, 55, rc.EVENT_UNSHADED)
    assert recruit_count_limits(board, rc.MORINI) == {'min': 0, 'max': 1, 'cap': 1}
    recruit_in_region(board, rc.MORINI, 'place_auxilia', count=1)
    assert count_pieces(board, rc.MORINI, rc.ROMANS, rc.AUXILIA) == 1


@pytest.mark.parametrize('available,required', [(10, 2), (1, 1), (0, 0)])
def test_base_gallia_togata_fixed_two_is_bounded_only_by_pool(available, required):
    board = state()
    board['markers'].setdefault(rc.CISALPINA, {})[rc.MARKER_GALLIA_TOGATA] = {'card_id': 5}
    place_piece(board, rc.CISALPINA, rc.ROMANS, rc.AUXILIA)
    place_piece(board, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA,
                get_available(board, rc.ROMANS, rc.AUXILIA) - available)
    assert recruit_count_limits(board, rc.CISALPINA) == {
        'min': required, 'max': required, 'cap': 2}
    if required:
        assert_unchanged_failure(board, lambda: recruit_in_region(
            board, rc.CISALPINA, 'place_auxilia', count=required - 1))
    result = recruit_in_region(board, rc.CISALPINA, 'place_auxilia')
    assert result['pieces_placed'][rc.AUXILIA] == required
    assert count_pieces(board, rc.CISALPINA, rc.ROMANS, rc.AUXILIA) == 1 + required


def test_ario_gallia_addition_is_compulsory_in_total_troop_count():
    board = state(rc.SCENARIO_ARIOVISTUS)
    board['markers'].setdefault(rc.CISALPINA, {})[rc.MARKER_GALLIA_TOGATA] = {'card_id': 'A5'}
    place_piece(board, rc.CISALPINA, rc.ROMANS, rc.FORT)
    assert recruit_count_limits(board, rc.CISALPINA) == {'min': 1, 'max': 2, 'cap': 2}
    assert_unchanged_failure(board, lambda: recruit_in_region(
        board, rc.CISALPINA, 'place_auxilia', count=0))
    result = recruit_in_region(board, rc.CISALPINA, 'place_auxilia', count=1)
    assert result['pieces_placed'][rc.AUXILIA] == 1
    assert count_pieces(board, rc.CISALPINA, rc.ROMANS, rc.AUXILIA) == 1


def test_ario_gallia_addition_also_follows_ally_recruit():
    board = state(rc.SCENARIO_ARIOVISTUS)
    board['markers'].setdefault(rc.CISALPINA, {})[rc.MARKER_GALLIA_TOGATA] = {'card_id': 'A5'}
    place_piece(board, rc.CISALPINA, rc.ROMANS, rc.AUXILIA)
    result = recruit_in_region(board, rc.CISALPINA, 'place_ally', tribe=rc.TRIBE_NORI)
    assert result['pieces_placed'] == {rc.ALLY: 1, rc.AUXILIA: 1}
    assert board['tribes'][rc.TRIBE_NORI]['allied_faction'] == rc.ROMANS
    assert count_pieces(board, rc.CISALPINA, rc.ROMANS, rc.AUXILIA) == 2


def aquitani_board():
    board = state()
    activate_capability(board, 25, rc.EVENT_SHADED)
    set_capability_owner(board, 25, rc.ARVERNI)
    place_piece(board, rc.PICTONES, rc.ARVERNI, rc.LEADER, leader_name=rc.VERCINGETORIX)
    return board


def test_aquitani_total_includes_two_extra_and_is_scoped_to_owner_and_region():
    board = aquitani_board()
    assert rally_count_limits(board, rc.PICTONES, rc.ARVERNI) == {'min': 2, 'max': 4, 'cap': 4}
    assert_unchanged_failure(board, lambda: rally_in_region(
        board, rc.PICTONES, rc.ARVERNI, 'place_warbands', count=1))
    result = rally_in_region(board, rc.PICTONES, rc.ARVERNI, 'place_warbands', count=3)
    assert result['pieces_placed'][rc.WARBAND] == 3
    assert count_pieces(board, rc.PICTONES, rc.ARVERNI, rc.WARBAND) == 3
    assert _ally_tribe(board, rc.TRIBE_PICTONES, rc.AEDUI)
    assert rally_count_limits(board, rc.PICTONES, rc.AEDUI) == {'min': 0, 'max': 1, 'cap': 1}
    assert _ally_tribe(board, rc.TRIBE_SEQUANI, rc.ARVERNI)
    assert rally_count_limits(board, rc.SEQUANI, rc.ARVERNI) == {'min': 0, 'max': 2, 'cap': 2}


@pytest.mark.parametrize('action,tribe', [('place_ally', rc.TRIBE_PICTONES),
                                       ('place_citadel', rc.TRIBE_ARVERNI)])
def test_aquitani_addition_follows_static_options(action, tribe):
    board = aquitani_board()
    region = rc.PICTONES
    if action == 'place_citadel':
        region = rc.ARVERNI_REGION
        assert _ally_tribe(board, tribe, rc.ARVERNI)
    result = rally_in_region(board, region, rc.ARVERNI, action, tribe=tribe)
    assert result['pieces_placed'][rc.WARBAND] == 2
    assert count_pieces(board, region, rc.ARVERNI, rc.WARBAND) == 2
    assert check_structural_integrity(board) == []


def test_aquitani_can_supply_two_when_ordinary_warband_cap_is_zero():
    board = state()
    place_piece(board, rc.PICTONES, rc.AEDUI, rc.WARBAND)
    activate_capability(board, 25, rc.EVENT_SHADED)
    set_capability_owner(board, 25, rc.AEDUI)
    assert rally_count_limits(board, rc.PICTONES, rc.AEDUI) == {'min': 2, 'max': 2, 'cap': 2}
    result = rally_in_region(board, rc.PICTONES, rc.AEDUI, 'place_warbands', count=2)
    assert result['pieces_placed'][rc.WARBAND] == 2
    assert count_pieces(board, rc.PICTONES, rc.AEDUI, rc.WARBAND) == 3


def test_a70_addition_is_not_lost_on_home_without_ally_or_after_ally_option():
    board = state(rc.SCENARIO_ARIOVISTUS)
    activate_capability(board, 'A70', rc.EVENT_SHADED)
    assert rally_count_limits(board, rc.NERVII, rc.BELGAE) == {'min': 2, 'max': 3, 'cap': 3}
    first = rally_in_region(board, rc.NERVII, rc.BELGAE, 'place_warbands', count=2)
    assert first['pieces_placed'][rc.WARBAND] == 2
    second = rally_in_region(board, rc.NERVII, rc.BELGAE, 'place_ally', tribe=rc.TRIBE_NERVII)
    assert second['pieces_placed'] == {rc.ALLY: 1, rc.WARBAND: 2}
    assert count_pieces(board, rc.NERVII, rc.BELGAE, rc.WARBAND) == 4


def test_card30_removes_leader_plus_one_from_cap_but_keeps_home_exception():
    board = state()
    place_piece(board, rc.MANDUBII, rc.ARVERNI, rc.LEADER, leader_name=rc.VERCINGETORIX)
    assert _ally_tribe(board, rc.TRIBE_MANDUBII, rc.ARVERNI)
    assert rally_count_limits(board, rc.MANDUBII, rc.ARVERNI)['cap'] == 3
    activate_capability(board, 30, rc.EVENT_UNSHADED)
    assert rally_count_limits(board, rc.MANDUBII, rc.ARVERNI) == {'min': 0, 'max': 1, 'cap': 1}
    assert rally_count_limits(board, rc.ARVERNI_REGION, rc.ARVERNI) == {'min': 0, 'max': 1, 'cap': 1}
    assert_unchanged_failure(board, lambda: rally_in_region(
        board, rc.MANDUBII, rc.ARVERNI, 'place_warbands', count=2))


def test_german_home_bonus_is_in_total_and_cannot_be_declined_with_zero():
    board = state(rc.SCENARIO_ARIOVISTUS)
    assert rally_count_limits(board, rc.UBII, rc.GERMANS, include_home_bonus=True) == {
        'min': 1, 'max': 1, 'cap': 1}
    assert_unchanged_failure(board, lambda: rally_in_region(board, rc.UBII, rc.GERMANS,
        'place_warbands', count=0, include_home_bonus=True))
    result = rally_in_region(board, rc.UBII, rc.GERMANS, 'place_warbands',
                             count=1, include_home_bonus=True)
    assert result['pieces_placed'][rc.WARBAND] == 1
    assert count_pieces(board, rc.UBII, rc.GERMANS, rc.WARBAND) == 1


def test_german_settlement_addition_applies_after_ally_and_bounds_total_cap():
    board = state(rc.SCENARIO_ARIOVISTUS)
    place_piece(board, rc.SEQUANI, rc.GERMANS, rc.SETTLEMENT)
    assert rally_count_limits(board, rc.SEQUANI, rc.GERMANS, include_home_bonus=True) == {
        'min': 1, 'max': 2, 'cap': 2}
    result = rally_in_region(board, rc.SEQUANI, rc.GERMANS, 'place_ally',
                             tribe=rc.TRIBE_SEQUANI, include_home_bonus=True)
    assert result['pieces_placed'] == {rc.ALLY: 1, rc.WARBAND: 1}
    assert board['resources'][rc.GERMANS] == 19
    assert rally_count_limits(board, rc.SEQUANI, rc.GERMANS, include_home_bonus=True) == {
        'min': 1, 'max': 3, 'cap': 3}


def test_base_german_home_rally_requires_one_when_available():
    board = state()
    assert rally_count_limits(board, rc.UBII, rc.GERMANS) == {'min': 1, 'max': 1, 'cap': 1}
    assert_unchanged_failure(board, lambda: rally_in_region(
        board, rc.UBII, rc.GERMANS, 'place_warbands', count=0))


def test_mandatory_bonus_is_partial_when_only_one_piece_available():
    board = aquitani_board()
    place_piece(board, rc.SEQUANI, rc.ARVERNI, rc.WARBAND,
                get_available(board, rc.ARVERNI, rc.WARBAND) - 1)
    assert rally_count_limits(board, rc.PICTONES, rc.ARVERNI) == {'min': 1, 'max': 1, 'cap': 4}
    result = rally_in_region(board, rc.PICTONES, rc.ARVERNI, 'place_warbands', count=1)
    assert result['pieces_placed'][rc.WARBAND] == 1
    assert get_available(board, rc.ARVERNI, rc.WARBAND) == 0


def test_zero_available_zero_requested_still_pays_without_exceeding_inventory():
    board = gallic_base()
    place_piece(board, rc.AEDUI_REGION, rc.AEDUI, rc.WARBAND,
                get_available(board, rc.AEDUI, rc.WARBAND))
    assert rally_count_limits(board, rc.MANDUBII, rc.AEDUI) == {'min': 0, 'max': 0, 'cap': 2}
    result = rally_in_region(board, rc.MANDUBII, rc.AEDUI, 'place_warbands', count=0)
    assert result['pieces_placed'][rc.WARBAND] == 0
    assert board['resources'][rc.AEDUI] == 19
    assert check_structural_integrity(board) == []


def test_bounded_grant_caps_total_including_additions_without_live_mutation():
    board = aquitani_board()
    before = encode(board)
    assert rally_count_limits(board, rc.PICTONES, rc.ARVERNI, max_pieces=1) == {
        'min': 1, 'max': 1, 'cap': 1}
    assert encode(board) == before
    result = rally_in_region(board, rc.PICTONES, rc.ARVERNI, 'place_warbands',
                             count=1, max_pieces=1)
    assert result['pieces_placed'][rc.WARBAND] == 1


def test_suppressing_already_applied_bonuses_preserves_ordinary_optional_count():
    board = aquitani_board()
    assert rally_count_limits(board, rc.PICTONES, rc.ARVERNI, include_bonuses=False) == {
        'min': 0, 'max': 2, 'cap': 2}
    result = rally_in_region(board, rc.PICTONES, rc.ARVERNI, 'place_warbands',
                             count=1, include_bonuses=False)
    assert result['pieces_placed'][rc.WARBAND] == 1


def enlisted_bonus_board(card=25, *, borrowed=1):
    expansion = card == 'A70'
    board = state(rc.SCENARIO_ARIOVISTUS if expansion else rc.SCENARIO_GREAT_REVOLT)
    region, tribe = ((rc.NERVII, rc.TRIBE_NERVII) if expansion
                     else (rc.PICTONES, rc.TRIBE_PICTONES))
    place_piece(board, region, rc.BELGAE, rc.LEADER,
                leader_name=rc.BODUOGNATUS if expansion else rc.AMBIORIX)
    place_piece(board, region, rc.GERMANS, rc.WARBAND, borrowed)
    activate_capability(board, card, rc.EVENT_SHADED)
    if card == 25:
        set_capability_owner(board, card, rc.BELGAE)
    begin_borrow(board, {'command': rc.CMD_RALLY, 'sa': rc.SA_ENLIST,
        'sa_regions': [region], 'details': {'enlist': {
            'type': 'borrow', 'regions': [region]}}})
    return board, region, tribe


@pytest.mark.parametrize('card', [25, 'A70'])
@pytest.mark.parametrize('mix', [{rc.BELGAE: 2}, {rc.GERMANS: 2},
                                {rc.BELGAE: 1, rc.GERMANS: 1}])
def test_static_ally_bonus_enlist_mix_keeps_physical_owners_and_exact_total(card, mix):
    board, region, tribe = enlisted_bonus_board(card)
    before = {owner: get_available(board, owner, rc.WARBAND)
              for owner in (rc.BELGAE, rc.GERMANS)}
    result = rally_in_region(board, region, rc.BELGAE, 'place_ally',
                             tribe=tribe, warband_mix=mix)
    assert result['pieces_placed'] == {rc.ALLY: 1, rc.WARBAND: 2}
    assert result['warband_owners'] == {owner: mix.get(owner, 0) for owner in before}
    assert board[BORROW_KEY]['affected'] == 1 + mix.get(rc.GERMANS, 0)
    assert board['resources'][rc.BELGAE] == (19 if card == 'A70' else 18)
    assert board['tribes'][tribe]['allied_faction'] == rc.BELGAE
    end_borrow(board)
    for owner in before:
        assert get_available(board, owner, rc.WARBAND) == before[owner] - mix.get(owner, 0)
        expected = mix.get(owner, 0) + (1 if owner == rc.GERMANS else 0)
        assert count_pieces_by_state(board, region, owner, rc.WARBAND, rc.HIDDEN) == expected
    assert check_structural_integrity(board) == []


@pytest.mark.parametrize('mix', [
    {}, {rc.BELGAE: 1}, {rc.BELGAE: 3}, {rc.GERMANS: -1, rc.BELGAE: 3},
    {rc.BELGAE: True, rc.GERMANS: 1}, {rc.BELGAE: 1.0, rc.GERMANS: 1},
    {rc.AEDUI: 2}, [2], '2',
])
def test_static_bonus_mix_rejects_bad_type_or_total_before_ally_and_payment(mix):
    board, region, tribe = enlisted_bonus_board()
    assert_unchanged_failure(board, lambda: rally_in_region(board, region, rc.BELGAE,
        'place_ally', tribe=tribe, warband_mix=mix))


def test_static_bonus_mix_rejects_physical_pool_overflow_before_ally_and_payment():
    board, region, tribe = enlisted_bonus_board()
    place_piece(board, rc.MORINI, rc.BELGAE, rc.WARBAND,
                get_available(board, rc.BELGAE, rc.WARBAND) - 1)
    assert_unchanged_failure(board, lambda: rally_in_region(board, region, rc.BELGAE,
        'place_ally', tribe=tribe, warband_mix={rc.BELGAE: 2}))


def test_static_bonus_mix_rejects_ario_four_piece_limit_before_ally_and_payment():
    board, region, tribe = enlisted_bonus_board('A70', borrowed=3)
    assert_unchanged_failure(board, lambda: rally_in_region(board, region, rc.BELGAE,
        'place_ally', tribe=tribe, warband_mix={rc.GERMANS: 2}))


@pytest.mark.parametrize('action', ['place_ally', 'place_warbands'])
def test_enlist_compulsory_bonus_is_bounded_by_remaining_four_piece_allowance(action):
    """A4.5.1/§5.1.3: fill the last legal slot even with larger German stock."""
    board, region, tribe = enlisted_bonus_board('A70', borrowed=3)
    place_piece(board, rc.MORINI, rc.BELGAE, rc.WARBAND,
                get_available(board, rc.BELGAE, rc.WARBAND))
    german_pool = get_available(board, rc.GERMANS, rc.WARBAND)
    assert german_pool > 1
    assert_unchanged_failure(board, lambda: rally_in_region(board, region, rc.BELGAE,
        action, tribe=tribe, warband_mix={rc.GERMANS: 0}))
    result = rally_in_region(board, region, rc.BELGAE, action,
                             tribe=tribe, warband_mix={rc.GERMANS: 1})
    assert result['pieces_placed'][rc.WARBAND] == 1
    assert result['warband_owners'] == {rc.BELGAE: 0, rc.GERMANS: 1}
    assert board[BORROW_KEY]['affected'] == 4
    assert board['resources'][rc.BELGAE] == 19
    assert (board['tribes'][tribe]['allied_faction'] == rc.BELGAE) == (action == 'place_ally')
    end_borrow(board)
    assert count_pieces_by_state(board, region, rc.GERMANS, rc.WARBAND, rc.HIDDEN) == 4
    assert count_pieces(board, region, rc.BELGAE, rc.WARBAND) == 0
    assert get_available(board, rc.GERMANS, rc.WARBAND) == german_pool - 1
    assert check_structural_integrity(board) == []


@pytest.mark.parametrize('card', [25, 'A70'])
def test_static_zero_bonus_mix_only_when_no_eligible_physical_stock_remains(card):
    board, region, tribe = enlisted_bonus_board(card)
    for owner in (rc.BELGAE, rc.GERMANS):
        place_piece(board, rc.SEQUANI, owner, rc.WARBAND,
                    get_available(board, owner, rc.WARBAND))
    result = rally_in_region(board, region, rc.BELGAE, 'place_ally',
                             tribe=tribe, warband_mix={rc.BELGAE: 0, rc.GERMANS: 0})
    assert result['pieces_placed'] == {rc.ALLY: 1}
    assert board['tribes'][tribe]['allied_faction'] == rc.BELGAE
    assert board['resources'][rc.BELGAE] == (19 if card == 'A70' else 18)
    end_borrow(board)
    assert count_pieces(board, region, rc.GERMANS, rc.WARBAND) == 1
    assert check_structural_integrity(board) == []


@pytest.mark.parametrize('card', [25, 'A70'])
def test_static_mix_does_not_invent_a_city_for_citadel_bonus(card):
    board, region, tribe = enlisted_bonus_board(card)
    assert _ally_tribe(board, tribe, rc.BELGAE)
    # Neither Pictones nor Nervii has a City. The other Aquitani Region's
    # City, Gergovia, is Arverni-only: no legal Belgic Citadel bonus exists.
    assert_unchanged_failure(board, lambda: rally_in_region(board, region, rc.BELGAE,
        'place_citadel', tribe=tribe, warband_mix={rc.GERMANS: 1, rc.BELGAE: 1}))


def test_base_gallia_fixed_two_also_applies_when_recruiting_dynamic_colony_ally():
    from fs_bot.cards.card_effects import execute_card_71, _unally_tribe
    board = state()
    board['markers'].setdefault(rc.CISALPINA, {})[rc.MARKER_GALLIA_TOGATA] = {'card_id': 5}
    place_piece(board, rc.CISALPINA, rc.ROMANS, rc.AUXILIA)
    board['executing_faction'] = rc.ROMANS
    board['event_params'] = {'region': rc.CISALPINA}
    execute_card_71(board)
    colony = next(tribe for tribe, info in board['tribes'].items()
                  if info.get('region') == rc.CISALPINA)
    assert _unally_tribe(board, colony) == rc.ROMANS
    result = recruit_in_region(board, rc.CISALPINA, 'place_ally', tribe=colony)
    assert result['pieces_placed'] == {rc.ALLY: 1, rc.AUXILIA: 2}
    assert board['tribes'][colony]['allied_faction'] == rc.ROMANS
    assert count_pieces(board, rc.CISALPINA, rc.ROMANS, rc.AUXILIA) == 3
    assert check_structural_integrity(board) == []


@pytest.mark.parametrize('scenario', [rc.SCENARIO_GREAT_REVOLT, rc.SCENARIO_ARIOVISTUS])
@pytest.mark.parametrize('faction', [rc.ROMANS, rc.AEDUI])
def test_sacking_permanently_dispersed_city_rejects_recruit_and_rally_allies(scenario, faction):
    """Card23: Razed has every Dispersed restriction, including §§3.2.1/3.3.1."""
    from fs_bot.board.pieces import remove_piece
    from fs_bot.cards.card_effects import execute_card_23

    board = state(scenario)
    place_piece(board, rc.BITURIGES, rc.ROMANS, rc.AUXILIA)
    board['event_params'] = {'target_city': rc.CITY_AVARICUM}
    execute_card_23(board)
    assert board['tribes'][rc.TRIBE_BITURIGES]['status'] == rc.MARKER_RAZED
    if faction == rc.AEDUI:
        remove_piece(board, rc.BITURIGES, rc.ROMANS, rc.AUXILIA)
        place_piece(board, rc.BITURIGES, rc.AEDUI, rc.WARBAND)

    before = encode(board)
    with pytest.raises(CommandError, match='not eligible'):
        if faction == rc.ROMANS:
            recruit_in_region(board, rc.BITURIGES, 'place_ally', tribe=rc.TRIBE_BITURIGES)
        else:
            rally_in_region(board, rc.BITURIGES, faction, 'place_ally', tribe=rc.TRIBE_BITURIGES)
    assert encode(board) == before
    assert check_structural_integrity(board) == []
