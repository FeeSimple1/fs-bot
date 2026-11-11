# Fourth comparison repairs, Batch 2 · 10 November 2026

[Finding ledger](comparison-audit-round4-2026-11-10.json) ·
[Validation evidence](fourth-comparison-batch2-2026-11-10-evidence.zip)

| Finding | Repaired behavior |
|---|---|
| FE4-01, free Battle timing | Each selected Battle checks attacker and defender presence when it resolves. Scout can first move Roman Auxilia into the Battle Region. A plan with an absent attacker or defender still rolls back the Event. |
| FE4-02, Event scope | Validation reads the same authored plans as the executor. Mons Cevenna confines Scout movement origins and Reveal Regions to the granted Region. An Auxilia group can move from there to a legal destination outside it. |
| FE4-03, Assembly of Gaul | The human Carnutes controller can add two distinct free Special Abilities to a single Command. Each can resolve before, at its own Command step, or after. Ambush and Besiege modify the selected Battles. The terminal and durable interface accept both abilities, and existing zero- and one-ability plans still work. A Non-player uses the ability selected by its flowchart. |
| BE4-03, Druids | Select one to three distinct Gallic factions. Aedui, Arverni, and Belgae resolve in printed order. Each can add a free Special Ability to its required free Limited Command when possible. A Non-player Gallic executor selects itself. The Event executor receives the eligibility benefit. |

Card Reference 9, 48 and 52 and §§3.2.4, 3.3.4, 4.1, 4.2.2, 5.1–5.4,
8.1.2, 8.2.3 and A8.2.3 govern these changes. Existing
[PR-10](../provisional-rulings.md#pr-10) handles an automatic Ariovistus
Arverni recipient. The open questions about repeating an ability type and
guiding a base-game German Carnutes controller are recorded in
[QUESTIONS.md](../../QUESTIONS.md#q-assembly-ability-types--two-uses-of-the-same-ability-10-november-2026).

## Verification

Tests and game runs used Python 3.12.14 and the repair above parent
`55fa4847f3da9112ec1c6d42542341f12859297d`. The tested Python-source
SHA-256 is `b97a582f9a3af89b343abc9669ecf9e677118eb21e36514a9f403cad7830f267`
across 589 files.

| Check | Result |
|---|---|
| Full suite | 9,777 passed. |
| New regression cases | 55 passed on the repair. The parent produced 48 failures and seven passing controls. |
| Saved decisions | Two new grants retain the pending ID and board after an invalid response, then accept a corrected response after reload and replay to the same board. Separate checks reproduce the previous valid one-recipient Druids and one-ability Assembly request signatures and final boards. |
| Second-edition bot games | 20 completed with zero audit failures or missing rankings. Six winners changed from the parent. |
| Second-edition mixed-player games | 20 cases replayed, with identical output across hash seeds 0 and 987. The runs had zero hard findings and one soft partial plan. |
| Legacy balance | 100 games stayed within the existing 15-point band. Seventeen winners changed from the parent. |

The second-edition matrices use seeds 25–28 in all five scenarios. Each
mixed-player run records 729 human turns, 186 Event attempts and 163
executed Events. Both hash runs with replay total 80 game executions.
The balance matrix uses seeds 1–20 in all five scenarios. The largest
win-rate shift against the reviewed baseline is 15 percentage points
for Aedui in Pax Gallica?, from 10% to 25%.

All 23 games with a changed winner first diverge on Druids from identical
pre-card boards. In the legacy Pax Gallica? seed 5, the parent gave three
Gallic factions free Commands. The Aedui executor now takes its own free
March. In legacy Ariovistus seed 8, the parent granted free Commands to
Aedui and Belgae after a German Druids Event. The German bot now declines
the Event under A8.2.3. The evidence records each pair's first differing
draw, Commands, outcomes and reproduction commands.

The fourth comparison ledger now has 10 of 16 findings closed.
