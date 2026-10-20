"""Cards 63/A63 grant two paid actions with explicit human control."""
import io

import pytest

import fs_bot.rules_consts as rc
from fs_bot.board.pieces import place_piece, count_pieces
from fs_bot.board.control import refresh_all_control
from fs_bot.state.state_schema import build_initial_state
from fs_bot.cards.card_effects import execute_card_A63
from fs_bot.cards.capabilities import get_capability_owner, is_capability_active
from fs_bot.engine.winter_campaign import resolve_winter_campaign, validate_plan, winter_campaign_after_harvest


def _state(faction=rc.ARVERNI, scenario=rc.SCENARIO_GREAT_REVOLT):
    st = build_initial_state(scenario, seed=4)
    st["resources"][faction] = 10
    return st


def _march(origin, destination):
    return {"command": "March", "sa": "No SA", "regions": [],
            "details": {"origins": [origin], "destinations": [destination],
                        "routes": {origin: [destination]}}}


def test_two_human_marches_pay_twice_and_second_sees_first_result():
    st = _state()
    place_piece(st, rc.CARNUTES, rc.ARVERNI, rc.WARBAND, 4)
    refresh_all_control(st)
    requests = []
    def agent(board, faction, request):
        assert request["kind"] == "winter_campaign"
        requests.append(request)
        if len(requests) == 1:
            return _march(rc.CARNUTES, rc.MANDUBII)
        assert count_pieces(board, rc.MANDUBII, faction, rc.WARBAND) == 4
        assert board["resources"][faction] == 9
        return _march(rc.MANDUBII, rc.CARNUTES)
    st["decision_agent"] = agent
    result = resolve_winter_campaign(st, rc.ARVERNI, 63)
    assert [r["remaining_actions"] for r in requests] == [2, 1]
    assert st["resources"][rc.ARVERNI] == 8
    assert count_pieces(st, rc.CARNUTES, rc.ARVERNI, rc.WARBAND) == 4
    assert result["remaining_actions"] == 0
    assert all(e["result"]["executed"] for e in result["actions"])


def test_np_march_also_pays_normal_cost(monkeypatch):
    st = _state()
    st["non_player_factions"] = {rc.ARVERNI}
    place_piece(st, rc.CARNUTES, rc.ARVERNI, rc.WARBAND, 4)
    refresh_all_control(st)
    plans = iter([_march(rc.CARNUTES, rc.MANDUBII), {"command": "Pass"}])
    monkeypatch.setattr("fs_bot.bots.bot_dispatch.dispatch_bot_turn",
                        lambda board, faction: next(plans))
    resolve_winter_campaign(st, rc.ARVERNI, 63)
    assert st["resources"][rc.ARVERNI] == 9


def test_winter_campaign_does_not_swallow_interrupted_choice():
    st = _state()
    def stop(*args):
        raise EOFError("player paused")
    st["decision_agent"] = stop
    with pytest.raises(EOFError):
        resolve_winter_campaign(st, rc.ARVERNI, 63)


def test_a63_records_nonroman_executing_owner_and_fires(monkeypatch):
    st = _state(rc.GERMANS, rc.SCENARIO_ARIOVISTUS)
    st["executing_faction"] = rc.GERMANS
    execute_card_A63(st, shaded=True)
    assert get_capability_owner(st, "A63") == rc.GERMANS
    requests = []
    def agent(board, faction, request):
        requests.append((faction, request))
        return {"decline": True}
    st["decision_agent"] = agent
    result = winter_campaign_after_harvest(st)
    assert result["owner"] == rc.GERMANS
    assert requests[0][1]["card_id"] == "A63"


def test_roman_cannot_take_a63_shaded():
    st = _state(rc.ROMANS, rc.SCENARIO_ARIOVISTUS)
    st["executing_faction"] = rc.ROMANS
    execute_card_A63(st, shaded=True)
    assert not is_capability_active(st, "A63")


def test_card_exception_allows_standalone_sa_and_otherwise_incompatible_pair():
    st = _state(rc.AEDUI)
    assert validate_plan(st, rc.AEDUI, {"sa": "Suborn"}) == 1
    assert validate_plan(st, rc.AEDUI, {"command": "Battle", "sa": "Suborn"}) == 2
    with pytest.raises(ValueError, match="pair with Battle"):
        validate_plan(st, rc.AEDUI, {"sa": "Ambush"})
    with pytest.raises(ValueError, match="remaining"):
        validate_plan(st, rc.AEDUI, {"command": "Battle", "sa": "Ambush"}, 1)


def test_cli_can_explicitly_decline_campaign():
    from fs_bot.cli.reactive import make_cli_reactive
    out = io.StringIO()
    st = _state()
    agent = make_cli_reactive([rc.ARVERNI], io.StringIO("Finish Winter Campaign\n"), out)
    assert agent(st, rc.ARVERNI, {"kind": "winter_campaign", "remaining_actions": 2}) == {"decline": True}
    assert "pay costs" in out.getvalue()
