"""§3.3.3/Card8: humans choose every legal Raider and its own target."""
import io

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces_by_state, place_piece
from fs_bot.cli.human_plan import _collect_raid
from fs_bot.commands.sa_enlist import begin_borrow, end_borrow
from fs_bot.engine.execute import _execute_raid
from fs_bot.state.serialize import encode
from fs_bot.state.state_schema import build_initial_state


def _state():
    return build_initial_state(rc.SCENARIO_PAX_GALLICA, seed=7)


def _collect(state, faction, lines, *, single=True, excluded=()):
    before = encode(state)
    output = io.StringIO()
    result = _collect_raid(state, faction, io.StringIO('\n'.join(lines) + '\n'),
                           output, single, excluded=excluded)
    assert encode(state) == before  # No reveals, Resources, or policy RNG spent.
    return result, output.getvalue()


def test_two_raiders_can_choose_different_targets_in_one_region():
    state = _state()
    place_piece(state, rc.NERVII, rc.AEDUI, rc.WARBAND, 3)
    place_piece(state, rc.NERVII, rc.ROMANS, rc.AUXILIA)
    state['resources'][rc.ROMANS] = 1
    details, _ = _collect(state, rc.AEDUI, [rc.NERVII, '2',
                        'gain 1 Resource', f'steal from {rc.ROMANS}'])
    assert details == {'raid_plan': [{'region': rc.NERVII, 'target': None},
                                     {'region': rc.NERVII, 'target': rc.ROMANS}]}
    result = _execute_raid(state, rc.AEDUI, {'details': details})
    assert result['executed'] and not result.get('errors')
    assert state['resources'][rc.AEDUI] == 2
    assert state['resources'][rc.ROMANS] == 0
    assert count_pieces_by_state(state, rc.NERVII, rc.AEDUI, rc.WARBAND, rc.HIDDEN) == 1


@pytest.mark.parametrize('owner,maximum', [(None, 2), (rc.BELGAE, 2), (rc.AEDUI, 3)])
def test_card8_third_raider_is_offered_only_to_the_shaded_owner(owner, maximum):
    state = _state()
    place_piece(state, rc.NERVII, rc.AEDUI, rc.WARBAND, 4)
    if owner:
        state['capabilities'][8] = rc.EVENT_SHADED
        state['capability_owners'] = {8: owner}
    details, shown = _collect(state, rc.AEDUI,
        [rc.NERVII, str(maximum)] + ['gain 1 Resource'] * maximum)
    assert len(details['raid_plan']) == maximum
    assert ('  3) 3\n' in shown) == (maximum == 3)
    result = _execute_raid(state, rc.AEDUI, {'details': details})
    assert result['executed'] and not result.get('errors')
    assert state['resources'][rc.AEDUI] == maximum
    assert count_pieces_by_state(state, rc.NERVII, rc.AEDUI, rc.WARBAND,
                                 rc.REVEALED) == maximum


def test_borrowed_and_native_raiders_reserve_their_physical_owner_counts():
    state = _state()
    place_piece(state, rc.NERVII, rc.BELGAE, rc.LEADER, leader_name=rc.AMBIORIX)
    place_piece(state, rc.NERVII, rc.BELGAE, rc.WARBAND)
    place_piece(state, rc.NERVII, rc.GERMANS, rc.WARBAND)
    action = {'command': rc.CMD_RAID, 'sa': rc.SA_ENLIST, 'sa_regions': [rc.NERVII],
              'details': {'enlist': {'type': 'borrow', 'regions': [rc.NERVII]}}}
    begin_borrow(state, action)
    try:
        details, shown = _collect(state, rc.BELGAE, [rc.NERVII, '2',
            'gain 1 Resource', rc.GERMANS, 'gain 1 Resource'])
        assert [entry['physical_owner'] for entry in details['raid_plan']] == [
            rc.GERMANS, rc.BELGAE]
        assert shown.count('Reveal a Warband belonging to which Faction?') == 1
        result = _execute_raid(state, rc.BELGAE, {'details': details})
        assert result['executed'] and not result.get('errors')
    finally:
        end_borrow(state)
    for owner in (rc.BELGAE, rc.GERMANS):
        assert count_pieces_by_state(state, rc.NERVII, owner, rc.WARBAND,
                                     rc.REVEALED) == 1
    assert state['resources'][rc.BELGAE] == 2


def test_victim_resources_are_reserved_across_flips_and_regions():
    state = _state()
    for region in (rc.MORINI, rc.NERVII):
        place_piece(state, region, rc.AEDUI, rc.WARBAND, 2)
        place_piece(state, region, rc.ROMANS, rc.AUXILIA)
    state['resources'][rc.ROMANS] = 1
    details, shown = _collect(state, rc.AEDUI, [rc.MORINI, rc.NERVII,
        '2', f'steal from {rc.ROMANS}', 'gain 1 Resource',
        '2', 'gain 1 Resource', 'gain 1 Resource'], single=False)
    assert [entry['target'] for entry in details['raid_plan']] == [rc.ROMANS, None, None, None]
    assert shown.count(f'steal from {rc.ROMANS}') == 1
    result = _execute_raid(state, rc.AEDUI, {'details': details})
    assert result['executed'] and not result.get('errors')
    assert state['resources'][rc.AEDUI] == 4
    assert state['resources'][rc.ROMANS] == 0


def test_devastation_limits_raider_count_to_resources_that_can_be_stolen():
    state = _state()
    place_piece(state, rc.NERVII, rc.AEDUI, rc.WARBAND, 3)
    place_piece(state, rc.NERVII, rc.ROMANS, rc.AUXILIA)
    state['resources'][rc.ROMANS] = 1
    state['markers'][rc.NERVII] = {rc.MARKER_DEVASTATED: True}
    details, shown = _collect(state, rc.AEDUI,
        [rc.NERVII, f'steal from {rc.ROMANS}'])
    assert details == {'raid_plan': [{'region': rc.NERVII, 'target': rc.ROMANS}]}
    assert 'gain 1 Resource' not in shown
    assert 'how many' not in shown


def test_candidate_and_target_menus_keep_hidden_scope_and_fortification_checks():
    state = _state()
    place_piece(state, rc.MORINI, rc.AEDUI, rc.WARBAND, piece_state=rc.REVEALED)
    for region in (rc.NERVII, rc.TREVERI, rc.ATREBATES):
        place_piece(state, region, rc.AEDUI, rc.WARBAND)
    place_piece(state, rc.NERVII, rc.ROMANS, rc.FORT)
    state['resources'][rc.ROMANS] = 5
    state['_cli_allowed_regions'] = [rc.MORINI, rc.NERVII, rc.ATREBATES]
    details, shown = _collect(state, rc.AEDUI, [rc.NERVII, 'gain 1 Resource'],
                              excluded=[rc.ATREBATES])
    assert details == {'raid_plan': [{'region': rc.NERVII, 'target': None}]}
    assert all(region not in shown for region in (rc.MORINI, rc.TREVERI, rc.ATREBATES))
    assert f'steal from {rc.ROMANS}' not in shown
