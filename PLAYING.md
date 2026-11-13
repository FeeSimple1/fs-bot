# Playing Falling Sky against the bots

This engine supports GMT's **Falling Sky:
The Gallic Revolt Against Caesar** (2nd Edition) and the
**Ariovistus** expansion, with non-player bots for every faction.
You pick any seat (or several); the bots play the rest using the
published non-player flowcharts. See [current status](docs/current-status.md)
for verified fixes, test coverage, and provisional source interpretations. The
[documentation index](docs/README.md) also links assistant play and API guides.

The [human-choice audit](docs/reviews/human-choice-audit-2026-10-29.md)
records the original findings. The [current status](docs/current-status.md)
tracks repairs and remaining limits. At Command prompts, `b`/`board` shows
the planning position after preceding operations, including a Fort built
before March. Planning uses a detached board and random stream.

To use a Special Activity during a Command, choose
**Command, Special Activity, then continue Command**.
For Battle, select the Regions and defenders, then pick the Battle after
which the Special Activity resolves. Its choices use a preview of the
completed Battle. For Raid, the menu offers the Special Activity after a
flip and updates the next flip's choices. A single Raid Region keeps its
normal flip limit and its one intrinsic Germanic Intimidate opportunity.
Ambush and Besiege modify Battle directly.

The Aedui bot checks how many defenders survive its Attack before choosing
an additional Battle Region. It also checks whether a legal Retreat could
make the exchange unfavorable. After Rally, the bot uses the placed pieces
and remaining Resources to decide whether it can Trade or Suborn. Roman
players still give their Trade agreement when the Special Ability resolves.
[Aedui Battle and Rally repairs](docs/reviews/eighth-comparison-batch5-2026-11-12.md)

Battle requires your Forces in the selected Region when it resolves. Scout
before Battle may bring Auxilia into that Region. Scout movement uses the
scenario's playable Regions and Gallia Togata marker; base Cisalpina needs
that Event, and movement into or out of Britannia remains prohibited.

Harvest counts each Allied Tribe disc and Citadel once. Resource totals stay
between 0 and 45, including when the Ariovistus Roman score is negative.
Lost Eagle restricts only the next Senate Phase, including when a scenario
replaces the usual shift. Cicero and Pompey use their printed Senate effects.

Shaded Harudes places four German Warbands and one Settlement as far as supply
and legal spaces allow. Choose their allocation and order, then direct the
surviving placed Warbands' Raid. Shaded Migration requires an Ally at its
destination whenever one can be placed. Its Ally choice follows the movement
and reclamation window; movement still resolves if placement is impossible.

Colony adds a Tribe in a playable Region under your Control or with No Control.
In the base game, Gallia Togata opens Cisalpina to Roman placement. With that
Event in effect, Romans can also use Forced Marches to relocate mobile Forces
into or out of Cisalpina. Choose Forced Marches origins and destinations
outside Britannia. The Roman bot uses its March priorities for these
relocations, and the Auxilia it moves become Hidden.

The Colony counts as a Tribe in its recorded Region for Seize, Build, Entreat,
Trade, replacement Events, and Belgic Control Value. Menus offer its actual
name alongside the printed Tribes. A City Razed by Sacking earns no Seize
Forage and cannot be Dispersed again; it stays Razed through Spring.
Stalwart cancels Germanic Horse's extra Losses to Germans on both Attack
and Counterattack, while the Capability retains its effects against others.

For **March (between hops or groups)**, choose the routes and groups, then
select the pause. The Special Activity choices use a preview of the board
at that step. Live decisions before the pause can change the pieces that
are available. At resolution, Scout can split Auxilia off from the group.
When a choice could use either marching counters or identical residents,
the game asks which counters to use. The remaining group continues with
its original movement allowance. Britannia crossings exclude a Special
Activity for the whole March.

Drought now asks each human owner which single piece to lose in every
Devastated Region. Choose exact visibility, a named Allied Tribe/Citadel, or a
Leader, Fort or Legion as offered. Legions go to Fallen. Germans must lose
Warbands before Allied Tribes; Provincia's permanent Fort cannot be removed.
The Event executor chooses the new marker location, while each owner chooses
its own losses. `b`/`board` remains available, and interrupted choices can resume
without halving Resources or applying earlier casualties twice.

Three expansion Events now ask how much of their optional effect you want:
Alpine Tribes shaded lets you select zero to three eligible Regions; Siege of
Bibrax unshaded lets you remove zero to six exact Belgic Warbands by visibility;
Iccius & Andecomborius unshaded lets you place fewer Auxilia for more Roman
Resources. Zero is allowed. Bibrax's four troops/Fort and Iccius's Roman Ally
remain compulsory as possible. The Event's executor chooses, even when Romans
receive the benefit. `b`/`board` is available at each live prompt.

During Quarters, choose Hidden, Revealed or Scouted Warbands/Auxilia separately,
including how many of each relocate. Their visibility stays the same. Only
pieces originally present can take the adjacent step; Roman arrivals may then
take the later Provincia step if eligible. If Supply changes and the remaining
Provincia choices reopen, the menu again offers exact visibility cohorts.
`b`/`board` remains available at these prompts.

During bot Quarters, Belgae, Aedui, base-game Arverni, and Ariovistus
Germans evacuate unprotected Devastated Regions when they have a legal
refuge. Belgae, Arverni, and Germans also gather Warbands around their
Leader while keeping enough pieces behind for Control. You can agree to
or decline a bot's request to quarter in a Region you Control.

After a player selects a Command or Event, either party can give Resources
as long as the gift involves the executing faction. Opening gifts can fund
the Command before you choose its Regions. Choose one or more recipients and
type each exact amount up to the displayed limit. Select **Finish Resource
transfers** to finish for this action, or **Offer Resource transfers again
later in this action** to give at a later step. Use `b` or `board` to inspect
the position.

If one player runs both Factions in a gift, at most four Resources can move
between them during the whole Command or Event (§1.5.2/A1.5.2). Gifts in both
directions and at every pause draw from the same four.

Winter gifts use the same exact amounts. Eligible donors may give before
Quarters relocations and after Roman payments, and before and after Harvest
earnings. Opening Quarters gifts can fund Roman payments. The four-Resource
limit applies only during the Sequence of Play.

When Devastate takes casualties, each human owner chooses its own losses by
piece type and visibility. You may lose a Legion instead of Auxilia, or select
Hidden, Revealed or Scouted Warbands as offered. Remove the entire required
count; Legions go directly to Fallen, without a die roll. Leaders and static
pieces are protected. `b`/`board` is available. All owner choices are gathered
before that Region's pieces and marker change. Non-player/default losses follow
the printed priority, removing Scouted before Revealed before Hidden soft pieces.

Gallic Shouts unshaded privately shows the Roman player the next two facedown
cards, including text and initiative information, before the free Limited
Command/Become Eligible choice. The already face-up next card is excluded.
This benefit belongs to Romans even if another Faction played the Event.
The console labels the alternative **Become Eligible**; `b`/`board` remains
available, and the peek neither draws nor rearranges cards.

At the first Pax Gallica Harvest, distribute the three Winter Track Legions
among any Belgica Regions: Atrebates, Morini and Nervii. You may split them or
place all together, regardless of existing Roman pieces or enemy Control.
All offered Legions must be placed; `b`/`board` remains available. The same choice
applies at the first Harvest after the Gallic War Interlude when its expedition
left Legions in the Winter box. An empty box places none.

When Roman Besiege applies in Battle, choose the exact defending Citadel or
Allied Tribe to remove. Ariovistus also offers a German Settlement. You may
leave every piece by declining the removal. The prompt appears before Battle
Losses, even if those Losses are zero or the Defender declared Retreat.
Use `b`/`board` to inspect before choosing. Removing the Citadel preserves its
normal halving for that Battle unless Ballistae cancels that protection.

A defending Fort or Citadel still halves Attack Losses during an Ambush,
rounded down. Each remaining Loss removes a piece outright unless defending
Caesar rolls 4–6, or 5–6 against Belgae. A successful test restores Roman
saving rolls and allows a Counterattack. Base-game German Battle follows the
same Ambush procedure. In Ariovistus, ordinary German Battle uses the normal
saving rolls and Counterattack rules.

When playing shaded Ballistae or Winter Campaign, choose Arverni, Aedui or
Belgae to receive the Capability. This choice belongs to the Event executor.

If your Faction owns shaded Ballistae, each completed Ambush with a surviving
defending Fort or Citadel now asks whether to remove it. You may decline.
The choice comes after all Battle Losses and Reveal; it is independent in each
Region, including a free Event Ambush. The prompt shows the physical owner
and the Citadel's Tribe, and `b`/`board` inspects the live post-combat board.
Provincia's permanent Fort can never be removed and is excluded.

Unshaded Balearic Slingers lets Romans select one Region in an enemy Battle
Command, including fixed Event Battles and automatic Ambushes. You can use
it while defending or when the attacker is fighting a third Faction. The menu
shows Roman Auxilia counts. A selected Region with zero or one Auxilia can cause zero
initial Losses. There is no separate decline. If both Slingers and Germanic
Horse are unshaded, the initial fire inflicts one Loss per Auxilia. Slingers
is used only once in the Command. The Arverni and Germans Phases and unshaded
German Allegiances use the live PR-13 choices below.

Stalwart German Phalanx cancels Slingers fire against attacking Germans.
It also cancels the Fort protection from unshaded Ballistae. Fort saves
against German Attack or Counterattack Losses remove the Fort on 1–3.
Inflexible cancels the shaded Legio X limit when Caesar attacks German
defenders, so each of his Legions inflicts two Losses before halving.

Shaded Massed Gallic Archers makes the other side absorb one opening Loss
when at least six Arverni Warbands take part, on either side of a Battle.
This also applies in Event Battles and automatic Ambushes. The owner of
the affected pieces chooses how to absorb the Loss when prompted. Stalwart
protects Germans from this opening Loss. Inflexible cancels the unshaded
Archers reduction in Arverni Attack Losses against Germans.

Germanic Horse asks its owner to select a Region in ordinary and free Battle
plans, including fixed Event Battles. Romans may decline the unshaded bonus.
The shaded Gallic owner selects one Region for attack or counterattack.
The menu shows current protection.
The Gallic faction that plays the shaded Event takes the card.
A defending Fort, Citadel or active Abatis blocks attacking Horse doubling.
Unshaded Morasses ignores its defender's Citadel for this calculation.
A defending owner's Citadel blocks its counterattack doubling; Abatis alone
does not. Choosing a currently blocked Region does not bypass that restriction.
Use `b`/`board` to inspect the live position. The chosen Region survives later
casualty prompts and saving, and its bonus expires with that Battle Command.
Prospective queues use the live windows below.

In a prospective Battle queue, unshaded Horse now offers a fresh Roman choice
as each actual Battle becomes eligible. Use it here, save it for a later
Battle if offered, or decline for the rest of the Command. Saving does not
spend the use and does not guarantee a later Battle. A Retreat can create a
new eligible window. Once used or declined, no second activation is possible.
Slingers and shaded Horse offer use here or save for later while candidates
remain. At the final candidate, if it becomes a Battle, use here is the only
action. There is no general decline. If no later eligible Battle occurs after
you reserve, the benefit expires unused without replaying combat. This follows
[provisional PR-13](docs/provisional-rulings.md#pr-13), subject to official
correction. Selecting a protected or zero-Auxilia Battle never bypasses the
capability's printed effect. Saved decisions and replay retain these choices.

Unshaded Lucterius now lets the Event executor choose either zero to five
Auxilia in Provincia or zero to six nearby Arverni Warbands to remove. Select
exact Regions and Hidden/Revealed/Scouted pieces. Unshaded Hostages lets you
select zero to four Warbands/Auxilia in Regions you Control, choosing removal
only or replacement for each selected cohort. You can mix the actions. Your
replacement is Roman Auxilia or your faction's Warband; an unavailable
replacement leaves the original removed. Use `b`/`board` to inspect before
choosing. These live choices survive pending replies, saving and replay.

Shaded Hostages lets you choose one or two distinct Subdued Tribes where
Roman pieces are present. Choose the Gallic Ally owner and the Warband owner
at each Tribe. Both pieces use that Tribe's Region. An unavailable piece
does not prevent the other placement.

Shaded Lucterius restores the Arverni Successor as Vercingetorix. You can
place him in his current Region or any legal destination. Shaded Flight of
Ambiorix restores a Belgic Successor or the Available Leader in Germania,
Morini, Nervii, Treveri, or Sequani. Bots decline the shaded side when
named Ambiorix is already on the map. Its unshaded side uses the Belgic
Control-Allies total shown on the board.

Shaded Marcus Antonius (6) lets the executor choose up to four Roman Auxilia
to move to Provincia. Select their origin and visibility. The pieces keep
their visibility when they arrive. Moving zero pieces still applies the
card's eligibility effects.

Unshaded Alaudae places its Legion and Auxilia in one Roman Controlled
Region. Unshaded Numidians places its Auxilia and grants Battle in the Roman
Leader's Region or an adjacent one, in either edition. A Roman Successor
supplies that range.

Shaded Alaudae (7) applies when the Legions track starts with seven or
fewer Legions. Choose one on-map Legion to return to the track, then
one on-map Auxilia by Region and visibility to return to Available.
Each removal applies as far as possible.

Shaded Numidians (11) lets the executor remove four Roman Auxilia from
any Regions, or all on the map if fewer are present. In both editions,
choose the exact Hidden, Revealed or Scouted Auxilia to return to Available.

Shaded Sappers (24) lets the executor choose one Region with an Arverni
Citadel and remove any mix of two Roman Legions and Auxilia there. If the
chosen Region has fewer than two eligible pieces, remove all of them.
Choose Auxilia by visibility. Removed Legions go to Fallen.

Shaded Cotuatus & Conconnetodumnus (31) lets the executor name one Roman
Ally, one Aedui Ally, and one additional Ally of either faction. Each
prompt reflects the pieces still on the board. Citadels are protected,
and the Event carries out the removals that are possible.

Unshaded Litaviccus (45) lets the executor replace up to two Arverni
Warbands with Aedui Warbands in each of up to two Regions. Choose the
Arverni Warbands by visibility. If an Aedui replacement is unavailable,
the source Warband is still removed. Arverni transfer up to four
Resources to Aedui even if the executor chooses zero replacements.

Unshaded Aduatuca (58) lets the executor choose one Region with a Roman
Fort and remove nine Belgic or Germanic Warbands there in any mix. If
fewer than nine are present, remove all of them. Choose each group by
faction and visibility.

Unshaded Indutiomarus (60) lets the executor choose Treveri or one
adjacent Region and remove any mix of six Belgic Warbands and Allies.
Choose Warbands by visibility and Allies by Tribe. Citadels are protected.
If the chosen Region has fewer than six eligible pieces, remove all of them.

Unshaded Catuvolcus (61) lets the executor choose one or more named
Allies of a single faction in Nervii. Then choose five Warbands there
by faction and visibility, or all remaining eligible Warbands if fewer
are present. The Warbands can come from any combination of factions.
Each step applies as far as possible.

Shaded Pompey applies when four or fewer Legions remain on the track.
Shaded Gallia Togata applies when the Senate is outside Adulation.
When the removal applies, the Roman player chooses the pieces even if
another faction played the Event. Split the removals across Regions
and select the exact Auxilia visibility. Remove as many of each printed
type as the board allows. Legions return to the track and Auxilia return
to Available.

Unshaded Usipetes & Tencteri (A36) lets the faction playing the Event choose
which German Settlements and Warbands to remove in Morini, Nervii and
Treveri. Select exact Warband visibility, including Scouted. Remove two
Settlements and eight Warbands when enough are present.

Shaded Publius Licinius Crassus (A17) lets the faction playing the Event
choose one Region and the exact Roman Auxilia to remove there. Remove four
or all present if fewer. Rome is ineligible through the next card.

Shaded Aduatuci (A58) lets the faction playing the Event select one Belgica
Region, name the Roman Ally to replace, and choose exact Auxilia by
visibility. The replacements are followed by a free Ambush against Rome in
that Region if the executor can Ambush there.

Unshaded Bellovaci (A69) lets the executor select four Belgic Warbands in
Atrebates, or all present if fewer, by exact visibility. Choose the Roman
or Aedui Ally and choose Roman Auxilia or Aedui Warbands separately. The
Event places four of the chosen troops, or all Available if fewer.

At a March route prompt, **Stay here (hide pieces; pay March cost)** selects
the origin without moving a group. All its Revealed Auxilia or Warbands hide;
Scouted pieces instead lose their marker and remain Revealed. You still pay
that origin's normal March cost, doubled by Devastation as usual. No group
quantity or Harassment prompt follows for that stay. You can combine staying
origins with moving origins; Frost still prohibits ordinary March. Events
requiring a specific destination offer movement routes only.

For Roman Build, pick Regions in the order you want to resolve them. The
planner completes each Region before moving to the next: an optional Fort,
then either Subdue or place one Roman Ally. Resources, Control and Supply
eligibility are checked on the evolving position. This allows an Ally in one
Region before a Fort in another. Non-player Romans retain their published
Fort/Subdue/Ally priorities. See the [Build report](docs/reviews/build-order-2026-11-04.md).

For Mons Cevenna (card 9), choose the first March's origin, exact mobile
pieces and adjacent destination within Provincia, Sequani and Arverni.
All pieces at the selected origin undergo the normal March visibility flip.
Then choose the free Command and optional Special Ability, in either supported
order, in or from that destination. The second Command may March out of it.
If no native March is possible, choose one of the three Regions for the
remaining benefit. `b`/`board` is available while planning. Diviciacus
cooperation requires separate consent for each Command.

For shaded Aduatuca (card 58), the Event player chooses a Roman Fort
Region and which adjacent German groups March there, with exact quantities.
You may select an origin for hiding without moving Warbands. Each origin
can send only one group. Resident Germans join the following Ambush against
Romans; Hidden superiority is not required, and the Fort does not halve
the one Loss per two German Warbands. Roman casualty choices remain with
the Roman player. The shaded Event skips the unrelated unshaded removal
prompts, and `b`/`board` remains available during March selection.

For unshaded German Allegiances (card 65), the Event player chooses up to
two German origin Regions, exact moving quantities and adjacent destinations.
Zero Warbands selects an origin for hiding only; it still counts against the
two-Region limit. Only original counters can leave each selected origin:
arrivals cannot March again or be hidden a second time. Then choose the
order and defenders for Ambushes in every Region able to act. Hidden
superiority remains required, and Forts retain their normal protection.
Even a zero-Loss Ambush may be legal. Roman/Aedui defensive cooperation is
checked before combat; Germans cannot switch to an ordinary Battle if it
removes their ability to Ambush. Choosing the bot default at the first March
menu delegates the complete grant; a later Ambush default chooses only the
next Ambush. `b`/`board` remains available at these menus.

For unshaded Germanic Chieftains (card 17), Romans choose up to three German
moving groups and then a single Ambush Region and defender, whoever played
the Event. These are moving groups with positive Warband quantities, one
per original origin; choosing no groups is allowed. The whole selected
origin undergoes normal visibility changes, but arrivals cannot move or
flip again. Only the one chosen Region Ambushes, even when others are able.
The Roman player also owns German visibility formation choices. Choosing
the Roman bot for the whole grant applies the Roman card instructions;
shaded Germanic Chieftains still runs the separate Germans Phase procedure.
`b`/`board` and saving at the following Ambush decision remain available.

In the automatic Germans Phase, Rally adds at most one new Ally per Region,
starting with Suebi, then other Tribes in Germania, then elsewhere. March
forms all groups before moving any of them and moves the largest groups
first. Each group can enter one adjacent Region. March first favors gaining
new Germanic Control, then favors Regions Controlled by a human player
within either tier. Scouted Warbands lose their markers and stay Revealed
during the March step, including Warbands that stay in place.
Battle with Ambush selects one defender per Region, preferring human players
to Non-players. Consuetudine (card 53) waives the Hidden-piece comparison
and keeps the one-defender limit.

For Circumvallation (card 4), Romans choose or decline the complete benefit,
regardless of who plays the Event. Choose the enemy Citadel destination and
exact adjacent Roman groups; multiple groups may leave an original Region.
There is no four-Legion limit. The normal origin visibility step applies to
pieces left behind. An empty March leaves the remaining placement effect to
resident Romans; a new marker is placed only after March and only if a
non-Roman Citadel and Roman pieces remain there. Cooperation requires separate
consent. `b`/`board` and save/resume at physical formation remain available.

**Circumvallation limitation:** its continuing marked-group movement and Fort
rules, attack/elimination marker cleanup, and exact Interlude removal remain
broken. The marker now clears when no physical Roman pieces remain; a lone
Roman Ally, Fort or Leader counts as Roman presence. The
[new follow-up](docs/reviews/circumvallation-persistence-followup-2026-11-04.md)
records reproducible witnesses. The repaired choice flow does not make this
card's persistent effects rules-complete.

## Requirements

Python 3.10 or newer. Nothing else — no packages to install, no
internet needed.

- **Windows**: install from https://www.python.org/downloads/ and
  tick **"Add python.exe to PATH"** during setup.
- macOS/Linux: `python3` is usually already present.

You can also install this checkout with `python -m pip install .` and use
`fs-bot --save autosave.json` outside the source directory. See
[RELEASES.md](RELEASES.md) for local distribution and compatibility checks.

## Starting a game

**Windows**: double-click **`play.bat`**.

**Any platform**, from a terminal in this folder:

    python -m fs_bot.cli.app --save autosave.json

A setup wizard asks for the scenario and who runs each Faction. For a first
game, try **The Great Revolt** as the **Arverni**.

In standard solitaire, one human Faction plays against three Non-players.
The human must survive to final scoring and place first by victory margin.
A Non-player that passes its threshold wins in any Victory Phase, including
the final one (§8.9).

The Gallic War Interlude supplies a new deck with five Winter cards. Its
fifth Winter is the final one for scoring by margins (§2.4.1, A2.1).

### Spare Factions

Choose **Human** for a separate player or **Human with Aedui** or
**Human with Belgae** to assign a printed pair to one player
(§1.5.1/A1.5.1). The paired player makes each Faction's decisions when
they come up.

| Scenario | First pair | Second pair |
|---|---|---|
| Original scenarios | Romans and Aedui | Arverni and Belgae |
| Ariovistus and the first half of The Gallic War | Romans and Aedui | Germans and Belgae |

At the Gallic War Interlude, the German player takes over Arverni and keeps
Belgae if they were paired. A pair uses its lower victory margin and both
Factions must pass their threshold for early victory. In The Great Revolt,
the Arverni and Belgae pair uses its higher margin and either Faction can
qualify. That scenario starts Belgae with Ambiorix if a player runs Belgae
alone or a player runs the Romans and Aedui pair.

For a scripted setup, repeat `--pair` for both pairs. For example, two
players can run The Great Revolt with this command.

    python -m fs_bot.cli.app --scenario "The Great Revolt" --bots "" --pair Romans,Aedui --pair Arverni,Belgae --save autosave.json

### Saving and other setup options

`--save autosave.json` writes a snapshot after every card. Resume any
time with:

    python -m fs_bot.cli.app --load autosave.json --save autosave.json

Other options: `--scenario "Name"` and `--bots Romans,Aedui,Belgae`
skip the wizard; `--seed N` makes the deck deterministic; see
`python -m fs_bot.cli.app --help`.

Choose card versions when starting a game with
`--card-edition second-edition` or `--card-edition original`. This choice
governs the five optional revised cards (11, 30, 39, 44, and 54), including
their displayed text and effects. It does not change the expansion deck or
scenario rules. The default, `legacy`, preserves the previous behavior:
original versions in base scenarios and revised versions in Ariovistus.
Explicit editions remain unchanged through the Gallic War Interlude;
`legacy` continues to follow the current scenario. Older saves without a
choice use `legacy`. A loaded game cannot change editions.

To use the published optional Diviciacus Leader rule in an original
scenario, add `--diviciacus-option` when starting the game. It replaces
card 38 with O38; Diviciacus starts off-map and can be placed by that Event.
This is separate from the five-card edition choice. It does not change the
Gallic War Interlude's existing A38 replacement. The option cannot change
when loading or replaying a game.

Three other printed options are available as new-game flags, including when
using the setup wizard. They also work with `llm_seat init`.

| Flag | Effect | Availability |
|---|---|---|
| `--sudden-frost` | When Winter is exposed next, switch it with the current Event and conduct Winter immediately. The Event starts the next Year unless the game ends. | Any scenario, with every player's agreement at setup |
| `--even-initiative` | Shuffle four first-symbol piles, deal equal numbers into a pool until it reaches or exceeds the needed count, then shuffle and deal the scenario's Events. | Every initial scenario except Pax Gallica? |
| `--short-great-revolt` | Use 30 Events in six piles, with Winter shuffled into piles 3 and 6. | The Great Revolt only |

Even Initiative selects 30 Events from a 32-card pool, 45 from a 48-card pool,
or all 60 selected cards. The final partial selection can make the finished
deck's initiative counts unequal. The Gallic War Interlude still explicitly
replaces the first-half deck with its printed Pax Gallica? deck. Even
Initiative applies to the initial deck, and Sudden Frost continues in the
second half. The option flags are saved and cannot change during load or
replay. Older saves select the standard rules for any absent option.

## How a turn works

Each Event card shows the initiative order. When it is your turn the
CLI walks you through menus: pick Command / Command + Special
Ability / Event / Pass (as eligibility allows), then the regions and
pieces involved. With Command + Special Ability, the Command menu also
offers **Special Activity first, then Command**. You can instead choose
the Command first and add its Special Activity afterward. The interrupt
option allows Rally, Recruit, Raid, or Seize in some Regions, then the
Special Activity, then the rest of that Command in other Regions.
For base-game Arverni Rally, it also allows the Special Activity between
Vercingetorix's two options in the same Region.
Ambush and Besiege resolve within their accompanying Battle.

Entreat menus select the exact Allied Tribe disc. When an enemy has a
Citadel and another Tribe's Ally in the same Region, selecting that Ally
changes its own allegiance and preserves the City Citadel's allegiance.
The Arverni replacement follows Available-piece and stacking limits (§4.3.1).

Seize and Entreat cannot select a Region twice. Battle casualty menus show
only the legally eligible group of pieces for the current loss: static pieces
first when retreating and after other pieces otherwise, with Diviciacus last.
Defending Abatis can absorb a Loss with a Fort's saving roll, or you can
assign the Loss to another eligible piece. Diviciacus waits while the marker
can still absorb. Stalwart cancels both Legio X adjustments when Rome and
the Germans Battle, during the Attack and any Counterattack.
Some exact physical casualty selections remain on the audit backlog.

The Aedui bot starts Battle when it can force a Loss on an enemy Leader,
Ally, Citadel, Legion, or an Ariovistus Settlement. It checks legal casualty
choices and possible Retreats. For example, a defending player can assign
a Loss to an eligible Fort to spare an Ally. When Diviciacus fights, the
Aedui check the selected defender's possible Counterattack after the Attack,
with Ambush protection in the assigned Region.

The Belgic, Arverni, and German bots forecast Counterattack from surviving
defenders. The forecast uses the named Leaders' Attack rates, including one
Loss per Warband with Ambiorix. The Arverni check whether the Losses reach a
Legion through its screening pieces. The Roman bot counts a Rampage threat
when the Belgae can legally target the Region and their Hidden Warbands can
affect more pieces than the Romans have Auxilia there.

Recruit and Rally now ask how many Auxilia or Warbands to place. The
quantity menu includes zero where the rules allow it, and includes any
compulsory additions in the displayed total. Choosing zero still selects
and pays for the Region; use **Skip this Region** to omit it. Later choices
use the pieces and Resources left after your earlier placements.

With named Vercingetorix, Rally can place an Ally or Citadel and Warbands
in either order. Choose the first placement, then the second or **Finish
this Region**. The Region costs Resources only once. A Successor does not
have this ability. All three Gallic factions can choose a Citadel at a
City where they have an Ally. Enlist's free German Rally also offers its
legal quantities, including the base game's Warbands after placing an Ally.
When using Diviciacus cooperation, choose the physical Roman/Aedui pieces
before planning the next Region; this preserves the correct remaining pools.
In an interrupted Rally, choose the Special Activity after completing the
first option, then continue from the resulting position. The second option
must still be legal when reached; entering or removing Vercingetorix can
change that permission. You do not pay for the Region twice.

For an Ariovistus Enlist March, choose one German origin, then a destination
and the Warbands in that group by visibility. Use the remaining allowance for
another group, to hide selected Warbands in the origin, or choose **Finish
March**. All groups together can affect up to four Warbands. Each moving
group enters one adjacent Region. Base-game Enlist March moves one group.

During your Sequence-of-Play Command or Event, the menus offer voluntary
removal of your own physical pieces and replacement of your Citadels with
Allies. These choices appear before planning quantities, so an empty
Available pool need not prevent reclaiming a piece for the next placement.
Choose **Finish voluntary removal** to confirm the selected removals, or
leave the position unchanged if none were selected.
Legions return to their track; the permanent Provincia Fort cannot be
removed. A Citadel replacement needs an Available Ally; without one, the
Citadel is simply removed. Lending pieces does not transfer ownership.
Where it matters, menus distinguish moving, already moved, borrowed, and
Event-selected counters from other pieces in the same Region.

With shaded River Commerce (Card 39), choose the one Region that will
Trade. The menu appears after Supply Line declarations and after any
preceding Command, so its income estimates use the actual position. It
includes every legal Region, even one yielding no Resources, and permits
declining Trade. The ordinary Command still takes effect if Trade is
declined or earns nothing. Use `board` or `b` at the choice as usual.

When a Roman bot needs your Supply Line permission for Recruit and its
preceding activity, it asks before making changes. A refusal makes it
reconsider the plan; accepted permissions hold for the Command or Event
you agreed to. You can still inspect the board at the prompt.

For Event grants with human-choice support, the menu lets you plan the permitted action,
request the bot default, or decline where the card allows. Region and piece
limits still apply. Paid grants, such as Winter Campaign and Frumentum,
use their own action and Resource budgets.

Winter Campaign gives its owner up to two paid actions after Harvest.
Select each Battle Region once per Command. You can select it again in
a second Battle Command. On a multi-Region March, choose which pieces
to leave before the remaining group continues from an intermediate Region.

Numidians, Aquitani, unshaded Morasses, shaded Litaviccus and Camulogenus's
Battle step ask the battling player to select a legal Region and opponent.
Where the Event already fixes the Region or defender, that restriction
remains. The engine applies the card's special Battle rules automatically,
including Aquitani's ability to Battle without friendly Forces and revised
Numidians' Auxilia-only participation. Card information, changes and
`board`/`b` inspection remain available before choosing. These Battles must
be carried out when possible.

For unshaded Camulogenus, the Roman player first accepts or declines the
entire March-and-Battle benefit, even when another faction played the Event.
If accepted, choose Atrebates, Carnutes, or Mandubii as the single destination
and select the groups, quantities and routes from their original Regions.
At most four Legions may move in total, alongside any selected Auxilia.
Caesar can accompany a group and permit its third step; the groups cannot
drop off pieces along the way. Only participating Auxilia change visibility.
Troops already at the destination remain available for the following Battle.
Diviciacus cooperation requires its normal separate agreements for March
and Battle. The final Battle cannot be separately declined when possible.

For Litaviccus, the Aedui force participates throughout Battle, including
Counterattack casualties and Reveal. Counters retain their physical owners;
board inspection shows those owners and explains the combined force.

The repaired Event menus listed in the [Event validation report](docs/reviews/event-validation-2026-11-03.md)
enforce their printed quantities and areas. An invalid Event stays pending so you can correct it without losing eligibility; a legal
Event that has no effect is still allowed. Fixed effects occur as far as
possible, while “up to” choices let you select less. If an Event replaces a
piece but the new one is unavailable or cannot legally stack, the original
is still removed.

Some repaired Events assign their choices to Romans or Arverni even when
another faction plays the card. Legiones XIIII et XV, Rhenus Bridge and unshaded Sacking
ask Romans whether to use the effect and which legal sources or targets to use.
Gobannitio asks Arverni about Ally changes, then their free Rally. Its menu
separates “Skip Ally changes; decide Rally” from declining both effects.
Missing or invalid answers stay pending. The same board and card information
remains available while answering another faction's Event.

Shaded Rhenus Bridge (18 and A18) applies the Roman Resource and
Eligibility penalties when a Legion is in or adjacent to Germania. Bots
continue their flowcharts when that requirement fails.

Shaded Sacking requires one of the executor's Citadels in the same Region
as a Roman Legion. It sends one Legion to Fallen and makes Romans Ineligible
through the next card. Unshaded Assembly of Gaul drains eight Resources once
from each chosen Gallic faction when the Carnutes condition is met.

Shaded Assembly of Gaul gives the Carnutes controller one free Command
and up to two free Special Activities. Choose the ordinary plan for zero
or one activity. Choose **Plan a Command with two Special Activities** for
two distinct types, and set each one's timing before, during, or after the
Command. Ambush and Besiege resolve in the selected Battles. The Aedui may
Ambush in one Region of the Command. Choices at the same step resolve in
the order selected.

A free March into or out of Britannia excludes accompanying Special
Abilities. During a standard free March, choose which pieces to leave at a
transit Region before the rest move on. Land of Mist and Mystery separately
grants a Special Ability in Britannia.

Druids asks the Event player to choose one to three distinct Gallic
factions. Aedui, Arverni, then Belgae each resolve their own free Limited
Command if selected and able, with an optional free Special Activity.
Only the Event player receives the card's eligibility benefit.

Shaded German Allegiances (65) lets you choose the exact German Warbands and
Ally in Regions you Control, including visibility and Tribe, and whether
each is removed or replaced. Romans receive Auxilia; Gallic factions receive
their own Warbands. For unshaded Harudes (A29), the Event player chooses the
beneficiary, which then makes its placements. For shaded Usipetes & Tencteri
(A36), Germans make both the placement and Ally-removal choices. Each owner
sees the current board and can use `board` or `b` before answering.

Unshaded Gallia Togata (A5) lets the Event player order multiple affected
owners. Each owner then chooses Home destinations or removal for
all its Cisalpina pieces, including Allies and Settlements. You can split
Warbands among Homes; their Hidden/Revealed/Scouted states stay unchanged.
Allies need legal empty Tribe spaces. German Settlements create additional
Homes, but Cisalpina itself is excluded. Later owners see earlier moves;
game-run Arverni evacuate automatically. Use `board` or `b` at each choice.

Rampage lets the Belgae choose how many Hidden Warbands to Reveal in each
selected Region. Choose one through the number of eligible enemy pieces and
Hidden Belgic Warbands currently available; there is no two-Warband cap.
Only that many flip, leaving the others Hidden. Skip the Region to decline
Rampage there. Quantity is checked again at execution if the Command changes
the available force. NPC Belgae use all able Warbands, while preserving the
last enemy piece before Battle. The target chooses the exact affected pieces
and, for each, removal or Retreat. All pieces that Retreat share one selected
legal destination. Removed Legions go to Fallen without a die roll. The menus
show each piece's visibility and support `b` or `board` inspection. A target
without a legal refuge can still choose which pieces to remove. Arverni in
Ariovistus are removed automatically. If a later Region pauses, saving and
resuming retains the earlier accepted victim choice.

Intimidate now lets you choose the exact Allied Tribe to remove, including
after Raid and through A45. Later choices cannot reuse the selected disc,
and a City's Citadel is not offered as an Ally. Assistant plans name the
Tribe with `target_tribe`; a missing or invalid choice stays pending.

Dread (A22), shaded, lets ordinary Intimidate Reveal up to three Hidden
Warbands, removing one piece per Warband. After Raid with Ariovistus, the menu
shows how many removals the actual Raiders support and whether you can
Reveal one additional Hidden Warband for one extra removal. Three actual
Raiders can supply all three removals without another Reveal. This free
effect does not spend the accompanying Special Activity; a separate normal
Intimidate must use Hidden Warbands still available. Dread's unshaded side
protects Romans from Intimidate removals and from Intimidated markers
blocking Recruit; other Recruit restrictions remain.

Vosegus (A21) and Sabis (A57) let you choose the first Battle's Region and
defender, then decide whether to Battle again there against a currently
available defender. The first Battle forbids Retreat; the second uses normal
Retreat rules. Gaius Valerius Procillus (A19), shaded, lets the Event player choose which
whole Roman force Marches and its adjacent destination with Germans.
Unshaded Procillus uses the named Caesar for its Ally replacement range.
It removes a selected Ally if a Roman Ally is unavailable or cannot stack
there. The Roman bot replaces or removes up to three eligible Allies.
Harudes (A29) lets the Event player choose how the newly placed German
Warbands Raid. Bellovaci (A69) lets that player choose the Ambush defender;
only surviving newly placed Warbands receive the printed extra Losses.

For Morbihan (A20) and Aduatuci (A58), the Roman player decides whether to
accept the complete benefit, even when someone else played the card. A20's
Arverni removals happen only after acceptance. Each following Battle or
Seize choice uses the resulting board. Seize lets you choose exact Tribes,
including Forage without Dispersal; neither card allows enemy Rally, and
A58 also prevents Harassment. Required choices remain pending if a bot
default cannot perform a legal action. A refused troop loan lets you replan.
Use `board` or `b` at these menus to inspect the current position.

Gallic Shouts (35 shaded) and Celtic Rites (46 shaded) let the Event player
choose a Gallic beneficiary. That player makes its own Command choices.
Gallic Shouts also lets the beneficiary put its full and Limited Commands
in either order; both are free, without Battle or a Special Activity.
Celtic Rites permits Battle but no Special Activity, and keeps the original
Event player Eligible. Required actions cannot be declined when possible.
Unshaded Celtic Rites requires at least one Gallic target. Each selected
faction loses three Resources and is Ineligible through the next card.
The ordinary March menu's pending hide-without-movement limitation also
affects these grants.

Under [PR-10](docs/provisional-rulings.md#pr-10), automatic Arverni receiving
an Event Command in Ariovistus act only while At War. They take the first
possible permitted Command in Rally, March, Raid, Battle order, retaining
inherent Ambush if Battle is allowed. They receive no human decision prompt.
This project ruling is provisional and subject to official correction.

Arduenna (67) lets the Event player select Romans or a Gallic faction;
expansion Arduenna (A67) instead permits any beneficiary other than Arverni.
That player may accept or decline the complete sequence. After accepting,
choose a March into either or both Nervii and Treveri, then a non-March
Command in either or both Regions, before the final Hide step. Each action
is required when possible. You can select
the moving groups and legal routes, including split groups and transit
dropoffs; pieces that arrive cannot move again from another selected origin.
Scouted pieces that moved lose their marker during March and can Hide at
the end; Scouted residents lose their marker at the end and stay Revealed.

Oppida (28) first offers Subdued Cities outside Roman Control for Gallic
Ally placements. Then choose which City Allies to upgrade with Available
Citadels of their own factions, including Allies placed during the first
step. The menus show City names and recalculate the options after each
placement, upgrade, or voluntary removal. Bots also use the board after
their own Ally placements to choose City upgrades.

Remi Influence (68 shaded) asks the Gallic faction allied with Remi whether
to accept and which City to use: Alesia or Cenabum. That faction receives
the Citadel and four Warbands as available, even if another player played
the Event. Only the chosen City's Ally, Citadel and status are cleared;
other forces in its Region remain. Use `board` or `b` at these menus to
inspect the current position before choosing.

When unshaded Remi Influence applies, select one or two eligible Allied
Tribes for Roman replacement. Shaded Siege of Bibrax lets you select up
to five exact Roman or Aedui pieces in Atrebates, including the named Tribe
for each Ally. You can finish with zero removals at Bibrax.

The unshaded “remove all” effects of Ariovistus's Wife (A25), Divico (A26),
Orgetorix (A30) and Galba (A56) include Scouted Warbands. Printed restrictions
on Regions, factions and Leaders still apply.
Shaded Divico places up to twelve Available Arverni Warbands in Aedui and
Sequani. German bots divide the placement when needed to keep German Control
and pass over the Event if neither Region can take any.

A Citadel placed by shaded Orgetorix allies its City Tribe to the Arverni.
The Event's stacking exception permits an Arverni Citadel at Bibracte.
After clearing the two Regions, place nine Arverni pieces as far as
possible. Shaded Galba places its four Warbands and two Allies as far as
possible before gaining Resources. Shaded Kinship requires the four
Warband and two Ally replacements as far as the chosen source permits.
The placement and replacement menus show each legal choice after the
preceding steps. Abatis requires a Region with your Warband when one exists.
Hidden, Revealed and Scouted Warbands all qualify.

Shaded Land of Mist and Mystery (57) requires the executor to remove one
Ally or Dispersed marker in Britannia when a target exists. The terminal
then shows the Gallic Ally choices on the resulting board. Place one if
possible, followed by zero to four Available Warbands. The Ally and
Warbands may belong to different Gallic factions.

Shaded Surus lets the Event executor choose up to four Aedui Warbands
by visibility in Treveri or one adjacent Region. Zero is allowed. A
selected Aedui Warband is still removed if its German replacement is
unavailable. Only surviving newly placed Germans can take the free
March, Raid, or Battle. A base-game German March can send one group from
each origin to one adjacent Region. You can leave any of its Warbands
behind.

Seize's successful Rally checks resolve their free Rally
choices immediately, before the next roll or Forage.

The Province offers its printed Auxilia or Resources choice, showing the
Available pool and Resource-cap limits. Ambacti asks for its removal choice
after showing the die roll, then lets you select the exact Auxilia by Region
and visibility. Its unshaded menu offers Regions containing Roman pieces;
only the named Caesar increases the placement from four to six.

Chieftains' Council lets the executor select a qualifying Region and at
least two participating player Factions there. Each participant acts in the
card's initiative order, sees the next two face-down cards, and may choose
a free Limited Command anywhere, become Eligible, or decline. The look
skips the already face-up upcoming card. Private prompts name their
recipient; people sharing one terminal must manage who can see that screen.

Winter Uprising records who took the card. After a normal Quarters Phase,
its human holder can activate it or keep it for a later Quarters Phase.
The Gallic War Interlude requires activation. The selected beneficiary
chooses the printed Allies and Warbands within one Region of the marker;
for Arverni, the holder chooses their placements. Menus show the full held
card and allow Warbands to be split among legal Regions. The following
Command is required when possible, with normal Special Activity ordering.

Spring prompts let you choose where an Available Successor returns. Every
legal destination is offered, including empty Home Regions with your printed
Rally or Recruit symbol. Placement is required; Diviciacus has no Successor.
Bots place Leaders with the most of their own pieces and break equal ties
using the game's seeded randomness.

In Pax Gallica, you can place Vercingetorix from the Spring box beginning
the first Spring, or leave him there for later. Placement opportunities
continue between completed operations inside Commands, Events, and Winter,
including other factions' actions. He may enter any playable Region without
using a turn or changing Eligibility. In the Gallic War, this begins in the
first Winter after the Interlude. Each opportunity lets you defer again;
it does not automatically place him. **Use bot placement priorities** is an
explicit placement choice. Planning menus ask for a specific Region instead.

Boii has dedicated menus for its beneficiary, Allied Tribes and troop
placements. The remaining allowance follows each choice across Regions.
Parley offers complete legal meetings, including either direction when the
named Leaders are adjacent. Wailing Women and Nervii appear in the active
capability list on either side, including in older saves that recorded their
unshaded effects only as internal modifiers.

Before your decisions, the display shows the current and upcoming card
texts and changes since your previous decision. Type **`b`** or **`board`**
at a menu or yes/no prompt to inspect the full board, including piece
states, Tribes, markers, available forces, and active capabilities.
Planning displays are labelled as previews; inspecting them does not alter
the live game. For Seize, choose the exact Subdued Tribes to Disperse, or
finish without choosing any to Forage only. You may choose any legal Tribe
even when only one marker remains; a selected Tribe cannot be chosen twice.
Seize planning reserves markers across your ordered Regions and estimates Forage, while
Rally checks and Harassment resolve during execution. Later decisions use
the actual changes, including intervening Leader entry.

Every plan is checked by the rules engine. A Command with no legal effect
leaves your turn pending so you can choose again; a partly legal plan
shows which portions would have no effect before you confirm it. You will
also be consulted for in-battle decisions on other factions' turns:
Retreats, loss order, Supply-Line and Trade agreements, and Harassment.
You declare a Battle Retreat before the Attack, even with no adjacent
destination. After taking Losses, choose one legal destination for the
survivors or remove them. Against Romans you may keep the surviving
Leader and any number of surviving Hidden Warbands in place. The rest move
together or are removed. Any host agreement must come before the Attack.
Non-player Leaders end a Retreat where the most of their own pieces can
join them. Against Romans, non-player Hidden Warbands stay in place.
Non-players forecast their Counterattack using the defenders that would
survive the Attack. A defender can Retreat without an adjacent refuge
when survivors can stay in the Battle Region under the Roman Battle rules.
Shaded Motivation adds a Counterattack Loss when a German piece survives.

When Harassment causes a loss, you can choose an offered soft casualty or a
saving roll, then choose a hard casualty if the roll requires one. The menus
also distinguish piece visibility and specific Allied Tribes when relevant.
On an ordinary March with another hop available, choose exactly which
traveling pieces to leave in the intermediate Region before Harassment.
The menu shows physical owner and visibility and leaves at least one piece
moving. Only the continuing group faces Harassment. If Caesar stays at
the first stop, the rest can still make the second hop. A Leader required
for the next hop stays with the group. Choose **Keep the remaining pieces
moving** to finish the menu.

Pieces that arrived or dropped off at a later origin stay there when that
origin forms its own groups. They still undergo its normal hiding procedure.
If voluntary removal distinguishes them from pieces that can still move,
the menu labels them **Already marched**.

Suborn offers each legal physical owner, piece type, visibility and Allied
Tribe. Choices update the remaining Resources and pieces as you build the
plan; you can undo a choice or cancel. Convictolitavis can permit a second
Region, and unshaded Vergobret permits a fourth piece, including a second
Ally, in each Region.

When Diviciacus permits cooperation, the menus offer Regions in which to
request it. Planning shows the possible combined forces; the other human
Faction agrees or refuses when the action resolves. Commands and eligible
Special Activities have their own selections. Defense also offers an
explicit request. Roman Auxilia and Aedui Warbands keep their physical
owners, and the board identifies their temporary treatment separately.
When selecting a subset or placing pieces, prompts distinguish their
physical owners as well as visibility where relevant.

Roman Build planning permits both a Fort and the legal Ally action in one
Region. Scout planning updates the position after each move, prevents the
same counter moving twice, and offers the arriving Hidden Auxilia for
Reveal. Choose how many Hidden Auxilia to flip in a Region, then choose up to
two Warbands per Auxilia by faction and visibility. One Auxilia can Scout one
Belgic and one Arverni Warband; you can select Revealed targets while leaving
Hidden ones alone. `b`/`board` shows the planning board. Agreed Diviciacus loans
retain their physical owners. Under shaded Vercingetorix's Elite, the Arverni choose the actual
Warbands treated as Legions; casualty choices distinguish those counters.
If Vercingetorix's arrival changes Roman Quarters Supply, the Romans can
revise their remaining Provincia moves and payments after completed adjacent
moves, without repeating those moves.

When saving is enabled, Ctrl-C also saves between decisions on the same
card. Completed faction actions stay completed. If interrupted while
resolving an action or Winter phase, that unfinished action or phase is
restored to its starting board and random-number state and retried on
resume. Gallic War saves retain both the current seats and the original
seats needed for replay after the Interlude.

## The rules

The full rulebook transcriptions ship in `Reference Documents/`
(base chapters 1-8, Ariovistus A-chapters, card texts, non-player
flowcharts), including transcribed errata marked as `[ERRATA ...]` notes.
The implementation follows these supplied references and the rulings
recorded in QUESTIONS.md. That file is a historical decision ledger;
[current status](docs/current-status.md) supersedes older completion claims.
The owner adopted [twelve provisional rulings](docs/provisional-rulings.md),
all subject to possible later correction if an authoritative source is found:

- A30 has no special Belgic instruction; bots use their normal shaded Event procedure.
- For A28, non-player Aedui and Belgae lend only where the executor contributes
  its own participating pieces. Human consent remains your choice.
- Romans retain unused Frumentum funding, subject to the Resource cap.
- German-owned A63 activates at the Interlude, then remains German-owned and
  dormant in the base-game half.
- Ariovistus Harassment follows printed faction order, with Arverni last.
- Winter Harassment uses the last non-Winter card actually played, including
  a card on which everyone passed. The game-run faction remains last.
- Non-player Aedui roll once for Supply permission for a human Roman action,
  covering its Command, accompanying Special Ability and relevant Regions.
  Replanning the same decision does not grant a new roll.
- Ordinary Rally/Recruit placement prerequisites are checked before the
  bonus pieces arrive. Bonuses still apply where the normal troop quantity
  would be zero, and explicit printed exceptions remain.
- A20 casualties follow the required visibility order, then choose an
  original Region at equal odds for each otherwise tied Warband loss.

- Automatic Arverni Event Commands follow PR-10's first-possible phase order
  and actual At War condition, with inherent Ambush for Battle.
- Numeric Arduenna's Arverni bot uses PR-11's conservative Legion-Loss
  prediction, printed NPC Retreat and Vercingetorix Harassment safety;
  actual human choices and dice still resolve normally.
- Shaded Litaviccus's Belgic bot uses PR-12 to maximize predicted Legion
  Losses, accounting for the Roman bot's Retreat rules or a human Roman's
  safer legal standing/Retreat response. Real decisions and dice remain yours.

These are project interpretations, not official errata. The ruling register
explains each source gap and the fallback for older saves without usable
card history.

## Scenarios

| Scenario | Factions | Length |
|---|---|---|
| Pax Gallica? | Ro / Ar / Ae / Be | medium |
| The Great Revolt | Ro / Ar / Ae / Be | medium — the classic |
| Reconquest of Gaul | Ro / Ar / Ae / Be | short |
| Ariovistus | Ro / Ge / Ae / Be | medium (expansion) |
| The Gallic War | both sets | epic two-act (a German seat becomes the Arverni after the Interlude) |

For measured outcomes by scenario, see the [23 October validation
report](docs/reviews/outstanding-fixes-2026-10-23.md). Those seeded bot games
check the implementation; they do not predict results against a human player.

The owner's replacement Diviciacus card photograph resolves a separate
printed-label question: both O38 sides are Capabilities under §5.3. Bots
therefore decline either side in the final year; this does not restrict a
human's Event selection. See the [29 October rules report](docs/reviews/rulings-trade-2026-10-29.md)
for the evidence and the narrower remaining Capability-removal question.

### German Interlude force adjustments

In The Gallic War, the German player chooses which 15 Warbands leave play
from the map and Available. Next, choose eligible Subdued Tribes for German
Allies replacing Settlements under German Control. If Ally discs are
scarce, choose which eligible Regions get them. Each remaining Settlement
converts to three Hidden Warbands, as Available permits.

After conversion, choose at least a quarter of the on-map Allies and a
quarter of the on-map Warbands to return to Available. The menu rounds up
each minimum and unlocks Germania after the selected type's pieces outside
Germania are exhausted. Choose Allies by Tribe and Warbands by Region and
visibility.

Use `b` or `board` to inspect the board while selecting. You can delegate
each choice to the bot. Saving and resuming Winter retains answers you
have already given.

### Belgic Interlude force reduction

The Belgic player chooses at least half of the on-map Allies and half
of the on-map Warbands to return to Available, rounding up each minimum.
Take pieces outside Belgica first for each type. The terminal lists
Allies by Tribe and Warbands by Region and visibility. Use `b` or `board`
during selection or delegate to the bot.

The remaining pieces determine Ambiorix's destination. If multiple
Regions tie, choose among them. Saving at that prompt retains the
accepted Belgic removals when Winter resumes.

### Aedui Interlude force adjustments

After Diviciacus leaves play, choose one eligible Aedui Citadel to replace
with an Ally or remove if no disc is Available. Bibracte goes last. The
terminal resolves a sole eligible target automatically.

Then choose at least half of the on-map Allies and half of the on-map
Warbands to return to Available, rounding up each minimum. Take the
Aedui Region last for each type. The new Ally is eligible for this
reduction. Choose Allies by Tribe and Warbands by Region and visibility.
Use `b` or `board` during either choice. Saving at the reduction prompt
retains the accepted Citadel selection when Winter resumes.

If Bibracte lacks an Aedui Ally or Citadel after the reductions, restore
the Aedui Ally at that City. Any occupant of Bibracte is cleared first.
Other Forces and the Colony circle in the Aedui Region stay in place.

### Arverni Interlude force adjustments

The German player makes the Arverni choices before taking over that seat.
Choose two eligible Arverni Citadels, taking Gergovia last. When only one
Ally disc is Available for two Citadels, the first selected Citadel gets
the disc and the second is removed. A forced selection resolves automatically
when its order has no effect.

Then choose at least half of the Arverni Allies and half of the Arverni
Warbands to return to Available, rounding up. The Arverni Region goes
last for each type. You may choose the Cadurci and Volcae Ally discs early.
Use `b` or `board` to inspect the board, or delegate either choice to the
bot. Saving at the later prompt retains the accepted Citadel choices.

If Gergovia lacks an Arverni Ally or Citadel after the reductions, restore
the Arverni Ally at that City. Other Forces and Tribe circles stay in place.
The reinforcement then brings the Arverni Region up to three Arverni Warbands
as far as the supply permits.

### Roman Interlude force reductions

During Adjust Forces, choose at least half of the on-map Forts outside
Provincia, half of the Roman Allies, and half of the Roman Auxilia to
return to Available. Round up each minimum. Provincia's Fort and all
Legions stay in place during this step. Choose Allies by Tribe and Auxilia
by Region and visibility, taking Provincia last within each type. Use
`b` or `board` to inspect the position, or delegate the reduction to the bot.
The surviving pieces determine where an available Caesar can be placed.

### Interlude Cisalpina relocation

Unless Gallia Togata is active, each faction clears its forces from
Cisalpina. Germans go first, then Belgae, Aedui, Arverni, and Romans. The
German player makes the Arverni choices before the seat changes hands.
Move any offered pieces to legal Home Regions, or remove them. Allies need
an offered Subdued Tribe. You can split groups of the same visibility and
inspect the board with `b` or `board`. The bot default removes the pieces.

### Roman Interlude decisions

In The Gallic War, human Romans choose whether to conduct the Britannia
expedition after Adjust Forces. A conducted expedition reserves exactly three
Legions for the Harvest box and sends the Roman Leader, at least three other
Legions and at least one Auxilia to Britannia. Choose each origin and count,
including the Auxilia's visibility. Larger expedition forces are permitted.
The menus reserve Harvest Legions first so a counter cannot be used twice.
Use `b` or `board` while allocating pieces to inspect the current position.

Before Interlude Spring, Romans can preserve one offered Dispersed or
Dispersed-Gathering marker as it is, or keep none. An interrupted answer pauses
Winter. Saving and resuming retains accepted reductions, relocations, and
expedition choices while awaiting a later decision.

At the Interlude, Britannia's Catuvellauni Tribe enters play and Nori is
retired. Return any remaining Nori Ally to Available. A Colony keeps its
Region and allegiance. If it uses the Catuvellauni name, the engine
distinguishes it from the returning printed Tribe.

The second-half deck uses A38 Vergobret in the slot for card 38. Active
Capabilities stay out of the deck. Gallia Togata and Colony are also held
out while their effects are active. A resumed game continues the deck
already dealt in its save.

### Exact Battle casualties

When absorbing Battle Losses, choose the exact Hidden, Revealed or Scouted
Warband/Auxilia offered in the current tier. Ally discs appear by Tribe name,
with the physical owner's name when the piece is lent to another Battle force.
Choosing a Tribe clears that Tribe's allegiance while preserving other Allies
and any City represented by a surviving Citadel. Hard pieces still use their
normal saving rolls. Use `b` or `board` to inspect the live position.

Each Loss rebuilds the available choices. An interrupted later casualty can
be saved and resumed with earlier accepted choices retained. Existing saved
generic casualty prompts finish under their recorded contract when their board
still matches. New casualty prompts distinguish the physical pieces.
