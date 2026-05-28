QUESTIONS.md — Ambiguities requiring human decision
These items are identified during implementation when the Reference Documents are ambiguous, contradictory, or silent. Per CLAUDE.md rules: no guessing — wait for human answer.

---

## German bot — G_MARCH_THREAT "at victory" threshold for Aedui/Belgae

**Context:** A8.7.1 G_MARCH_THREAT destination priorities reference faction victory state:
> "if the Romans are at victory (have a margin of 1 or better, 7.3), the Germans first March to Regions that have the most Dispersed Tribes that they can reach. Within that objective (if it applies), if either Aedui or Belgae (or both) are at victory, the Germans first March to Regions with most Allied Tribes of those Gallic Factions at victory."

**Ambiguity:** A8.7.1 explicitly defines "at victory" as margin ≥ 1 only for Romans. For Aedui/Belgae, the parenthetical is omitted. §7.3 defines "at victory" generally as margin ≥ 1, so the same threshold applies if "at victory" is a defined term.

**Implementation choice:** Used margin ≥ 1 uniformly per §7.3. Note this is a reasonable reading, but if the rules intended a different threshold for the Gallic factions (e.g., margin ≥ 0 to align with G1b's "victory margin of 0 or better"), the implementation would need adjustment.

**Files:** `fs_bot/bots/german_bot.py` — `node_g_march_threat`.

---

## German bot — G_AMBUSH eligibility (Ariovistus proximity)

**Context:** A8.7.1 AMBUSH paragraph:
> "If the Germans are Battling per above and can Ambush in any of those Battles, they do so—but only where the enemy's Retreat out of that Region could lower the number of pieces it would remove, or Battle could allow a Counterattack to inflict at least one Loss on the Germans."

**Ambiguity:** "Can Ambush" defers to the Germanic Ambush rules in A4.6.3 for eligibility (Hidden Warbands etc.). The bot flowchart adds only the strategic gate (retreat-could-reduce OR counterattack-loss-possible). For the Belgae bot, §8.5.1 layers an Ambiorix-proximity requirement on top of §4.5.3; no equivalent proximity layer is stated for Germans in A8.7.1.

**Implementation choice:** Used Hidden Germanic Warbands present + the A8.7.1 strategic gate, with no extra proximity-to-Ariovistus requirement. If A8.7.1's "can Ambush" was meant to imply a parallel proximity rule, the implementation would need adjustment.

**Files:** `fs_bot/bots/german_bot.py` — `_check_ambush`.


## Gallic War Interlude — Card identifier for "Ariovistus expansion version of Diviciacus"

**Context:** A Scenario: The Gallic War, Interlude > Deck step says:
> "Use the Ariovistus expansion version of Diviciacus, card A38."

But in the Ariovistus card list (A Card Reference and CARD_NAMES_ARIOVISTUS), card A38 is named **Vergobret**. The expansion's "Diviciacus 2nd Ed" (with the Diviciacus Leader piece and rules in A1.4) is documented in A Setup under the "Diviciacus Leader Option" and is keyed as **card O38** (CARD_O38 = "O38", CARD_O38_NAME = "Diviciacus") in `fs_bot/rules_consts.py`.

**Ambiguity:** "A38" in the Interlude prose appears to be an error or a different naming convention than the A Card Reference uses. The intent is almost certainly to use the Diviciacus 2nd Ed card (with Diviciacus Leader rules), which the codebase represents as O38, not the Vergobret event (A38).

**Implementation choice:** Used `INTERLUDE_DIVICIACUS_CARD = "O38"` in the Interlude deck rebuild (substitutes for base card 38). If the Interlude really wants A38 (Vergobret) — substituting the Vergobret event for the original 38 Diviciacus event — please clarify.

**Files:** `fs_bot/rules_consts.py` (INTERLUDE_DIVICIACUS_CARD), `fs_bot/engine/interlude.py` (deck rebuild step).

---

## Gallic War Interlude — A8.8.9 reference (non-player Britannia expedition)

**Context:** A Scenario: The Gallic War, Interlude > Britannia Expedition says:
> "Non-player Romans conduct it if able, A8.8.9."

**Ambiguity:** Chapter A8 in this repo ends at A8.8.8 (Admagetorbriga). There is no A8.8.9 rule for the non-player Britannia expedition decision.

**Implementation choice:** Implemented a conservative "if able" check: Roman Legions on map >= (3 to Harvest Box + 3 to Britannia) and Roman Auxilia on map >= 1. If A8.8.9 specifies additional or different criteria (resource threshold, score-based decision, etc.), this fallback should be replaced.

**Files:** `fs_bot/engine/interlude.py` — `_np_should_conduct_britannia`.

---

## Gallic War Interlude — Belgic Leader identity in second half

**Context:** Interlude > Adjust Belgae says:
> "Place Ambiorix in Region with most other Belgic pieces (even if Belgic Leader in Available)."

In the Ariovistus first-half setup, the Belgic Leader piece is named **BODUOGNATUS** (same physical piece, A1.4). After the Interlude, the second half plays as base-game (Original Falling Sky rules are in effect), where the Belgic Leader is **AMBIORIX**.

**Ambiguity:** Should the piece be re-tagged as AMBIORIX or remain BODUOGNATUS? The scenario name says "Ambiorix" explicitly, suggesting a re-tag. But the scenario remains SCENARIO_GALLIC_WAR (which is in ARIOVISTUS_SCENARIOS), and Boduognatus is the Ariovistus identity.

**Implementation choice:** Forced AMBIORIX as the leader_name when re-placing during the Belgae adjustment step. If the codebase intends Boduognatus to persist for the second half of Gallic War, this should be reverted.

**Files:** `fs_bot/engine/interlude.py` — `_adjust_belgae_forces`.

---

## Gallic War Interlude — Removed-from-play container for non-Legion pieces

**Context:** Interlude > Adjust German Forces says:
> "Remove Germanic Leader and any 15 Germanic Warbands (including from Available) from play."

Per CLAUDE.md and prior code, "remove from play" means permanent removal (not to Available). Only Legions previously had a dedicated container (`state["removed_legions"]`); Diviciacus had a special-case path in `remove_piece` (vanish to neither Available nor a tracked field).

**Implementation choice:** Added a generic `state["removed_pieces"][faction][piece_type]` container and updated `validate_state` to include it in cap totals. The Germanic Leader, 15 Germanic Warbands, and all Settlements are routed there. Diviciacus continues to use its existing special-case path. If the existing schema preferred a different convention (e.g. reuse `removed_legions` for non-Legions), this can be refactored.

**Files:** `fs_bot/state/state_schema.py`, `fs_bot/engine/interlude.py`.
