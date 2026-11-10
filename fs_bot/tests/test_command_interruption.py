"""§4.1: an intervening SA keeps the same Battle or Raid Command."""

from copy import deepcopy
from io import StringIO

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces, count_pieces_by_state, place_piece
from fs_bot.cards.capabilities import activate_capability, set_capability_owner
from fs_bot.cli.human_plan import collect_player_action
from fs_bot.engine import execute as ex
from fs_bot.engine.free_actions import execute_free_action_plan, validate_free_action_response
from fs_bot.engine.game_engine import ACTION_COMMAND_SA, ACTION_LIMITED_COMMAND
from fs_bot.engine.horse_choice import FLAGS
from fs_bot.state.serialize import encode
from fs_bot.state.state_schema import build_initial_state, validate_state
from fs_bot.tools.seat_session import validate_response


def raid_position():
    state = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=23)
    place_piece(state, rc.CARNUTES, rc.AEDUI, rc.WARBAND, 2)
    state['resources'][rc.AEDUI] = 0
    state['resources'][rc.BELGAE] = 3
    action = {'command': rc.CMD_RAID, 'sa': rc.SA_SUBORN, 'sa_timing': 'during',
              'sa_regions': [rc.CARNUTES], 'details': {
                  'sa_after_step': 1,
                  'raid_plan': [{'region': rc.CARNUTES, 'target': None},
                                {'region': rc.CARNUTES, 'target': rc.BELGAE}],
                  'suborn_plan': [{'region': rc.CARNUTES, 'actions': [
                      {'action': 'place', 'faction': rc.BELGAE, 'piece_type': rc.WARBAND}]}]}}
    return state, action


def battle_position(scenario=rc.SCENARIO_GREAT_REVOLT):
    state = build_initial_state(scenario, seed=23)
    state['resources'][rc.ROMANS] = 4
    for region in (rc.SEQUANI, rc.MANDUBII):
        place_piece(state, region, rc.ROMANS, rc.LEGION, 3, from_legions_track=True)
        place_piece(state, region, rc.BELGAE, rc.WARBAND, piece_state=rc.REVEALED)
    place_piece(state, rc.SEQUANI, rc.ROMANS, rc.AUXILIA)
    place_piece(state, rc.MANDUBII, rc.ROMANS, rc.AUXILIA)
    action = {'command': rc.CMD_BATTLE, 'sa': rc.SA_SCOUT, 'sa_timing': 'during',
              'details': {'sa_after_step': 1, 'battle_plan': [
                  {'region': rc.SEQUANI, 'target': rc.BELGAE},
                  {'region': rc.MANDUBII, 'target': rc.BELGAE}],
                  'scout_plan': {'auxilia_moves': [{'from_region': rc.SEQUANI,
                      'to_region': rc.MANDUBII, 'count': 1, 'piece_state': rc.REVEALED}]}}}
    return state, action


def run(state, faction, action):
    return ex.execute_decision(state, faction,
                               {'action': ACTION_COMMAND_SA, 'player_action': action})


def assert_raid(state, result, *, free=False):
    assert result['executed'] and not result['errors'], result
    assert result['sa_timing'] == 'during' and result['sa_execution']['executed']
    assert result['regions_resolved'] == [rc.CARNUTES]
    assert result['raids'][0]['warbands_flipped'] == 2
    assert count_pieces_by_state(state, rc.CARNUTES, rc.AEDUI, rc.WARBAND, rc.REVEALED) == 2
    assert count_pieces(state, rc.CARNUTES, rc.BELGAE, rc.WARBAND) == 1
    assert state['resources'][rc.AEDUI] == (2 if free else 1)
    assert state['resources'][rc.BELGAE] == 2
    assert validate_state(state) == []


def test_suborn_can_spend_first_raid_resource_to_make_second_flip_target_legal():
    state, action = raid_position()
    for timing in ('before', 'after'):
        unsplit = deepcopy(action)
        unsplit['sa_timing'] = timing
        del unsplit['details']['sa_after_step']
        before = encode(state)
        assert not run(state, rc.AEDUI, unsplit)['executed']
        assert encode(state) == before
    assert_raid(state, run(state, rc.AEDUI, action))


def test_terminal_raid_offers_the_new_target_after_the_sa():
    state, _ = raid_position()
    before = encode(state)
    output = StringIO()
    action = collect_player_action(state, rc.AEDUI, ACTION_COMMAND_SA, StringIO(
        'Command, Special Activity, then continue Command\n'
        f'Raid (between individual Warband flips)\n{rc.CARNUTES}\n'
        f'Gain 1 Resource\ny\nSuborn\n{rc.CARNUTES}\nplace a {rc.BELGAE} Warband\n'
        f'(done)\nSteal from {rc.BELGAE}\n'), output)
    assert action['details']['sa_after_step'] == 1
    assert encode(state) == before
    assert_raid(state, run(state, rc.AEDUI, action))


def test_declined_raid_interruption_carries_no_later_special_ability_choices(monkeypatch):
    from fs_bot.cli import human_plan

    def decline(board, faction, action, *args, **kwargs):
        action['details']['sa_details'] = {'timing_actions': [
            {'kind': 'voluntary_removal', 'response': {'done': True}}]}
        return action

    monkeypatch.setattr(human_plan, '_collect_sa_plan', decline)
    state, _ = raid_position()
    action = collect_player_action(state, rc.AEDUI, ACTION_COMMAND_SA, StringIO(
        'Command, Special Activity, then continue Command\n'
        f'Raid (between individual Warband flips)\n{rc.CARNUTES}\n'
        'Gain 1 Resource\ny\nGain 1 Resource\n'), StringIO())
    assert action['sa'] == 'No SA' and 'sa_details' not in action['details']
    assert 'sa_after_step' not in action['details']
    assert run(state, rc.AEDUI, action)['raids'][0]['warbands_flipped'] == 2


def test_one_scoped_free_raid_region_contains_both_flips():
    state, action = raid_position()
    request = {'request_type': 'event_command', 'allowed_commands': [rc.CMD_RAID],
               'with_sa': True, 'allowed_regions': [rc.CARNUTES], 'max_regions': 1}
    before = encode(state)
    assert validate_free_action_response(state, rc.AEDUI, request, action) is None
    assert encode(state) == before
    assert validate_free_action_response(state, rc.AEDUI, dict(request, with_sa=False), action)
    assert validate_free_action_response(state, rc.AEDUI, dict(request, allowed_sas=[rc.SA_TRADE]), action)
    assert_raid(state, execute_free_action_plan(state, rc.AEDUI, request, action), free=True)


def test_bad_follow_on_raid_rolls_back_the_first_flip_and_suborn():
    state, action = raid_position()
    action['details']['raid_plan'][1]['target'] = rc.ROMANS
    before = encode(state)
    result = run(state, rc.AEDUI, action)
    assert not result['executed'] and result['rolled_back'], result
    assert encode(state) == before


def test_a3_4_3_counts_only_both_raid_flips_in_one_intrinsic_intimidate():
    state = build_initial_state(rc.SCENARIO_ARIOVISTUS, seed=23)
    place_piece(state, rc.CARNUTES, rc.GERMANS, rc.LEADER, leader_name=rc.ARIOVISTUS_LEADER)
    place_piece(state, rc.CARNUTES, rc.GERMANS, rc.WARBAND, 3)
    place_piece(state, rc.CARNUTES, rc.AEDUI, rc.WARBAND, 3)
    credit = []

    def agent(board, faction, request):
        if request['kind'] == 'raid_intimidate':
            credit.append(request['raiders'])
            assert count_pieces_by_state(board, rc.CARNUTES, rc.GERMANS, rc.WARBAND, rc.REVEALED) == 3
            return {'decline': True}

    state['decision_agent'] = agent
    action = {'command': rc.CMD_RAID, 'sa': rc.SA_INTIMIDATE, 'sa_timing': 'during',
              'details': {'sa_after_step': 1, 'raid_plan': [{'region': rc.CARNUTES}] * 2,
                          'intimidate_plan': [{'region': rc.CARNUTES,
                              'target_faction': rc.AEDUI, 'target_piece': rc.WARBAND,
                              'target_state': rc.HIDDEN}]}}
    result = run(state, rc.GERMANS, action)
    assert result['executed'] and result['sa_execution']['executed'], result
    assert credit == [2]
    assert count_pieces(state, rc.CARNUTES, rc.AEDUI, rc.WARBAND) == 2
    assert validate_state(state) == []


def test_scout_between_battles_keeps_one_horse_choice_and_two_region_costs(monkeypatch):
    state, action = battle_position()
    activate_capability(state, 59, rc.EVENT_UNSHADED)
    requests, combat = [], []

    def agent(board, faction, request):
        if request['kind'] == 'horse_region':
            requests.append(request['legal_regions'])
            return {'region': rc.MANDUBII}

    state['decision_agent'] = agent
    resolve = ex.resolve_battle

    def record(board, region, attacker, defender, **kwargs):
        combat.append((region, count_pieces(board, region, rc.ROMANS, rc.AUXILIA),
                       board['resources'][rc.ROMANS], board['event_modifiers'].get(FLAGS[0])))
        return resolve(board, region, attacker, defender, **kwargs)

    monkeypatch.setattr(ex, 'resolve_battle', record)
    result = run(state, rc.ROMANS, action)
    assert result['executed'] and result['sa_execution']['executed'], result
    assert result['battles_resolved'] == [(rc.SEQUANI, rc.BELGAE), (rc.MANDUBII, rc.BELGAE)]
    assert requests == [[rc.SEQUANI, rc.MANDUBII]]
    assert combat == [(rc.SEQUANI, 1, 2, rc.MANDUBII), (rc.MANDUBII, 2, 0, rc.MANDUBII)]
    assert FLAGS[0] not in state['event_modifiers']
    assert validate_state(state) == []


def test_terminal_scout_menu_uses_survivors_revealed_by_the_first_battle():
    state, expected = battle_position()
    before = encode(state)
    output = StringIO()
    action = collect_player_action(state, rc.ROMANS, ACTION_COMMAND_SA, StringIO(
        'Command, Special Activity, then continue Command\n'
        f'Battle (between Regions)\n{rc.SEQUANI}\n{rc.MANDUBII}\n'
        f'{rc.BELGAE}\n{rc.BELGAE}\n{rc.SEQUANI}\nScout\n'
        f'Revealed Auxilia from {rc.SEQUANI} (1 unmoved)\n{rc.MANDUBII}\n1\n'
        'Finish Scout movement\nFinish Scout Reveal\nn\n'), output)
    assert encode(state) == before
    assert action['details']['sa_after_step'] == 1
    assert action['details']['scout_plan']['auxilia_moves'] == expected['details']['scout_plan']['auxilia_moves']
    result = run(state, rc.ROMANS, action)
    assert result['executed'] and result['sa_execution']['executed'], result


def test_battle_and_intervening_scout_keep_separate_diviciacus_agreements():
    state, action = battle_position(rc.SCENARIO_ARIOVISTUS)
    place_piece(state, rc.MANDUBII, rc.AEDUI, rc.LEADER, leader_name=rc.DIVICIACUS)
    for region in (rc.SEQUANI, rc.MANDUBII):
        place_piece(state, region, rc.AEDUI, rc.WARBAND)
    action['details']['diviciacus_regions'] = [rc.SEQUANI, rc.MANDUBII]
    action['details']['diviciacus_sa_regions'] = [rc.SEQUANI]
    action['details']['scout_plan']['auxilia_moves'][0]['physical_owners'] = {rc.AEDUI: 1}
    phases = []

    def agent(board, faction, request):
        if request.get('request_type') == 'diviciacus':
            assert faction == rc.AEDUI
            phases.append(request['context']['phase'])
            return {'agree': True}

    state['decision_agent'] = agent
    result = run(state, rc.ROMANS, action)
    assert result['executed'] and result['sa_execution']['executed'], result
    assert phases == ['command', 'special_ability']
    assert count_pieces(state, rc.SEQUANI, rc.AEDUI, rc.WARBAND) == 0
    assert count_pieces(state, rc.MANDUBII, rc.AEDUI, rc.WARBAND) == 2
    assert validate_state(state) == []


def test_battle_interruption_resumes_after_a_saved_mid_command_pause(tmp_path):
    from fs_bot.cli.display import HumanTurnDisplay
    from fs_bot.engine.game_engine import _action_transaction
    from fs_bot.state.serialize import decode, load_game, save_game
    from fs_bot.tools.seat_session import DecisionPending, SeatSession, board_copy

    state, action = battle_position()
    activate_capability(state, 59, rc.EVENT_UNSHADED)
    origin = encode(state)

    def setup(board, meta, log):
        session = SeatSession(board, meta, log, HumanTurnDisplay(StringIO()))

        def agent(current, faction, request):
            if request['kind'] == 'horse_region' or (
                    request['kind'] == 'voluntary_removal'
                    and request['window']['stage'] == 'special_ability'):
                return session.reactive(current, faction, request)

        agent.supports_action_windows = True
        board['decision_agent'] = agent
        return session

    def attempt(session):
        def driver(*args):
            pass

        driver.transaction_checkpoint = session.checkpoint
        driver.transaction_restore = session.restore
        with _action_transaction(session.state, driver):
            return run(session.state, rc.ROMANS, action)

    session = setup(state, {'seat': rc.ROMANS}, [])
    with pytest.raises(DecisionPending):
        attempt(session)
    first = session.data['pending']
    assert decode(first['request'])['kind'] == 'horse_region'
    session.import_inbox({'decision_id': first['id'], 'response': {'region': rc.MANDUBII}})
    with pytest.raises(DecisionPending):
        attempt(session)
    later = deepcopy(session.data['pending'])
    assert decode(later['request'])['window']['stage'] == 'special_ability'
    assert count_pieces_by_state(decode(later['board']), rc.SEQUANI, rc.ROMANS,
                                rc.AUXILIA, rc.REVEALED) == 1
    assert len(session.data['journal']) == 1 and encode(board_copy(state)) == origin

    path = tmp_path / 'between-battles.json'
    save_game(state, path, meta=session.meta, log=session.log)
    restored, meta, log = load_game(path, validate=True)
    resumed = setup(restored, meta, log)
    with pytest.raises(DecisionPending):
        attempt(resumed)
    assert resumed.data['pending'] == later
    resumed.import_inbox({'decision_id': later['id'], 'response': {'done': True}})
    result = attempt(resumed)
    resumed.finish()
    assert result['executed'] and result['sa_execution']['executed'], result
    assert [entry['reactive'] for entry in log] == ['horse_region', 'voluntary_removal']
    assert count_pieces(restored, rc.MANDUBII, rc.ROMANS, rc.AUXILIA) == 2
    assert restored['resources'][rc.ROMANS] == 0
    assert validate_state(restored) == []


@pytest.mark.parametrize('step', [0, 2, True, '1'])
def test_durable_turn_refuses_noninterior_or_noninteger_boundary(step):
    state, action = raid_position()
    action['details']['sa_after_step'] = step
    request = {'kind': 'turn', 'faction': rc.AEDUI, 'options': [ACTION_COMMAND_SA]}
    with pytest.raises(ValueError, match='between two Command steps'):
        validate_response(state, request, {'action': ACTION_COMMAND_SA, 'player_action': action})


def test_battle_modifier_and_limited_command_cannot_use_a_standalone_boundary():
    state, action = battle_position()
    modifier = dict(action, sa=rc.SA_BESIEGE)
    assert run(state, rc.ROMANS, modifier)['rejected']
    result = ex.execute_decision(state, rc.ROMANS,
                                 {'action': ACTION_LIMITED_COMMAND, 'player_action': action})
    assert result['rejected'] and 'Limited Command' in result['reason']


def test_baggage_trains_preserves_the_total_raid_cap_across_the_sa():
    state, action = raid_position()
    place_piece(state, rc.CARNUTES, rc.AEDUI, rc.WARBAND)
    plan = action['details']['raid_plan']
    plan.append({'region': rc.CARNUTES})
    assert 'at most 2' in run(state, rc.AEDUI, action)['reason']
    activate_capability(state, 8, rc.EVENT_SHADED)
    set_capability_owner(state, 8, rc.AEDUI)
    plan.append({'region': rc.CARNUTES})
    assert 'at most 3' in run(state, rc.AEDUI, action)['reason']
    plan.pop()
    result = run(state, rc.AEDUI, action)
    assert result['executed'] and result['raids'][0]['warbands_flipped'] == 3, result
