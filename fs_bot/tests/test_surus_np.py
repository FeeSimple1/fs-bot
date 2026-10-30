"""Card 51 and §8.2.3: printed chooser priorities with native German rules."""
from copy import deepcopy
import pytest

from fs_bot import rules_consts as rc
from fs_bot.board import pieces
from fs_bot.board.control import refresh_all_control
from fs_bot.cards.surus_np import choose_surus_action
from fs_bot.commands.sa_enlist import scoped_free_force
from fs_bot.engine.free_actions import validate_free_action_response, execute_free_action_plan
from fs_bot.state.state_schema import build_initial_state


def position(count=4, seed=51):
    state = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=seed)
    state['non_player_factions'] = {rc.ROMANS, rc.ARVERNI, rc.AEDUI, rc.BELGAE}
    state['resources'].update({f: 10 for f in state['non_player_factions']})
    pieces.place_piece(state, rc.TREVERI, rc.GERMANS, rc.WARBAND, count)
    return state


def choose(state, chooser, count=4):
    refresh_all_control(state)
    with scoped_free_force(state, rc.TREVERI, {rc.HIDDEN: count}, source='Surus'):
        return choose_surus_action(state, chooser, rc.TREVERI)


def execute(state, chooser, action, count=4):
    request = {'kind': 'free_action', 'request_type': 'event_command', 'card_id': 51,
               'acting_faction': rc.GERMANS, 'allowed_commands': [rc.CMD_MARCH, rc.CMD_RAID, rc.CMD_BATTLE],
               'allowed_regions': [rc.TREVERI], 'max_regions': 1, 'with_sa': False, 'free': True}
    with scoped_free_force(state, rc.TREVERI, {rc.HIDDEN: count}, source='Surus'):
        assert validate_free_action_response(state, chooser, request, action) is None
        result = execute_free_action_plan(state, chooser, request, action)
    assert result['executed'], result


@pytest.mark.parametrize('chooser', [rc.BELGAE, rc.AEDUI])
def test_gallic_chooser_battles_with_german_intrinsic_ambush(chooser):
    state = position()
    enemy = rc.ARVERNI
    pieces.place_piece(state, rc.TREVERI, enemy, rc.WARBAND, 1)
    pieces.place_piece(state, rc.TREVERI, enemy, rc.ALLY)
    action = choose(state, chooser)
    assert action['command'] == rc.CMD_BATTLE
    assert action['sa'] == 'No SA'
    assert action['details']['battle_plan'] == [{'region': rc.TREVERI, 'target': enemy}]
    execute(state, chooser, action)
    assert pieces.count_pieces(state, rc.TREVERI, enemy) == 0


def test_belgae_battle_gate_uses_four_placed_not_resident_warbands():
    state = position(8)
    pieces.place_piece(state, rc.TREVERI, rc.ROMANS, rc.LEGION, from_legions_track=True)
    assert choose(state, rc.BELGAE, count=3) is None
    assert choose(state, rc.BELGAE, count=4)['command'] == rc.CMD_BATTLE


def test_equal_hidden_defenders_prevent_intrinsic_battle_and_force_belgic_withdrawal():
    state = position()
    pieces.place_piece(state, rc.TREVERI, rc.ARVERNI, rc.WARBAND, 4)
    pieces.place_piece(state, rc.MANDUBII, rc.BELGAE, rc.WARBAND)
    action = choose(state, rc.BELGAE)
    assert action['command'] == rc.CMD_MARCH
    assert action['details']['groups'] == {rc.TREVERI: {rc.WARBAND: 4}}
    assert len(action['details']['destinations']) == 1
    execute(state, rc.BELGAE, action)
    assert pieces.count_pieces(state, rc.TREVERI, rc.GERMANS) == 0


@pytest.mark.parametrize('chooser', [rc.ROMANS, rc.ARVERNI])
def test_no_native_leader_or_remote_troops_projected_into_surus_battle(chooser):
    state = position()
    pieces.place_piece(state, rc.TREVERI, rc.AEDUI, rc.ALLY)
    pieces.place_piece(state, rc.NERVII, chooser, rc.LEADER,
                       leader_name=rc.CAESAR if chooser == rc.ROMANS else rc.VERCINGETORIX)
    action = choose(state, chooser)
    assert action is None or action['command'] != rc.CMD_BATTLE


@pytest.mark.parametrize('chooser', [rc.AEDUI, rc.ARVERNI])
def test_spread_march_is_one_group_one_warband_and_leaves_one(chooser):
    state = position(7)
    pieces.place_piece(state, rc.NERVII, rc.GERMANS, rc.WARBAND, 4)
    action = choose(state, chooser, count=2)
    assert action['command'] == rc.CMD_MARCH
    assert action['details']['origins'] == [rc.TREVERI]
    assert len(action['details']['destinations']) == 1
    assert action['details']['groups'] == {rc.TREVERI: {rc.WARBAND: 1}}
    assert action['details']['extra_groups'] == []
    execute(state, chooser, action, count=2)
    assert pieces.count_pieces(state, rc.TREVERI, rc.GERMANS, rc.WARBAND) == 6
    assert pieces.count_pieces(state, rc.NERVII, rc.GERMANS, rc.WARBAND) == 4


def test_aedui_spreading_prioritizes_enemy_base_and_never_moves_remote_germans():
    state = position()
    pieces.place_piece(state, rc.MANDUBII, rc.ARVERNI, rc.ALLY)
    pieces.place_piece(state, rc.UBII, rc.GERMANS, rc.WARBAND, 6)
    action = choose(state, rc.AEDUI)
    assert action['details']['destinations'] == [rc.MANDUBII]
    execute(state, rc.AEDUI, action)
    assert pieces.count_pieces(state, rc.MANDUBII, rc.GERMANS, rc.WARBAND) == 1
    assert pieces.count_pieces(state, rc.UBII, rc.GERMANS, rc.WARBAND) == 6


@pytest.mark.parametrize('chooser', [rc.AEDUI, rc.BELGAE])
def test_low_resource_raid_branch_gains_zero_and_does_not_substitute_march(chooser):
    state = position(seed=1)  # first die is 2
    state['resources'][chooser] = 0
    pieces.place_piece(state, rc.TREVERI, rc.ROMANS, rc.AUXILIA)
    before = deepcopy(state['resources'])
    assert choose(state, chooser) is None
    assert state['resources'] == before


def test_arverni_native_strategic_gate_does_not_use_german_available_pool():
    state = position()
    # With six native bases and fewer than six native Available Warbands,
    # V4 declines spread. Its bottom March needs the unavailable Leader.
    for region in (rc.NERVII, rc.MANDUBII, rc.SEQUANI, rc.CARNUTES, rc.AEDUI_REGION, rc.ARVERNI_REGION):
        pieces.place_piece(state, region, rc.ARVERNI, rc.ALLY)
        tribe = next(t for t, info in state['tribes'].items() if rc.TRIBE_TO_REGION.get(t) == region)
        state['tribes'][tribe]['allied_faction'] = rc.ARVERNI
    pieces.place_piece(state, rc.ARVERNI_REGION, rc.ARVERNI, rc.WARBAND,
                       pieces.get_available(state, rc.ARVERNI, rc.WARBAND) - 5)
    assert pieces.get_available(state, rc.GERMANS, rc.WARBAND) >= 6
    assert choose(state, rc.ARVERNI) is None


def test_roman_march_targets_native_enemy_base_with_actual_free_germans():
    state = position(7)
    state['resources'][rc.ROMANS] = 0
    pieces.place_piece(state, rc.MANDUBII, rc.ARVERNI, rc.ALLY)
    action = choose(state, rc.ROMANS)
    assert action['command'] == rc.CMD_MARCH
    assert action['details']['destinations'] == [rc.MANDUBII]
    execute(state, rc.ROMANS, action)
    assert pieces.count_pieces(state, rc.MANDUBII, rc.GERMANS, rc.WARBAND) == 4
    assert pieces.count_pieces(state, rc.TREVERI, rc.GERMANS, rc.WARBAND) == 3
    assert state['resources'][rc.ROMANS] == 0


def test_roman_clean_origin_rule_sees_resident_native_german_ally():
    state = position()
    pieces.place_piece(state, rc.TREVERI, rc.GERMANS, rc.ALLY)
    pieces.place_piece(state, rc.MANDUBII, rc.ARVERNI, rc.ALLY)
    assert choose(state, rc.ROMANS) is None


def test_planning_preserves_board_input_and_has_replayable_ties():
    state = position()
    state['decision_agent'] = lambda *args: pytest.fail('planning called live input')
    other = deepcopy(state)
    before = deepcopy(state['spaces'])
    assert choose(state, rc.ARVERNI) == choose(other, rc.ARVERNI)
    assert state['spaces'] == before
    assert state['rng'].getstate() == other['rng'].getstate()


def test_frost_free_march_remains_legal_if_no_player_is_advanced():
    state = position()
    state['frost'] = True
    action = choose(state, rc.AEDUI)
    assert action['command'] == rc.CMD_MARCH
    execute(state, rc.AEDUI, action)


def test_surus_does_not_leak_into_ariovistus_or_unscoped_german_forces():
    state = position()
    with pytest.raises(ValueError, match='newly placed'):
        choose_surus_action(state, rc.BELGAE, rc.TREVERI)
    state['scenario'] = rc.SCENARIO_ARIOVISTUS
    with pytest.raises(ValueError, match='replaced'):
        choose(state, rc.BELGAE)


def test_caesar_possible_counterattack_is_not_suppressed_by_intrinsic_ambush():
    state = position()
    pieces.place_piece(state, rc.TREVERI, rc.ROMANS, rc.LEADER, leader_name=rc.CAESAR)
    pieces.place_piece(state, rc.TREVERI, rc.ROMANS, rc.LEGION, 4, from_legions_track=True)
    # Germans inflict two, but Caesar's successful Ambush roll permits the
    # surviving Caesar and two Legions to Counterattack for three Losses.
    assert choose(state, rc.BELGAE)['command'] == rc.CMD_MARCH


def test_frost_battle_cannot_advance_human_arverni_victory_by_removing_legion():
    from fs_bot.engine.victory import calculate_victory_margin
    state = position()
    state['non_player_factions'].remove(rc.ARVERNI)
    state['frost'] = True
    # Ten Arverni Allies and seven off-map Legions => margin one. Removing
    # this Legion increases the player's margin to two, prohibited by 8.4.4.
    for tribe in list(state['tribes'])[:10]:
        region = rc.TRIBE_TO_REGION[tribe]
        pieces.place_piece(state, region, rc.ARVERNI, rc.ALLY)
        state['tribes'][tribe]['allied_faction'] = rc.ARVERNI
    pieces.place_piece(state, rc.TREVERI, rc.ROMANS, rc.LEGION, from_legions_track=True)
    pieces.place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.LEGION, 4, from_legions_track=True)
    assert calculate_victory_margin(state, rc.ARVERNI) == 1
    action = choose(state, rc.BELGAE)
    assert action is None or action['command'] != rc.CMD_BATTLE
