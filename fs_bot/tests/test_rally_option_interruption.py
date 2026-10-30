"""One Rally Region can straddle an SA without resetting its Command ledger."""

from copy import deepcopy
from io import StringIO

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.control import refresh_all_control
from fs_bot.board.pieces import count_pieces, get_available, place_piece, remove_piece
from fs_bot.cards.capabilities import activate_capability, set_capability_owner
from fs_bot.cards.card_effects import _ally_tribe
from fs_bot.cli.human_plan import _collect_command
from fs_bot.cli.menus import set_board_hook
from fs_bot.engine import execute as ex
from fs_bot.engine.action_validation import validate_human_structure
from fs_bot.engine.free_actions import execute_free_action_plan, validate_free_action_response
from fs_bot.engine.game_engine import ACTION_COMMAND_SA, ACTION_LIMITED_COMMAND
from fs_bot.engine.moves import preview_player_action, validate_player_action
from fs_bot.state.serialize import encode
from fs_bot.state.state_schema import build_initial_state, validate_state


def position(region=rc.PICTONES, *, bonus=True):
    state = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=12)
    state['non_player_factions'] = set()
    state['resources'][rc.ARVERNI] = 10
    place_piece(state, region, rc.ARVERNI, rc.LEADER, leader_name=rc.VERCINGETORIX)
    if bonus:
        activate_capability(state, 25, rc.EVENT_SHADED)
        set_capability_owner(state, 25, rc.ARVERNI)
    refresh_all_control(state)
    return state


def plan(*, troops_first=False):
    ally = {'region': rc.PICTONES, 'action': 'place_ally', 'tribe': rc.TRIBE_PICTONES}
    troops = {'region': rc.PICTONES, 'action': 'place_warbands', 'count': 4 if troops_first else 3}
    return {'command': rc.CMD_RALLY, 'regions': [], 'sa': rc.SA_DEVASTATE, 'sa_timing': 'during',
            'sa_regions': [rc.PICTONES], 'details': {
                'rally_plan': {'steps': [troops, ally] if troops_first else [ally, troops]},
                'sa_after_rally_step': 1}}


@pytest.mark.parametrize('troops_first,total', [(False, 5), (True, 3)])
def test_devastate_between_options_uses_live_troops_and_one_cost_and_bonus(troops_first, total):
    state = position()
    state['resources'][rc.ARVERNI] = 1
    result = ex.execute_decision(state, rc.ARVERNI, {'player_action': plan(troops_first=troops_first)})
    assert result['executed'] and not result['errors'], result
    assert result['sa_timing'] == 'during' and result['sa_execution']['executed']
    assert state['markers'][rc.PICTONES][rc.MARKER_DEVASTATED]
    assert state['resources'][rc.ARVERNI] == 0
    assert count_pieces(state, rc.PICTONES, rc.ARVERNI, rc.WARBAND) == total
    assert count_pieces(state, rc.PICTONES, rc.ARVERNI, rc.ALLY) == 1
    assert validate_state(state) == []


def entreat_plan():
    return {'command': rc.CMD_RALLY, 'sa': rc.SA_ENTREAT, 'sa_timing': 'during',
            'sa_regions': [{'region': rc.MANDUBII, 'action': 'replace_ally',
                            'target_faction': rc.AEDUI, 'tribe': rc.TRIBE_MANDUBII}],
            'details': {'sa_after_rally_step': 1, 'rally_plan': {'steps': [
                {'region': rc.MANDUBII, 'action': 'place_warbands', 'count': 2},
                {'region': rc.MANDUBII, 'action': 'place_citadel', 'tribe': rc.TRIBE_MANDUBII}]}}}


def test_entreat_can_create_the_ally_for_the_second_citadel_option():
    state = position(rc.MANDUBII, bonus=False)
    _ally_tribe(state, rc.TRIBE_MANDUBII, rc.AEDUI)
    result = ex.execute_decision(state, rc.ARVERNI, {'player_action': entreat_plan()})
    assert result['executed'] and not result['errors'], result
    assert result['sa_execution']['executed']
    assert count_pieces(state, rc.MANDUBII, rc.ARVERNI, rc.CITADEL) == 1
    assert count_pieces(state, rc.MANDUBII, rc.AEDUI, rc.ALLY) == 0
    assert state['resources'][rc.ARVERNI] == 8
    assert validate_state(state) == []


@pytest.mark.parametrize('later_count,legal', [(2, True), (3, False)])
def test_entreat_and_second_rally_option_share_the_remaining_piece_pool(later_count, legal):
    state = position()
    place_piece(state, rc.PROVINCIA, rc.ARVERNI, rc.WARBAND,
                get_available(state, rc.ARVERNI, rc.WARBAND) - 5)
    place_piece(state, rc.PICTONES, rc.ROMANS, rc.AUXILIA)
    action = plan()
    action['sa'] = rc.SA_ENTREAT
    action['sa_regions'] = [{'region': rc.PICTONES, 'action': 'replace_piece',
                             'target_faction': rc.ROMANS, 'piece_type': rc.AUXILIA}]
    action['details']['rally_plan']['steps'][1]['count'] = later_count
    before = encode(state)
    result = ex.execute_decision(state, rc.ARVERNI, {'player_action': action})
    assert result['executed'] is legal, result
    if legal:
        assert not result['errors'] and result['sa_execution']['executed']
        assert get_available(state, rc.ARVERNI, rc.WARBAND) == 0
        assert count_pieces(state, rc.PICTONES, rc.ARVERNI, rc.WARBAND) == 5
        assert count_pieces(state, rc.PICTONES, rc.ROMANS, rc.AUXILIA) == 0
    else:
        assert result['errors'] and encode(state) == before


def test_late_invalid_quantity_rolls_back_both_options_and_intervening_sa():
    state = position()
    turn = {'accepted': []}
    state['_card_turn'] = turn
    action = plan()
    action['details']['rally_plan']['steps'][1]['count'] = 4
    before = encode(state)
    result = ex.execute_decision(state, rc.ARVERNI, {'player_action': action})
    assert not result['executed'] and result['errors'] and result['rolled_back']
    assert state['_card_turn'] is turn and encode(state) == before


def test_later_option_rechecks_vercingetorix_presence(monkeypatch):
    state = position()
    before = encode(state)
    def remove_leader(board, faction, action):
        remove_piece(board, rc.PICTONES, rc.ARVERNI, rc.LEADER)
        return {'executed': True, 'sa': rc.SA_DEVASTATE}
    monkeypatch.setattr(ex, '_execute_sa', remove_leader)
    result = ex.execute_decision(state, rc.ARVERNI, {'player_action': plan()})
    assert not result['executed'] and result['errors']
    assert encode(state) == before


def test_pending_intervening_choice_restores_command_start(monkeypatch):
    state = position()
    before = encode(state)
    def pending(*args):
        raise EOFError('pending choice')
    monkeypatch.setattr(ex, '_execute_sa', pending)
    with pytest.raises(EOFError, match='pending choice'):
        ex.execute_decision(state, rc.ARVERNI, {'player_action': plan()})
    assert encode(state) == before


@pytest.mark.parametrize('field,value', [
    ('sa_after_rally_step', True), ('sa_after_rally_step', 0),
    ('sa_after_rally_step', 2), ('sa_after_rally_step', '1'),
    ('sa', 'No SA'), ('sa_timing', 'before'), ('command', rc.CMD_RAID),
    ('command_parts', []),
])
def test_invalid_interruption_shapes_are_rejected_before_mutation(field, value):
    state = position()
    action = plan()
    target = action['details'] if field in ('sa_after_rally_step', 'command_parts') else action
    target[field] = value
    before = encode(state)
    result = ex.execute_decision(state, rc.ARVERNI, {'player_action': action})
    assert not result['executed'] and result['errors']
    assert encode(state) == before


def test_limited_and_ariovistus_do_not_accept_option_level_sa():
    state = position()
    assert validate_human_structure(state, rc.ARVERNI, plan(), limited=True)
    result = ex.execute_decision(state, rc.ARVERNI,
                                {'action': ACTION_LIMITED_COMMAND, 'player_action': plan()})
    assert not result['executed']
    expansion = build_initial_state(rc.SCENARIO_ARIOVISTUS)
    assert validate_human_structure(expansion, rc.ARVERNI, plan())


def test_return_to_an_earlier_region_is_not_a_second_rally_selection():
    state = position()
    action = plan()
    action['details']['rally_plan']['steps'].insert(1, {
        'region': rc.ARVERNI_REGION, 'action': 'place_warbands', 'count': 1})
    before = encode(state)
    result = ex.execute_decision(state, rc.ARVERNI, {'player_action': action})
    assert not result['executed'] and encode(state) == before


def test_human_previews_are_pure_and_match_actual_execution():
    state = position()
    before = encode(state)
    allowed, result = validate_player_action(state, rc.ARVERNI, plan())
    assert allowed and not result.get('errors'), result
    _, _, preview = preview_player_action(state, rc.ARVERNI, plan())
    assert encode(state) == before
    ex.execute_decision(state, rc.ARVERNI, {'player_action': plan()})
    assert encode(preview) == encode(state)


def test_free_grant_counts_one_region_and_honors_sa_authorization():
    state = position()
    request = {'request_type': 'event_command', 'allowed_commands': [rc.CMD_RALLY],
               'allowed_regions': [rc.PICTONES], 'max_regions': 1, 'with_sa': True}
    before = encode(state)
    assert validate_free_action_response(state, rc.ARVERNI, request, plan()) is None
    assert encode(state) == before
    forbidden = dict(request, with_sa=False)
    assert validate_free_action_response(state, rc.ARVERNI, forbidden, plan())
    result = execute_free_action_plan(state, rc.ARVERNI, request, plan())
    assert result['executed'] and result['sa_execution']['executed'], result
    assert state['resources'][rc.ARVERNI] == 10
    assert count_pieces(state, rc.PICTONES, rc.ARVERNI, rc.WARBAND) == 5


def test_real_cli_can_insert_sa_and_inspect_updated_board_without_live_mutation():
    state = position()
    state['current_card'] = 25
    before = encode(state)
    output = StringIO()
    original_hook = lambda: output.write('ORIGINAL BOARD HOOK\n')
    set_board_hook(original_hook)
    answers = '\n'.join([
        'Command, Special Activity, then continue Command', 'Rally',
        rc.PICTONES, '(done)', 'an Ally at a Subdued Tribe', rc.TRIBE_PICTONES,
        'Use Special Activity now', 'board', 'Devastate', rc.PICTONES, '(done)',
        'b', 'Warbands', '1', ''])
    try:
        action = _collect_command(state, rc.ARVERNI, ACTION_COMMAND_SA,
                                  StringIO(answers), output)
        from fs_bot.cli import menus
        assert menus._BOARD_HOOK[0] is original_hook
    finally:
        set_board_hook(None)
    assert action == plan()
    assert encode(state) == before
    shown = output.getvalue()
    assert 'Rally planning preview' in shown and 'changes since your last' in shown
    assert 'Aquitani' in shown and 'Devastated' in shown
    assert 'ORIGINAL BOARD HOOK' not in shown
    result = ex.execute_decision(state, rc.ARVERNI, {'player_action': action})
    assert result['executed'] and not result['errors'], result


def test_interrupted_cli_eof_restores_board_hook_and_live_state():
    state = position()
    before = encode(state)
    from fs_bot.cli.recruit_rally import collect_interrupted
    from fs_bot.cli import menus
    original = lambda: None
    set_board_hook(original)
    try:
        with pytest.raises(EOFError):
            collect_interrupted(state, rc.ARVERNI, StringIO(
                f'{rc.PICTONES}\n(done)\nan Ally at a Subdued Tribe\n'
                f'{rc.TRIBE_PICTONES}\nUse Special Activity now\nboard\n'), StringIO())
        assert menus._BOARD_HOOK[0] is original
    finally:
        set_board_hook(None)
    assert encode(state) == before


def test_cli_warbands_then_entreat_offers_new_citadel_with_one_region_grant():
    state = position(rc.MANDUBII, bonus=False)
    _ally_tribe(state, rc.TRIBE_MANDUBII, rc.AEDUI)
    before = encode(state)
    output = StringIO()
    answers = '\n'.join([
        'Command, Special Activity, then continue Command', 'Rally',
        rc.MANDUBII, 'Warbands', '1', 'Use Special Activity now',
        'Entreat', rc.MANDUBII,
        f'replace {rc.AEDUI} Ally at {rc.TRIBE_MANDUBII} with yours', 'n',
        'a Citadel (replace your Ally at a City)', rc.TRIBE_MANDUBII, ''])
    action = _collect_command(state, rc.ARVERNI, ACTION_COMMAND_SA,
                              StringIO(answers), output,
                              allowed_commands=[rc.CMD_RALLY], max_regions=1)
    expected = dict(entreat_plan(), regions=[])
    assert action == expected
    assert encode(state) == before
    result = ex.execute_decision(state, rc.ARVERNI, {'player_action': action})
    assert result['executed'] and not result['errors'], result


def boxed_position_and_plan():
    from fs_bot.engine.spring import UNLOCK_KEY
    from fs_bot.state.setup import setup_scenario
    state = setup_scenario(rc.SCENARIO_PAX_GALLICA, seed=31)
    state['non_player_factions'] = {rc.ROMANS, rc.AEDUI, rc.BELGAE}
    state[UNLOCK_KEY] = True
    state.pop('first_winter_special', None)
    state['winter_count'] = 1
    state['current_card'] = state['current_card_id'] = 10
    action = {'command': rc.CMD_RALLY, 'details': {'rally_plan': {'steps': [
        {'region': rc.ARVERNI_REGION, 'action': 'place_warbands', 'count': 2},
        {'region': rc.ARVERNI_REGION, 'action': 'place_citadel', 'tribe': rc.TRIBE_ARVERNI},
    ]}}}
    return state, action


def test_explicit_entry_between_options_is_applied_before_live_option_validation():
    from fs_bot.engine.action_windows import scope
    state, action = boxed_position_and_plan()
    entry = action['details']['rally_plan']['steps'][1]
    entry['timing_actions'] = [{'kind': 'spring_leader', 'response': {'region': rc.ARVERNI_REGION}}]
    before = encode(state)
    preview = deepcopy(state)
    preview['_diviciacus_preview'] = True
    with scope(preview, actor=rc.ARVERNI, plan=action):
        result = ex.execute_decision(preview, rc.ARVERNI, {'player_action': action})
    assert result['executed'] and not result['errors'], result
    assert count_pieces(preview, rc.ARVERNI_REGION, rc.ARVERNI, rc.CITADEL) == 1
    assert count_pieces(preview, rc.ARVERNI_REGION, rc.ARVERNI, rc.WARBAND) == 4
    assert encode(state) == before
    assert validate_state(preview) == []


def test_cli_can_plan_spring_entry_before_second_option_and_preserves_tail_choices():
    from fs_bot.cli.human_plan import _collect_rally
    state, _ = boxed_position_and_plan()
    state['_cli_action_windows'] = True
    before = encode(state)
    answers = '\n'.join([
        rc.ARVERNI_REGION, 'Finish voluntary removal', 'Leave in the Spring box for now',
        'Warbands', '1', 'Finish voluntary removal', rc.ARVERNI_REGION,
        'a Citadel (replace your Ally at a City)', rc.TRIBE_ARVERNI,
        'Finish voluntary removal', ''])
    details = _collect_rally(state, rc.ARVERNI, StringIO(answers), StringIO(), single=True)
    steps = details['rally_plan']['steps']
    assert len(steps) == 2
    assert steps[0]['timing_actions'][-1]['response'] == {'defer': True}
    assert steps[1]['timing_actions'][-1]['response'] == {'region': rc.ARVERNI_REGION}
    assert details['after_command_timing_actions'] == [
        {'kind': 'voluntary_removal', 'response': {'done': True}}]
    assert encode(state) == before
    result = ex.execute_decision(state, rc.ARVERNI, {'player_action': {
        'command': rc.CMD_RALLY, 'details': details}})
    assert result['executed'] and not result['errors'], result
    assert count_pieces(state, rc.ARVERNI_REGION, rc.ARVERNI, rc.CITADEL) == 1


@pytest.mark.parametrize('sa_before_tail,total', [(True, 2), (False, 3)])
def test_cli_tail_removal_preserves_its_order_relative_to_sa(sa_before_tail, total):
    from fs_bot.cli.recruit_rally import collect_interrupted
    state = position()
    state['_cli_action_windows'] = True
    before = encode(state)
    prefix = [rc.PICTONES, '(done)', 'Finish voluntary removal', 'Warbands', '1',
              'Use Special Activity now' if sa_before_tail else 'Continue Rally']
    sa = ['Devastate', 'Finish voluntary removal', 'Finish voluntary removal',
          rc.PICTONES, 'Finish voluntary removal']
    maximum = 3 if sa_before_tail else 4
    tail = [f'Remove {rc.WARBAND} {rc.HIDDEN} in {rc.PICTONES} [up to {maximum}]',
            '1', 'Finish voluntary removal', 'Finish this Region']
    answers = prefix + (sa + tail if sa_before_tail else tail + sa) + ['']
    action = collect_interrupted(state, rc.ARVERNI, StringIO('\n'.join(answers)), StringIO())
    assert len(action['details']['rally_plan']['steps']) == 1
    assert bool(action['details'].get('sa_after_rally_step')) is sa_before_tail
    assert action['details']['after_command_timing_actions'][0]['response']['operations']
    assert encode(state) == before
    result = ex.execute_decision(state, rc.ARVERNI, {'player_action': action})
    assert result['executed'] and not result['errors'], result
    assert result['sa_execution']['executed']
    assert count_pieces(state, rc.PICTONES, rc.ARVERNI, rc.WARBAND) == total


@pytest.mark.parametrize('entry_stage', ['rally_option', 'special_ability'])
def test_pending_entry_survives_save_resume_and_exact_replay(tmp_path, entry_stage):
    from fs_bot.cli.display import HumanTurnDisplay
    from fs_bot.engine.action_windows import scope
    from fs_bot.engine.game_engine import _action_transaction
    from fs_bot.state.serialize import decode, load_game, save_game
    from fs_bot.tools.seat_session import DecisionPending, SeatSession, board_copy
    state, action = boxed_position_and_plan()
    if entry_stage == 'special_ability':
        action.update(sa=rc.SA_DEVASTATE, sa_timing='during', sa_regions=[rc.ARVERNI_REGION])
        action['details']['sa_after_rally_step'] = 1
    origin = deepcopy(state)

    def attach(board, meta=None, log=None):
        session = SeatSession(board, meta or {'seat': rc.ARVERNI}, log or [],
                              HumanTurnDisplay(StringIO()))
        def agent(current, faction, request):
            window = request.get('window') or {}
            if (request['kind'] == 'spring_leader'
                    and window.get('stage') == entry_stage
                    and (entry_stage != 'rally_option' or window.get('index') == 1)):
                return session.reactive(current, faction, request)
            return None
        agent.supports_action_windows = True
        board['decision_agent'] = agent
        return session

    def execute(session):
        def driver(*args):
            pass
        driver.transaction_checkpoint = session.checkpoint
        driver.transaction_restore = session.restore
        with _action_transaction(session.state, driver):
            with scope(session.state, actor=rc.ARVERNI, plan=action):
                return ex.execute_decision(session.state, rc.ARVERNI, {'player_action': action})

    session = attach(state)
    with pytest.raises(DecisionPending):
        execute(session)
    pending = deepcopy(session.data['pending'])
    pending_board = decode(pending['board'])
    assert count_pieces(pending_board, rc.ARVERNI_REGION, rc.ARVERNI, rc.WARBAND) == 4
    assert rc.VERCINGETORIX in pending_board['spring_box_leaders']
    assert encode(board_copy(state)) == encode(origin)
    save_game(state, tmp_path / 'rally.json', meta=session.meta, log=session.log)
    saved, meta, log = load_game(tmp_path / 'rally.json')
    resumed = attach(saved, meta, log)
    resumed.import_inbox({'decision_id': pending['id'], 'response': {'region': rc.ARVERNI_REGION}})
    result = execute(resumed)
    resumed.finish()
    assert result['executed'] and not result['errors'], result
    assert len(resumed.log) == 1
    assert count_pieces(saved, rc.ARVERNI_REGION, rc.ARVERNI, rc.CITADEL) == 1
    assert count_pieces(saved, rc.ARVERNI_REGION, rc.ARVERNI, rc.WARBAND) == (
        3 if entry_stage == 'special_ability' else 4)
    assert saved['resources'][rc.ARVERNI] == origin['resources'][rc.ARVERNI] - 1
    assert validate_state(saved) == []
    replay = attach(deepcopy(origin))
    replay.data['queue'] = [SeatSession._inbox_entry(entry) for entry in resumed.log]
    assert execute(replay) == result
    replay.finish()
    assert encode(board_copy(replay.state)) == encode(board_copy(saved))
