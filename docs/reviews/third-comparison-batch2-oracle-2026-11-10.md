# Third comparison, Batch 2: source-derived expectations

These expectations were written from the supplied references before inspecting
the affected implementation or tests. The starting revision is
`8b7227054fe520e05f74646a622296140e3d0f70`. No additional project ruling is needed.

| Finding | Supplied authority | Required behavior and controls |
|---|---|---|
| CM3-01 | Chapter 1 §1.4.2; Chapter 4 §4.2.2; Card Reference 5; Chapter A1 §§A1.3.2, A1.4.2; A Card Reference A5 | Scout moves Auxilia between adjacent playable Regions, never into/out of Britannia. Base Cisalpina is unavailable without Gallia Togata. Cisalpina remains legal in Ariovistus and with the appropriate lingering Gallia Togata effect after Interlude. Illegal movement must leave pieces, Resources, RNG, and the pending decision unchanged. Ordinary adjacent playable movement remains legal. |
| CM3-03 | Chapter 3 §§3.2.4, 3.3.4; Chapter 5 §§5.1.1, 5.4 | Ordinary Battle requires own and opposing Forces in each selected Region before charging or resolving effects. Selecting a Region without attackers must reject without revealing enemies or spending Resources. Legitimate low-strength or structure-only Forces still satisfy the printed presence condition. Explicit Event exceptions retain their printed scope. |
| WS3-01 | Chapter 1 §1.4.2; Chapter 6 §§6.4.2–6.4.3; Chapter A6 §§A6.4.2, A6.4.4 | Each physical Allied Tribe disc or Citadel contributes once to Gallic Harvest, at two Resources each; Aedui also gain four River Tolls. A Citadel replaces a City Ally rather than adding a second physical disc. Check initialized Reconquest and Great Revolt earnings, no-Citadel controls, the Resource cap, and expansion earnings isolation. |
| WS3-02 | Card Reference 33 and its Tip; Card Reference 1 and 3; Chapter 6 §6.5.1; Scenario - Pax Gallica, first Winter; Chapter A6 §A6.5.1; A Scenario - The Gallic War, second half first Winter | Lost Eagle blocks downward Senate changes only during the next Senate Phase. Intervening Cicero/Pompey effects resolve normally. The marker expires at the end of that Phase, including when Pax sets Intrigue or the post-Interlude rule leaves the Senate unchanged. Later Senate Phases are unrestricted by that expired marker. Upward shifts and other independent Senate restrictions remain intact. |

The repair report will record executable regressions, their failures against
the starting engine, the accepted source identity, integrated checks, and
remaining findings. Protected references and canonical constants remain read-only.
