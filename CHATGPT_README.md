# Playing fs-bot with an AI assistant (ChatGPT / Claude / etc.)

fs-bot is a rules-faithful Python engine for GMT's **Falling Sky: The
Gallic Revolt Against Caesar** (2nd Ed.) and its **Ariovistus**
expansion, with full non-player bots for every faction. It is pure
Python 3 standard library — no pip installs, no internet — so it runs
inside a sandboxed code-interpreter environment.

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

3. Advance the game:

       python -m fs_bot.tools.llm_seat play

   Bots take their turns; whenever your seat has a decision, including a
   reaction during another faction's action, the board and request print.

4. Read the pending request and its stable decision id. Submit a response:

       python -m fs_bot.tools.llm_seat submit --response '{"action":"pass"}'

   `submit` answers the current request and continues until the next decision.
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
   - Agreement or harassment: `true` or `false`.
   - Quarters: your faction's relocation/payment object (see AGENT_INTERFACE).
   - Winter Campaign: one Command, one standalone SA, a Command+SA using both
     actions, or `{"decline":true}`. A second single action is requested after
     the first resolves.

   Reactions accept `{"use_default":true}` only when you explicitly want the
   engine's default choice. Nothing is silently decided for your seat.

5. Continue submitting responses until `*** GAME OVER` prints.

To inspect the saved board without advancing play:

    python -m fs_bot.tools.llm_seat board

The board includes current/upcoming card text, piece states, Tribes,
markers, and available forces. During a reaction it shows the live board at
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

- **AGENT_INTERFACE.md** — the full `player_action` schema: every
  command's `details` shape (battle_plan, rally_plan, raid_plan,
  recruit_plan, March `origins`/`destinations`/`routes`/`groups`/
  `extra_groups`, Roman `build_plan`/`scout_plan`, suborn/entreat/
  rampage/enlist plans, Event `card_id`/`text_preference`/
  `event_params`, and optional `transfers`).
- **`fs_bot/cli/human_plan.py`** — reference implementation that
  builds each shape.
- **`fs_bot/cards/param_schema.py`** — per-card `event_params`
  schemas (call `generate_params` or read `EVENT_PARAM_SCHEMAS`).
- **Reference Documents/** — the transcribed rulebook chapters, card
  reference, and non-player flowcharts, with published errata applied
  inline as `[ERRATA ...]` annotations.

Illegal plans are REFUSED cleanly with a reason (the engine
validates everything); re-read the reason, fix the plan, run again.
A refused Command still consumes your turn only if part executed, so
prefer checking region adjacency and costs before committing.

## Victory conditions (checked each Winter)

- Romans: Subdued + Dispersed + Roman Allies > 15 (minus Germanic
  Settlements in Ariovistus, > 15 there too).
- Arverni (base): off-map Legions > 6 AND Arverni Allies+Citadels > 8.
- Aedui: Aedui Allies+Citadels exceed every other Faction's.
- Belgae (base): Belgic Control + Belgic AND Germanic Allies/
  Citadels/Control > 15.
- Germans (Ariovistus): Germanic-controlled Germania Regions +
  controlled Settlements > 6.

## Tips learned from play (all five seats have been played)

- The Roman bot consolidates Legions the moment you threaten them and
  garrisons origins when it Marches; you rarely get the battle you
  want. Kill its ALLIES to drag its score down.
- Ambush prevents the Counterattack, but a defending Fort/Citadel
  still gives Legions their 1-3 removal roll (§4.3.3) and halves
  Losses.
- Each Gallic Ally you place at a Subdued tribe is also -1 to the
  Roman score. Card 28 (Oppida) can swing Rome by -3 in one action.
- Marching flips your Revealed Warbands to Hidden (§3.3.2); Hidden
  count drives Ambush legality and Ambush Losses.
