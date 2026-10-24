# Agent interface — playing by judgment (human / LLM)

This engine can be driven by an external **agent** (a human or an LLM) that
plays a Faction by its own judgment instead of the built-in NP bot flowcharts.
The standard frontends dispatch bot seats to the built-in non-player logic;
a custom turn callback must dispatch those seats explicitly. See [current status](docs/current-status.md) for revision-specific
verification and adopted provisional rulings, and the [documentation
index](docs/README.md) for the other guides. The owner-adopted
[PR-01 through PR-06](docs/provisional-rulings.md) are subject to possible
later correction if an authoritative source is found.

There are **two integration points**, because a Faction makes two kinds of
decisions:

1. **Top-level Sequence-of-Play turns** — what to do on your own turn (Command /
   Event / Special Activity, and the full plan). Driven by the engine's
   `decision_func` callback.
2. **Decisions during resolution** — Retreat, Battle and Harassment losses,
   agreements, March piece selection, Event grants, and Winter choices. Driven
   by `state["decision_agent"]`.

Plus a **legal-move / validation API** (`fs_bot.engine.moves`) so an agent can
enumerate options and dry-run a candidate move before committing it.

---

## 1. Top-level turns — `decision_func`

`run_game(state, decision_func, execute=True)` calls
`decision_func(state, faction, options, position)` when a Faction needs its
SoP action. A rejected action may cause another call for the same turn.
Return a dict whose `action` is one of the legal engine constants in `options`,
and — for a non-Pass action — a `player_action` carrying the full plan.
This minimal shape example uses a placeholder faction and passes for other
seats; use a real dispatcher for an actual game, as in `fs_bot/tools/llm_seat.py`:

```python
def decision_func(state, faction, options, position):
    if faction == MY_FACTION and "command" in options:
        return {"action": "command", "player_action": {
            "command": "Rally", "regions": [], "sa": "No SA", "sa_regions": [],
            "details": {"rally_plan": {"citadels": [], "allies": [],
                                       "warbands": ["Aedui"]}}}}
    return {"action": "pass"}
```

`execute_decision` runs `player_action` through the same rules engine used by
the bots. Inspect the execution result and any reported sub-action errors;
a partial execution differs from a wholly refused action. A `player_action` is:

```text
{"command": "Battle"|"March"|"Rally"|"Raid"|"Recruit"|"Seize"|"Event",
 "regions": [...], "sa": "No SA"|<Special Ability>, "sa_regions": [...],
 "details": { ...command-specific plan... }}
```

The per-command `details` shapes (battle_plan, raid_plan, rally_plan,
recruit_plan, March origins/destinations, disperse_regions, and Event
`card_id`/`text_preference`/`event_params`) are exactly what
`fs_bot/cli/human_plan.py` builds for the interactive CLI — use it as the
reference. March plans additionally accept exact per-origin `routes`
({origin: [region, ...]}), per-origin subset `groups`
({origin: {piece_type: count, "Leader": bool}}), and §3.3.2
`extra_groups` ([{origin, route, group}] — further groups from the
post-departure remainder of an origin). The Roman Build and Scout
Special Abilities accept player plans (`build_plan`
{forts, subdue, allies} and `scout_plan` {auxilia_moves,
scout_targets}); without one, the bots' flowchart plans run instead.
Optional `details.transfers` (`[{"to": faction, "amount": integer}]`, §1.5.2)
ride an action. The helpers below provide validation; the source plan builders
remain the detailed reference for each Command and Special Activity.

Human plans may set `sa_timing` to `"before"` or `"after"` (default).
This controls resolution, independently of the timing required by the bot
flowcharts. Ambush and Besiege are Battle modifiers and resolve within the
Battle. For Rally, Recruit, Raid, or Seize, `sa_timing: "during"` accepts
`details.command_parts: [first_plan, second_plan]`: two plans for the same
Command, selecting different Regions, with the accompanying Special
Activity between them. March and Battle currently support before/after
timing; their Command-wide movement and Battle bookkeeping is not split.

Diviciacus cooperation is requested through `details.diviciacus_regions`
for a Command and `details.diviciacus_sa_regions` for a Special Activity.
Use `engine.diviciacus.eligible_regions(state, faction, phase)` to find
eligible Regions (`command` or `special_ability`); explicit `[]` declines.
Human plans do not silently request loans when these fields are absent.
The other Faction's consent is obtained during execution. A preview can
show a conditional plan assuming human consent; it never consumes that
human's actual decision. Original card 38 covers Commands and defense;
the Leader's A1.4 effect also covers Special Activities within its range.

Suborn uses `details.suborn_plan`, with a list of Region entries containing
`region` and ordered `actions`. Each canonical action has `action` (`place`
or `remove`), `faction`, `piece_type`, and `physical_owner` matching the
Faction; removals can specify `piece_state`, and Allies specify `tribe`.
Use `commands.sa_suborn.legal_suborn_operations(state, region)` and
`suborn_preview(state, region, operations)` to build a cumulative legal
sequence. Explicit physical owners retain their printed colour during
Diviciacus cooperation. Existing bot action labels remain supported.

The Sequence-of-Play engine persists progress through the current card in
the state. An interruption rolls back only the unfinished action or phase,
including its RNG changes. Frontends with external queues/logs can attach
`transaction_checkpoint()` and `transaction_restore(token)` attributes to
their `decision_func` to keep those synchronized with rollback.
A wholly refused human Command raises `ActionRejected` without consuming the
turn; interactive frontends can provide
`decision_func.decision_rejected(state, faction, result)` to explain the
failure and retry the same turn.

## 2. Reactive decisions — `state["decision_agent"]`

Set `state["decision_agent"] = agent`, a callable:

```python
agent(state, faction, request) -> response | None
```

The callback receives the live board, which it must treat as read-only, and
is consulted for decisions during resolution. At this low-level interface,
returning `None` or raising an ordinary exception defers to default logic;
raising `EOFError` interrupts. A raw callback is therefore not a durable
human-input queue. The terminal and [file-based session](#file-based-assistant-sessions)
frontends handle pending human input explicitly and validate responses.

The constants `RETREAT`, `LOSS_ORDER`, `AGREEMENT`, and `HARASSMENT_LOSS`
come from `fs_bot.engine.agent`; other kinds below are literal strings.
Requests can include additional context. Copy offered values rather than
inventing pieces, regions, owners, or internal grant flags.

| `request["kind"]` | request fields | response |
|---|---|---|
| `RETREAT` | `region, attacker, defender, is_ambush, legal_regions` | `{"retreat": bool, "region": dest_or_None}` (region must be in `legal_regions`) |
| `LOSS_ORDER` | `region, faction, num_losses, is_retreat, is_ambush, pieces` | an ordered subset of the supplied entries; borrowed forces may add a third `physical_owner` field; hard pieces still roll |
| `HARASSMENT_LOSS` | `region, harasser, loss_index, num_losses, phase, options`; March carries `departing_pieces`, Seize carries `pieces` | `{"choice": option}` from `options`; see the phases below |
| `march_cohort` | `phase, region, piece_type, count, available`; may include `acting_faction, physical_owner` | `{"counts": {visibility: count}}`, totaling exactly the requested `count` |
| `diviciacus_pieces` | `phase` (`placement`, `formation`, `dropoff`, `loss`), `region, piece_type, count, available` by physical owner | `{"counts": {owner: count}}`, totaling `count` without exceeding `available` |
| `AGREEMENT` | `request_type, requesting_faction, context` | `bool` (agree?) — `request_type` in {`retreat_into_control`, `supply_line`, ...} |
| `free_action` | `request_type` plus the Event's scope; ordinary grants may carry `allowed_commands, allowed_regions, max_regions, with_sa, free, allow_decline`; standalone SAs use `allowed_sas` | ordinary action or subtype-specific response below; decline only when permitted |
| `kinship` | A65; `attackers, regions_by_faction` | `{"faction": attacker, "regions": [...]}`, decline, or explicit default |
| `quarters_plan` | `faction, errors` | relocation/payment object described below, or explicit default |
| `winter_campaign` | `card_id, remaining_actions`, optional `errors` | one paid action, combined Command+SA, or decline; see the Winter section below |
| `frumentum_amount` | A53; `available_resources` (Aedui) | `{"amount": integer}`, `{"decline":true}` (zero), or explicit default |
| `frumentum_action` | A53; `remaining_actions, remaining_resources, reserved_roman_resources` | one Recruit/March plan or standalone Build/Scout plan, `{"skip": action_name}`, finish with `{"decline":true}`, or explicit default |
| `raid_intimidate` | A3.4.3; `region, raiders, max_removals, targets` | `{"targets":[...]}`, marker only `{"targets":[]}`, `{"decline":true}`, or `{"use_default":true}` |

The file-based frontend accepts `{"use_default":true}` for a non-turn
request only as an explicit decision. An omitted or invalid response remains
pending. A normal turn still requires a legal `action` and its plan.

Diviciacus uses `AGREEMENT` with `request_type: "diviciacus"` for the
other Faction's consent. Its context identifies the phase, selected Regions,
Command/Special Activity and targets. A human defender first receives
`request_type: "diviciacus_defense"` to choose whether to request cooperation.
Fixed Event Battles use `request_type: "diviciacus_command"` for the
acting human's opt-in before requesting the lender's agreement.
Both replies are booleans. Loss-order entries retain physical owners even
when borrowed pieces fight as the other type; copy the offered entries.

### Harassment and physical March pieces

A `HARASSMENT_LOSS` request's `phase` determines what is being selected:

| Phase | Choice |
|---|---|
| `absorb` | An offered soft piece type or `"roll"` |
| `remove` | A hard piece type after a failed saving roll; the request includes `roll` |
| `piece_state` | The offered visibility of the soft casualty |
| `ally` | The exact Allied Tribe lost to Seize Harassment |

Return one offered value, for example `{"choice":"roll"}` only when
`"roll"` is in `options`. The engine makes the roll and requests any resulting
casualty separately. Later harassers see earlier losses. Choosing whether to
Harass is a separate `AGREEMENT` request with `request_type: "harassment"`.
Under provisional PR-05, Ariovistus uses the printed faction order with
Germans in their printed slot, then automatic Arverni last. PR-06 retains the
last actually played non-Winter card's order throughout Winter, including
all-pass cards. The engine derives that order from saved `played_cards`; it
does not replace `current_card` or use the upcoming card. If no preceding
Event can be recovered, the compatibility fallback uses card 63/A63's
scenario-appropriate order, then the game-run faction. See the
[ruling register](docs/provisional-rulings.md#pr-06) for scope and status.

`march_cohort` identifies physical pieces after origin flipping (`formation`)
or when leaving part of the carried group behind (`dropoff`). For a request
with `count: 2` and sufficient offered counts, a response can be
`{"counts":{"Hidden":1,"Revealed":1}}`. Counts cannot exceed `available`
or change the group's planned total. The request may identify a different
acting faction or physical owner, as with Divination or Enlist; that identity
is supplied by the engine and cannot be changed by the response.

The validators are `commands.march.validate_harassment_response` and
`engine.march_choices.validate_response`; both validate without moving
pieces or consuming RNG.

### Scoped Event grants

Free-action requests describe an Event's scope. `event_command` and
`event_rally` select a Command; `event_sa` selects only an SA. Optional
`as_if_control` and `allow_devastated` apply only to the granted Rally/Recruit.
`required_destinations` restricts where every March group must end.
`engine.free_actions.validate_free_action_response` checks a response on an
isolated board and RNG and returns an error string or `None`. The terminal
prompts **Plan the action / Use bot default / Decline**, keeps normal
before/during/after SA ordering, and offers a new plan after a failed check.
EOF interrupts and preserves the pending decision. A grant can require a
follow-on action when possible (`allow_decline: false`); the generic decline
response does not override that requirement. An engine-supplied
`acting_faction` identifies the force commanded by a different chooser,
such as German pieces under Divination. Do not add or change grant fields in
a submitted action.

Some `free_action` subtypes use a specialized response instead of an ordinary
Command plan. These shapes describe the response, not guaranteed legal
choices for a particular board:

| `request_type` | Response fields | Validator/source |
|---|---|---|
| `impetuosity_march` | `origin, destination, warbands` | `cards/impetuosity.py`; one original Hidden group, no Leader |
| `impetuosity_unshaded_march` | `destination, groups: [{origin, group}]` | `cards/impetuosity_unshaded.py`; selected origins are adjacent to one destination |
| `impetuosity_enemy_battle` | `attacker` from the request's `attackers` | `engine/free_actions.py`; chooses the enemy attacker, not a normal Battle plan |
| `publius_march` | `origin, route, legions, auxilia`, optional `dropoffs` | `cards/publius.py`; route is a Region list, drop-offs map intermediate Regions to piece counts |
| `morasses_faction` | `faction` from the request's `factions` | `cards/morasses.py` |
| `morasses_march` | `action, in_place` | `cards/morasses.py`; `action` is an ordinary March plan or null, `in_place` lists stationary origins |

Use `engine.free_actions.validate_free_action_response` for these subtypes
as well as ordinary grants. It returns an error string or `None`; do not
submit a custom subtype as a top-level Command. Subsequent Battle choices
arrive as their own requests on the resulting board. Unshaded Impetuosity's
adjacent March is required when possible; A17's follow-on Battle is required
when possible after the optional combined action has been accepted.

Kinship uses the separate `kinship` kind, selecting the attacker and any
eligible Battle Regions together. Its Battle excludes the attacking Leader
from fighting and losses without moving that physical piece. The validator
is `cards.kinship.validate_response(state, response)`.

### Quarters

A `quarters_plan` response maps the acting faction to relocations:
`{"Belgae":[["Warband","Morini","Atrebates",2]]}` is a shape example.
Each entry is `[piece_type, origin, destination, count]`; legality depends on
the current board and any host agreement. `{"Belgae":[]}` chooses no
relocations. Arrivals cannot make a second adjacent relocation in the same
step; Roman movement to Provincia is a later step.

Romans may also include `"Romans_quartering"`, mapping Regions to choices
with `free_pieces` and `pay_pieces` lists of `[piece_type, visibility, count]`
(use null visibility for Legions), or aggregate `pay`/`roll` counts. Optional
`_pay_order` within `Romans_quartering` controls Resource allocation order.
The printed free capacity and available Resources still apply. See
`engine.quarters.validate_quarters_plan` and
`fs_bot/tests/test_quarters_decisions.py` for concrete legal examples.

### Other paid and optional grants

After Germanic Warbands Raid with Ariovistus, `raid_intimidate` offers their
optional free Intimidate. The pending board shows the completed Raid's
Resources and revealed Warbands before the choice. `raiders` is the number
that actually Raided; `max_removals` is the lesser of that number and two.
Each offered target has `target_faction`, `target_piece`, `target_state`, and
`available`. Return the first three fields for each chosen piece, repeating an
entry only up to its available count. All chosen pieces must belong to one
Faction with no Leader in the Region. For example:

```json
{"targets":[{"target_faction":"Romans","target_piece":"Auxilia","target_state":"Hidden"}]}
```

An empty `targets` list places only the Intimidated marker. Decline leaves
the Raid intact, while explicit default uses the German bot's priorities.
This effect uses the Warbands that just Raided, does not reveal additional
Hidden Warbands, and does not consume a Special Ability. A separate normal
Intimidate may use additional Hidden Warbands. The validator
`engine.raid_intimidate.validate_response(state, request, response)` raises
`ValueError` for an illegal choice without changing the live board or RNG.
Missing or invalid assistant input remains pending; accepted choices are
journaled and replayed with the rest of the action.

Frumentum uses **normal paid costs** and only the specified Aedui allocation.
Romans choose the order of Recruit, March, and one Special Ability; each may
be used at most once. After each action, the next request shows the updated
board and remaining allowance. The Roman personal treasury is reserved.
NP Aedui supply half their Resources only to NP Romans (A8.6.6), and none to
human Romans. Under provisional [PR-03](docs/provisional-rulings.md#pr-03),
Romans retain unused transferred funds subject to the normal cap. The result
field `unused_policy` keeps the historical string `legacy_roman_retention`
for compatibility; it now describes an adopted project ruling. No automatic
refund occurs. Any negotiated return remains an explicit normal transfer.
`engine.frumentum.validate_response` validates both request kinds without
spending live resources or RNG or consuming any human reaction.

```python
from fs_bot.engine.agent import RETREAT, AGREEMENT

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
move would produce using that preview's default reactions. These helpers
remove the live decision agent; they do not ask another human for consent or
predict that human's future choices. Actual execution can therefore depend
on later agreement, Retreat, casualty, or March-piece decisions.

## Putting it together

A custom driver must identify human seats independently of its callbacks:
remove them from `state["non_player_factions"]`. This set affects bot rules,
request ownership, and victory comparisons. For example, after setup:

```python
from fs_bot.engine.game_engine import get_sop_factions

state["non_player_factions"] = set(get_sop_factions(state)) - {MY_FACTION}
state["decision_agent"] = reactive          # reactive decisions
run_game(state, decision_func, execute=True) # top-level turns
```

The Gallic War changes German and Arverni seats at the Interlude. The standard
frontends maintain that transition; a custom driver must do so as well.

See `fs_bot/tests/test_agent_interface.py` for runnable examples, including a
full game with one agent-controlled Faction playing alongside the bots.

## Current limits

- Reactive hooks cover Retreat, Loss absorption, Supply Line, Quarters hosting,
  Trade, Harassment and its losses, physical March pieces, Winter Campaign,
  Raid Intimidate, Kinship, and scoped Event-granted actions.
  Resource gifts are explicit `details.transfers` entries in the acting
  faction's plan.
- There is no full legal-move *generator* (COIN's branching is enormous);
  `moves` gives the building blocks plus a validator, which is the practical
  shape for an LLM that proposes a move and checks it.


## File-based assistant sessions

`python -m fs_bot.tools.llm_seat` implements both integration points without
interactive stdin. `play` stops at the next human request; `submit --response
'<JSON>' --decision-id ID` answers the displayed id and continues. The
optional id flag rejects stale submissions; without it, `submit` targets the
current pending request. `board` shows that pending
request's live board, while the saved engine state retains a safe transaction
boundary. Each human decision is preceded by current/upcoming card information
and changes since that seat's previous decision. `board` (or `b`) can inspect
the pending board without advancing play. Do not edit the save to answer a
request.

`save.json` is authoritative for inbox consumption, pending requests, accepted
choices within an interrupted action, and the committed decision log. The
frontend verifies and replays the earlier choices when the engine retries an
unfinished action. Bot preview copies cannot consume this human input.
`queue.json` is only an inbox, supporting a `{decision_id,response}` envelope
or legacy lists; unchanged inbox submissions cannot execute twice. Explicit
`{use_default:true}` is supported for reactions. Missing, stale, malformed,
or illegal responses pause rather than silently handing the choice to a bot.

Winter Campaign requests include `remaining_actions` (initially 2). Return a
normal Command plan, a standalone `{sa,sa_regions,details}` plan, or a combined
Command+SA plan (two actions); `{decline:true}` ends the capability's actions.
Ambush/Besiege must be paired with Battle. Cards 63/A63 permit other SAs
independently of their usual accompanying Commands and pay normal costs.
A single action resolves before the second decision is requested.
Provisional [PR-04](docs/provisional-rulings.md#pr-04) resolves German-owned
A63 during the Interlude before the scenario transition, then retains German
ownership with no later activations in the base-game half. It does not
transfer to the Arverni seat. Aedui/Belgic ownership continues to activate.
`engine.winter_campaign.validate_human_plan` checks both the action budget
and normal paid execution on a copy. Unaffordable, malformed, and ineffective
human plans leave the same decision pending; the terminal offers another plan
without spending an action. Preview validation never consumes live input or RNG.

`replay --output-dir DIR` reconstructs the saved session from its origin and
complete human decision log, verifies request context, and compares the final
board and RNG with the live save. It never overwrites the live game.
