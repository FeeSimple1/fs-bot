"""Immediate Event actions must never trigger again on a later card."""
import fs_bot.rules_consts as rc
from fs_bot.engine.execute import _resolve_free_actions
from fs_bot.state.state_schema import build_initial_state

def test_card72_free_action_is_consumed_before_later_card44(monkeypatch):
    import fs_bot.engine.execute as exe
    s = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=4)
    s.setdefault("event_modifiers", {})["card_72_march_and_enemy_battle"] = True
    calls = []
    monkeypatch.setattr(exe, "_resolve_card72_march_enemy_battle", lambda *a: calls.append(1) or [])
    _resolve_free_actions(s, rc.AEDUI)
    _resolve_free_actions(s, rc.AEDUI)
    assert len(calls) == 1

