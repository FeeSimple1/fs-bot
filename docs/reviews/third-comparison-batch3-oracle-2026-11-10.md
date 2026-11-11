# Third comparison, Batch 3: source-derived expectations

Starting revision: `c6ed9dd43597cbe4958821c2474ed9e5f9fbb406`.
These expectations precede inspection of the affected implementation and tests.

| Finding | Supplied authority | Required behavior and controls |
|---|---|---|
| BE3-01 | Card Reference 53; Chapter 6 §6.2; Chapter 3 §3.4.4; Chapter 1 §1.4.3; Chapter 5 §5.1.1 | Consuetudine hides every German Warband, removing a Scouted marker instead of hiding that piece. Resolve the Germans Phase without March and with the printed Ambush exception regardless of Hidden enemy numbers. Carry that exception through target selection and combat; ordinary Germans Phase behavior remains distinct. |
| BE3-03 | Card Reference 71; Chapter 5 §§5.1.1, 5.1.3 | Placing the Colony marker creates its Tribe and adds its Control Value even if the executing Ally cannot be placed. A newly created unallied Colony is Subdued and counts for Roman victory. Placing a possible Ally and replacing an existing Colony retain their other printed effects. |
| BE3-04 | Card Reference 66 shaded and Tip; Chapter 5 §5.1.3 | After the selected Gallic relocation, place an Ally at a legal Subdued Tribe in the selected Region whenever possible. An authored plan cannot omit a possible mandatory placement. Preserve player selection among legal Tribes, scarcity, stacking, and atomic rejection. |
| EX3-01 | A Card Reference A29 shaded; Chapter 5 §§5.1.1, 5.1.3 | Place four German Warbands and one Settlement among Regions adjacent to Germania, to the extent supply and legal placement permit. Preserve exact allocation, ordered timing choices and the surviving newly placed cohort's free Raid. Reject incomplete human selections when a fuller printed effect remains possible. |
| EX3-03 | A Card Reference A35 unshaded; Chapter 5 §§5.1.1, 5.1.3; Chapter 1 §1.4.2 | The Ally at Treveri replaces its prior occupant or Dispersed/Gathering marker. Clear that Tribe's status and associated reminder, even when the selected replacement Ally is unavailable. Preserve unrelated Region markers and the optional reinforcement quantity. |

All sources are supplied project references. Protected references and canonical
constants remain read-only. The final report will record regression evidence,
complete validation, source identity and the still-open final repair batch.
