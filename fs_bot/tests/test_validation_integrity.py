"""Validation cannot certify incomplete games or hide replay-state changes."""
import copy
import json

import pytest

from fs_bot import rules_consts as rc
from fs_bot.state.setup import setup_scenario
from fs_bot.tools import error_census, player_fuzz


def terminal_result(winner=rc.ROMANS):
    return {'card_results': [{'card': rc.WINTER_CARD, 'game_over': True,
                             'winner': winner}],
            'game_over': True, 'total_cards_played': 1, 'winter_count': 1}


@pytest.mark.parametrize('change', [
    lambda s: s['rng'].random(),
    lambda s: s['available'][rc.ROMANS].update({rc.AUXILIA: 0}),
    lambda s: s['capabilities'].update({38: rc.EVENT_UNSHADED}),
    lambda s: s['eligibility'].update({rc.ROMANS: rc.INELIGIBLE}),
    lambda s: s['senate'].update(firm=not s['senate']['firm']),
    lambda s: s['deck'].reverse(),
    lambda s: s.update(card_edition='second-edition'),
    lambda s: s.update(scenario_phase='second_half'),
])
def test_replay_digest_includes_complete_persistent_state(change):
    state = setup_scenario(rc.SCENARIO_GREAT_REVOLT, seed=4)
    changed = copy.deepcopy(state)
    change(changed)
    assert player_fuzz._digest(changed, terminal_result()) != player_fuzz._digest(state, terminal_result())


def test_replay_digest_includes_result_trajectory_and_preserves_key_types():
    state = setup_scenario(rc.SCENARIO_GREAT_REVOLT, seed=4)
    original = terminal_result()
    altered = copy.deepcopy(original)
    altered['card_results'][0]['turn_result'] = {'actions_taken': {rc.ROMANS: {'action': 'pass'}}}
    assert player_fuzz._digest(state, original) != player_fuzz._digest(state, altered)
    state['capabilities'] = {38: rc.EVENT_UNSHADED}
    first = player_fuzz._digest(state, original)
    state['capabilities'] = {'38': rc.EVENT_UNSHADED}
    assert player_fuzz._digest(state, original) != first


def test_replay_digest_ignores_dictionary_insertion_order_and_live_agent():
    state = setup_scenario(rc.SCENARIO_GREAT_REVOLT, seed=4)
    state['capabilities'] = {38: rc.EVENT_UNSHADED, 'A22': rc.EVENT_SHADED}
    changed = copy.deepcopy(state)
    changed['capabilities'] = dict(reversed(list(state['capabilities'].items())))
    changed['decision_agent'] = lambda *args: None
    assert player_fuzz._digest(state, terminal_result()) == player_fuzz._digest(changed, terminal_result())


BAD_RESULTS = [
    None, [], {}, {'card_results': []},
    {'card_results': [], 'game_over': True, 'total_cards_played': 0},
    {**terminal_result(), 'game_over': False},
    {**terminal_result(), 'total_cards_played': 2},
    {**terminal_result(), 'total_cards_played': True},
    {'card_results': [{'game_over': False}], 'game_over': True, 'total_cards_played': 1},
    terminal_result(None), terminal_result(rc.GERMANS),
]


@pytest.mark.parametrize('result', BAD_RESULTS)
def test_fuzz_records_incomplete_or_ineligible_games(monkeypatch, result):
    monkeypatch.setattr(player_fuzz, 'run_game', lambda *args, **kwargs: copy.deepcopy(result))
    record = player_fuzz.play_game(rc.SCENARIO_PAX_GALLICA, 1)
    assert not record['game_completed']
    assert any(kind == 'incomplete-game' for kind, _, _ in record['findings'])


@pytest.mark.parametrize('result', BAD_RESULTS)
@pytest.mark.parametrize('strict', [False, True])
def test_census_fails_incomplete_games_even_without_strict(monkeypatch, tmp_path, result, strict):
    monkeypatch.setattr(error_census, 'play_game', lambda *args, **kwargs: copy.deepcopy(result))
    path = tmp_path / 'evidence.json'
    args = ['--scenario', rc.SCENARIO_PAX_GALLICA, '--seeds', '1', '--out', str(path)]
    assert error_census.main(args + (['--strict'] if strict else [])) != 0
    evidence = json.loads(path.read_text())
    assert evidence['games'] == 1 and evidence['completed'] == 0
    assert evidence['failed_games'] == 1 and evidence['failures']


def test_census_retains_failure_and_continues_to_other_seeds(monkeypatch, tmp_path):
    def play(scenario, seed, **kwargs):
        if seed == 1:
            raise RuntimeError('reproduced crash')
        return terminal_result()
    monkeypatch.setattr(error_census, 'play_game', play)
    path = tmp_path / 'evidence.json'
    assert error_census.main(['--scenario', rc.SCENARIO_PAX_GALLICA, '--seeds', '1-2',
                             '--out', str(path)]) == 1
    evidence = json.loads(path.read_text())
    assert evidence['games'] == 2 and evidence['completed'] == 1
    assert evidence['failures'][0]['seed'] == 1
    assert 'reproduced crash' in evidence['failures'][0]['error']


def test_completion_uses_final_scenario_after_interlude():
    assert error_census.game_completion_error(terminal_result(rc.GERMANS), rc.SCENARIO_GALLIC_WAR) is None
    assert error_census.game_completion_error(terminal_result(rc.ARVERNI), rc.SCENARIO_PAX_GALLICA) is None
    assert error_census.game_completion_error(terminal_result(rc.GERMANS), rc.SCENARIO_PAX_GALLICA)


def test_second_replay_findings_are_not_hidden_by_matching_digest(monkeypatch):
    calls = []
    def play(scenario, seed, **settings):
        calls.append(seed)
        return dict(scenario=scenario, seed=seed, card_edition=settings['card_edition'],
                    seats=[rc.ROMANS], human_turns=1, event_turns=0, events_ok=0,
                    partial=0, digest='same-final-state',
                    findings=[] if len(calls) == 1 else [('dirty-event', 5, 'bad rollback')])
    monkeypatch.setattr(player_fuzz, 'play_game', play)
    assert player_fuzz.main(['--scenario', rc.SCENARIO_PAX_GALLICA, '--seeds', '1']) == 1


def test_census_retains_actual_ending_scenario(monkeypatch):
    def game(state, **kwargs):
        state['scenario'] = rc.SCENARIO_PAX_GALLICA
        return terminal_result(rc.ARVERNI)
    monkeypatch.setattr(error_census, 'run_game', game)
    result = error_census.play_game(rc.SCENARIO_GALLIC_WAR, 1)
    assert result['ending_scenario'] == rc.SCENARIO_PAX_GALLICA
    assert error_census.game_completion_error(result, result['ending_scenario']) is None
