# Falling Sky — Self-Play Strategy & Balance Notes

*Generated June 2026 by the process in `SELFPLAY_PLAYBOOK.md`: heuristic strategy
profiles seated via the agent interface (`AGENT_INTERFACE.md`) against the NP bots,
run in large self-play batches. These are findings about **this engine's bots**, not
about human play. Strategy priors come from the designer's InsideGMT faction articles
(used for hypotheses only — never for rules decisions, per CLAUDE.md); all rules
behavior is the engine's own.*

## Method

Two competing strategy hypotheses per Faction were encoded as plan-building policies
(`fs_bot/agents/heuristic.py`), each dry-run through `moves.validate_player_action`
before committing, with a degrade-to-Pass fallback so a profile can never wedge a
game. Each profile was compared against a random-legal-plan baseline (`RANDOM`) and a
pure bot-only reference (`BOTS`) on identical seeds. Volume: 780 games — 20 seeds ×
13 configurations across the three base scenarios (Pax Gallica?, Reconquest of Gaul,
The Great Revolt). No game errored. Each game runs in ~0.1 s. With n = 20 the 95%
noise band is roughly ±20 points; only larger gaps are reported.

Profiles: Romans **R-PACIFY** (Seize/Recruit/Build, disperse, allies) vs **R-HUNT**
(Battle-first, Scout). Arverni **A-DEVASTATE** (Rally + Devastate attrition) vs
**A-BATTLE** (direct Battle, Entreat). Aedui **AE-SUBORN** (quiet Suborn growth,
avoid Romans) vs **AE-ARMY** (militarized, Trade). Belgae **B-CONTROL** (spread
control, Enlist) vs **B-RAMPAGE** (Battle/Rampage aggression).

## Results (own-faction win rate)

| Seat | Profile | Pax Gallica | Reconquest | Great Revolt |
|---|---|---|---|---|
| Romans | R-PACIFY | 15% | 0% | 0% |
| Romans | R-HUNT | **35%** | 0% | 0% |
| Romans | RANDOM | 25% | 0% | 0% |
| Arverni | A-DEVASTATE | 15% | 15% | **95%** |
| Arverni | A-BATTLE | 0% | 0% | **95%** |
| Arverni | RANDOM | 0% | 25% | 90% |
| Aedui | AE-SUBORN | 0% | 0% | 0% |
| Aedui | AE-ARMY | 0% | 0% | 0% |
| Belgae | B-CONTROL | 15% | 20% | 0% |
| Belgae | B-RAMPAGE | 0% | 20% | 0% |

Bot-only reference (20 seeds): Pax Gallica -> Arverni 8, Belgae 9, Aedui 3, Roman 2;
Reconquest -> Belgae 10, Arverni 6, Aedui 4; Great Revolt -> **Arverni 20/20**.

## Findings

**1. The Great Revolt is Arverni-decided regardless of the other seats.** Arverni
win 20/20 in every configuration, including bot-only, and no profile in any other
chair deflects it (Romans 0/60, Aedui 0/60, Belgae 0/60 there). The cause is a
setup property plus an engine defect, separable by experiment (next two findings).

**2. Arverni begin the Great Revolt already over one of their two thresholds.** Their
victory needs off-map Legions > 6 **and** Allies + Citadels > 8; at setup they hold
11 Allies+Citadels. So the entire scenario reduces to a single race — get 5+ of
Rome's 10 on-map Legions off the map — and the Arverni also lead the end-game margin
ranking by default. This is a balance observation about a faithfully-implemented
setup (it matches the scenario reference exactly); whether bot-only balance is a
design target is outside what the Reference Documents state, so it is recorded, not
"fixed."

**3. Engine defect — the Roman bot's Quarters/Spring plans are never consumed
(QUESTIONS.md Q12).** `roman_bot.node_r_quarters` builds a faithful section 8.8.7
Winter Quarters plan (retreat Legions to Provincia, pay to avoid rolls), but the
Winter engine always runs with `relocations=None`, so it falls through to "roll for
all": every Legion outside Provincia rolls for removal each Winter, with no payment
even when affordable, and none retreat to safety. Isolating it (neutralize the roll):
Great Revolt off-map Legions stop climbing (2 -> ~3 instead of 2 -> ~12), and the
Arverni stop achieving outright victory — they then win only on margin ranking
(10/12 instead of 12/12). The faithful fix has genuine ambiguities (Supply-Line
routing, pay budget) that CLAUDE.md says not to guess, so it is filed for owner
decision rather than patched.

**4. Romans are the skill-elastic seat; everyone else is structure.** Romans are the
only Faction whose result responds to profile choice — R-HUNT 35% vs R-PACIFY 15% in
Pax Gallica — implying Roman move quality matters and the seat rewards aggression
there. Most other seats move little between their two profiles and the random
baseline, suggesting the bots and scenario structure dominate over simple policy in
those chairs (or that these heuristics don't yet express the lines that matter — see
caveats).

**5. A-BATTLE self-destructs outside the Great Revolt.** Direct-battle Arverni win
0% in Pax Gallica with the shortest games in the study (avg ~9 cards) — they throw
warbands at Legions and collapse. A-DEVASTATE (attrition, avoid unfavorable battles)
is far steadier (15% Pax/Reconquest). This matches the designer's framing of
Devastate as the Arverni's distinctive lever and is the clearest "how to play the
Arverni" signal: starve, don't charge.

**6. Belgae reward mobility/control over rampage in the longer scenarios.** B-CONTROL
matches or beats B-RAMPAGE in Pax Gallica (15% vs 0%) and they tie in Reconquest
(20%); rampage-first Belgae, like battle-first Arverni, end games faster and worse.

## Caveats and next experiments

These heuristics deprioritize Events and use only coarse special-activity targeting,
so findings understate Faction lines that hinge on event timing or precise SA use
(Suborn/Entreat placement, Scout, Ambush). The Aedui's 0% everywhere is suspicious in
that light — their strength (Suborn among enemies) is exactly what a keyword policy
expresses worst — so read it as "these heuristics can't pilot the Aedui," not "the
Aedui can't win." Natural next steps: wire the Quarters fix once Q12 is answered and
re-measure the Great Revolt; give the Roman seat an event-aware profile; and replace
keyword SA targeting with state-scored placement.

## Reproduce

```bash
python -m fs_bot.tools.heuristic_selfplay --scenario "The Great Revolt" --seeds 1-20 --out r.jsonl
python -m fs_bot.tools.balance_smoke          # guardrail vs committed baseline
```

## Sources for the strategy priors

Designer faction-strategy articles (priors only): InsideGMT —
[Roman](https://insidegmt.com/coin-series-falling-sky-roman-strategy/),
[Arverni](https://insidegmt.com/coin-series-falling-sky-arverni-strategy/),
[Aedui](https://insidegmt.com/coin-series-falling-sky-aedui-strategy/),
[Belgic](https://insidegmt.com/coin-series-falling-sky-belgic-strategy/).

---

## Addendum: Q12 resolved and wired

The owner confirmed Q12 (see QUESTIONS.md): the Roman Quarters/Spring bot plans now
drive the Winter engine — §6.3.3 relocation (Supply-Line Regions to Provincia, one
adjacent hop for stranded stacks, Leader from anywhere) and §8.8.7
pay-all-affordable in priority order. Bot-only balance, before → after (20 seeds):
Great Revolt Arverni 100% → 55% with Belgae taking 45%; Pax Gallica Belgae
40% → 60%; Reconquest Belgae 45% → 30% (Arverni 35% → 45%). The Great Revolt is no
longer a foregone conclusion: Rome keeping its Legions alive through Winter denies
the Arverni their off-map-Legions condition in nearly half of games, and the
beneficiary is mostly the Belgae, whose Control-based score profits from a longer,
multipolar war. Findings 1–3 above describe the pre-fix engine; finding 4's
Roman skill-elasticity and findings 5–6 remain directionally consistent post-fix.
The balance baseline was refreshed at this commit; the canary guards the new state.

---

## Addendum: the AE-DEEP experiment (Suborn-aware Aedui)

To test whether the Aedui's 0%-everywhere was a heuristic limitation or a seat
property, `AE-DEEP` (`fs_bot/agents/heuristic.py`) replaces keyword preferences
with a state-scored planner: Suborn only when it moves the Ally race (place own
Ally at a Subdued Tribe, else remove the leading rival's Ally — NP 8.6.3
priorities), Rally as the carrier when it scores, March to push Hidden Warbands
toward future Suborn Regions (never Raid as carrier when solvent, since Raiding
Reveals the Warbands Suborn needs Hidden), Trade for income otherwise.

Result (20 seeds, post-Q12 field): Reconquest 15% (3/20) vs 0–10% for the keyword
profile and 0% for random — the first repeatable Aedui wins in the study — but
Pax Gallica 0/20 and Great Revolt 1/20. Verdict: partly heuristics, mostly seat.
State-aware Suborn play lifts the Aedui floor in their best scenario, yet their
margin (beat EVERY rival's Allies+Citadels) keeps failing against the Belgae
bot's Control-value engine and the Arverni's scale; mid-game Aedui ally counts
peak around 4 and get stripped faster than Suborn rebuilds them.

The diagnostic value exceeded the win rate. Building the profile surfaced two
defects: the agent-interface Suborn executor dropped the tribe on `remove_ally`
(fixed — it silently desynced the tribes record), and, behind it, a whole class
of Event handlers that mutate tribe allegiance without touching space pieces —
roughly 20 Event cards desync `state["tribes"]` from board pieces in ordinary
bot games (filed as Q13 with a per-card detector, `fs_bot/tools/sync_check.py`).
Until that audit lands, treat space-piece ALLY counts as unreliable; victory
math reads the tribes dict and is unaffected.

---

## Addendum: Q13 fixed — and it was a balance bug wearing a bookkeeping costume

The tribe/piece desync audit (Q13, flagged by both this study and an external
playtest) is complete: ~67 sites across 40 Event handlers paired their
allegiance mutations with the matching ALLY/CITADEL piece operations, plus the
reverse direction nobody had flagged — Battle losses, Besiege, Seize, and
Intimidate removed Ally/Citadel pieces without clearing the authoritative
tribes record, leaving phantom allied tribes that still scored. A subtle root
cause: Card 71 Colony tribes carried no region key, making them invisible to
the detector and smearing blame across a dozen innocent cards.

The balance impact of pure bookkeeping fixes was large (bot-only, 20 seeds):

| Scenario | Before | After |
|---|---|---|
| Pax Gallica? | Belgae 60%, Ro 15%, Ar 15%, Ae 10% | Romans 50%, Belgae 30%, Ar 10%, Ae 10% |
| Reconquest | Ar 45%, Be 30%, Ae 25%, Ro 0% | Aedui 55%, Romans 20%, Ar 15%, Be 10% |
| Great Revolt | Ar 55%, Be 45% | Belgae 40%, Aedui 35%, Ar 20%, Ro 5% |

Phantom allies had been propping up exactly the factions this study called
dominant: the Belgae Pax engine and the Arverni everywhere were partly scoring
tribes whose discs had already been removed in battle, and the Aedui — whose
entire victory is the allies-and-citadels count — were the systematic victim.
Post-fix, every faction wins somewhere in bot-only play. All per-faction
strategy claims in the notes above predate this fix; treat them as historical.
The sync invariant is now enforced by 15 dedicated tests including per-scenario
full-game canaries, and the balance baseline was refreshed at this commit.
