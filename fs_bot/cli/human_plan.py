"""Human player plan collection — Phase 6 (mixed human/bot games).

After a human picks an action TYPE (menus.prompt_action), this module collects
the concrete plan (which Command, Regions, targets, Special Activity, Event
side) and returns it as a ``player_action`` dict in the same shape bot
flowcharts emit. ``engine.execute.execute_decision`` then applies it through the
same machinery used for bot turns, so a human turn resolves identically.

Design: present ONLY legal choices (a Region must hold the acting Faction's
pieces, a Battle needs an enemy present, etc.). This is the human-side analogue
of the "no illegal moves" hard-block in menus.prompt_action — the executors and
mechanic functions remain the final validators.

The plan shapes mirror what each command executor consumes (engine/execute.py):
Seize ``regions`` + ``details['disperse_regions']``; Raid ``details['raid_plan']``;
Rally ``details['rally_plan']``; Battle ``details['battle_plan']``; Recruit
``details['recruit_plan']``; March ``details['origins']`` + ``['destinations']``.
"""

from fs_bot.rules_consts import (
    ROMAN_COMMANDS, GALLIC_COMMANDS, GERMAN_COMMANDS,
    ROMAN_SPECIAL_ABILITIES, AEDUI_SPECIAL_ABILITIES, BELGAE_SPECIAL_ABILITIES,
    ARVERNI_SPECIAL_ABILITIES_BASE, ARVERNI_SPECIAL_ABILITIES_ARIOVISTUS,
    GERMAN_SPECIAL_ABILITIES_BASE, GERMAN_SPECIAL_ABILITIES_ARIOVISTUS,
    ROMANS, ARVERNI, AEDUI, BELGAE, GERMANS,
    FACTIONS, LEGION, AUXILIA, WARBAND,
    EVENT_SHADED, EVENT_UNSHADED, ARIOVISTUS_SCENARIOS,
)
from fs_bot.engine.game_engine import (
    ACTION_COMMAND, ACTION_COMMAND_SA, ACTION_LIMITED_COMMAND,
    ACTION_EVENT, ACTION_PASS,
)
from fs_bot.map.map_data import get_playable_regions, get_adjacent
from fs_bot.board.pieces import count_pieces, get_leader_in_region
from fs_bot.cli.menus import prompt_choice, prompt_yes_no

_SA_NONE = "No SA"

_FACTION_COMMANDS = {
    ROMANS: ROMAN_COMMANDS,
    ARVERNI: GALLIC_COMMANDS, AEDUI: GALLIC_COMMANDS, BELGAE: GALLIC_COMMANDS,
    GERMANS: GERMAN_COMMANDS,
}


def _faction_special_abilities(faction, scenario):
    ario = scenario in ARIOVISTUS_SCENARIOS
    if faction == ROMANS:
        return ROMAN_SPECIAL_ABILITIES
    if faction == AEDUI:
        return AEDUI_SPECIAL_ABILITIES
    if faction == BELGAE:
        return BELGAE_SPECIAL_ABILITIES
    if faction == ARVERNI:
        return (ARVERNI_SPECIAL_ABILITIES_ARIOVISTUS if ario
                else ARVERNI_SPECIAL_ABILITIES_BASE)
    if faction == GERMANS:
        return (GERMAN_SPECIAL_ABILITIES_ARIOVISTUS if ario
                else GERMAN_SPECIAL_ABILITIES_BASE)
    return ()


def _mobile_count(state, region, faction):
    n = (count_pieces(state, region, faction, LEGION)
         + count_pieces(state, region, faction, AUXILIA)
         + count_pieces(state, region, faction, WARBAND))
    if get_leader_in_region(state, region, faction) is not None:
        n += 1
    return n


def _regions_with_pieces(state, faction):
    return [r for r in get_playable_regions(state["scenario"],
                                            state.get("capabilities"))
            if count_pieces(state, r, faction) > 0]


def _enemies_in_region(state, region, faction):
    return [f for f in FACTIONS
            if f != faction and count_pieces(state, region, f) > 0]


def _battle_regions(state, faction):
    out = []
    for r in get_playable_regions(state["scenario"], state.get("capabilities")):
        if (_mobile_count(state, r, faction) > 0
                and _enemies_in_region(state, r, faction)):
            out.append(r)
    return out


def _subdued_tribes(state, region):
    from fs_bot.map.map_data import get_tribes_in_region
    out = []
    for t in get_tribes_in_region(region, state["scenario"]):
        ti = state.get("tribes", {}).get(t, {})
        if ti.get("allied_faction") is None and ti.get("status") is None:
            out.append(t)
    return out


def _pick_regions(stdin, stdout, prompt, candidates, *, at_least_one=True,
                  single=False):
    """Pick Region(s) from ``candidates`` (each pickable once). ``single``
    collects exactly one; otherwise add Regions until "(done)"."""
    chosen, remaining = [], list(candidates)
    while remaining:
        opts = [(r, r) for r in remaining]
        if not single and (chosen or not at_least_one):
            opts.append(("(done)", None))
        pick = prompt_choice(stdin, stdout, prompt, opts)
        if pick is None:
            break
        chosen.append(pick)
        remaining.remove(pick)
        if single:
            break
    return chosen


def _collect_battle(state, faction, stdin, stdout, single):
    regions = _battle_regions(state, faction)
    if not regions:
        return None
    picked = _pick_regions(stdin, stdout, "Battle in which Region(s)?",
                           regions, single=single)
    plan = []
    for r in picked:
        enemies = _enemies_in_region(state, r, faction)
        target = prompt_choice(stdin, stdout, f"  Defender in {r}?",
                               [(f, f) for f in enemies])
        plan.append({"region": r, "target": target})
    return {"battle_plan": plan} if plan else None


def _collect_raid(state, faction, stdin, stdout, single):
    regions = [r for r in _regions_with_pieces(state, faction)
               if count_pieces(state, r, faction, WARBAND) > 0]
    if not regions:
        return None
    picked = _pick_regions(stdin, stdout, "Raid in which Region(s)?",
                           regions, single=single)
    plan = []
    for r in picked:
        enemies = _enemies_in_region(state, r, faction)
        opts = [(f"steal from {f}", f) for f in enemies]
        opts.append(("gain 1 Resource", None))
        target = prompt_choice(stdin, stdout, f"  Raid target in {r}?", opts)
        plan.append({"region": r, "target": target})
    return {"raid_plan": plan} if plan else None


def _collect_march(state, faction, stdin, stdout, single):
    origins_c = [r for r in _regions_with_pieces(state, faction)
                 if _mobile_count(state, r, faction) > 0]
    if not origins_c:
        return None
    origins = _pick_regions(stdin, stdout, "March OUT of which Region(s)?",
                            origins_c, single=single)
    if not origins:
        return None
    dest_set = []
    for o in origins:
        for a in get_adjacent(o, state["scenario"]):
            if a not in dest_set and a not in origins:
                dest_set.append(a)
    destinations = _pick_regions(stdin, stdout,
                                 "March INTO which adjacent Region(s)?",
                                 dest_set, single=single)
    if not destinations:
        return None
    return {"origins": origins, "destinations": destinations}


def _collect_rally(state, faction, stdin, stdout, single):
    regions = _regions_with_pieces(state, faction)
    if not regions:
        return None
    picked = _pick_regions(stdin, stdout, "Rally in which Region(s)?",
                           regions, single=single)
    warbands, allies = [], []
    for r in picked:
        what = prompt_choice(stdin, stdout, f"  In {r}, place:",
                             [("Warbands", "warbands"),
                              ("an Ally at a Subdued Tribe", "ally")])
        if what == "ally":
            subdued = _subdued_tribes(state, r)
            if subdued:
                tribe = prompt_choice(stdin, stdout,
                                      f"  Ally which Tribe in {r}?",
                                      [(t, t) for t in subdued])
                allies.append({"region": r, "tribe": tribe})
                continue
        warbands.append(r)
    return {"rally_plan": {"citadels": [], "allies": allies,
                           "warbands": warbands}}


def _collect_recruit(state, faction, stdin, stdout, single):
    regions = get_playable_regions(state["scenario"], state.get("capabilities"))
    cand = [r for r in regions if count_pieces(state, r, ROMANS) > 0]
    if not cand:
        return None
    picked = _pick_regions(stdin, stdout, "Recruit in which Region(s)?",
                           cand, single=single)
    plan = []
    for r in picked:
        action = prompt_choice(stdin, stdout, f"  In {r}:",
                               [("place Auxilia", "place_auxilia"),
                                ("place a Roman Ally", "place_ally")])
        entry = {"region": r, "action": action}
        if action == "place_ally":
            subdued = _subdued_tribes(state, r)
            if subdued:
                entry["tribe"] = prompt_choice(
                    stdin, stdout, f"  Ally which Tribe in {r}?",
                    [(t, t) for t in subdued])
        plan.append(entry)
    return {"recruit_plan": plan} if plan else None


def _collect_seize(state, faction, stdin, stdout, single):
    from fs_bot.commands.seize import get_dispersible_tribes
    regions = get_playable_regions(state["scenario"], state.get("capabilities"))
    cand = [r for r in regions if count_pieces(state, r, ROMANS) > 0]
    if not cand:
        return None
    picked = _pick_regions(stdin, stdout, "Seize in which Region(s)?",
                           cand, single=single)
    disperse = []
    for r in picked:
        if get_dispersible_tribes(state, r) and prompt_yes_no(
                stdin, stdout, f"  Disperse Subdued Tribes in {r}?",
                default=True):
            disperse.append(r)
    return {"_regions": picked, "disperse_regions": disperse}


_COMMAND_COLLECTORS = {
    "Battle": _collect_battle, "Raid": _collect_raid, "March": _collect_march,
    "Rally": _collect_rally, "Recruit": _collect_recruit,
    "Seize": _collect_seize,
}


def _collect_command(state, faction, engine_action, stdin, stdout):
    scenario = state["scenario"]
    single = engine_action == ACTION_LIMITED_COMMAND
    commands = _FACTION_COMMANDS.get(faction, ())
    cmd = prompt_choice(stdin, stdout, "Which Command?",
                        [(c, c) for c in commands])
    collector = _COMMAND_COLLECTORS.get(cmd)
    details = (collector(state, faction, stdin, stdout, single)
               if collector else None)
    if details is None:
        return None

    action = {"command": cmd, "regions": [], "sa": _SA_NONE,
              "sa_regions": [], "details": {}}
    if cmd == "Seize":
        action["regions"] = details.pop("_regions", [])
    action["details"] = details

    if engine_action == ACTION_COMMAND_SA:
        sas = _faction_special_abilities(faction, scenario)
        if sas and prompt_yes_no(stdin, stdout,
                                 "Add a Special Activity?", default=False):
            sa = prompt_choice(stdin, stdout, "Which Special Activity?",
                               [(s, s) for s in sas])
            action["sa"] = sa
            cand = _regions_with_pieces(state, faction)
            if cand:
                action["sa_regions"] = _pick_regions(
                    stdin, stdout, f"{sa} in which Region(s)? (optional)",
                    cand, at_least_one=False)
    return action


def collect_player_action(state, faction, engine_action, stdin, stdout):
    """Collect a human's full plan for a chosen action TYPE.

    Returns a ``player_action`` dict (bot-action shape) for a Command or Event,
    or None for Pass / when the player has no legal concrete action (the caller
    then treats it as a Pass-equivalent no-op).
    """
    if engine_action == ACTION_PASS:
        return None
    if engine_action == ACTION_EVENT:
        card_id = state.get("current_card")
        side = prompt_choice(stdin, stdout, "Play which side of the Event?",
                             [("Unshaded", EVENT_UNSHADED),
                              ("Shaded", EVENT_SHADED)])
        return {"command": "Event", "regions": [], "sa": _SA_NONE,
                "sa_regions": [], "details": {"card_id": card_id,
                                              "text_preference": side}}
    if engine_action in (ACTION_COMMAND, ACTION_COMMAND_SA,
                         ACTION_LIMITED_COMMAND):
        return _collect_command(state, faction, engine_action, stdin, stdout)
    return None
