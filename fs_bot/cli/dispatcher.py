"""CLI decision_func factory — Phase 6.

Routes each faction's turn to either bot logic (via bot_dispatch) or a
human menu (via menus.prompt_action). Translates the bot's full action
dict into the engine's action constants per §2.3.4 / §2.3.5 and §8.1.2.

The returned action dict carries the engine action plus, when a bot
played, the full bot decision dict under "bot_action" so the caller
can render details.

Reference:
  §2.3.4   Options for Eligible Factions
  §2.3.5   Limited Command (2nd Eligible)
  §8.1.2   NPs receive full Command + SA instead of Limited Command
            (when limitation comes from Sequence of Play)
"""

import sys

from fs_bot.bots.bot_dispatch import dispatch_bot_turn
from fs_bot.engine.game_engine import (
    ACTION_COMMAND, ACTION_COMMAND_SA, ACTION_LIMITED_COMMAND,
    ACTION_EVENT, ACTION_PASS,
)
from fs_bot.cli.menus import prompt_action
from fs_bot.cli.display import format_action


# Bot action.command string constants (all bots use these literal labels)
_BOT_PASS = "Pass"
_BOT_EVENT = "Event"
_BOT_NONE = "None"
# Any of these means "the bot wants a Command of some kind"
_BOT_COMMAND_NAMES = {"Battle", "March", "Rally", "Raid", "Recruit", "Seize"}
# SA "no SA" sentinel — all bots use the literal "No SA"
_BOT_SA_NONE = "No SA"


def _translate_bot_action(bot_action, options):
    """Translate a bot action dict to an engine action constant.

    Rules:
    - command == "Pass"  -> ACTION_PASS
    - command == "Event" -> ACTION_EVENT
    - command == "None"  -> ACTION_PASS (defensive — treat as a Pass)
    - command in {Battle, March, Rally, Raid, Recruit, Seize}:
        - If sa != "No SA"            -> ACTION_COMMAND_SA
        - Else                        -> ACTION_COMMAND
      Then, if the engine's legal options does NOT include the chosen
      constant but DOES include LIMITED_COMMAND, downgrade to
      LIMITED_COMMAND (§2.3.5). This handles the case where the engine
      has already trimmed the menu for a 2nd Eligible whose options
      are {LIMITED_COMMAND, ...}. Per §8.1.2 the NP would normally be
      upgraded back to full Command+SA, but the engine's option list is
      authoritative for what's legal in this position.

    Args:
        bot_action: Dict from a bot module.
        options: List of legal engine action strings.

    Returns:
        The chosen engine action constant.

    Raises:
        ValueError: If translation produces a non-legal action and
            cannot be downgraded.
    """
    cmd = bot_action.get("command", _BOT_NONE)

    if cmd == _BOT_PASS or cmd == _BOT_NONE:
        if ACTION_PASS in options:
            return ACTION_PASS
        # Defensive: if engine doesn't allow Pass somehow, fall through
        raise ValueError(f"Bot chose Pass but it is not legal: {options}")

    if cmd == _BOT_EVENT:
        if ACTION_EVENT in options:
            return ACTION_EVENT
        # Engine forbids Event in this position — fall back to a Command
        if ACTION_COMMAND in options:
            return ACTION_COMMAND
        if ACTION_LIMITED_COMMAND in options:
            return ACTION_LIMITED_COMMAND
        return ACTION_PASS

    # Command of some kind
    if cmd in _BOT_COMMAND_NAMES:
        sa = bot_action.get("sa", _BOT_SA_NONE)
        if sa and sa != _BOT_SA_NONE:
            preferred = ACTION_COMMAND_SA
        else:
            preferred = ACTION_COMMAND
        if preferred in options:
            return preferred
        # 2nd Eligible after 1st played Command-only:
        # only LIMITED_COMMAND and PASS are legal — downgrade.
        if ACTION_LIMITED_COMMAND in options:
            return ACTION_LIMITED_COMMAND
        # Fallback to whatever Command-like option is left
        if ACTION_COMMAND in options:
            return ACTION_COMMAND
        if ACTION_COMMAND_SA in options:
            return ACTION_COMMAND_SA
        if ACTION_PASS in options:
            return ACTION_PASS
        raise ValueError(
            f"Cannot translate bot command {cmd!r} into any of {options}"
        )

    # Unknown command literal — defensive fallback
    if ACTION_PASS in options:
        return ACTION_PASS
    raise ValueError(f"Unknown bot command label: {cmd!r}")


def make_decision_func(faction_modes, stdin=None, stdout=None, *, pause=True):
    """Build the engine decision callback.

    Args:
        faction_modes: Dict {faction: "human"|"bot"}. Factions not in
            this dict are treated as bot. Game-run factions (Germans in
            base, Arverni in Ariovistus) never appear here; the engine
            handles them automatically.
        stdin: Input stream (default sys.stdin).
        stdout: Output stream (default sys.stdout).
        pause: If True and stdin is a TTY, pause after each turn with
            "Press Enter for next...". Skip if not a TTY so automated
            tests don't hang.

    Returns:
        Callable with signature (state, faction, options, position) -> dict
        matching the engine's resolve_card_turn decision_func contract.
    """
    if stdin is None:
        stdin = sys.stdin
    if stdout is None:
        stdout = sys.stdout

    def decision_func(state, faction, options, position):
        mode = faction_modes.get(faction, "bot")

        if mode == "bot":
            # Sync legacy bot key — bots read state["current_card_id"]
            # while the engine writes state["current_card"]. Mirror so
            # bot code sees what the engine sees.
            state["current_card_id"] = state.get("current_card")
            # Mark which slot we're in (bots use this if available)
            state["is_second_eligible"] = (position == "2nd_eligible")
            # Tell the bot whether playing the Event is legal this turn (the
            # bots' event nodes gate on state["can_play_event"]). Without this
            # the flag is never set and bots can NEVER play an Event.
            state["can_play_event"] = (ACTION_EVENT in options)

            bot_action = dispatch_bot_turn(state, faction)
            stdout.write(format_action(bot_action, faction=faction) + "\n")
            stdout.flush()
            engine_action = _translate_bot_action(bot_action, options)
            return {
                "action": engine_action,
                "bot_action": bot_action,
            }

        # Human
        if mode == "human":
            decision = prompt_action(
                state, faction, options, position, stdin, stdout
            )
            return decision

        raise ValueError(f"Unknown faction_modes value for {faction}: {mode!r}")

    # Optional after-turn pause; the engine doesn't expose hooks for this,
    # so we just attach the helpers as attributes for callers that want
    # to use them. The actual pause logic is exercised by app.py.
    decision_func.faction_modes = faction_modes
    decision_func.pause = pause
    decision_func.stdin = stdin
    decision_func.stdout = stdout
    return decision_func


def maybe_pause(decision_func):
    """If pause is enabled and stdin is a TTY, prompt 'Press Enter'.

    Called by the app between cards. Skipped when stdin is not a TTY so
    that piped/tested input doesn't hang.
    """
    if not getattr(decision_func, "pause", False):
        return
    stdin = decision_func.stdin
    stdout = decision_func.stdout
    try:
        is_tty = stdin.isatty()
    except (AttributeError, ValueError):
        is_tty = False
    if not is_tty:
        return
    stdout.write("Press Enter for next card...")
    stdout.flush()
    stdin.readline()
