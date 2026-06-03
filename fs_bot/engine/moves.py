"""Legal-move enumeration and validation for human/LLM (agent) play.

An external driver (e.g. an LLM) uses these to (a) see the legal top-level
Sequence-of-Play actions for a Faction, (b) enumerate the legal building blocks
for a Command plan (which Regions, which targets/Tribes, which Special
Abilities), and (c) VALIDATE a candidate ``player_action`` by dry-running it on
a throwaway copy before committing it to the live game.

A ``player_action`` is the same dict bots/humans emit and ``execute_decision``
consumes::

    {"command": "Battle"|"March"|"Rally"|"Raid"|"Recruit"|"Seize"|"Event",
     "regions": [...], "sa": "No SA"|<Special Ability>, "sa_regions": [...],
     "details": { ...command-specific plan... }}

See fs_bot/cli/human_plan.py for the per-command ``details`` shapes.
"""

import copy

from fs_bot.engine.game_engine import (
    get_first_eligible_options, get_second_eligible_options,
)
from fs_bot.engine.execute import execute_decision
from fs_bot.cli.human_plan import (
    _FACTION_COMMANDS as _FACTION_COMMANDS,
    _faction_special_abilities as faction_special_abilities,
    _regions_with_pieces as regions_with_pieces,
    _battle_regions as battle_regions,
    _enemies_in_region as enemies_in_region,
    _subdued_tribes as subdued_tribes,
)


def legal_sop_actions(state, position="1st_eligible", first_action=None):
    """Legal top-level engine actions for a Faction at this SoP position.

    ``position`` is "1st_eligible" or "2nd_eligible"; for the 2nd Eligible,
    pass the 1st Eligible's chosen ``first_action`` (its engine constant).
    """
    if position == "2nd_eligible":
        return list(get_second_eligible_options(first_action))
    return list(get_first_eligible_options())


def legal_commands(faction):
    """The Command types ``faction`` may choose (Roman/Gallic/German set)."""
    return list(_FACTION_COMMANDS.get(faction, ()))


def validate_player_action(state, faction, player_action):
    """Dry-run a ``player_action`` on a DEEP COPY of state, without touching the
    live game. Returns ``(ok, info)``: ``ok`` is True iff the action executed
    (had a legal effect); ``info`` is the execution result dict, or a reason
    string if it raised. The copy drops any live ``decision_agent`` so dry-run
    validation never re-enters the agent.
    """
    sim = copy.deepcopy(state)
    sim.pop("decision_agent", None)
    try:
        res = execute_decision(sim, faction, {"player_action": player_action})
    except Exception as exc:  # never raise out of a validation probe
        return (False, repr(exc))
    return (bool(res.get("executed")), res)


def preview_player_action(state, faction, player_action):
    """Like validate_player_action, but also returns the resulting state copy so
    a driver can inspect the board the action WOULD produce. Returns
    ``(ok, info, resulting_state)``."""
    sim = copy.deepcopy(state)
    sim.pop("decision_agent", None)
    try:
        res = execute_decision(sim, faction, {"player_action": player_action})
        return (bool(res.get("executed")), res, sim)
    except Exception as exc:
        return (False, repr(exc), sim)
