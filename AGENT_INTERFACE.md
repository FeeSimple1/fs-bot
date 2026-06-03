# Agent interface — playing by judgment (human / LLM)

This engine can be driven by an external **agent** (a human or an LLM) that
plays a Faction by its own judgment instead of the built-in NP bot flowcharts.
The all-bot harness is untouched: with no agent configured, play is byte-for-byte
identical and deterministic.

There are **two integration points**, because a Faction makes two kinds of
decisions:

1. **Top-level Sequence-of-Play turns** — what to do on your own turn (Command /
   Event / Special Activity, and the full plan). Driven by the engine's
   `decision_func` callback.
2. **Reactive decisions** — choices forced on you *during another action's
   resolution*: defending Retreat, which pieces absorb Battle Losses, and
   inter-Faction agreements. Driven by `state["decision_agent"]`.

Plus a **legal-move / validation API** (`fs_bot.engine.moves`) so an agent can
enumerate options and dry-run a candidate move before committing it.

---

## 1. Top-level turns — `decision_func`

`run_game(state, decision_func, execute=True)` calls
`decision_func(state, faction, options, position)` once per Faction's SoP turn.
Return a dict whose `action` is one of the legal engine constants in `options`,
and — for a non-Pass action — a `player_action` carrying the full plan:

```python
def decision_func(state, faction, options, position):
    if faction == MY_FACTION and "command" in options:
        return {"action": "command", "player_action": {
            "command": "Rally", "regions": [], "sa": "No SA", "sa_regions": [],
            "details": {"rally_plan": {"citadels": [], "allies": [],
                                       "warbands": ["Aedui"]}}}}
    return {"action": "pass"}
```

`execute_decision` runs `player_action` through the **real rules engine** — the
same machinery the bots use — so illegal sub-actions are skipped/reported, not
crashed. A `player_action` is:

```text
{"command": "Battle"|"March"|"Rally"|"Raid"|"Recruit"|"Seize"|"Event",
 "regions": [...], "sa": "No SA"|<Special Ability>, "sa_regions": [...],
 "details": { ...command-specific plan... }}
```

The per-command `details` shapes (battle_plan, raid_plan, rally_plan,
recruit_plan, March origins/destinations, disperse_regions, and Event
`card_id`/`text_preference`/`event_params`) are exactly what
`fs_bot/cli/human_plan.py` builds for the interactive CLI — use it as the
reference, or call the `moves` helpers below.

## 2. Reactive decisions — `state["decision_agent"]`

Set `state["decision_agent"] = agent`, a callable:

```python
agent(state, faction, request) -> response | None
```

It is consulted whenever `faction` must make a reactive decision. **Return
`None` (or raise) to defer** that decision to the default NP logic — so an agent
may control any subset of Factions and decision kinds. Request kinds
(`fs_bot.engine.agent`):

| `request["kind"]` | request fields | response |
|---|---|---|
| `RETREAT` | `region, attacker, defender, is_ambush, legal_regions` | `{"retreat": bool, "region": dest_or_None}` (region must be in `legal_regions`) |
| `LOSS_ORDER` | `region, faction, num_losses, is_retreat, is_ambush, pieces` | an ordered list of `(piece_type, piece_state)` (which piece absorbs next); hard pieces still roll |
| `AGREEMENT` | `request_type, requesting_faction, context` | `bool` (agree?) — `request_type` in {`retreat_into_control`, `supply_line`, ...} |

```python
def reactive(state, faction, request):
    if faction != MY_FACTION:
        return None                       # let the bots handle the rest
    if request["kind"] == RETREAT:
        legal = request["legal_regions"]
        return {"retreat": bool(legal), "region": legal[0] if legal else None}
    if request["kind"] == AGREEMENT:
        return False                      # refuse to help opponents
    return None                           # default Loss order
```

## 3. Legal-move / validation API — `fs_bot.engine.moves`

```python
from fs_bot.engine import moves

moves.legal_sop_actions(state, position="1st_eligible", first_action=None)  # ["command","event","pass",...]
moves.legal_commands(faction)                  # the Faction's Command types
moves.regions_with_pieces(state, faction)      # Regions to act in/from
moves.battle_regions(state, faction)           # Regions where a Battle is possible
moves.enemies_in_region(state, region, faction)
moves.subdued_tribes(state, region)
moves.faction_special_abilities(faction, scenario)

ok, info = moves.validate_player_action(state, faction, player_action)   # dry-run on a copy
ok, info, resulting_state = moves.preview_player_action(state, faction, player_action)
```

`validate_player_action` runs the plan on a **deep copy** (never touching the
live game, and never re-entering the live agent) and reports whether it executed
and any per-region `errors`. `preview_player_action` also returns the board the
move *would* produce, so an agent can look before it leaps.

## Putting it together

```python
state["decision_agent"] = reactive          # reactive decisions
run_game(state, decision_func, execute=True) # top-level turns
```

See `fs_bot/tests/test_agent_interface.py` for runnable examples, including a
full game with one agent-controlled Faction playing alongside the bots.

## Current limits

- The reactive hooks cover Retreat, Loss absorption, and the Retreat-into-Control
  and Supply-Line agreements. Other niche agreements (Quarters, resource
  transfers) still use the NP defaults; add an `AGREEMENT` `request_type` at
  those call sites the same way if needed.
- There is no full legal-move *generator* (COIN's branching is enormous);
  `moves` gives the building blocks plus a validator, which is the practical
  shape for an LLM that proposes a move and checks it.
