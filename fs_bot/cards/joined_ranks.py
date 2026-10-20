"""Card 54's bounded March and optional, same-defender Battles.

Sources: Card Reference 54 and its Tips; A Card Reference 54; §§3.2.2,
3.3.2, 5.4. The second Non-player never Battles under this Event.
"""
from fs_bot.rules_consts import (
    ROMANS, ARVERNI, AEDUI, BELGAE, GERMANS, FACTIONS,
    LEGION, AUXILIA, WARBAND, LEADER, ARIOVISTUS_SCENARIOS,
)
from fs_bot.board.pieces import count_pieces
from fs_bot.map.map_data import get_playable_regions, is_adjacent
from fs_bot.commands.march import _max_steps_for_group, _check_crossing_stop
from fs_bot.engine.agent import consult_agent, AGREEMENT


def _revised(state):
    from fs_bot.cards.edition import uses_second_edition
    return uses_second_edition(state)


def _group(state, faction, origin, params, limit):
    from fs_bot.engine.execute import _mobile_march_group
    available = _mobile_march_group(state, faction, origin)
    keys = {LEGION: "march_legions", AUXILIA: "march_auxilia",
            WARBAND: "march_warbands", LEADER: "march_leader"}
    explicit = any(key in params for key in keys.values())
    result, left = {}, limit
    for piece in (LEADER, LEGION, AUXILIA, WARBAND):
        maximum = int(bool(available[piece])) if piece == LEADER else available[piece]
        n = params.get(keys[piece], 0) if explicit else min(maximum, left)
        if isinstance(n, bool):
            n = int(n) if piece == LEADER else -1
        if not isinstance(n, int) or not 0 <= n <= maximum:
            raise ValueError(f"Invalid Card 54 {piece} selection")
        result[piece] = available[piece] if piece == LEADER and n else (None if piece == LEADER else n)
        left -= n
    if left < 0 or left == limit:
        raise ValueError("Card 54 March requires one group of 1–8 mobile pieces, including its Leader")
    return result


def _validate_route(state, faction, origin, route, group, region, playable):
    if not isinstance(route, list) or not route or route[-1] != region:
        raise ValueError("Card 54 March route must end in the selected Region")
    if len(route) > _max_steps_for_group(state, origin, faction, group):
        raise ValueError("Card 54 March route exceeds this group's normal distance")
    previous = origin
    for i, destination in enumerate(route):
        if destination not in playable or not is_adjacent(previous, destination):
            raise ValueError("Card 54 March must use adjacent playable Regions")
        stops, _ = _check_crossing_stop(state, previous, destination, faction)
        if stops and i < len(route) - 1:
            raise ValueError("Card 54 March cannot continue past a required stop")
        previous = destination


def resolve_joined_ranks(state, faction, march_limit=8, second_always_retreat=False):
    from fs_bot.engine.execute import (
        _attacker_has_force, _mobile_march_group, _group_has_pieces,
        _march_with_harassment, _rank_free_battle_defender, _execute_battle,
        _CMD_BATTLE, SA_ACTION_NONE_LABEL,
    )
    from fs_bot.engine.game_engine import get_sop_factions
    params = state.get("event_params") or {}
    playable = set(get_playable_regions(state["scenario"], state.get("capabilities")))
    qualifying = FACTIONS if _revised(state) else (ROMANS, ARVERNI, AEDUI, BELGAE)
    candidates = [r for r in sorted(playable) if sum(
        count_pieces(state, r, f) > 0 for f in qualifying if f != faction) >= 2]
    region = params.get("region")
    if region is not None and region not in candidates:
        raise ValueError("Card 54 destination must already contain two other qualifying Factions")
    if region is None:
        region = next((r for r in candidates if _attacker_has_force(state, r, faction)), None)
        if region is None:
            region = next((r for r in candidates if any(
                is_adjacent(o, r) and _group_has_pieces(_mobile_march_group(state, faction, o))
                for o in sorted(playable))), None)
    if region is None:
        return [{"free_action": "joined_ranks", "flag": "card_54", "executed": False,
                 "reason": "no qualifying Region reachable"}]
    do_march = params.get("march", True)
    if not isinstance(do_march, bool):
        raise ValueError("Card 54 march must be true or false")
    origin = params.get("origin_region") if do_march else None
    if do_march and origin is None and not _attacker_has_force(state, region, faction):
        origin = next((o for o in sorted(playable) if is_adjacent(o, region)
                       and _group_has_pieces(_mobile_march_group(state, faction, o))), None)
    group = route = None
    if origin is not None:
        if origin not in playable or origin == region:
            raise ValueError("Card 54 March needs a different, playable origin")
        group = _group(state, faction, origin, params, min(march_limit, 8))
        route = params.get("march_regions", [region])
        _validate_route(state, faction, origin, route, group, region, playable)
    defender = params.get("target_faction")
    if defender is None:
        defender = _rank_free_battle_defender(state, region, faction)
    if defender is not None and (defender == faction or defender not in FACTIONS
                                or count_pieces(state, region, defender) == 0):
        raise ValueError("Card 54 needs an opposing defender in its destination")
    second = params.get("second_faction")
    players = get_sop_factions(state)
    if second is not None and (second not in players or second in (faction, defender)
                               or not _attacker_has_force(state, region, second)):
        raise ValueError("Card 54 second attacker must be another player Faction already there")
    first = params.get("first_battle", True)
    if not isinstance(first, bool):
        raise ValueError("Card 54 first_battle must be true or false")
    # All explicit selections above are checked before the first mutation.
    results = []
    if group is not None:
        arrived = _march_with_harassment(state, faction, origin, route, group_cap=group)
        results.append({"free_action": "march", "flag": "card_54", "source": origin,
                        "dest": arrived, "group": group})
    first_executed = False
    if first and defender is not None and _attacker_has_force(state, region, faction):
        result = _execute_battle(state, faction, {
            "command": _CMD_BATTLE, "sa": SA_ACTION_NONE_LABEL, "sa_regions": [],
            "details": {"battle_plan": [{"region": region, "target": defender}],
                        "no_retreat": True}})
        first_executed = bool(result.get("executed"))
        results.append({"free_action": "battle", "flag": "card_54", "battler": faction,
                        "region": region, "defender": defender, "result": result})
    possible = [second] if second is not None else [f for f in players
                if f not in (faction, defender) and _attacker_has_force(state, region, f)]
    for ally in possible:
        if ally in state.get("non_player_factions", set()):
            continue  # Card 54 Tips: a second Non-player would not Battle.
        if defender is None or count_pieces(state, region, defender) == 0:
            break  # Both Battles must attack the SAME third Faction.
        agrees = consult_agent(state, ally, {"kind": AGREEMENT,
            "request_type": "joined_ranks_battle", "requesting_faction": faction,
            "context": {"region": region, "defender": defender, "free": True,
                        "no_retreat": not (_revised(state) or first_executed)}})
        if agrees is not True:
            continue
        result = _execute_battle(state, ally, {
            "command": _CMD_BATTLE, "sa": SA_ACTION_NONE_LABEL, "sa_regions": [],
            "details": {"battle_plan": [{"region": region, "target": defender}],
                        "no_retreat": not (_revised(state) or first_executed)}})
        results.append({"free_action": "battle", "flag": "card_54", "battler": ally,
                        "region": region, "defender": defender, "result": result})
        break
    return results
