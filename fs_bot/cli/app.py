"""Top-level CLI orchestrator.

Responsibilities:
  - Argument parsing (--scenario, --seed, --bots, --non-interactive,
    --save, --load, --replay)
  - Optional interactive setup wizard (scenario picker, faction-mode picker)
  - Build initial state via setup_scenario (with an explicit seed, so every
    game is replayable)
  - Mark non_player_factions for bot dispatch; install the CLI reactive
    agent (Retreat / Loss order / Agreements) for human seats
  - Run the game card by card with FULL rules execution
    (play_card(execute=True)), displaying each card's outcome
  - Autosave after every card when --save is given; --load resumes a
    snapshot exactly (rng position included); --replay re-runs a game from
    its logged human decisions and goes interactive when the log ends

Scenario isolation per CLAUDE.md:
  - In Ariovistus scenarios, Arverni is game-run (A6.2) and CANNOT be
    human or bot. Germans CAN be either.
  - In base scenarios, Germans are game-run (§6.2) and CANNOT be human
    or bot. Arverni CAN be either.
"""

import argparse
import random as _random
import sys
from collections import deque

from fs_bot.rules_consts import (
    ROMANS, ARVERNI, AEDUI, BELGAE, GERMANS,
    FACTIONS,
    BASE_SCENARIOS, ARIOVISTUS_SCENARIOS, ALL_SCENARIOS,
)
from fs_bot.state.setup import setup_scenario
from fs_bot.engine.game_engine import (
    get_sop_factions, start_game, play_card,
)
from fs_bot.state import serialize
from fs_bot.cli.reactive import make_cli_reactive
from fs_bot.cli.dispatcher import make_decision_func, maybe_pause
from fs_bot.cli.display import (
    format_state_summary, format_region_table, format_tribes_table,
    format_victory_state, format_action, format_card,
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
            bot_act = info.get("bot_action") or info.get("player_action")
            if bot_act:
                stdout.write(
                    f"  {f}: {action}  | {format_action(bot_act)}\n"
                )
            else:
                stdout.write(f"  {f}: {action}\n")
            ex = info.get("execution")
            if isinstance(ex, dict):
                if not ex.get("executed"):
                    why = ex.get("reason") or "no effect"
                    stdout.write(f"      (did not execute: {why})\n")
                elif ex.get("errors"):
                    stdout.write(f"      ({len(ex['errors'])} sub-action(s) "
                                 f"had no effect)\n")
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
            "Falling Sky bot engine — interactive CLI with full rules "
            "execution, save/resume, and replay."
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
            "(e.g. Romans,Aedui,Belgae). Others become human. "
            "If omitted, the wizard asks per faction."
        ),
    )
    p.add_argument(
        "--save", default=None, metavar="FILE",
        help="Autosave the game to FILE after every card.",
    )
    p.add_argument(
        "--load", default=None, metavar="FILE",
        help="Resume the exact snapshot in FILE (rng position included).",
    )
    p.add_argument(
        "--replay", default=None, metavar="FILE",
        help=(
            "Re-run the game in FILE from its logged human decisions "
            "(rebuilt from scenario+seed); goes interactive when the "
            "log ends."
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
    if args.load and args.replay:
        stdout.write("--load and --replay are mutually exclusive.\n")
        return 2

    log = []
    if args.load or args.replay:
        # Scenario / seed / seats come from the save file.
        state, meta, log = serialize.load_game(args.load or args.replay)
        scenario = meta.get("scenario") or state.get("scenario")
        seed = meta.get("seed")
        faction_modes = meta.get("faction_modes") or {}
        if not faction_modes:
            assignable = get_assignable_factions(scenario)
            faction_modes = {
                f: ("bot" if f in state.get("non_player_factions", set())
                    else "human") for f in assignable}
        if args.replay:
            if seed is None:
                stdout.write("Save has no seed; cannot --replay.\n")
                return 2
            state = setup_scenario(scenario, seed=seed)
    else:
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

        # Explicit seed always, so every game is saveable/replayable.
        seed = (args.seed if args.seed is not None
                else _random.randrange(2 ** 31))
        state = setup_scenario(scenario, seed=seed)

    meta = {"scenario": scenario, "seed": seed,
            "faction_modes": dict(faction_modes)}
    # Non-player factions = bots (the engine uses this for tiebreak;
    # bot_dispatch requires it).
    state["non_player_factions"] = {
        f for f, m in faction_modes.items() if m == "bot"
    }
    humans = [f for f, m in faction_modes.items() if m == "human"]

    # Replay queues: human SoP decisions and reactive responses recorded
    # in the log. Determinism (same scenario+seed+decisions) makes the
    # request sequences line up; any desync abandons replay and goes
    # interactive.
    replay_decisions = deque(
        e for e in log if "reactive" not in e) if args.replay else deque()
    replay_reactive = deque(
        e for e in log if "reactive" in e) if args.replay else deque()
    live_log = list(log)

    # Decision callback (bots via flowcharts, humans via menus), wrapped to
    # feed/record the replay log.
    pause = not args.non_interactive
    base_decision = make_decision_func(
        faction_modes, stdin=stdin, stdout=stdout, pause=pause,
    )

    def decision(state_, faction, options, position):
        if faction_modes.get(faction) == "human" and replay_decisions:
            e = replay_decisions[0]
            if (e.get("faction") == faction
                    and e.get("card") == state_.get("current_card")):
                replay_decisions.popleft()
                stdout.write(f"[replay] {faction}: {e.get('action')}\n")
                d = {"action": e.get("action")}
                if e.get("player_action") is not None:
                    d["player_action"] = e["player_action"]
                return d
            stdout.write("[replay] log desynced from game — going "
                         "interactive\n")
            replay_decisions.clear()
            replay_reactive.clear()
        d = base_decision(state_, faction, options, position)
        if faction_modes.get(faction) == "human":
            entry = {"card": state_.get("current_card"), "faction": faction,
                     "position": position, "action": d.get("action")}
            if d.get("player_action") is not None:
                entry["player_action"] = d["player_action"]
            live_log.append(entry)
        return d

    # Reactive agent (Retreat / Loss order / Agreements) for human seats,
    # wrapped the same way.
    if humans:
        cli_agent = make_cli_reactive(humans, stdin, stdout)

        def agent(state_, faction, request):
            if faction in humans and replay_reactive:
                e = replay_reactive[0]
                if (e.get("faction") == faction
                        and e.get("reactive") == request.get("kind")):
                    replay_reactive.popleft()
                    return serialize.decode(e.get("response"))
                replay_reactive.clear()
                replay_decisions.clear()
            resp = cli_agent(state_, faction, request)
            if faction in humans and resp is not None:
                live_log.append({"reactive": request.get("kind"),
                                 "faction": faction,
                                 "card": state_.get("current_card"),
                                 "response": serialize.encode(resp)})
            return resp

        state["decision_agent"] = agent

    # Initial display
    stdout.write(format_state_summary(state) + "\n")
    stdout.write(format_region_table(state) + "\n")
    stdout.flush()

    # Run the game card by card with full rules execution, displaying and
    # autosaving after every card.
    resumed = bool(args.load) and (state.get("current_card") is not None
                                   or state.get("played_cards"))
    try:
        if not resumed:
            start_game(state)
        results = []
        while state["current_card"] is not None:
            card_result = play_card(state, decision, execute=True)
            results.append(card_result)
            display_card_result(card_result, stdout)
            if args.save:
                serialize.save_game(state, args.save, meta=meta,
                                    log=live_log)
            if card_result["game_over"]:
                break
            maybe_pause(base_decision)
    except (KeyboardInterrupt, EOFError):
        if args.save:
            serialize.save_game(state, args.save, meta=meta, log=live_log)
            stdout.write(f"\nInterrupted — game saved to {args.save} "
                         f"(resume with --load).\n")
        else:
            stdout.write("\nInterrupted.\n")
        return 0
    except Exception as exc:
        if args.save:
            serialize.save_game(state, args.save, meta=meta, log=live_log)
        stdout.write(f"\nGame stopped with exception: {type(exc).__name__}: "
                     f"{exc}\n")
        return 1

    stdout.write("\n" + format_state_summary(state) + "\n")
    stdout.write(format_victory_state(state) + "\n")
    stdout.write(f"\nGame ended. Cards played: "
                 f"{len(state['played_cards'])}.  Winters: "
                 f"{state['winter_count']}.\n")
    stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
