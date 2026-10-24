"""Old-writer fixtures and installed resources remain usable after updates."""
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path

import pytest

from fs_bot import rules_consts as rc
from fs_bot.state.serialize import SaveFileError, encode, load_game, save_game
from fs_bot.state.setup import setup_scenario
from fs_bot.version import __version__, engine_identity

FIXTURES = Path(__file__).parent / "fixtures" / "compatibility_8ef88e2"
MANIFEST = json.loads((FIXTURES / "manifest.json").read_text(encoding="utf-8"))
_spec = importlib.util.spec_from_file_location("_old_save_fixture_driver", FIXTURES / "generate.py")
_driver = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_driver)


@pytest.mark.parametrize("name", sorted(MANIFEST["fixtures"]))
def test_archived_old_writer_save_resumes_to_recorded_result(name):
    evidence = MANIFEST["fixtures"][name]
    path = FIXTURES / name
    assert hashlib.sha256(path.read_bytes()).hexdigest() == evidence["file_sha256"]
    # These files really were written by the old serializer, without the new
    # provenance envelope or subsequently introduced optional state fields.
    assert "engine" not in json.loads(path.read_text(encoding="utf-8"))
    state, meta, log = load_game(path, validate=True)
    with contextlib.redirect_stdout(io.StringIO()):
        result = _driver.continue_fixture(evidence["kind"], state, meta, log)
    assert _driver.digest(result) == evidence["continued_sha256"]


def test_compatibility_fixture_generator_has_recorded_identity():
    assert MANIFEST["source_commit"] == _driver.SOURCE_COMMIT
    assert MANIFEST["source_sha256"] == _driver.SOURCE_SHA256
    assert hashlib.sha256((FIXTURES / "generate.py").read_bytes()).hexdigest() == MANIFEST["generator_sha256"]


def test_writer_records_engine_identity_without_changing_state_or_metadata(tmp_path):
    state = setup_scenario(rc.SCENARIO_GREAT_REVOLT, seed=613)
    before = encode(state)
    meta = {"scenario": state["scenario"], "seed": 613}
    path = tmp_path / "save.json"
    save_game(state, path, meta=meta)
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["fsbot_save"] == 1
    assert payload["engine"] == engine_identity()
    assert payload["engine"]["version"] == __version__
    assert len(payload["engine"]["source_sha256"]) == 64
    assert encode(state) == before
    loaded, loaded_meta, log = load_game(path, validate=True)
    assert encode(loaded) == before
    assert loaded_meta == meta
    assert log == []


def test_different_writer_identity_does_not_invent_a_save_format_migration(tmp_path):
    state = setup_scenario(rc.SCENARIO_GREAT_REVOLT, seed=613)
    path = tmp_path / "save.json"
    save_game(state, path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["engine"] = {"version": "0.0.1", "source_sha256": "a" * 64}
    path.write_text(json.dumps(payload), encoding="utf-8")
    assert encode(load_game(path, validate=True)[0]) == encode(state)


@pytest.mark.parametrize("identity", [None, [], {},
    {"version": 1, "source_sha256": "a" * 64},
    {"version": "0.1.0", "source_sha256": "bad"},
    {"version": "0.1.0", "source_sha256": "g" * 64},
])
def test_malformed_writer_provenance_is_rejected(tmp_path, identity):
    path = tmp_path / "save.json"
    path.write_text(json.dumps({"fsbot_save": 1, "engine": identity, "state": {}}), encoding="utf-8")
    with pytest.raises(SaveFileError, match="Engine provenance"):
        load_game(path)


def test_installed_reference_fallback_provides_both_card_sets(tmp_path, monkeypatch):
    from fs_bot import version
    from fs_bot.cards import card_text
    source = version.reference_directory()
    package = tmp_path / "site-packages" / "fs_bot"
    target = package / "_references"
    (target / "Ariovistus").mkdir(parents=True)
    for relative in ("Card Reference", "Ariovistus/A Card Reference"):
        (target / relative).write_bytes((source / relative).read_bytes())
    monkeypatch.setattr(version, "__file__", str(package / "version.py"))
    monkeypatch.setattr(card_text, "_CACHE", None)
    assert version.reference_directory() == target
    assert "Cicero" in card_text.get_card_text(1)
    assert "Vergobret" in card_text.get_card_text("A38")
    assert "Diviciacus" in card_text.get_card_text(rc.CARD_O38)
    assert "pick 4 Arverni Warbands" in card_text.get_card_text(30, card_edition="second-edition")
