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

## [RESOLVED] Gallic War Interlude — Diviciacus card identifier (A38 vs O38)

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
Added `TestBritanniaNonPlayerAbility` (2 tests). NOTE: should A8.8.9 ever be
supplied with additional criteria (e.g. a resource or score threshold), this
"if able" check would be extended accordingly.

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

**Known dead code (not a live bug, left for a focused follow-up):**
`event_eval.py::_has_subdued_tribes` / `_has_subdued_city_tribes` test
`status == "subdued"` (lowercase), which no Tribe ever has (Subdued = `status is
None`; the constant is `SUBDUED = "Subdued"`). Both helpers are currently
**unreferenced**, so they affect no behaviour; flagged here for cleanup.

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

### Remaining — larger engine features (real, unimplemented; need new logic)
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
