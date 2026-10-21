"""The outcome guardrail must compare every requested game/faction."""
import json

import pytest

import fs_bot.rules_consts as rc
from fs_bot.tools import balance_smoke as balance


def _baseline(tmp_path, games):
    path = tmp_path / "baseline.json"
    path.write_text(json.dumps({"games": games}), encoding="utf-8")
    return str(path)


def _game(winner=rc.ROMANS):
    return {"winner": winner, "cards": 20}


def test_default_matrix_covers_all_five_scenarios(tmp_path, monkeypatch):
    scenarios = {rc.SCENARIO_PAX_GALLICA, rc.SCENARIO_RECONQUEST,
                 rc.SCENARIO_GREAT_REVOLT, rc.SCENARIO_ARIOVISTUS,
                 rc.SCENARIO_GALLIC_WAR}
    path = _baseline(tmp_path, {f"{s}|1": _game() for s in scenarios})
    played = []
    def play(scenario, seed):
        played.append((scenario, seed))
        return _game()
    monkeypatch.setattr(balance, "play_bot_game", play)
    assert balance.main(["--seeds", "1", "--baseline", path]) == 0
    assert set(played) == {(s, 1) for s in scenarios}
    assert len(played) == 5


def test_german_drift_detected_when_every_other_faction_is_within_band(tmp_path, monkeypatch, capsys):
    # Each old faction loses only 1/3, below band0.4. Germans gain 100%.
    # Excluding Germans would falsely report a clean result.
    scenario = rc.SCENARIO_ARIOVISTUS
    path = _baseline(tmp_path, {f"{scenario}|{i}": _game(f)
        for i, f in enumerate((rc.ROMANS, rc.AEDUI, rc.BELGAE), 1)})
    monkeypatch.setattr(balance, "play_bot_game", lambda *a: _game(rc.GERMANS))
    assert balance.main(["--seeds", "1-3", "--scenarios", scenario,
                         "--baseline", path, "--band", "0.4"]) == 1
    output = capsys.readouterr().out
    assert "Germans" in output and "DRIFT" in output


@pytest.mark.parametrize("selection,baseline_games", [
    (rc.SCENARIO_PAX_GALLICA,
     {f"{rc.SCENARIO_PAX_GALLICA}|1": _game()}),
    (rc.SCENARIO_PAX_GALLICA + "|" + rc.SCENARIO_ARIOVISTUS,
     {f"{rc.SCENARIO_PAX_GALLICA}|1": _game(),
      f"{rc.SCENARIO_PAX_GALLICA}|2": _game()}),
])
def test_partial_baseline_is_rejected_before_any_games_run(tmp_path, monkeypatch, capsys,
                                                          selection, baseline_games):
    path = _baseline(tmp_path, baseline_games)
    def should_not_run(*args):
        raise AssertionError("missing coverage must fail before playing")
    monkeypatch.setattr(balance, "play_bot_game", should_not_run)
    assert balance.main(["--seeds", "1-2", "--scenarios", selection,
                         "--baseline", path]) == 2
    assert "Missing" in capsys.readouterr().out


def test_unknown_scenario_is_not_silently_skipped(tmp_path, monkeypatch):
    with pytest.raises(SystemExit) as exc:
        balance.main(["--scenarios", "Typo scenario", "--baseline",
                      _baseline(tmp_path, {})])
    assert exc.value.code == 2


def test_invalid_baseline_outcome_is_reported(tmp_path, capsys):
    path = _baseline(tmp_path, {f"{rc.SCENARIO_ARIOVISTUS}|1": {"winner": "none", "cards": 20}})
    assert balance.main(["--seeds", "1", "--scenarios", rc.SCENARIO_ARIOVISTUS,
                         "--baseline", path]) == 2
    assert "Invalid baseline game" in capsys.readouterr().out


def test_update_can_add_missing_scenario_without_removing_existing_games(tmp_path, monkeypatch):
    existing = f"{rc.SCENARIO_PAX_GALLICA}|1"
    path = _baseline(tmp_path, {existing: _game()})
    monkeypatch.setattr(balance, "play_bot_game", lambda *a: _game(rc.GERMANS))
    assert balance.main(["--update", "--seeds", "1", "--scenarios", rc.SCENARIO_ARIOVISTUS,
                         "--baseline", path]) == 0
    games = json.loads(open(path, encoding="utf-8").read())["games"]
    assert games[existing] == _game()
    assert games[f"{rc.SCENARIO_ARIOVISTUS}|1"] == _game(rc.GERMANS)


IMPOSSIBLE_WINNERS = [
    (rc.SCENARIO_PAX_GALLICA, rc.GERMANS),
    (rc.SCENARIO_RECONQUEST, rc.GERMANS),
    (rc.SCENARIO_GREAT_REVOLT, rc.GERMANS),
    (rc.SCENARIO_ARIOVISTUS, rc.ARVERNI),
]


@pytest.mark.parametrize('scenario,winner', IMPOSSIBLE_WINNERS)
def test_impossible_baseline_winner_fails_before_play(tmp_path, monkeypatch, capsys,
                                                     scenario, winner):
    path = _baseline(tmp_path, {f'{scenario}|1': _game(winner)})
    def should_not_run(*args):
        raise AssertionError('an impossible baseline must fail before playing')
    monkeypatch.setattr(balance, 'play_bot_game', should_not_run)
    assert balance.main(['--seeds', '1', '--scenarios', scenario,
                         '--baseline', path]) == 2
    assert 'Invalid baseline game' in capsys.readouterr().out


@pytest.mark.parametrize('scenario,winner', IMPOSSIBLE_WINNERS)
@pytest.mark.parametrize('update', [False, True])
def test_impossible_current_winner_fails_without_overwriting_baseline(
        tmp_path, monkeypatch, capsys, scenario, winner, update):
    path = _baseline(tmp_path, {f'{scenario}|1': _game()})
    before = open(path, encoding='utf-8').read()
    monkeypatch.setattr(balance, 'play_bot_game', lambda *args: _game(winner))
    args = ['--seeds', '1', '--scenarios', scenario, '--baseline', path]
    assert balance.main(args + (['--update'] if update else [])) == 2
    assert 'Invalid game outcome' in capsys.readouterr().out
    assert open(path, encoding='utf-8').read() == before


@pytest.mark.parametrize('winner', [rc.GERMANS, rc.ARVERNI])
def test_gallic_war_accepts_winner_from_either_half(tmp_path, monkeypatch, winner):
    scenario = rc.SCENARIO_GALLIC_WAR
    path = _baseline(tmp_path, {f'{scenario}|1': _game(winner)})
    monkeypatch.setattr(balance, 'play_bot_game', lambda *args: _game(winner))
    assert balance.main(['--seeds', '1', '--scenarios', scenario,
                         '--baseline', path]) == 0
