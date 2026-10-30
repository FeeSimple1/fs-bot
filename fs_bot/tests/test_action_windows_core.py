"""Rules timing changes legality without borrowing another player's authority."""
from copy import deepcopy

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces, get_available, place_piece
from fs_bot.commands.common import CommandError
from fs_bot.commands.sa_scout import scout_move
from fs_bot.commands.raid import raid_in_region
from fs_bot.engine import action_windows as timing, voluntary_removal as removal
from fs_bot.engine.execute import execute_decision, _execute_suborn
from fs_bot.engine.moves import preview_player_action
from fs_bot.engine.spring import UNLOCK_KEY
from fs_bot.state.serialize import encode
from fs_bot.state.state_schema import build_initial_state, validate_state


def board():
    state = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=124)
    state['non_player_factions'] = set()
    state['resources'][rc.AEDUI] = state['resources'][rc.ROMANS] = 20
    return state


def reclaim(region, piece, *, count=1, cohort=None):
    op = {'action': 'remove', 'region': region, 'piece_type': piece, 'count': count}
    if piece in rc.FLIPPABLE_PIECES:
        op['piece_state'] = rc.HIDDEN
    if cohort:
        op['cohort'] = cohort
    return {'kind': removal.KIND, 'response': {'operations': [op]}}


class Agent:
    supports_action_windows = True

    def __init__(self, response=None):
        self.response, self.seen = response, []

    def __call__(self, state, faction, request):
        self.seen.append((faction, deepcopy(request)))
        if self.response:
            answer = self.response(state, faction, request)
            if answer is not None:
                return answer
        if request['kind'] == removal.KIND:
            return {'done': True}
        if request['kind'] == 'spring_leader':
            return {'defer': True}
        return None


def test_nested_grant_keeps_outer_event_ownership_and_scope_is_ephemeral():
    state = board()
    place_piece(state, rc.CARNUTES, rc.AEDUI, rc.WARBAND)
    place_piece(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA)
    agent = Agent()
    state['decision_agent'] = agent
    with timing.scope(state, actor=rc.AEDUI):
        with timing.scope(state, actor=rc.ROMANS, force=True):
            timing.window(state, 'free_command', author=rc.ROMANS)
            with pytest.raises(CommandError, match='executing player'):
                timing.apply_authored(state, rc.ROMANS,
                    [reclaim(rc.CARNUTES, rc.AUXILIA)])
    assert {f for f, req in agent.seen if req['kind'] == removal.KIND} == {rc.AEDUI}
    assert timing.SCOPE not in state and timing.BUSY not in state and timing.COHORTS not in state


def test_two_authored_batches_advance_exact_registered_cohort():
    state = board()
    place_piece(state, rc.CARNUTES, rc.AEDUI, rc.WARBAND, 3)
    with timing.scope(state, actor=rc.AEDUI, force=True):
        timing.set_cohorts(state, 'event', rc.AEDUI, [
            {'id': 'event:placed', 'label': 'Placed by this Event',
             'region': rc.CARNUTES, 'piece_type': rc.WARBAND,
             'piece_state': rc.HIDDEN, 'count': 2}])
        actions = [reclaim(rc.CARNUTES, rc.WARBAND, cohort='event:placed')]*2
        timing.window(state, 'event_step', author=rc.AEDUI, timing_actions=actions)
        assert timing.get_cohorts(state, 'event')[0]['count'] == 0
    assert count_pieces(state, rc.CARNUTES, rc.AEDUI, rc.WARBAND) == 1
    assert validate_state(state) == []


def test_legacy_agent_receives_no_added_requests_and_no_scope_metadata():
    state = board()
    before = encode(state)
    state['decision_agent'] = lambda *args: pytest.fail('Unexpected new request')
    with timing.scope(state, actor=rc.AEDUI):
        timing.window(state, 'example')
        assert timing.SCOPE not in state
    state.pop('decision_agent')
    assert encode(state) == before


def test_direct_grant_cannot_silently_ignore_unauthorized_authored_removal():
    state = board()
    place_piece(state, rc.CARNUTES, rc.AEDUI, rc.WARBAND)
    before = encode(state)
    with pytest.raises(CommandError, match='active Command'):
        timing.window(state, 'free_command', author=rc.AEDUI,
                       timing_actions=[reclaim(rc.CARNUTES, rc.WARBAND)])
    assert encode(state) == before


def test_removal_before_recruit_can_supply_a_previously_empty_pool_purely():
    state = board()
    place_piece(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA,
                get_available(state, rc.ROMANS, rc.AUXILIA))
    place_piece(state, rc.MANDUBII, rc.ROMANS, rc.FORT)
    action = {'command': rc.CMD_RECRUIT, 'sa': 'No SA', 'details': {
        'recruit_plan': [{'region': rc.MANDUBII, 'action': 'place_auxilia', 'count': 1,
                          'timing_actions': [reclaim(rc.CARNUTES, rc.AUXILIA)]}]}}
    original = encode(state)
    _, _, preview = preview_player_action(state, rc.ROMANS, action)
    assert encode(state) == original
    result = execute_decision(state, rc.ROMANS, {'player_action': action})
    assert result['executed'] and not result.get('errors'), result
    assert encode(state) == encode(preview)
    assert count_pieces(state, rc.MANDUBII, rc.ROMANS, rc.AUXILIA) == 1


def test_failed_exact_command_restores_earlier_authored_removal():
    state = board()
    place_piece(state, rc.CARNUTES, rc.AEDUI, rc.WARBAND)
    action = {'command': rc.CMD_RALLY, 'sa': 'No SA', 'details': {
        'timing_actions': [reclaim(rc.CARNUTES, rc.WARBAND)],
        'rally_plan': {'steps': [{'region': rc.CARNUTES,
                                  'action': 'place_warbands', 'count': 100}]}}}
    before = encode(state)
    result = execute_decision(state, rc.AEDUI, {'player_action': action})
    assert not result['executed'] and result['rolled_back']
    assert encode(state) == before


def test_suborn_can_reclaim_before_each_operation_without_preflight_rejection():
    state = board()
    place_piece(state, rc.CARNUTES, rc.AEDUI, rc.WARBAND)
    place_piece(state, rc.NERVII, rc.AEDUI, rc.WARBAND,
                get_available(state, rc.AEDUI, rc.WARBAND))
    def choose(current, faction, request):
        if (request['kind'] == removal.KIND
                and request.get('window', {}).get('stage') == 'suborn_operation'
                and get_available(current, faction, rc.WARBAND) == 0):
            return reclaim(rc.NERVII, rc.WARBAND)['response']
    state['decision_agent'] = Agent(choose)
    operations = [{'action': 'place', 'faction': rc.AEDUI, 'piece_type': rc.WARBAND}]*2
    with timing.scope(state, actor=rc.AEDUI):
        result = _execute_suborn(state, rc.AEDUI, {'details': {'suborn_plan': [
            {'region': rc.CARNUTES, 'actions': operations}]}})
    assert result['executed'] and not result['errors'], result
    assert count_pieces(state, rc.CARNUTES, rc.AEDUI, rc.WARBAND) == 3
    assert state['resources'][rc.AEDUI] == 18


def move(origin, target, count=1, **extra):
    return {'from_region': origin, 'to_region': target, 'count': count,
            'piece_state': rc.HIDDEN, **extra}


def test_scout_rejects_moving_arrivals_twice_and_restores_the_batch():
    state = board()
    place_piece(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA, 2)
    before = encode(state)
    with pytest.raises(CommandError, match='move twice'):
        scout_move(state, [move(rc.CARNUTES, rc.MANDUBII),
                           move(rc.MANDUBII, rc.SEQUANI)])
    assert encode(state) == before


@pytest.mark.parametrize('moved', [False, True])
def test_scout_removal_distinguishes_moved_arrivals_and_residents(moved):
    state = board()
    place_piece(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA)
    place_piece(state, rc.MANDUBII, rc.ROMANS, rc.AUXILIA, 2)
    identifier = f'scout:{rc.ROMANS}:{rc.MANDUBII}:{rc.HIDDEN}' if moved else None
    removal_action = reclaim(rc.MANDUBII, rc.AUXILIA, cohort=identifier)
    # Two unmoved residents survive only when the arrival was removed.
    plan = [move(rc.CARNUTES, rc.MANDUBII),
            move(rc.MANDUBII, rc.SEQUANI, 2, timing_actions=[removal_action])]
    before = encode(state)
    with timing.scope(state, actor=rc.ROMANS, force=True):
        if moved:
            scout_move(state, plan)
        else:
            with pytest.raises(CommandError, match='move twice'):
                scout_move(state, plan)
    if moved:
        assert count_pieces(state, rc.SEQUANI, rc.ROMANS, rc.AUXILIA) == 2
        assert count_pieces(state, rc.MANDUBII, rc.ROMANS, rc.AUXILIA) == 0
        assert validate_state(state) == []
    else:
        assert encode(state) == before


def test_mid_raid_spring_entry_enables_a_later_steal():
    state = build_initial_state(rc.SCENARIO_PAX_GALLICA, seed=94)
    state['available'][rc.ARVERNI][rc.LEADER] -= 1
    state['spring_box_leaders'] = [rc.VERCINGETORIX]
    state[UNLOCK_KEY] = True
    state['resources'][rc.ARVERNI] = 4
    place_piece(state, rc.CARNUTES, rc.AEDUI, rc.WARBAND, 2)
    def choose(current, faction, request):
        if (request['kind'] == 'spring_leader'
                and request.get('window', {}).get('stage') == 'raid_flip'
                and request['window']['index'] == 1):
            return {'region': rc.CARNUTES}
    state['decision_agent'] = Agent(choose)
    before_rng = state['rng'].getstate()
    with timing.scope(state, actor=rc.AEDUI):
        result = raid_in_region(state, rc.CARNUTES, rc.AEDUI,
                               [{'type': 'gain'}, {'type': 'steal', 'target': rc.ARVERNI}])
    assert result['resources_gained'] == 2 and state['resources'][rc.ARVERNI] == 3
    assert state['rng'].getstate() == before_rng
    assert validate_state(state) == []


def test_removing_an_actual_raider_reduces_intrinsic_intimidate_credit():
    state = build_initial_state(rc.SCENARIO_ARIOVISTUS, seed=12)
    place_piece(state, rc.CARNUTES, rc.GERMANS, rc.LEADER,
                leader_name=rc.ARIOVISTUS_LEADER)
    place_piece(state, rc.CARNUTES, rc.GERMANS, rc.WARBAND, 2)
    place_piece(state, rc.CARNUTES, rc.GERMANS, rc.WARBAND, piece_state=rc.REVEALED)
    place_piece(state, rc.CARNUTES, rc.AEDUI, rc.WARBAND, 2)
    removed = []
    def choose(current, faction, request):
        if (not removed and request['kind'] == removal.KIND
                and request.get('window', {}).get('stage') == 'raid_flip'
                and request['window']['index'] == 1):
            selected = next(o for o in request['options']
                            if o.get('cohort') == f'raid_credit:{rc.CARNUTES}')
            removed.append(True)
            return {'operations': [removal.operation(selected)]}
        if request['kind'] == 'raid_intimidate':
            assert request['raiders'] == 1
            return {'decline': True}
    state['decision_agent'] = Agent(choose)
    with timing.scope(state, actor=rc.GERMANS):
        result = raid_in_region(state, rc.CARNUTES, rc.GERMANS,
                               [{'type': 'gain'}, {'type': 'gain'}])
    assert removed and result['resources_gained'] == 2
    assert result['raid_intimidate']['declined']
    assert count_pieces(state, rc.CARNUTES, rc.GERMANS, rc.WARBAND) == 2
    assert validate_state(state) == []


def test_recorded_noops_remain_noops_after_earlier_live_board_changes():
    state = board()
    with timing.scope(state, actor=rc.ARVERNI, force=True):
        timing.window(state, 'rally_option', author=rc.ARVERNI, timing_actions=[
            {'kind': 'spring_leader', 'response': {'defer': True}},
            {'kind': removal.KIND, 'response': {'done': True}}])
    assert validate_state(state) == []


def test_seize_loss_window_keeps_fixed_harassment_total_and_updates_next_choices():
    from fs_bot.engine.execute import _resolve_seize_harassment
    state = board()
    state['non_player_factions'] = {rc.BELGAE}
    place_piece(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA, 3)
    place_piece(state, rc.CARNUTES, rc.BELGAE, rc.WARBAND,
                2 * rc.HARASSMENT_WARBANDS_PER_LOSS)
    removed = []
    def choose(current, faction, request):
        window = request.get('window', {})
        if (not removed and request['kind'] == removal.KIND
                and window.get('stage') == 'seize_harassment_loss'
                and window['loss_index'] == 2):
            assert window['num_losses'] == 2
            removed.append(True)
            return reclaim(rc.CARNUTES, rc.AUXILIA)['response']
    state['decision_agent'] = Agent(choose)
    before_rng = state['rng'].getstate()
    with timing.scope(state, actor=rc.ROMANS):
        losses = _resolve_seize_harassment(state, rc.CARNUTES)
    assert removed and len(losses) == 2
    assert count_pieces(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA) == 0
    assert state['rng'].getstate() == before_rng


def test_vercingetorix_can_become_a_new_target_between_germans_phase_raid_flips():
    from fs_bot.commands.raid import germans_phase_raid_region
    state = build_initial_state(rc.SCENARIO_PAX_GALLICA, seed=4)
    state['available'][rc.ARVERNI][rc.LEADER] -= 1
    state['spring_box_leaders'] = [rc.VERCINGETORIX]
    state[UNLOCK_KEY] = True
    state['resources'].update({rc.AEDUI: 1, rc.ARVERNI: 2})
    place_piece(state, rc.CARNUTES, rc.GERMANS, rc.WARBAND, 2)
    place_piece(state, rc.CARNUTES, rc.AEDUI, rc.WARBAND)
    def choose(current, faction, request):
        if (request['kind'] == 'spring_leader'
                and request.get('window', {}).get('stage') == 'germans_raid_flip'
                and request['window']['index'] == 1):
            return {'region': rc.CARNUTES}
    state['decision_agent'] = Agent(choose)
    with timing.scope(state, phase='winter'):
        result = germans_phase_raid_region(state, rc.CARNUTES)
    assert result['resources_stolen'] == {rc.AEDUI: 1, rc.ARVERNI: 1}
    assert validate_state(state) == []
