"""Source-backed Suborn choices and atomic plans (§4.4.2, cards 43/A38)."""
import io

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import (
    count_pieces, count_pieces_by_state, get_available, place_piece)
from fs_bot.cards.capabilities import activate_capability
from fs_bot.cli.human_plan import _collect_suborn
from fs_bot.commands.common import CommandError
from fs_bot.commands.sa_suborn import (
    legal_suborn_operations, suborn, suborn_limits, validate_suborn_region)
from fs_bot.engine.execute import _execute_suborn
from fs_bot.state.serialize import encode
from fs_bot.state.state_schema import build_initial_state


def _state(*regions, resources=10):
    state = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=43)
    state['non_player_factions'] = set()
    state['resources'][rc.AEDUI] = resources
    for region in regions or (rc.CARNUTES,):
        place_piece(state, region, rc.AEDUI, rc.WARBAND)
    return state


def _op(action, owner, piece, **extra):
    return {'action': action, 'faction': owner, 'piece_type': piece,
            'physical_owner': owner, **extra}


def _action(*entries):
    return {'sa': 'Suborn', 'details': {'suborn_plan': [
        {'region': region, 'actions': operations}
        for region, operations in entries]}}


def _collect(state, *answers):
    # All menu planning must leave pieces, pools, costs, and RNG untouched.
    before = encode(state)
    stream, output = io.StringIO('\n'.join(answers) + '\n'), io.StringIO()
    regions, details = _collect_suborn(state, rc.AEDUI, stream, output)
    assert encode(state) == before
    assert stream.read() == '', output.getvalue()
    return regions, details, output.getvalue()


def test_every_native_faction_piece_can_be_placed_without_heuristic_pruning():
    state = _state()
    operations = legal_suborn_operations(state, rc.CARNUTES)
    actual = {(op['faction'], op['piece_type']) for op in operations
              if op['action'] == 'place'}
    expected = {(faction, rc.ALLY) for faction in rc.FACTIONS}
    expected.update((faction, rc.WARBAND) for faction in rc.FACTIONS
                    if faction != rc.ROMANS)
    expected.add((rc.ROMANS, rc.AUXILIA))
    assert actual == expected
    assert all(op['physical_owner'] == op['faction'] for op in operations)


@pytest.mark.parametrize('owner,piece,label', [
    (rc.ROMANS, rc.AUXILIA, f'place a {rc.ROMANS} {rc.AUXILIA}'),
    (rc.ARVERNI, rc.WARBAND, f'place a {rc.ARVERNI} {rc.WARBAND}'),
    (rc.BELGAE, rc.WARBAND, f'place a {rc.BELGAE} {rc.WARBAND}'),
    (rc.GERMANS, rc.WARBAND, f'place a {rc.GERMANS} {rc.WARBAND}'),
])
def test_terminal_places_other_factions_native_mobile_pieces(owner, piece, label):
    state = _state()
    pool = get_available(state, owner, piece)
    regions, details, _ = _collect(state, rc.CARNUTES, label, '(done)')
    assert regions == [rc.CARNUTES]
    result = _execute_suborn(state, rc.AEDUI, {'details': details})
    assert result['executed'], result
    assert count_pieces_by_state(state, rc.CARNUTES, owner, piece, rc.HIDDEN) == 1
    assert get_available(state, owner, piece) == pool - 1
    assert state['resources'][rc.AEDUI] == 9


@pytest.mark.parametrize('visibility', [rc.HIDDEN, rc.REVEALED, rc.SCOUTED])
def test_terminal_removes_the_exact_selected_visibility_of_own_piece(visibility):
    state = _state()
    place_piece(state, rc.CARNUTES, rc.AEDUI, rc.WARBAND, piece_state=rc.REVEALED)
    place_piece(state, rc.CARNUTES, rc.AEDUI, rc.WARBAND, piece_state=rc.SCOUTED)
    _, details, _ = _collect(state, rc.CARNUTES,
        f'remove a {rc.AEDUI} {rc.WARBAND}', visibility, '(done)')
    result = _execute_suborn(state, rc.AEDUI, {'details': details})
    assert result['executed'], result
    for ps in (rc.HIDDEN, rc.REVEALED, rc.SCOUTED):
        assert count_pieces_by_state(state, rc.CARNUTES, rc.AEDUI,
                                     rc.WARBAND, ps) == (0 if ps == visibility else 1)


@pytest.mark.parametrize('owner', rc.FACTIONS)
def test_terminal_places_any_factions_ally_at_unrestricted_tribe(owner):
    state = _state()
    label = ('place your Ally at a Subdued Tribe' if owner == rc.AEDUI
             else f'place a {owner} Ally at a Subdued Tribe')
    _, details, _ = _collect(state, rc.CARNUTES, label, rc.TRIBE_CARNUTES, '(done)')
    result = _execute_suborn(state, rc.AEDUI, {'details': details})
    assert result['executed'], result
    assert state['tribes'][rc.TRIBE_CARNUTES]['allied_faction'] == owner
    assert count_pieces(state, rc.CARNUTES, owner, rc.ALLY) == 1
    assert state['resources'][rc.AEDUI] == 8


def test_native_ally_choices_obey_home_restriction_and_available_pool():
    state = _state(rc.AEDUI_REGION)
    operations = legal_suborn_operations(state, rc.AEDUI_REGION)
    assert {op['faction'] for op in operations if op.get('tribe') == rc.TRIBE_AEDUI
            and op['action'] == 'place'} == {rc.AEDUI}
    place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA,
                get_available(state, rc.ROMANS, rc.AUXILIA))
    assert not any(op['action'] == 'place' and op['piece_type'] == rc.AUXILIA
                   for op in legal_suborn_operations(state, rc.AEDUI_REGION))


def test_named_city_citadel_is_not_an_ally_even_with_another_ally_in_region():
    state = _state(rc.MANDUBII)
    place_piece(state, rc.MANDUBII, rc.AEDUI, rc.CITADEL)
    place_piece(state, rc.MANDUBII, rc.AEDUI, rc.ALLY)
    for tribe in (rc.TRIBE_MANDUBII, rc.TRIBE_SENONES):
        state['tribes'][tribe]['allied_faction'] = rc.AEDUI
    removable = {op['tribe'] for op in legal_suborn_operations(state, rc.MANDUBII)
                 if op['action'] == 'remove' and op['piece_type'] == rc.ALLY}
    assert removable == {rc.TRIBE_SENONES}
    before = encode(state)
    result = _execute_suborn(state, rc.AEDUI, _action((rc.MANDUBII, [
        _op('remove', rc.AEDUI, rc.ALLY, tribe=rc.TRIBE_MANDUBII)])))
    assert not result['executed'] and result['errors'], result
    assert encode(state) == before


def _add_colony(state, owner):
    from fs_bot.cards.card_effects import execute_event
    before = set(state['tribes'])
    # One Auxilia balances the existing Aedui Warband: either Faction can
    # legally play Colony where there is No Control (Card 71).
    place_piece(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA)
    state['executing_faction'] = owner
    state['event_params'] = {'region': rc.CARNUTES}
    execute_event(state, 71)
    colony, = set(state['tribes']) - before
    return colony


def test_real_colony_can_be_removed_then_reallied_by_terminal_suborn():
    state = _state(resources=4)
    colony = _add_colony(state, rc.AEDUI)
    activate_capability(state, 'A38', rc.EVENT_UNSHADED)
    _, details, _ = _collect(state, rc.CARNUTES, 'remove your Ally',
        f'{colony} ({rc.AEDUI})', f'place a {rc.ROMANS} Ally at a Subdued Tribe',
        colony, '(done)')
    result = _execute_suborn(state, rc.AEDUI, {'details': details})
    assert result['executed'], result
    assert state['tribes'][colony]['allied_faction'] == rc.ROMANS
    assert state['markers'][rc.CARNUTES][rc.MARKER_COLONY]
    assert state['resources'][rc.AEDUI] == 0
    assert count_pieces(state, rc.CARNUTES, rc.AEDUI, rc.ALLY) == 0
    assert count_pieces(state, rc.CARNUTES, rc.ROMANS, rc.ALLY) == 1


@pytest.mark.parametrize('remove_enemy', [False, True])
def test_np_suborn_includes_real_colony_in_ally_priorities(remove_enemy):
    from fs_bot.bots.aedui_bot import _determine_suborn_sa
    from fs_bot.board.pieces import clear_allied_tribe, remove_piece
    state = _state(resources=2)
    owner = rc.ROMANS if remove_enemy else rc.AEDUI
    colony = _add_colony(state, owner)
    # Occupy both printed Tribes so the Colony is the only Ally operation.
    place_piece(state, rc.CARNUTES, rc.AEDUI, rc.ALLY, 2)
    for tribe in (rc.TRIBE_CARNUTES, rc.TRIBE_AULERCI):
        state['tribes'][tribe]['allied_faction'] = rc.AEDUI
    if not remove_enemy:
        remove_piece(state, rc.CARNUTES, owner, rc.ALLY)
        clear_allied_tribe(state, rc.CARNUTES, owner, rc.ALLY, tribe=colony)
    sa, regions, details = _determine_suborn_sa(state, state['scenario'])
    operation, = details['suborn_plan'][0]['actions']
    assert operation['action'] == ('remove_ally' if remove_enemy else 'place_ally')
    assert operation['tribe'] == colony
    result = _execute_suborn(state, rc.AEDUI, {'sa': sa, 'details': details})
    assert result['executed'] and result['regions'] == regions, result
    assert state['tribes'][colony]['allied_faction'] == (None if remove_enemy else rc.AEDUI)


def test_a38_second_ally_can_replace_an_ally_removed_earlier_in_same_region():
    state = _state(resources=4)
    activate_capability(state, 'A38', rc.EVENT_UNSHADED)
    place_piece(state, rc.CARNUTES, rc.AEDUI, rc.ALLY)
    state['tribes'][rc.TRIBE_CARNUTES]['allied_faction'] = rc.AEDUI
    assert suborn_limits(state) == (4, 2)
    _, details, text = _collect(state, rc.CARNUTES, 'remove your Ally',
        f'{rc.TRIBE_CARNUTES} ({rc.AEDUI})',
        f'place a {rc.BELGAE} Ally at a Subdued Tribe', rc.TRIBE_CARNUTES, '(done)')
    assert 'Suborn action 3 of up to 4' in text
    result = _execute_suborn(state, rc.AEDUI, {'details': details})
    assert result['executed'], result
    assert count_pieces(state, rc.CARNUTES, rc.AEDUI, rc.ALLY) == 0
    assert count_pieces(state, rc.CARNUTES, rc.BELGAE, rc.ALLY) == 1
    assert state['tribes'][rc.TRIBE_CARNUTES]['allied_faction'] == rc.BELGAE
    assert state['resources'][rc.AEDUI] == 0


def test_without_a38_replacing_an_ally_is_two_ally_operations_and_atomic():
    state = _state()
    place_piece(state, rc.CARNUTES, rc.AEDUI, rc.ALLY)
    state['tribes'][rc.TRIBE_CARNUTES]['allied_faction'] = rc.AEDUI
    before = encode(state)
    with pytest.raises(CommandError, match='at most 1 Ally'):
        suborn(state, rc.CARNUTES, [
            _op('remove', rc.AEDUI, rc.ALLY, tribe=rc.TRIBE_CARNUTES),
            _op('place', rc.BELGAE, rc.ALLY, tribe=rc.TRIBE_CARNUTES)])
    assert encode(state) == before


def test_last_hidden_aedui_can_be_removed_before_remaining_suborn_operations():
    state = _state()
    _, details, _ = _collect(state, rc.CARNUTES,
        f'remove a {rc.AEDUI} {rc.WARBAND}',
        f'place a {rc.BELGAE} {rc.WARBAND}', '(done)')
    result = _execute_suborn(state, rc.AEDUI, {'details': details})
    assert result['executed'], result
    assert not validate_suborn_region(state, rc.CARNUTES)[0]
    assert count_pieces(state, rc.CARNUTES, rc.BELGAE, rc.WARBAND) == 1
    assert state['resources'][rc.AEDUI] == 8


@pytest.mark.parametrize('failure', ['piece', 'tribe', 'resources', 'pool'])
def test_cumulative_plan_preflight_rejects_duplicate_or_exhausted_items_atomically(failure):
    state = _state()
    if failure == 'piece':
        place_piece(state, rc.CARNUTES, rc.BELGAE, rc.WARBAND,
                    piece_state=rc.REVEALED)
        operation = _op('remove', rc.BELGAE, rc.WARBAND, piece_state=rc.REVEALED)
    elif failure == 'tribe':
        activate_capability(state, 'A38', rc.EVENT_UNSHADED)
        operation = _op('place', rc.BELGAE, rc.ALLY, tribe=rc.TRIBE_CARNUTES)
    else:
        operation = _op('place', rc.BELGAE, rc.WARBAND)
        if failure == 'resources':
            state['resources'][rc.AEDUI] = 1
        else:
            place_piece(state, rc.PROVINCIA, rc.BELGAE, rc.WARBAND,
                        get_available(state, rc.BELGAE, rc.WARBAND) - 1)
    before = encode(state)
    result = _execute_suborn(state, rc.AEDUI,
                            _action((rc.CARNUTES, [operation, operation])))
    assert not result['executed'] and result['errors'], result
    assert encode(state) == before


@pytest.mark.parametrize('failure', ['resources', 'pool'])
def test_second_region_failure_cannot_leave_first_region_paid_or_changed(failure):
    state = _state(rc.CARNUTES, rc.MANDUBII)
    activate_capability(state, 43, rc.EVENT_UNSHADED)
    operation = _op('place', rc.ROMANS, rc.AUXILIA)
    if failure == 'resources':
        state['resources'][rc.AEDUI] = 1
    else:
        place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA,
                    get_available(state, rc.ROMANS, rc.AUXILIA) - 1)
    before = encode(state)
    result = _execute_suborn(state, rc.AEDUI, _action(
        (rc.CARNUTES, [operation]), (rc.MANDUBII, [operation])))
    assert not result['executed'] and result['errors'], result
    assert encode(state) == before


def test_a38_and_convictolitavis_apply_full_limits_in_both_selected_regions():
    state = _state(rc.CARNUTES, rc.MANDUBII, resources=8)
    activate_capability(state, 43, rc.EVENT_UNSHADED)
    activate_capability(state, 'A38', rc.EVENT_UNSHADED)
    for region, tribe in ((rc.CARNUTES, rc.TRIBE_CARNUTES),
                           (rc.MANDUBII, rc.TRIBE_MANDUBII)):
        place_piece(state, region, rc.AEDUI, rc.ALLY)
        state['tribes'][tribe]['allied_faction'] = rc.AEDUI
    entries = [(region, [
        _op('remove', rc.AEDUI, rc.ALLY, tribe=tribe),
        _op('place', rc.BELGAE, rc.ALLY, tribe=tribe),
        _op('place', rc.ROMANS, rc.AUXILIA),
        _op('place', rc.ROMANS, rc.AUXILIA)])
        for region, tribe in ((rc.CARNUTES, rc.TRIBE_CARNUTES),
                              (rc.MANDUBII, rc.TRIBE_MANDUBII))]
    result = _execute_suborn(state, rc.AEDUI, _action(*entries))
    assert result['regions'] == [rc.CARNUTES, rc.MANDUBII], result
    assert state['resources'][rc.AEDUI] == 0
    for region in result['regions']:
        assert count_pieces(state, region, rc.ROMANS, rc.AUXILIA) == 2
        assert count_pieces(state, region, rc.BELGAE, rc.ALLY) == 1


def test_cli_region_and_piece_undo_cancel_back_preserve_full_choices():
    state = _state()
    _, details, _ = _collect(state, rc.CARNUTES,
        f'place a {rc.BELGAE} Ally at a Subdued Tribe', '(back)',
        f'place a {rc.ROMANS} {rc.AUXILIA}', '(undo last operation)',
        f'place a {rc.BELGAE} {rc.WARBAND}', '(cancel this Region)',
        rc.CARNUTES, f'place a {rc.GERMANS} {rc.WARBAND}', '(done)')
    assert details['suborn_plan'][0]['actions'] == [
        _op('place', rc.GERMANS, rc.WARBAND)]


def test_cli_can_cancel_before_any_piece_or_region_is_chosen():
    state = _state()
    assert _collect(state, '(done)')[:2] == (None, None)
    assert _collect(state, rc.CARNUTES, '(cancel this Region)', '(done)')[:2] == (None, None)


def test_cli_offers_second_region_with_remaining_budget_and_independent_limits():
    state = _state(rc.CARNUTES, rc.MANDUBII, resources=2)
    activate_capability(state, 43, rc.EVENT_UNSHADED)
    regions, details, _ = _collect(state, rc.CARNUTES,
        f'place a {rc.BELGAE} {rc.WARBAND}', '(done)', rc.MANDUBII,
        f'place a {rc.GERMANS} {rc.WARBAND}', '(done)')
    result = _execute_suborn(state, rc.AEDUI, {'details': details})
    assert regions == result['regions'] == [rc.CARNUTES, rc.MANDUBII]
    assert state['resources'][rc.AEDUI] == 0


def test_native_choices_preserve_physical_colour_and_free_auxilia_with_diviciacus():
    from fs_bot.engine.diviciacus import force_scope
    state = _state(resources=0)
    activate_capability(state, 'A38', rc.EVENT_UNSHADED)
    place_piece(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA)
    roman_pool = get_available(state, rc.ROMANS, rc.AUXILIA)
    aedui_pool = get_available(state, rc.AEDUI, rc.WARBAND)
    with force_scope(state, rc.AEDUI, [rc.CARNUTES], phase='sa'):
        _, details, text = _collect(state, rc.CARNUTES,
            f'place a {rc.ROMANS} {rc.AUXILIA}', '(done)')
        assert f'place a {rc.ROMANS} {rc.AUXILIA}' in text
        result = _execute_suborn(state, rc.AEDUI, {'details': details})
        assert result['executed'], result
        # The lender's newly placed counter joins the existing effective view.
        assert count_pieces(state, rc.CARNUTES, rc.AEDUI, rc.WARBAND) == 3
    assert count_pieces(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA) == 2
    assert count_pieces(state, rc.CARNUTES, rc.AEDUI, rc.WARBAND) == 1
    assert get_available(state, rc.ROMANS, rc.AUXILIA) == roman_pool - 1
    assert get_available(state, rc.AEDUI, rc.WARBAND) == aedui_pool
    assert state['resources'][rc.AEDUI] == 0


@pytest.mark.parametrize('actions', [None, 'place_warband', [{}],
    [{'action': 'place', 'faction': rc.ROMANS, 'piece_type': rc.ALLY, 'tribe': []}]])
def test_malformed_suborn_operations_fail_without_mutation(actions):
    state = _state()
    before = encode(state)
    result = _execute_suborn(state, rc.AEDUI, _action((rc.CARNUTES, actions)))
    assert not result['executed'] and result['errors'], result
    assert encode(state) == before
