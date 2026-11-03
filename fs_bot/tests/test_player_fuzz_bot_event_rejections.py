"""Explicit NPC Event rejection must fail mixed-seat acceptance (§8.1.1)."""
import copy
import json

import pytest

from fs_bot import rules_consts as rc
from fs_bot.tools import player_fuzz as fuzz


def _record(*, bot=True, command=rc.FIRST_DID_EVENT, execution=None):
    return {
        "action": fuzz.ACTION_EVENT,
        "bot_action" if bot else "player_action": {"command": command},
        "execution": execution,
    }


def _completed(records):
    cards = [{"card": card, "turn_result": {"actions_taken": actions}}
             for card, actions in records]
    cards[-1].update(game_over=True, winner=rc.ROMANS)
    return {"card_results": cards, "game_over": True,
            "total_cards_played": len(cards), "winter_count": 1}


def test_rejected_npc_event_fails_cli_even_when_both_replays_match(
        monkeypatch, tmp_path, capsys):
    # This is the actual A45 rejection text retained from the failing CI
    # trajectory. Equal digests previously let this swallowed exception pass.
    reason = ('event not applicable: TypeError("\'<\' not supported between '
              'instances of \'str\' and \'NoneType\'")')
    rejected = {"executed": False, "rejected": True, "reason": reason}
    trajectory = _completed([
        ("A44", {rc.AEDUI: _record(bot=False, execution=rejected)}),
        ("A45", {rc.AEDUI: _record(execution=rejected)}),
        ("A46", {rc.ROMANS: _record(execution={
            "executed": True, "event_result": {"declined": True}})}),
    ])
    # The same faction appears on both authoring paths. Its current/final
    # seat label must not cause the NPC record to be ignored or the human
    # malformed-input record to be reported as an NPC error.
    monkeypatch.setattr(fuzz, "_pick_seats", lambda *_: [rc.AEDUI])
    calls = []

    def returned_game(*args, **kwargs):
        calls.append(True)
        return copy.deepcopy(trajectory)

    monkeypatch.setattr(fuzz, "run_game", returned_game)
    output = tmp_path / "fuzz.json"
    exit_code = fuzz.main(["--scenario", rc.SCENARIO_ARIOVISTUS,
                           "--seeds", "17", "--out", str(output)])

    result = json.loads(output.read_text())
    assert len(calls) == 2  # The real CLI requested normal same-seed replay.
    assert exit_code == result["hard_findings"] == 1
    assert result["by_kind"] == {"bot-event-rejected": 1}
    assert result["records"][0]["game_completed"] is True
    assert result["records"][0]["findings"] == [
        ["bot-event-rejected", "A45", f"{rc.AEDUI}: {reason}"]]
    assert "hard-findings=1" in capsys.readouterr().out


@pytest.mark.parametrize("execution", [
    {"executed": True, "event_result": {"declined": True}},
    {"executed": False, "reason": "free Command declined"},
    {"executed": False, "rejected": False, "reason": "free Rally declined"},
    {"executed": True, "rejected": True},
    {"executed": False},
    None,
])
def test_only_explicit_failed_bot_events_are_classified(monkeypatch, execution):
    monkeypatch.setattr(fuzz, "run_game", lambda *args, **kwargs: _completed([
        (2, {rc.ROMANS: _record(execution=execution)}),
    ]))
    result = fuzz.play_game(rc.SCENARIO_PAX_GALLICA, 1)
    assert result["game_completed"] is True
    assert result["findings"] == []


def test_bot_commands_and_human_malformed_events_are_not_npc_event_failures(monkeypatch):
    rejected = {"executed": False, "rejected": True, "reason": "invalid plan"}
    monkeypatch.setattr(fuzz, "run_game", lambda *args, **kwargs: _completed([
        (2, {rc.ROMANS: _record(bot=False, execution=rejected),
             rc.AEDUI: _record(command=rc.CMD_RALLY, execution=rejected)}),
    ]))
    result = fuzz.play_game(rc.SCENARIO_PAX_GALLICA, 1)
    assert result["findings"] == []


def test_each_rejected_bot_event_retains_its_actor_card_and_raw_error():
    first = "event not applicable: ValueError('invalid target')"
    second = "event not applicable: TypeError('invalid None comparison')"
    trajectory = _completed([
        ("A45", {rc.AEDUI: _record(execution={
            "executed": False, "rejected": True, "reason": first})}),
        (45, {rc.BELGAE: _record(execution={
            "executed": False, "rejected": True, "reason": second})}),
    ])
    assert fuzz._rejected_bot_events(trajectory) == [
        (rc.AEDUI, "A45", first), (rc.BELGAE, 45, second)]
