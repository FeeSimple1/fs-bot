"""Dumnorix windows retain original sources and just-placed participants."""
import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import place_piece, count_pieces, count_pieces_by_state
from fs_bot.cards import dumnorix
from fs_bot.engine import action_windows, voluntary_removal
from fs_bot.engine.execute import _execute_event
from fs_bot.state.state_schema import build_initial_state, validate_state


class Agent:
    supports_action_windows = True
    def __init__(self, choose):
        self.choose, self.did = choose, False
    def __call__(self, state, faction, request):
        answer = self.choose(self, state, faction, request)
        if answer is not None:
            return answer
        if request['kind'] == voluntary_removal.KIND:
            return {'done': True}
        if request['kind'] == 'spring_leader':
            return {'defer': True}
        return None


def board():
    state = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=64)
    state['card_edition'] = 'original'
    state['executing_faction'] = rc.AEDUI
    return state


def replacement(source, destination, piece=rc.WARBAND, target_piece=rc.WARBAND,
                region=rc.CARNUTES, count=1):
    return {'region': region, 'from_faction': source, 'to_faction': destination,
            'from_type': piece, 'to_type': target_piece, 'count': count}


def play(state, faction=rc.AEDUI, shaded=False):
    with action_windows.scope(state, actor=faction, force=True):
        return _execute_event(state, faction, {'details': {'card_id': 44,
            'text_preference': rc.EVENT_SHADED if shaded else rc.EVENT_UNSHADED,
            'event_params': state['event_params']}}, human=True)


@pytest.mark.parametrize('remove_original', [False, True])
def test_replacement_window_distinguishes_original_from_new_counter(remove_original):
    state = board()
    place_piece(state, rc.CARNUTES, rc.BELGAE, rc.WARBAND)
    place_piece(state, rc.CARNUTES, rc.AEDUI, rc.WARBAND)
    state['event_params'] = {'replacements': [
        replacement(rc.BELGAE, rc.AEDUI),
        replacement(rc.AEDUI, rc.ROMANS, target_piece=rc.AUXILIA)]}
    def choose(agent, current, faction, request):
        window = request.get('window', {})
        if (not agent.did and request['kind'] == voluntary_removal.KIND
                and window.get('step') == 'dumnorix_replacement'
                and window.get('index') == 1):
            prefix = 'dumnorix.sources.' if remove_original else 'dumnorix.placed.'
            choice = next(c for c in request['options'] if c.get('cohort', '').startswith(prefix))
            agent.did = True
            return {'operations': [voluntary_removal.operation(choice)]}
    state['decision_agent'] = Agent(choose)
    assert play(state)['executed']
    assert count_pieces(state, rc.CARNUTES, rc.AEDUI, rc.WARBAND) == int(remove_original)
    assert count_pieces(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA) == int(not remove_original)
    assert validate_state(state) == []


def test_removal_at_grant_does_not_substitute_resident_scouts():
    state = board()
    place_piece(state, rc.CARNUTES, rc.ROMANS, rc.LEADER, leader_name=rc.CAESAR)
    place_piece(state, rc.CARNUTES, rc.AEDUI, rc.WARBAND, 3)
    place_piece(state, rc.CARNUTES, rc.BELGAE, rc.WARBAND, 3)
    state['event_params'] = {'replacements': [replacement(rc.BELGAE, rc.AEDUI)],
        'scout_reveals': [{'region': rc.CARNUTES, 'faction': rc.AEDUI,
                          'target_faction': rc.BELGAE, 'count': 2}]}
    def choose(agent, current, faction, request):
        if (not agent.did and request['kind'] == voluntary_removal.KIND
                and request.get('window', {}).get('step') == 'grant.card_44_free_scout'):
            choice = next(c for c in request['options'] if c.get('cohort', '').startswith('dumnorix.placed.'))
            agent.did = True
            return {'operations': [voluntary_removal.operation(choice)]}
    state['decision_agent'] = Agent(choose)
    assert play(state)['executed']
    assert count_pieces_by_state(state, rc.CARNUTES, rc.AEDUI, rc.WARBAND, rc.HIDDEN) == 3
    assert count_pieces_by_state(state, rc.CARNUTES, rc.BELGAE, rc.WARBAND, rc.SCOUTED) == 0
    assert validate_state(state) == []


@pytest.mark.parametrize('remove_arrived', [False, True])
def test_scout_movement_distinguishes_arrivals_from_pieces_allowed_to_move(remove_arrived):
    state = board()
    for region in (rc.CARNUTES, rc.MANDUBII):
        place_piece(state, region, rc.BELGAE, rc.WARBAND)
    state['event_params'] = {'replacements': [
        replacement(rc.BELGAE, rc.AEDUI, region=rc.CARNUTES),
        replacement(rc.BELGAE, rc.AEDUI, region=rc.MANDUBII)],
        'scout_moves': [
            {'from_region': rc.CARNUTES, 'to_region': rc.MANDUBII, 'faction': rc.AEDUI},
            {'from_region': rc.MANDUBII, 'to_region': rc.AEDUI_REGION, 'faction': rc.AEDUI}]}
    def choose(agent, current, faction, request):
        window = request.get('window', {})
        if (not agent.did and request['kind'] == voluntary_removal.KIND
                and window.get('step') == 'dumnorix_scout_move' and window.get('index') == 1):
            kind = 'dumnorix.arrived' if remove_arrived else 'dumnorix.original'
            choice = next(c for c in request['options'] if c.get('cohort') == kind
                          and c['region'] == rc.MANDUBII)
            agent.did = True
            return {'operations': [voluntary_removal.operation(choice)]}
    state['decision_agent'] = Agent(choose)
    assert play(state)['executed']
    assert count_pieces(state, rc.AEDUI_REGION, rc.AEDUI, rc.WARBAND) == int(remove_arrived)
    assert count_pieces(state, rc.MANDUBII, rc.AEDUI, rc.WARBAND) == int(not remove_arrived)
    assert validate_state(state) == []


def test_scout_target_choice_updates_other_new_pieces_later_eligibility():
    state = board()
    place_piece(state, rc.CARNUTES, rc.ROMANS, rc.LEADER, leader_name=rc.CAESAR)
    place_piece(state, rc.CARNUTES, rc.AEDUI, rc.WARBAND)
    place_piece(state, rc.CARNUTES, rc.BELGAE, rc.WARBAND, 4)
    state['event_params'] = {'replacements': [
        replacement(rc.BELGAE, rc.ROMANS, target_piece=rc.AUXILIA),
        replacement(rc.BELGAE, rc.AEDUI)],
        'scout_reveals': [
            {'region': rc.CARNUTES, 'faction': rc.ROMANS, 'target_faction': rc.AEDUI, 'count': 1},
            {'region': rc.CARNUTES, 'faction': rc.AEDUI, 'target_faction': rc.BELGAE, 'count': 2}]}
    def choose(agent, current, faction, request):
        if request['kind'] == 'force_cohort':
            return {'counts': {'selected': 1, 'other': 0}}
    state['decision_agent'] = Agent(choose)
    assert play(state)['executed']
    assert count_pieces_by_state(state, rc.CARNUTES, rc.AEDUI, rc.WARBAND, rc.SCOUTED) == 1
    assert count_pieces_by_state(state, rc.CARNUTES, rc.AEDUI, rc.WARBAND, rc.HIDDEN) == 1
    assert count_pieces_by_state(state, rc.CARNUTES, rc.BELGAE, rc.WARBAND, rc.SCOUTED) == 0
    assert validate_state(state) == []


def test_scout_validation_in_timed_scope_still_rejects_original_overuse():
    state = board()
    place_piece(state, rc.CARNUTES, rc.ROMANS, rc.LEADER, leader_name=rc.CAESAR)
    place_piece(state, rc.CARNUTES, rc.BELGAE, rc.WARBAND, 4)
    state['event_params'] = {'replacements': [replacement(rc.BELGAE, rc.AEDUI)],
        'scout_reveals': [{'region': rc.CARNUTES, 'faction': rc.AEDUI,
                          'target_faction': rc.BELGAE, 'count': 3, 'scouts': 2}]}
    state['decision_agent'] = Agent(lambda *args: None)
    with action_windows.scope(state, actor=rc.AEDUI, force=True):
        with pytest.raises(ValueError):
            dumnorix.execute_replacements(state, False)
    assert count_pieces(state, rc.CARNUTES, rc.BELGAE, rc.WARBAND) == 4
    assert count_pieces(state, rc.CARNUTES, rc.AEDUI, rc.WARBAND) == 0


def test_removing_last_unspent_placed_raider_preserves_first_raid_and_residents():
    state = board()
    place_piece(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA, 2)
    place_piece(state, rc.CARNUTES, rc.ARVERNI, rc.WARBAND, 2)
    state['event_params'] = {'replacements': [replacement(
        rc.ROMANS, rc.ARVERNI, piece=rc.AUXILIA, count=2)],
        'raid_actions': [{'region': rc.CARNUTES, 'faction': rc.ARVERNI},
                         {'region': rc.CARNUTES, 'faction': rc.ARVERNI}]}
    def choose(agent, current, faction, request):
        window = request.get('window', {})
        if (not agent.did and request['kind'] == voluntary_removal.KIND
                and window.get('stage') == 'raid_flip' and window.get('index') == 1):
            choice = next(c for c in request['options'] if c.get('loan_kind') == 'free_force'
                          and c.get('piece_state') == rc.HIDDEN)
            agent.did = True
            return {'operations': [voluntary_removal.operation(choice)]}
    state['decision_agent'] = Agent(choose)
    assert play(state, rc.ARVERNI, shaded=True)['executed']
    assert state['decision_agent'].did
    assert state['resources'][rc.ARVERNI] == 1
    assert count_pieces_by_state(state, rc.CARNUTES, rc.ARVERNI, rc.WARBAND, rc.HIDDEN) == 2
    assert count_pieces_by_state(state, rc.CARNUTES, rc.ARVERNI, rc.WARBAND, rc.REVEALED) == 1
    assert validate_state(state) == []


def test_replacement_validation_does_not_overwrite_rng_used_by_live_leader_entry():
    from fs_bot.engine.spring import UNLOCK_KEY
    from fs_bot.board.pieces import find_leader
    state = build_initial_state(rc.SCENARIO_PAX_GALLICA, seed=64)
    state['card_edition'] = 'original'
    state['executing_faction'] = rc.AEDUI
    state['available'][rc.ARVERNI][rc.LEADER] -= 1
    state['spring_box_leaders'] = [rc.VERCINGETORIX]
    state[UNLOCK_KEY] = True
    place_piece(state, rc.CARNUTES, rc.BELGAE, rc.WARBAND)
    state['event_params'] = {'replacements': [replacement(rc.BELGAE, rc.AEDUI)]}
    def choose(agent, current, faction, request):
        if (request['kind'] == 'spring_leader'
                and request.get('window', {}).get('step') == 'dumnorix_replacement'):
            return {'use_default': True}
    state['decision_agent'] = Agent(choose)
    before = state['rng'].getstate()
    assert play(state)['executed']
    assert find_leader(state, rc.ARVERNI) is not None
    assert state['rng'].getstate() != before
    assert validate_state(state) == []


@pytest.mark.parametrize('authored', [False, True])
def test_empty_replacement_pool_can_be_replenished_before_placing_scout(authored):
    state = board()
    place_piece(state, rc.SEQUANI, rc.AEDUI, rc.WARBAND,
                state['available'][rc.AEDUI][rc.WARBAND])
    place_piece(state, rc.CARNUTES, rc.BELGAE, rc.WARBAND)
    state['event_params'] = {'replacements': [replacement(rc.BELGAE, rc.AEDUI)],
        'scout_moves': [{'from_region': rc.CARNUTES, 'to_region': rc.MANDUBII,
                         'faction': rc.AEDUI}]}
    if authored:
        state['event_params']['stage_timing_actions'] = {'dumnorix_replacement:0': [{
            'kind': 'voluntary_removal', 'response': {'operations': [{
                'action': 'remove', 'region': rc.SEQUANI, 'piece_type': rc.WARBAND,
                'piece_state': rc.HIDDEN, 'count': 1}]}}]}
    def choose(agent, current, faction, request):
        if (not agent.did and request['kind'] == voluntary_removal.KIND
                and request.get('window', {}).get('step') == 'dumnorix_replacement'):
            choice = next(c for c in request['options'] if c['region'] == rc.SEQUANI)
            agent.did = True
            return {'operations': [voluntary_removal.operation(choice)]}
    if not authored:
        state['decision_agent'] = Agent(choose)
    assert play(state)['executed']
    assert count_pieces(state, rc.CARNUTES, rc.AEDUI, rc.WARBAND) == 0
    assert count_pieces(state, rc.MANDUBII, rc.AEDUI, rc.WARBAND) == 1
    assert state['available'][rc.AEDUI][rc.WARBAND] == 0
    assert validate_state(state) == []


def test_authored_removal_of_placed_scout_reduces_grant_in_preflight_and_live():
    state = board()
    place_piece(state, rc.CARNUTES, rc.BELGAE, rc.WARBAND)
    # A resident piece must not substitute for the removed Event Scout.
    place_piece(state, rc.CARNUTES, rc.AEDUI, rc.WARBAND)
    state['event_params'] = {'replacements': [replacement(rc.BELGAE, rc.AEDUI)],
        'scout_moves': [{'from_region': rc.CARNUTES, 'to_region': rc.MANDUBII,
                         'faction': rc.AEDUI}],
        'stage_timing_actions': {'dumnorix_scout_move:0': [{
            'kind': 'voluntary_removal', 'response': {'operations': [{
                'action': 'remove', 'region': rc.CARNUTES, 'piece_type': rc.WARBAND,
                'piece_state': rc.HIDDEN, 'cohort': 'dumnorix.original', 'count': 1}]}}]}}
    before_rng = state['rng'].getstate()
    assert play(state)['executed']
    assert count_pieces(state, rc.CARNUTES, rc.AEDUI, rc.WARBAND) == 1
    assert count_pieces(state, rc.MANDUBII, rc.AEDUI, rc.WARBAND) == 0
    assert state['rng'].getstate() == before_rng
    assert validate_state(state) == []


def test_timed_scout_plan_cannot_reuse_arriving_piece_in_original_grant():
    state = board()
    place_piece(state, rc.CARNUTES, rc.BELGAE, rc.WARBAND)
    state['event_params'] = {'replacements': [replacement(rc.BELGAE, rc.AEDUI)],
        'scout_moves': [
            {'from_region': rc.CARNUTES, 'to_region': rc.MANDUBII, 'faction': rc.AEDUI},
            {'from_region': rc.MANDUBII, 'to_region': rc.AEDUI_REGION, 'faction': rc.AEDUI}]}
    state['decision_agent'] = Agent(lambda *args: None)
    before_rng = state['rng'].getstate()
    with action_windows.scope(state, actor=rc.AEDUI, force=True):
        with pytest.raises(ValueError, match='only once'):
            dumnorix.execute_replacements(state, False)
    assert count_pieces(state, rc.CARNUTES, rc.BELGAE, rc.WARBAND) == 1
    assert count_pieces(state, rc.CARNUTES, rc.AEDUI, rc.WARBAND) == 0
    assert state['rng'].getstate() == before_rng
    assert validate_state(state) == []
