"""The free Germanic Limited Command option of Enlist (§4.5.1/A4.5.1)."""

from contextlib import nullcontext

from fs_bot.rules_consts import (
    GERMANS, FACTIONS, WARBAND, AUXILIA, HIDDEN, REVEALED, SCOUTED,
    BASE_SCENARIOS, ARIOVISTUS_SCENARIOS,
    ENLIST_MAX_GERMAN_PIECES_ARIOVISTUS,
)
from fs_bot.board.pieces import count_pieces, count_pieces_by_state, get_available
from fs_bot.commands.common import CommandError, free_action_scope
from fs_bot.commands.sa_enlist import validate_enlist_region
from fs_bot.map.map_data import get_adjacent, get_playable_regions


def select_warbands(state, region, requested=None, *, hiding=False):
    """Validate a player's visibility selection, or choose a bounded default.

    A4.5.1 limits the *entire* Enlist to four pieces, not four per Region.
    A free Command has a single origin/Region, so this selection is its budget.
    Legacy bot plans may supply a total rather than a visibility mapping.
    """
    states = (REVEALED, SCOUTED, HIDDEN) if hiding else (HIDDEN, REVEALED, SCOUTED)
    available = {ps: count_pieces_by_state(state, region, GERMANS, WARBAND, ps)
                 for ps in states}
    limit = (ENLIST_MAX_GERMAN_PIECES_ARIOVISTUS
             if state["scenario"] in ARIOVISTUS_SCENARIOS else sum(available.values()))
    if requested is None:
        requested = min(sum(available.values()), limit)
    if type(requested) is int:
        if requested < 1 or requested > limit or requested > sum(available.values()):
            raise CommandError("Enlist Warband count exceeds available pieces or its limit")
        left = requested
        selected = {}
        for ps in states:
            selected[ps] = min(available[ps], left)
            left -= selected[ps]
    elif isinstance(requested, dict):
        if set(requested) - {HIDDEN, REVEALED, SCOUTED}:
            raise CommandError("Enlist selection may contain only Warband visibility states")
        selected = {ps: requested.get(ps, 0) for ps in states}
        if any(type(n) is not int or n < 0 for n in selected.values()):
            raise CommandError("Enlist Warband counts must be nonnegative integers")
        if any(selected[ps] > available[ps] for ps in states):
            raise CommandError("Selected German Warbands are not present")
        if not 1 <= sum(selected.values()) <= limit:
            raise CommandError("Enlist exceeds its Warband limit")
    else:
        raise CommandError("Enlist Warbands must be a count or visibility mapping")
    return selected


def _force_scope(state, region, selected):
    if state["scenario"] in BASE_SCENARIOS:
        return nullcontext()
    # Effective combat/movement reads see just the selected Warbands; their
    # physical ownership, all unrelated pieces, and Control remain intact.
    from fs_bot.commands.sa_enlist import scoped_free_force
    return scoped_free_force(state, region, selected)


def execute_free_enlist(state, plan):
    """Resolve one source-defined free Command; reject invalid selections first."""
    kind = plan.get("type")
    allowed = {"german_battle", "german_march", "german_march_hide",
               "german_rally", "german_raid"}
    if kind not in allowed:
        raise CommandError("Unknown free Enlist sub-Command")
    if kind in ("german_march", "german_march_hide"):
        from fs_bot.engine.game_engine import is_frost
        if is_frost(state):
            raise CommandError("No Enlist March during Frost (§4.5.1)")
    region = plan.get("origin") if kind == "german_march" else plan.get("region")
    playable = get_playable_regions(state["scenario"], state.get("capabilities"))
    if region not in playable:
        raise CommandError("Enlist must select a playable Region")
    valid, reason = validate_enlist_region(state, region)
    if not valid:
        raise CommandError(reason)
    base = state["scenario"] in BASE_SCENARIOS

    if kind in ("german_march", "german_march_hide"):
        from fs_bot.commands.march import _flip_origin_pieces, march_group
        if kind == "german_march":
            destination = plan.get("destination")
            if destination not in get_adjacent(region, state["scenario"],
                                               state.get("capabilities")):
                raise CommandError("Enlisted Germans may March to one adjacent Region only")
        selected = select_warbands(state, region, plan.get("warbands"),
                                   hiding=kind == "german_march_hide")
        if kind == "german_march_hide" and not (selected[REVEALED] or selected[SCOUTED]):
            raise CommandError("No selected German Warband can Hide or lose its Scouted marker")
        with _force_scope(state, region, selected):
            flipped = _flip_origin_pieces(state, region, GERMANS)
            if kind == "german_march_hide":
                return {"flipped": flipped}
            marched = march_group(state, GERMANS, region, [destination],
                                   {WARBAND: sum(selected.values())}, free=True)
            return {"flipped": flipped, "march": marched}

    if kind == "german_battle":
        from fs_bot.engine.execute import _decide_defender_retreat
        from fs_bot.battle.resolve import resolve_battle
        target = plan.get("target")
        if target not in FACTIONS or target == GERMANS or not count_pieces(state, region, target):
            raise CommandError("Enlist Battle requires another Faction with pieces in the Region")
        selected = select_warbands(state, region, plan.get("warbands"))
        if base:
            if sum(selected.values()) != count_pieces(state, region, GERMANS, WARBAND):
                raise CommandError("Base Germanic Battle uses all Warbands in its Region")
            enemy_hidden = sum(count_pieces_by_state(state, region, target, pt, HIDDEN)
                               for pt in (WARBAND, AUXILIA))
            if selected[HIDDEN] <= enemy_hidden:
                raise CommandError("Base-game Germans may Battle only where they can Ambush")
        with free_action_scope(state, GERMANS), _force_scope(state, region, selected):
            declaration, retreat_region = _decide_defender_retreat(
                state, region, GERMANS, target, base)
            return resolve_battle(state, region, GERMANS, target, is_ambush=base,
                                  retreat_declaration=declaration,
                                  retreat_region=retreat_region)

    if kind == "german_raid":
        from fs_bot.commands.raid import raid_in_region
        actions = plan.get("actions")
        if actions is None:
            target = plan.get("target")
            count = plan.get("count", 1)
            if type(count) is not int or not 1 <= count <= 2:
                raise CommandError("Enlist Raid count must be one or two Warbands")
            actions = [({"type": "steal", "target": target} if target
                        else {"type": "gain"}) for _ in range(count)]
        if not isinstance(actions, list) or any(not isinstance(a, dict) for a in actions):
            raise CommandError("Enlist Raid actions must be a list of action mappings")
        return raid_in_region(state, region, GERMANS, actions, free=True)

    from fs_bot.commands.rally import rally_in_region
    place = plan.get("place", "warbands")
    if place not in ("ally", "warbands"):
        raise CommandError("Enlist Rally may place only German Allies or Warbands")
    action = "place_ally" if place == "ally" else "place_warbands"
    first = rally_in_region(state, region, GERMANS, action,
                            tribe=plan.get("tribe"), free=True,
                            include_home_bonus=True,
                            max_pieces=None if base else ENLIST_MAX_GERMAN_PIECES_ARIOVISTUS)
    result = {"rally": [first]}
    # §3.4.1 places Warbands after an Ally, even at the same Region. The
    # Ariovistus replacement instead chooses one option plus its Home bonus.
    if base and place == "ally" and get_available(state, GERMANS, WARBAND):
        result["rally"].append(rally_in_region(
            state, region, GERMANS, "place_warbands", free=True))
    return result
