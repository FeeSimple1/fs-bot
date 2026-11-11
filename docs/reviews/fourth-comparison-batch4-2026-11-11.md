# Fourth comparison repairs, Batch 4 · 11 November 2026

[Finding ledger](comparison-audit-round4-2026-11-10.json) ·
[Validation evidence](fourth-comparison-batch4-2026-11-11-evidence.zip)

| Finding | Repaired behavior |
|---|---|
| WS4-02, Interlude deck | The Event pool substitutes A38 Vergobret for card 38 before filtering active Capabilities. Active Gallia Togata and Colony hold cards 5 and 71 out of the pool. The fifth Winter is the final card if the available Events do not reach pile 14. |
| WS4-03, Tribe conversion | Markers cleanup removes the printed Nori Tribe and returns any remaining Nori Ally to Available. Catuvellauni enters play in Britannia. A lingering Colony retains its Region and allegiance, with a distinct name if it used Catuvellauni. Roman score and Harvest use 30 printed Tribes plus any lingering Colony. |

The Gallic War scenario's Markers, Lingering Events, Deck, and Second Half
steps govern the changes. The deck also follows original Setup and the
Pax Gallica? scenario. §§1.4.2, 6.4.1, 7.2, A1.3.2 and A1.3.4 govern
the map, stacking and Roman accounting.

## Saved games

A valid save made before the Interlude runs the corrected transition. A
valid save made after it continues its dealt deck. The loader removes the
obsolete printed Nori entry. A recorded in-progress assistant action
replays on its saved board and applies the cleanup before the next draw.

The original seed-3 fixtures and their prior continuation checksums
remain in the compatibility record. Continuing the pre-Interlude fixture
changes its deck, card cursors and Nori record. Continuing the post-Interlude
fixture changes only the Nori record, including the check after playing
its current card. The archive includes both continuation boards.

## Verification

Tests ran on Python 3.12.14 with parent
`b0d936c4c066565e6237818a8d1801389f5c8770`. The tested Python-source
SHA-256 is `31e50801e3a187cf7c9def52e09df7ef5b39a895f55d32a4abfe0a08a42d2341`
across 591 files.

| Check | Result |
|---|---|
| Full suite | 9,806 passed. |
| Focused Interlude, setup and save checks | 304 passed. All 12 new regressions fail on the parent and pass on the repair. |
| Audited bot games | All 100 legacy games and 20 second-edition games completed with four-faction rankings, zero integrity findings and zero nonlegal diagnostics. |
| Mixed-player replay | Twenty second-edition cases match across hash seeds 0 and 987. One reaches the second half of The Gallic War. Both runs have zero hard findings and one soft partial plan. |
| Balance | The 100-game check passed the existing 15-point band. The largest faction win-rate shift was five percentage points. |

Legacy seeds 1–20 and second-edition seeds 25–28 covered all five
scenarios. Five legacy winners and four second-edition winners changed.
Twelve games reached the Interlude. The paired boards match before each
of those Winter cards. Eleven of the new decks differ, and the Roman
score after each transition is one lower. In legacy seed 12, the dealt
deck is identical and the Roman score falls from 21 to 20. In legacy
seed 8, Vergobret is the first card dealt in the second half.

All 16 findings in the fourth comparison are closed.
