"""Choose voluntary physical removal/replacement without changing the board."""

from copy import deepcopy

from fs_bot import rules_consts as rc
from fs_bot.cli.menus import prompt_choice
from fs_bot.engine import voluntary_removal as removal


def _label(choice):
    verb = "Replace" if choice["action"] == "downgrade" else "Remove"
    piece = choice.get("leader", choice["piece_type"])
    identity = choice.get("tribe", choice.get("piece_state", ""))
    label = f"{verb} {piece} {identity} in {choice['region']}".replace("  ", " ")
    if "cohort" in choice:
        label += f" ({choice.get('cohort_label', choice['cohort'])})"
    if "loan_kind" in choice:
        label += f" ({choice['loan_kind'].replace('_', ' ')} selected pieces)"
    if choice["action"] == "downgrade":
        label += (" with an Allied Tribe disc" if choice["replacement_available"]
                  else "; no Ally is Available, so the Citadel is removed")
    elif piece == rc.DIVICIACUS:
        label += " (out of play; can return by Event)"
    elif choice["piece_type"] == rc.LEADER:
        label += " (a later return uses the Successor)"
    elif choice["piece_type"] == rc.LEGION:
        label += " (to the Legions track)"
    return f"{label} [up to {choice['max_count']}]"


def collect_removals(state, faction, request, stdin, stdout):
    """Collect an ordered batch, refreshing pools after each proposed choice."""
    trial = deepcopy({key: value for key, value in state.items()
                      if key != "decision_agent"})
    cohorts = deepcopy(request.get("cohorts", []))
    from fs_bot.cli import menus
    from fs_bot.cli.display import format_board
    previous_hook = menus._BOARD_HOOK[0]
    menus.set_board_hook(lambda: stdout.write(
        "\nProposed board after selected removals:\n" + format_board(trial) + "\n"))
    try:
        return _collect_removals(trial, faction, cohorts, stdin, stdout)
    finally:
        menus.set_board_hook(previous_hook)


def _collect_removals(trial, faction, cohorts, stdin, stdout):
    operations = []
    stdout.write(f"\n{faction}: you may remove your own pieces during this action.\n")
    while True:
        choices = removal.options(trial, faction, cohorts=cohorts)
        menu = [("Finish voluntary removal", "done")]
        if not operations:
            menu.append(("Use default (remove no pieces)", "default"))
        menu.extend((_label(choice), choice) for choice in choices)
        selected = prompt_choice(stdin, stdout, "Voluntary removal?", menu)
        if selected in ("done", "default"):
            if operations:
                return {"operations": operations}
            return {"use_default": True} if selected == "default" else {"done": True}
        count = 1
        if selected["max_count"] > 1:
            count = prompt_choice(stdin, stdout, "How many pieces?",
                [(str(n), n) for n in range(1, selected["max_count"] + 1)]
                + [("Cancel this removal", 0)])
        if count == 0:
            continue
        op = removal.operation(selected, count)
        current = removal.make_request(trial, faction, cohorts=cohorts)
        effects = removal.apply_response(trial, current, {"operations": [op]},
                                         cohorts=cohorts)
        cohorts = removal.advance_cohorts(cohorts, effects)
        operations.append(op)
