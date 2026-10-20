"""Malformed saves fail before play; valid version-1 snapshots remain usable."""
import io
import json

import pytest

from fs_bot import rules_consts as rc
from fs_bot.cli.app import main
from fs_bot.state import serialize
from fs_bot.state.setup import setup_scenario


@pytest.mark.parametrize('payload', [[], None, 1, {},
    {'fsbot_save': True, 'state': {}},
    {'fsbot_save': 999, 'state': {}},
    {'fsbot_save': 1},
    {'fsbot_save': 1, 'state': []},
    {'fsbot_save': 1, 'state': {}, 'meta': []},
    {'fsbot_save': 1, 'state': {}, 'log': ['bad']},
    {'fsbot_save': 1, 'state': {'x': {'__tuple__': 'abc'}}},
    {'fsbot_save': 1, 'state': {'x': {'__set__': {}, 'extra': 1}}},
    {'fsbot_save': 1, 'state': {'x': {'__dict__': [['x', 1], ['x', 2]]}}},
    {'fsbot_save': 1, 'state': {'rng': {'__rng__': None}}},
])
def test_malformed_envelope_and_encoded_values(tmp_path, payload):
    path = tmp_path / 'bad.json'
    path.write_text(json.dumps(payload))
    with pytest.raises(serialize.SaveFileError):
        serialize.load_game(path)


@pytest.mark.parametrize('contents', ['{', '', '\xff'])
@pytest.mark.parametrize('flag', ['--load', '--replay'])
def test_cli_reports_bad_save_without_traceback_or_overwriting(tmp_path, contents, flag):
    path = tmp_path / 'bad.json'
    path.write_bytes(contents.encode('latin1'))
    before = path.read_bytes()
    out = io.StringIO()
    assert main([flag, str(path), '--save', str(path)],
                stdin=io.StringIO(''), stdout=out) == 2
    assert 'Cannot load game' in out.getvalue()
    assert 'Traceback' not in out.getvalue()
    assert path.read_bytes() == before


def test_cli_reports_missing_save(tmp_path):
    out = io.StringIO()
    assert main(['--load', str(tmp_path / 'missing.json')], stdout=out) == 2
    assert 'Cannot load game' in out.getvalue()


@pytest.mark.parametrize('scenario', rc.ALL_SCENARIOS)
def test_strict_load_accepts_version_one_setup_without_new_optional_metadata(tmp_path, scenario):
    state = setup_scenario(scenario, seed=5)
    path = tmp_path / 'save.json'
    serialize.save_game(state, path)
    resumed, meta, log = serialize.load_game(path, validate=True)
    assert serialize.encode(resumed) == serialize.encode(state)
    assert meta == {} and log == []


@pytest.mark.parametrize('corrupt', [
    lambda s: s.pop('rng'),
    lambda s: s.update(scenario='invalid'),
    lambda s: s.update(spaces=[]),
    lambda s: s['spaces'].pop(rc.MORINI),
    lambda s: s['spaces'][rc.MORINI].update(control='invalid'),
    lambda s: s['spaces'][rc.PROVINCIA]['pieces'][rc.ROMANS].update({rc.LEGION: -1}),
    lambda s: s['available'][rc.ROMANS].update({rc.AUXILIA: 1.5}),
    lambda s: s['available'][rc.ROMANS].update({rc.AUXILIA: True}),
    lambda s: s['resources'].update({rc.ROMANS: -1}),
    lambda s: s['resources'].update({rc.ROMANS: 46}),
    lambda s: s['deck'].append('not a card'),
    lambda s: s['available'][rc.ROMANS].update({rc.AUXILIA: 999}),
    lambda s: s['tribes'][rc.TRIBE_MENAPII].update(allied_faction='invalid'),
    lambda s: s.update(_card_turn={'card': s['current_card'], 'idx': -1}),
])
def test_strict_load_rejects_malformed_or_inconsistent_board(tmp_path, corrupt):
    state = setup_scenario(rc.SCENARIO_GREAT_REVOLT, seed=5)
    corrupt(state)
    path = tmp_path / 'save.json'
    serialize.save_game(state, path)
    with pytest.raises(serialize.SaveFileError):
        serialize.load_game(path, validate=True)


@pytest.mark.parametrize('meta', [
    {'scenario': 'invalid'}, {'seed': []},
    {'faction_modes': {rc.ROMANS: 'invalid'}},
    {'faction_modes': []}, {'human_snapshots': []},
    {'human_snapshots': {rc.ROMANS: {}}},
])
def test_strict_load_rejects_bad_frontend_metadata(tmp_path, meta):
    path = tmp_path / 'save.json'
    serialize.save_game(setup_scenario(rc.SCENARIO_GREAT_REVOLT, seed=5), path, meta=meta)
    with pytest.raises(serialize.SaveFileError):
        serialize.load_game(path, validate=True)


def test_failed_replace_preserves_previous_save_and_removes_temporary(tmp_path, monkeypatch):
    path = tmp_path / 'save.json'
    serialize.save_game({'old': True}, path)
    before = path.read_bytes()
    def fail(*args):
        raise OSError('disk replacement failed')
    monkeypatch.setattr(serialize.os, 'replace', fail)
    with pytest.raises(OSError):
        serialize.save_game({'new': True}, path)
    assert path.read_bytes() == before
    assert list(tmp_path.iterdir()) == [path]


def test_partial_states_remain_supported_by_low_level_loader(tmp_path):
    path = tmp_path / 'partial.json'
    serialize.save_game({'example': {'__set__': 'literal key'}}, path)
    assert serialize.load_game(path)[0] == {'example': {'__set__': 'literal key'}}
    with pytest.raises(serialize.SaveFileError):
        serialize.load_game(path, validate=True)


@pytest.mark.parametrize('missing', ['first_action', 'frost', 'arverni_phase',
                                    'actions_taken', 'eligible', 'passes'])
def test_pending_turn_requires_every_field_consumed_on_resume(tmp_path, missing):
    from fs_bot.engine.game_engine import start_game, play_card
    state = setup_scenario(rc.SCENARIO_GREAT_REVOLT, seed=1)
    start_game(state)
    def pause(*args):
        raise EOFError()
    with pytest.raises(EOFError):
        play_card(state, pause, execute=True)
    state['_card_turn'].pop(missing)
    path = tmp_path / 'pending.json'
    serialize.save_game(state, path)
    with pytest.raises(serialize.SaveFileError, match='Pending turn'):
        serialize.load_game(path, validate=True)


def test_pending_turn_rejects_limited_command_as_first_action(tmp_path):
    from fs_bot.engine.game_engine import (
        ACTION_LIMITED_COMMAND, start_game, play_card,
    )
    state = setup_scenario(rc.SCENARIO_GREAT_REVOLT, seed=1)
    start_game(state)

    def pause(*args):
        raise EOFError()

    with pytest.raises(EOFError):
        play_card(state, pause, execute=True)
    state['_card_turn']['first_action'] = ACTION_LIMITED_COMMAND
    path = tmp_path / 'pending.json'
    serialize.save_game(state, path)
    with pytest.raises(serialize.SaveFileError, match='first action'):
        serialize.load_game(path, validate=True)
