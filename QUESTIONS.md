QUESTIONS.md — Ambiguities and their resolutions

These items were identified during implementation when the Reference Documents
appeared ambiguous, contradictory, or silent. They have now been resolved by
re-reading the Reference Documents closely (the only permitted source of truth
per CLAUDE.md). Each entry records the question, the reference basis for the
answer, and the resulting implementation. No open questions remain.

---

## [RESOLVED] German bot — G_MARCH_THREAT "at victory" threshold for Aedui/Belgae

**Context:** A8.7.1 G_MARCH_THREAT destination priorities reference faction
victory state. The Roman clause says "if the Romans are at victory (have a
margin of 1 or better, 7.3)"; the Aedui/Belgae clause says only "if either
Aedui or Belgae (or both) are at victory" with no parenthetical number.

**Resolution:** Margin >= 1 for Aedui/Belgae (unchanged — the existing code is
correct). §7.3 defines a victory margin as "the amount a Faction is beyond or
short of its condition" and states "The margin will be positive if the Faction
has reached its goal, negative or zero if not." So the defined term "at
victory" = has reached its goal = positive margin = margin >= 1. The Roman
parenthetical "(margin of 1 or better, 7.3)" merely restates that §7.3
definition the first time the sentence uses it; the Aedui/Belgae "at victory"
in the same sentence is the same defined term. The deliberately looser phrase
"victory margin of 0 or better" appears only on the *march-trigger* clause,
confirming by contrast that the destination-priority "at victory" is the
stricter >= 1.

**Files:** `fs_bot/bots/german_bot.py` — `node_g_march_threat` (no change).

---

## [RESOLVED] German bot — G_AMBUSH eligibility (Ariovistus proximity)

**Context:** A8.7.1 AMBUSH says the Germans Ambush "where ... can Ambush in
any of those Battles" plus a strategic gate. The earlier note looked for a
proximity requirement in the *bot flowchart* (A8.7.1) — as the Belgae bot's
§8.5.1 has — found none, and so implemented Germanic Ambush with no
proximity layer.

**Resolution:** Proximity to Ariovistus DOES apply; "can Ambush" defers to the
Germanic Ambush Special-Ability rules, which carry the proximity requirement:

- **A4.6.3:** "Germanic Ambush in Ariovistus ... [works] like Arverni Ambush
  in Falling Sky (4.3.3) but uses Germanic instead of Arverni pieces
  (including Ariovistus instead of Vercingetorix)."
- **§4.3.3:** an Ambushable Region must "both begin with more Hidden Arverni
  than Hidden Defenders **and** occur either within one Region of Vercingetorix
  or in the same Region as his Successor." With A4.6.3's substitution, read
  "Germanic ... Ariovistus" — so the Region must be within 1 of Ariovistus (or
  hold his Successor).
- **A4.1.2 (Ariovistus)** independently confirms it: "German and Aedui Special
  Abilities may select only Regions within a distance of 1 Region of that
  Faction's named Leader ... or (for Germans) the same Region that has its
  Successor Leader."

The proximity requirement is therefore a Special-Ability rule, not a bot-layer
rule — which is exactly why the SA execution layer (`validate_ambush_region`)
already enforces it for `GERMANS` in Ariovistus. The bug was only that the
German bot's `_check_ambush` heuristic did not mirror that check (unlike the
Belgae and Aedui bots), so it could propose Ambushes the engine would reject.

**Implementation:** `_check_ambush` now calls `validate_ambush_region` (the
single authoritative eligibility check — Hidden-count + proximity) for the 1st
Battle and for each subsequent Battle, matching the Belgae/Aedui pattern.
Added `TestGermanAmbushEligibility` (5 tests) covering out-of-range, in-region,
adjacent, insufficient-Hidden, and multi-Battle filtering.

**Files:** `fs_bot/bots/german_bot.py` — `_check_ambush`;
`fs_bot/tests/test_german_bot.py`.

---

## [OVERTURNED — see the July 2026 BGG-ruling section at end of file] Gallic War Interlude — Diviciacus card identifier (A38 vs O38)

**Context:** A Scenario: The Gallic War, Interlude > Deck step: "Use the
Ariovistus expansion version of Diviciacus, card A38." But in the A Card
Reference, A38 is **Vergobret**, while the Diviciacus-Leader card is **O38**.

**Resolution:** O38 is correct (unchanged — the existing code is correct);
"A38" in the Interlude prose is an error. Three independent reference points:

1. The descriptive phrase matches O38 verbatim. A Setup, "Diviciacus Leader
   Option": "Original Falling Sky can use the expansion version of card 38,
   Diviciacus 2nd Ed, with the Diviciacus Leader piece and rules in A1.4." The
   A Card Reference keys this card as **O38. Diviciacus** ("Place Diviciacus
   piece in any Region. Ariovistus Diviciacus Leader rules apply").
2. A38 (Vergobret) is a different card — a Suborn Capability — that does **not**
   place the Diviciacus piece.
3. Game-state necessity: the Interlude's Aedui step removes the Diviciacus
   piece "(It may return by Event.)", and the second half plays with Diviciacus
   Leader rules. Only O38 can return the Diviciacus piece by Event; A38 cannot.
   So the deck must contain O38.

The "A38" label is best explained as a draft artifact (the Diviciacus-Leader
card was relabeled O38 once the A38 slot became Vergobret).

**Files:** `fs_bot/rules_consts.py` (`INTERLUDE_DIVICIACUS_CARD = "O38"`),
`fs_bot/engine/interlude.py` (no change).

---

## [RESOLVED] Gallic War Interlude — A8.8.9 (non-player Britannia expedition)

**Context:** Interlude > Britannia Expedition: "Non-player Romans conduct it if
able, A8.8.9." Chapter A8 in the references ends at A8.8.8 (Admagetorbriga)
and then jumps to A8.9 — there is no A8.8.9.

**Resolution:** The cited rule is genuinely absent, so there is no extra
strategic/score criterion to apply. "If able" is therefore resolved against the
physical requirements the scenario itself enumerates: the Romans must relocate
3 Legions to the Harvest-Phase box **plus** the Roman Leader, 3-or-more further
Legions, and 1-or-more Auxilia to Britannia. Non-player Romans conduct the
expedition iff they hold those pieces on the map: >= 6 Legions, >= 1 Auxilia,
**and** the Roman Leader.

**Implementation:** `_np_should_conduct_britannia` already checked the Legion
(>= 6) and Auxilia (>= 1) minimums; added the missing Roman-Leader-on-map check
(the scenario lists "plus the Roman Leader ... from the map to Britannia").
Added `TestBritanniaNonPlayerAbility` (2 tests).

**DESIGNER-CONFIRMED (July 2026, BGG thread 3732430):** Volko Ruhnke:
the "A8.8.9" reference "is spurious, rather than any rules section
having gone missing. The page 17 rule appears complete and
self-contained: Non-player Romans choose to do the Britannia
Expedition if they can by the page 17 Rule" — a drafted NP-Roman rule
was folded into page 17 and the dangling reference never removed. No
additional criteria exist; the engine's "if able" reading is exactly
the rule. The earlier NOTE about future extension is closed.

**Files:** `fs_bot/engine/interlude.py` — `_np_should_conduct_britannia`;
`fs_bot/tests/test_interlude.py`.

---

## [RESOLVED] Gallic War Interlude — Belgic Leader identity (Ambiorix vs Boduognatus)

**Context:** The first half (Ariovistus) names the Belgic Leader piece
**Boduognatus** (A1.4). Interlude > Adjust Belgae: "Place Ambiorix in Region
with most other Belgic pieces (even if Belgic Leader in Available)."

**Resolution:** Re-tag the piece to **Ambiorix** (unchanged — the existing code
is correct). The Interlude prose names the leader "Ambiorix" explicitly, and
the Second Half section states "Original Falling Sky rules are in effect" —
under which the Belgic Leader is Ambiorix. The physical piece is the same; only
its rules identity changes for the second half.

**Files:** `fs_bot/engine/interlude.py` — `_adjust_belgae_forces` (no change).

---

## [RESOLVED] Gallic War Interlude — Removed-from-play container for non-Legion pieces

**Context:** Interlude > Adjust German Forces: "Remove Germanic Leader and any
15 Germanic Warbands (including from Available) from play." Per CLAUDE.md,
"remove from play" means permanent removal (not to Available). Only Legions had
a dedicated off-board container (`state["removed_legions"]`).

**Resolution:** This is an internal schema choice, not a rules ambiguity — the
references are clear that the pieces leave play permanently. The chosen
convention (generic `state["removed_pieces"][faction][piece_type]`, with Legions
keeping their rules-mandated separate track and Diviciacus its existing
special-case path) is sound and is fully reconciled by `validate_state`, which
includes `removed_pieces` in the cap totals for Leaders and all non-Legion
piece types. No change required.

**Files:** `fs_bot/state/state_schema.py` (`validate_state`, schema init),
`fs_bot/engine/interlude.py` (no change).

---

## [RESOLVED] Card A31 (German Phalanx) unshaded — scope of "Event effects benefitting Germans in Battle are cancelled"

**Context:** A31 unshaded reads: "Event effects benefitting Germans in Battle
are cancelled, and Ariovistus does not double Losses." The first clause is
generic and does not enumerate which effects it targets, which raised the
question of how to implement it faithfully.

**Resolution:** Grounded in the Battle engine, not a guess. `resolve_battle`
(`fs_bot/battle/resolve.py`) and `calculate_losses`
(`fs_bot/battle/losses.py`) read exactly one persistent German-favoring Battle
benefit: the Ariovistus doubling of Losses. A31 cancels precisely that via the
`card_A31_no_ario_double` flag (checked in both modules). Every other event
Battle modifier in the executor (double_auxilia, auto_legion_loss, extra
losses, ignore_fort/citadel, ally_first, etc.) is applied only as an explicit
argument inside the same card's free-Battle resolution; none is read from
`event_modifiers` during arbitrary later Battles, so none persists as a
standing German benefit for a separately-played A31 to cancel. The generic
clause therefore has no additional modeled referent. `card_A31_cancel_german_benefits`
is set for completeness and documented at the flag site; A31's concrete
mechanical effect (the no-double) is fully implemented and tested.

**Files:** `fs_bot/cards/card_effects.py` (`execute_card_A31`, documenting
comment), `fs_bot/battle/resolve.py` and `fs_bot/battle/losses.py`
(`card_A31_no_ario_double` consumption).

---

## [RESOLVED] Card 42 (Roman Wine) shaded — what is a "Roman-Aedui Supply Line"

**Context:** Card 42 shaded removes 1-3 Roman or Aedui Allies "from Roman-Aedui
Supply Lines." The Tips clarify: "Shaded Roman-Aedui Supply Lines are any
Regions that would at that moment be in Supply Lines (3.2.1) if Romans and Aedui
both agreed." The question is which Regions qualify when computing §3.2.1 supply
for this removal.

**Resolution:** A §3.2.1 Supply Line is a chain of adjacent Regions reaching the
Cisalpina border (base) / including Provincia or Cisalpina (Ariovistus), each
chain Region having No Control or Control of a Faction that agrees. The card
fixes the agreement question by hypothesis: "if Romans and Aedui both agreed."
So the qualifying chains are those where every Region is No Control, Roman
Control, or Aedui Control — Romans and Aedui agree; any other controlling
Faction does not (a chain through an enemy-controlled Region is not a Roman-Aedui
Supply Line). This maps exactly to `has_supply_line(state, region,
faction=ROMANS, agreements={ROMANS: True, AEDUI: True})` (the existing
`agreements` dict defaults non-listed Factions to False). The deriver removes
only *enemies'* Roman/Aedui Allies (§8.2.3 — never the acting Faction's own).

**Files:** `fs_bot/engine/execute.py` — `_derive_card_42` (shaded branch).

---

## [RESOLVED] Free Command "in/from <named Region>" — which Command when the flowchart's board-wide best cannot act there

**Context:** Several Events grant a free Command restricted to a named Region or
set of Regions (e.g. card 70 "select 1 [of Atrebates/Carnutes/Mandubii] for a
free Command + Special Ability"; card 9 "in (or from) the destination Region").
The faithful free-Command chooser is the Faction's own flowchart (NP guideline:
"For free Commands and Special Abilities, follow their flowcharts"). The
flowchart returns the Faction's board-wide best Command; when that Command's
plan lies entirely outside the named Region(s), constraining it yields nothing —
so previously the free Command silently did not occur (~64% of restricted calls
in all-bot games).

**Resolution:** Still "follow the flowchart," now region-aware. When the
board-wide best Command cannot act in the allowed Region(s), evaluate the
Faction's Command nodes in *flowchart-decision order* (the order its own tree
considers Commands — e.g. Roman Battle → March → Recruit → Seize; Aedui Battle →
Rally → Raid → March; the analogous orders for Arverni/Belgae/German), constrain
each to the allowed Region(s), and take the first whose plan is legal there.
This is the Faction's own command priority applied to the named Region — not an
invented heuristic. Command nodes are read-only planners; they are evaluated on
a deep copy because they consume `state["rng"]` for §8.3.4 tie-breaks, keeping
the real RNG stream deterministic. If no Command is legal in the Region(s), the
free Command faithfully does not occur.

**Files:** `fs_bot/engine/execute.py` — `_region_restricted_free_command`,
`_FACTION_COMMAND_NODE_ORDER`, `_resolve_free_command`.

---

## [RESOLVED] Human execution path — execution layer + CLI plan-collection menu

**Context:** `execute_decision` applies a plan from either `bot_action` (bot) or
`player_action` (human/UI); a mixed human/bot game resolves human turns through
the same Command/SA/Event machinery (human Events use the player's own
`event_params` rather than NP auto-derivation).

**CLI menu:** `fs_bot/cli/human_plan.py::collect_player_action` collects a full
human plan (Command + Regions + targets, optional Special Activity, or Event
side), presenting only legal choices; `menus.prompt_action` attaches it as
`player_action`. All six Commands and Event side selection are playable end to
end. If scripted input ends mid-plan, prompt_action falls back to the action
type (graceful — execute_decision then reports "no executable plan").

**Documented scope limits (faithful, not bugs):** the Event menu collects the
side but not per-card Event params — cards that need a player choice of
parameters rely on `details['event_params']` being supplied by a richer
front-end (self-resolving cards work as-is). Plan-based Special Activities
(Intimidate/Suborn/Rampage/Entreat) are taken as `sa` + `sa_regions`; their
detailed target plans use the executor's recompute fallback rather than a
per-target human menu. Both are natural extension points, not correctness gaps.

**Files:** `fs_bot/engine/execute.py` (`execute_decision`, `_execute_event`),
`fs_bot/cli/human_plan.py`, `fs_bot/cli/menus.py`.

---

## [RESOLVED] Dispersed/Subdued stored in tribe["status"], not the markers dict — bug-class sweep

**Context:** During review of the card 22/68 fixes, a systemic bug class surfaced.
Disperse (and Razed) are canonically stored in `tribe["status"]` (= `Dispersed`
/ `Dispersed-Gathering` / `Razed`; set by Seize, setup, card 23; read by
seize.py, rally.py, victory.py, interlude.py). Nothing ever writes a Disperse
marker into `state["markers"][tribe]` — that dict is only ever *popped*. Several
card handlers tested or cleared Disperse against `state["markers"]`, so the check
was dead (a Dispersed Tribe read as Subdued; a "remove Dispersed" del was a
no-op). A Subdued Tribe is one that is neither Allied nor Dispersed (Key Terms
Index) = `allied_faction is None and status is None`.

**Resolution (all fixed against `tribe["status"]`):**
- Card 22 shaded deriver, Card 68 unshaded deriver+handler — Dispersed Tribe/Remi
  no longer mis-read as Subdued.
- Card A51 unshaded — a Dispersed Remi no longer wrongly satisfies "Remi ... or
  Subdued."
- Card 29 — "Remove any Dispersed from both Suebi" now clears `status` (was a
  no-op, leaving a Tribe both Dispersed and newly Allied).
- Card 57 shaded — "Remove ... Dispersed from Britannia" now clears `status`.
- Card 68 shaded — "remove anything" at Alesia/Cenabum now clears a Dispersed/
  Razed `status` before placing the Citadel.
- Card 52 unshaded — left as-is: its `is_roman_ally or is_subdued or is_dispersed`
  gate triggers identically for a Dispersed Carnutes (no behavioural error), so
  the imprecise label has no effect.

Each fix has a regression test (TestSubduedDispersedHandling,
TestDispersedStatusHandling).

**Known dead code — REMOVED (July 2026):**
`event_eval.py::_has_subdued_tribes` / `_has_subdued_city_tribes` had been
corrected at some point but remained unreferenced; deleted. In the same
hygiene pass: the stale `_execute_sa` docstring (claimed Build/Scout/
Entreat/Suborn/Rampage/Enlist were "deferred" — all are wired), the dead
`_UNWIRED_COMMANDS` branch (empty since the proof slice), and the "not
yet wired" reason strings. Fuzz digest unchanged — behaviour-free.

**Files:** `fs_bot/cards/card_effects.py` (cards 29, 57, 68, A51),
`fs_bot/engine/execute.py` (`_derive_card_22`, `_derive_card_68`).

---

## [AUDIT] Card-by-card faithfulness audit — results and remaining gaps

A full audit of all ~116 card handlers (72 base + 39 Ariovistus + 5 2nd-ed
text-change) against the Card Reference was performed. Real bugs found were
fixed with regression tests (see commits). This entry records the gaps NOT yet
fixed, by severity, so they are tracked rather than lost.

### Fixed in this pass (for reference)
Subdued/Dispersed storage class on Ally placement / Dispersed clearing: cards
22, 28, 37, 40, 41, 60, 61, 66, A29, A30, A40, A45, A56 (+ earlier 29/57/68).
Bounded conditions: card 33 (Lost Eagle Senate no-shift-down wired), A18
(Roman-Control requirement), A60 (refund counts the Ally), A24/A27/A32 (Arverni
Phase "as if At War" forced), A58 shaded (Ambush Romans only), A67 (non-German
routing), card 54 (Ariovistus player set: Germans not Arverni), A45 (Celtica +
within-1-of-Intimidated).

### Remaining — larger engine features
**[RECONCILED July 2026 — see "Card-audit gaps closed" at the end of this
file: every item below was implemented in later passes (this note was
stale); the last true gap, A70 unshaded, is now closed too.]**
- **A34 unshaded** — "A non-German player may use German pieces to free March or
  Battle in/from up to 3 Regions." Flag set, no consumer → no-op. Needs a
  borrow-German-pieces March/Battle resolver.
- **A70 shaded (capability)** — ongoing effects "If Nervii Subdued at end of any
  action, place a Belgic Ally" and "Belgic Rally at Nervii places +2 Warbands"
  have no engine hook. The capability is recorded but its effects are inert.
- **A53 unshaded** — Romans get free Recruit + March but not the granted "+1
  Special Activity" (one fewer free action than the card allows).
- **Card 11a unshaded (Ariovistus)** — 2nd-ed restricts the free Battle to
  Auxilia ("attack restricted to Auxilia"); the shared resolver attacks with all
  Roman pieces (resolve_battle has no attacker-type restriction).
- **A29 / A40 unshaded** — no NP deriver, so the placement no-ops for bots; when
  params are supplied, the handler does not enforce A29's Settlement-region
  gating + caps (≤2 Allies, 5 Warbands OR 3 Auxilia) nor A40's 3-Region limit +
  per-Region 3/2/1 caps.

### Remaining — minor / benign (documented, low impact)
- **A65 unshaded** — "without Leader" Battle condition not enforced (a Leader
  present could contribute to the free Battle).
- **Card 57 unshaded** — "+4 Resources if in Britannia" is granted
  unconditionally (the March is deferred to the caller, so post-March position
  is not checked).
- **A20 unshaded** — "free Seize as if Roman Control": the Disperse step still
  needs real Roman Control (Seize/Forage execute); a documented refinement.
- **Cards 30 & 39 capability magnitudes** — 2nd-ed Ariovistus changes (card 30
  pick-4 Warbands; card 39 Trade regardless of Supply Lines) are not modeled —
  but there is no consumer of capability 30/39 at all (pre-existing, also affects
  base), so the _ariovistus handlers are not independently unfaithful.
- **Card 19 shaded** — Successor recovery handles "Available" but not the
  "on map" relocation branch.
- **Cards 35/A34-shaded/A35 faction-gating, cards 16/25/26/61/64/65 caps &
  region constraints** — handlers trust caller/event-eval-supplied params; benign
  in normal NP flow.
- **Card 52 unshaded** — Carnutes Subdued/Dispersed misclassification is benign
  (Roman-Ally / Subdued / Dispersed all trigger the same −8 branch).

---

## [AUDIT FOLLOW-UP] QUESTIONS.md remaining-gaps — resolutions

The "larger engine features" and minor items recorded above were taken up and
grounded in the rules. Resolved with tests:

- **A53 unshaded** — Romans now take the granted free Special Activity (a Roman
  Build, the NP default per node_r_recruit/node_r_march, §8.8.1/§8.8.4).
- **Card 11a unshaded** — free Battle attack restricted to Auxilia
  (auxilia_only_attack threaded through resolve_battle; card_11a only).
- **A29 / A40 unshaded** — handler caps + Settlement/Cisalpina gating, and NP
  derivers added (cards now play for bots).
- **A34 unshaded** — non-German player uses German pieces to free Battle the
  acting Faction's rivals in up to 3 Regions (was a dead flag).
- **A70 shaded** — ongoing effects wired: end-of-action Belgic Ally at a Subdued
  Nervii; Belgic Rally at Nervii +2 Warbands.
- **A65 unshaded** — free Battle now "without Leader" (no_attacker_leader).
- **Card 57 unshaded** — +4 Resources applied after the March, only "if in
  Britannia".
- **Card 19 shaded** — Arverni Successor "on map" relocation handled.
- **Card 30 unshaded** — Arverni Rally cap drops the Leader+1 when active.
- **Card 39** — Trade capability wired: unshaded +2 per Aedui Ally/Citadel in
  Supply Lines; shaded limits Trade to 1 Region.
- **A20 unshaded** — free Seize "as if Roman Control" Disperses Veneti
  regardless of actual Control (as_if_control override).

### Resolved — Card 30 shaded (capability)
- **Card 30 shaded** — "In any Battles with their Leader, Arverni pick 2 Arverni
  Warbands — they take & inflict Losses as if Legions." Implemented:
  - INFLICT: in the Attack step (`_calculate_attack_losses`) and the
    Counterattack step (`calculate_losses`), 2 Arverni Warbands count as Legions
    (1 Loss each, not ½) when the Arverni Leader is in the Battle and the
    capability is active (`card30_arverni_legion_warbands`).
  - ABSORB: in `resolve_losses`, up to 2 Arverni Warband Losses take the §3.2.4
    save roll (1-3 remove to Available — not Fallen, per Tip; 4-6 absorb, and
    the survivor may be targeted again).
  - Counterattack Tip: the surviving picked-Warband count from the Attack absorb
    is threaded (`arverni_legion_override`) into the Counterattack inflict, so
    if both picked Warbands were removed while absorbing, the Counterattack
    gains no Legion bonus.
  Tested in TestCard30ShadedLegionWarbands (inflict, no-leader, absorb save
  roll, counterattack override). Card 30 *unshaded* (the Rally cap) was already
  implemented.

### Open items: none from the audit remain.

---

## [SIMPLIFICATION AUDIT] Rules-accuracy sweep

A full sweep for shortcuts/simplifications (grep of every "simplif / approximat /
for now / TODO / deferred / refinement" marker, plus review of the introduced
diff) was performed. Findings by category:

### Mandatory card-effect simplifications — FIXED
- **A20 / A58 free Seize "as if Roman Control"** — both previously Dispersed only
  where Romans actually Controlled. Now Disperse every Seize Region's Subdued
  Tribes regardless of Control (`as_if_control`), and A58 also suppresses
  Harassment ("with no Harassment", `no_harassment`). These were the only
  mandatory-effect shortcuts found.

### Stale comments — effects were already complete (no code change needed beyond
the comments)
- Cards 2 and 21 carried "TODO: battle module integration" comments, but their
  free Battles are fully resolved by the orchestration layer
  (`_resolve_card2_battle`, `_resolve_card21_provincia_battle`) via event
  modifiers. Comments corrected.

### Optional effects / NP choices — NOT rules violations (and deliberately not
"invented", per CLAUDE.md "never guess NP behavior")
The mandatory parts of each are implemented; the untaken part is an *optional*
"may" or a choice the references' bot instructions would dictate:
- **Card 57** "may add any free Special Ability there" (the March and the
  conditional +4 are done).
- **A34** "may use German pieces to free March OR Battle" — Battle (the
  substantive use) is implemented; March is the alternative.
- **A53** "+1 Special Ability" — the Roman NP's default SA (Build) is taken;
  Build/Scout/Besiege is an NP choice.
- **A28** "and—with their agreement—any other Factions' Warbands/Auxilia as own"
  — Arverni (combined-Battle Loss math) implemented; other-Faction agreement is
  a separate inter-Faction agreement-protocol extension.
- **A67** "without losing Germanic Control" surplus-gathering, and defender
  **Retreat into another Faction's Control** (§1.5.2 agreement) — both are
  NP-decision refinements; the core effects (March/Battle/flip; Retreat into own
  Control) are done.

### Pre-existing bot-decision approximations (NP strategy, not card effects)
The bot flowchart nodes (roman_bot, aedui_bot, raid/march tie-breaks) approximate
some §8.x decision criteria — e.g. "fewest Losses" ≈ fewest enemy mobile pieces;
"ending in a Supply Line" ≈ region has Roman pieces — because exact evaluation
needs full battle simulation at decision time. These are deliberate choices by
the original authors, predate this work, and affect *how the bot chooses*, not
the *rules-correct execution* of the chosen action. Flagged for awareness; not
changed.

---

## [BOT FAITHFULNESS] Decision-layer approximations replaced with exact rules

The NP bot decision nodes had several documented approximations (made before the
battle engine / supply-line helpers were complete). All are now exact:

- **Roman R_BATTLE (§8.8.1)** — now applies the real condition "Roman Losses
  will be < 1/2 enemy's AND no Loss on Caesar," evaluated by a deterministic
  battle predictor (predict_battle: resolves on a state copy forcing all
  Defender Loss rolls to removals, no Defender Retreat — the flowchart's stated
  basis). Previously it battled every threat Region.
- **Roman R_MARCH (b)** — ranks destinations by the actual Losses the enemy
  would inflict (Battle loss formula), not a "fewest enemy mobile pieces" proxy.
  (d) already used the real has_supply_line.
- **Roman R1 threat** — implements "enemy Battle or Rampage would force a Loss
  on a Legion or Caesar" (Auxilia buffer the hard pieces, §3.2.4 no-Retreat).
- **Roman Besiege check** — uses the exact predicted inflicted Losses.
- **Roman R_RECRUIT (§8.8.4)** — decides on what can ACTUALLY be placed (Region
  eligibility, Subdued Tribes, Auxilia caps), not raw Available counts. Fixed a
  latent ally-placement bug (the Subdued-tribe helper returns a list).
- **Aedui Trade estimate (§4.4.1)** — computes the exact Trade gain via the real
  Trade mechanic (real §3.2.1 Supply Lines), not an allies+citadels count.
- **German-Phase Raid (§6.2.3) / March (§6.2.2)** — target/destination priority
  now distinguishes player vs Non-player Factions (state["non_player_factions"]).
- **Seize Harassment (§3.2.3)** — the hard-target roll now actually removes a
  Legion/Leader/Fort (was a no-op recording "hard_target_hit").
- **Event decline (§8.1.1)** — should_decline_event now checks Ineffectiveness
  via event_eval.is_event_effective (and fixed a latent crash in
  _any_active_capabilities). Bots no longer play Ineffective Events.

All exercised by the test suite (1911) and validated across all-bot games
(valid + deterministic in every scenario).

---

## Q12: Roman bot Quarters/Spring plans never consumed by the Winter engine — RESOLVED

**Discovered:** via self-play instrumentation (see `selfplay-strategy-notes.md`).

**What I was doing:** running bot-only and agent-vs-bots games across all three
base scenarios to characterize balance. In **The Great Revolt**, the Arverni win
essentially every game (20/20 across all seat configurations, including bot-only),
which prompted a root-cause audit.

**The defect (unambiguous part):** `fs_bot/bots/roman_bot.py:node_r_quarters`
builds a faithful §8.8.7 Quarters plan (1 Auxilia stays per Fort & Roman Ally;
all others incl. Leader move to Provincia if able, incl. via adjacent Supply-Line
Regions; pay to avoid rolls — Roman Allies first, then non-Devastated, Devastated
last). `node_r_spring` similarly exists. **Neither is ever called in production.**
The only call sites are unit tests:

```
$ grep -rn node_r_quarters fs_bot/ --include=*.py | grep -v 'def \|test'
(no output)
```

`resolve_winter_card` → `run_winter_round` is always invoked with
`relocations=None` (`game_engine.py:583, 633`). As a result, in every Winter:
- `_apply_relocations(state, ROMANS, [])` moves no Roman pieces — legions never
  retreat to Provincia or along Supply Lines, and
- `_quarters_roman_pay_or_roll(state, {})` hits its documented default of
  "rolling for all" (`winter.py`): every Legion/Auxilia outside Provincia (beyond
  the free per-Fort/per-Ally pieces) rolls, removed on 1–3, Legions to Fallen —
  with **no payment even when the Romans can afford it.**

**Measured effect (The Great Revolt, bot-only, 12 seeds):**
- As shipped: Arverni 12/12. Off-map Legions climb 2 → ~12 (every Legion ends
  off-map), satisfying the Arverni off-map-Legions condition outright.
- With the Quarters roll neutralized (pay/keep all): Arverni 10/12, Belgae 2/12,
  and off-map Legions stay at ~3 — the Arverni win on end-game margin ranking
  rather than by crossing threshold (their Allies+Citadels start at 11, already
  over the threshold of 8).

So the unconsumed Quarters plan is a real, quantified contributor (it converts
"Arverni lead on margin" into "Arverni achieve outright victory"), layered on top
of a scenario that already favors the Arverni at setup.

**The ambiguity (why I did not just fix it):** wiring the bot's plan into the
Winter engine faithfully requires choices the flowchart text does not pin down
for me without risk of guessing, contrary to CLAUDE.md:
1. **Supply-Line routing.** `node_r_quarters` says move to Provincia "if able,
   including via adjacent Supply Line regions," but the returned plan
   (`move_to_provincia`: a flat region list) does not encode the route, and
   reaching Provincia from interior Regions (e.g. Mandubii, Treveri in Great
   Revolt) depends on Supply Lines that may pass through enemy-Controlled or
   Devastated Regions. What is the exact legality test the bot should apply, and
   what does a Legion that *cannot* reach Provincia do (stay and pay, or stay and
   roll)?
2. **Pay budget.** "Pay to avoid rolls" in priority order — but for how many
   pieces? All it can afford? Reserve Resources for the coming year? The
   flowchart gives an order, not a quantity.
3. **`node_r_spring`** is likewise unconsumed; does Spring need a parallel wiring?

**Decision (owner, 2026-06-10):**
(a) Wire both Quarters and Spring — the dead code was a wiring omission.
(b) Routing: implement §6.3.3 to the letter (adjacent un-Devastated
Roman/agreed-Control hop; Supply-Line Regions, determined at that time, to
Provincia; Leader from anywhere; agreement via the AGREEMENT hook then the
host's NP agreements node).
(c) Pay quantity: most literally rules-faithful reading — "pay to avoid
rolls" means pay for every remaining piece in §8.8.7 priority order until
Resources run out; no reserve. The priority order only has work to do if
payment continues until funds run short, and the order tracks cost
(Allies cheapest), consistent with maximizing pieces saved per Resource.

**Implemented:** `roman_bot.build_np_winter_relocations` (built after the
Germans Phase so counts are current), consumed by `run_winter_round`;
`_quarters_roman_pay_or_roll` honors `_pay_order`; Spring successor
placement for NP Romans follows §8.3.2 (most Roman pieces). Balance impact
(bot-only, 20 seeds): Great Revolt Arverni 100% → 55% (Belgae 45%);
Pax Gallica Belgae 40% → 60%; Reconquest Belgae 45% → 30%. Baseline
refreshed; regression tests added.

(Separately and for the record: even with faithful Quarters, the Great Revolt
appears Arverni-favored in bot-only play — Arverni begin over their
Allies+Citadels threshold. Whether bot-only balance is a design target at all is
outside what the Reference Documents state, so this is recorded as an observation,
not a defect.)

---

## Q13: Event handlers desync `state["tribes"]` from space ALLY/CITADEL pieces — BUG REPORT (not a rules question) — FIXED in this commit

**Discovered:** while building the AE-DEEP agent profile: per-space
`count_pieces(..., ALLY)` disagreed wildly with `victory._count_allies_and_citadels`
late in games (e.g. Belgae 0 vs 13).

**Evidence:** `python -m fs_bot.tools.sync_check --scenario "Reconquest of Gaul"
--seeds 1-4` replays bot games and attributes each new desync to the card that
introduced it. Across 4 seeds, ~20 distinct Event cards introduce tribe/piece
desyncs (cards 2, 3, 8, 10, 13, 22, 23, 24, 36, 37, 38, 42, 45, 58, 60, 63, 64,
67, 68, 69, 71, 72 observed so far; both directions occur — allied tribes with
no piece, and more pieces than allied tribes).

**Cause class:** `fs_bot/cards/card_effects.py` has ~71 sites mutating
`allied_faction`; some pair the mutation with `place_piece`/`remove_piece`
(e.g. card 23), many do not. Rally/Suborn/Build/Entreat command paths are clean.
One agent-interface instance is already fixed in this commit:
`_execute_suborn` dropped the `tribe` field on `remove_ally`, leaving the tribes
dict stale after agent-driven Suborn removals.

**Why it matters:** victory counts read `tribes` (authoritative), but Winter
Quarters free-stay counting, Control refresh inputs, and any space-piece-based
logic read pieces — they silently diverge as Events fire. Not a rules
ambiguity; this is an implementation defect list. Suggest a dedicated pass:
audit the 71 mutation sites against the Card Reference, pair each with the
piece operation, and add the sync invariant to `validate_state` once clean
(sync_check exits non-zero while any desync remains, so it can serve as the
acceptance gate).

**RESOLUTION (this commit):** Dedicated pass completed. All ~71
`allied_faction` mutation sites and all ALLY/CITADEL `place_piece`/
`remove_piece` sites in `fs_bot/cards/card_effects.py` were audited against
the Card Reference / A Card Reference; 40 handlers (21 base-game: 18, 22,
23, 26, 28, 29, 31, 34, 37, 40, 41, 42, 49, 57, 60, 61, 64, 65, 66, 68, 71;
19 Ariovistus: A19, A20, A24, A25, A26, A27, A29, A30, A32, A35, A36, A37,
A40, A43, A45, A56, A58, A60, A65, A69) were fixed — roughly 67 individual
sites. Four shared helpers were added near the top of card_effects.py and
the sites refactored onto them: `_ally_tribe` (place ALLY disc + set
`allied_faction` together; no piece Available means no allegiance recorded,
mirroring Rally), `_unally_tribe` (remove the tribe's matching piece — the
ALLY disc, or the CITADEL for a City tribe holding one — + clear
`allied_faction` together), `_tribe_piece_type`, and
`_unally_faction_tribes_in_region`; transfers are `_unally_tribe` then
`_ally_tribe`. Region-targeted removals that pick a piece (not a tribe) now
pair with the existing `clear_allied_tribe` (cards 31, 49 and the defensive
Citadel sweeps in 23, 26, 68, A20, A30, A43, A56). Card 71 Colony tribes
now carry their `"region"` in the tribes-dict entry, and
`sync_check.desyncs()` was extended to (a) read that dynamic region and
(b) also flag pieces with NO tribes-dict entry (it previously only checked
(region, faction) pairs that had allied tribes) — the detector is strictly
stronger than before. Cards 2, 3, 8, 10, 13, 14, 17, 55 etc. from the
original observation list were attribution artifacts: an earlier desync
(usually the invisible Colony) changing shape on a later card's turn.
`python -m fs_bot.tools.sync_check` is now clean for all three base
scenarios, seeds 1–6, and `fs_bot/tests/test_tribe_piece_sync.py` adds unit
coverage for the helpers plus per-scenario bot-game canaries. No handler
was found whose existing logic contradicts the Card Reference text beyond
the missing bookkeeping fixed here, so no new OPEN items were filed.
Remaining follow-up (unchanged): add the sync invariant to
`validate_state`.


---

## Q13 follow-up: Ariovistus Arverni-Phase Citadel upgrade desync — FIXED

The external four-seat playtest (effective-play bundle) found one residual
Q13-class defect outside the audited Event layer: the game-run Arverni
Phase's Rally procedure (A6.2.1) upgraded a City Ally to a Citadel by
removing the Ally piece AND clearing `allied_faction`, then placing the
Citadel — leaving an Arverni Citadel on the map with no allied-tribe
record. Its 34 "triggering cards" in Ariovistus replays were activation
triggers of this single procedural bug, not 34 handler defects.

Fix (their patch, verified and applied): the upgrade keeps
`allied_faction = ARVERNI` — a Citadel is the fortified form of the same
Allied tribe. Regression test added; sync_check now clean on Ariovistus
(seeds 1-8) and The Gallic War (seeds 1-3) in addition to the three base
scenarios; the in-suite canary now includes an Ariovistus bot game.


---

## External mixed-matrix playtest (1,280 games) — three defect families fixed

A 1,280-game mixed human/bot matrix over all five scenarios surfaced three
state-integrity defects, all fixed here with regression tests
(test_mixed_matrix_fixes.py); post-fix sync sweeps are clean on all five
scenarios (seeds 1-16) and the suite is 1951 passing.

1. FIXED — stale one-shot Event free-action flags survived in
   state["event_modifiers"] and could replay in a later unrelated Event.
   _resolve_free_actions now consumes a curated set of 75 one-shot flags
   after their actions resolve, preserving the persistent modifiers later
   phases read (lost_eagle_no_shift_down, optimates_active,
   card_A63_quarters_devastated_only, card_A66_winter_uprising).
2. FIXED — Ariovistus A18 (Rhenus Bridge) and A25 (Ariovistus's Wife)
   removed German Ally discs without clearing the authoritative tribe
   allegiance. Both now use _unally_faction_tribes_in_region plus a
   defensive stray-disc sweep (Q13 class, outside the original card-effects
   audit because they sit in Ariovistus handlers).
3. FIXED (rules guard) — an after-Command Special Activity was awarded even
   when the Command produced no legal effect (e.g. a 0-Resource Aedui
   Rally still ran Trade). _execute_bot_command and execute_decision now
   withhold the after-Command SA when the Command did not execute.

## OPEN follow-ups from the same report (not state-integrity; play quality)

- Before-Command SAs (Entreat/Intimidate before a Battle) still mutate the
  board even when the Battle then fails ("defender not present"). Needs
  transactional or prevalidated execution; ~65 cases in the matrix. The
  after-Command guard does not address these by design.
- Aedui Rally+Trade and Belgae Rally+Enlist need interruptible SA timing
  (§4.1 allows an SA before/during/after a Command); the engine has a fixed
  before/after schedule. The guard enforces the rule but does not provide
  the interrupt.
- Resource-oblivious Rally plans (Arverni/Aedui plan Citadels/Allies/
  Warbands after Resources are exhausted); Arverni empty-list threat
  Marches; German invalid Rally-region Ally placement; occasional
  ineffective Event selection. These are planner-quality bugs (the bot
  forfeits the Command via a clean rejection, not a crash) and are the
  main remaining work for bot reliability.

---

## All-bot timing/sync audit (external, June 2026) — triage

The external audit ran a 500-game all-bot sync sweep, a 1,280-game mixed
human/bot matrix, and a targeted SA-timing audit. Triage:

### Confirmed clean (verification, not defects)
- 500 all-bot games (100 seeds x 5 scenarios), 20,209 cards: **zero
  tribe/piece desyncs**. The Q13 / A18 / A25 / Arverni-Phase-Citadel fixes
  hold at scale.

### FIXED
- First-year (off-track) Senate shift crashed. Pax Gallica?: "During the
  first year, the Senate ... does not shift", so setup leaves
  senate.position = None; Cicero (1), Legiones (2) and Pompey (3) called
  _SENATE_INDEX[None] -> KeyError(None), caught as "event not applicable"
  (~72 forfeited bot Events in the matrix). _apply_senate_shift and card 2
  now treat an off-track Senate as a clean no-op per the year-1 rule.
  Regression test: test_first_year_senate.py.

### OPEN — planner quality (NOT state-integrity; executor rejects cleanly)
These are the published-bot planners proposing sub-actions the executor
legally refuses; the command still does what it legally can, no corruption.
Per CLAUDE.md (faithful flowcharts, never guess) these need per-faction
flowchart transcription, not speculative rewrites. Prioritized by frequency
in the 1,280-game matrix:

- Resource-oblivious / illegal-region Rally (Aedui 2303, Belgae 1979,
  Arverni 1183, Germans 472 sub-errors): planners propose Rally regions
  with no Control/Ally/Citadel/Leader/Rally-symbol, or with 0 Resources,
  or Ally placement without Control. Fix: filter the plan to executor-legal
  regions/pieces (the "one rule, one implementation" pattern), per each
  faction's Rally flowchart node.
- Arverni "expand/mass march: nothing marchable" (912): node_v_march_threat
  returns a March with no marchable pieces instead of falling through.
- Romans Recruit (557) / Romans Battle+Scout (2976) / Romans March+Build
  (1633): after-Command SAs that find nothing to do (executed:False, no
  effect) and Recruit plans exceeding Resources.
- Interruptible SA timing (Aedui Rally+Trade, 791 cases where Trade
  executes after Rally already failed for lack of Resources; Belgae
  Rally+Enlist control ordering): §4.1 allows an SA before/during/after a
  Command; the engine has a fixed before/after schedule with no "interrupt
  Rally to Trade, then continue" model. Architectural.
- before-Command SA obviates its Command (67: Arverni Battle+Entreat 11,
  Germans Battle+Intimidate 56): the SA legally converts/removes the
  Battle's target, then the Battle has nothing to do. The SA effect is
  legitimate and beneficial (no rollback warranted); the planner should
  not pair a Battle with an SA that removes its target. Play quality.

---

## Census-driven executor-rejection sweep (June 2026 continuation)

Resumed the planner-quality backlog using `fs_bot.tools.error_census` as the
acceptance instrument (bot-only games, all scenarios, seeds 1-20 = 100 games).
Starting point this sweep: 462 incidents/100 games (the ~6,800 figure predates
the Rally/March/Roman/Aedui fixes already on main). Endpoint: ~150.

### FIXED (each with a regression test; faithful to the cited rule)
- Arverni Entreat (§4.3.1): filter replace_ally/remove_ally to Arverni-
  Controlled Regions and to the Resource budget (1/Region); and require an
  actual Ally disc — Entreat replaces "not a Citadel", so a City tribe holding
  the faction's Citadel is not a removable Ally. 462 -> 305 -> (later) clean.
- Aedui Suborn (§4.4.2 / §8.6.3 step 2): "remove enemy Ally" removes an Ally
  disc, never a Citadel; require an Ally piece and name an Ally-backed tribe
  (mirrors board.pieces.clear_allied_tribe). 305 -> 237.
- German/Aedui/Belgae Raid (§3.3.3 / A8.7.3 / §8.5.4): only steal from a
  Faction that has Resources; route all three through the canonical
  validate_raid_steal_target. Eliminated "Cannot steal from <F>: 0 Resources"
  from the bot Raid planners.
- All bots — Devastation source of truth: planners read MARKER_DEVASTATED in
  state["markers"], not the never-set state["spaces"][R]["devastated"] flag.
  commands.common._is_devastated is now canonical (honours both). Fixed Belgae
  Raid bank-gain in Devastated Regions and made all Devastation-aware play
  correct (Quarters, Devastate timing, March cost).
- German Intimidate (A8.7.1): re-derive Intimidate-or-Settle "at that moment"
  (after the Raid/March moves/reveals pieces), mirroring the Aedui Trade/Suborn
  re-derivation. Eliminated stale "Only 0 Hidden Germanic Warbands in <R>".
- March (§3.2.2): a March's group is selected at the ORIGIN and carried through
  multi-hop paths; the executor no longer re-scoops each Region's RESIDENT
  forces (which ballooned the army and tried to move resident Revealed Warbands
  as Hidden — "Only 1 Hidden Warband in <R>, need 15") nor applies Harassment
  to residents. Balance baseline rebaselined (intended deterministic change).

### OPEN — remaining tail (data, not vibes)
- Determinism under PYTHONHASHSEED: the census total drifts ~5% across
  PYTHONHASHSEED values with identical game seeds (e.g. seeds 1-5: 27 incidents
  at HASHSEED=0/1, 33 at HASHSEED=2). Some decision depends on set-iteration
  order. state["rng"] is used for explicit tie-breaks, so the leak is a set
  built/iterated in decision logic upstream of an rng draw (candidate list
  order). Not an executor error, but it violates strict replay determinism
  (CLAUDE.md) and should be hunted by sorting any set before it feeds a choice.
- before-Command SA obviates its Command ("defender not present" on
  Germans/Arverni Battle): the paired Entreat/Intimidate legally removes the
  Battle's lone target first. Documented previously as legitimate play-quality
  (the SA effect is beneficial; no corruption). Planner should not pair a
  Battle with an SA that removes its target.
- Event-path Raids (cards A38, 40) steal from a 0-Resource Faction, and a few
  card/capability effects (A22 "Intimidate has no effect on Romans"); these run
  through Event handlers, not the bot Raid planner that was fixed.
- Suborn/Rally Ally placement at a faction-restricted Tribe ("Cannot place
  Aedui Ally at Suebi — restricted to Germans"): planner should respect
  TribeData.faction_restriction (§1.4.2) when choosing the place_ally Tribe.
- A handful of "Only N Hidden Warband in <R>, need M" March residuals
  (off-by-a-few) surface only under some PYTHONHASHSEED values; investigate
  together with the determinism item above.

---

## Determinism + tail sweep (June 2026, continuation 2)

Picked up the OPEN items from the previous sweep.

### FIXED — strict replay determinism (the big one)
Several bot/event paths iterated a `set` whose order is PYTHONHASHSEED-dependent
and then kept the first element under a strict `>`/`max()` tie-break, so play
diverged across processes with identical game seeds (census drifted ~5% by
hashseed). Sorted every such decision-feeding iteration (arverni_bot V_MARCH
spread; execute.py card-72 Hidden-Warband March+Battle; 17 `for ... in playable`
/ comprehensions over `set(get_playable_regions(...))`). Verified bit-identical
play across PYTHONHASHSEED 0/1/2/3/5/7/13/42/99 for all 5 scenarios x seeds
1-20; the census is now constant (128) regardless of hashseed.

### FIXED — remaining executor rejections (each with a regression test)
- March: move a group's Warbands/Auxilia in their actual flip state, not forced
  Hidden — a group of de-Scouted (Revealed) Warbands raised "Only 0 Hidden
  Warband in <R>, need N" (§3.3.2).
- Raid (German/Aedui/Belgae): per-Faction steal ledger across Regions, so the
  plan never steals more than a Faction has ("Cannot steal from <F>: 0
  Resources" on the 2nd Region) (§3.3.3).
- German Intimidate before Battle: exclude the Battle's defender, so Intimidate
  complements (not replaces) the Battle — eliminated "defender not present" and
  the A22 Romans-Intimidate refusals (A8.7.1).
- Roman Scout: a Successor may Scout only its own Region, not within-1 (§4.1.2).
- Arverni Entreat: Step 3 (remove) no longer re-targets a piece Step 2
  (replace) already took (§8.7.1).

Census trajectory this continuation: 214 (post-determinism) -> 128, hard
executor errors reduced to 4 incidents/100 games.

### OPEN — residual tail (4 hard incidents/100 games; documented, low-value)
- Romans Recruit "No Roman Allies Available" (2): a paired Build SA places
  Roman Allies before the Recruit Command, draining the shared Ally pool; the
  Recruit's planned Ally then fails. Cross-Command/SA resource coordination
  (same architectural class as interruptible-SA timing).
- Arverni Battle "defender not present" (1): the paired before-Battle Entreat
  legally removes the Battle's lone target. The Arverni flowchart NOTE
  prescribes "instead March and Entreat" — a Command re-plan (not implemented;
  the German analog was handled by excluding the defender from Intimidate, but
  Entreat's cross-Region targeting makes the Arverni case a larger change).
- Arverni March+Entreat (1): a residual Entreat targeting edge.
- The remaining ~124 incidents are soft: `sa-no-effect` (an SA that legally
  accomplishes nothing — the planner should "if none, no SA"), `sa-skipped`,
  and flowchart-legal `command-refused` ("event not applicable", "expand/mass
  march: nothing marchable" IF-NONE fall-throughs). None are executor
  rejections of illegal moves and none corrupt state.

---

## Flowchart-conformance audit — Aedui (§8.6, June 2026)

Node-by-node comparison of aedui_bot_flowchart.txt against aedui_bot.py.
Overall the Aedui bot is highly faithful: A1-A6 routing, A_BATTLE (enemy set
Gauls/Germans + Romans only at victory; Step-2 high-value and Step-3
favorable conditions), A_RALLY (Citadel/Ally/Warband order), A_TRADE (exact
§8.6.3 precondition + trigger + IF-NONE edges), A_SUBORN (priority order incl.
A8.4 German/Arverni swap), and A_QUARTERS all match.

### FIXED
- A_MARCH "Lose no Aedui Control" (§8.6.5): the spread (Step 1) and control-
  supply (Step 2) planning used a bare `warbands - 1` leave-behind and ignored
  Control preservation, so the planner picked origins the executor then had to
  trim (surfacing as the "expand/mass march: nothing marchable" legal-decline).
  Both now use the executor's own `_control_keep_warbands` (leave one Warband
  AND enough to keep Control) — one rule, one implementation. Legal-decline
  incidents 41 -> 29 (seeds 1-20). Regression:
  test_march_does_not_spread_from_control_critical_region.

### DOCUMENTED — status updated (see 'Reconciliation' at end of file)
- [RESOLVED June 2026] A_RAID priority (§8.6.4): now orders players at 0+
  victory margin ahead of other non-Roman enemies (tier-1/tier-2 target list).
  ORIGINAL NOTE: the chart orders (1) players at 0+ victory margin,
  then (2) other non-Roman enemies. The code special-cases only Romans (raid
  only if a player at 0+ victory); it does not order a *non-Roman* player at
  0+ victory ahead of a non-Roman enemy below victory. Impact is limited to
  steal-target choice among enemies co-present in a Raid Region.
- [RESOLVED June 2026] A_MARCH Britannia / §4.1.3: the no-SA gate now covers
  every tracked march origin (Step-1 spread + Diviciacus). ORIGINAL NOTE:
  detected from the destination list and Step-1 origin only; a Step-2 control-
  supply move or the Diviciacus march that happens to depart Britannia is not
  counted as "out of Britannia". Rare (Britannia is base-game only and seldom
  the supply source).
- _estimate_trade_resources: when estimating whether Trade clears the ">2
  Resources" trigger, a *player* Roman is assumed to agree only at victory
  score < 10. The Agreements rule has a 10-12 die-roll tier (agree on 1-4);
  the estimate treats 10-12 as "won't agree", so it can under-estimate Trade
  yield in that band and skip an otherwise-triggered Trade. Conservative.

---

## Flowchart-conformance audit — Arverni (§8.7, June 2026)

Node-by-node comparison of arverni_bot_flowchart.txt against arverni_bot.py.
The Arverni bot is highly faithful: V1-V5 routing (incl. the V2c Carnyx
"Auto 1-4" event branch), V_BATTLE (the §8.7.1 Loss restriction via
_can_battle_in_region, the Caesar >2:1 mobile-ratio gate, trigger Battles then
Step-5 extras restricted to Romans/Aedui/player-Belgae and NOT NP Belgae or
Germans), V_RALLY, V_MARCH_THREAT/SPREAD/MASS, and the Ambush/Devastate/Entreat
SA-selection order all match.

### FIXED (each with a regression test)
- V_RAID (§8.7.5): the Arverni Raid planner was the last of the four still
  missing the §3.3.3 Resource check and the cross-Region steal ledger, so it
  stole from a 0-Resource Faction. Now routed through validate_raid_steal_target
  with a planned-steal ledger, like German/Aedui/Belgae.
- V_ENTREAT (§4.3.1): replacing/removing an Allied Tribe consumes an Ally disc.
  When a Region holds more allied tribes of a Faction than Ally pieces (the
  surplus represented by Citadels), Step 1/Step 3 emitted one action PER TRIBE
  and overran the discs. Capped Ally actions per Region at the Ally-piece count.

These closed the two remaining Arverni entries in the census `illegal` tier
(4 -> 2; the lone survivor is the architectural Roman Recruit/Build-SA case).

### DOCUMENTED — status updated (see 'Reconciliation' at end of file)
- [RESOLVED June 2026] V_ENTREAT NOTE / V_BATTLE obviation: implemented — drop
  Battles whose lone target the before-Battle Entreat removes; if EVERY Battle
  is obviated, March and Entreat instead. This cleared the last census illegal
  defect. ORIGINAL NOTE: V_ENTREAT NOTE / V_BATTLE: "In the rare case that Entreat prevents Battle by
  removing a lone target piece, instead March and Entreat per above." Not
  implemented — when the before-Battle Entreat removes a Battle's only target,
  the Battle resolves as a no-op (executor skips "defender not present") and the
  Entreat still happens. Prior analysis judged this benign (the Entreat is a
  legal, beneficial conversion; rolling it back would undo a good action). The
  faithful "March instead" remedy is a Command re-plan whose multi-Battle
  semantics ("March instead" vs "drop the obviated Battle") are ambiguous in the
  text — left for a ruling rather than guessed.
- V_MARCH_THREAT planner approximations: the Vercingetorix destination is chosen
  as the Region with the most Arverni pieces without checking reachability or
  the §8.7.1 Harassment-loss limits ("no more than three Losses, none on
  Vercingetorix"); Step 2 marches every other Region with 2+ Warbands toward
  Vercingetorix's destination rather than "toward Vercingetorix counting by
  adjacent Regions". The executor enforces leave-behind/Control and Harassment,
  so these are graceful, but the planner is more permissive than the chart.

### STATE-INTEGRITY QUESTION — RESOLVED by the 'Citadel over-placement' fix
### directly below (traced to card 69 / Rally / Arverni Phase; fixed at
### place_piece + each upgrade site + the oracle).
- [HISTORICAL] In a Reconquest game, Mandubii showed THREE tribes allied to Aedui (Mandubii
  city + Senones + Lingones) backed by 1 Ally disc + 2 Citadels. Citadels sit
  only at Cities and Mandubii has one City, so 2 Aedui Citadels there — and a
  3rd allied tribe with no remaining backing piece — looks like a tribe/piece
  desync (the Q13 class) rather than legal state. The V_ENTREAT cap above hides
  the symptom for the planner, but the underlying allegiance/piece mismatch
  should be traced to its source (Event handler or piece op) and confirmed
  legal or fixed.

---

## STATE-INTEGRITY FIX — Citadel over-placement (one Citadel per Region)

The Arverni audit's Mandubii oddity (3 tribes allied to Aedui, 1 Ally + 2
Citadels) traced to a real corruption: a Region's one City holds one Citadel,
so a Region may have at most ONE Citadel — but multiple placement paths placed
a SECOND. They keyed on "Faction has an Ally disc in the Region" (region-level)
instead of "the City tribe has an Ally to upgrade", so a City already
Citadel-backed plus a non-City Ally elsewhere in the Region triggered a 2nd
Citadel (consuming the non-City tribe's Ally instead). validate_state only
checks the global pool cap, so it never caught two Citadels in one Region.
This was happening silently ~2.7 times per game in the all-bot census.

FIXED at every layer:
- board.pieces.place_piece(CITADEL): hard invariant — refuse if the Region
  already holds any Faction's Citadel (one City/Citadel per Region). Backstops
  all paths; PieceError is already caught by command/event execution.
- commands.rally.rally_in_region place_citadel: require the Region to have a
  Faction Ally and NO existing Faction Citadel before replacing.
- Event handlers (cards 28 / 30 / the Arverni-upgrade card / Suebi) and
  engine.arverni_phase: same Ally-present + Citadel-absent guard before each
  Ally->Citadel upgrade (prevents partial state: Ally removed, no Citadel).
- Rally planners (Aedui node_a_rally, Arverni V_RALLY): Step 1 proposes a
  Citadel only where the City has an Ally and the Region has no Citadel yet —
  previously these proposed 2nd Citadels the executor silently accepted (199
  Arverni + 69 Aedui such proposals per 100 games once the executor guard
  surfaced them).

Verified: across all 5 scenarios x seeds 1-20, NO Region ever holds >1 Citadel.
Census illegal stays at 3 (architectural Roman Recruit + the documented Arverni
Battle/Entreat obviation); total 117 -> 97; determinism and balance hold.
Regression: test_citadel_one_per_region_invariant (+ updated Arverni Rally
tests that had been draining the pool by stacking Citadels in one Region).

---

## State-integrity ORACLE — structural invariants + permanent guardrail

Motivated by the Citadel over-placement (which validate_state's pool-conservation
check could not see), added a structural checker that encodes the board
invariants the rules guarantee but nothing verified:

  state_schema.check_structural_integrity(state) ->
    1. At most one Citadel per Region (one City/Region — §1.4/§3.3.1).
    2. Tribe allegiance <-> backing piece: per Region/Faction, the number of
       allied Tribes equals that Faction's Ally + Citadel pieces (the Q13
       desync class, caught in BOTH directions).
    3. Control-flag freshness: cached space["control"] equals a fresh
       calculate_control (stale flags were a real planner/Winter bug class).
    4. Resources and Available pools non-negative.

Ran it as an oracle after every turn across all 5 scenarios x seeds 1-20 (100
bot-only games): **zero structural violations** — the Citadel fix and the prior
Q13 / Control-refresh work hold at scale, and no other silent corruption of
these classes exists.

Left in as a PERMANENT guardrail:
  - test_structural_integrity_checker_flags_corruption (the checker catches a
    2-Citadel Region, an unbacked allegiance, a stale Control flag, and
    negative Resources).
  - test_self_play_maintains_structural_integrity (every bot game stays
    structurally sound at each turn boundary — this test would have failed on
    the Citadel over-placement bug).

check_structural_integrity is intentionally SEPARATE from validate_state (which
some unit tests construct partial states against) so it can be strict without
breaking those. Future candidates if a new corruption class appears: Fort
per-Region limits, Dispersed/Subdued marker vs tribe["status"] consistency,
flippable-state validity.

---

## Flowchart-conformance audit — Belgae (§8.5, June 2026)

Node-by-node comparison of belgae_bot_flowchart.txt against belgae_bot.py.
The Belgae bot is largely faithful: B1-B5 routing (incl. the B2 "no Pass in
Winter / if 1st on both cards" NOTE and the A8.5.1 German-as-enemy + Settlement
handling), B_BATTLE (Ambiorix step, enemy set, Ambush->Rampage-before-Battle->
Enlist SA order), B_RALLY, and B_RAID (already carried the Resource ledger).

### FIXED (each with a regression test)
- B_MARCH (§8.5.5) "losing no Belgic Control": the control-supply leave-behind
  used a hardcoded -1/-2 instead of the executor's keep rule. Both the Belgica
  and outside-Belgica supply loops now use _control_keep_warbands (leave one
  Warband AND enough to keep Control) — the same fix applied to Aedui A_MARCH.
- B_ENLIST Step 4 (German free Raid): checked pieces and Citadel/Fort but not
  Resources, so it could target a 0-Resource player. Now routed through
  validate_raid_steal_target (§3.3.3).
- B_ENLIST Step 1 (German free Battle) and Step 2(1) (German free March): the
  flowchart says "a. player b. other Non-player" / "a. Player's b. Non-player's
  Control", but the code picked by Faction order (Romans/Aedui/Arverni),
  ignoring player-status. Now a two-pass scan prefers a PLAYER target/Control
  across all eligible Regions before any Non-player.
- B_RALLY Step 1 (Citadel): same Ally-present + Citadel-absent guard as the
  Aedui/Arverni Rally citadel steps (don't propose a 2nd Citadel where the City
  already has one).

Census illegal stays at the architectural minimum (Roman Recruit + the
documented Arverni Battle/Entreat obviation); structural oracle, balance canary,
and determinism all hold. The control-keep fix raises the legal-decline tier
(the Belgae March now correctly falls through to Raid when it cannot add Control
without losing Control — faithful conservative play, not a defect).

### DOCUMENTED — both RESOLVED June 2026 (see 'Reconciliation' at end of file)
- [RESOLVED] B_BATTLE now uses the §8.3.4 random tie-break (random_select).
  ORIGINAL NOTE: B_BATTLE / B_ENLIST set the order of Battles among equal
  candidates by a fixed
  Region iteration rather than the chart's §8.3.4 random tie-break. Deterministic
  and consistent with the other faction bots; a faithful rng-based tie-break
  would still be replay-deterministic but is a behaviour change deferred for a
  ruling.
- [RESOLVED June 2026] B_ENLIST Step 2(1): the German free-March destination is
  now required to be OUTSIDE Belgica/Germania (A8.5.1). ORIGINAL NOTE:
  the destination was not verified to be outside those Regions; it only requires
  enemy Control at an adjacent destination. Rare edge.

---

## Flowchart-conformance audit — Roman (§8.8, June 2026)

Node-by-node comparison of roman_bot_flowchart.txt against roman_bot.py. The
Roman bot is the most complex and is highly faithful: R1-R5 routing (incl. the
R2 "2+ Legions and 4+ Auxilia with Caesar" detail), R_BATTLE target ranking
(a Leaders, b most Warbands, c players, d most Allies+Citadels, e victory
margin — exact), the R_BATTLE Loss restriction + "Caesar can't Battle -> March",
the R_MARCH destination tiers (1 enemies at 0+ victory players-first; die-roll
tiers 2-4 incl. the Ariovistus Arverni swap; sub-priorities b-e), R_RECRUIT,
R_SEIZE (no-Harassment gate, Disperse player-pieces-then-Belgica), R_BUILD
(Forts at non-Aedui Warbands; Subdue best-margin-then-players with the
Ally-disc cap; faction-restricted Ally placement; the <6 Resource floor), and
the Besiege/Scout SA selection all match.

### FIXED
- R_RECRUIT / _execute_recruit (§8.8.4 "Build before Recruit"): the Build SA
  resolves first and can empty the shared Ally pool; the Recruit then refused
  its planned place_ally ("No Roman Allies Available") — the last standing
  `illegal` census defect. Recruit now skips a place_ally once no Roman Ally is
  Available (treated as superseded-by-Build, faithful to "place all Allies
  ABLE"). Census illegal 2 -> 1 (only the documented Arverni Battle/Entreat
  obviation remains). Regression:
  test_recruit_place_ally_superseded_when_pool_exhausted.
- R4 event-decline: unlike the other four faction bots, the Roman R4 did not
  consult the bot Event Instruction's NO_EVENT directive (it `pass`ed). Now it
  checks `instr.action == NO_EVENT` like Aedui/Arverni/Belgae/German. In the
  current card sets this coincides with should_decline_event (no behaviour
  change today), so it is a consistency/robustness fix guarding against the
  instruction data diverging from is_no_faction_event.

### DOCUMENTED — RESOLVED June 2026 (see 'Reconciliation' at end of file)
- [RESOLVED] R_BUILD Fort placement assumes one Fort per Region (skips a Region that
  already has a Roman Fort). If that is the intended rule, a "one Fort per
  Region" structural invariant now lives in both place_piece and the
  state-integrity oracle (§1.4 'Only one Roman Fort may be in each Region').

---

## Flowchart-conformance audit — German (Ariovistus, §A8.7, June 2026)

Node-by-node comparison of Ariovistus/german_bot_flowchart.txt against
german_bot.py (the Germans are an Ariovistus-only player faction). The bot is
highly faithful: G1/G1b routing (Ariovistus or 6+ Warbands vs ANY enemy; the
12+ Warband victory check), G2 (the "no Pass in Winter / 1st on both cards"
NOTE), G3b (the most thorough event-decline of all five bots — NO_Germans,
final-year Capability, and per-card "treat as No Germans" conditionals for
Romans/Belgae-NP and final Winter), G4/G5, G_BATTLE (Ariovistus-first vs
fewer-mobile, all-enemy set, Resource cap, and it correctly uses the §8.3.4
random tie-break), G_MARCH_THREAT (the nested victory destination priorities —
Dispersed Tribes if Romans at victory, then at-victory-Gaul Allies, then most
Control — with the random tie-break), G_MARCH_EXPAND (already computes the
proper leave-1-and-keep-Control supply inline), G_RAID (Resource ledger +
validator, fixed earlier), and Intimidate (before-Battle defender exclusion +
re-derivation, fixed earlier).

### FIXED (regression test)
- G3b was missing the "Event Ineffective" decline branch that the flowchart
  lists ("Event Ineffective, or Capability in final year, or 'No Germans'?")
  and that all four other faction bots check. Added is_event_effective (SHADED,
  as the Germans use shaded text) for GENERIC (PLAY_EVENT) cards only —
  specific-instruction cards remain governed by their A8.2.1 directive.
  Ariovistus census ineffective-event -> 0. Regression:
  test_g3b_declines_ineffective_generic_event.

All five faction bots are now audited (Aedui, Arverni, Belgae, Roman, German).
Ariovistus census: illegal=0; structural oracle, balance, determinism hold.

---

## All documented audit findings resolved (June 2026)

Worked through every outstanding documented finding from the five-faction audit:

### FIXED
- Aedui A_RAID priority (§8.6.4): targets ordered (1) players at 0+ victory
  margin, then (2) other non-Roman enemies (Romans only via tier 1).
- Aedui A_MARCH Britannia (§4.1.3): the no-SA gate covers every tracked march
  origin (Step-1 spread + Diviciacus), not just the Step-1 origin.
- Belgae B_BATTLE (§8.3.4): random tie-break (random_select) among equally-valid
  Battle targets, like the German bot (was fixed Region order).
- Belgae Enlist German March (A8.5.1): the destination must be OUTSIDE
  Belgica/Germania ("move them out of").
- Arverni V_BATTLE / V_ENTREAT NOTE: when the before-Battle Entreat removes a
  Battle Region's lone target, drop that obviated Battle; if EVERY Battle is
  obviated, March and Entreat instead. This eliminated the last census `illegal`
  defect ("defender not present"): census illegal 1 -> 0.
- Fort one-per-Region (§1.4 "Only one Roman Fort may be in each Region"): the
  place_piece executor already enforces it (MAX_FORTS_PER_REGION); added the
  same invariant to the structural-integrity oracle alongside the Citadel one.

### CENSUS STATE
illegal=0 across all 5 scenarios x seeds 1-20 (deterministic across hashseeds).
The remaining ~120 incidents are all soft: wasteful-sa (an SA that legally
accomplishes nothing — the flowchart's "if none, no SA"), a few
ineffective-event, and legal-decline (published IF-NONE fall-throughs). None are
executor rejections of illegal moves.

### STILL OPEN (judgment calls, not bugs)
- [RESOLVED July 2026] Aedui _estimate_trade_resources player-Roman agreement:
  the estimate now assumes agreement (see the Aedui Trade Roman-agreement
  section at the end of this file).
- [RESOLVED June 2026] The soft wasteful-sa tier: re-derive after-Command SAs
  and decline cleanly ("if none, no SA"); plus the _check_rampage ally-only
  over-attachment fix. wasteful-sa 84 -> 0. (See the wasteful-sa cleanup
  section below.)

---

## wasteful-sa cleanup — re-derive after-Command SAs / "if none, no SA" (June 2026)

The census "wasteful-sa" tier (84/100 games) was the planner attaching an SA
that legally accomplished nothing. Root cause: an after-Command SA is chosen at
decision time but resolves AFTER the Command moves/reveals pieces (e.g. a Raid
Reveals the very Belgic Warbands a Rampage would flip, or a March empties the
Region the Entreat targeted). The flowchart's "If none ... no Special Ability"
applies at resolution.

### FIXED
- Arverni Entreat: re-derived _check_entreat already runs at execution; when it
  yields nothing, return declined_no_effect ("if none, no SA") instead of a
  bare no-effect.
- Belgae Rampage (after Rally/Raid): re-derive _check_rampage against the
  post-Command board (like the German Intimidate / Aedui Trade-Suborn paths);
  decline cleanly if nothing. The generic Rampage path (e.g. after Battle) also
  reports declined_no_effect when it legally removes nothing.
- Belgae Enlist: the after-Command re-derivation already existed but EXCLUDED
  Battle commands; removed that exclusion so a standalone Enlist after a Battle
  re-derives too (the in-Battle loss-absorbing Enlist is a separate mechanism
  under Ambush/Rampage, so this is safe).
- Belgae _check_rampage: a real planner over-attachment — it approved a Region
  where the enemy's only presence was an ALLY, but §4.5.2 Rampage removes/
  Retreats only MOBILE pieces (Warbands/Auxilia/Legions/Leader). The bot would
  pick a no-op Rampage over a possibly-effective Enlist. Now requires an enemy
  mobile piece.

### CENSUS STATE — effectively clean
wasteful-sa 84 -> 0; illegal 0; total 120 -> 38, deterministic across
hashseeds. The remaining 38 are all legal: legal-decline (the published flow-
chart's IF-NONE fall-throughs) and a few ineffective-event (Events that resolve
to no effect — a separate small play-quality item). None are executor
rejections of illegal moves or wasted SA attempts.

---

## ineffective-event cleanup — card 69 Germans Phase (June 2026)

The last soft tier (ineffective-event = 6/100 games, all Arverni Event) was NOT
an Arverni decision error — node_v2b already declines ineffective Events via
should_decline_event. It was a bug in card 69 (Segni & Condrusi): its inline
Germans Phase looped EVERY Region calling germans_phase_raid_region, which
raises in a Region with no German Hidden Warbands (§6.2.3). The first empty
Region aborted the whole Event ("Germans have no Hidden Warbands in <R>"). The
other Germans-Phase card events already guard the loop with a Hidden-Warband
check; card 69 now does the same.

### CENSUS STATE — fully clean
illegal=0, wasteful-sa=0, ineffective-event=0. Total 38 -> 32, and ALL 32
remaining are legal-decline (the published flowchart's own IF-NONE fall-throughs
— "command produced no legal effect", "event not applicable", "nothing
marchable"). Deterministic across hashseeds. There are no executor rejections,
no wasted SAs, and no ineffective Events left: every census incident is the
bot/flowchart working exactly as published. Regression:
test_card_69_germans_phase_skips_empty_regions.

---

## Reconciliation — authoritative current status (June 2026)

This section supersedes every earlier "OPEN" / "DOCUMENTED (not fixed)" note.
The all-bot census (5 scenarios x seeds 1-20, deterministic across hashseeds)
is now **defect-free**: illegal=0, wasteful-sa=0, ineffective-event=0. The only
remaining incidents are legal-decline — the published flowcharts' own IF-NONE
fall-throughs, which are correct behaviour, not bugs.

### Earlier OPEN backlogs — all superseded / resolved
- "OPEN — planner quality (executor rejects cleanly)" and the various
  "residual tail" lists (resource-oblivious Rally, before-Command SA obviating
  Battle, interruptible SA timing, Raid 0-Resource steals, Suborn/Entreat
  Citadel-vs-Ally, March 'need N' / scouted-Warband, German Intimidate
  staleness, the Roman Recruit Build-SA Ally-pool case): all resolved on the
  path to illegal=0.
- "STATE-INTEGRITY QUESTION" (Mandubii 2 Citadels): resolved by the Citadel
  over-placement fix (one Citadel per Region enforced at place_piece, every
  upgrade site, and the oracle).
- Per-faction audit "DOCUMENTED (not fixed)" notes: A_RAID priority, A_MARCH
  Britannia gate, the Arverni V_BATTLE/V_ENTREAT obviation, the Belgae §8.3.4
  Battle tie-break and Enlist-destination, and the Roman Fort-per-Region
  invariant — all FIXED (annotated [RESOLVED] in place above).
- The wasteful-sa and ineffective-event tiers: cleared to 0.

### Genuinely OPEN (not defects)
1. [RESOLVED July 2026] Aedui _estimate_trade_resources player-Roman
   agreement: the estimate now assumes agreement, and the executor resolves
   the actual declaration (fixing a real §8.6.3 under-payment bug found in
   the process). See the Aedui Trade Roman-agreement section at the end of
   this file.
2. March-planner approximations (Arverni V_MARCH_THREAT, German
   G_MARCH_THREAT): the Leader destination is chosen by piece count without the
   planner predicting reachability or the §8.7.1/A8.7.1 Harassment-loss limits.
   The EXECUTOR enforces leave-behind, Control preservation, and Harassment, so
   the bot never makes an illegal or corrupting move — this is planner
   permissiveness, not a defect.

There are no correctness defects outstanding.

---

## RESOLVED — Vercingetorix March Harassment-aware routing (§8.7.1, June 2026)

Previously a known planner approximation: node_v_march_threat picked the
Vercingetorix destination by Arverni piece-count alone, ignoring reachability
and the §8.7.1 Harassment-loss limits ("fewest possible Harassment Losses ...
only to Regions reachable suffering no more than three Losses that March and
none on Vercingetorix").

FIXED:
- _verc_march_route now chooses the destination with the MOST Arverni pieces
  that Vercingetorix can reach within 2 Regions (3.3.2) by the Harassment-
  minimizing route, subject to <=3 total Losses and 0 on Vercingetorix. A
  group is safe iff total Losses <= the Warbands marching with him (Warbands
  are lost first). Harassment is predicted with the executor's own
  _np_harassers (H//3 Losses per opting Faction per pass-through Region) — one
  rule, one implementation. Ties: most Arverni, then fewest Losses, then random
  (§8.3.4).
- The planner records the chosen route in march_plan["routes"]; _execute_march
  now honours a planner-supplied per-origin route verbatim instead of BFS, so
  Vercingetorix takes exactly the Losses the planner accounted for and no other.

Remaining of the original item: only the German G_MARCH_THREAT reachability
note — the German threat-March has NO Harassment-loss cap in A8.7.1 (that limit
is Vercingetorix-specific), and the executor marches whatever it legally can, so
there is no faithful constraint left to enforce there. The Aedui Trade-yield
estimate (player-Roman 10-12 tier) remains the sole genuinely-open judgment call.

Census stays defect-free (illegal=0, wasteful-sa=0, ineffective-event=0),
deterministic across hashseeds; balance within band. Regression:
TestVercMarchHarassment.

---

## RESOLVED — German threat-March reachability (A8.7.1 / A3.4.2, June 2026)

Previously the last remaining piece of the March-planner approximation:
node_g_march_threat ranked destination Regions over ALL playable Regions, and
the executor chained BFS steps to reach a far one — over-Marching a German group
through two or three Regions.

The rules resolve this unambiguously. A3.4.2: "The German Leader and Warbands
March in the same way as Gallic Leaders and Warbands do (3.3.2; NOT into a 2nd
Region — an effect particular to Vercingetorix)." So every German group Marches
exactly ONE adjacent Region, and A8.7.1's "Regions that they can reach" means
Regions adjacent to an origin.

FIXED:
- node_g_march_threat now assigns each origin its highest-priority ADJACENT
  non-origin Region (A8.7.1 priorities a/b/c, random tie-break 8.3.4), recorded
  as a per-origin route. Deduplicated this is >=1 and <= one-per-origin distinct
  destinations (the A8.7.1 cap); origins adjacent to a shared high-value Region
  converge on it; and "March out of EACH Region" is honoured for every origin
  that has any legal one-Region destination.
- _execute_march honours a planner-supplied max_steps bound (German plan sets
  max_steps=1) so an origin can never be BFS-routed beyond its legal one-Region
  March, even absent an explicit route.

This closes the March-planner item entirely (Arverni Vercingetorix harassment
routing + German reachability both done). Census defect-free (illegal=0) and
deterministic across hashseeds; balance within band. Regressions:
test_destinations_are_reachable_in_one_region, test_executor_max_steps_blocks_
over_march.

Only genuinely-open item remaining at the time: the Aedui Trade-yield estimate
(player-Roman agreement) — resolved below (July 2026).

---

## RESOLVED — Aedui Trade: Roman agreement in the trigger estimate and at execution (§4.4.1 / §8.6.3, July 2026)

**The ambiguity (real, but narrow).** The §8.6.3 A_TRADE trigger asks whether
"Trade would add > 2 Resources," and the yield depends on Roman agreement
(§4.4.1: doubles Aedui Ally/Citadel yields and switches on Subdued/Roman-Ally
sources). The flowchart says only "Non-player Romans agree" — it is silent on
a *player* Rome because at a physical table there is nothing to forecast: the
humans running the bot resolve the declaration live. Any software forecast is
therefore an approximation, not a rules reading. BGG search confirmed a player
Rome may refuse (a real tactic against an Aedui close to winning) and turned
up no designer ruling on bot forecasting — consistent with "resolved live."

**Decision: assume agreement in the trigger estimate** (`romans_agree = True`
in `_estimate_trade_resources`), replacing the old `victory_score(Rome) < 10`
heuristic. Rationale:
1. The old heuristic keyed on the wrong variable. A Rome refuses to deny an
   Aedui who threatens to win — a function of *Aedui* standing, not Rome's.
   Predicting refusal whenever Rome is comfortable has no basis; a
   comfortable Rome has the least reason to starve its ally.
2. Cost asymmetry favors optimism. The estimate gates only the ">2" trigger
   arm; the trigger fires only when the Aedui are poor. Wrong-optimistic is
   recoverable at resolution (call-off / reduced yield); wrong-pessimistic
   silently skips Trades the table would allow.
3. The alliance's designed default is cooperation (why NP Rome auto-agrees),
   and agreement is usually buy-able ("offer some of the added Resources").
The estimate also strips `decision_agent` from its throwaway sim, so a yield
estimate can never interactively ping a live agent (determinism).

**Real bug found while verifying the execution path:** `_execute_trade`
called `trade(state)` with the default `roman_agreed=False` — every executed
Trade paid the un-doubled rate and skipped Subdued/Roman-Ally yields, even in
all-bot games where §8.6.3 says NP Romans always agree. The estimate
predicted the doubled yield; execution paid half. FIXED:
`_execute_trade` now resolves the declaration at SA time via
`_trade_roman_agreement`: NP Rome → agree (§8.6.3); player Rome → consulted
through the existing decision-agent AGREEMENT hook
(`request_type="trade_roman_agreement"`, the same channel
`_region_allows_supply_line` uses for Supply Lines); no agent / agent defers
→ the alliance default, agree. Aedui bot Trade income roughly doubles in
all-bot games.

**Not modeled (documented approximation):** the player-Aedui right to call
off a Trade after hearing declarations ("the Aedui may call off the Trade if
unhappy"), and side-payment negotiation. For the NP Aedui, an agent-Rome
refusal simply resolves at the un-doubled §4.4.1 rate; the flowchart gives
the NP Aedui no call-off logic.

**Regressions:** test_trade_triggers_with_player_rome_at_high_score (player
Rome at victory score >= 10, Trade now triggers when agreement clears the >2
bar), test_trade_estimate_assumes_player_roman_agreement,
test_executed_trade_np_rome_pays_agreed_rate,
test_executed_trade_player_rome_consults_agent (agent refusal → base rate;
no agent → agreed rate).

**Verification:** 2009 tests passing; census seeds 1-20 illegal=0 and
byte-identical under PYTHONHASHSEED=0 and 7 (legal-decline 40 → 28, all
remaining incidents published IF-NONE fall-throughs, none Aedui); balance
canary within band — no rebaseline needed.

No genuinely-open judgment calls remain.

---

## NEW INSTRUMENT — player-action fuzzer (fs_bot.tools.player_fuzz, July 2026)

The error census fuzzes only BOT decisions; nothing exercised the
human-facing action surface at volume. `player_fuzz` closes that: each game
seats a random subset of factions as *players* (removed from
`non_player_factions`, so player-vs-NP code paths — Trade Roman-agreement
consult, German player-target priorities, the player-Rome Quarters default —
genuinely run) driven by RandomPlanPolicy, with fully randomized reactive
decisions (Retreat / Loss order / Agreements) through the decision-agent
hook. Oracles per game: crash; structural integrity at every turn boundary
and at game end; dry-run-vs-live execution divergence (the chosen plan is
re-dry-run at decision time under a CLONED reactive agent with cloned rng,
so live must match exactly); and replay determinism (double-run digest).
All fuzz randomness derives from `random.Random(str)` (sha512), so batch
digests must be identical across PYTHONHASHSEED values — that comparison is
the cross-hashseed determinism oracle, now a CI job (seeds 1-40, HASHSEED
0 vs 7, diff of full output).

**Harness lesson (not an engine bug):** `moves.validate_player_action`
strips the decision agent, so a dry-run can legitimately diverge from live
execution wherever resolution consults an agreement (e.g. Recruit
supply-line cost, Harassment) — table-accurate behaviour. The fuzzer's
divergence oracle therefore dry-runs under a cloned agent, not a stripped
one. First naive sweep "found" 3 divergences that were exactly this.

**Real defect found and fixed:** `execute.py::_choose_free_battle` (the
A21/A28/A57/Legiones free-Battle deriver) iterated its ``allowed_regions``
argument — a set from `_free_battle_region_set` — and broke score ties by
iteration order, leaking PYTHONHASHSEED into which Region/defender a
Non-player attacks. Found by the cross-hashseed digest oracle on mixed
games (Ariovistus seed 27, The Great Revolt seed 47 diverged between
HASHSEED 0 and 7); invisible to the bot-only census at seeds 1-20 because
no tie arose there. Fixed by iterating `sorted(allowed_regions)` (the
repo's deterministic tie-break convention, cf. sa_trade card-39). This was
precisely the class CLAUDE.md's determinism rule worries about: a set
built/iterated in decision logic upstream of the choice.

**Status:** 500 fuzzed games (5 scenarios x seeds 1-100), double-run,
hashseed-identical, ZERO hard findings (crash=0 structural=0 divergence=0
nondeterminism=0). Soft "partial" incidents (validated plans whose
sub-actions partially fail under partial-execution semantics) are the
random policy's own sloppiness, reported but not defects. Regressions:
test_player_fuzz.py (shapes, determinism, clean smoke incl. the two
formerly-diverging games), test_free_battle_tie_break_is_input_order_
independent.

**Not yet fuzzed:** player EVENT execution — CLOSED by the extension below.

---

## EXTENSION — player Event fuzzing + transactional Events (July 2026)

player_fuzz now fuzzes player EVENT execution: seated players play Events on
~50% of SoP turns where legal, with `event_params` generated three ways —
NP-derived (well-formed), mutated-derived, and from-scratch against the
param-key inventory harvested from card_effects.py source (auto-tracks new
cards). Every generated param set is dry-run in an isolated sim with two new
oracles: **event-crash** (handler raised outside the _EVENT_SAFE_ERRORS
"report, do not crash" contract) and **dirty-event** (handler reported
not-applicable but MUTATED the board — a half-applied Event). The outcome
signature now also includes the refusal reason, sharpening the dry-vs-live
divergence oracle.

### Defects found and fixed

1. **Half-applied Events (systemic) — `_execute_event` is now
   TRANSACTIONAL.** Card 62 (War Fleet) applied its per-move list one move
   at a time and set its event modifier BEFORE validating; a later illegal
   move raised a safe error, leaving earlier moves and the modifier behind
   an ``executed=False`` "not applicable" report. The class is generic (any
   handler that mutates mid-loop then raises), so the fix is at the
   dispatcher: `_execute_event` snapshots the state and rolls back on the
   safe-error path. "Report, do not crash" now also means "a failed Event
   did not happen." The decision agent is shared (never copied); the rng is
   part of the snapshot, so failed-Event die rolls roll back too —
   replay-deterministic either way.

2. **Card 62 region constraint unenforced.** Moves are "among Arverni
   Region, Pictones, and Regions within 1 of Britannia"; the handler moved
   pieces between ANY regions. All moves now validated (endpoints in the
   allowed set, required keys) before any is applied.

3. **Tribe<->piece desync via unvalidated `piece_type` (A35, A51, A69).**
   The structural oracle caught A35 unshaded placing 4 tribe-less Aedui
   Ally pieces at Treveri from a fuzzed ``piece_type="Ally"`` — the card
   allows "up to 8 Warbands or 4 Auxilia" only. Same unvalidated pattern in
   A51 ("4 Auxilia or Aedui Warbands") and A69 ("4 Warbands/Auxilia", plus
   the Ally must be Roman/Aedui; A35's Ally must be Gallic/Roman). All
   three now raise ValueError on illegal types/factions (rolled back
   cleanly by fix 1).

### Status

525 event-fuzzed games (5 scenarios x seeds 1-105, double-run), ~4,200
fuzzed Event turns: ZERO hard findings, batch digests identical across
PYTHONHASHSEED 0 and 7. Suite 2017 passing; bot-only census unchanged
(illegal=0, 28 legal-declines, hashseed-identical); balance canary within
band. Regressions: test_execute_event_rolls_back_failed_event,
test_card_62_moves_restricted_to_coastal_regions,
test_card_a35_a51_a69_reject_illegal_piece_types, and the fuzz smoke now
replays every past catch (Great Revolt 1/47, Ariovistus 27, Gallic War 73).

Remaining fuzz frontier: param generation is name-heuristic typed, so
deeply-structured params (multi-step moves with piece_state/leader_name,
card-specific nested shapes) are exercised mostly through the derived +
mutated modes on the 25 derivable cards; a per-card schema would deepen
coverage of the other ~90 handlers' success paths (their failure paths are
now well covered).

---

## PRODUCT SURFACE — CLI completed: execution, reactive play, save/resume/replay (July 2026)

The CLI predated the executor: `app.py` ran `run_game(state, decision)`
with the default ``execute=False`` — every CLI game, human or bot, decided
but never moved a piece ("decision layer only" was stale truth). Completed
in this pass:

1. **Full execution wired.** The CLI now runs its own card loop via
   `play_card(execute=True)`, displays each card's outcome including
   execution failures/sub-action warnings, and pauses between cards.
2. **Reactive play for humans** (`cli/reactive.py`): the decision-agent
   hook now prompts human seats for Retreat (§3.2.4/§8.4.3), Loss order
   (§3.2.4, piece by piece with a default-order escape), and §1.5.2
   Agreements (Supply Line, Retreat-into-Control, Trade, Harassment...).
   Previously human factions silently got NP defaults.
3. **Validation feedback loop** (menus.prompt_action): every collected
   human plan is dry-run via moves.validate_player_action; failures show
   the reason and offer a re-plan; partial-effect plans show warnings and
   ask for confirmation. EOF keeps the plan (the executor stays the final
   validator), so scripted/piped input cannot hang.
4. **Save / resume / replay** (`state/serialize.py`): exact JSON round-
   trip of the state — tagged encoding for sets, tuples, non-str-keyed
   dicts (capabilities), and the rng position (so a resumed game continues
   byte-for-byte; CLAUDE.md determinism). `--save` autosaves after every
   card and on interrupt/crash; `--load` resumes the snapshot; `--replay`
   re-runs a game from its logged human decisions + reactive responses
   (rebuilt from scenario+seed) and goes interactive when the log ends.
   Every game now gets an explicit seed so it is always replayable.
   Tested property: interrupt mid-game + resume produces a byte-identical
   end state to the uninterrupted run.
5. **Plan-builder completeness.** Rally can now place Citadels (§3.3.1
   upgrade, Aedui/Arverni). SA collectors emit the executors' real plan
   shapes for Suborn (§4.4.2, ≤3 pieces/1 Ally), Entreat (§4.3.1),
   Rampage (§4.5.2), Intimidate (A4.6.2), and Enlist (§4.5.1 five
   Germanic sub-commands); Trade needs no plan and Build/Scout recompute
   faithful plans against the board. Event params for humans: the keys a
   card's handler reads are extracted from its source (auto-tracks new
   cards), the NP-derived "standard choices" are offered as a default
   where a deriver exists, and each key gets a typed, skippable picker.

Verification: 2027 tests (new: end-to-end CLI games via a scripted
player — full bot game + replay equality, human game, interrupt/resume
byte-equality, log-driven replay; collector unit tests; serialize
round-trip incl. rng). Census and player_fuzz unchanged and
hashseed-identical; canary in band.

Known limits at the time: the generic event-param entry collector only
prompted a common field set — CLOSED by the per-card schemas below.

---

## PER-CARD EVENT-PARAM SCHEMAS (cards/param_schema.py, July 2026)

Every card handler's ``event_params`` reads are now extracted from its own
AST into a typed schema: scalar keys with kinds (region / faction / tribe
/ count / direction / piece_type / piece_state / leader_name), plural
lists of scalars (``list:tribe`` etc.), and ``entries`` lists carrying the
exact per-entry fields the handler reads (``for m in params.get("moves"):
m["from_region"] ... m.get("piece_state")``). Extraction is from source,
so schemas track new/changed cards automatically;
test_schema_covers_every_params_key_all_cards sweeps every handler to
keep them complete. ``_OVERRIDES`` adds the card-legal value constraints
(A35/A51/A69 piece types, card 26 placements, card 62's coastal region
pool, card 71's colony name omitted — see below).

Consumers:
- **CLI**: a human Event now prompts every key and entry field with typed
  pickers drawn from the shared kind vocabulary — including the rare
  fields (piece_state, leader_name, from_type) the old heuristic
  collector could not ask for — and only offers card-legal values where
  a constraint is known.
- **Fuzzer**: a new schema mode generates typed, complete params — the
  success-path generator for the ~90 cards without an NP deriver (their
  failure paths were already covered). The report now prints
  ``events-ok`` (dry-run-executed player Events) to track success-path
  coverage: ~98% of fuzzed player Event turns now execute.

### Defects found immediately by schema-mode fuzzing (fixed + regressions)
1. **Card 26 (Gobannitio) unshaded** — ``place_faction``/``place_type``
   unvalidated: any faction/piece pair was placed at Gergovia and the
   Tribe marked allied behind it (a Warband-backed "Ally" — tribe<->piece
   desync). Now only a Roman Ally or an Aedui Ally/Citadel, per the card.
2. **Card 71 (Colony)** — ``colony_tribe_name`` unvalidated: a name
   matching an existing Tribe silently OVERWROTE that Tribe's allegiance
   entry (fuzz case: "Lingones", stranding its Aedui Ally piece in
   Mandubii). Existing names now raise; the schema omits the key so
   humans/fuzzers use the safe per-Region default.

### Status
Sweeps: seeds 1-115 x 5 scenarios (575 games, ~4,900 fuzzed player
turns per 100 games incl. Events), double-run, hard-findings=0,
batch digests identical across PYTHONHASHSEED 0/7. Suite 2038 passing;
census unchanged (illegal=0, hashseed-identical).

---

## REACTIVE-DECISION HOOK COMPLETENESS (July 2026)

Audit of every reactive decision point against the decision-agent hook —
the class the Trade Roman-agreement bug belonged to (a player faction's
choice silently made for them by NP logic).

Already wired: Supply Line (§3.2.1), Trade Roman agreement (§4.4.1),
Quarters host agreement (§6.3.3), defender Retreat (§3.2.4), Retreat
into another's Control (§3.2.4), Loss order (§3.2.4).

**Gaps found and wired (agent defers -> NP logic, all-bot unchanged):**
1. **Harassment opt-in (§3.2.2)** — `_np_harassers` (all March
   intermediate stops + Seize) applied the §8.4.2 NON-PLAYER table to
   player factions: e.g. a human Aedui could never Harass a Belgic March
   because the NP instruction says the Aedui only Harass Vercingetorix.
   Player factions with 3+ Hidden Warbands are now consulted
   (AGREEMENT / "harassment", context: region, hidden_warbands,
   vercingetorix); the table remains the NP default.
2. **Rampage target response (§4.5.2)** — the target's remove-vs-Retreat
   choice was auto-decided by the NP defaults (§8.4.1/§8.4.3) even for a
   player target. Player targets are now consulted (RETREAT kind with
   ``context={"rampage": True, "num_pieces": n}``); A4.5 forced removal
   (Ariovistus Arverni) bypasses the choice as the rule requires.

CLI: reactive.py gained tailored prompts for both (harassment opt-in
defaults to No — it is an opt-in, not a favour; Rampage offers
remove-vs-retreat with legal destinations). The fuzzer's random reactive
agent covers both automatically (AGREEMENT coin flip / RETREAT choice),
so mixed-game sweeps now exercise player harassment and Rampage
responses; agent.py documents the wired request_types.

**Not modeled at the time:** voluntary resource transfers — CLOSED by
the section below (July 2026).

Verification: 2040 tests (new: harassment opt-in consult honored +
NP-table fallback; Rampage player-choice honored + NP fallback);
census unchanged (illegal=0); fuzz sweeps seeds 1-90 all scenarios
hard-findings=0, hashseed-identical.

---

## RESOLVED — voluntary Resource transfers (§1.5.2/A1.5.2) + the §8.6.6 NP Aedui subsidy (July 2026)

**Rule basis.** §1.5.2: a Faction may transfer Resources to another during
either's SoP execution of a Command or Event; any amounts to non-German
Factions during the Winter Quarters/Harvest Phases; A1.5.2 lets Ariovistus
Germans give/receive like everyone else. §8.4.2/§8.6.6/§8.8.6: NP Belgae,
Arverni, and Romans never voluntarily transfer; NP Aedui transfer 10 to
the Romans at each instant Roman Resources drop below 2 while the Aedui
hold more than 20 (per the §8.6.6 NOTE, gated for player Romans by the
victory tiers: NP always, <10 always, 10-12 on a 1-4 roll, >12 never).

**What existed before: nothing that moved Resources.** Every bot's
agreements node had the "resources" decision logic — and no code ever
called it. The mandatory §8.6.6 subsidy simply never happened.

**Implemented:**
1. `commands/transfer.py::transfer_resources` — validation: distinct
   factions, positive amount, base-game German exclusion, card 38 shaded
   (Diviciacus) Rome<->Aedui ban, giver stock; receiver caps at
   MAX_RESOURCES with the giver paying only what arrives.
2. §8.6.6 subsidy (`execute.maybe_np_aedui_subsidy`) — checked after
   every executed SoP action and after the Winter Quarters/Harvest
   phases (the documented approximation of "at each instant"). The
   score gates were also ADDED to node_a_agreements' "resources" branch
   (it previously ignored the §8.6.6 NOTE). Post-Q12, NP Rome rarely
   drops below 2 Resources (measured: never in 100 census games), so
   the subsidy is the safety net the rule intends, not a balance shift
   — census and canary unchanged.
3. Player transfers ride the plan: ``details["transfers"] = [{"to",
   "amount"}]`` on any Command/Event player_action, applied by
   execute_decision (errors reported, never blocking the action) — so
   save/replay, the validation dry-run, and the fuzz oracles all get
   them for free. CLI: a menu-driven optional gift on each Command/
   Event (first option "No"; one grouped gift per action — documented
   simplification, as is the lack of interactive transfers during
   Winter and of the 4-per-execution same-player cap, which cannot
   bind when no player runs two Factions).
4. Fuzzer: ~12% of fuzzed plans carry a random transfer (both legal and
   illegal — the German ban and stock errors are exercised); outcome
   signatures include transfer results; the dirty-failure oracle skips
   transfer-carrying plans (a §1.5.2 gift legitimately stands even when
   the action fizzles).

**Two more silent corruptions found by the reshuffled sweeps, fixed:**
1. **Suborn allied Dispersed Tribes** (§4.4.2/§1.7): both the Suborn
   mechanic's validation AND the Aedui bot's planner tested only
   ``allied_faction is None`` — a Dispersed-Gathering Tribe passed as
   "Subdued", the NP Aedui allied it, and the next Spring Phase cleared
   the marker AND the allegiance, stranding the Ally piece (Gallic War
   seed 2). Both now require ``status is None``. Rally/Recruit already
   checked status; Suborn was the hole.
2. **Card A51 shaded stranded allegiances**: removing a Roman/Aedui
   Ally disc at Atrebates never called clear_allied_tribe (Q13 desync
   class; Ariovistus seed 45). Also fixed the same class in card 22
   unshaded, which accepted ANY piece_type for its "Warbands or
   Auxilia" replacement (now rejected; control requirement also
   enforced; schema override added).

Verification: 2054 tests passing (13 new); census 26 legal-declines /
illegal=0 both hashseeds (26 vs 28: the Suborn planner fix changed two
games' trajectories); fuzz sweeps seeds 1-85 all scenarios
hard-findings=0, hashseed-identical.


---

## Card-audit gaps closed — reconciliation (July 2026)

The audit's "Remaining — larger engine features" list was stale: later
passes implemented nearly all of it without updating the ledger. Verified
item by item against current code, with tests added where coverage was
missing:

- **A34 unshaded** — IMPLEMENTED (`execute._resolve_card_A34_german_pieces`:
  borrowed-German free Battles in up to 3 Regions, never against the
  acting Faction; free March permitted via the same layer). New test:
  test_card_A34_unshaded_borrowed_german_battles.
- **A70 shaded** — IMPLEMENTED (end-of-action Nervii-Subdued hook in
  execute.py + Rally-at-Nervii +2 Warbands in rally.py); already tested.
- **A53 unshaded** — IMPLEMENTED incl. the granted +1 Special Activity
  (`_resolve_card_A53_frumentum`: transfer + free Recruit + free March +
  free Build SA). New test: test_card_A53_unshaded_grants_recruit_march_
  and_sa.
- **Card 11a unshaded** — IMPLEMENTED (`_free_double_aux_battle(...,
  auxilia_only=True)` restricts the attack to Auxilia); already tested.
- **A29 / A40 unshaded** — IMPLEMENTED (Settlement gating + 2-Ally/5-WB-
  or-3-AUX caps; 3-Region + per-Region caps; NP derivers exist for both);
  already tested.
- **Minor tail** — A65 "without Leader" (no_attacker_leader=True), card 57
  Britannia-conditional +4, card 19 shaded on-map Successor branch, A20
  as-if-Roman-Control Disperse, cards 30/39 2nd-ed text-change handlers:
  all present and consumed.

**The one real gap found and closed: A70 unshaded ("Belgae never
Retreat").** The handler set `card_A70_no_belgae_retreat` and the battle
mechanic refused Belgae Retreats (persisting un-popped — correct
capability semantics), but `_decide_defender_retreat` neither knew the
modifier nor A33's German equivalent: NP logic could still DECLARE a
Retreat (harmlessly refused downstream) and, worse, a human Belgae
defender was consulted about a choice that does not exist. Both
modifiers now short-circuit the decision (no agent consult), mirroring
the base-German/Ariovistus-Arverni lines. End-to-end test proves the
declared-Retreat refusal, the consult skip, and the modifier's
persistence.

Verification: 2057 tests passing; census illegal=0 both hashseeds (26
legal-declines); fuzz seeds 1-20 hard-findings=0, hashseed-identical.


---

## PLAY QUALITY PASS — telemetry instrument + two major fidelity finds (July 2026)

New instrument `fs_bot.tools.play_quality`: per-faction command/SA mix,
no-effect turns, pass and event rates, resource dynamics (at-zero /
at-cap), win distributions and game lengths across bot-only games. The
census guarantees legality; this measures whether a legal bot is
BEHAVING like the published flowcharts.

### Find 1 — German Rally+Settle turns wasted (A8.7.4)
The Germans' "Rally and Settle" is ONE combined node: they take it "if
doing EITHER would place a Germanic Ally, a Settlement, or at least four
Warbands". The executor's wasteful-sa rule ("command produced no legal
effect -> skip the SA") cancelled the Settle whenever the Rally itself
placed nothing — the Germans wasted their whole turn ~10 times per 20
games. Fixed with a scoped exemption (`_sa_survives_empty_command`);
census incidents fell 26 -> 6. Telemetry now counts a no-effect TURN
only when no SA salvaged it.

### Find 2 — The Gallic War second half never happened (A2.1)
`is_final` treated the first half's 3rd Winter as the game's last:
victory_phase declared a margins winner, and the Interlude — fully
implemented — was UNREACHABLE. Every Gallic War game was byte-identical
to Ariovistus. Chain of fixes to make the second half real:
1. `is_final=False` for pre-Interlude Gallic War Winters (outright
   victory still ends the first half, per "If the game does not end by
   the 3rd Victory Phase").
2. `_count_winter_cards_in_game` survives the Interlude's deck reset
   (winter_count-based), so the second half's LAST Winter is final;
   run_game's total_cards_played likewise (len(results)).
3. **Card O38** (2nd-Ed Diviciacus, A2.1 Deck) implemented: card data,
   handler (unshaded returns Diviciacus FROM the removed pool; shaded =
   base card 38's capability so the existing Rome<->Aedui transfer ban
   applies), NP deriver (§8.3.2-style placement), schema/dispatch for
   the "O38" id. remove_piece now tracks Diviciacus in removed_pieces
   at EVERY removal site (conservation exact; O38 returns him).
4. **Scenario switch**: the second half IS Pax Gallica? — the Interlude
   now sets state["scenario"] accordingly, which makes every rules gate
   (SoP factions, game-run Germans §3.4/§6.2, base Retreat rules, base
   card texts, Winter phases) apply the base game automatically.
   Diviciacus proximity gates (Trade/Suborn/Aedui Ambush, A4.1.2) are
   keyed on the PIECE, not the scenario, so O38 keeps his rules alive;
   piece caps use Ariovistus totals for the German inventory and the
   Diviciacus Leader (`_second_half_caps`); A6.5.1's no-shift Senate is
   keyed on its flag; Britannia's Tribe entries are backfilled.
5. **Seat swap** (A2.1 "the Germanic player takes on the role of the
   Arverni"): the Interlude swaps non_player_factions membership; the
   CLI remaps a human German seat to Arverni mid-game; the fuzz harness
   does the same.
6. **Interlude Q13 repairs** — the force adjustments predated the sync
   discipline and desynced tribes from pieces (player_fuzz structural
   catches, seeds 30/73): Citadel->Ally replacements now keep the CITY
   tribe allied (they used to ally a random second tribe with the bogus
   status "Allied"); every Ally/Citadel removal (faction loops,
   circumvallation, Gergovia/Bibracte resets, Cisalpina relocation)
   pairs with clear_allied_tribe; Gergovia/Bibracte/Britannia Ally
   placements name their city Tribe explicitly.
7. **Card 40 (Alpine Tribes) unshaded** hardened while fuzzing the new
   second half: "3 Warbands, 2 Auxilia, or 1 Ally" — piece types now
   validated and per-Region caps enforced (a fuzzed Citadel placement
   used to strand a backing piece).
8. Fuzz oracle: dry-run signatures are keyed by (card, faction,
   OCCURRENCE) — the two-deck Gallic War repeats card ids across halves.

### Balance observations (recorded, not tuned)
Win rates, 20 seeds/scenario, current main: Pax Gallica Romans 16/20;
Great Revolt Arverni 13/20; Reconquest 8/5/4/3 (R/Ae/B/Ar); Ariovistus
9/7/2/2 (R/G/Ae/B); Gallic War now two-act with second-half winners
across Romans/Belgae/Aedui/Arverni. Romans never Seize in base
scenarios — faithful: §8.8.5 Seize is the LAST fall-through and the
post-Q12 Romans always find a better Command. Aedui Ariovistus pass
rates (~9%) are faithful destitution (all Pass turns sampled at 0
Resources with 0-2 Warbands on map). Whether these distributions match
the published design's table balance is a playtest question, not a bot
defect.

Verification: 2063 tests passing (new: second-half reachability + seats,
interlude structural integrity, O38 round-trip, card 40 caps); census 6
legal-declines / illegal=0 both hashseeds; fuzz seeds 1-50 all scenarios
hard-findings=0, hashseed-identical.

**Hardening sweep of the new second half (post-5cf7df5):** fuzz seeds
41-115 (375 more games incl. full two-act Gallic Wars) hard-findings=0;
census seeds 21-40 illegal=0 (5 legal-declines); everything
hashseed-identical — the first newly-opened territory to come up clean
on its hardening pass. Balance ledger refreshed with current bot-only
distributions (selfplay-strategy-notes.md July addendum); play_quality
pinned into the suite (test_play_quality.py).


---

## RULES TRACEABILITY PASS — every numbered section accounted for (July 2026)

New instrument `fs_bot.tools.rules_trace`: parses all numbered rule
sections out of the Reference Document chapters (261 sections, base
Chapters 1-8 + Ariovistus A1-A8) and counts citations of each across the
source. `test_rules_trace.py` gates the result: every section must be
cited in code or allow-listed as not-applicable WITH A REASON — new
sections or citations lost to refactors fail the suite.

Census result: 248/261 cited before the pass; 13 flagged and triaged:

**Genuine behavioral gap found and fixed — §8.3.3 (Using Capabilities):**
"Non-players use Capabilities that apply to a limited number of Regions
in the FIRST Regions that apply." Card 39 shaded (Trade is maximum 1
Region) picked the BEST-VALUE Region even for a Non-player Aedui. NP
Aedui now Trade the first applicable Region in standard map order; a
player Aedui keeps the highest-yield choice (players choose freely).
Deliberate deterministic change (fuzz digests moved; canary in band).

**Implemented but uncited (citations added at the implementing sites):**
- §5.1.1 Events vs Rules (never place unavailable pieces / remove rather
  than replace / stacking) — enforced across handlers; cited in
  card_effects' module docstring.
- §5.1.3 Partial Execution — honoured INSIDE handlers (skip what cannot
  apply); reconciled explicitly with the transactional Event layer: a
  raise is reserved for invalid parameters or a wholly inapplicable
  Event, and the CLI validation loop means the plan that finally
  executes satisfies §5.1.3.
- A6.4.1 Ariovistus Roman earnings — the "less Settlements" term lives
  in calculate_victory_score (A7.2); cited at harvest_phase.
- A5.1.1 / A5.4 — structurally inert for the game-run Arverni (outside
  the SoP; no path grants them Entreat/Devastate); cited at
  get_sop_factions.
- A3.1 — chapeau; specifics carried by the cited A3.4.x sections.

**Not applicable (allow-listed with reasons in rules_trace.py):**
3.1.1 (physical pawns), 8.1.3 (how to read the flowchart sheets),
A1.0 (introduction), A1.4.1 (Available Forces display layout),
A1.5.1 (three-player seating; the related 4-Resource transfer cap note
lives in commands/transfer.py), A2.2 (cylinder colour swap).

Verification: 2068 tests passing; census illegal=0 both hashseeds; fuzz
hard-findings=0, hashseed-identical.


---

## DEEP-SOAK CI (July 2026)

`.github/workflows/deep-soak.yml` — weekly (Mondays 09:00 UTC) and
on-demand (Actions -> deep-soak -> Run workflow, seed ranges
overridable):

- **census-soak**: `error_census --strict` over seeds 1-500 (2,500
  bot-only games) under PYTHONHASHSEED 0 and 7, full-output diff. The
  new `--strict` flag exits nonzero on any defect-class incident
  (illegal / wasteful-sa / ineffective-event / other-refused);
  legal-decline never fails.
- **fuzz-soak**: `player_fuzz` over seeds 1-300 (1,500 player-surface
  games, each double-run for replay determinism) under both hashseeds,
  full-output diff; the tool already exits nonzero on hard findings.
- **telemetry**: `play_quality --seeds 1-40` snapshot uploaded as an
  artifact for trend-watching (informational; never fails).

Rationale: rare-path bugs surface at volume — the per-push CI runs
~10-25x shallower. All three step bodies rehearsed locally; runtimes
calibrated (~12s per 100 census games, ~30s per 100 fuzzed games) to
fit well inside the 60-minute job timeouts.


---

## HUMAN-SEAT PLAYTHROUGH FINDINGS (July 2026) — three engine bugs

Played the Aedui seat live against the bots (Pax Gallica?, seed 42) via
a turn-by-turn harness on the save/load layer. Three real bugs in as
many hours of play:

1. **Suborn remove_ally trusted the plan's tribe name** — naming a tribe
   not allied to the target faction removed the enemy piece while
   un-allying the NAMED tribe (my own). Silent desync that
   validate_player_action cannot catch (the plan executes); only the
   structural oracle sees it. Validator now requires the named tribe to
   be the target's allied tribe in-region; unnamed removals pair via
   clear_allied_tribe. (Commit 07c5ee7.)
2. **Setup wrote the legacy tribe status "Allied"** — removal paths
   cleared allied_faction but left the status, creating zombie tribes:
   never Subdued again, invisible to §7.2 Roman scoring, Suborn, and
   the CLI. Setup now writes status None; every allegiance-clearing
   path normalizes the legacy value. (Commit 07c5ee7.)
3. **Pax Gallica's 1st-Winter Special Rules were dead state** — setup
   stored them (skip Victory Phase, skip Germans Phase, 3 Winter-Track
   Legions to Belgica at Harvest, Senate set to Intrigue, Vercingetorix
   in the Spring box) and NOTHING consumed them. Consequences: Rome —
   opening above the >15 threshold — won at the first Victory Phase the
   rules say to SKIP (min game length was 6 cards; a large share of the
   16/20 Roman wins were illegal victories), and Vercingetorix never
   entered the scenario at all (spring_box_leaders had no consumer).
   run_winter_round now consumes the specials once (victory/Germans
   skips, Belgica Legions with a documented NP default of the
   piece-heaviest Belgica Region, Senate forced to Intrigue,
   Vercingetorix placed per §8.3.2); the Gallic War Interlude sets the
   same specials for its second half's first Winter (A2.1 Quarters-box
   marker). Post-fix Pax Gallica: min game length 23 cards (was 6);
   Rome still wins 15/20 but at later Winters — the remaining tilt is a
   design observation, not an engine defect.

Also fixed en route: the played observation that removing ANY Ally
feeds Roman scoring (correct §7.2 behaviour post-zombie-fix) — recorded
as Aedui strategy guidance, not a bug: prefer placement-denial over
removal when Rome nears the threshold.


---

## PLAYTHROUGH VERDICT — the Aedui seat, played with skill (July 2026)

Full game, Pax Gallica? seed 42, me (human) as Aedui vs three bots, via
a turn-by-turn harness on the save/load layer. Result: Rome wins the
2nd Victory Phase at exactly 16 (>15), with the played Aedui SECOND at
margin +1 — ahead of every Gallic faction, one denial (a queued
Pictones Suborn) and one card short of forcing the game long.

**Engine findings (all fixed during play, commits 07c5ee7/ff8cf17 +
subset-March):** Suborn tribe-allegiance validation; zombie "Allied"
status; the unconsumed Pax Gallica 1st-Winter Special Rules (illegal
Roman Winter-1 victories, Vercingetorix never entering); human
subset March (§3.2.2).

**Known remaining human-play gap:** one origin cannot March TWO groups
to different destinations in one Command (§3.2.2 allows it; the plan
shape keys groups by origin). Workaround: successive turns. Fix shape
when wanted: per-column entries [(origin, destination, group), ...].

**Seat verdict (played evidence, not telemetry):** the Aedui seat is
strong in human hands. The engine that emerges: Trade snowballs with
board position (march-to-control of subdued-tribe supply-line regions
took a single Trade from 4 to 10), Convictolitavis (card 43 unshaded)
doubles Suborn, and every Suborn ally placement is DOUBLE-duty in this
scenario (+1 Aedui, -1 Rome — placement is denial). The bot Aedui
plays the same verbs but never marches hidden Warbands INTO new
subdued-tribe regions to extend Suborn/Trade reach — its flowchart
Suborns only where it already stands (§8.6.3 as published). That, plus
no faction coordinating denial, is why bot-only Rome still runs away
(~15/20): the design appears to assume table diplomacy against the
runaway leader, which three flowcharts cannot supply. Design
observation, not an engine defect.

**Aedui strategy notes for the human player:** never leave a lone Ally
in an Arverni-controlled Region (Entreat removes it for 1 Resource);
prefer placement-denial over Ally-removal while Rome is near the
threshold (every removed Ally of ANY faction is +1 Roman Subdued);
Raid is a free Command to carry a Suborn when the treasury is at 2.


---

## SECOND PLAYTHROUGH — the Roman seat, The Great Revolt (July 2026)

Full game, Great Revolt seed 42, me (human) as Rome vs three bots.
Result: Belgae outright at Winter 2 (margin +6; Rome -7) — but the
probe's finding is what happened on the way.

**A played Rome broke the Arverni.** The 13/20 bot-only Arverni
dominance evaporated against basic Roman discipline: never battle
Vercingetorix's stack, hunt naked Allies with the Legion army early
(Sequani: citadel+ally killed in one blow), then storm the emptied
Gergovia with an AUXILIA column while the horde was north (both home
Allies, then the citadel, then Seize-dispersal of the homeland).
Arverni allies+citadels: 14 -> 5; their off-map-Legions condition froze
at 4 of the needed >6 once the Legions bunkered in supply lines.

**The two-runaway structure.** With every sword pointed at the Arverni
— mine, and then Vercingetorix pointing his at the BELGAE in a genuinely
impressive bot turn (his horde stormed Atrebates and Britannia when the
Belgae became the leader) — the quiet faction compounded allies+control
unopposed: 12 -> 15 -> 21. Rome's armies cannot reach Belgica in time
from the south. Confirms the Aedui-game conclusion from the other side:
Great Revolt bot-only is decided by whichever Gallic faction the table
ignores; three flowcharts cannot cover two simultaneous runaways. The
design assumes players redistribute pressure; that is diplomacy, not a
bot defect.

**Engine findings:** player-Rome Quarters fixed mid-game (commit
14c9524 — roll-for-all was the seat's hidden loss condition; my two
stranded Treveri Legions still died to a fair rule: consolidation
errors are punished). Observation for later: a human Build SA executes
the BOT's §8.8.1 plan (fort/subdue/ally placement is not the player's
choice) — same class as the old Quarters gap, lower stakes; and the
Aedui bot ended the game hoarding 37 Resources with no Suborn pressure
on the runaway — its flowchart spends only on self-development,
never on leader-denial. Both recorded as play-quality items, not
defects.

## Playthrough verdict 3 — Germans, Ariovistus (July 2026)

Seat: Germans (player) vs NP Rome/Aedui/Belgae, Ariovistus scenario,
seed 42, /tmp harness (save/queue snapshots at card boundaries).
**Result: German win at Winter 3** — score 7 (>6): Ubii + Sugambri
under Germanic control plus Settlements under control at Treveri,
Nervii, Morini, Sequani, Aedui. Rankings: Germans 1st, Rome 2nd
(margin -2), Aedui, Belgae.

**The German seat plays like a race with a wrecking crew loose.**
Settle is a dual-purpose engine (each Settlement is +1 toward >6 AND
-1 to the Roman score), and March+Settle in one command — Settle
validating control AFTER the March resolves — is the seat's core
tempo move; the engine handles it correctly. Settlements are
battle-removable last-priority pieces, so a thin settlement empire
invites eviction: Rome, the Belgae (Sabis), and the Arverni Phases
destroyed three of my Settlements mid-game and the seesaw at
Morini/Nervii flipped five times. The Arverni-as-environment design
(no victory tracked, Phase-driven hordes of 12-14 Warbands) reads
correctly: they conquered Provincia and Cisalpina and kept Rome to
13-15 without any bot "trying" to win. NP-turn-denial matters: taking
a limited command as 2nd actor to lock Rome out of a card was
repeatedly correct.

**Bot behaviours verified legal, worth knowing:** (1) NP Belgae
Enlist placed a German Ally at Menapii — A4.5.1 restrictions (4-piece
cap, no Ariovistus region) are enforced in sa_enlist.py; in Ariovistus
an NP Belgae Enlist can genuinely build the German player's board.
(2) Solo-Caesar attrition: Caesar alone in Ubii Battled every card for
1 Loss (Leaders cause 1 Loss each, §3.3.4 NOTE), grinding warband,
warband, then Ally (loss order correct) and creating a 1v1 control tie
in a Germania region. Legal and nasty — a caution for German players
who strip the homeland.

**Engine findings fixed this session:**
- **A33 shaded "Motivation" capability was activated but never
  consumed** — bought it in-game, it did nothing. Now implemented in
  battle/losses.py: defending Germans suffer half Losses whether or
  not Retreating (halving applies once, never quartered) and inflict
  +1 Counterattack Loss (applied only when Germans are the
  counterattacking defender). 5 regression tests.
- **Human March could not express per-origin destinations**: the CLI
  pooled destinations (bot threat-march shape) and *excluded any
  destination that was also an origin*, so chained marches (A->B
  while B->C) were impossible and multi-origin groups routed to the
  nearest pooled destination — in-game this sent Ariovistus to
  Sequani when ordered to Treveri (fortuitously won the game, still
  wrong). _collect_march now prompts one destination per origin and
  emits exact plan["routes"] (already honored by the executor);
  adjacency prompts sorted for hashseed determinism. Regression test
  covers the chained case.

Verification: 2077 tests pass; strict census seeds 1-20 exit 0,
illegal=0, hashseed 0/7 byte-identical; player_fuzz seeds 1-12
hard-findings=0.

## Playthrough verdict 4 — Belgae, The Great Revolt (July 2026)

Seat: Belgae (player) vs NP Rome/Arverni/Aedui, Great Revolt, seed 7.
**Result: Arverni win at Winter 2** (margin 2); Belgae 2nd at -2
(peaked 14 of the >15 needed). An honest loss with a clear shape.

**The Belgae game is a corner economy under a sky of meteors.** Card
55 shaded (Conspirator — free Rally, any-piece as-if-Control; inert
before this session, implemented during it) powered 5 -> 14 through
pure ally-farming: every tribe allied is simultaneously +1 Belgae and
-1 Rome (one fewer Subdued). Rampage is the seat's quiet weapon —
no-Counterattack attrition stripped Roman Auxilia and Arverni
Warbands turn after turn. Enlist worked as designed both ways:
Germans died cheaply chipping Rome at Treveri, and the §7.2 rule that
Belgic victory counts GERMANIC Control and Allies was confirmed
working (the Germans' own Winter rally added to my score).

**Why it was lost.** NP Caesar twice erased my forward allies with
doomstack battles (thin garrisons are properly punished), but the
decisive event was bot-vs-bot: Vercingetorix hoarded 28 Resources,
rallied a 31-Warband horde at Carnutes, and killed SIX LEGIONS in two
cards (fallen=6, off-map 8>6) while holding allies+citadels 12>8 —
both Arverni conditions met as Winter arrived. From Belgica I could
reach exactly one Arverni ally to strip. Fourth data point for the
two-runaway thesis: the player can farm their corner perfectly and
still lose to whichever runaway the table cannot reach. As designed,
arguably — the Belgae's diplomatic lever (pointing Rome at the
Arverni) does not exist against bots.

**Engine findings this playthrough:**
- **Rally-plan crash**: ally/citadel entries given as plain region
  strings raised TypeError in _execute_rally (warbands already
  tolerated strings). Now coerced uniformly; malformed tribes fall
  through to captured CommandErrors. Regression test added.
- **Capability audit (the big one)**: prompted by A33, a sweep for
  activate_capability IDs never consumed found TEN inert base-game
  capabilities: 8 (Baggage Trains), 10 (Ballistae), 12 (Titus
  Labienus), 13 (Balearic Slingers), 15 (Legio X), 27 (Massed Gallic
  Archers), 43 (Convictolitavis), 55 (Commius), 59 (Germanic Horse),
  63 (Winter Campaign). (25, A22, A31, A38, A63 are fine — wired via
  event_modifiers.) **Card 55 implemented both sides this session**
  (rally cost/control for Belgae; Recruit as-if-Control and +1
  virtual Ally in Belgica for Rome, incl. the from-zero Auxilia Tip),
  6 touch points, 6 regression tests. **Follow-up arc: implement the
  remaining nine** — each touches battle/march/raid/besiege/suborn/
  quarters internals; none currently do anything when their events
  are played.

Verification: 2084 tests pass; strict census seeds 1-20 exit 0
illegal=0, hashseed 0/7 byte-identical.


## OVERTURNED-AND-FIXED — Interlude deck card: A38 Vergobret, not O38 (BGG ruling, July 2026)

The earlier "[RESOLVED] Diviciacus card identifier (A38 vs O38)" entry
concluded the Interlude's "Use the Ariovistus expansion version of
Diviciacus, card A38" was a typo for O38. **A BGG ruling says otherwise**
(thread 3701651, answer by Niko / Ze_German_Guy, May): O38 is only the
OPTIONAL Diviciacus-Leader variant for base-game scenarios; "if you are
playing an expansion scenario, including the second half of Gallic War,
you will use A38." The sentence parses as "the expansion's version of
[the card-38 slot, base-named] Diviciacus" = A38 Vergobret — not "the
expansion card that features Diviciacus."

The old entry's strongest argument — the Interlude Aedui step's
"Remove Diviciacus piece from play. (It may return by Event.)" — is
therefore a dangling editing leftover: nothing in the ruled second-half
deck can return the piece. (Worth a follow-up post; if a future ruling
revives a return path, revisit.) A side effect of the ruling: Vergobret's
shaded "If no Diviciacus..." fallback clause now has an obvious home —
the second half, where Diviciacus is always gone.

**Changes:**
- `INTERLUDE_DIVICIACUS_CARD = "A38"` (rules_consts, with citation).
- `get_card` falls through to the Ariovistus deck cards for string ids
  under base scenarios (A38 must resolve during the Pax Gallica? second
  half).
- **A38 shaded implemented** (it was inert — the 11th such capability
  found, and the ruling makes it live in Gallic War second halves):
  Suborn only at Diviciacus; if no Diviciacus, Suborn AND Trade only
  within 1 Region of Bibracte (sa_suborn validation + sa_trade
  supply-region filter; with Diviciacus on map the card restricts only
  Suborn — A4.1.2's within-1 filter already covers Trade).
- O38 and its handler remain (the optional base-game variant card);
  comments updated to stop calling it the second-half substitute.
- Tests: interlude deck asserts A38 present / O38 absent / base 38
  absent; get_card("A38", Pax Gallica?) resolves; 3 A38-shaded
  restriction tests (Suborn at-Diviciacus, Suborn/Trade
  within-1-of-Bibracte).

Verification: 2088 tests pass; strict census seeds 1-20 exit 0,
illegal=0, hashseed 0/7 byte-identical.

## OFFICIAL ERRATA AUDIT — BGG thread 2072553 (Volko-maintained), July 2026

The user supplied the designer's errata/clarification thread for
Ariovistus (last updated 15Nov2018). Every item audited against the
engine; transcriptions annotated in place with [ERRATA 15Nov2018]
tags so the traceability pass reads post-errata text.

### Already conformant (verified, no change)
- Correction 1 (Ariovistus doubling includes his own +1 Loss): both
  loss calculators double the full total incl. the Leader component.
- Correction 2 (Roman flowchart 2nd diamond No): transcription and
  bot already correct.
- Correction 3 (delete "or is outnumbered", A8.7.1 + 8.5.1): neither
  bot ever implemented an outnumbered gate — only the two conditions
  the errata keeps (guaranteed-losses, no Loss on the leader).
  Transcriptions annotated.
- BrentS follow-up (German Raid gains nothing in Devastated, A3.4.3
  via 3.3.3): the shared Raid validation already enforces it (the
  errata was about the player-aid omission).
- Clarification 2 (A5.1.1 stacking list non-exhaustive): no engine
  impact — stacking is enforced per-card, not from that list.

### Bugs found and FIXED
- **Correction 4 — Arverni Phase ran BEFORE the card's activations**
  (pre-errata A2.3.9 wording; A6.2 "after regular Faction activations"
  was always correct). Moved to after the SoP in play_card. This
  legitimately changed all-bot trajectories: Gallic War seed 1 now
  ends in a first-half Roman win at Winter 3; the interlude/telemetry
  tests moved to seed 4.
- **A33 "Motivation" halving was missing from the REAL battle path.**
  The earlier fix patched battle/losses.calculate_losses (estimates +
  Counterattack) but resolve_battle computes Attack losses via
  battle/resolve._calculate_attack_losses — a second, parallel
  calculator. The half-losses clause now lives in both; regression
  test covers the real path. (Lesson recorded: any Battle modifier
  must be wired into BOTH calculators.)
- **A31 shaded "Stalwart" was inert** (named enemy Leaders do not
  double Losses to Germans): Caesar's x2-Legions and Ambiorix's
  x1-Warbands rates now revert to normal against German defenders
  under the capability, in both calculators.
- **Card A64 Abatis had placement only — zero battle/march effect.**
  Implemented per card text + Clarification 1: owner-defending Abatis
  halves Losses like a Fort, negates all Losses caused by Auxilia,
  and blocks Ariovistus doubling (acts as a Fort); Roman March treats
  an Abatis Region as Devastated (cost doubling, any owner's marker);
  A31 unshaded cancel-benefits flag voids a GERMAN defender's Abatis,
  A31 shaded voids an enemy Abatis against German attackers
  (Clarification 1's German Phalanx interaction). 7 regression tests.
  NOT yet modeled: the marker absorbing a Loss and being removed on a
  1-3 roll like a Fort piece (Clarification 1 sentence 1) — the loss-
  resolution engine treats only pieces as loss-eligible; documented
  simplification, defender is never worse off (the marker persists).

### Corrected rule text recorded, implementation deferred (planner-quality)
- Correction 5a (8.8.1 March: "most Auxilia able to leave without
  LOSING Roman Control or adding enemy Control"): the Roman threat-
  March executor still marches all mobile forces; per-group Auxilia
  leave-behind remains the known deferred item. The errata fixes what
  the leave-behind should preserve when it is built.
- Correction 5b (8.8.1 SCOUT: "Move Auxilia only exceeding Legions by
  Region and..."): the Scout planner implements the Caesar-escort move
  only; the Supply-Line and join-Legions Auxilia moves (now with the
  exceeding-Legions cap) remain unimplemented planner steps.

Verification: 2095 tests pass; strict census seeds 1-15 exit 0
illegal=0, hashseed 0/7 byte-identical; rules_trace UNACCOUNTED=0.

## §8.8.1 PLANNER STEPS IMPLEMENTED — March groups + Scout moves (July 2026)

The two errata-recorded deferred items are now real:

**Roman threat-March per-origin groups** (`_march_group_8_8_1`): Leader
+ all Legions + at least 1 Auxilia, plus the most Auxilia able to leave
without losing Roman Control or adding enemy Control beyond what the
mandatory departures already cause (errata'd 8.8.1 bullet 1). Emitted
as plan["groups"]; the executor's existing subset-March applies them.
Ends the "Rome marches everything out" era — origins keep garrisons.

**Scout Auxilia moves** (`_scout_auxilia_moves`): concrete, executor-
schema moves for all three SCOUT bullets under the global constraints
(only Auxilia exceeding Legions per Region — the errata insertion;
keep 4 with Caesar throughout; keep Roman Control; add no enemy
Control; lose no guaranteed Supply Line): (1) escort to 4 with Caesar,
(2) break Arverni/Belgae/player-Aedui/Germanic Control adjacent to
movable Auxilia where it adds guaranteed Supply Lines to the most
Roman-piece Regions (greedy, deterministic), (3) join Auxilia to the
most Legions in equal number by Region. "Guaranteed" treats NP Aedui
Control as agreeing (§8.6.2). The Scout executor already executed any
concrete from/to moves the planner produced; the old escort-intention
dicts are gone.

**Balance effect (canary rebaselined deliberately):** NP Rome is much
stronger — Pax Gallica 20-seed sweep now Rome-dominant (garrisoned
origins stop the rally-behind exploit every Gallic bot enjoyed), and
Gallic War first halves end in Roman wins more often (interlude tests
repointed to seed 7). This is rule-cited behavior replacing a known
approximation, not tuning: the flowchart's Rome was always supposed
to garrison. 8 new planner tests.

Verification: 2103 tests pass; strict census seeds 1-15 exit 0
illegal=0, hashseed 0/7 byte-identical; canary rebaselined and green.

## CAPABILITY ARC COMPLETE — all nine inert base-game capabilities implemented (July 2026)

The audit's backlog (cards 8, 10, 12, 13, 15, 27, 43, 59, 63) is done;
with 55, A33, and A38-shaded from earlier this week, every capability
in both games now has a consumer. New schema: owner-scoped
capabilities ("Take this card" / "Place near a Gallic Faction") record
their holder in state["capability_owners"] (set/get_capability_owner;
Shifting Loyalties' deactivate clears it).

Per card (text: Card Reference; each with regression tests):
- **8 Baggage Trains**: owner March costs 0; owner Raids 3 Warbands
  per Region and steal despite Citadel/Fort.
- **10 Ballistae**: unshaded — Besiege cancels Citadel halving, Battle
  rolls remove Forts on 1-2 not 1-3; shaded — owner's Ambush then
  removes defending Citadel (first) or Fort, Q13 tribe sync applied.
- **12 Titus Labienus**: unshaded — Roman SAs ignore leader proximity
  (check_leader_proximity gate); shaded — Build and Scout Reveal
  trimmed to 1 Region (§8.3.3 first-Region for NP plans).
- **13 Balearic Slingers**: unshaded — on an enemy Battle Command the
  Romans pre-fire Auxilia (1/2 each) on the attacker in 1 Region (NP
  choice: most Auxilia; fires before the Battle resolves); shaded —
  Recruit only where Supply Line, always 2 Resources.
- **15 Legio X**: unshaded — with Roman Leader AND Legion: final
  Losses Romans inflict +2, against Romans -1 (post-rounding, both
  calculators, per the card Tip); shaded — Caesar doubles ONE Legion.
- **27 Massed Gallic Archers**: unshaded — Arverni attack inflicts 1
  fewer before halving (attack step only, per Tip); shaded — with 6+
  Arverni Warbands the other side absorbs 1 Loss at Battle start
  (attacking or defending; a wiped defender skips the Battle).
- **43 Convictolitavis**: unshaded — Suborn max 2 Regions (the base
  1-Region cap was previously UNENFORCED in the executor — now both
  are); shaded — Aedui Command costs double (March/Rally). Also fixed
  the Aedui bot's dead 'convictolitavis_unshaded' key.
- **59 Germanic Horse**: unshaded — Roman Auxilia inflict 1 each in 1
  Region per Battle Command (attack and counterattack, per Tip; NP
  picks most-Auxilia Region); shaded — the Gallic owner doubles enemy
  Losses in 1 Region per own Battle Command unless Defender has
  Fort/Citadel. Per-Command region flags in event_modifiers, cleared
  after the Command.
- **63 Winter Campaign**: unshaded — Roman Quarters cost 0 outside
  Devastated Regions (shares the A63 rule); shaded — after each
  Harvest the Gallic owner takes its flowchart Command + SA ("any 2
  Commands and/or SAs", paying costs; player owner consulted via
  decision agent kind "winter_campaign", NP fallback).

**Also fixed en route**: Roman Recruit is now budget-aware (entries
the Romans cannot afford are skipped as "unaffordable" per the rule's
own 'all able' qualifier — census had flagged 4 illegal
Recruit-overruns when card 13 shaded removed the Supply discount).

**Balance**: canary rebaselined (second deliberate rebaseline this
week): Great Revolt spread out (Ro 4 / Ae 4 / Be 9 / Ar 3); Pax
Gallica and Reconquest stay Rome-heavy post-§8.8.1.

NP approximations documented: NP region/owner choices for 10/13/59/63
default to self/most-value/first-region as noted per card; player
hooks exist where a choice is interactive (63 shaded).

Verification: 2125 tests pass (22 new capability tests); strict census
seeds 1-15 exit 0 illegal=0, hashseed 0/7 byte-identical; player_fuzz
seeds 1-8 hard-findings=0; canary green post-rebaseline.

## A31 Q&A APPLIED — designer/expert ruling on "Event effects" scope (July 2026)

BGG thread 2079436 (Ralph Graham's questions; answers by Niko /
Ze_German_Guy, confirmed in part by Volko Ruhnke, who folded the
Abatis point into the official errata):

1. **"Event effects" includes capabilities** (and one-shot event
   effects like a Germans-executed Sabis no-retreat, which in this
   engine resolve within their own card and cannot be standing targets).
   Applied: **A31 unshaded now cancels A33 Motivation** (half-losses
   AND the +1 Counterattack Loss) — reversing this ledger's earlier
   "no additional modeled referent" conclusion a second time (first
   Abatis via the errata thread, now A33 via the capability reading).
   Standing German-benefit battle effects cancelled by A31 unshaded
   are now: Ariovistus doubling (card text), German-owned Abatis
   (errata clarification), A33 Motivation (this Q&A).
2. **A31 unshaded IS a capability** ("Why do you think it is not?").
   It was wired as bare event_modifiers — invisible to card 50
   Shifting Loyalties and to the Interlude's capability bookkeeping.
   Now registered via activate_capability. Same class fixed for A63
   unshaded and A22 unshaded (the CAPABILITY banner covers both
   sides; the C/L/S letters in the card headers are NP instruction
   symbols — Carnyx/Laurels/Swords — not side-type markers, per the
   Card Reference legend).
3. **New bug class found and fixed: companion-modifier leak.**
   Dual-wired capabilities (capability entry + event_modifiers) left
   their modifiers in effect forever after card 50 removal or a
   §5.1.2 Dueling-Events side replacement. capabilities.py now keeps
   a _CAPABILITY_MODIFIERS registry (A31/A63/A22 unshaded) cleared on
   deactivate AND on side replacement. 4 regression tests.

Verification: 2129 tests pass; strict census seeds 1-12 exit 0
illegal=0, hashseed 0/7 byte-identical; canary within band (no
rebaseline needed).

## USER RULINGS + FINAL HOMEWORK — the open-questions list closed (July 2026)

The project owner ruled on the four remaining askable questions:

1. **"(It may return by Event.)" points at nothing** — RULED (owner).
   The Interlude parenthetical is an editing leftover; under the A38
   deck ruling nothing in the second half returns the Diviciacus
   piece. No engine change (already the behavior); question closed.
2. **A31 vs one-shot Event battle benefits** — delegated to engine
   judgment. Implemented per the BGG 2079436 reading: with A31
   unshaded standing, a GERMAN attacker's event-granted no_retreat /
   warband_full_loss are cancelled; with A31 shaded, an event's
   no-retreat does not bind a GERMAN defender. (One-shots resolved
   before A31 arrives are inherently untouchable — effects are not
   retroactive.)
3. **Card 42 "Roman-Aedui Supply Lines"** — RULED: the Tip's
   hypothesis reading is final (chains of No Control / Roman / Aedui
   Control only). Already implemented; closed.
4. **A8.7.1 "at victory" for Aedui/Belgae** — RULED: the margin >= 1
   inference from §7.3's defined term is final. Already implemented;
   closed.

**Checkable homework, done:**
- **NP event instructions for cards 10/13/59/63 audited**: Aedui
  per-card says "Use shaded text" for Baggage Trains / Ballistae /
  Germanic Horse / Winter Campaign (owner = executing Gallic faction
  — matches the implemented default); Ballistae is "No Arverni" and
  "No Belgae"; Balearic/Legio X/Labienus carry the Roman-player
  conditional gates already encoded in bot_instructions.py. Defaults
  verified conformant; no changes needed.
- **Abatis loss absorption implemented** (errata Clarification 1
  sentence 1): the marker absorbs Losses in the Fort tier when its
  owner defends — die roll per Loss, removed on 1-3, auto-removed
  under Ambush (Caesar-counterattack exception honored); attacker-side
  losses never use it. resolve_losses gains abatis_defender, set only
  by the Attack-step call. The last documented Abatis simplification
  is closed.
- **Card 27 shaded in bot estimates**: card27_shaded_absorption
  (bot_common) adds the +1 absorbed Loss to the German/Aedui/Belgae
  estimators' go/no-go math when facing 6+ Arverni Warbands.

With these, the QUESTIONS.md open list is EMPTY except the three
permanent physical-table porting decisions (Trade forecasting, Trade
call-off/side-payments, §4.1 SA interrupts), each documented where
decided. 4 new tests.

Verification: 2133 tests pass; strict census seeds 1-12 exit 0
illegal=0, hashseed 0/7 byte-identical; canary within band.

## CONTINUOUS-RUN BATCH — validation sweep + human Build/Scout SA (July 2026)

Standing instruction from the owner: keep rolling, batch notes, stop
only for adjudication. This batch:

**Validation after the capability/errata week**: play_quality
telemetry (6 seeds x 4 scenarios) healthy — no-effect turns ~zero,
SAs firing, Great Revolt spread Ro2/Be2/Ae2. Deep census seeds 1-60
strict: ONE new illegal class found at depth (seeds 21-40) and fixed
— bot Recruit planned place_auxilia entries whose Leader/Ally/Fort
prerequisite vanished by execution (Build resolves first, §8.8.4);
now presence-prechecked and skipped as "no longer able", matching the
budget pre-check pattern. Census 1-60 now illegal=0, hashseed 0/7
byte-identical; fuzz seeds 20-30 hard-findings=0.

**Human-seat SA gap closed (the old Quarters class)**: a human
Roman's Build and Scout SAs executed the BOT's recomputed plan.
_execute_build/_execute_scout now honor player-supplied
details['build_plan'] / details['scout_plan']; CLI collectors added
(_collect_build: per-Region fort/subdue/ally choice with tribe
prompts; _collect_scout: Auxilia moves + Reveal targets within 1 of
Caesar/same-Region Successor). Bots unchanged (fall back to
flowchart plans). 2 executor-override tests.

The known human-seat plan gaps are now closed (Quarters, March
groups/routes, Build, Scout). Remaining CLI polish only: multi-group
March from one origin (§3.2.2 allows several groups; the CLI takes
one per origin).

Design questions owed by the owner (parked, per instruction): Pax
Gallica?/Reconquest Roman dominance; Aedui seat strength.

## Playthrough verdict 5 — Arverni, The Great Revolt, vs the POST-FIX bots (July 2026)

Seat: Arverni (the last unplayed faction) vs NP Rome/Aedui/Belgae,
Great Revolt, seed 11 — the first human game against the
capability-era, §8.8.1-garrisoning Rome. **Result: Roman win at
Winter 1, margin 1.** Arverni 2nd at -4.

**The strengthened Rome is a different animal.** The moment
Vercingetorix's 14-Warband horde marched adjacent, the 8-Legion army
executed a textbook §8.8.1 threat-evacuation to Caesar (leaving the
1-Auxilia garrison), then subdue-farmed GERMANIA — Suebi North/South,
Sugambri, Ubii — rocketing 13 -> 18 in six cards. The old bot lost
this position; the new one refused every engagement and won on the
subdued-tribes ledger. A human Arverni cannot force battles on an
opponent with superior movement discipline: my one Ambush (2 Legions
+ Fort at Treveri) killed a single Auxilia — the Fort's §4.3.3
exception let both Legions roll-save (verified legal, dice 4-6 x3;
the rules' own PLAY NOTE warns of exactly this).

**The Oppida counter-play worked and then didn't.** Card 28 dragged
Rome 18 -> 15 in one action (every Gallic Ally at a Subdued City is
-1 Rome), demonstrating the real anti-Rome lever in the endgame. The
NP Aedui then battled the fresh Allies before Winter, re-subduing 2
tribes — Rome back to 17, game over. Corollary to the two-runaway
thesis: the post-fix Rome doesn't even need to be ignored; the other
bots actively feed it (every Gallic-on-Gallic Ally kill is +1 Rome).
This sharpens the Pax-Gallica?/Reconquest dominance data the owner is
weighing — in bot-only Great Revolt the Gauls' mutual predation is
Rome's best asset. (Design question parked with the owner.)

**Engine findings fixed this session:**
- **Card 28 Oppida validation**: the handler allied ANY tribe named in
  params — now requires a City Tribe, Subdued status, an Available
  Ally disc, and non-Roman control.
- **No-effect Rally charged Resources**: with the Warband pool empty
  (all 35 Arverni deployed), rally_in_region took the Region cost and
  placed nothing. §3.3.1's "(to have effect)" qualifier now refuses
  the selection before payment; the two tests codifying pay-for-
  nothing were rewritten (one had asserted it as intended behavior).
- **March-hides semantics verified** (§3.3.2 "flip Revealed Warbands
  to Hidden") with a clean repro after the ambush anomaly suggested
  otherwise — engine correct; the anomaly was the Fort roll-saves.

Verification: 2135 tests pass; census seeds 1-20 strict illegal=0.
