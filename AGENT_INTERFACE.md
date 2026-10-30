# Agent interface — playing by judgment (human / LLM)

This engine can be driven by an external **agent** (a human or an LLM) that
plays a Faction by its own judgment instead of the built-in NP bot flowcharts.
The standard frontends dispatch bot seats to the built-in non-player logic;
a custom turn callback must dispatch those seats explicitly. See [current status](docs/current-status.md) for revision-specific
verification and adopted provisional rulings, and the [documentation
index](docs/README.md) for the other guides. The owner-adopted
[PR-01 through PR-09](docs/provisional-rulings.md) are subject to possible
later correction if an authoritative source is found.

Known contract gaps are catalogued in the
[human-choice audit](docs/reviews/human-choice-audit-2026-10-29.md), including
accepted illegal loss/Region selections, unrequested Event/seasonal choices
and malformed nested Supply responses. Current dry-run acceptance verifies
the implemented path; it is not complete printed-rule validation. The audit
changes no response schema or engine behavior.

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

Recruit entries accept an exact integer `count` for `place_auxilia`:

```json
{"recruit_plan":[{"region":"Provincia","action":"place_auxilia","count":1}]}
```

Use ordered Rally steps to preserve the player's choices, including named
Vercingetorix's Ally-or-Citadel plus Warbands in either order:

```json
{"rally_plan":{"steps":[
  {"region":"Arverni","action":"place_warbands","count":2},
  {"region":"Arverni","action":"place_ally","tribe":"Arverni"}
]}}
```

Rally troop steps accept `count`; it is the total Warbands for that step,
including compulsory additions not already applied in the Region. Ordinary
counts may be zero, with the Region's normal cost still charged. Fixed Event
placements and mandatory German Home placements impose a minimum. Omit
`count` to request the maximum; explicit null, Boolean, fractional, negative,
and out-of-range counts are invalid in a submitted plan. Static placements
do not accept `count`. Enlisted `warband_mix` is an alternative exact physical
allocation and cannot accompany `count`; static Rally steps may use it for
their compulsory Warband additions.

Do not mix `steps` with the legacy `citadels`/`allies`/`warbands` lists. Legacy
plans retain their existing order and maximum-placement defaults. A Recruit
Region may appear only once. Rally permits a second option only under its
printed exceptions; Vercingetorix pays the Region once. A Limited Command
still selects only one Region even when Rally has two steps there, and an
ordinary Limited Command cannot include a Special Activity. Event grants
can independently permit an accompanying activity under their own text.
The `command_parts` interface requires distinct Regions on each side of an
intervening SA. Base-game Arverni can instead use one ordered `rally_plan`
with `sa_timing: "during"` and `details.sa_after_rally_step: N`. This places
the accompanying Devastate or Entreat after the first `N` completed steps,
including between Vercingetorix's two options in one Region. Do not combine
this marker with `command_parts`. The second option is validated on the
resulting board, and the Region's cost and compulsory additions are counted
once. Ordinary Limited Commands still cannot add an SA.
Normally `N` is between 1 and one less than the step count. The final-step
boundary is also accepted when an `after_command_timing_actions` continuation
remains after the SA; it cannot represent an otherwise empty second half.

For Enlist's free German Rally, `details.enlist.count` selects the Warband
total. With a base-game `place: "ally"`, it instead selects the following
Warbands. Ariovistus's Ally option has only its compulsory Home addition
and does not accept `count`.

With agreed Diviciacus cooperation, a placement entry can also specify
`"placement_owners":{"Romans":0,"Aedui":1}` for one physical Aedui
Warband acting as Auxilia. The total must equal that entry's actual troop
placement, and the offered physical pools and consent still constrain it.
The terminal collects this allocation before computing later quantities.
Omit the field to retain the existing reactive `diviciacus_pieces` request.
This mapping is separate from Belgic Enlist's `warband_mix`.

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
Build permits both a Fort and the legal Ally operation in a Region. Scout
movement entries can name `physical_owners` when Diviciacus lends counters;
their counts must total that move and use only still-unmoved pieces.
Arrivals may participate in subsequent Scout Reveal, but may not Scout-move
again. A Scout target's legacy `hidden` field specifies the requested total
Warbands to Scout, including eligible Revealed Warbands.
For Trade under shaded River Commerce (39), `details.trade_region` names
one Region; `details.sa_details.trade_region` is also accepted. If both are
present they must agree. A non-string or a field attached to another Special
Ability is invalid; a named Region must be legal when Trade actually runs.
Omission defers the human choice until after the Supply declarations and
any preceding Command. The `trade_region` request carries `legal_regions`,
`roman_agreed`, and `choices` entries with `region`, `resources_gained`, and
`per_item`. Respond with `{"region": "<offered Region>"}`, `{"decline": true}`,
or the explicit `{"use_default": true}`. Zero-yield Regions remain legal
choices. A declined or zero-yield Trade retains the accompanying legal
Command and reports `declined_no_effect`; it does not silently choose a
higher-yield Region. Missing or invalid durable responses remain pending.

Optional `details.transfers` (`[{"to": faction, "amount": integer}]`, §1.5.2)
ride an action. The helpers below provide validation; the source plan builders
remain the detailed reference for each Command and Special Activity.

Boii (37) unshaded accepts `place_faction` (Romans or Aedui) and
`placements`: entries contain `region`, `piece_type`, and positive integer
`count`; an Ally entry also names its `tribe` and has count 1. The complete
plan must place the legal available portion of two Allies and two native
troops, within one Region of Aedui Control. Shaded `replacements` contains
one or two distinct `{"tribe": name}` entries within one Region of Arverni
Control when targets exist. Invalid complete plans are rejected before
mutation; pool shortages allow the partial execution required by §5.1.3.

The Province (21) unshaded accepts `province_choice: "auxilia"` or
`"resources"`; omission retains the Auxilia default. Both require only Roman
pieces in Provincia. Available pools and the Resource cap limit the actual
benefit. The shaded side asks the Arverni for its scoped Raid/Battle after
placement when applicable, independently of who played the Event.

Ambacti (16) unshaded accepts `target_region`, which must contain Roman
pieces. Shaded human choices arrive after the actual die roll in the
`ambacti_removal` request below. The legacy `removal_choice` and
`auxilia_removal_regions: [[region, count], ...]` parameters remain available
for direct callers without a decision agent; live human decisions take
precedence over those pre-roll parameters.

Chieftains' Council (47) accepts `region` and `target_factions` (at least
two distinct player Factions with pieces there). The Region itself must
contain at least two non-German Factions. In Ariovistus, game-run Arverni
can contribute to that condition but cannot be selected; Germans can be
selected and use the Arverni initiative position. The selected subset is
fixed before any beneficiary acts. Omitted selections prompt the executor
through `council_selection` in a durable session. A raw caller without an
agent, or an explicit default, uses a seeded Region choice and all player
Factions there. This compatibility default does not change the printed
non-player instruction to decline selecting the Council Event.

Winter Uprising (A66) requires a legal `region` for its marker. Missing,
malformed or out-of-scenario targets reject before any delayed trigger is
recorded. Human placement does not require own pieces; non-player Belgae
and Germans use their respective printed geographic restrictions.

Parley (A23) accepts `meeting_region` and `who_moves` (`"caesar"`,
`"ariovistus"`, or `"both"`). Use `cards.parley.meeting_choices(state)`
for legal pairs. Adjacent named Leaders can meet in either one's Region;
Leaders two Regions apart must both move to a common adjacent Region.
An omitted meeting is rejected when a legal meeting exists. When no meeting
is possible, the independent next-card ineligibility still applies.

Human plans may set `sa_timing` to `"before"` or `"after"` (default).
This controls resolution, independently of the timing required by the bot
flowcharts. Ambush and Besiege are Battle modifiers and resolve within the
Battle. For Rally, Recruit, Raid, or Seize, `sa_timing: "during"` accepts
`details.command_parts: [first_plan, second_plan]`: two plans for the same
Command, selecting different Regions, with the accompanying Special
Activity between them. March and Battle currently support before/after
timing; their Command-wide movement and Battle bookkeeping is not split.

### Choices between operations

The outer Sequence-of-Play human Command or Event owns voluntary removal
permission, including its accompanying SA and nested grants. A guest faction
executing a free action does not acquire that permission. Passing, another
faction's turn, and ordinary Winter do not authorize voluntary removal.
Borrowing changes which counters a force can use, not their physical owner.
Unlocked boxed Vercingetorix has a separate Arverni entry opportunity during
other factions' actions and Winter as well as during Arverni actions.

Plans may author an ordered `timing_actions` list before a particular
operation. Each entry has exactly `kind` and `response`:

```json
{"timing_actions":[
  {"kind":"voluntary_removal","response":{"operations":[
    {"action":"remove","region":"Arverni","piece_type":"Warband",
     "piece_state":"Hidden","count":1}
  ]}},
  {"kind":"spring_leader","response":{"region":"Carnutes"}}
]}
```

This is a shape example for an eligible Arverni actor; current legality still
applies. Authored Spring entry must name a Region or use `{"defer":true}`;
it cannot delegate a random/default placement during preview. Only the
Arverni may author their Leader's entry. Removal instructions cannot supply
their own permission, owner, or cohort definitions.

| Plan location | When its list runs |
|---|---|
| `details.timing_actions` | At Command/Event start |
| An operation entry's `timing_actions` | Before that Recruit/Rally step, Raid flip, Scout move/Reveal, or other supported operation |
| `details.after_command_timing_actions` | After a successful Command, before an after-Command SA |
| `details.sa_details.timing_actions` | Before the SA |
| `details.sa_details.after_sa_timing_actions` | At SA completion |
| `details.stage_timing_actions["seize_region:0"]` | Before the first Seize Region; scalar stages use `stage:index` keys |
| `details.sa_details.stage_timing_actions["build_fort:0"]` | Before the first scalar Build Fort entry |
| `details.scout_plan.movement_timing_actions` | After Scout movements, before their moved-piece ledger closes |
| `details.raid_timing_actions[region]` | After that Region's Raid flips, before intrinsic Intimidate uses surviving raiders |
| `details.event_params.stage_timing_actions["A37.moves:0"]` | Before an indexed Event step; scalar Event stages use the step name without `:index` |

The CLI applies these choices on detached planning boards before computing
Available pools and legal menus, then the engine revalidates them during
execution. A skipped menu option carries its choices forward or stores them
in the appropriate completion list; it does not apply them to the live game
while planning. Timing requests occur between complete rules operations,
not inside an indivisible replacement or die-result application.
For ordered Event lists, `step:len(entries)` is their completion boundary.
Typed entries can carry `timing_actions` directly; that takes precedence over
the corresponding indexed stage list. Use the active card's supported step
names rather than inventing stage keys.

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

PR-07 makes one exception to ordinary rejected-attempt rollback: a genuine
non-player Aedui die refusal must remain fixed when human Rome rechooses.
The engine retains the refusal and its RNG receipt, while rolling back the
failed Command. Durable sessions retain that rejected attempt in history,
give the corrected decision a new ID, and re-execute and verify the rejection
during replay. Player-authored plans cannot supply their own permission or
RNG receipt. Other invalid plans retain ordinary rollback behavior.

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

Raw callbacks opt into the additional between-operation requests by setting
`agent.supports_action_windows = True` (or that attribute on a bound method's
owner). Legacy callbacks remain unchanged unless opted in. The terminal and
`SeatSession` enable the protocol. An authored `timing_actions` plan does not
need this flag: its explicit choices still execute without live prompting.
For optional mid-action `spring_leader` requests carrying `window`, raw
`None` defers entry; for `voluntary_removal`, it removes nothing. Explicit
`{"use_default":true}` places Vercingetorix using the established priorities,
so it is different from deferral. Durable sessions require an actual reply.

The constants `RETREAT`, `LOSS_ORDER`, `AGREEMENT`, and `HARASSMENT_LOSS`
come from `fs_bot.engine.agent`; other kinds below are literal strings.
Requests can include additional context. Copy offered values rather than
inventing pieces, regions, owners, or internal grant flags.

| `request["kind"]` | request fields | response |
|---|---|---|
| `RETREAT` | `region, attacker, defender, is_ambush, legal_regions` | `{"retreat": bool, "region": dest_or_None}` (region must be in `legal_regions`) |
| `LOSS_ORDER` | `region, faction, num_losses, is_retreat, is_ambush, pieces` | an ordered subset of the supplied entries; borrowed forces may add `physical_owner`, and Elite counters may carry a fourth tag; copy entries intact; hard pieces still roll |
| `HARASSMENT_LOSS` | `region, harasser, loss_index, num_losses, phase, options`; March carries `departing_pieces`, Seize carries `pieces` | `{"choice": option}` from `options`; see the phases below |
| `march_cohort` | `phase, region, piece_type, count, available`; may include `acting_faction, physical_owner` | `{"counts": {visibility: count}}`, totaling exactly the requested `count` |
| `diviciacus_pieces` | `phase` (`placement`, `formation`, `dropoff`, `loss`), `region, piece_type, count, available` by physical owner | `{"counts": {owner: count}}`, totaling `count` without exceeding `available` |
| `force_cohort` | `region, piece_type, piece_state, operation, count, available` with `selected`/`other` counts; optional descriptive labels | `{"counts":{"selected":n,"other":m}}`, totaling `count`, or explicit default |
| `voluntary_removal` | `faction, options, window`; may include engine-owned `cohorts` | `{"operations":[...]}`, `{"done":true}`, or explicit default (no removals) |
| `battle_elite` | `faction, region, count, available` by visibility, `window` | `{"counts":{"Hidden":n,"Revealed":m,"Scouted":k}}` totaling the exact offered count, or explicit default |
| `AGREEMENT` | `request_type, requesting_faction, context` | `bool` (agree?) — `request_type` in {`retreat_into_control`, `supply_line`, ...} |
| `supply_refusal` | `action_type, action, allowed_commands, allowed_special_abilities, limited, context`; grants may add `allowed_regions, max_regions` | `{"continue":true}` or `{"replacement": action}`; see scope below |
| `trade_region` | `faction, legal_regions, roman_agreed, choices` with each Region's Resource gain and breakdown | `{"region":name}`, `{"decline":true}`, or `{"use_default":true}` |
| `free_action` | `request_type` plus the Event's scope; ordinary grants may carry `allowed_commands, allowed_regions, max_regions, with_sa, free, allow_decline`; standalone SAs use `allowed_sas` | ordinary action or subtype-specific response below; decline only when permitted |
| `kinship` | A65; `attackers, regions_by_faction` | `{"faction": attacker, "regions": [...]}`, decline, or explicit default |
| `ambacti_removal` | 16; `roll, removal_counts, targets` | `{"removal_choice":"roll"\|"three", "removals":[{"region":name,"piece_state":visibility,"count":integer}, ...]}` or explicit default |
| `council_selection` | 47; `regions` maps qualifying Regions to player Factions present, `minimum_factions` | `{"region":name,"target_factions":[...]}` or explicit default |
| `council_choice` | 47; `region, target_factions, private_cards` and the one-Region, free, no-SA Command scope | `{"choice":"eligible"}`, a complete ordinary Command plan, `{"decline":true}`, or explicit default |
| `winter_uprising_timing` | A66; full `card_text`, `region, holder, forced` | `{"activate":true}` or `{"activate":false}`, or explicit default |
| `winter_uprising_placement` | A66; full `card_text`, `region, holder, forced, beneficiary, regions, tribes, allies, warbands` | `{"allies":[tribe,...],"warbands":[{"region":name,"count":integer},...]}` or explicit default |
| `quarters_plan` | `faction, errors` | relocation/payment object described below, or explicit default |
| `quarters_provincia` | `faction, original_moves, legal_moves, errors` | `{"moves":[[piece,origin,"Provincia",count],...]}`, `{"decline":true}`, or explicit default |
| `quarters_payment` | `faction, reason`, optional `errors` | `{"payments":{...}}` using the existing Roman quartering allocation shape, or explicit default |
| `spring_leader` | `faction, leader, source, reason, legal_regions, can_defer`; mid-action offers add `window`, scenario ties may set `equal_priority` | `{"region":name}`, `{"defer":true}` only when offered, or explicit default |
| `winter_campaign` | `card_id, remaining_actions`, optional `errors` | one paid action, combined Command+SA, or decline; see the Winter section below |
| `frumentum_amount` | A53; `available_resources` (Aedui) | `{"amount": integer}`, `{"decline":true}` (zero), or explicit default |
| `frumentum_action` | A53; `remaining_actions, remaining_resources, reserved_roman_resources` | one Recruit/March plan or standalone Build/Scout plan, `{"skip": action_name}`, finish with `{"decline":true}`, or explicit default |
| `raid_intimidate` | A3.4.3; `region, raiders, max_removals, targets` | `{"targets":[...]}`, marker only `{"targets":[]}`, `{"decline":true}`, or `{"use_default":true}` |

The file-based frontend accepts `{"use_default":true}` for a non-turn
request only as an explicit decision. An omitted or invalid response remains
pending. A normal turn still requires a legal `action` and its plan.
Free-action defaults and declines must be single-field objects containing
Boolean `true`; numeric `1`, strings and mixed sentinel/action objects are
invalid.

For `voluntary_removal`, copy an offered option's identifying fields and add
a positive `count` no greater than `max_count`. Operations require `action`
(`remove` or `downgrade`), `region`, `piece_type`, and `count`, plus only the
applicable `piece_state`, `tribe`, `loan_kind`, and `cohort`. Use
`engine.voluntary_removal.operation(option, count)` to construct them; labels,
maximum counts and replacement descriptions are request metadata. Citadel
downgrades use the same City; without an Available Ally the Citadel is simply
removed. Legions return to their track, Diviciacus goes out of play, and the
permanent Provincia Fort is excluded.

`cohort` identifies a specific offered subset, such as moving March pieces,
already moved Scout pieces, actual raiders, or an Event-selected force.
Omitting it does not select that subset. `loan_kind` can identify overlapping
loan memberships and must be copied exactly. Neither field transfers
ownership or expands the player's removal permission. New requests expose
remaining physical counters after every completed change.

`supply_refusal` follows an actual non-player Aedui roll of 5–6 for human
Rome. `action_type` identifies whether the current Command or only the
current Special Ability can be reconsidered. A replacement must respect
the offered Command/SA lists and any Event Region limits. Changing Build
does not undo an earlier March or other completed action. The answer is
fixed under PR-07; continuing or replacing the plan does not roll again.
Unknown permission remains conditional in pure previews, while an already
recorded refusal is reflected in them. This request does not replace human
Aedui permission choices or Winter Quarters' own procedure.

When `command_only` is true, the replacement supplies only the remaining
Command, with no new SA. `accompanying_sa` and `completed_sa_result` preserve
constraints from the selected or completed SA. An interrupted continuation
may set `continuation` and `excluded_regions`; it cannot change the already
started Command type or reuse completed Regions. If nothing has resolved,
the offered replacement can cover the untouched plan instead. Event-owned
`grant` and `frumentum` context constrain replacements to their existing
action lists, timing and funding. These are engine-supplied request fields,
not permissions that the responding player can add to a plan.

Within A53, a refused Recruit may be skipped with
`{"replacement":{"skip":"Recruit"}}`. A standalone SA replacement with
`sa: "No SA"`, when offered, skips that SA without spending its allocation.
Neither response issues fresh funding, refunds prior spending, nor restores
an action already used under the Event.

Spring Successors must enter a Region from `legal_regions`: a playable Home
Region with the faction's printed symbol, or a Region containing its pieces.
They cannot defer. A single mandatory destination resolves without asking.
The Gallic War Interlude uses the same request for choices among the printed
highest-priority destinations for Ambiorix or Caesar.

For Vercingetorix in the Spring box, `can_defer` is true. His arrival becomes
available beginning the first Pax Gallica Spring, including the first Winter
after the Gallic War Interlude; the Interlude's own Spring does not unlock it.
After deferral, the game offers placement at later complete-operation
boundaries inside Commands, Events and Winter, including opponents' actions,
without spending a Command or changing Eligibility. A mid-action request
includes `window` with its `stage`, phase and relevant Region/step context.
An explicit default is preserved in the transcript rather than normalized
to the `None` that means defer at these new windows.
All placement answers support pending input, save/resume and exact replay.

Diviciacus uses `AGREEMENT` with `request_type: "diviciacus"` for the
other Faction's consent. Its context identifies the phase, selected Regions,
Command/Special Activity and targets. A human defender first receives
`request_type: "diviciacus_defense"` to choose whether to request cooperation.
Fixed Event Battles use `request_type: "diviciacus_command"` for the
acting human's opt-in before requesting the lender's agreement.
Both replies are booleans. Loss-order entries retain physical owners even
when borrowed pieces fight as the other type; copy the offered entries.

Non-player Recruit forecasts can produce `AGREEMENT` requests with
`request_type: "supply_line"` before the planned Build/Scout and Recruit
take effect. Answer with a boolean. The context identifies the Region and
may include `proposed_action`. A refusal causes the bot to replan before
effects; accepted permissions apply through the actual Command/Event.
A replacement ordinary Command obtains its own required permissions.
Missing or invalid human replies remain pending under the session contract.
Event-granted Commands retain their own Region limits and SA allowances.

### Harassment and physical March pieces

A `HARASSMENT_LOSS` request's `phase` determines what is being selected:

| Phase | Choice |
|---|---|
| `absorb` | An offered soft piece type or `"roll"` |
| `remove` | A hard piece type after a failed saving roll; the request includes `roll` |
| `piece_state` | The offered visibility of the soft casualty |
| `physical_owner` | Which offered physical owner supplies the moving-group casualty, such as Enlisted German versus Belgic Warbands |
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

`force_cohort` similarly separates Event-selected counters from other pieces,
or the physical colours in an Enlist drop-off. Use the request's labels and
offered counts; the `selected` label is not always an Event force.
Shaded Vercingetorix's Elite uses `battle_elite` to select actual Warbands
for that Battle. Subsequent loss-order entries can identify a selected piece
as `["Warband", visibility, null, "elite"]`; other Warbands remain separate.

### Scoped Event grants

Seize's successful Arverni and Belgae Rally checks issue separate
`free_action` requests with `request_type: "event_rally"`, `source: "seize"`,
`source_region`, `tribe`, and the actual `roll`. They permit free Rally in the
offered adjacent non-Devastated Regions, with no SA. Each successful grant
resolves before the next die or Forage; return an ordinary explicit Rally
plan, decline, or explicit default. In Ariovistus, the Arverni result uses
their game-run procedure rather than a player request.

Shaded Surus (51) gives the Event executor an `event_command` request with
`acting_faction: "Germans"`. Choose March, Raid, or Battle using only the newly
placed surviving German Warbands, from the offered Region. The grant is free,
selects one Region, allows no SA and cannot be declined when an action is
possible. Existing residents do not join it. Base-game German Battle keeps
its intrinsic Ambush requirements. `acting_faction` does not transfer
voluntary-removal ownership to the chooser or the Germans.

Winter Uprising's timing request belongs to its human holder. Deferring
keeps the card, marker and delayed effect. Non-player holders activate at
the earliest window; the Gallic War Interlude forces activation and skips
the optional timing request. Belgae and Germans choose their own granted
placements; the holder chooses Arverni placements before the automatic
Arverni Phase. `allies` and `warbands` in the request are exact required
totals after Available-pool and destination limits. Choose distinct offered
Tribes and positive integer Warband allocations in offered Regions.

The follow-on Belgae/German free Command has `allow_decline: false`; it
retains the granted Special Activity and its ordinary ordering choices.
Pending placement or Command input rolls back the activation until the
transaction can finish. New saves retain the actual holder. If an older
save contains no recoverable holder, the engine reports
`legacy_holder_unknown: true` and preserves its earlier automatic timing;
it does not invent a human owner. A known beneficiary still receives its
placement and Command decisions.

Council's `private_cards` contains only the next two face-down cards,
excluding the public upcoming card, or fewer when the deck is short. Each
entry includes `card_id`, `title`, full available `text`, scenario-mapped
`faction_order` and `np_symbols`, `is_winter`, and `has_carnyx_trigger`. Each
selected beneficiary receives its own request in printed initiative order.
Peek data is absent from public board snapshots, change reports and Event
results. Full saves, request journals and raw callbacks are trusted
interfaces that already contain the deck; they are not access-control
boundaries. Do not publish a participant's private request to other seats.

The Council Command is free, selects at most one Region, permits Frost
March, and has no Special Activity. Declining or executing an ineffective
Command does not automatically grant Eligible. Non-player beneficiaries
randomly choose Command or Eligible, then use their real limited flowchart
when Command is selected. Choosing Eligible survives card cleanup.

Ambacti's `removal_counts` gives the required total for each alternative,
limited by the Auxilia on the map. Each `targets` entry provides a Region,
physical `piece_state`, and `available` count. Submit exactly the selected
total without exceeding an entry's availability. There is no decline option.
An invalid or missing durable-session response leaves the same decision
pending; saving and resuming does not reroll the die. Ordinary board output
and the current/upcoming-card display remain available before the choice.

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

If an intervening Leader entry changes Supply after adjacent relocations,
`quarters_provincia` reopens only the remaining Provincia moves. Completed
adjacent moves stay completed. `legal_moves` entries use their final count as
the maximum offered; explicit default retains only still-legal original
moves, while decline chooses none. A changed relocation outcome then requests
`quarters_payment` for the pieces actually left outside Provincia, before
payment or loss rolls. Explicit default uses standard payments.

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

- Timing is offered at complete rules-operation boundaries. Some legacy
  scalar-list or dynamically constructed Event menus collect these choices
  only during live execution; typed placement entries and A37 additionally
  expose them while planning. The source-derived completeness audit remains
  open; this list is not exhaustive.
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
For new timing transactions, inbox receipts include the accepted response
ancestry: a corrected plan may legitimately reuse a decision ID and the same
answer without being mistaken for an already consumed earlier attempt.

Replay retains older accepted and pending transcripts that predate these
optional windows. Newly added prompts are skipped only while verifying that
old recorded transaction; no synthetic choices are appended to its history.
Fresh requests require explicit answers, including after an old pending
decision has been answered. Transient engine timing frames are not game
facts, but actual board changes, cohort options, and the request's `window`
context remain checked. New timing decisions carry version metadata so they
cannot silently use the old no-prompt path.
This compatibility covers inserted timing decisions, not changed outcomes
from substantive rule corrections. A historical transcript affected by such
a correction, including previously omitted Seize Rally effects, can fail
verified replay; the frontend reports the mismatch rather than treating a
different board as equivalent.

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
