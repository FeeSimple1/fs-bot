# Playing fs-bot with an AI assistant (ChatGPT / Claude / etc.)

fs-bot implements the supplied rules and non-player flowcharts for GMT's
**Falling Sky: The Gallic Revolt Against Caesar** (2nd Ed.) and its
**Ariovistus** expansion. Gameplay uses the Python 3.10+ standard library,
with no package installation or internet connection required.

See the [documentation index](docs/README.md), [current engineering
status](docs/current-status.md), and [terminal play guide](PLAYING.md).
The status document identifies verified fixes and source questions. The
owner adopted [nine provisional project rulings](docs/provisional-rulings.md),
all subject to possible later correction if an authoritative source is found.
Apply them when playing; they are not official errata. Passing tests is not
a claim of complete rules compliance.

The [human-choice audit](docs/reviews/human-choice-audit-2026-10-29.md) records
open missing prompts, incorrect Event recipients, incomplete physical choices
and validation gaps. A successful plan or absence of a pending request does
not establish that every printed human decision was offered. Consult its
finding register for current scope; the audit changed no engine behavior.

Recruit/Rally plans can specify exact troop `count` values. Use
`rally_plan.steps` to preserve Vercingetorix's two placement orders, and
`placement_owners` to reserve exact Roman/Aedui pieces during agreed
Diviciacus cooperation. The [agent interface](AGENT_INTERFACE.md) defines
the fields, mandatory bonuses, Region limits and remaining interruption gap.

Under shaded River Commerce (39), let the `trade_region` request present
the legal Regions and actual gains after Supply declarations. Choose one
Region, explicitly decline, or explicitly request the default. A missing
answer stays pending. A complete turn plan may instead supply
`details.trade_region`; see the [agent interface](AGENT_INTERFACE.md).

## Quick start (for the assistant)

You are about to PLAY one faction against the built-in bots.

1. Unzip the archive and `cd` into it.
2. Initialise a game (pick a scenario, a seat, and a seed):

       python -m fs_bot.tools.llm_seat init \
           --scenario "The Great Revolt" --seat Arverni --seed 11

   Scenarios: "Pax Gallica?", "The Great Revolt", "Reconquest of
   Gaul", "Ariovistus", "The Gallic War" (two-act epic; a German seat
   becomes the Arverni after the Interlude).
   Seats: Romans, Arverni, Aedui, Belgae (base) / Romans, Germans,
   Aedui, Belgae (Ariovistus).

   `init --card-edition original|second-edition|legacy` selects the five
   optional card versions. In an original scenario, `--diviciacus-option`
   separately selects O38 and the optional Diviciacus Leader rule. Both
   choices persist in saves and replay.

3. Advance the game:

       python -m fs_bot.tools.llm_seat play

   Bots take their turns; whenever your seat has a decision, including a
   reaction during another faction's action, the board and request print.

4. Read the pending request and its stable decision id. Submit a response:

       python -m fs_bot.tools.llm_seat submit --decision-id d000001 \
           --response '{"action":"pass"}'

   Replace `d000001` with the displayed id. Including `--decision-id` rejects
   an outdated submission. The flag is optional; without it, `submit` targets
   whichever decision is currently pending. Submit Pass only when offered.
   `submit` answers the request and continues until the next decision.
   For a Command, the response is an action object like this:

       {"action": "command",
        "player_action": {
           "command": "Rally", "regions": [],
           "sa": "No SA", "sa_regions": [],
           "details": {"rally_plan": {"citadels": [], "allies": [],
                       "warbands": ["Carnutes"],
                       "settlements_before": [],
                       "settlements_after": []}}}}

   Own-turn `action` is one of the printed options: `command`, `command_sa`,
   `limited_command`, `event`, `pass`. Reactions also pause for your answer:

   - Retreat: `{"retreat":true,"region":"Aedui"}` or `{"retreat":false}`.
   - Loss order: a list of the piece entries offered by the request, such as
     `[["Auxilia",null],["Legion",null]]`. Enlisted pieces may include an owner
     as the third entry; copy those entries exactly.
   - Agreement or opting to Harass: `true` or `false`.
   - Harassment loss: `{"choice": option}` using an entry from `options`.
     Absorbing a loss, choosing a hard casualty after a failed roll, selecting
     visibility, and choosing an Allied Tribe are separate requests.
   - Marching pieces: `{"counts":{"Hidden":1,"Revealed":1}}` selects the
     requested total from the offered visibility counts. This example applies
     only when both states are offered and `count` is 2.
   - Diviciacus physical pieces: `{"counts":{"Romans":1,"Aedui":1}}`
     selects owners for an offered placement or March subset of two pieces.
     Copy the owners and limits from `available`; this differs from the
     visibility counts in `march_cohort`. Cooperation requests themselves
     use the boolean agreement response.
   - Kinship (A65): `{"faction":"Belgae","regions":["Nervii"]}` chooses
     an offered attacker and its eligible Battle Regions; consult the request
     before choosing Regions. This Event also permits an explicit decline.
   - Ambacti (16): read the actual `roll`, choose `"roll"` or `"three"` in
     `removal_choice`, and submit `removals` with each offered `region`,
     `piece_state` and positive integer `count`. The total must match that
     choice's `removal_counts`. Saving or retrying does not reroll the die.
   - Council (47): answer `council_selection` with `region` and at least two
     offered `target_factions`. A selected beneficiary then receives
     `council_choice`, including private face-down card information, and can
     answer `{"choice":"eligible"}`, `{"decline":true}`, or a complete free
     Limited Command plan. Keep that private request with its recipient.
   - Winter Uprising (A66): a holder answers `winter_uprising_timing` with
     `{"activate":true}` or `{"activate":false}`. The Interlude forces it
     without that prompt. For `winter_uprising_placement`, provide the
     exact offered Ally total as distinct Tribe names in `allies`, and
     the Warband total as `{"region":name,"count":integer}` entries in
     `warbands`. The following granted Command is required when possible.
   - Quarters: your faction's relocation/payment object (see AGENT_INTERFACE).
   - Leader placement: answer `spring_leader` with `{"region":name}` from
     `legal_regions`. Only requests with `can_defer:true` allow
     `{"defer":true}`. Successor placement is mandatory; boxed Vercingetorix
     may wait for a later offered window. Placement does not spend a turn.
   - Winter Campaign: one Command, one standalone SA, a Command+SA using both
     actions, or `{"decline":true}`. A second single action is requested after
     the first resolves.
   - Raid Intimidate with Ariovistus: `{"targets":[]}` for the marker only,
     `{"decline":true}` to skip, or a `targets` list copying each chosen
     `target_faction`, `target_piece`, and `target_state` from the request.
     Choose at most `max_removals` pieces of one Faction, within their offered
     counts. The Warbands that just Raided provide this free effect; no
     additional Hidden Warbands or Special Ability are spent.

   Reactions accept `{"use_default":true}` only when you explicitly want the
   engine's default choice. Nothing is silently decided for your seat.

5. Continue submitting responses until `*** GAME OVER` prints.

The default game directory is `llm_play`. To maintain separate games, use
`--dir YOUR_DIRECTORY` consistently on `init`, `play`, `submit`, `board`,
and `replay`. The shell examples use POSIX quoting; in PowerShell or another
shell, preserve the response as one valid JSON argument.

To inspect the saved board without advancing play:

    python -m fs_bot.tools.llm_seat board

The board includes current/upcoming card text, piece states, Tribes,
markers, available forces, and active capabilities. `b` is an alias for `board`. During a reaction it shows the live board at
that decision, including any preceding effects within the unfinished action.
Each decision also shows changes since your last decision.

A halt preserves completed actions. An unfinished action is retried from its
starting board and RNG, automatically replaying your already accepted choices;
it does not ask those questions again. Invalid responses remain pending.

The save atomically records the board, accepted input, pending request, and
complete decision history. `queue.json` is an inbox: an unchanged submitted
file is never consumed twice. You may write
`{"decision_id":"d000001","response":{"action":"pass"}}` into it and run
`play`. Original list queues are accepted, but an identical list is treated
as an already imported submission. Use `submit` (or the new decision id) when
making the same choice again. A new submission replaces unconsumed inbox
entries; it cannot change earlier accepted choices inside a pending action.

Replay into a separate empty directory without changing the live game:

    python -m fs_bot.tools.llm_seat replay --output-dir llm_replay

Replay checks every recorded request against its board and verifies the final
checkpoint and RNG. Older saves begin their assistant history when first
upgraded; choices made before that checkpoint cannot be reconstructed.
`init --card-edition legacy|original|second-edition` selects the saved card
profile. The legacy default preserves existing scenario-based behavior.

Human plans may set `sa_timing` to `"before"` or `"after"` to control the
Special Activity's order. See **AGENT_INTERFACE.md** for interrupted
Rally/Recruit/Raid/Seize plans and Battle-modifying Special Activities.

## Where to find the plan formats

- [AGENT_INTERFACE.md](AGENT_INTERFACE.md) — the core `player_action`
  format, callback contract, typed decision responses, Event-specific request
  formats, and links to the current validators and plan builders.
- **`fs_bot/cli/human_plan.py`** — reference implementation that
  builds each shape.
- **`fs_bot/cards/param_schema.py`** — per-card `event_params`
  schemas (call `generate_params` or read `EVENT_PARAM_SCHEMAS`).
- **Reference Documents/** — the transcribed rulebook chapters, card
  reference, and non-player flowcharts, with published errata applied
  inline as `[ERRATA ...]` annotations.

Invalid assistant responses remain pending with an explanation. A Command
with no legal effect can be replanned; a partially executed Command reports
its results and can consume the turn. Check the returned result and use the
preview API described in [AGENT_INTERFACE.md](AGENT_INTERFACE.md) before
submitting a complex plan. A preview cannot supply another human's future
agreement or casualty choices.

## Victory conditions (checked each Winter)

- Romans: Subdued + Dispersed + Roman Allies > 15 (minus Germanic
  Settlements in Ariovistus, > 15 there too).
- Arverni (base): off-map Legions > 6 AND Arverni Allies+Citadels > 8.
- Aedui: Aedui Allies+Citadels exceed each other Faction's total;
  Germanic Settlements count as Germanic Allies in Ariovistus.
- Belgae: total Belgic Control Value + Belgic Allies + Citadels > 15.
- Germans (Ariovistus): Germanic-controlled Germania Regions +
  controlled Settlements > 6.

These summarize threshold checks in Chapter 7/A7. Final-Winter ranking,
Non-player victory priority, and scenario-specific exceptions also apply.
Use the displayed scores and the supplied references for those cases.

## Play observations from earlier revisions

These observations predate the October corrections. They are possible
strategy ideas, not evidence of current win rates or expert human balance.
For current validation and the reports for each revision, see
[current engineering status](docs/current-status.md).

- Roman March priorities can consolidate Legions under threat and leave
  garrisons at origins. Removing Roman Allies can reduce the Roman score.
- Ambush normally prevents Counterattack and removes hard pieces without
  saving rolls; Caesar's exception can restore both (§4.3.3/§4.5.3).
  A defending Fort/Citadel still reduces inflicted Losses.
- Each Gallic Ally you place at a Subdued tribe is also -1 to the
  Roman score. Card 28 (Oppida) can swing Rome by -3 in one action.
- Marching flips Revealed Warbands to Hidden (§3.3.2). Scouted Warbands
  instead lose their Scouted marker and remain Revealed (§4.2.2); that
  distinction affects later Ambush choices.
