"""Failure-injection tests for the outcome study itself, not game simulations."""
from collections import Counter

import pytest

import fs_bot.rules_consts as rc
from fs_bot.tools import run_batch as runner
from fs_bot.tools.error_census import census_result


@pytest.fixture
def synthetic_game(monkeypatch):
    monkeypatch.setattr(runner, 'setup_scenario', lambda *a, **k:
                        {'scenario': rc.SCENARIO_PAX_GALLICA, 'resources': {}, 'current_card': 1})
    monkeypatch.setattr(runner, 'get_sop_factions', lambda state: [rc.ROMANS, rc.ARVERNI, rc.AEDUI, rc.BELGAE])
    monkeypatch.setattr(runner, 'make_decision_func', lambda *a, **k: None)
    monkeypatch.setattr(runner, 'start_game', lambda state: None)
    monkeypatch.setattr(runner, 'play_card', lambda *a, **k:
                        {'game_over': True, 'winner': rc.ROMANS, 'final_ranking': [(rc.ROMANS, 1)]})
    monkeypatch.setattr(runner, 'validate_state', lambda state: [])
    monkeypatch.setattr(runner, 'check_structural_integrity', lambda state: [])
    monkeypatch.setattr(runner, 'determine_final_ranking', lambda state:
                        [(rc.ROMANS, 1), (rc.ARVERNI, 0), (rc.AEDUI, 0), (rc.BELGAE, 0)])
    monkeypatch.setattr(runner, 'check_victory', lambda state, faction: faction == rc.ROMANS)
    monkeypatch.setattr(runner, 'encode', lambda state: {})


def fail(*args, **kwargs):
    raise RuntimeError('injected failure')


@pytest.mark.parametrize('operation,stage', [
    ('setup_scenario', 'setup'), ('make_decision_func', 'bot-initialization'),
    ('play_card', 'gameplay'), ('determine_final_ranking', 'outcome-audit'),
    ('census_result', 'diagnostics'), ('encode', 'serialization'),
])
def test_stage_failure_is_a_record_not_an_escaped_exception(synthetic_game, monkeypatch, operation, stage):
    monkeypatch.setattr(runner, operation, fail)
    record = runner.play_one((rc.SCENARIO_PAX_GALLICA, 1))
    assert not record['completed']
    assert record['error'] == 'injected failure'
    assert record['stage'] == stage
    summary = runner.summarize([record])[rc.SCENARIO_PAX_GALLICA]
    assert summary['crashes'] == 1 and summary['completed'] == 0
    assert summary['wins'] == {}


def test_successful_engine_can_have_failed_audit_without_becoming_a_win(synthetic_game, monkeypatch):
    monkeypatch.setattr(runner, 'determine_final_ranking', fail)
    record = runner.play_one((rc.SCENARIO_PAX_GALLICA, 1))
    assert record['game_completed']
    assert not record['completed'] and not record['audit_completed']


def test_baseline_synthetic_game_is_counted(synthetic_game):
    record = runner.play_one((rc.SCENARIO_PAX_GALLICA, 1))
    assert record['completed']
    assert runner.summarize([record])[rc.SCENARIO_PAX_GALLICA]['wins'] == {rc.ROMANS: 1}


def test_worker_failure_does_not_abort_collection():
    class FailedFuture:
        result = fail
    record = runner.collect_future(FailedFuture(), (rc.SCENARIO_PAX_GALLICA, 8))
    assert record['seed'] == 8 and record['stage'] == 'worker'
    assert not record['completed']


def test_old_contradictory_completed_and_error_record_not_counted(synthetic_game):
    record = runner.play_one((rc.SCENARIO_PAX_GALLICA, 1))
    record['error'] = 'failure after completed=True'
    summary = runner.summarize([record])[rc.SCENARIO_PAX_GALLICA]
    assert summary['completed'] == 0 and summary['crashes'] == 1
    assert summary['wins'] == {}


def test_diagnostics_keep_distinct_causes_and_every_raw_occurrence():
    causes = [dict(region=rc.CARNUTES, error="requires 'Hidden' Warbands"),
              dict(region=rc.CARNUTES, error='outside leader range')]
    ex = {'executed': True, 'sa_execution': {'sa': rc.SA_SUBORN,
          'executed': False, 'errors': causes + causes[:1]}}
    result = {'card_results': [{'card': 1, 'turn_result': {'actions_taken': {
        rc.AEDUI: {'bot_action': {'command': rc.CMD_RALLY, 'sa': rc.SA_TRADE},
                   'execution': ex}}}}]}
    counts, examples, events = Counter(), {}, []
    census_result(result, counts, examples, 'test', 1, events)
    errors = [e for e in events if e['kind'] == 'sa-error']
    assert len(errors) == 3
    assert errors[0]['raw'] == causes[0]
    assert errors[0]['message'] == "requires 'Hidden' Warbands"
    assert all(e['command'].endswith(rc.SA_SUBORN) for e in errors)
    assert len([k for k in counts if k[2] == 'sa-error']) == 2
