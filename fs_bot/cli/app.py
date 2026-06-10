"""Top-level CLI orchestrator — Phase 6.

Responsibilities:
  - Argument parsing (--scenario, --seed, --bots, --non-interactive)
  - Optional interactive setup wizard (scenario picker, faction-mode picker)
  - Build initial state via setup_scenario
  - Mark non_player_factions for bot dispatch
  - Run the game via fs_bot.engine.game_engine.run_game
  - Display each card's result and the final victory

Scenario isolation per CLAUDE.md:
  - In Ariovistus scenarios, Arverni is game-run (A6.2) and CANNOT be
    human or bot. Germans CAN be either.
  - In base scenarios, Germans are game-run (§6.2) and CANNOT be human
    or bot. Arverni CAN be either.

The CLI runs the full rules engine: each faction's decision is both
recorded and EXECUTED on the board (run_game(..., execute=True)), so
the displayed state, victory track, and final outcome reflect real
play.
"""

import argparse
import sys

from fs_bot.rules_consts import (
    ROMANS, ARVERNI, AEDUI, BELGAE, GERMANS,
    ARIOVISTUS_SCENARIOS, ALL_SCENARIOS,
    SCENARIO_GALLIC_WAR,
)
from fs_bot.state.setup import setup_scenario
from fs_bot.engine.game_engine import (
    run_game,
)
from fs_bot.cli.dispatcher import make_decision_func, maybe_pause
from fs_bot.cli.display import (
    format_state_summary, format_region_table, format_victory_state, format_action, format_card,
)
from fs_bot.cli.menus import prompt_choice


# ============================================================================
# FACTION/SCENARIO ELIGIBILITY
# ============================================================================

def get_assignable_factions(scenario):
    """Return the factions that may be assigned human/bot in a scenario.

    Excludes game-run factions:
      - Base scenarios: Germans excluded (§6.2 game-run)
      - Ariovistus scenarios: Arverni excluded (A6.2 game-run)

    Returns:
        Tuple of faction constants in SoP order.
    """
    if scenario in ARIOVISTUS_SCENARIOS:
        # Romans, Germans, Aedui, Belgae — A2.0
        return (ROMANS, GERMANS, AEDUI, BELGAE)
    # Base: Romans, Arverni, Aedui, Belgae — §2.3
    return (ROMANS, ARVERNI, AEDUI, BELGAE)


# ============================================================================
# SETUP WIZARD
# ============================================================================

def setup_wizard(stdin, stdout, *, preset_scenario=None,
                 preset_faction_modes=None):
    """Interactive scenario and faction-mode picker.

    If preset_scenario is provided, skip the scenario question. If
    preset_faction_modes is provided, skip the faction-mode questions
    (but still validate them against the chosen scenario).

    Returns:
        (scenario, faction_modes) tuple. faction_modes is a dict
        {faction: "human"|"bot"} containing exactly the assignable
        factions for the chosen scenario.
    """
    # Scenario
    if preset_scenario is not None:
        if preset_scenario not in ALL_SCENARIOS:
            raise ValueError(f"Unknown scenario: {preset_scenario!r}")
        scenario = preset_scenario
    else:
        choices = [(s, s) for s in ALL_SCENARIOS]
        scenario = prompt_choice(
            stdin, stdout, "Select scenario:", choices
        )

    # Faction modes
    assignable = get_assignable_factions(scenario)
    if preset_faction_modes is not None:
        faction_modes = {}
        for f in assignable:
            mode = preset_faction_modes.get(f, "bot")
            if mode not in ("human", "bot"):
                raise ValueError(f"Bad mode for {f}: {mode!r}")
            faction_modes[f] = mode
    else:
        faction_modes = {}
        mode_choices = [("Human", "human"), ("Bot", "bot")]
        for f in assignable:
            mode = prompt_choice(
                stdin, stdout, f"Mode for {f}:", mode_choices
            )
            faction_modes[f] = mode

    return scenario, faction_modes


# ============================================================================
# CARD RESULT DISPLAY
# ============================================================================

def display_card_result(card_result, stdout):
    """Print what happened on a card.

    Reports: card id, turn type (event/winter), passes, actions taken,
    Frost flag, Arverni Phase (if any), Winter result, game-over.
    """
    stdout.write("\n")
    card = card_result.get("card")
    stdout.write(f"=== Card {card} resolved ===\n")
    if card_result.get("type") == "winter":
        wr = card_result.get("winter_result", {})
        is_final = wr.get("is_final", False)
        stdout.write(
            f"  Winter round ({'FINAL' if is_final else 'normal'})\n"
        )
        phases = wr.get("winter_result", {}).get("phases", {})
        victory = phases.get("victory", {}) if isinstance(phases, dict) else {}
        if victory.get("game_over"):
            stdout.write(f"  Victory phase: GAME OVER -- "
                         f"winner {victory.get('winner')}\n")
    else:
        turn = card_result.get("turn_result", {})
        if turn.get("frost"):
            stdout.write("  Frost applies (§2.3.8)\n")
        if turn.get("arverni_phase"):
            stdout.write("  Arverni Phase ran (A2.3.9)\n")
        actions = turn.get("actions_taken", {})
        passes = turn.get("passes", [])
        for f, info in actions.items():
            action = info.get("action", "?")
            bot_act = info.get("bot_action")
            if bot_act:
                stdout.write(
                    f"  {f}: {action}  | {format_action(bot_act)}\n"
                )
            else:
                stdout.write(f"  {f}: {action}\n")
        if not actions:
            stdout.write(f"  (all factions passed)  passes={passes}\n")
    if card_result.get("game_over"):
        stdout.write("  *** GAME OVER ***\n")
    stdout.flush()


# ============================================================================
# ARG PARSING
# ============================================================================

def _parse_args(argv):
    p = argparse.ArgumentParser(
        prog="fs_bot",
        description=(
            "Falling Sky bot engine — interactive CLI. Runs the full "
            "rules engine: decisions are executed on the board."
        ),
    )
    p.add_argument(
        "--scenario",
        choices=list(ALL_SCENARIOS),
        default=None,
        help="Scenario to play. If omitted, the setup wizard asks.",
    )
    p.add_argument(
        "--seed", type=int, default=None,
        help="RNG seed for deterministic replay.",
    )
    p.add_argument(
        "--bots", default=None,
        help=(
            "Comma-separated faction names to be bot-controlled "
            "(e.g. Romans,Aedui,Belgae), or 'all'. Others become human. "
            "If omitted, the wizard asks per faction."
        ),
    )
    p.add_argument(
        "--non-interactive", action="store_true",
        help=(
            "Bot-only mode for testing: all assignable factions are bots, "
            "no setup wizard prompts, no inter-card pause."
        ),
    )
    return p.parse_args(argv)


def _parse_bots_arg(bots_arg, assignable):
    """Parse the comma-separated --bots argument into a faction_modes dict."""
    modes = {f: "human" for f in assignable}
    if bots_arg is None:
        return None
    bot_names = [s.strip() for s in bots_arg.split(",") if s.strip()]
    if any(n.lower() == "all" for n in bot_names):
        return {f: "bot" for f in assignable}
    valid_names = {f.lower(): f for f in assignable}
    chosen_bots = set()
    for n in bot_names:
        key = n.lower()
        if key not in valid_names:
            raise ValueError(
                f"Unknown or non-assignable faction in --bots: {n!r}. "
                f"Assignable: {list(assignable)}"
            )
        chosen_bots.add(valid_names[key])
    for f in assignable:
        modes[f] = "bot" if f in chosen_bots else "human"
    return modes


# ============================================================================
# MAIN
# ============================================================================

def main(argv=None, stdin=None, stdout=None):
    """Run the CLI.

    Args:
        argv: Optional argv list (None means sys.argv[1:]).
        stdin/stdout: Streams (default sys.stdin/sys.stdout).

    Returns:
        Exit code (int).
    """
    if stdin is None:
        stdin = sys.stdin
    if stdout is None:
        stdout = sys.stdout

    args = _parse_args(argv)

    # Determine faction_modes — preset from --bots if scenario known
    preset_modes = None
    if args.scenario is not None and args.bots is not None:
        assignable = get_assignable_factions(args.scenario)
        preset_modes = _parse_bots_arg(args.bots, assignable)
    elif args.non_interactive:
        # --non-interactive without --bots: scenario must be set too,
        # else we fall through to the wizard which will fail on stdin.
        if args.scenario is not None:
            assignable = get_assignable_factions(args.scenario)
            preset_modes = {f: "bot" for f in assignable}

    # Either run the wizard or use preset
    if args.scenario is not None and preset_modes is not None:
        scenario = args.scenario
        faction_modes = preset_modes
    else:
        scenario, faction_modes = setup_wizard(
            stdin, stdout,
            preset_scenario=args.scenario,
            preset_faction_modes=preset_modes,
        )

    # Gallic War: after the Interlude the German seat plays the Arverni
    # (A Scenario: The Gallic War, Second Half). Mirror the German
    # human/bot assignment onto the Arverni up front so the decision
    # callback handles both halves.
    if scenario == SCENARIO_GALLIC_WAR and GERMANS in faction_modes:
        faction_modes.setdefault(ARVERNI, faction_modes[GERMANS])

    # Build state
    state = setup_scenario(scenario, seed=args.seed)
    # Non-player factions = bots (the engine uses this for tiebreak;
    # bot_dispatch requires it).
    state["non_player_factions"] = {
        f for f, m in faction_modes.items() if m == "bot"
    }

    # Decision callback
    pause = not args.non_interactive
    decision = make_decision_func(
        faction_modes, stdin=stdin, stdout=stdout, pause=pause,
    )

    # Initial display
    stdout.write(format_state_summary(state) + "\n")
    stdout.write(format_region_table(state) + "\n")
    stdout.flush()

    # Run game — engine calls our decision_func for every faction turn.
    # Wrap the decision callback so we can pause and show the card header
    # whenever a new card comes up (run_game exposes no per-card hook).
    last_card = [None]

    def per_card_decision(st, faction, options, position):
        card = st.get("current_card")
        if card != last_card[0]:
            if last_card[0] is not None:
                maybe_pause(decision)
            last_card[0] = card
            stdout.write("\n" + format_card(card, st["scenario"]) + "\n")
            stdout.flush()
        return decision(st, faction, options, position)

    try:
        result = run_game(state, per_card_decision, execute=True)
    except Exception as exc:
        stdout.write(f"\nGame stopped with exception: {type(exc).__name__}: "
                     f"{exc}\n")
        return 1

    stdout.write("\n" + format_state_summary(state) + "\n")
    stdout.write(format_victory_state(state) + "\n")
    stdout.write(f"\nGame ended. Cards played: "
                 f"{result['total_cards_played']}.  Winters: "
                 f"{result['winter_count']}.\n")
    stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
