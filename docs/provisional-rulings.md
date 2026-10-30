# Provisional project rulings

**PR-01–PR-06 adopted on 24 October 2026; PR-07–PR-09 adopted on
29 October 2026 (America/Chicago).** These nine rulings determine the
engine's behavior where the available sources conflict or leave a procedure
unspecified. For the first six, the owner instructed:
"Use each of these. Mark them as subject to possible later correction if
authoritative source is found."

**Every ruling below is provisional and subject to possible later correction
if an authoritative source is found.** They are project decisions, not
official GMT errata or designer-confirmed answers. Adoption settles how this
project plays the affected cases; it does not resolve the external source
questions. The protected `Reference Documents/**` and `rules_consts.py`
remain unchanged.

| ID | Adopted behavior | Prior behavior |
|---|---|---|
| [PR-01](#pr-01) | Ignore A30's extra Belgic laurels; use normal shaded Event procedure. | Same behavior, now explicitly adopted. |
| [PR-02](#pr-02) | Non-player Aedui and Belgae lend for A28 only where the executor contributes its own participating pieces. | Both factions' agreement policies were left unresolved. |
| [PR-03](#pr-03) | Romans retain unused Frumentum funding, subject to the Resource cap. | Legacy Roman retention, now explicitly adopted. |
| [PR-04](#pr-04) | German-owned A63 resolves at Interlude, retains German ownership, then becomes dormant. | Same behavior, now explicitly adopted. |
| [PR-05](#pr-05) | Ariovistus Harassment follows printed faction order, then automatic Arverni last. | Fixed faction-order fallback. |
| [PR-06](#pr-06) | Winter Harassment carries forward the last actually played non-Winter card's order. | Fixed faction-order fallback. |
| [PR-07](#pr-07) | One non-player Aedui Supply agreement roll covers the current Roman action, across all relevant Regions and routes. | Separate Region-keyed agreement rolls. |
| [PR-08](#pr-08) | Rally/Recruit bonuses cannot establish the prerequisite for the ordinary placement in the same Region. | Same behavior, now explicitly adopted. |
| [PR-09](#pr-09) | Each tied A20 Counterattack casualty selects an eligible origin Region with equal probability. | Fixed origin-allocation order. |

## Sources and research scope

The owner authorized external research specifically for these questions.
The research checked GMT's [Ariovistus rules][ariovistus-rules],
[Ariovistus playbook][ariovistus-playbook], [Spanish translation][spanish],
and [Second Edition base rules][base-rules], alongside the supplied
transcriptions and the earlier authorized [Vassal comparison][vassal].
The owner then supplied the text of [Volko Ruhnke's errata thread][errata],
including the 15 November 2018 update and the quoted later comments. That
material does not settle any of those six questions. No ruling here should
be attributed to that thread.

On 29 October, the owner separately authorized research into the Supply
roll's geographic scope, Rally/Recruit bonus timing, A20 Counterattack
casualty origins, and optional O38's Capability label, then adopted the
recommendations for the three unresolved procedures. That research did not
find an authoritative answer to PR-07–PR-09. The O38 label question was
resolved separately by the owner's photograph of the replacement card and
the boundary-label rule in §5.3; it is not a provisional project ruling.

The [question ledger](../QUESTIONS.md#current-open-source-questions)
preserves the ambiguities and historical dispositions. Research did not
establish that no authoritative answer exists elsewhere.

<a id="pr-01"></a>

## PR-01: A30 Orgetorix and Belgic laurels

**Ruling:** Ignore the extra Belgic laurels on the card face. Non-player
Belgae use their normal shaded Event procedure and ordinary Event targeting
priorities. Do not add a special Orgetorix instruction or a new No Event
condition.

**Basis:** The Ariovistus playbook's card list, printed page 12, identifies
German and Aedui laurels but none for Belgae. The supplied Belgic instruction
sheet has no corresponding entry. This supports treating the extra symbol
as an error, although no designer confirmation was found.

**Status:** Provisional; subject to possible later correction if an
authoritative source is found. Review the cue and any associated instruction
together if new evidence supplies one.

<a id="pr-02"></a>

## PR-02: A28 Admagetobriga agreements

**Ruling:** Apply the conditional lending rule to both non-player Aedui and
non-player Belgae. In each selected Battle Region, either faction lends its
Warbands only if the executing faction contributes its own pieces that
actually participate in that Battle. A piece merely present but unable to
participate does not satisfy the condition. Check each Region separately.

Non-player Romans still refuse to lend Auxilia. Game-run Arverni
participation remains automatic. Human factions still choose whether to lend.
This ruling concerns A28 only; it does not grant consent for other Events,
Supply Lines, Retreat, Quarters, or Diviciacus cooperation.

**Basis:** A8.6.6's heading names Aedui, while its operative sentence names
Belgae. The published English rulebook, printed page 10, and the Spanish
translation repeat that conflict. Applying the condition to both is the
owner-adopted reconciliation. Replacing only one faction name would leave
the other faction's lending procedure unspecified. Base 8.4.2's restrictions
on particular agreements do not establish a general refusal of all lending.

**Status:** Provisional; subject to possible later correction if an
authoritative source is found. The extension to both factions is a project
decision, not a discovered official correction.

<a id="pr-03"></a>

## PR-03: A53 Frumentum's unused funding

**Ruling:** Treat the amount specified by Aedui as transferred funding.
Romans retain any part not spent on the granted actions, subject to the
normal Resource cap. For example, supplying 8 and spending 5 leaves 3 for
Romans. There is no automatic refund. Any agreed return is an explicit
Resource transfer under the ordinary agreement rules.

The granted actions still spend only the specified allocation; unrelated
Roman Resources remain reserved. The non-player contribution policy remains
half of Aedui Resources to non-player Romans and none to human Romans.

**Basis:** A53's human text, Ariovistus playbook printed page 9, does not
specify ownership of unspent funding. A8.6.6 expressly describes the
non-player contribution as a transfer. This ruling uses that wording to
interpret the Event's ownership mechanism consistently across seats.

**Compatibility:** The result field `unused_policy` retains its historical
value `legacy_roman_retention` for existing consumers. That string does not
mean the policy remains unadopted; PR-03 is its current project authority.

**Status:** Provisional; subject to possible later correction if an
authoritative source is found. A spending-allowance interpretation remains
an unresolved alternative in the source record.

<a id="pr-04"></a>

## PR-04: German-owned A63 after the Gallic War Interlude

**Ruling:** Resolve the German-owned shaded A63 activation during the
Interlude's specified Winter Events step, before changing factions and
Forces. Retain German ownership afterward, but grant no further activations
in the base-game half. The card becomes dormant; its ownership does not move
to Arverni with the player seat. Aedui- or Belgic-owned A63 continues to work.

**Basis:** The Gallic War scenario, Ariovistus rules printed pages 16-17,
explicitly preserves capabilities, including Germanic ones, with their
factions. It separately changes the player's role and the Resource,
Eligibility and Victory markers. It supplies neither a capability ownership
transfer nor a paid-action procedure for the now game-run Germans.

**Status:** Provisional; subject to possible later correction if an
authoritative source is found. Dormancy is a project interpretation; the
source's instruction that capabilities remain in effect leaves this point
open to correction.

<a id="pr-05"></a>

## PR-05: Ariovistus Harassment order

**Ruling:** Resolve eligible harassers in the printed faction order, then
resolve automatic Arverni Harassment last. Per A2.3.2, Germans use the green
Arverni symbol on original cards or the black Germanic symbol on expansion
cards. Germans receive only that one position in the order.

**Basis:** Base 3.2.2 and 3.2.3 put the printed factions before game-run
Germans. A2.3.2 gives playable Germans a printed position, while A3.2.2
requires Arverni Harassment without assigning its position. PR-05 carries
the base structure over to the expansion's game-run faction.

**Status:** Provisional; subject to possible later correction if an
authoritative source is found. The Arverni-last placement is an adopted
interpretation, not an express published timing rule.

<a id="pr-06"></a>

## PR-06: Harassment during Winter Campaign

**Ruling:** During Winter, retain the faction order of the last non-Winter
card actually played. A card counts even if all factions passed or nobody
executed its Event text. Do not use the upcoming card. Apply the usual
game-run faction last: Germans in the base game, or Arverni under PR-05 in
Ariovistus. The Interlude's Winter Events use the first-half order before
the scenario changes.

**Basis:** Base 3.2.2 and 3.2.3 refer to the current Event's order, but the
Winter card has none. This convention preserves the order governing the end
of the year. It does not give an unplayed card an early effect or assign the
same permanent order to every Winter. A concrete affected case is
Vercingetorix's two-step March during Winter Campaign.

**Saves and replay:** Recover the order read-only from the saved
`played_cards` history; `current_card` remains Winter. No new history field
or save-format version is required. If a manual or incomplete older state
has no recoverable preceding Event, use the current scenario's Winter
Campaign card order (63 in the base game, A63 in Ariovistus), followed by the
game-run faction. That deterministic compatibility fallback is not claimed
to reconstruct missing history.

**Status:** Provisional; subject to possible later correction if an
authoritative source is found. Both the normal convention and the
missing-history fallback must remain identified as project decisions.

<a id="pr-07"></a>

## PR-07: One Aedui Supply agreement roll per Roman action

**Adopted:** 29 October 2026 (America/Chicago).

**Ruling:** When §8.6.6 calls for a die to determine whether non-player
Aedui agree to a human Roman Supply Line, roll once for the current Roman
action. Apply that answer to all Aedui-controlled Regions needed by that
action's Supply Lines, including its accompanying Special Ability. Do not
roll again because a route crosses another Aedui-controlled Region, because
the Romans choose a different route, or because a refused action is replanned.
The Romans retain the rule's option to choose their action again after a
refusal. A later action obtains its own answer when required.

The shared answer does not expand the reconsideration window: §8.6.6
rechooses the current Recruit or Build at its actual boundary, preserving
any earlier completed Command or Special Ability and their legal constraints.

This does not change the printed victory-score thresholds, the 1–4 consent
range at Roman scores 10–12, human Aedui's decisions, or other factions'
agreement policies. It is not a general rule about lending, Retreat,
Harassment, or the number of Winter Quarters rolls.

**Basis:** §8.6.6 describes Aedui agreement during Roman actions and permits
rechoosing the current action after refusal; §1.5.2 binds an agreement for
the action. A single diplomatic answer for that action avoids making the
same faction's cooperation less likely solely because a route passes
through more of its Regions. Neither passage explicitly sets roll scope;
this is the owner-adopted interpretation.

**Status:** Provisional; subject to possible later correction if an
authoritative source is found. The one-roll scope is not official errata.

**Compatibility:** Previously confirmed Region-specific permissions retain
their original scope. A later refusal for a still-unanswered Region cannot
revoke those promises, and their presence does not invent broader historical
permission for Regions that were never approved.

<a id="pr-08"></a>

## PR-08: Rally and Recruit bonuses follow ordinary prerequisites

**Adopted:** 29 October 2026 (America/Chicago).

**Ruling:** For Aquitani (25 shaded), Nervii (A70 shaded), and Gallia Togata
(A5 unshaded), determine whether the selected ordinary Rally/Recruit option
is legal before placing its bonus Warbands or Auxilia. The bonus cannot
establish Control and thereby authorize an otherwise illegal Allied Tribe
placement during that same Region's Rally/Recruit.

The compulsory bonus still applies even when ordinary troop placement is
zero, subject to available pieces and the printed action restrictions. This
does not remove Caesar's or Vercingetorix's express Ally permissions,
Vercingetorix's two-option Rally, a legal accompanying Special Ability, or
A70's separate end-of-action Allied Tribe placement. The explicit German
Home addition remains at the end under A3.4.1.

**Basis:** §§3.2.1 and 3.3.1 give prerequisites for each ordinary placement;
§5.1.1 retains normal rules unless an Event changes them. These three cards
state additional quantities, but do not expressly provide an earlier
placement window. Aquitani's published Tip confirms extra pieces when the
ordinary count is zero without specifying a bonus-first option. The owner
adopted the existing prerequisite-before-bonus procedure.

**Status:** Provisional; subject to possible later correction if an
authoritative source is found. This ordering is a project interpretation,
not a discovered timing clarification.

<a id="pr-09"></a>

## PR-09: A20 Counterattack casualties among equal origins

**Adopted:** 29 October 2026 (America/Chicago).

**Ruling:** When A20 Morbihan temporarily combines Arverni Warbands from
several Regions and a Counterattack causes casualties, first follow
A3.2.4's visibility priority: Scouted, then other Revealed, then Hidden.
Within the current visibility class, choose an origin Region uniformly at
random for each casualty, among the origins still contributing such
Warbands. Remove one from the chosen origin and repeat, recalculating the
eligible origins after each loss. Use the game's seeded RNG.

This is equal probability per eligible **Region**, not per counter: an
origin contributing three tied Warbands and an origin contributing one each
have a one-half chance to suffer the next casualty. An origin with none
remaining in that class is no longer eligible. With only one eligible
origin, no random tie-break is needed. Ordinary Battle priorities, whether
Counterattack occurs, and surviving pieces' return and visibility remain
unchanged.

**Basis:** A20 projects pieces into Battle without relocating their physical
origins permanently. A3.2.4 determines the class of piece lost, but does not
resolve origin ties. §8.3.4's equal-Region selection is a useful consistency
principle, rather than an explicit rule for this unusual Event. The owner
adopted random origin selection to avoid a fixed geographic preference.

**Status:** Provisional; subject to possible later correction if an
authoritative source is found. The source does not expressly assign an
origin chooser or this tie-break.

## Later corrections and evidence

If an authoritative clarification is found, record its exact source,
applicable edition, and the ruling it supersedes. Preserve this adoption
record and the earlier validation evidence. Update the affected code,
regressions, player/API guides, and save/replay compatibility notes together.
Review any changed outcomes on the same seeds before replacing a baseline.

Earlier validation reports describe the source revisions they tested. Their
test counts and game outcomes do not validate these later adopted rulings.

[ariovistus-rules]: https://s3-us-west-2.amazonaws.com/gmtwebsiteassets/Ariovistus/Ariovisus_Rules_Final_Lo-Res.pdf
[ariovistus-playbook]: https://s3-us-west-2.amazonaws.com/gmtwebsiteassets/Ariovistus/Ariovistus_Playbook_Final_Lo-Res.pdf
[spanish]: https://s3-us-west-2.amazonaws.com/gmtwebsiteassets/Ariovistus/Ariovistus_Rulebook-Spanish.pdf
[base-rules]: https://gmtwebsiteassets.s3-us-west-2.amazonaws.com/FallingSky/FS_Rules_2018.pdf
[vassal]: reviews/vassal-module-2026-10-20.md
[errata]: https://boardgamegeek.com/thread/2072553/ariovistus-official-errata
