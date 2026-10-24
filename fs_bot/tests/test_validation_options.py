"""Study settings must reach gameplay and remain attached to the evidence."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json

import pytest

import fs_bot.rules_consts as rc
from fs_bot.cards.edition import CARD_EDITIONS
from fs_bot.tools import error_census, player_fuzz, run_batch, sync_check
from fs_bot.tools.validation_metadata import parse_seed_range


@pytest.mark.parametrize('text,expected', [('0', [0]), ('201', [201]),
                                          ('201-203', [201, 202, 203])])
def test_seed_ranges_are_explicit_and_inclusive(text, expected):
    assert parse_seed_range(text) == expected


@pytest.mark.parametrize('text', ['3-1', '-1', '1-', '1-2-3', '', 'a', '1.5'])
def test_malformed_ranges_cannot_certify_zero_games(text):
    with pytest.raises(argparse.ArgumentTypeError):
        parse_seed_range(text)


@pytest.mark.parametrize('edition', CARD_EDITIONS)
@pytest.mark.parametrize('module', [error_census, player_fuzz])
def test_selected_edition_reaches_engine_state(monkeypatch, edition, module):
    observed = []

    def inspect_state(state, **kwargs):
        observed.append(state['card_edition'])
        return {'card_results': [{'game_over': True, 'winner': rc.ROMANS}],
                'game_over': True, 'total_cards_played': 1}

    monkeypatch.setattr(module, 'run_game', inspect_state)
    result = module.play_game(rc.SCENARIO_PAX_GALLICA, 201, card_edition=edition)
    assert observed == [edition]
    if module is player_fuzz:
        assert result['card_edition'] == edition


def test_census_settings_and_exact_seed_range_are_recorded(monkeypatch, tmp_path):
    observed = []

    def record_game(scenario, seed, *, card_edition):
        observed.append((scenario, seed, card_edition))
        return {'card_results': [{'game_over': True, 'winner': rc.ROMANS}],
                'game_over': True, 'total_cards_played': 1}

    monkeypatch.setattr(error_census, 'play_game', record_game)
    output = tmp_path / 'census.json'
    assert error_census.main(['--scenario', rc.SCENARIO_ARIOVISTUS,
                             '--seeds', '201-202', '--card-edition', 'original',
                             '--strict', '--out', str(output)]) == 0
    evidence = json.loads(output.read_text())
    assert observed == [(rc.SCENARIO_ARIOVISTUS, seed, 'original')
                        for seed in (201, 202)]
    assert evidence['metadata']['card_edition'] == 'original'
    assert evidence['metadata']['seeds'] == [201, 202]
    assert len(evidence['metadata']['source_sha256']) == 64
    assert evidence['games'] == 2


def test_fuzz_replay_keeps_edition_and_saves_per_game_findings(monkeypatch, tmp_path):
    editions = []

    def record_game(scenario, seed, **settings):
        editions.append(settings['card_edition'])
        return dict(scenario=scenario, seed=seed, card_edition=settings['card_edition'],
                    seats=[rc.ROMANS], human_turns=1, event_turns=0, events_ok=0,
                    partial=0, findings=[], digest='same-board')

    monkeypatch.setattr(player_fuzz, 'play_game', record_game)
    output = tmp_path / 'fuzz.json'
    assert player_fuzz.main(['--scenario', rc.SCENARIO_GALLIC_WAR,
                            '--seeds', '202', '--card-edition', 'second-edition',
                            '--out', str(output)]) == 0
    assert editions == ['second-edition', 'second-edition']
    evidence = json.loads(output.read_text())
    assert evidence['metadata']['replay'] is True
    assert evidence['metadata']['seeds'] == [202]
    assert evidence['records'][0]['card_edition'] == 'second-edition'


def test_batch_held_out_seeds_are_not_replaced_by_one_through_n(monkeypatch, tmp_path):
    monkeypatch.setenv('PYTHONHASHSEED', '0')
    monkeypatch.setattr(run_batch, 'ProcessPoolExecutor', ThreadPoolExecutor)
    monkeypatch.setattr(run_batch, 'play_one', run_batch._new_record)
    output = tmp_path / 'study'
    assert run_batch.main(['--scenario', rc.SCENARIO_RECONQUEST,
                           '--seeds', '201-202', '--card-edition', 'original',
                           '--workers', '1', '--out', str(output)]) == 1
    records = [json.loads(line) for line in (output / 'games.jsonl').read_text().splitlines()]
    assert [(r['seed'], r['card_edition']) for r in records] == [(201, 'original'), (202, 'original')]
    metadata = json.loads((output / 'metadata.json').read_text())
    assert metadata['seeds'] == [201, 202]
    assert metadata['games_per_scenario'] == 2
    assert metadata['card_edition'] == 'original'


def test_batch_refuses_to_overwrite_any_existing_evidence(monkeypatch, tmp_path):
    monkeypatch.setenv('PYTHONHASHSEED', '0')
    existing = tmp_path / 'earlier-failure.txt'
    existing.write_text('preserve this')
    with pytest.raises(SystemExit) as error:
        run_batch.main(['--games', '1', '--out', str(tmp_path)])
    assert error.value.code == 2
    assert existing.read_text() == 'preserve this'
    assert not (tmp_path / 'metadata.json').exists()


def test_sync_setup_desync_is_a_failure_and_edition_reaches_setup(monkeypatch):
    observed = []

    def setup(scenario, seed, *, card_edition):
        observed.append((seed, card_edition))
        return {'current_card': None}

    monkeypatch.setattr(sync_check, 'setup_scenario', setup)
    monkeypatch.setattr(sync_check, 'get_sop_factions', lambda _: [])
    monkeypatch.setattr(sync_check, 'start_game', lambda _: None)
    monkeypatch.setattr(sync_check, 'desyncs', lambda _: {(rc.CARNUTES, rc.ROMANS, 1, 0)})
    assert sync_check.main(['--seeds', '201', '--card-edition', 'second-edition']) == 1
    assert observed == [(201, 'second-edition')]


def test_generated_reports_do_not_change_source_identity(monkeypatch, tmp_path):
    import subprocess
    from fs_bot.tools import validation_metadata
    root = tmp_path / 'checkout'
    source = root / 'fs_bot' / 'tools' / 'validation_metadata.py'
    source.parent.mkdir(parents=True)
    source.write_text('# source\n')
    def git(*args):
        return subprocess.run(['git', *args], cwd=root, check=True,
                              capture_output=True, text=True)
    git('init')
    git('add', 'fs_bot')
    git('-c', 'user.name=Test', '-c', 'user.email=test@example.invalid',
        'commit', '-m', 'Initial source')
    monkeypatch.setattr(validation_metadata, '__file__', str(source))
    first = validation_metadata.source_identity()
    assert first['dirty'] is False
    (root / 'report.json').write_text('{}')
    assert validation_metadata.source_identity() == first
    (root / 'fs_bot' / 'new_module.py').write_text('# new source\n')
    changed = validation_metadata.source_identity()
    assert changed['dirty'] is True
    assert changed['source_sha256'] != first['source_sha256']
