"""Synthetic Recruit choices tolerate a possible NPC Aedui Supply refusal."""
import gzip
import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest

from fs_bot import rules_consts as rc
from fs_bot.agents.heuristic import _validated_candidate, plan_turn, PROFILES
from fs_bot.board.pieces import place_piece, remove_piece
from fs_bot.engine.execute import execute_decision
from fs_bot.engine.game_engine import ACTION_PASS, ACTION_COMMAND, ACTION_COMMAND_SA
from fs_bot.engine.moves import validate_player_action
from fs_bot.engine.recruit_planning import ANSWERS
from fs_bot.engine.victory import calculate_victory_score
from fs_bot.state.serialize import decode, encode
from fs_bot.state.state_schema import check_structural_integrity


def captured():
    path = Path(__file__).parent / 'fixtures/recruit_supply_before/great-revolt-r-hunt-1.json.gz'
    with gzip.open(path, 'rt') as stream:
        fixture = json.load(stream)
    assert hashlib.sha256(json.dumps(fixture['state'], sort_keys=True).encode()).hexdigest() == (
        fixture['provenance']['state_sha256'])
    return decode(fixture['state']), fixture['decision']


class NoLiveInput:
    def __call__(self, *_):
        pytest.fail('A synthetic preview consulted live input')

    def __deepcopy__(self, _):
        pytest.fail('A synthetic preview copied live input')


def test_captured_zero_resource_recruit_stays_possible_for_human_but_not_risk_averse_policy():
    state, decision = captured()
    action = decision['player_action']
    assert calculate_victory_score(state, rc.ROMANS) == 10
    assert state['resources'][rc.ROMANS] == 0
    state['decision_agent'] = NoLiveInput()
    before = encode({k: v for k, v in state.items() if k != 'decision_agent'})
    # The human can request the possible agreement. The experimental policy
    # cannot assume that possible permission is guaranteed at execution.
    assert validate_player_action(state, rc.ROMANS, action)[0]
    assert not _validated_candidate(state, rc.ROMANS, action)
    selected = plan_turn(state, rc.ROMANS, PROFILES['R-HUNT'],
                         [ACTION_COMMAND_SA, ACTION_COMMAND, ACTION_PASS], '2nd_eligible')
    assert selected != decision
    assert encode({k: v for k, v in state.items() if k != 'decision_agent'}) == before
    if selected['action'] != ACTION_PASS:
        result = execute_decision(state, rc.ROMANS, selected)
        assert result['executed'] and not result.get('errors')


def test_payable_recruit_survives_actual_refusal_without_mutating_preview_rng():
    state, decision = captured()
    state['resources'][rc.ROMANS] = 2
    before = encode(state)
    assert _validated_candidate(state, rc.ROMANS, decision['player_action'])
    assert encode(state) == before
    # The preserved concrete state next rolls5: a genuine refusal, not a
    # test-forced answer or inspection performed by the heuristic policy.
    result = execute_decision(state, rc.ROMANS, decision)
    assert result['executed'] and not result.get('errors')
    assert state['resources'][rc.ROMANS] == 0
    assert check_structural_integrity(state) == []


@pytest.mark.parametrize('score', [9, 10, 11, 12, 13])
def test_actual_score_tiers_keep_guaranteed_and_uncertain_permission_distinct(score):
    state, decision = captured()
    if score == 9:
        place_piece(state, rc.AEDUI_REGION, rc.AEDUI, rc.ALLY)
        state['tribes'][rc.TRIBE_AEDUI]['allied_faction'] = rc.AEDUI
    else:
        for region, tribe in [(rc.ARVERNI_REGION, rc.TRIBE_CADURCI),
                              (rc.ARVERNI_REGION, rc.TRIBE_VOLCAE),
                              (rc.PICTONES, rc.TRIBE_PICTONES)][:score - 10]:
            remove_piece(state, region, rc.ARVERNI, rc.ALLY)
            state['tribes'][tribe]['allied_faction'] = None
    assert calculate_victory_score(state, rc.ROMANS) == score
    assert check_structural_integrity(state) == []
    before = encode(state)
    assert _validated_candidate(state, rc.ROMANS, decision['player_action']) is (score == 9)
    assert encode(state) == before


@pytest.mark.parametrize('context', [ANSWERS, '_supply_line_agreements'])
def test_previously_confirmed_permission_is_retained(context):
    state, decision = captured()
    state[context] = {(rc.ROMANS, rc.AEDUI, rc.AEDUI_REGION): True}
    before = encode(state)
    assert _validated_candidate(state, rc.ROMANS, decision['player_action'])
    assert encode(state) == before
    result = execute_decision(state, rc.ROMANS, decision)
    assert result['executed'] and not result.get('errors')
    assert state['rng'].getstate() == decode(before)['rng'].getstate()


def test_future_die_does_not_change_the_conservative_choice():
    state, decision = captured()
    for seed in (1, 5):
        trial = deepcopy(state)
        trial['rng'].seed(seed)
        before = encode(trial)
        assert not _validated_candidate(trial, rc.ROMANS, decision['player_action'])
        assert encode(trial) == before
