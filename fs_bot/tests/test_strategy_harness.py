"""Experimental outcomes must describe actual policy seats and audited games."""
import json
from pathlib import Path

import pytest

import fs_bot.rules_consts as rc
from fs_bot.engine.game_engine import ACTION_PASS
from fs_bot.tools import heuristic_selfplay as study
from fs_bot.agents import heuristic


def _success():
    return dict(completed=True, game_completed=True, winner=rc.ROMANS,
                cards=1, decisions=1, ending_agent_faction=rc.ROMANS,
                ending_scenario=rc.SCENARIO_GREAT_REVOLT,
                integrity_findings=[], diagnostics=[])


def _cli(monkeypatch, tmp_path, play):
    # Isolate the resume contract from unrelated parallel working-tree edits.
    monkeypatch.setattr(study, 'source_identity', lambda: {
        'commit': 'reviewed-source', 'dirty': False, 'source_sha256': 'digest'})
    monkeypatch.setattr(study, 'play_game', play)
    path = tmp_path / 'study.jsonl'
    args = ['--profiles', 'R-PACIFY', '--seeds', '1', '--out', str(path)]
    return path, args


def test_error_exit_and_resume_retry_preserve_failed_attempt(monkeypatch, tmp_path):
    attempts = []

    def play(*args, **kwargs):
        attempts.append(args)
        if len(attempts) == 1:
            raise RuntimeError('reproduced failure')
        return _success()

    path, args = _cli(monkeypatch, tmp_path, play)
    assert study.main(args) == 1
    assert study.main(args) == 0
    assert study.main(args) == 0
    assert len(attempts) == 2  # the failure retried, the success resumed
    records = [json.loads(line) for line in path.read_text().splitlines()]
    assert len(records) == 2
    assert records[0]['error'] == 'RuntimeError: reproduced failure'
    assert records[1]['completed'] is True


@pytest.mark.parametrize('changes', [
    {'completed': False}, {'game_completed': False}, {'winner': None},
    {'cards': 0}, {'decisions': 0}, {'integrity_findings': ['missing piece']},
    {'diagnostics': [{'severity': 'illegal'}]},
    {'cards': None}, {'decisions': None}, {'diagnostics': [None]},
    {'diagnostics': 'malformed'}, {'winner': rc.GERMANS},
])
def test_unsuccessful_outcomes_fail_and_remain_retryable(monkeypatch, tmp_path, changes):
    attempts = []

    def play(*args, **kwargs):
        attempts.append(args)
        return {**_success(), **changes}

    path, args = _cli(monkeypatch, tmp_path, play)
    assert study.main(args) == 1
    assert study.main(args) == 1
    assert len(attempts) == 2


@pytest.mark.parametrize('changed', ['source', 'edition'])
def test_changed_identity_cannot_mix_results(monkeypatch, tmp_path, changed):
    path, args = _cli(monkeypatch, tmp_path, lambda *a, **kw: _success())
    assert study.main(args) == 0
    before = path.read_bytes()
    if changed == 'source':
        monkeypatch.setattr(study, 'source_identity', lambda: {'source_sha256': 'new'})
    else:
        args += ['--card-edition', 'original']
    with pytest.raises(SystemExit) as error:
        study.main(args)
    assert error.value.code == 2
    assert path.read_bytes() == before


def test_output_making_checkout_dirty_does_not_prevent_resume(monkeypatch, tmp_path):
    path, args = _cli(monkeypatch, tmp_path, lambda *a, **kw: _success())
    assert study.main(args) == 0
    before = path.read_bytes()
    monkeypatch.setattr(study, 'source_identity', lambda: {
        'commit': 'reviewed-source', 'dirty': True, 'source_sha256': 'digest'})
    monkeypatch.setattr(study, 'play_game', lambda *a, **kw: pytest.fail('must resume'))
    assert study.main(args) == 0
    assert path.read_bytes() == before


@pytest.mark.parametrize('changes', [
    {'faction': rc.GERMANS}, {'label': 'not-a-profile'}, {'label': None}, {'seed': None},
    {'scenario': rc.SCENARIO_ARIOVISTUS}, {'card_edition': 'original'},
])
def test_record_identity_fields_cannot_silently_disagree(monkeypatch, tmp_path, changes):
    path, args = _cli(monkeypatch, tmp_path, lambda *a, **kw: _success())
    assert study.main(args) == 0
    record = json.loads(path.read_text())
    path.write_text(json.dumps({**record, **changes}) + '\n')
    before = path.read_bytes()
    with pytest.raises(SystemExit) as error:
        study.main(args)
    assert error.value.code == 2
    assert path.read_bytes() == before


def test_historical_or_damaged_logs_are_never_silently_reused(monkeypatch, tmp_path):
    path, args = _cli(monkeypatch, tmp_path, lambda *a, **kw: _success())
    original = b'{"label":"R-PACIFY","scenario":"The Great Revolt","seed":1}\n'
    path.write_bytes(original)
    with pytest.raises(SystemExit):
        study.main(args)
    assert path.read_bytes() == original
    path.unlink()
    assert study.main(args) == 0
    with path.open('a') as fh:
        fh.write('{"incomplete":')
    damaged = path.read_bytes()
    with pytest.raises(SystemExit):
        study.main(args)
    assert path.read_bytes() == damaged


@pytest.mark.parametrize('scenario', rc.ALL_SCENARIOS)
def test_default_profiles_only_include_actual_player_seats(scenario):
    labels = study._labels(scenario, None)
    factions = {study._faction(label) for label in labels} - {None}
    assert factions == set(study.get_sop_factions({'scenario': scenario}))
    if scenario in rc.ARIOVISTUS_SCENARIOS:
        assert 'G-GROW' in labels and 'A-BATTLE' not in labels
    else:
        assert 'A-BATTLE' in labels and 'G-GROW' not in labels


def test_ineligible_or_unknown_profiles_rejected_before_output(monkeypatch, tmp_path):
    play_game = study.play_game
    path, args = _cli(monkeypatch, tmp_path, lambda *a, **kw: pytest.fail('must not run'))
    for profile in ('A-BATTLE', 'RANDOM:Arverni', 'missing', 'RANDOM:typo'):
        with pytest.raises(SystemExit):
            study.main(['--scenario', rc.SCENARIO_ARIOVISTUS,
                        '--profiles', profile, '--out', str(path)])
        assert not path.exists()
    with pytest.raises(ValueError, match='not a playable seat'):
        play_game(rc.SCENARIO_ARIOVISTUS, 1, rc.ARVERNI, lambda *a: None)


def test_policy_seat_is_human_and_reactive_fallbacks_are_recorded(monkeypatch):
    observed = []

    def planner(state, faction, options, position):
        assert faction not in state['non_player_factions']
        observed.append(faction)
        return {'action': ACTION_PASS}

    result = study.play_game(rc.SCENARIO_PAX_GALLICA, 1, rc.ROMANS, planner,
                             card_edition='original')
    assert result['completed'], result
    assert observed and set(observed) == {rc.ROMANS}
    assert result['decisions'] == len(observed)
    assert result['reactive_decisions']
    assert {row['response'] for row in result['reactive_decisions']} <= {'policy', 'default'}


@pytest.mark.parametrize('label,target', [('G-GROW', 'A-DEVASTATE'), ('G-BATTLE', 'A-BATTLE')])
def test_gallic_war_explicit_policy_and_reactive_handover(monkeypatch, label, target):
    selected = []
    monkeypatch.setattr(study, 'plan_turn', lambda s, f, p, o, pos:
                        selected.append((f, p)) or {'action': ACTION_PASS})
    faction, planner = study._make(label, 1)
    assert faction == rc.GERMANS
    planner({}, rc.GERMANS, [], '')
    planner({'interlude_completed': True}, rc.ARVERNI, [], '')
    assert selected[0] == (rc.GERMANS, heuristic.PROFILES[label])
    assert selected[1] == (rc.ARVERNI, heuristic.PROFILES[target])
    assert study._active_seat({'interlude_completed': True}, faction) == rc.ARVERNI
    assert study._active_seat({'interlude_completed': True}, rc.ROMANS) == rc.ROMANS


def test_real_gallic_war_policy_handoff_resumes_legal_interlude_checkpoint(monkeypatch):
    # The Recruit fixes make former full-game seeds 3 and 7 end lawfully
    # before Interlude. A bounded 0-10 fixture search found no replacement.
    # Resume the unchanged historical save at its pending third Winter;
    # real Victory, Interlude, and subsequent policy play still execute.
    from fs_bot.state.serialize import load_game
    checkpoint = (Path(__file__).parent / 'fixtures' / 'compatibility_8ef88e2'
                  / 'pre-interlude.json')
    state, meta, _ = load_game(checkpoint, validate=True)
    assert state['current_card'] == rc.WINTER_CARD and state['winter_count'] == 2
    assert not state['interlude_completed']
    assert study._active_seat(state, rc.GERMANS) == rc.GERMANS

    def resume_setup(scenario, *, seed, card_edition):
        assert scenario == state['scenario'] == rc.SCENARIO_GALLIC_WAR
        assert seed == meta['seed'] and card_edition == state['card_edition']
        return state

    def resume_display(board):
        assert board is state and board['current_card'] == rc.WINTER_CARD
        return board['current_card']  # The saved game already drew this card.

    monkeypatch.setattr(study, 'setup_scenario', resume_setup)
    monkeypatch.setattr(study, 'start_game', resume_display)
    faction, planner = study._make('G-GROW', meta['seed'])
    result = study.play_game(rc.SCENARIO_GALLIC_WAR, meta['seed'], faction, planner,
                             card_edition=state['card_edition'])
    assert result['completed'], result
    assert result['interlude_completed']
    assert result['ending_agent_faction'] == rc.ARVERNI
    # The saved Winter has no ordinary German turn, but its policy receives
    # a real Winter reaction before the same seat becomes Arverni.
    assert any(row['faction'] == rc.GERMANS and row['count'] > 0
               for row in result['reactive_decisions'])
    assert result['decisions_by_faction'][rc.ARVERNI] > 0


@pytest.mark.parametrize('seed', [3, 7])
def test_real_gallic_war_policy_keeps_the_seat_matching_its_actual_ending(seed):
    # The Gallic War Interlude applies only if the game has not ended by
    # its third Victory Phase; a completed first-half game is legitimate.
    faction, planner = study._make('G-GROW', seed)
    result = study.play_game(rc.SCENARIO_GALLIC_WAR, seed, faction, planner,
                             card_edition='second-edition')
    assert result['completed'] and result['game_completed'], result
    assert result['decisions_by_faction'][rc.GERMANS] > 0
    # Rules corrections can change whether a particular seed reaches the
    # Interlude. Audit the actual seat transition, not a frozen outcome.
    if result['interlude_completed']:
        assert result['ending_scenario'] == rc.SCENARIO_PAX_GALLICA
        assert result['ending_agent_faction'] == rc.ARVERNI
        assert result['decisions_by_faction'].get(rc.ARVERNI, 0) > 0
    else:
        assert result['winters'] <= 3
        assert result['ending_scenario'] == rc.SCENARIO_GALLIC_WAR
        assert result['ending_agent_faction'] == rc.GERMANS
        assert result['decisions_by_faction'].get(rc.ARVERNI, 0) == 0
        assert result['ranking'][0][1] > 0
    assert result['ranking'][0][0] == result['winner']


@pytest.mark.parametrize('info', [
    {'executed': True, 'errors': [{'error': 'partial illegal target'}]},
    {'executed': True, 'sa_execution': {'executed': False, 'reason': 'no effect'}},
    {'executed': True, 'free_actions': [{'executed': True, 'error': 'nested failure'}]},
])
def test_partial_success_does_not_make_a_clean_policy_plan(monkeypatch, info):
    monkeypatch.setattr(heuristic.moves, 'validate_player_action', lambda *a: (True, info))
    assert not heuristic._validated_candidate({'scenario': rc.SCENARIO_ARIOVISTUS},
                                              rc.GERMANS, {'command': rc.CMD_RALLY})


def test_decline_is_not_an_illegal_policy_plan(monkeypatch):
    info = {'executed': True, 'sa_skipped': 'command produced no legal effect'}
    monkeypatch.setattr(heuristic.moves, 'validate_player_action', lambda *a: (True, info))
    assert heuristic._validated_candidate({'scenario': rc.SCENARIO_ARIOVISTUS},
                                          rc.GERMANS, {'command': rc.CMD_RALLY})


def test_selected_edition_and_provenance_reach_every_record(monkeypatch, tmp_path):
    editions = []

    def play(*args, **kwargs):
        editions.append(kwargs['card_edition'])
        return _success()

    path, args = _cli(monkeypatch, tmp_path, play)
    assert study.main(args + ['--card-edition', 'second-edition']) == 0
    record = json.loads(path.read_text())
    manifest = json.loads(path.with_name(path.name + '.manifest.json').read_text())
    assert editions == ['second-edition']
    assert record['identity'] == manifest
    assert manifest['card_edition'] == 'second-edition'
    assert manifest['seat_semantics'] == 'human-policy-seat'
    assert manifest['policy_version'] == study.POLICY_VERSION
