"""Human player menu UI — Phase 6.

Provides numeric-menu helpers that only present legal options and
hard-block illegal input. All prompts accept stdin/stdout to support
test injection via io.StringIO.

The action prompt is the hard-block layer for "no illegal moves":
- options is the engine's legal-actions list — only those are shown
- non-numeric input is rejected and re-prompts
- out-of-range numeric input is rejected and re-prompts

Reference:
  §2.3.4  Options for Eligible Factions
  §2.3.5  Limited Command
"""

import sys

from fs_bot.rules_consts import (
    FIRST_ELIGIBLE, SECOND_ELIGIBLE,
)
from fs_bot.engine.game_engine import (
    ACTION_COMMAND, ACTION_COMMAND_SA, ACTION_LIMITED_COMMAND,
    ACTION_EVENT, ACTION_PASS,
)
from fs_bot.cards.card_data import get_card


# Human-readable labels for engine action constants — §2.3.4
ACTION_LABELS = {
    ACTION_COMMAND: "Command (no Special Ability)",
    ACTION_COMMAND_SA: "Command + Special Ability",
    ACTION_LIMITED_COMMAND: "Limited Command (one region, no SA)",
    ACTION_EVENT: "Event",
    ACTION_PASS: "Pass",
}


def _read_line(stdin, prompt, stdout):
    """Print prompt to stdout, read a line from stdin, strip newline."""
    stdout.write(prompt)
    stdout.flush()
    line = stdin.readline()
    if line == "":
        # EOF — treat as empty input (will cause re-prompt or error)
        return None
    return line.rstrip("\r\n")


def prompt_choice(stdin, stdout, prompt, choices):
    """Show a numeric menu and return the value for the chosen option.

    Args:
        stdin: Input stream.
        stdout: Output stream.
        prompt: Header line.
        choices: List of (label, value) tuples.

    Returns:
        The value associated with the chosen option.

    Hard-blocks invalid input: out-of-range numbers and non-numeric
    input both re-prompt.
    """
    if not choices:
        raise ValueError("prompt_choice requires at least one choice")

    stdout.write(prompt + "\n")
    for i, (label, _value) in enumerate(choices, 1):
        stdout.write(f"  {i}) {label}\n")
    stdout.flush()

    n = len(choices)
    while True:
        line = _read_line(stdin, f"Enter 1-{n}: ", stdout)
        if line is None:
            raise EOFError("stdin closed during prompt_choice")
        line = line.strip()
        if not line:
            stdout.write(f"Please enter 1-{n}\n")
            continue
        try:
            idx = int(line)
        except ValueError:
            stdout.write(f"Please enter 1-{n} (got {line!r})\n")
            continue
        if idx < 1 or idx > n:
            stdout.write(f"Please enter 1-{n} (got {idx})\n")
            continue
        return choices[idx - 1][1]


def prompt_yes_no(stdin, stdout, prompt, default=None):
    """Yes/no prompt. Re-prompts on bad input.

    Args:
        stdin/stdout: Streams.
        prompt: Question text.
        default: True/False/None — default if user just presses Enter.

    Returns:
        bool.
    """
    suffix = ""
    if default is True:
        suffix = " [Y/n]: "
    elif default is False:
        suffix = " [y/N]: "
    else:
        suffix = " [y/n]: "
    while True:
        line = _read_line(stdin, prompt + suffix, stdout)
        if line is None:
            raise EOFError("stdin closed during prompt_yes_no")
        line = line.strip().lower()
        if not line:
            if default is not None:
                return default
            stdout.write("Please answer y or n\n")
            continue
        if line in ("y", "yes"):
            return True
        if line in ("n", "no"):
            return False
        stdout.write(f"Please answer y or n (got {line!r})\n")


def prompt_action(state, faction, options, position, stdin, stdout):
    """Show a legal-options menu and collect the player's action choice.

    PRESENT ONLY THE OPTIONS PROVIDED — this is the hard-block illegal
    moves layer. Bad input (out-of-range, non-numeric) is rejected and
    re-prompts.

    Args:
        state: Game state dict.
        faction: Faction the player controls.
        options: List of legal engine action strings (from
            get_first_eligible_options / get_second_eligible_options).
        position: "1st_eligible" or "2nd_eligible".
        stdin/stdout: Streams.

    Returns:
        Dict with "action" set to the chosen engine action constant. For a
        non-Pass action, also "player_action": the full plan (Command/Event)
        the engine executes via execute_decision, so a human turn resolves
        through the same machinery as a bot turn.
    """
    scenario = state["scenario"]
    card_id = state.get("current_card")
    card_title = ""
    if card_id is not None:
        try:
            card_title = f" ({get_card(card_id, scenario).title})"
        except KeyError:
            pass

    pos_label = FIRST_ELIGIBLE if position == "1st_eligible" else SECOND_ELIGIBLE
    header = (
        f"\nYou are {faction}, the {pos_label} on card {card_id}"
        f"{card_title}."
    )
    stdout.write(header + "\n")

    choices = [
        (ACTION_LABELS.get(opt, opt), opt) for opt in options
    ]
    chosen = prompt_choice(stdin, stdout, "Choose your action:", choices)
    decision = {"action": chosen}
    if chosen != ACTION_PASS:
        # Collect the concrete plan so the engine can execute the human turn.
        # If input ends before the plan is complete (piped/scripted input),
        # fall back to the action type alone — execute_decision then reports
        # "no executable plan" rather than crashing the turn.
        from fs_bot.cli.human_plan import collect_player_action
        try:
            player_action = collect_player_action(
                state, faction, chosen, stdin, stdout)
        except EOFError:
            player_action = None
        if player_action is not None:
            decision["player_action"] = player_action
    return decision
