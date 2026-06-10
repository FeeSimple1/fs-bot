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
