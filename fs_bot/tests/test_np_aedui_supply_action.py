"""PR-07: one automated Aedui Supply answer for a complete Roman action.

The owner adopted this provisional interpretation of §§1.5.2/8.6.6 and the
playbook's p.11 combined Command+SA agreement example; it is not official errata.
"""
from copy import deepcopy

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces, count_pieces_by_state, move_piece, place_piece, remove_piece
from fs_bot.commands.rally import has_supply_line, supply_agreement_scope, supply_query_scope
from fs_bot.engine.execute import execute_decision
from fs_bot.engine.game_engine import ACTION_COMMAND
from fs_bot.engine.moves import validate_player_action
from fs_bot.engine.recruit_planning import (
    ANSWERS, REQUESTS, confirm_supply_plan, forecast_answer, forecast_supply,
)
from fs_bot.engine.victory import calculate_victory_score
from fs_bot.state.serialize import encode
from fs_bot.state.setup import setup_scenario
from fs_bot.state.state_schema import check_structural_integrity


def _state(seed=1, *, diviciacus_option=False):
    state = setup_scenario(rc.SCENARIO_GREAT_REVOLT, seed=1,
                           diviciacus_option=diviciacus_option)
    state['non_player_factions'] = {rc.AEDUI, rc.BELGAE, rc.ARVERNI}
    state['resources'][rc.ROMANS] = 10
    for origin in state['spaces']:
        for visibility in (rc.HIDDEN, rc.REVEALED, rc.SCOUTED):
            n = count_pieces_by_state(state, origin, rc.AEDUI, rc.WARBAND, visibility)
            if n:
                remove_piece(state, origin, rc.AEDUI, rc.WARBAND, n, piece_state=visibility)
    for origin in (rc.SEQUANI, rc.MANDUBII, rc.CARNUTES):
        for faction in rc.FACTIONS:
            for piece in (rc.LEADER, rc.LEGION):
                n = count_pieces(state, origin, faction, piece)
                if n:
                    move_piece(state, origin, rc.PROVINCIA, faction, piece, n)
            for piece in (rc.AUXILIA, rc.WARBAND):
                for visibility in (rc.HIDDEN, rc.REVEALED, rc.SCOUTED):
                    n = count_pieces_by_state(state, origin, faction, piece, visibility)
                    if n:
                        move_piece(state, origin, rc.PROVINCIA, faction, piece, n, piece_state=visibility)
    for region in (rc.SEQUANI, rc.MANDUBII):
        place_piece(state, region, rc.AEDUI, rc.WARBAND, 6)
        place_piece(state, region, rc.ROMANS, rc.AUXILIA)
        if not count_pieces(state, region, rc.ROMANS, rc.FORT):
            place_piece(state, region, rc.ROMANS, rc.FORT)
        assert state['spaces'][region]['control'] == rc.AEDUI_CONTROL
    move_piece(state, rc.PROVINCIA, rc.SEQUANI, rc.ROMANS, rc.LEADER)
    assert calculate_victory_score(state, rc.ROMANS) == 12
    assert check_structural_integrity(state) == []
    state['rng'].seed(seed)
    return state


def _recruit(regions=(rc.SEQUANI, rc.MANDUBII)):
    return {'command': rc.CMD_RECRUIT, 'regions': [], 'sa': 'No SA',
            'details': {'recruit_plan': [
                {'region': region, 'action': 'place_auxilia', 'count': 1}
                for region in regions]}}


@pytest.mark.parametrize('seed,agrees', [(1, True), (5, False)])
def test_one_real_die_covers_multiple_regions_queries_and_same_action(seed, agrees):
    state = _state(seed)
    rng = deepcopy(state['rng'])
    assert (rng.randint(1, 6) <= 4) is agrees
    with supply_agreement_scope(state):
        for region in (rc.SEQUANI, rc.MANDUBII, rc.SEQUANI):
            with supply_query_scope(state):
                assert has_supply_line(state, region) is agrees
            assert state['rng'].getstate() == rng.getstate()
    assert '_supply_line_agreements' not in state
    assert '_supply_line_query' not in state
    # An independent action gets the next genuine roll.
    next_agrees = rng.randint(1, 6) <= 4
    with supply_agreement_scope(state):
        assert has_supply_line(state, rc.MANDUBII) is next_agrees
    assert state['rng'].getstate() == rng.getstate()


@pytest.mark.parametrize('seed,agrees', [(1, True), (5, False)])
def test_actual_human_recruit_all_regions_share_one_answer(seed, agrees):
    state = _state(seed)
    rng = deepcopy(state['rng'])
    rng.randint(1, 6)
    result = execute_decision(state, rc.ROMANS, {'player_action': _recruit()})
    assert result['executed'] and not result['errors'], result
    assert state['resources'][rc.ROMANS] == (10 if agrees else 6)
    assert state['rng'].getstate() == rng.getstate()
    assert all(count_pieces(state, region, rc.ROMANS, rc.AUXILIA) == 2
               for region in (rc.SEQUANI, rc.MANDUBII))
    assert '_supply_line_agreements' not in state
    assert check_structural_integrity(state) == []


@pytest.mark.parametrize('timing', ['before', 'during', 'after'])
@pytest.mark.parametrize('seed,agrees', [(1, True), (5, False)])
def test_recruit_and_build_share_answer_in_every_legal_order(timing, seed, agrees):
    state = _state(seed)
    place_piece(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA)
    place_piece(state, rc.CARNUTES, rc.AEDUI, rc.WARBAND, 6)
    # Caesar needs to cover Carnutes while both Recruit Regions remain legal.
    move_piece(state, rc.SEQUANI, rc.MANDUBII, rc.ROMANS, rc.LEADER)
    action = _recruit()
    action.update(sa=rc.SA_BUILD, sa_regions=[rc.CARNUTES], sa_timing=timing)
    action['details']['build_plan'] = {'forts': [rc.CARNUTES], 'allies': [], 'subdue': []}
    if timing == 'during':
        action['details'].pop('recruit_plan')
        action['details']['command_parts'] = [_recruit((rc.SEQUANI,)), _recruit((rc.MANDUBII,))]
    rng = deepcopy(state['rng'])
    rng.randint(1, 6)
    result = execute_decision(state, rc.ROMANS, {'player_action': action})
    assert result['executed'] and not result.get('errors'), result
    assert result['sa_execution']['executed'] is agrees
    assert state['resources'][rc.ROMANS] == (8 if agrees else 6)
    assert state['rng'].getstate() == rng.getstate()
    assert '_supply_line_agreements' not in state
    assert check_structural_integrity(state) == []


def test_preview_does_not_consume_live_or_detached_rng_or_create_a_known_roll():
    state = _state(5)
    before = encode(state)
    assert validate_player_action(state, rc.ROMANS, _recruit())[0]
    assert encode(state) == before
    sim = deepcopy(state)
    sim['_diviciacus_preview'] = True
    with supply_agreement_scope(sim):
        assert has_supply_line(sim, rc.SEQUANI)
        assert has_supply_line(sim, rc.MANDUBII)
        assert (rc.ROMANS, rc.AEDUI, None) not in sim['_supply_line_agreements']
    assert sim['rng'].getstate() == state['rng'].getstate()


def test_human_aedui_region_permissions_are_still_independent():
    state = _state()
    state['non_player_factions'].discard(rc.AEDUI)
    calls = []

    def player(board, faction, request):
        region = request['context']['region']
        calls.append((faction, region))
        return region == rc.SEQUANI

    state['decision_agent'] = player
    rng = state['rng'].getstate()
    with supply_agreement_scope(state):
        assert has_supply_line(state, rc.SEQUANI)
        assert not has_supply_line(state, rc.MANDUBII)
    assert calls == [(rc.AEDUI, rc.SEQUANI), (rc.AEDUI, rc.MANDUBII)]
    assert state['rng'].getstate() == rng


@pytest.mark.parametrize('seed,agrees', [(1, True), (5, False)])
def test_planning_reuses_action_answer_for_newly_encountered_region(seed, agrees):
    state = _state(seed)
    answers = {}
    action = _recruit()
    action['details'][REQUESTS] = [
        {'requesting_faction': rc.ROMANS, 'faction': rc.AEDUI, 'region': region}
        for region in (rc.SEQUANI, rc.MANDUBII)]
    rng = deepcopy(state['rng'])
    rng.randint(1, 6)
    assert confirm_supply_plan(state, action, answers)
    assert state['rng'].getstate() == rng.getstate()
    state[ANSWERS] = answers
    assert forecast_answer(state, rc.ROMANS, rc.AEDUI, rc.CARNUTES) is agrees
    # A second pass of the same concrete planner cannot buy another die.
    confirm_supply_plan(state, action, answers)
    assert state['rng'].getstate() == rng.getstate()


def test_unrolled_high_score_refusal_can_change_but_rolled_refusal_is_fixed(monkeypatch):
    state = _state(5)
    score = [13]
    monkeypatch.setattr('fs_bot.bots.bot_common.calculate_victory_score', lambda *_: score[0])
    rng = deepcopy(state['rng'])
    with supply_agreement_scope(state):
        assert not has_supply_line(state, rc.SEQUANI)
        assert state['rng'].getstate() == rng.getstate()
        assert (rc.ROMANS, rc.AEDUI, None) not in state['_supply_line_agreements']
        score[0] = 12
        assert not has_supply_line(state, rc.MANDUBII)
        assert rng.randint(1, 6) == 5
        assert state['rng'].getstate() == rng.getstate()
        score[0] = 9
        assert not has_supply_line(state, rc.SEQUANI)
        assert state['rng'].getstate() == rng.getstate()


@pytest.mark.parametrize('cache', ['_recruit_supply_answers', '_supply_line_agreements'])
def test_old_region_promise_survives_refusal_for_a_new_region(cache):
    # §1.5.2: accepted promises bind. Older saves may have a Region-keyed
    # answer; PR-07 must not revoke it or silently extend it to every Region.
    state = _state(5)
    state[cache] = {(rc.ROMANS, rc.AEDUI, rc.SEQUANI): True}
    expected_rng = deepcopy(state['rng'])
    assert expected_rng.randint(1, 6) == 5
    result = execute_decision(state, rc.ROMANS, {
        'action': ACTION_COMMAND, 'player_action': _recruit()})
    assert result['executed'] and not result.get('errors'), result
    assert state['resources'][rc.ROMANS] == 8  # Only unpromised Mandubii costs2.
    assert count_pieces(state, rc.SEQUANI, rc.ROMANS, rc.AUXILIA) == 2
    assert count_pieces(state, rc.MANDUBII, rc.ROMANS, rc.AUXILIA) == 2
    assert state['rng'].getstate() == expected_rng.getstate()


def test_known_positive_forecast_still_records_its_execution_dependency():
    state = _state(1)
    state[ANSWERS] = {(rc.ROMANS, rc.AEDUI, rc.SEQUANI): True}
    before = encode(state)
    with forecast_supply(state) as requests:
        assert has_supply_line(state, rc.SEQUANI)
    assert requests == [{'requesting_faction': rc.ROMANS,
                         'faction': rc.AEDUI, 'region': rc.SEQUANI}]
    assert encode(state) == before

