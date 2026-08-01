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

   Bots take their turns; when it is YOUR turn the board prints and
   the program halts, showing your legal options.

4. Decide, then write `llm_play/queue.json` with a LIST of decisions
   and run `play` again. One decision looks like:

       [{"action": "command_sa",
         "player_action": {
           "command": "Rally", "regions": [],
           "sa": "Ambush", "sa_regions": ["Carnutes"],
           "details": {"rally_plan": {"citadels": [], "allies": [],
                       "warbands": ["Carnutes"],
                       "settlements_before": [],
                       "settlements_after": []}}}}]

   `action` is one of the printed options: `command`, `command_sa`,
   `limited_command`, `event`, `pass`.

5. Repeat step 3-4 until `*** GAME OVER` prints.

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
