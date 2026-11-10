# Agent interface — playing by judgment (human / LLM)

This engine can be driven by an external **agent** (a human or an LLM) that
plays a Faction by its own judgment instead of the built-in NP bot flowcharts.
The standard frontends dispatch bot seats to the built-in non-player logic;
a custom turn callback must dispatch those seats explicitly. See [current status](docs/current-status.md) for revision-specific
verification and adopted provisional rulings, and the [documentation
index](docs/README.md) for the other guides. The owner-adopted
[PR-01 through PR-12](docs/provisional-rulings.md) are subject to possible
later correction if an authoritative source is found.

Known contract gaps are catalogued in the
[human-choice audit](docs/reviews/human-choice-audit-2026-10-29.md). The
[first small repair batch](docs/reviews/cheap-fixes-2026-10-29.md) closes its
casualty-tier, duplicate Seize/Entreat, malformed Supply, forbidden transfer
and sole-human-Belgae setup findings. Unrequested Event/seasonal choices and
other contract gaps remain. Current dry-run acceptance verifies the implemented
path; it is not complete printed-rule validation.

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

## Optional setup

`setup_scenario` accepts boolean keyword arguments `sudden_frost`,
`even_initiative`, and `short_great_revolt`, all defaulting to `False`.
Non-booleans and scenario-invalid combinations raise `ValueError` before
setup. Both terminal startup and `llm_seat init` expose the matching flags
`--sudden-frost`, `--even-initiative`, and `--short-great-revolt`.

Sudden Frost requires all players' agreement and switches a showing Winter
with its preceding Event before any Event action or carnyx activation. The
unplayed Event remains atop the deck for the next Year. Even Initiative
balances the pool before final selection and is unavailable in Pax Gallica?.
The 30-Event/two-Winter short deck is Great Revolt only. See
[Playing](PLAYING.md) for precise deck composition and the explicit Gallic War
Interlude deck replacement. Enabled selections are saved in state and origin
snapshots. Metadata records all three booleans. Missing legacy fields mean
`False`. Default setup preserves the previous RNG consumption and board hash.

### Player ownership

Pass `faction_owners` to `setup_scenario` as a mapping from playable
Faction names to stable player ID strings. Assign the same ID to both members
of a printed Spare Factions pair. The remaining playable Factions are
Non-players. Existing `human_factions` setups without an ownership mapping
retain their legacy behavior. The board stores current assignments in
`faction_owners`. Frontend metadata saves `setup_faction_owners` for replay.
At the Gallic War Interlude the German player ID follows the Arverni role.

In a paired game, a Winter victory result adds `winner_player`,
`winner_factions`, and `player_rankings`. The player ID is `None` for a
Non-player winner. Each ranking row has `player` (the player ID), `factions`,
`faction` (the Faction supplying the margin), `margin`, `passed`, and
`non_player`.
The existing `winner` field contains the winning side's representative
Faction. The result uses the pair's lower margin unless it is the Arverni
and Belgae pair in The Great Revolt, which uses the higher margin.

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

Human turn responses accept `action` and, for a non-Pass action,
`player_action`. Pass uses `action` alone. The engine supplies eligibility
exceptions and accepted-decision metadata. Additional top-level fields,
including `free_action` and `assistant_response`, leave the submitted turn
pending for correction. The coordinator constructs its own execution record
from the chosen action and plan.

A Command-only or Limited Command response carries a Command with no Special
Ability. Use `command_sa` when choosing one. If the Special Ability is declined
or produces no effect, the engine records Command only. An `event` response
carries the current Event. Omit `details.card_id` to use the current card or
give its exact ID. The saved edition determines the text of revised numeric
cards. Any actions the Event grants resolve through its own requests.

`execute_decision` runs `player_action` through the same rules engine used by
the bots. Inspect the execution result and any reported sub-action errors;
a partial execution differs from a wholly refused action. A `player_action` is:

```text
{"command": "Battle"|"March"|"Rally"|"Raid"|"Recruit"|"Seize"|"Event",
 "regions": [...], "sa": "No SA"|<Special Ability>, "sa_regions": [...],
 "details": { ...command-specific plan... }}
```

Ordinary Battle plans choose their Regions, defenders, and accompanying
Special Ability. Event resolution supplies printed combat modifiers.
`details.no_retreat`, `force_retreat`, `allied_factions`, and
`warband_full_loss` are reserved and rejected in ordinary Battle plans.
Choices that an Event expressly grants, such as A28's permitted lenders,
use that Event's own request and parameters.

Entreat names the physical Allied Tribe disc being replaced. Validation
checks that identity before accepting an authored turn and again at removal.
The selected disc and its Tribe allegiance change together. A City Citadel
retains its allegiance when Entreat takes another Tribe's disc in the Region.
Available replacement pieces and stacking determine whether Arverni place
their counterpart after taking the selected disc (§4.3.1).

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
intervening SA. Supply exactly two portions of the same Command and use
`sa_timing: "during"`. Base-game Arverni can instead use one ordered `rally_plan`
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
recruit_plan, March origins/destinations, exact disperse_tribes, and Event
`card_id`/`text_preference`/`event_params`) are exactly what
`fs_bot/cli/human_plan.py` builds for the interactive CLI — use it as the
reference. March plans additionally accept exact per-origin `routes`
({origin: [region, ...]}), per-origin subset `groups`
({origin: {piece_type: count, "Leader": bool}}), and §3.3.2
`extra_groups` ([{origin, route, group}] — further groups from the
post-departure remainder of an origin).

Each extra group uses an origin already selected for the March. A legacy
`explicit_moves` list supplies `origin` and `path` for each group. The one-origin
Limited Command rule and the Britannia Special Ability restriction apply to
both formats and to routes produced by the destination planner.

For an origin that stays in place, supply an explicit empty route in
`details.routes` (or `details.march_plan.routes`):

```json
{"command":"March","sa":"No SA","details":{"origins":["Morini"],"destinations":[],"routes":{"Morini":[]}}}
```

This selects and pays for Morini, runs its normal whole-origin visibility
procedure, and moves no pieces. No moving-group allocation or Harassment
choice is needed. The result has `executed: true`, `stayed_origins: ["Morini"]`
and an empty `marches` list. Mixed moving/staying origins use their selected
order and share the origin Resource budget. An extra moving group from the
same origin does not add cost or repeat its visibility flip. Missing routes
retain their legacy destination-planning behavior; they do not imply a stay.
Frost and Limited Command restrictions still apply. Event-required destinations
reject an empty route; unrestricted free March may stay at no Resource cost.
Staying in Britannia does not itself enter or leave it for the SA prohibition.

The Roman Build and Scout
Special Abilities accept player plans (`build_plan`
{forts, subdue, allies, region_order} and `scout_plan` {auxilia_moves,
scout_targets}); without one, the bots' flowchart plans run instead.
Build permits both a Fort and the legal Ally operation in a Region. Supply
`build_plan.region_order` as an array naming exactly the Regions with operations,
each once. The executor completes each Region in that order: its optional Fort,
then either one Subdue or one Ally placement. For example:

```json
{"build_plan":{"forts":["Aedui"],"allies":[{"region":"Sequani","tribe":"Helvetii"}],"region_order":["Sequani","Aedui"]}}
```

This spends on the Sequani Ally before the Aedui Fort. Entries retain their
category indices for `build_fort:N`, `build_subdue:N`, and `build_ally:N` timing
keys; those windows execute in Region order, not numeric/category order.
Top-level `details.build_plan` takes precedence over a nested non-null
`details.sa_details.build_plan`. Duplicate/missing/extra Region names and more
than one Fort or Tribe operation per Region are rejected before an accompanying
human Command. Card 12 shaded rejects an ordered plan selecting multiple Regions.
Both terminal collectors emit `region_order`. Omission retains the older
Fort/Subdue/Ally passes for existing controllers and the §8.8.1 non-player
procedure; controllers should add the field to express human Region order.
An empty ordered plan is `{ "region_order": [] }`.

Scout movement entries can name `physical_owners` when Diviciacus lends
counters; their counts must total that move and use only still-unmoved pieces.
Arrivals may participate in subsequent Scout Reveal. The grouped Reveal row
allocates one `auxilia_count` to an exact `targets` list in the same Region:

```json
{"scout_plan":{"auxilia_moves":[],"scout_targets":[{"region":"Morini","auxilia_count":1,"targets":[{"faction":"Belgae","piece_state":"Hidden","count":1},{"faction":"Arverni","piece_state":"Revealed","count":1}]}]}}
```

That one Hidden Auxilia Scouts both selected Warbands. A row may target up to
two Warbands per Auxilia, across factions and Hidden/Revealed/Scouted cohorts;
an already-Scouted target needs no additional marker. Counts must fit the
actual available Auxilia and target cohorts, including repeated targets.
A grouped row can name `physical_owners` to specify Roman and agreed Aedui
counter counts; omission uses the existing physical-owner request when a
choice is needed. An older transcript that used automatic allocation for mixed
loans may now need an owner response. Any `timing_actions` on that row run before the whole
allocation. Shaded Titus Labienus limits Reveal to one Region. Invalid grouped
plans restore their Scout movements and earlier Reveal steps; previews use
copies and never consume live answers or RNG. Terminal planning and durable
validation use the same grouped shape.

Legacy `region`/`enemy`/`hidden` rows still use their old per-row count and
Hidden-before-Revealed selection, including eligible Revealed Warbands. Bots
continue to emit those rows. Use grouped rows to share Auxilia across factions
or select exact visibility.
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
author the executor's own opening gifts. Other donors choose their own gifts
through [live Resource transfer requests](#sequence-of-play-resource-transfers).
The source plan builders remain the detailed reference for each Command and
Special Activity.
Durable turns reject ineligible transfer parties and plans that exceed the
shared-player allowance. Game-run Germans in original scenarios and
game-run Arverni in Ariovistus cannot give or receive Resources. Current
scenario rules apply after Interlude. The raw executor reports a refused
gift and continues the accompanying Command.

The following repaired Event sides use complete, side-specific
`details.event_params` plans. Fields describe shapes, not permission to
select targets absent from the current board. Unknown fields and malformed
counts are rejected. Existing entry `timing_actions` and
`stage_timing_actions` remain supported at the named operation boundaries.

| Card/side | Parameters and limits |
|---|---|
| 28, either side | Ordered `ally_placements: [{tribe, faction}]` at Subdued Cities outside Roman Control, followed by `citadel_upgrades: [city]` using City names such as `"Bibracte"`. Each upgrade uses an Available Citadel of the Ally's faction. Both steps may be empty. |
| 40 unshaded | `placements: [{region, piece_type, count?, faction?, tribe?}]`; one piece type per Region adjacent to Cisalpina, totaling at most 3 Warbands, 2 Auxilia or 1 Ally there. Count defaults to 1, faction to executor; Ally needs its Tribe. Empty placement still grants Resources. |
| 41, either side | `ally_placements: [{tribe, region?, faction?, count?}]` (at most 2, own faction, count 1); optional `citadel_upgrade_tribe` and `fort_region`. The executor must have an Ally or Citadel at Avaricum; Control alone is insufficient. Fort placement is Roman-only. All choices are within one Region of Bituriges. |
| 42 unshaded | `removals: [{tribe, faction?, region?, count?}]`; count 1, with optional `mode: "controlled"` or `"adjacent"`. Choose at most 4 under Roman Control OR at most 2 adjacent to it; omitted mode is inferred only when valid. Zero is permitted. |
| 42 shaded | Same exact removal entries, no mode: 1–3 Roman/Aedui Allies in Supply Lines as if both agreed; zero only when no eligible targets exist. |
| 51 unshaded | Required `region` within one of Treveri; `replacements: [{from_faction, piece_state?, count?, region?}]`, totaling four original Warbands as possible in that Region. An explicitly chosen empty Region remains legal and still grants the Aedui Command. |
| 57 shaded | `removal: {type, tribe}` selects a Britannia Ally (`"ally"`) or either face of a Dispersed marker (`"dispersed"`). Use `ally_tribe` and `ally_faction` for the Gallic Ally placement, then `warband_faction` and `warband_count` for up to four Available Gallic Warbands. The terminal computes each menu after the preceding effects and records timing actions under `57.removal`, `57.ally` and `57.warbands`. |
| 65 shaded | Ordered `replacements: [{region, piece_type, piece_state or tribe, replace}]`; exactly five German Warbands and one German Ally as possible in executor-Controlled Regions. `replace` is a required Boolean; false selects removal only. Warbands require exact visibility; Allies exact Tribe. |
| 68 unshaded | `replacements: [{tribe}]` selects one or two distinct eligible non-Roman Allies within one of Remi. Supply an empty list only when the effect has no eligible target. |
| A29 unshaded | `faction` selects Romans, Arverni, Aedui or Belgae. That owner supplies `placements: [{region, piece_type, faction?, count?, tribe?}]` among Settlement Regions: up to 2 Allies and five own Warbands or three Auxilia as possible. Other executors select only the beneficiary. |
| A30 unshaded | `region`: one Region within one of Sequani; removes all Arverni there. |
| A30 shaded | `placements: [{region, piece_type, count?, tribe?}]` places nine Arverni Warbands, Allies, or Citadels as possible after clearing Allied pieces from Aedui and Sequani. Name the Tribe for an Ally. The Region identifies the City for a Citadel. |
| A36 shaded | German-owned `placements: [{region, piece_type, count?}]` and `ally_removals: [{tribe}]`; two Settlements, four Warbands and two Ally removals as possible within one of Sugambri. A foreign executor supplies `{}` and awaits the German request. |
| A43 unshaded | `replacements: [{region, from_type, to_faction, tribe or piece_state}]`; two Arverni Allies and two original Arverni Warbands as possible within one of Bibracte. Counterparts belong to Romans or Aedui. |
| A45 unshaded | `placements: [{tribe, faction}]`; up to three non-German Allies in legal Subdued Celtica Tribes within one of an Intimidated marker. |
| A51 shaded | `removals: [{faction, piece_type, piece_state? or tribe?}]` selects up to five eligible Roman or Aedui pieces in Atrebates. Name the Tribe for each Ally. A legacy entry without a Tribe requires one unique match. An empty list is legal. |
| A56 shaded | `warband_placements: [{region, count?}]` and `ally_placements: [{tribe}]` place four Warbands and two Belgic Allies as possible in Belgica before the Resource gain. An Ally can replace another faction's Ally disc. |
| A65 shaded | `from_faction` selects Belgae or Germans. `warband_replacements: [{region, piece_state?}]` and `ally_replacements: [{tribe}]` replace four Warbands and two Allies as possible. A missing counterpart still leaves the source removed. |

Abatis (A64) accepts a Region with a Warband of any visibility owned by
the executor, including Scouted.

Unshaded Alaudae uses `target_region` under Roman Control. Unshaded
Numidians uses `target_region` in the original edition and `region` in
the revised edition, with the Roman Leader's Region or a playable adjacent
Region as the target. Shaded Sacking uses `target_region` with a Roman Legion
and the executor's Citadel. These checks run before placement,
removal, or eligibility changes.

Shaded Lucterius and Flight of Ambiorix accept `target_region` when the
respective Successor is on the map or the Leader is Available. Flight
limits the destination to Germania, Morini, Nervii, Treveri, or Sequani.
Assembly of Gaul unshaded counts each Gallic entry in `target_factions`
once. Shaded A65 accepts Belgae or Germans in `from_faction` and uses the
other faction as the replacement owner.

Integer card 65 remains distinct from expansion A65. Its old
`warband_replacements`/`ally_replacement_tribe` fields are not silently
converted into default physical choices; affected transcripts need new
exact input. Romans replace German Warbands with Auxilia; Gallic executors
use their own Warbands. Incoming pieces use ordinary placement visibility.

Printed replacement instructions follow §5.1.1: unavailable or stacking-invalid
counterparts still remove the selected source. This includes Avaricum's
Ally-to-Citadel conversion when no own Citadel can enter. Mere placement
shortfalls do not create pieces. Fixed counts are required as possible;
up-to selections retain their smaller legal choices. Surus replacements use
original counters, so a newly placed Aedui Warband cannot become another
source in the same Event.

A29 and A36 may issue `kind: "free_action"`,
`request_type: "expansion_event_choices"`, carrying `card_id`,
`acting_faction`, `regions` and `allow_decline: false`. The named owner
responds with the corresponding parameter object above or explicit
`{"use_default":true}`; it cannot change the owner or decline required
effects. Game-run Arverni resolve automatically. Missing/invalid durable
responses retain the pending ID and accepted history. Current card/change
display and `board`/`b` remain available. Voluntary timing actions still
belong to the original Event executor, independently of the placement owner.

Named-owner optional effects on 2/18/23 unshaded, 26 shaded and A18 unshaded
use `kind: "free_action"`, `request_type: "named_event_effect"`, `card_id`,
`acting_faction`, `allow_decline: true` and `validate_default_response: true`.
The initial terminal Event plan leaves these decisions for the live owner
request. A same-owner typed Event may supply its own parameters directly;
a foreign executor cannot supply that owner's targets. Empty initial parameters
request the decision; missing durable input never means an automatic default.

| Card/side | Named owner | Accepted owner response |
|---|---|---|
| 2 unshaded | Romans | `legions_from_track` and `legions_from_fallen`: nonnegative integer counts, totaling two as far as possible. The Senate must be able to shift or flip. Available source choices may change after a legal timing action. |
| 18/A18 unshaded | Romans | `target_region` from `target_regions`. A18 also accepts its previous `region` alias; if both appear they must agree. A18 excludes named Ariovistus, but includes a Successor in its complete German removal. |
| 23 unshaded | Romans | `target_city` from `target_cities`; Roman Control is required, not Roman ownership of the City. Existing Dispersed/Razed status is not a blanket human prohibition. |
| 26 shaded | Arverni | `ally_removals` and `ally_placements`: ordered lists of exact Tribe names in Arverni Region. Remove only actual Allies, of any faction; place only own Allies at legal Subdued Tribes. Empty lists still proceed to the separately chosen free Rally. |

Each request also accepts a sole strict-Boolean `{"decline":true}` or
`{"use_default":true}`. For 26, decline skips both Ally changes and Rally.
Explicit default follows the named faction's non-player policy; Roman Card2
policy declines unless both Legions can enter, even though human partial
execution is broader. A legal ineffective human selection remains permitted.

Owner replies may include `stage_timing_actions` at `2.legions`,
`2.fallen_legions`, or `26.removals:<index>`/`26.placements:<index>`, including
the final list-length index. Unknown steps, malformed timing maps and unused
reply-level `timing_actions` are rejected. Outer Event entry timing belongs in
`details.timing_actions`. Outer `handler_complete` and Card26's
`grant.card_26_arverni_rally` remain executor-authored Event timing points;
they are not owner-response fields. The original executor retains voluntary
piece-removal authority, while Arverni can independently author eligible
Spring entry. Owner responses cannot claim another faction's authority.

Invalid replies retain the pending ID, board, RNG and accepted history.
Saved sessions and exact replay preserve both the owner effect and later
Rally choice. Older affected transcripts can require new owner decisions;
there is no save-format version change. Numeric 26 remains distinct from A26.

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
Activity between them.

Select each Battle Region once and name an opposing defender. A legacy ranked
`targets` list uses its first Faction. Select each Devastate Region once per
Special Ability. A later Devastate may select a Region that already has its
marker.

For an interruption within one ordered Battle or Raid plan, use
`sa_timing: "during"` and `details.sa_after_step: N`. Supply a single
`battle_plan` or `raid_plan` and the accompanying standalone Special
Ability plan. The Special Ability resolves after entry `N` completes. Use
its 1-based position, up to the penultimate entry. Battle entries are distinct
Regions. The Command retains its original Region selections and capability
choices. Raid entries are individual flips. Keep all entries for each Raid
Region contiguous within the plan and within its normal flip limit. At a
Raid Region's end, intrinsic Germanic Intimidate resolves as part of that
Region. An interruption between flips in one Region keeps both flips in the
same Raid procedure. Choose Enlist borrowing with the Command's force
selection. Use the free Germanic Command option to interrupt with Enlist.

For March, supply explicit `origins` and a `routes` entry for each origin
in `details` or `details.march_plan`. Set `sa_timing` to `"during"` and
`details.sa_after_step` to `{"group":1,"hop":1}` to use the Special Ability
after the first hop of the first group. Groups are numbered in `origins`
order, followed by `extra_groups`. `hop: 0` uses the step after the origin
visibility procedure and before the group's first departure. For a
hide-only origin it uses the completed stay. An interruption after the last
hop of a group requires another declared group. Use `"after"` at the end of
the Command. The ability resolves before transit drop-offs and Harassment.

Each origin is paid once when selected. A later origin can use Resources
gained in the interruption. Counters that already Marched or arrived during
the Special Ability stay out of later groups from that origin. The engine
uses `force_cohort` when the ability can affect either moving or resident
pieces of the same physical owner and visibility. The rest of the group
retains its route and any remaining movement allowance. Routes that cross
into or out of Britannia exclude an accompanying Special Ability.

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
A wholly refused human Command or explicitly rejected human Event raises
`ActionRejected` without consuming the turn; interactive frontends can provide
`decision_func.decision_rejected(state, faction, result)` to explain the
failure and retry the same turn. Legal ineffective Events remain permitted;
the engine's structured rejection marker distinguishes invalid plans from
that case. If supplied, `details.event_params` must be an object: null,
false, zero and lists are not aliases for an empty plan. Omission retains
its existing supported meaning.

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

The constants `RETREAT`, `RETREAT_DISPOSITION`, `LOSS_ORDER`, `AGREEMENT`, and `HARASSMENT_LOSS`
come from `fs_bot.engine.agent`; other kinds below are literal strings.
Requests can include additional context. Copy offered values rather than
inventing pieces, regions, owners, or internal grant flags.

For each Battle Loss, `LOSS_ORDER.pieces` contains only the currently legal
tier: Allies/Forts/Citadels/Settlements first when retreating, last otherwise.
Diviciacus remains the last possible casualty. Later losses rebuild the legal
options, including when a hard piece survives its die roll. Ordinary human
Warbands/Auxilia carry exact visibility, and Ally discs name their Tribe.
When `LOSS_ORDER.is_ambush` is true, an assigned Loss removes a hard piece
without a saving roll, even behind a Fort or Citadel. A successful Caesar
test restores saving rolls and clears this flag for the Roman defender.

| `request["kind"]` | request fields | response |
|---|---|---|
| `RETREAT` | `stage:"declare", region, attacker, defender, is_ambush, legal_regions` | `{"retreat":bool}`. Retreat may be declared with an empty `legal_regions`. |
| `RETREAT_DISPOSITION` | `region, attacker, defender, pieces, legal_regions, can_stay_leader, max_hidden_warbands, default, window` | `{"region":offered_region_or_null,"stay_leader":bool,"stay_hidden_warbands":n}` or explicit default |
| `LOSS_ORDER` | `region, faction, num_losses, is_retreat, is_ambush, pieces` | an ordered subset of the supplied entries; borrowed forces may add `physical_owner`, and Elite counters may carry a fourth tag; copy entries intact |
| `HARASSMENT_LOSS` | `region, harasser, loss_index, num_losses, phase, options`; March carries `departing_pieces`, Seize carries `pieces` | `{"choice": option}` from `options`; see the phases below |
| `drought_loss` | `card_id:49, faction, region, targets` exact physical piece objects | `{"piece":<one offered target>}` or explicit default; no decline |
| `event_up_to` | `card_id, shaded, faction, max_count`; A40 `legal_regions`; A51 `region, available` visibility/count cohorts; A60 `region, available_count` | A40 `{"regions":[...]}`; A51 `{"removals":[{"piece_state":...,"count":n},...]}`; A60 `{"count":n}`; or explicit default |
| `devastate_losses` | `faction, region, count, available` cohort objects `{piece_type,piece_state,count}` | `{"removals":[cohort objects]}` totaling exactly `count`, or explicit default; no decline |
| `harvest_legions` | `count, legal_regions, source:"winter_track"` | `{"placements":{region:positive_integer,...}}` totaling exactly `count`, or explicit default; no decline |
| `resource_transfer` | Donor `faction`, `available`, `recipients` by maximum amount, and `window` | `{"transfers":[{"to":faction,"amount":positive_integer},...]}`, optional `"defer":true` during the action, or explicit default |
| `interlude_reduction` | Faction-owned stage with `stage, minimums, cohorts` | `{"removals":[cohort objects]}` in selection order, or explicit default |
| `interlude_settlements` | German-owned choice after permanent Warband removals, with `options` by Region and `required_allies` | `{"allies":{region:tribe,...}}` or explicit default |
| `interlude_aedui_citadel` | Aedui-owned choice with eligible `regions` and `ally_available` | `{"region":offered_region}` or explicit default |
| `interlude_arverni_citadels` | German-owned choice with Arverni `regions,count,available_allies` | `{"regions":[region,...]}` in replacement order, or explicit default |
| `interlude_cisalpina_relocation` | Interlude controller and physical `acting_faction`, `origin`, `home_regions`, `pieces` with legal `destinations` | `{"allocations":[{"piece_id":id,"count":n,"destination":region_or_null,"tribe":name_if_required},...]}` or explicit default |
| `interlude_expedition` | Roman Interlude choice after Adjust Forces, with `legions`, exact `auxilia` cohorts, `leader_region`, `harvest_count` and printed minima | `{"conduct":false}`, complete allocation described below, or explicit default |
| `interlude_marker` | Romans before Interlude Spring, with `markers` entries carrying `tribe,status` | `{"tribe": offered_tribe}`, `{"tribe":null}` to keep none, or explicit default |
| `besiege_target` | `region, defender, targets, may_decline`; each target is `{piece_type, tribe}` | `{"target": <one offered target>}`, `{"decline":true}`, or explicit default; a Settlement has `tribe:null` |

A Retreat declaration precedes the Attack and fixes the Loss procedure.
Host agreements are collected during this step. `retreat_disposition`
uses the mobile pieces that actually survived and the current Control of
adjacent Regions. A host's agreement applies to its Region if that host
still Controls it. Against Romans the defender can keep any number of
surviving Hidden Warbands up to `max_hidden_warbands`, and can keep the
Leader if `can_stay_leader` is true. A null destination removes the pieces
that do not stay. Any movement uses one destination for all of them.

An explicit default at declaration delegates Retreat to the existing bot
policy. At disposition, `default` gives the offered survivor allocation.
Raw older adapters can still send an offered `region` with the declaration
to use that destination and the old stay defaults. Verified older assistant
prompts retain their recorded response format. Rampage uses its own
`retreat` contract described below.

`event_piece_choice` goes to the executor for unshaded numeric 19 (Lucterius)
and 22 (Hostages), on the live Event-step board. The request carries `card_id`,
`owner`, `legal_regions`, `available` physical cohorts, and `max_count` (six
for 19, four for 22). A cohort carries `region`, `target_faction`, `piece_type`,
`piece_state` and its available `count`. Lucterius also reports the Roman
Auxilia Available pool and its five-piece placement maximum.

For 19 respond `{"choice":"auxilia","count":2}` or
`{"choice":"warbands","removals":[<cohorts with chosen counts>]}`.
Zero Auxilia or an empty removal list is legal. Auxilia placement is in
Provincia and is capped by actual Available; removals must total at most six
Arverni Warbands within one Region of Provincia. Counts and visibility are
exact. Use the same `choice`/`count`/`removals` keys in authored `event_params`.

For 22 respond `{"selections":[<cohorts with chosen counts and action>]}`.
Each entry adds `"action":"remove"` or `"action":"replace"`; mix actions
across at most four physical pieces in total, including zero. Only Warbands
and Auxilia in the executor's currently Controlled Regions are offered.
An explicitly selected group can remove own pieces and can finish its selected
removals even if removing them loses Control. Replacement places the executor's
Hidden Auxilia (Romans) or Warbands (other factions), subject to Available.
If no replacement is Available, remove the selected original pieces anyway
(§5.1.1). For authored params use `{"piece_choices":[<entries>]}`. Do not mix
that new plan with legacy `replacements`.

Both exact plans are collected after the `19.piece_choice` or `22.piece_choice`
Event timing window and validated before their aggregate mutation. The terminal
supports `b`/`board`, smaller totals, exact visibility and removal-only choices.
Missing/invalid durable replies stay pending with board/RNG rollback, stable
IDs, save/load and exact replay. Previews do not consume live choices or RNG.
Raw `None` or explicit `{"use_default":true}` retains the delegated plan.
Legacy explicit `choice`/`removal_regions` (19) and `replacements` (22) remain
supported. The legacy Gallic Hostages path also now correctly replaces Roman
Auxilia with its own Warbands. Older histories can stop at the new request or
vary under that corrected replacement.

Shaded Marcus Antonius (6) sends `event_piece_choice` to the executor after
`6.piece_choice`. Respond `{"selections":[...]}` with zero to `max_count`
offered Roman Auxilia, chosen by origin and visibility. The request includes
the fixed `destination` Provincia and excludes Auxilia already there. Moves
preserve visibility and use the selected groups in order. The same list can
be authored as `event_params.piece_choices`. The legacy `auxilia_moves`
origin/count pairs still work. Supply one plan format. A player who defers
moves zero pieces and still gets the printed eligibility effects. Older
histories may reach the new prompt or diverge under the corrected movement.

Shaded Alaudae (7) checks the Legions track at the start of resolution.
At seven or fewer, it sends the executor an `event_piece_choice` for
each piece type available in order, after `7.legion_removal` and then
`7.auxilia_removal`. Answer each with `{"selections":[...]}` from that
request's cohorts. Legions use `piece_state: null` and go to the track.
Auxilia use their exact visibility and return to Available. For an
authored plan, put both removals in `event_params.piece_choices`, or use
the Region-only keys `legion_removal_region` and `auxilia_removal_region`.
Older histories may pause for a choice or diverge under corrected
delegated targeting.

Shaded Numidians (11) sends `event_piece_choice` to the executor after
`11.piece_choice` in both editions. Respond `{"selections":[...]}` with
the offered Roman Auxilia cohorts, including exact visibility and Region.
Select four or all present if fewer, as specified in `required`. Use
`{"use_default":true}` to delegate, or supply the same selections in
`event_params.piece_choices`. Legacy `auxilia_removal_regions` pairs and
`removals` objects retain their Region priorities and are completed to
the required total. Use only one plan format. Older histories may reach
the new request or diverge where revised Numidians previously did nothing.

Shaded Sappers (24) sends `event_piece_choice` to the executor after
`24.piece_choice`. Its `required_by_region` gives the total in each Region
with an Arverni Citadel, capped at two. Respond `{"region":...,"selections":[...]}`
with that total from a single Region, in any mix of offered Legions and
Auxilia. Legions use `piece_state: null` and go to Fallen. Auxilia use their
exact visibility and return to Available. Use `event_params.target_region`
and `piece_choices` for an authored plan. Legacy quantity fields still set
the initial priorities, with any shortfall filled from the chosen Region.
Older histories may pause for the new choice or diverge under corrected
delegated targeting.

Shaded Cotuatus & Conconnetodumnus (31) sends `event_piece_choice` to the
executor for each applicable removal. The request identifies the `slot`
(`roman`, `aedui`, or `third`) and lists `targets` with `tribe`, `region`
and `target_faction`. Respond `{"tribe": <offered tribe>}` or
`{"use_default":true}`. Each offer uses the current board after the
preceding removals and timing windows. Citadels are excluded. Author
choices in advance with `roman_ally_tribe`, `aedui_ally_tribe`, and
`third_ally_tribe` in `event_params`. Legacy Region and faction parameters
remain supported for slots without a named Tribe. An older history with
unspecified targets may pause at a new choice.

Unshaded Litaviccus (45) sends `event_piece_choice` to the executor
after `45.piece_choice`. Respond `{"selections":[...]}` with exact
Arverni Warband cohorts from `available`. The limits are two Regions,
two Warbands per Region and four total. An empty list selects zero
replacements. The Arverni-to-Aedui Resource transfer still applies.
Use `event_params.piece_choices` to author the exact list. Entries
resolve in order of first Region appearance and then in selection
order within each Region. Legacy `regions` entries retain their
Region and replacement timing windows and delegate visibility.
Older histories may pause for the new choice or diverge under the
corrected replacements.

Unshaded Aduatuca (58) sends `event_piece_choice` to the executor after
`58.piece_choice`. Its `required_by_region` gives the number of Belgic
and Germanic Warbands to remove in each Region with a Roman Fort, capped
at nine. Respond `{"region":...,"selections":[...]}` with that Region's
exact total, using the offered faction and visibility cohorts. The removed
pieces return to their respective Available pools. To author the choice
in advance, set `event_params.region` and `piece_choices`. Legacy
`removals` entries keep their faction order and timing windows, and the
Event fills any shortfall within the selected Region. Older histories may
pause at the new choice or diverge under the corrected removals.

Unshaded Indutiomarus (60) sends `event_piece_choice` to the executor
after `60.piece_choice`. Its `required_by_region` gives the number of
eligible pieces in Treveri and each adjacent Region, capped at six.
Respond `{"region":...,"selections":[...]}` with that Region's exact
total. Each Belgic Ally row includes `tribe`, `piece_state: null` and
`count: 1`. Copy the Tribe into the selection. Warband rows use their
exact visibility and omit `tribe`. To author the choice in advance, set
`event_params.region` and `piece_choices`. Legacy `removals` entries
remain ordered single-piece preferences with their original timing
windows. The Event fills any shortfall within the chosen Region.
Older histories may pause for the new choice or diverge under the
corrected removals.

Unshaded Catuvolcus (61) sends two `event_piece_choice` requests to the
executor, one for each step with eligible targets. After `61.ally_choice`,
the request has `step: "allies"` and `targets` listing each named Ally
and its faction. Respond `{"tribes":[...]}` with one or more offered
Tribes of a single faction. After those removals and `61.warband_choice`,
the request has `step: "warbands"`, `available` and `required`.
Respond `{"selections":[...]}` with the required total from the offered
Nervii Warband cohorts, using exact faction and visibility. Any mix of
Warband factions is legal. Use `event_params.ally_removals` and
`piece_choices` for authored choices. Legacy `warband_removals`
keep their ordered faction preferences and timing windows, and the Event
fills any shortfall within Nervii. Older histories may pause for the
new choices or diverge under the corrected removals.

Shaded Pompey (3) and Gallia Togata (5/A5) send `event_piece_choice` to
the Romans, including when another faction executes the Event. After the
`3.piece_choice`, `5.piece_choice` or `A5.piece_choice` timing window, the request includes
`available` cohorts and `required` totals keyed by piece type. Legions have
`piece_state: null`. Auxilia have exact Hidden, Revealed or Scouted states.
Respond `{"selections":[<cohorts with chosen counts>]}`, meeting every
required total. The board may have fewer pieces than the printed amount.
Roman executors can also author `event_params.piece_choices` with the same
entries. Raw deferral and explicit default use the delegated Region-priority
plan, including legacy Region parameters from Roman executors. On A5 the
legacy keys are `legion_region` and `auxilia_removals` (entries with `region`).
Delegated A5 uses seeded selection among equal Regions and removes Scouted
before Revealed before Hidden Auxilia within a Region. If a legacy plan
covers only part of the required total, the default fills the remainder.
Durable sessions hold the action pending for Rome and revalidate before
moving Legions to the track and Auxilia to Available. Older decision
histories that predate the prompt can pause at the new Roman choice or
replay differently because delegated A5 now carries out its removals.

Unshaded Usipetes & Tencteri (A36) sends `event_piece_choice` to the
executing faction after `A36.piece_choice`. The same `{"selections":[...]}`
response and `event_params.piece_choices` format apply. The request gives
separate required totals for German Settlements and Warbands, capped by the
pieces present in Morini, Nervii and Treveri. For Settlements use
`piece_state: null`; for Warbands use the offered exact visibility.
Selections may span Regions and are validated together. A response with
`{"use_default":true}` delegates the complete effect, with seeded choices
among tied Regions and the printed own or enemy visibility priorities.
Older replays may reach the new choice or diverge under the corrected default.

Shaded Publius Licinius Crassus (A17) sends `event_piece_choice` to the
executing faction after `A17.piece_choice`. The request lists the required
Auxilia count for each playable Region in `required_by_region`. Respond
with `{"region":...,"selections":[...]}`, using exact cohorts from that
one Region. Authored Event plans use `region` and `piece_choices`. The
count is four, capped by the Auxilia present in the chosen Region, and
Rome becomes ineligible through the next card even when the count is zero.
A legacy Region-only plan keeps that Region and delegates visibility.
Older histories may reach the new prompt or diverge under revised bot
Region and visibility selection.

Shaded Aduatuci (A58) sends `event_piece_choice` to the executing faction.
Its `required_by_region` counts and `ally_tribes_by_region` lists cover
playable Belgica Regions. Respond with
`{"region":...,"ally_tribe":...,"selections":[...]}`. Use a listed Roman
Ally disc or `null` when the chosen Region has none. The Auxilia cohorts
must come from that Region and total three or all present if fewer.
Authored Event parameters use `region`, `ally_tribe` and `piece_choices`.
An older Region-only plan can delegate the piece identities. The Ambush
uses the board after the replacements and takes place in the chosen Region
if legal. Earlier histories may pause at the new choice or diverge if they
previously relied on a broader Ambush.

Unshaded Bellovaci (A69) sends `event_piece_choice` to the executor after
`A69.remove_warbands`. Reply with `{"selections":[...]}` using the offered
Hidden, Revealed and Scouted Belgic Warband cohorts in Atrebates. Select
four or all present if fewer. Use `{"use_default":true}` to delegate or
provide the same list in `event_params.piece_choices` to author it in
advance. Set `ally_faction` and `piece_faction` independently to `Romans`
or `Aedui`. The troop faction determines whether Auxilia or Warbands are
placed. Older plans can still specify `piece_type`. Without either troop
field the default troops follow the Ally faction. Earlier histories may
pause for the choice or diverge under corrected defaults.

`march_cohort` | `phase, region, piece_type, count, available`; may include `acting_faction, physical_owner` | `{"counts": {visibility: count}}`, totaling exactly the requested `count` |
| `march_dropoff` | `faction, acting_faction, region, destination, pieces, max_dropoffs, window`; may include `leader` | `{"dropoffs":[{"faction":owner,"piece_type":type,"piece_state":visibility_or_null,"count":n}]}` or explicit default |
| `diviciacus_pieces` | `phase` (`placement`, `formation`, `dropoff`, `loss`), `region, piece_type, count, available` by physical owner | `{"counts": {owner: count}}`, totaling `count` without exceeding `available` |
| `force_cohort` | `region, piece_type, piece_state, operation, count, available` with `selected`/`other` counts. May include `physical_owner` and descriptive labels. | `{"counts":{"selected":n,"other":m}}`, totaling `count`, or explicit default |
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
| `quarters_provincia` | `faction, original_moves, legal_moves, errors` | `{"moves":[[piece,origin,"Provincia",count,visibility],...]}`, `{"decline":true}`, or explicit default |
| `quarters_payment` | `faction, reason`, optional `errors` | `{"payments":{...}}` using the existing Roman quartering allocation shape, or explicit default |
| `spring_leader` | `faction, leader, source, reason, legal_regions, can_defer`; mid-action offers add `window`, scenario ties may set `equal_priority` | `{"region":name}`, `{"defer":true}` only when offered, or explicit default |
| `winter_campaign` | `card_id, remaining_actions`, optional `errors` | one paid action, combined Command+SA, or decline; see the Winter section below |
| `frumentum_amount` | A53; `available_resources` (Aedui) | `{"amount": integer}`, `{"decline":true}` (zero), or explicit default |
| `frumentum_action` | A53; `remaining_actions, remaining_resources, reserved_roman_resources` | one Recruit/March plan or standalone Build/Scout plan, `{"skip": action_name}`, finish with `{"decline":true}`, or explicit default |
| `raid_intimidate` | A3.4.3; `region, raiders, max_removals, targets`; shaded A22 adds `max_raider_removals, extra_warband_available, max_with_extra` | `{"targets":[...]}` with optional Boolean `extra_warband`, marker only `{"targets":[]}`, `{"decline":true}`, or `{"use_default":true}` |

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

Replacement `details`, if supplied, must be an object. Malformed nested
Supply replies retain the same pending request, input and board/RNG; they
cannot fall through to an automatic choice or a different decision kind.

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

`drought_loss` belongs separately to each physical owner in each Devastated
Region on Card 49, after Resources are halved and the new marker is placed.
Choose exactly one offered target under `piece`: soft pieces name `piece_type`
and `piece_state`; Allied Tribes/Citadels name `piece_type` and `tribe`; Leaders
name `piece_type` and `leader_name`; Legions, Forts and Settlements name only
`piece_type`. For example, `{"piece":{"piece_type":"Auxilia","piece_state":"Revealed"}}`
selects one Revealed Auxilia instead of a Legion. Legions go directly to Fallen;
Diviciacus leaves play. Exact Tribe removals update physical backing/allegiance.
Only the requested owner's pieces can be selected. German Allied Tribes are
not offered while German Warbands remain; the permanent Provincia Fort is
never offered. Empty/protected-only owners receive no request. Base Germans
and expansion Arverni are game-run and remain automatic.

Missing/invalid durable answers retain pending IDs and earlier accepted owner
choices through whole-Event rollback/save/resume, including a later Region.
The terminal offers exact pieces with board inspection. Raw None or explicit
default uses reverse own-piece priority: Scouted/Revealed/Hidden soft pieces,
ordinary Allies before City/Remi Allies, then structures, Legions and Leaders;
equal eligible Tribes use state RNG. Previews consume no live choices/RNG.

The old executor-authored Python `piece_removals` map is rejected explicitly.
It could control another owner's casualty and cannot safely migrate by guessing
consent. Use the JSON-safe owner response above. Card 49 Event parameters now
accept `devastate_region` and existing `stage_timing_actions`; a specified marker
Region must be playable and not already Devastated. The terminal offers legal
marker locations. Omitted marker selection retains the existing automatic
fallback; broader NPC marker targeting is outside this casualty repair.
Older transcripts that omitted owner decisions may require new responses.

`event_up_to` gives the Event executor the optional quantity choices on A40
shaded and A51/A60 unshaded (§5.1). It is a live request at the relevant step;
A51 has already performed its compulsory troop/Fort placements, and A60 its
Roman Ally placement, before asking. No choice transfers to a beneficiary.

- A40 selects zero to three distinct offered Regions within one of Cisalpina,
  without Roman Control. Each selected Region costs Romans five Resources;
  Stay Eligible applies even when the list is empty.
- A51 selects zero to six actual Belgic Warbands at Remi, naming exact Hidden,
  Revealed or Scouted counts. Duplicate entries share physical capacity.
  Selecting none does not cancel the compulsory four troops and Fort.
- A60 selects zero to four Auxilia. Pieces actually placed are limited by
  current Available forces; each unplaced Auxilia yields Romans two Resources,
  plus two independently if the Roman Ally could not be placed. The 45 cap
  applies. The terminal offers counts up to current availability.

Author plans may supply these choices directly as A40 `event_params.regions`,
A51 `event_params.warband_removals` (same entries as response `removals`), or A60
`event_params.auxilia_count`. A51 also accepts `piece_type` Auxilia or Warband
(the latter means Aedui Warbands). Unknown/wrong-side fields, malformed counts,
illegal Regions and overclaimed cohorts are rejected atomically. A60 authored
counts may request up to four even when fewer are Available; partial execution
and compensation use actual placements. A51's Remi prerequisite still applies.

Omitted choices ask the live executor. Missing/invalid durable input remains
pending, including after rollback/save/resume of the compulsory prefix. Raw
None or explicit `{"use_default":true}` uses maximum quantities and the existing
Hidden/Revealed/Scouted enemy-removal priority. Previews do not consume input or
RNG. These additional live decisions can require responses when replaying an
older transcript that omitted the choice. Terminal prompts support `b`/`board`.

`devastate_losses` goes separately to each affected physical owner at the live
Devastate step (§4.3.2). Arverni lose one in four Warbands; each other Faction
loses one in three total Warbands/Auxilia/Legions, rounded down. The request's
`available` list names physical visibility cohorts; Legions have `piece_state:null`.
For example, `{"removals":[{"piece_type":"Legion","piece_state":null,"count":1}]}`
selects a Legion instead of Auxilia when one Roman casualty is required.
Only offered cohorts of that request's owner may be removed. Counts must be
positive integers totaling the exact requirement. Leaders, Allies, Forts and
Citadels do not count and cannot absorb the losses. Legions go to Fallen.

All owner counts and choices are collected/validated before any casualty or
marker mutation. Zero losses produce no prompt. The terminal offers bounded
per-cohort quantities and board inspection. Missing/malformed durable input
retains the pending decision and earlier accepted choices through whole-action
rollback/save/resume, including a later Region. Raw None or explicit delegation
uses §8.4.1's own-piece priority: Scouted, then Revealed, then Hidden soft pieces,
then Legions. Named choices add `removal_details` to the mechanic result;
`removed` retains grouped type totals. Trusted low-level `devastate_region`
preselected tuple maps remain supported but must specify exact losses;
legacy soft-piece None visibility retains its H/R/S fallback. Normal actor plans
select Devastate Regions; each casualty request belongs to the affected owner.

Card 35 unshaded sends its Roman beneficiary a normal `free_action` /
`event_command` request with additive presentation fields: `card_id:35`,
`alternative:"eligible"`, and `private_cards`. Each private card contains
`card_id,title,text,faction_order,np_symbols,is_winter,has_carnyx_trigger`, using
the active scenario and card edition. The already face-up `next_card` is
excluded: live deck entries 1 and 2 are the two facedown cards, with fewer
entries reported near deck end. Winter is identified without invented Event
text. Reading does not draw, reveal publicly, reorder or consume RNG.

After reading, submit a legal free Limited Command (one origin/Region, no SA),
or `{"decline":true}` to take the existing Become Eligible alternative.
`{"use_default":true}` retains the established bot choice. The terminal prints
this private briefing before the choice and labels that alternative **Become
Eligible**. Requests go to Romans regardless of who played the Event. Private
card data belongs in the Roman request and trusted session journal; public
Event results, modifiers and board snapshots do not acquire it. The legacy
Boolean `card_35_roman_peek` receipt is unchanged and contains no card data.
Existing raw agents receive additive request fields; historical logs retain
their revision-specific meaning. Missing/malformed durable input remains
pending through rollback/save/resume; accepted requests and choices replay.

`harvest_legions` goes to the Roman seat at the start of the first Pax Gallica
Harvest, including the corresponding first Harvest after the Gallic War
Interlude if the expedition left Legions on the Winter Track. Choose any
allocation among the three Belgica Regions, including an empty Region or one
with enemy Control. For example, `{"placements":{"Morini":1,"Nervii":2}}`.
Omit zero entries; counts must be positive integers and total the entire offered
count. This is required placement, so `decline`, partial totals, booleans and
outside Regions are invalid. The request reflects actual Winter Track supply;
an empty box makes no request and creates no Legions.

Invalid/missing durable input remains pending across rollback and save/resume.
Raw None or explicit `use_default` keeps the existing concentrated NPC choice:
the most Roman Legions plus Auxilia, with sorted-first tie breaking. The default
result keeps `{region,legions}`; a human allocation returns `{placements,legions}`
in `phases.harvest_belgica_legions`. CLI allocation prompts support board
inspection. Each Legion transfers from the Winter box through the piece helper;
it is not taken from the Senate's Legions Track or Available.

`besiege_target` goes to the Roman seat immediately before Battle Losses when
Besiege applies. It offers each physical defending Citadel or Ally disc by
Tribe, plus a German Settlement in Ariovistus. Choose an entire offered
`target` object; a piece type alone is insufficient. For example,
`{"target":{"piece_type":"Ally","tribe":"Helvetii"}}`. The engine removes
exactly that physical target and clears only its Tribe's allegiance. A
Settlement removal clears no Tribe. `{"decline":true}` omits the optional
removal while the announced Besiege/active Ballistae rules still apply.

Choices are built from the live board after Retreat declarations and before
Losses, including a zero-Loss Battle. An originally defending Citadel still
halves Losses after removal, unless Ballistae cancels it. Each Battle Region
has a separate request. Invalid or missing durable responses remain pending
through rollback/save/resume. Raw callback `None` and explicit `use_default`
retain the legacy Citadel/Ally/Settlement type priority and deterministic Tribe
selection. Terminal play offers named choices, decline and `b`/`board` inspection.
Previews never consume a live choice; accepted requests and responses replay.

`ballistae_target` goes to Card 10 shaded's owning Gallic seat after its
Ambush has fully resolved, including combat casualties and Reveal. It offers
only surviving defending Forts or Citadels. Choose an entire offered `target`
object, such as
`{"target":{"piece_type":"Citadel","tribe":"Sequani","owner":"Arverni"}}`,
or respond `{"decline":true}` to leave every surviving target. This optional
removal causes no additional saving roll. Its target retains its physical
owner, and removing a Citadel clears exactly that Tribe's allegiance.
Provincia's permanent Roman Fort is never offered (§1.4.2).

Each Ambush Region has its own live request, including Event-granted Ambushes.
The Event executor and capability owner can differ. Invalid or missing durable
responses stay pending, with the entire Battle action and RNG restored until
the choice can be completed. Earlier accepted Region choices survive a later
pause and save/load/replay. Raw `None` and explicit `{"use_default":true}` retain
the Citadel-before-Fort default. Terminal play supports named targets, decline
and `b`/`board` inspection. Older cross-revision transcripts that passed this
formerly automatic step may stop for the newly required choice. This repair
does not close BE-09's separate Card 13/59 Region-selection gaps.

`slingers_region` goes to Romans at the start of an enemy's ordinary or free
Battle plan when Roman Auxilia are present in any selected Battle Region.
The request contains `attacker`, ordered `legal_regions`, `defenders` and
per-Region `auxilia` counts. Return `{"region":"Mandubii"}` for one offered
Region or explicit `{"use_default":true}`. Card 13 unshaded says to choose
one Region, so there is no decline. An offered Region with zero or one Auxilia
is legal even when it causes zero pre-fire Losses. A Region without either
of the planned combatants is not offered. Romans may be defending or a third
party while another Faction is the defender.

The selection applies once during that Command, before the chosen Battle.
Live Auxilia there inflict one-half Loss each, rounded down, or one each when
both Slingers and Germanic Horse are unshaded, as their printed Tips specify.
That initial-fire bonus does not depend on which Region has Horse's separate
ordinary-Battle bonus. The default now follows §8.3.3's first applicable
selected Region, replacing the old most-Auxilia heuristic.

Terminal play supports `b`/`board` inspection. Missing or invalid durable
responses remain pending with board, payments and RNG restored. An accepted
Region survives a later casualty prompt, save/load and replay. Previews never
consume live input. Older replays can stop at the new choice or diverge from
the corrected NPC priority/fire rate. The private prospective Battle queue
used by numeric 67's NPC branch uses the PR-13 live windows below. Horse's
ordinary/free-plan choices and optional unshaded queue windows are implemented.

`horse_region` goes to Card 59's owner before an ordinary/free Battle plan.
Unshaded belongs to Romans and offers their actual attacking/defending Battles;
third-party Roman presence alone does not make a normal Horse Battle bonus.
Shaded belongs to the recorded Gallic owner and offers that owner's actual
attacking/defending Battles. Ranked defender lists use the actual first target.
The request carries `side`, `owner`, `attacker`, ordered `legal_regions`,
`defenders`, Roman `auxilia` counts and the shaded side's current `blocked`
status. Return one offered `region` or explicit `use_default` delegation.

Only unshaded says "may" and accepts `{"decline":true}`. Shaded selects one
Region; selecting a currently protected Region is legal, but does not bypass
its live protection. Attack doubling is blocked by a defending Fort/Citadel
or active Abatis. The owner's defensive counterattack is blocked by its own
Citadel, while Abatis alone permits doubling. Existing A31 cancellation of
Abatis is respected. Auxilia's unshaded full-Loss rate still precedes normal
halving and rounding. Zero-Auxilia Regions can be selected. Non-player/default
selection uses the first currently applicable selected Battle per §8.3.3.

Each Battle Command scopes and clears its own Horse flags on completion or
interruption; an inner Battle temporarily replaces and then restores its
outer Command's selection. Both frontends preserve pending responses,
accepted selections through later casualties, save/load and exact replay.
Terminal `b`/`board` inspection and isolated previews remain available.
Older histories can stop for the new choice or diverge from corrected defaults.
The private prospective queue now offers optional unshaded Horse windows.
Slingers and shaded Horse use the mandatory PR-13 window below.

`horse_window` restores optional unshaded Horse timing in a prospective queue.
It is offered to Romans only when a candidate has actually become a Battle,
with Roman participation and Auxilia present. It carries `region`, `attacker`,
`defender`, the current `auxilia` count, offered `actions` and
`potential_regions`. Those later queue candidates may never become Battles.
Respond `{"action":"activate"}` to use Horse here, `{"action":"reserve"}`
to save it if offered, or `{"action":"decline"}` to decline for the remainder
of the Command. Explicit default activates here, preserving NPC behavior.

Reservation consumes no use. The next actual eligible Battle offers a new
window, including a Region reached by Retreat arrivals. Activation or whole-
Command decline prevents any second use/request. No future candidate means
no reservation option. If a reserved opportunity never occurs, the optional
unshaded effect expires unused. Terminal inspection and durable pending,
earlier acceptance, rollback/save/resume/replay remain supported. PR-11's
forecast branches these optional human choices and conservatively ranks the
lower predicted Legion Losses; it consumes no live decisions or RNG.

`capability_window` implements [PR-13](docs/provisional-rulings.md#pr-13)
for Card 13 unshaded and Card 59 shaded in prospective queues. It carries
`card_id`, `side`, `owner`, `region`, `attacker`, `defender`, live Roman
`auxilia`, current `blocked` status, `potential_regions` and `actions`.
Respond `{"action":"activate"}` or, while later candidates remain,
`{"action":"reserve"}`. There is no general decline. The final candidate,
if it becomes a Battle, offers only activation. Reserving may expire unused
if no later eligible Battle occurs; resolution never rewinds or invents a Battle.
Human selection can consume the use in a zero-Auxilia/protected Battle, without
bypassing the printed effects. Default delegation retains first-applicable use,
skipping a zero-Auxilia Slingers Battle or protected Horse Battle. Such internal
deferral is not an additional human action at the final window.

The owner receives the live request after Battle selection/payment and before
pre-fire. Each capability's use is independent. Terminal inspection, strict
pending validation, rollback, earlier accepted responses, save/load and replay
are supported. PR-11 prediction branches legal human responses without live
input or random-state consumption. Older cross-revision histories can stop at
the newly required request or diverge under expanded forecasts. PR-13 remains
provisional, subject to official correction.

`march_cohort` identifies physical pieces after origin flipping (`formation`)
or for the exact quantities in an Event's authored `dropoff`. For a request
with `count: 2` and sufficient offered counts, a response can be
`{"counts":{"Hidden":1,"Revealed":1}}`. Counts cannot exceed `available`
or change the group's planned total. The request may identify a different
acting faction or physical owner, as with Divination or Enlist; that identity
is supplied by the engine and cannot be changed by the response.

The validators are `commands.march.validate_harassment_response` and
`engine.march_choices.validate_response`; both validate without moving
pieces or consuming RNG.

Ordinary March uses the live `march_dropoff` request after arrival and before
Harassment. The acting player may leave any offered physical cohort and keep
at least one piece moving. Use the offered faction, type and visibility
with a positive integer `count` per cohort, within `max_dropoffs` in total.
Legions and Leaders use a null `piece_state`. The list can be empty, and
explicit delegation keeps the group together. The next hop must be legal
for the continuing pieces. The plan's route can end earlier if its remaining
members lose an extra hop by leaving a Leader.

The request contains only the pieces still traveling after earlier
Harassment and voluntary removal. Borrowed pieces retain their physical
owners. `window` identifies the origin, group index, current Region,
completed step and next destination. The terminal and durable assistant
enable the request by default. A custom reactive agent can opt in with
`supports_march_dropoffs = True`. Older recorded Marches use the no-drop
default at absent windows.

A later origin can form groups only from eligible pieces that have yet to
March in this Command. Earlier arrivals and drop-offs still undergo that
origin's normal visibility changes. During voluntary removal, the request
can distinguish those pieces with `cohort: "marched_pieces"` and the label
`Already marched`. Use the exact offered cohort to remove them. Older
transcripts whose requests or results depend on the previous grouping can
diverge under the corrected rules.

`force_cohort` similarly separates Event-selected counters from other pieces,
or the physical colours in an Enlist drop-off. Use the request's labels and
offered counts; the `selected` label is not always an Event force.
Shaded Vercingetorix's Elite uses `battle_elite` to select actual Warbands
for that Battle. Subsequent loss-order entries can identify a selected piece
as `["Warband", visibility, null, "elite"]`; other Warbands remain separate.

### Scoped Event grants

Numidians (11, both editions), Aquitani (25), unshaded Morasses (36), shaded
Litaviccus (45), and Camulogenus (70)'s Battle step use `free_action` with
`request_type: "fixed_event_battle"`. The request's `defenders_by_region`
maps each offered Region to its legal defenders. Return exactly
`{"region": "...", "defender": "..."}`, or explicitly request
`{"use_default": true}` when `default_available` is true. The engine applies
the printed modifiers; response fields cannot add Special Activities,
participants, extra Losses or exemptions. Subsequent Diviciacus agreement
requests remain separate from selecting the Battle.

These Battles are mandatory when possible. Camulogenus first offers Romans
the whole-benefit decision described below; after acceptance, its Battle
cannot be independently declined. Aquitani's offered
targets may include a Region without friendly Forces, as its text permits.
Missing or invalid durable-session responses remain pending with board/RNG
rollback; do not replace them with a default response.

Numeric4 uses `free_action` / `circumvallation_march` for Romans, independent
of the Event executor. `decline: true` declines the complete benefit before
any new marker or movement; `use_default: true` delegates the whole benefit.
An explicit plan contains `destination`, ordered `marches` and optional
`diviciacus_regions`. Each group contains `origin`, integer `legions` and
`auxilia`, and Boolean `leader`. Every group moves one adjacent step into
the same offered enemy Citadel Region. Counts are reserved from original
forces, including split groups and a Leader selected at most once. No extra
routes, dropoffs, other pieces or four-Legion cap apply. For example:

```json
{"destination":"Mandubii","marches":[{"origin":"Sequani","legions":0,"auxilia":2,"leader":false}]}
```

The empty list leaves placement to existing Romans. Marker placement occurs
after March, requiring a remaining non-Roman Citadel and Roman presence.
Missing/invalid durable answers stay pending; saves at formation preserve
accepted plans. Legacy `target_region` must name an enemy Citadel and only
seeds automatic planning; the Roman human owns the actual destination.
**Known follow-up CV-PERSISTENCE:** continuing marker restrictions, virtual
Fort behavior, attack/elimination cleanup and exact Interlude removals remain
incorrect. The no-Romans boundary now clears the marker after successful
physical moves/removals. Any resident Roman piece counts, including an Ally,
Fort or Leader; temporary effective-force views do not change ownership. See the [verified follow-up](docs/reviews/circumvallation-persistence-followup-2026-11-04.md).
Old transcripts may encounter the new decision; the save schema is unchanged.

Numeric 17 unshaded shares `german_guided_march` / `german_guided_ambush`,
but requests carry `card_id: 17` and are always consulted with Romans, not
the Event executor or Germans. Engine-owned `acting_faction` remains Germans.
The March request offers `max_origins: 3` and `moving_groups_only: true`.
Respond with `marches`, each containing one distinct original `origin`, an
adjacent `destination`, and a positive integer `warbands` quantity. An empty
list selects no moving groups. Unlike card65's Region grant, card17 grants
moving groups and does not offer additional hide-only origins. Normal
origin flips still affect pieces left behind; arrivals cannot move twice.

The following Ambush request has `max_regions: 1`: select one offered
`region` and `defender`. It is mandatory when possible, but no second
Region Ambushes. Physical formation choices go to Romans; defenders retain
their own reactions. Native Roman NPCs guide automatically even when another
player executes the Event. An explicit first-stage `use_default` invokes
the Roman card instructions for the whole grant; raw callback deferral
retains the established legacy contract. Durable missing/invalid replies
remain pending, with whole-grant rollback and save/resume. The shaded Germans
Phase is unchanged. New requests may change cross-revision replay needs.

Numeric 65 unshaded uses `free_action` / `german_guided_march` for the Event
executor, with engine-owned `acting_faction: Germans`. Respond with `marches`,
a list of at most two entries containing `origin`, `destination` and integer
`warbands`. Origins must be distinct and quantities must fit the initial force.
A positive group enters one adjacent playable Region; zero uses
`destination: null` and hides only the original counters at that origin.
The empty list selects no March. Arrivals never join later groups or receive
a second origin flip. For example:

```json
{"marches":[{"origin":"Provincia","destination":"Sequani","warbands":2}]}
```

The successive `german_guided_ambush` requests expose fresh
`defenders_by_region` and `remaining_regions`. Respond with one `region` and
`defender`. Each able Region must act once; the executor chooses order and
targets. No independent decline or repeated Region is accepted. Printed
Hidden superiority, Fort protection, and German-only Ambush requirements
remain in force, including after defensive cooperation. Zero predicted
Losses do not by themselves make an Ambush illegal. These choices are
separate from each physical defender's live reactions. Missing/invalid
answers remain pending and the complete grant rolls back while awaiting
later input; save/resume replays accepted earlier choices. Native NPCs
and raw callback deferral retain the previous whole-grant planner. An
explicit `use_default` at the March stage delegates the complete grant; at
a later Ambush request it delegates only the next choice. Old transcripts
may encounter new requests.

Numeric 58 shaded uses `free_action` / `aduatuca_march`, consulted with the
Event executor, with engine-owned `acting_faction: Germans`. Respond with
`destination` and ordered `marches`, each containing `origin` and integer
`warbands`. Choose a Roman Fort Region and distinct adjacent origins, at most
one group per origin. Zero selects an origin for its normal visibility flip
without moving pieces; an empty list leaves only resident Germans available
for the mandatory following Ambush. No response can redirect that Battle,
add pieces or routes, or independently decline it. For example:

```json
{"destination":"Mandubii","marches":[{"origin":"Sequani","warbands":2}]}
```

The granted March remains German movement, including Scouted handling;
`march_cohort` formation choices go to the executor and identify
`acting_faction: Germans`. Roman defender choices remain Roman-owned.
Explicit `use_default` retains the previous automatic planner. Missing or
invalid durable answers stay pending; saving at a later defender choice
preserves and replays the accepted March before resolving that choice.

Numeric 9 uses `free_action` / `mons_cevenna_march` for its human executor.
Respond with `origin`, `destination`, `group` and optional `diviciacus_regions`.
The group maps canonical mobile piece labels to integer quantities, with a
Boolean `Leader` selection. The single adjacent route must stay within
Provincia, Sequani and Arverni; it cannot add dropoffs or extra origins.
For example:

```json
{"origin":"Provincia","destination":"Sequani","group":{"Auxilia":1}}
```

If no native March is possible, use `origin: null`, an empty `group`, and
one offered destination for partial execution. An available first March
and following Command cannot be declined independently. Explicit
`use_default` retains automatic planning. The following `event_command`
request scopes Command and SA to that destination, while allowing March
or Scout to move out. Missing/invalid durable answers remain pending;
save/resume retains the chosen first March. Formation and cooperation
answers remain separate. Legacy `march_from`/`march_to` Event parameters
are validated as a complete adjacent pair; human players choose their
actual move at the new live decision rather than the initial parameter form.

Numeric 70 unshaded first uses `roman_event_accept` for the Roman beneficiary,
independently of which faction executed the Event. After acceptance,
`camulogenus_march` accepts `destination`, `marches`, and optional
`diviciacus_regions`. Each March entry contains `origin`, `route`, integer
`legions` and `auxilia` quantities, and Boolean `caesar`. Every nonempty
route must end at the same offered destination: Atrebates, Carnutes, or
Mandubii. Multiple groups may start in one or several original Regions,
with at most four Legions in total. No response can introduce dropoffs,
other pieces, an accompanying Special Activity, or extra movement.
An empty `marches` list leaves the destination's existing force available
for Battle without flipping stationary Auxilia. Formation requests select
the actual visibility and physical owners; Diviciacus consent remains a
separate request for each Command. A refused loan returns to planning.

Litaviccus's combined force also participates in Retreat forecasts,
Counterattack casualties and Reveal. Borrowed loss entries retain their
physical owner, including Aedui static pieces or a Leader. Copy the offered
entry intact. Board inspection shows physical ownership. PR-12 changes only
the scoped non-player Belgic target forecast; it creates no new human
response format and does not limit a human's legal target choices.

Battle loss results include `losses_requested`, the full Loss total passed
to casualty resolution, alongside `losses_taken` and `losses_absorbed`.
Requested Losses can exceed the number of remaining counters; do not infer
the original total from removals alone.

Seize's successful Arverni and Belgae Rally checks issue separate
`free_action` requests with `request_type: "event_rally"`, `source: "seize"`,
`source_region`, `tribe`, and the actual `roll`. They permit free Rally in the
offered adjacent non-Devastated Regions, with no SA. Each successful grant
resolves before the next die or Forage; return an ordinary explicit Rally
plan, decline, or explicit default. In Ariovistus, the Arverni result uses
their game-run procedure rather than a player request.

Shaded Surus (51) sends `event_piece_choice` after `51.piece_choice`.
Respond `{"selections":[...]}` with up to four exact Aedui Warbands from
Treveri or one adjacent Region. Use the offered visibility cohorts.
An empty list selects zero. Author the same list in
`event_params.piece_choices`. Legacy `region` and `count` still work
together and delegate visibility. The Event skips a selected source that
leaves during its replacement window. If the German replacement is
unavailable, the Event still removes the surviving Aedui source. Older histories may pause
for the new choice or diverge under the corrected replacements.

If any newly placed Warbands survive, Surus gives the Event executor an
`event_command` request with
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

Cards 35 shaded, 46 shaded and numeric 67 accept initial Event parameters
`{"faction": beneficiary}` or an empty object. Empty parameters defer
beneficiary selection to the Event executor's live `gallic_event_beneficiary`
request. The recipient then owns its subsequent choices. Card35 sends
`gallic_command_order` followed by two ordinary `event_command` requests:
one full and one with `max_regions: 1`, in the selected order. Both exclude
Battle and Special Abilities. Card46 sends one free Command request without
a Special Ability; the original Event executor alone stays Eligible.
Neither card permits declining a possible mandatory Command. Explicit
`use_default` uses the implemented bot priorities; missing durable input remains pending.
Initial `stage_timing_actions` may also name the executor's outer Event
boundaries: `handler_complete`, the corresponding `grant.card_*` step,
`<card>.beneficiary`, `resolve_free_command`, `35.order`, `35.command`,
`35.limited_command`, `46.command`, or `67.accept`/`67.march`/`67.command`/
`67.hide`, as applicable to that card. They do not authorize the executor
to answer recipient-owned decisions.

For 35/46 shaded, the legal expansion Arverni beneficiary resolves under
[PR-10](docs/provisional-rulings.md#pr-10). Actual At War permits the first
possible allowed Command in A6.2 order, respecting grant limits; Battle
retains its inherent Ambush condition. At Peace produces a legal no-effect.
No human Command or order prompt belongs to this automatic faction.
Numeric 67's non-player Arverni plan follows
[PR-11](docs/provisional-rulings.md#pr-11): printed Roman NPC Retreat, a
conservative response comparison for human Romans, printed Defender-roll
forecasting and normal Vercingetorix Harassment safety. Live choices/dice
remain distinct from that forecast. The score retains default casualty
priorities; Frost separately checks legal human casualty and dice outcomes.
Both policies are provisional.

Card68 shaded sends `remi_event_effect` to the actual Gallic owner of Remi.
Only that owner can author `target_city`, decline, or the optional
`stage_timing_actions` at `68.citadel` and `68.warbands`. The initial plan
cannot preselect a foreign owner's response. The printed four Warbands
are placed as available; there is no count field. Original-executor
voluntary removal and independent owner Spring-entry rights remain separate.
The live menus expose current/next card information, per-seat changes and
`board`/`b`; detached previews do not consume the live RNG or human replies.

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
| `gallia_evacuation_order` | `owner_order: [faction, ...]` | `cards/gallia_evacuation.py`; A5 executor orders every affected owner exactly once |
| `gallia_evacuation` | `allocations: [{piece_id, destination, count, tribe?}]` | `cards/gallia_evacuation.py`; each affected owner allocates all its Cisalpina pieces |
| `expansion_event_choices` | A29 `faction, placements`; A36 `placements, ally_removals` | `cards/expansion_validation.py`; named beneficiary/German owner selects within the request's scope |
| `gallic_event_beneficiary` | `faction` from the request's `factions`, or sole `use_default: true` | `cards/gallic_event_grants.py`; executor selects for 35S/46S/67; no decline |
| `gallic_command_order` | `order: ["command", "limited_command"]` or the reverse, or sole `use_default: true` | `cards/gallic_event_grants.py`; Card35 beneficiary chooses; no decline |
| `remi_event_effect` | `target_city: "Alesia"` or `"Cenabum"`, optional `stage_timing_actions`; or sole `decline: true` / `use_default: true` | `cards/remi_event_effect.py`; Card68 shaded belongs to Remi's Gallic owner |
| `procillus_march` | `origin, destination` | `cards/procillus.py`; A19 executor moves all mobile Romans from one offered origin |
| `decisive_battle` | `region, defender` | `cards/decisive_battle.py`; A21/A57 first Battle, then optional second in the same Region |
| `fixed_event_battle` | `region, defender` from `defenders_by_region`, or sole `use_default: true` if available | `cards/fixed_event_battles.py`; scoped Battles on 11/25/36/45/70, with printed modifiers applied by the engine |
| `arduenna_faction` | `faction` from the request's `factions` | `cards/arduenna.py`; executor selects a playable beneficiary other than Arverni |
| `arduenna_accept` | Sole `accept: true`, `decline: true` or `use_default: true` | `cards/arduenna.py`; beneficiary decides the complete 67/A67 sequence |
| `arduenna_march` | Ordinary March action with explicit `origins, destinations, routes, groups` and optional `extra_groups` in `details.march_plan` | `cards/arduenna_march.py`; actual movement ending in Nervii/Treveri; normal transit dropoffs |
| `arduenna_command` | Ordinary non-March Command action | `cards/arduenna.py`; Nervii/Treveri only, no SA |
| `harudes_raid` | `raid_actions: [{region, target_faction}]` | `cards/harudes_bellovaci.py`; one entry per newly placed surviving Raider; null target means gain |
| `bellovaci_ambush` | `defender` | `cards/harudes_bellovaci.py`; A69 fixed Region and actual placed survivors |
| `roman_event_accept` | `accept: true` or `decline: true` | `cards/roman_event_grants.py`; Romans decide the entire A20/A58/70 benefit |
| `camulogenus_march` | `destination, marches` and optional `diviciacus_regions`; each group has `origin, route, legions, auxilia, caesar` | `cards/camulogenus.py`; Roman-owned numeric 70 March, one named destination, four Legions total |
| `roman_event_battle` | Ordinary Battle action with offered Regions and defenders | `cards/roman_event_grants.py`; A58, no SA |
| `roman_event_seize` | Ordinary Seize action with `details.disperse_tribes: {Region: [Tribe, ...]}` | `cards/roman_event_grants.py`; exact Tribes, ordered distinct Regions; empty lists mean Forage only |

Use `engine.free_actions.validate_free_action_response` for these subtypes
as well as ordinary grants. It returns an error string or `None`; do not
submit a custom subtype as a top-level Command. Subsequent Battle choices
arrive as their own requests on the resulting board. Unshaded Impetuosity's
adjacent March is required when possible; A17's follow-on Battle is required
when possible after the optional combined action has been accepted.

For unshaded Gallia Togata (A5), an executor receives
`gallia_evacuation_order` only when multiple non-Roman owners have pieces in
Cisalpina. Return every faction in the request's `owners` exactly once in
`owner_order`. Each owner then receives its own `gallia_evacuation` request
on the resulting board; game-run Arverni resolve automatically. The request
provides `acting_faction`, `origin`, `home_regions`, and `pieces`. Each piece
entry has an opaque `id`, `piece_type`, `count`, optional `piece_state`,
`tribe` or `leader_name`, and legal `destinations`.

Copy each source `id` to an allocation's `piece_id`. Allocate its entire
count using positive integers, splitting a visibility cohort if desired.
Each move has a `destination`; Allies/Citadels also require the destination
`tribe`. Use `destination: null` to remove pieces and omit `tribe` for that
allocation. For example, when these pieces and destinations are offered:

```json
{"allocations":[
  {"piece_id":"Warband:Hidden","destination":"Ubii","count":2},
  {"piece_id":"Ally:Nori","destination":null,"count":1}
]}
```

Later allocations cannot reuse an occupied Tribe or exceed Settlement limits.
German Settlement Regions count as Homes; Cisalpina itself never qualifies.
Relocation retains visibility and Leader identity. Both A5 requests allow
explicit default but forbid decline; an owner can instead choose removal.
Missing or invalid durable responses remain pending, including when earlier
owners already have accepted choices. Board inspection shows the current
decision position; save/resume replays accepted choices before continuing.

For A21/A57, `phase: first` requires a legal Battle and forbids Retreat;
`phase: second` offers a fresh defender choice in that same Region, permits
ordinary Retreat and may be declined. Human choices include legal static-only
Forces and are not restricted by NPC damage priorities. A19, A29 and A69
choices belong to the Event executor even when the commanded pieces belong
to another faction. This does not transfer casualty, consent or physical
piece ownership. A29 permits one or two actual placed Raiders per Region
(or the applicable Capability limit); residents cannot replace removed
placed pieces. A69 retains ordinary resident participation, but its one-Loss
bonus applies only to surviving new Warbands. An impossible Ambush cannot
silently become an ordinary Battle or be inherited entirely by residents.

Numeric 67's Arverni bot default retains a known
[maximum-Legion-loss prediction gap](QUESTIONS.md#q-arduenna-np-prediction--maximizing-legion-losses-across-uncertain-actions-2-november-2026).
It must not be described as a verified global optimum.

For numeric 67 and A67, the beneficiary may decline the entire sequence before any changes.
After acceptance, March and the subsequent non-March Command are required
when mechanically possible, then friendly pieces in Nervii/Treveri Hide.
March routes must actually move pieces into a destination; an in-place
selection is not a substitute. Selected groups retain their initial-origin
physical ownership and visibility through split routes, transit dropoffs,
Harassment and later voluntary removals. Arrivals cannot move again as
another origin's pieces. Scouted pieces lose their marker and remain Revealed
at each applicable Hide step. If a loan refusal invalidates an accepted
plan, only the unfinished stage is reopened on the current board.

The Roman controller accepts or declines A20/A58 before their effects,
regardless of who played the Event. Accepted components resolve in order
when possible, with new requests on the resulting board. A20 removes all
Arverni in Veneti before Seize; A58 offers Battle then Seize in Belgica.
The engine-owned Seize request supplies the printed Control override and
no-Rally exception; only A58 also suppresses Harassment. Responses cannot
grant these exceptions, add an SA or use `command_parts` to escape scope.
Optional `details.diviciacus_regions` remains available. An actual loan
refusal reopens a required component; retry requests retain `attempt` and
`previous_error` and refresh current legal targets.

For requests with engine-owned `validate_default_response: true`, durable
sessions validate and preserve explicit `{"use_default":true}`. A default
that would skip a mandatory legal human action is rejected. This differs
from the raw callback's documented `None` fallback; missing durable input
always leaves a decision pending. These new prompts can require additional
choices when replaying an older affected transcript.

Kinship uses the separate `kinship` kind, selecting the attacker and any
eligible Battle Regions together. Its Battle excludes the attacking Leader
from fighting and losses without moving that physical piece. The validator
is `cards.kinship.validate_response(state, response)`.

### Sequence-of-Play Resource transfers

During an outer Command or Event, an eligible human donor may give Resources
when the executing faction is either participant. A donor other than the
executor sees only the executor as a possible recipient. Each request carries the donor's `faction`,
`available` stock and maximums in `recipients`. The `window` identifies the
`actor`, `action`, `card`, `stage` and its `occurrence` in the action. A
Region, step, or index may identify a live operation more precisely.

The terminal opens negotiations after the action type is selected, before
collecting its plan. The assistant asks after accepting the authored turn plan,
before executing its first Command or Event effect. Both can offer additional
gifts at complete operation boundaries and before the action closes. Include
`"defer":true` alongside the `transfers` list to ask for another offer later
in the action. An empty list without `defer` or an explicit default ends this
donor's offers for the action. A nested grant retains the outer executor's
transfer scope. A53 keeps ordinary Roman gifts in the public treasury and
resolves them between the grant's funded actions.

Each gift must fit the current stock and recipient room, including earlier
gifts in the list. The two Factions of one player can exchange a combined
four Resources per outer Command or Event. Earlier authored and live gifts
count against that allowance in both directions. Gifts apply in list order.
An invalid durable list leaves the same decision pending. Accepted gifts
participate in the action's transaction and replay. A dry-run uses authored
opening gifts and can report what the current board can fund without future
donor decisions.

### Winter Resource transfers

Each eligible human donor gets a `resource_transfer` request before
Quarters relocations and after Roman payments, and before and after
Harvest earnings. The `window` names its `phase`, `stage`, and `winter`
number. The donor can give to multiple recipients or repeat a recipient
within the offered limits. The entire list must fit the donor's `available`
stock and each recipient's cumulative cap. The shared-player allowance
applies only during the Sequence of Play. Use `{"transfers":[]}` or
`{"use_default":true}` to give nothing. Later donors see the updated balances.

The engine applies opening Quarters gifts before the Roman plan is
collected, so Romans can spend them on payments. Opening Harvest gifts
can make room for earnings, and closing gifts can use those earnings.
An invalid list leaves the request pending. Accepted gifts replay once
when the phase resumes. Existing transcripts can replay their recorded
choices using the no-gift default for absent transfer requests.

The terminal and file-based assistant enable these requests by default.
A custom reactive agent can opt in with `supports_resource_transfers = True`
for live Sequence-of-Play and Winter resolution.

### Quarters

A `quarters_plan` response maps the acting faction to relocations:
`{"Belgae":[["Warband","Morini","Atrebates",2,"Revealed"]]}` is a shape example.
Entries are `[piece_type, origin, destination, count, visibility]` for exact
Hidden/Revealed/Scouted Warband or Auxilia cohorts. Visibility is preserved;
this is relocation, without March's hiding procedure. Counts must be positive
integers and fit the selected physical cohort, including repeated entries.
Legions and Leaders use four entries without visibility. Legacy four-entry
Warband/Auxilia rows remain supported and consume Hidden, then Revealed, then
Scouted pieces. Mixed legacy/exact rows reserve cohorts in plan order.
Legality also depends on the current board and any host agreement. `{"Belgae":[]}` chooses no
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
adjacent moves stay completed. `legal_moves` retains four-entry summary rows
whose final count is the maximum offered across all visibility cohorts.
Response moves accept the same optional fifth visibility as `quarters_plan`;
aggregate counts must fit both that maximum and live selected cohorts.
Explicit default retains only still-legal original moves and their exact
visibility, trimming or dropping unavailable cohorts without substituting
another visibility. Decline chooses none. A changed relocation outcome then requests
`quarters_payment` for the pieces actually left outside Provincia, before
payment or loss rolls. Explicit default uses standard payments.

### Ordinary Seize Tribe choices

Human Seize plans use `details.disperse_tribes`, mapping every selected Region
to its ordered list of exact Tribe names. An empty list explicitly chooses
Forage without Dispersal:

```json
{"command":"Seize","regions":["Mandubii","Carnutes"],"sa":"No SA","sa_regions":[],"details":{"disperse_tribes":{"Mandubii":["Lingones"],"Carnutes":[]}}}
```

Tribes must belong to their selected Region and lists must be distinct.
Missing maps, null/malformed lists, extra/missing Region keys and mixed
`disperse_tribes`/legacy `disperse_regions` contracts are rejected. Interrupted
Seize uses a separate exact map in each of its two actual Command portions;
fictitious/nested portions cannot conceal an unselected dispersal plan.
Current Subdued status, Roman Control and the shared four-marker limit are
rechecked at each Region's resolution after preceding effects. Invalid live
choices are not silently replaced or truncated. Forage-only remains legal
when no markers remain or Romans lack Control but still have pieces there.

Both ordinary terminal paths offer every legal Tribe even if only one marker
remains, reserve markers across ordered Regions, retain `b`/`board`, and
estimate Forage without rolling Rally or Harassment dice or consuming live
input/RNG. Intervening Rally/timing effects can still change later eligibility.
Accepted named plans persist through Rally pauses, save/resume and journals.
Arduenna's mechanical witness and the synthetic human-policy builder emit the
same exact contract. The latter now puts selected Regions in `regions`,
rather than leaving them unused in `details._regions`.

NPC legacy `disperse_regions` plans keep their automatic selection path;
raw legacy mechanical callers remain supported. Human submissions need the
exact map, so old human transcripts may need adjustment. Save schema is
unchanged and exact cross-revision replay is not promised. Event-specific
Control, Rally and Harassment exceptions still require trusted grant scope;
ordinary exact maps cannot supply those exceptions themselves.

### Rampage quantity

For a human Rampage, each `sa_regions` entry supplies `region`, `target` and
an explicit positive integer `count` of Hidden Belgic Warbands to Reveal:

```json
{"command":"Rally","sa":"Rampage","sa_regions":[{"region":"Treveri","target":"Romans","count":1}],"details":{"rally_plan":{"steps":[{"region":"Treveri","action":"place_warbands","count":0}]}}}
```

The full Rally/Rampage plan still needs its normal legal prerequisites.
Count may exceed two, up to both current Hidden Belgic Warbands and the
eligible target Warbands/Auxilia/Legions. Availability is checked when Rampage
resolves, after its preceding Command/timing actions. An overlarge quantity
is rejected rather than reduced. Omit a Region to decline Rampage there;
each selected Region is one nonempty application against one target Faction.
Repeated Regions and missing, zero, Boolean, fractional or malformed human
counts are invalid. Durable missing choices remain pending. Both terminal
planners author the field, retain board inspection and preview the chosen
quantity without changing the live board.

Legacy NPC/default entries without `count` use all able Hidden Warbands per
§8.5.1. For NPC-controlled Belgae, the before-Battle default leaves at least one
enemy piece; that NPC restriction does not clamp an explicit human count. This corrects the former
artificial two-Warband default and can change bot outcomes. Save schema is
unchanged, but older human plans need the field and cross-revision replay is
not promised. A paused victim request carries the exact quantity in
`context.num_pieces`; accepted actor plans keep their count through save/resume.

The target's `retreat` request also includes `pieces`, a list of eligible
`[piece_type,piece_state]` pairs, repeated for separate counters. Respond with
one exact disposition per `context.num_pieces` and one shared destination.

```json
{"actions":[{"action":"remove","piece_type":"Legion","piece_state":null},{"action":"retreat","piece_type":"Auxilia","piece_state":"Revealed"}],"retreat_region":"Atrebates"}
```

Each action is `remove` or `retreat`. A removal-only response uses
`retreat_region:null`. Every Retreating piece uses the same offered Region.
Choose only offered physical cohorts, including exact visibility. This is the
target's response, supplied through its reactive channel. It is independent of
the Belgic actor's chosen count. Missing, incomplete, stale or overclaimed
fresh durable responses remain pending. Explicit default delegation is allowed.

Host consent is requested once for each candidate refuge. Rampage excludes
No Control and Germanic Control. Expansion Arverni cannot Retreat or agree to
a Retreat into their Control. The low-level operation validates all actions
before flipping Warbands and restores on failure.

Raw adapters can retain all-or-none `{"retreat":bool,"region":...}` responses
and the established default physical subset. Older durable journal entries,
pending prompts and replay expectations can finish that recorded contract only
on their matching original board and legal options. New durable requests use
exact actions. Older terminal replays containing two recorded rounds of host
consent may need that Rampage segment recorded again.

### Other paid and optional grants

Ordinary German Intimidate uses one or two Hidden Warbands per Region;
shaded Dread (A22) permits one added Warband to remove one extra piece,
for up to three. Its capacity is the lesser of that limit and the eligible
Hidden Warbands actually present. In `details.intimidate_plan`, provide one
entry per removed piece, each with `region`, `target_faction`, `target_piece`
and `target_state`. Each human Ally removal also requires `target_tribe`,
naming that Faction's actual disc in the selected Region. A City represented
by a Citadel is not an Ally target. Duplicate, foreign, absent, null or
non-Ally Tribe fields are invalid. All removals in a Region are validated
before any Reveal or marker placement. An ordinary three-removal plan needs three Hidden
participants; do not add `extra_warband` or invent Raid credit. Normal Region,
one-target-Faction, no-enemy-Leader and eligible-piece restrictions still apply.

After Germanic Warbands Raid with Ariovistus, `raid_intimidate` offers their
optional free Intimidate. The pending board shows the completed Raid's
Resources and revealed Warbands before the choice. `raiders` is the number
that actually Raided. Without shaded Dread, `max_removals` is the lesser of
that number and two, even if Baggage Trains allowed three Raiders.
Each offered target has `target_faction`, `target_piece`, `target_state`, and
`available`. Ally options additionally contain `target_tribe` and have
`available: 1`. Return the identity fields, including `target_tribe` for an
Ally; repeat a mobile-piece entry only up to its available count. All chosen pieces must belong to one
Faction with no Leader in the Region. For example:

```json
{"targets":[{"target_faction":"Romans","target_piece":"Auxilia","target_state":"Hidden"}]}
```

Ordinary, Raid-linked and A45 Intimidate menus select the named disc. Durable
human submissions missing an Ally's Tribe stay pending; Event-grant plans
also require the field. Unnamed bot plans and legacy low-level/raw Raid
callbacks retain the established sorted default. Direct `intimidate` calls
accept `(ALLY, None, tribe)` as well as legacy `(piece_type, piece_state)`
pairs. Results retain `target_removed` and add `target_details` with the
resolved `piece_type`, `piece_state` and `tribe` (null for non-Allies).
When mixing legacy unspecified and named discs, named targets are reserved
before automatic allocation. Save schema is unchanged; older human submissions
may need the new field, and cross-revision transcript replay is not promised.

An empty `targets` list places only the Intimidated marker. Decline leaves
the Raid intact, while explicit default uses the German bot's priorities.
This effect does not consume a Special Ability. With shaded Dread, the
request distinguishes the following capacities:

| Field | Meaning |
|---|---|
| `max_raider_removals` | Removals using actual Raiders alone, up to three |
| `extra_warband_available` | Whether one additional eligible Hidden Warband remains |
| `max_with_extra` | Removals using that fresh Warband plus at most two actual Raiders; zero if unavailable |
| `max_removals` | Maximum across those two choices |

A plain `{"targets":[...]}` response uses Raiders alone. Add
`"extra_warband": true` to Reveal one additional Hidden Warband for one
extra removal. This requires shaded Dread, an available eligible counter,
and two or three removals within `max_with_extra`. `false` is accepted;
non-Booleans, extra Reveals for marker-only/one-removal responses and invented
credits are rejected. Three actual Raiders can supply three removals with
Dread without a fourth Warband. A29's additional participant must belong
to its surviving newly placed cohort; its Event executor owns the choice.
A subsequent ordinary Intimidate uses remaining Hidden participants and
cannot reuse Raider credit or the newly Revealed bonus participant.

Unshaded Dread protects Romans from both Intimidate removals and Intimidated
markers blocking Recruit. It does not waive other Recruit restrictions.
The active Capability side takes precedence over stale legacy modifier data.

The validator
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
from fs_bot.engine.agent import RETREAT, RETREAT_DISPOSITION, AGREEMENT

def reactive(state, faction, request):
    if faction != MY_FACTION:
        return None                       # let the bots handle the rest
    if request["kind"] == RETREAT:
        legal = request["legal_regions"]
        if request.get("stage") == "declare":
            return {"retreat": bool(legal)}
        return {"retreat": bool(legal), "region": legal[0] if legal else None}
    if request["kind"] == RETREAT_DISPOSITION:
        return request["default"]
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
  Raid Intimidate, Kinship, scoped Event-granted actions, and donor-owned
  Resource gifts during Commands, Events, Quarters, and Harvest.
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

For `init --seat Romans,Aedui` and the other printed pairs, the saved
`player_id` owns both Factions in one session. The pending request's
`faction` names the Faction making that decision. The same ID is used on
resume and replay, including when Germans become Arverni at the Interlude.

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
a correction, including previously omitted Seize Rally effects or historical
Battle requests that offered both casualty tiers, can fail
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

### German Interlude force adjustments

The German seat receives `german_permanent` and `german_quarter` before it
becomes Arverni. For an `interlude_reduction` request, copy rows from `cohorts` into `{"removals":[...]}`, setting each `count` to
a positive number within that cohort's capacity. Rows have `region`,
`piece_type`, `piece_state`, `tribe`, and `count`. Warband cohorts name
their visibility. Ally rows name an exact Tribe with a count of one.

- `german_permanent` removes exactly 15 Warbands from play. The Available
  row has null `region` and `piece_state`. Select from the map and Available
  in any order.
- `german_quarter` uses the board after Settlement conversion. Return at
  least the requested count of each type to Available. Within each type,
  exhaust the cohorts outside Germania before selecting a cohort in
  Germania. Multiple rows from the same cohort share its offered count.

Between these stages, `interlude_settlements` offers German Ally
placements when there is a choice. Its `options` maps German-controlled
Settlement Regions to eligible Subdued Tribes. Assign exactly
`required_allies` in `{"allies":{"Mandubii":"Lingones"}}` form, with one
offered Tribe per selected Region. When discs are scarce, select which
Regions get them. Remaining Settlements convert to up to three Hidden
Warbands each from Available. Forced allocations resolve automatically.

Each request accepts `{"use_default":true}` to delegate to the bot. An
invalid allocation leaves the request pending. If Winter pauses, earlier
answers stay in the journal and replay against the restored board when
Winter resumes. Older German-seat transcripts may pause for new requests
when replayed.

### Belgic Interlude force reduction

Belgae receive the `belgic_half` stage of `interlude_reduction`. Use the
same ordered `{"removals":[...]}` contract or delegate with
`{"use_default":true}`. Select at least the offered minimum of each type.
Belgica goes last within each type. Choose Allies by Tribe and Warbands
by Region and visibility. The surviving forces determine where Ambiorix
is placed. If a tie needs a `spring_leader` response, the earlier Belgic
allocation is retained when Winter pauses.

### Aedui Interlude force adjustments

After Diviciacus leaves play, `interlude_aedui_citadel` is offered if more
than one Citadel can be selected. Respond with one offered Region. Bibracte
is eligible only when it is the sole Citadel. The chosen Citadel becomes
an Ally when a disc is Available and is removed otherwise. A sole eligible
target resolves automatically.

Aedui then receive `aedui_half` in `interlude_reduction`. Use the ordered
`{"removals":[...]}` contract to meet each offered minimum, taking the
Aedui Region last for each type. The cohorts and counts reflect the
Citadel step. Either request accepts `{"use_default":true}`. A save at the
reduction prompt retains the accepted Citadel selection.

### Arverni Interlude force adjustments

The German seat controls this adjustment before the faction handover.
`interlude_arverni_citadels` requests an ordered list of exactly `count`
distinct offered Regions, normally two. Gergovia goes last. Available
Ally discs replace the selected Citadels in response order. Any selected
Citadels without replacement discs are removed. Forced selections resolve
automatically unless order determines which Citadel gets a scarce disc.

The German seat then receives `arverni_half` in `interlude_reduction`.
Its `faction` identifies the German controller, while its cohorts contain
Arverni pieces. Use the usual ordered `{"removals":[...]}` contract to
meet each minimum. Take the Arverni Region last within each type, with
an exception allowing the Cadurci and Volcae Ally discs to be selected
early. That exception applies only to those named discs.

Either request accepts `{"use_default":true}`. Saving while awaiting
the reduction retains the earlier German removals and Arverni Citadel
choices. Older German-seat transcripts can pause for the added prompts.

### Roman Interlude force reductions

Romans receive `roman_half` in `interlude_reduction` during Adjust Forces.
Submit `{"removals":[...]}` in selection order. Meet the separate rounded-up
minimums for Forts, Allies, and Auxilia. Forts are listed by Region, Allies
by Tribe, and Auxilia by Region and visibility. Provincia's permanent Fort
and all Legions are excluded. Take Provincia last for Allies and Auxilia
independently. `{"use_default":true}` delegates the selection to the bot.
Any available Caesar is placed using the resulting board.

### Interlude Cisalpina relocation

Unless Gallia Togata is active, Cisalpina is cleared in order by Germans,
Belgae, Aedui, Arverni, and Romans. The German seat makes both its own and
the Arverni allocations. `faction` identifies the controller, while
`acting_faction` identifies the physical owner. Each request reflects the
board after earlier owners have finished.

Allocate every offered piece using `piece_id`, `count`, and `destination`.
Split cohorts as desired. Use an offered Home Region to move a cohort, or
`null` to remove it. Moved Allies and Citadels require an offered `tribe`.
Those slots must still be free when reached in the allocation. Visibility
and Leader identity carry over to the destination. `{"use_default":true}`
uses the existing remove-all procedure. A faction whose pieces have no
legal destination resolves automatically. The next expedition request
lists the resulting Roman forces.

### Roman Interlude allocations

`interlude_expedition` belongs to Romans. The request lists Legion counts by
Region and Auxilia cohorts with `region`, `piece_state` and `count`, using the
board after Adjust Forces and Cisalpina relocation. When the expedition is
possible, answer `{"conduct":false}` or provide its entire allocation.

```json
{"conduct":true,"harvest":{"Provincia":3},"legions":{"Morini":3},"auxilia":[{"region":"Morini","piece_state":"Revealed","count":1}]}
```

`harvest` must total exactly three. `legions` must total at least three, and
its combined counts with `harvest` must fit each offered Region. `auxilia`
selects at least one exact offered counter. Repeated cohort entries share the
same physical capacity. The Roman Leader moves to Britannia automatically
when conducting. A missing or invalid durable response remains pending.
If the force is insufficient, the printed decline consequence applies.

`interlude_marker` is offered when an eligible marker exists. Select one of
its named Tribes, or `{"tribe":null}` to preserve none. The chosen face survives
Spring. A later prompt can pause while accepted reduction, relocation and
expedition choices remain in the journal. Replaying the transaction applies
each once.

For either request, `{"use_default":true}` explicitly delegates to existing
NPC behavior. Raw `None` callbacks retain their fallback behavior. The raw
`britannia_decision=True/False` API and a raw conduct-only true dictionary
retain their minimum-force defaults. Durable human expedition responses need
the complete allocation or explicit default. Unsupported allocation fields
that older raw calls silently ignored are now rejected. Raw
`roman_dispersed_keep` validates that the named Tribe has an eligible marker.
Older saves that already reached a later Roman Interlude prompt retain the
automatic reduction and relocation used to reach it. Verified replays check
the original board and request before reusing recorded choices.

### Physical Battle casualty entries

New human `loss_order` requests offer ordinary flippable pieces as
`[piece_type,piece_state]`, such as `["Warband","Revealed"]`. Copy the offered
entries into an ordered response list. Repeated entries represent separate
counters and may be selected only as often as offered. A hard piece that saves
can be selected again in the following Loss request.

An ordinary Ally disc is `["Ally",null,null,tribe]`. The third position is a
physical owner when a combined force uses one, giving
`["Ally",null,"Aedui",tribe]`, for example. The fourth position of an Ally
entry names its actual Tribe. Elite Warbands retain their existing fourth
`"elite"` tag. A City whose disc has become a Citadel is excluded from Ally
disc choices. Legions, Leaders, Forts, Citadels and Settlements retain their
existing shapes and saving-roll rules.

Fresh durable responses must use the exact offered entries or explicit default.
A stale visibility, invented Tribe, foreign owner or overclaimed duplicate
remains pending. Raw explicit generic priority lists keep their wildcard
meaning within the legal current tier. Raw callbacks may defer normally.

Recorded old casualty journals, replay expectations and pending prompts can
finish with their older generic entries only when the original board signature
and the rest of the request match. The compatibility path changes only the
added ordinary physical distinctions and retains the recorded response and ID.
A changed board or unrelated request cannot use that path. New decisions
continue using exact physical choices.
