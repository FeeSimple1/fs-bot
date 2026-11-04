# CV-PERSISTENCE — verified Circumvallation follow-up

4 November 2026, America/Chicago. Status: **open; high priority**.
**Later partial repair, 4 November:** the
[no-Romans cleanup batch](circumvallation-no-romans-2026-11-04.md) repairs the
last-Roman boundary only. The observations below describe the earlier audited
revision; all other listed mechanics remain open. CV-PERSISTENCE is not closed.

This is a newly recorded mechanics finding outside the original 50-finding
human-choice audit. It is not repaired by the Circumvallation choice batch.

## Verified behavior

Card Reference 4 and its Tips say that the Citadel faction's marked pieces
cannot leave their Region, Romans defend as if Fort when that group attacks
alone, and the marker is removed when that group attacks Romans, is eliminated,
or has no Romans remaining in its Region. Later arrivals and placements are
separate from the marked group. The Interlude reference removes only Forces
under the marker, then the marker.

Read-only executable probes reproduce all of these existing defects:

| Probe | Required behavior | Observed behavior |
|---|---|---|
| One marked Arverni Warband attempts a normal March | Remain in the marked Region | It leaves successfully |
| Remove the last Roman piece there | Remove the marker | Marker remains |
| Four marked Arverni Warbands attack six Roman Auxilia alone, no Retreat | Virtual Fort reduces two Losses to one; five Auxilia remain | Four Auxilia remain; virtual Fort is absent |
| The marked group has just attacked Romans | Remove the marker | Marker remains |
| Interlude cleanup with marked Arverni and unmarked Romans together | Remove the marked force only | The unmarked Roman force is removed too |

Every before/after board validates. The parent revision
`947bf814129cfc135b49d2babbbbf740bb46f356` and the choice-repair candidate
produce the same probe results. These mechanics defects predate this batch.
The parent probe uses its existing card handler to place the Boolean marker;
the candidate uses the new post-choice placement helper. Both represent the
same initial marked group with no ambiguous later arrivals in these witnesses.

## Repair requirements

1. Persist the actual marked owner's physical cohort, including identities
   needed for Allies/Citadels, Leader and Warband visibility. Later arrivals
   and placements must remain outside that cohort.
2. Track that membership through removals, flips, cooperation, forced movement
   and other Events, applying the supplied source hierarchy and §5.1.2.
3. Enforce the movement restriction without blocking unmarked pieces that may
   share the Region, and preserve all legal physical selection choices.
4. Apply virtual Fort protection to the specified marked-group-alone attack
   without inventing an actual Fort casualty counter. Clear the marker at its
   printed boundaries while preserving the protection for the relevant Battle.
5. Fix Interlude cleanup to remove only marked Forces, preserving other
   factions and later unmarked arrivals of the same owner.
6. Define explicit handling for old Boolean-marker saves, which do not record
   enough information to reconstruct a mixed original/arriving force silently.

Adjacent review lead: `event_eval.py` classifies numeric4 as a Capability,
while the supplied text describes a marker Event. Its downstream effect on
NPC evaluation is not established by these probes and needs separate tracing.

## Evidence and accounting

The [choice-repair evidence ZIP](circumvallation-2026-11-04-evidence.zip)
contains the candidate and parent probe scripts/results. The parent script
loads only the common fixture helper from the candidate test file; all engine
operations run against the parent package. It can be made portable by updating
that fixture path or copying the helper into the extracted probe directory.

The original human Event-March choice finding BE-01 is closed separately.
Original bundle progress is **22/50 closed (44%), 28 open**, plus this additional
known high-priority follow-up. Neither the choice repair nor that percentage
claims complete Circumvallation rules compliance.
