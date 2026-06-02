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

## [NOTE] Human execution path — plan-collection UI is the remaining piece

**Context:** `execute_decision` now applies a plan from either `bot_action`
(bot) or `player_action` (human/UI), so a mixed human/bot game resolves human
turns through the same Command/SA/Event machinery (human Events use the player's
own `event_params` rather than NP auto-derivation). This is the execution layer.

**Remaining:** The CLI human menu (`fs_bot/cli/menus.py::prompt_action`) returns
only the chosen engine action *type*; it does not yet collect the full plan
(Regions, SA, targets, Event params). Until an interactive plan-collection menu
is added, a human non-Pass turn driven by the bundled CLI carries no
`player_action` and is reported (not crashed) as "decision carries no executable
plan." A front-end that supplies a `player_action` plan executes fully today.

**Files:** `fs_bot/engine/execute.py` — `execute_decision`, `_execute_event`.
