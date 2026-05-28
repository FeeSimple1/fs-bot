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

