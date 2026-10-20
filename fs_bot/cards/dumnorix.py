"""Card 44's replacement cohort and the actions granted to those pieces.

Card Reference 44 and its Tips restrict Scout/original Raid to the pieces
just placed. A Card Reference 44 instead gives the executing faction a
Command in the placement Regions. §5.1.1 removes a source even when its
replacement is unavailable; such removals do not create a participating
piece or a placement Region.
"""

from collections import Counter, defaultdict
from copy import deepcopy

from fs_bot.rules_consts import (
    ROMANS, AEDUI, ARVERNI, BELGAE, GERMANS, GALLIC_FACTIONS, FACTIONS,
    AUXILIA, WARBAND, LEGION, SETTLEMENT, HIDDEN, REVEALED, SCOUTED,
    CAESAR, BRITANNIA, GERMANIA_REGIONS, ARIOVISTUS_SCENARIOS,
    BASE_SCENARIOS, EVENT_SHADED,
)
from fs_bot.board.pieces import (
    count_pieces, count_pieces_by_state, get_available,
    place_piece, remove_piece, move_piece, flip_piece,
)
from fs_bot.map.map_data import (get_playable_regions_for_state, is_adjacent,
                                   get_adjacent, is_region_playable)
from fs_bot.commands.common import check_leader_proximity


def _clone(state):
    return deepcopy({k: v for k, v in state.items() if k != "decision_agent"})


def _count(value, label, *, zero=False):
    if type(value) is not int or value < (0 if zero else 1):
        raise ValueError(f"Card 44 {label} must be a {'nonnegative' if zero else 'positive'} integer")
    return value


def _entries(params, key):
    value = params.get(key, [])
    if not isinstance(value, list) or any(not isinstance(e, dict) for e in value):
        raise ValueError(f"Card 44 {key} must be a list of entries")
    return value


def _normalize_replacements(state, shaded):
    params = state.get("event_params") or {}
    if not isinstance(params, dict):
        raise ValueError("Card 44 event_params must be an object")
    entries = _entries(params, "replacements")
    normalized = []
    total = 0
    playable = set(get_playable_regions_for_state(state))
    for entry in entries:
        region = entry.get("region")
        if region not in playable:
            raise ValueError("Card 44 replacement Region must be playable")
        count = _count(entry.get("count", 1), "replacement count")
        total += count
        if total > (3 if shaded else 4):
            raise ValueError("Card 44 replaces at most 3 shaded or 4 unshaded pieces")
        source = entry.get("from_faction")
        kind = entry.get("from_type", AUXILIA if shaded else WARBAND)
        destination_kind = entry.get("to_type", WARBAND if shaded else AUXILIA)
        destination = entry.get("to_faction",
                                state.get("executing_faction") if shaded else
                                (ROMANS if destination_kind == AUXILIA else AEDUI))
        if shaded:
            if (source, kind) not in ((ROMANS, AUXILIA), (AEDUI, WARBAND)):
                raise ValueError("Card 44 shaded replaces only Roman Auxilia or Aedui Warbands")
            if destination_kind != WARBAND or destination not in (*GALLIC_FACTIONS, GERMANS):
                raise ValueError("Card 44 shaded places only Warbands of a faction that has them")
        else:
            if kind != WARBAND or source not in (*GALLIC_FACTIONS, GERMANS):
                raise ValueError("Card 44 unshaded replaces only Warbands")
            if (destination, destination_kind) not in ((ROMANS, AUXILIA), (AEDUI, WARBAND)):
                raise ValueError("Card 44 unshaded places only Roman Auxilia or Aedui Warbands")
        piece_state = entry.get("piece_state")
        if piece_state not in (None, HIDDEN, REVEALED, SCOUTED):
            raise ValueError("Card 44 source piece state is invalid")
        if kind == AUXILIA and piece_state == SCOUTED:
            raise ValueError("Auxilia cannot be Scouted")
        normalized.append((region, source, kind, piece_state,
                           destination, destination_kind, count))
    return normalized


def _replace(state, normalized):
    # Reserve original sources so a newly placed piece cannot be selected
    # again later in the list. Missing original pieces simply cannot apply
    # (§5.1.3); they never produce a replacement.
    remaining = {}
    for region, source, kind, ps, *_ in normalized:
        for visibility in (HIDDEN, REVEALED, SCOUTED):
            key = region, source, kind, visibility
            remaining.setdefault(key, count_pieces_by_state(
                state, region, source, kind, visibility))
    placed = Counter()
    for region, source, kind, ps, destination, destination_kind, count in normalized:
        states = (ps,) if ps is not None else (HIDDEN, REVEALED, SCOUTED)
        for _ in range(count):
            actual = next((v for v in states if remaining[(region, source, kind, v)]), None)
            if actual is None:
                continue
            remaining[(region, source, kind, actual)] -= 1
            remove_piece(state, region, source, kind, piece_state=actual)
            # Cards 5/A5 permit only Roman stacking in Cisalpina.
            # §5.1.1 removes instead of replacing when stacking forbids it.
            can_stack = is_region_playable(state, region, destination)
            if can_stack and get_available(state, destination, destination_kind) > 0:
                place_piece(state, region, destination, destination_kind)
                placed[(region, destination, destination_kind)] += 1
    return [{"region": r, "faction": f, "piece_type": pt, "count": n}
            for (r, f, pt), n in placed.items()]


def execute_replacements(state, shaded, revised=False):
    """Validate the whole declared Event before applying any replacement."""
    normalized = _normalize_replacements(state, shaded)
    params = state.get("event_params") or {}
    stage = _clone(state)
    cohort = _replace(stage, normalized)
    moves = _entries(params, "scout_moves")
    reveals = _entries(params, "scout_reveals")
    raid_actions = (None if "raid_actions" not in params
                    else _entries(params, "raid_actions"))
    if not shaded:
        scout_cohort(stage, cohort, moves, reveals)
    elif not revised:
        if raid_actions is None:
            raid_actions = derive_raids(stage, cohort)
        raid_cohort(stage, cohort, raid_actions)
    cohort = _replace(state, normalized)
    state["rng"].setstate(stage["rng"].getstate())
    mods = state.setdefault("event_modifiers", {})
    mods["card_44_placed"] = cohort
    if not shaded:
        mods["card_44_free_scout"] = True
        mods["card_44_scout_moves"] = deepcopy(moves)
        mods["card_44_scout_reveals"] = deepcopy(reveals)
    elif revised:
        mods["card_44a_free_command"] = bool(cohort)
        mods["card_44a_command_regions"] = sorted({e["region"] for e in cohort})
    else:
        mods["card_44_free_raid"] = True
        mods["card_44_raid_actions"] = deepcopy(raid_actions)
    return {"placed": cohort}


def scout_cohort(state, cohort, moves, reveals):
    """Scout only the new Auxilia/blue Warbands, preserving their ownership."""
    budget = Counter({(e["region"], e["faction"]): e["count"] for e in cohort})
    original = budget.copy()
    playable = set(get_playable_regions_for_state(state))
    moved = []
    for entry in moves:
        origin, target, faction = entry.get("from_region"), entry.get("to_region"), entry.get("faction", ROMANS)
        amount = _count(entry.get("count", 1), "Scout move count")
        if (origin not in playable or target not in playable or
                BRITANNIA in (origin, target) or not is_adjacent(origin, target)):
            raise ValueError("Card 44 Scout moves must be adjacent playable Regions outside Britannia")
        if not is_region_playable(state, target, faction):
            raise ValueError("Only Romans may stack in Cisalpina with Gallia Togata (Cards 5/A5)")
        if faction not in (ROMANS, AEDUI) or amount > original[(origin, faction)]:
            raise ValueError("Card 44 Scout may move each just-placed piece only once")
        original[(origin, faction)] -= amount
        budget[(origin, faction)] -= amount
        budget[(target, faction)] += amount
        kind = AUXILIA if faction == ROMANS else WARBAND
        move_piece(state, origin, target, faction, kind, count=amount, piece_state=HIDDEN)
        moved.append({"from_region": origin, "to_region": target,
                      "faction": faction, "count": amount})
    groups = defaultdict(list)
    for entry in reveals:
        region, faction, target = entry.get("region"), entry.get("faction", ROMANS), entry.get("target_faction")
        amount = _count(entry.get("count", 1), "Scout target count")
        scouts = _count(entry.get("scouts", (amount + 1) // 2), "Scout pieces", zero=True)
        if region not in playable or faction not in (ROMANS, AEDUI):
            raise ValueError("Card 44 Scout needs a playable Region and a placed Roman/Aedui piece")
        if target not in (*GALLIC_FACTIONS, GERMANS) or target == faction:
            raise ValueError("Card 44 Scout can reveal only enemy Warbands")
        valid, reason = check_leader_proximity(state, region, ROMANS, CAESAR, "Scout Reveal")
        if not valid:
            raise ValueError(reason)
        groups[(region, faction)].append((target, amount, scouts))
    from fs_bot.cards.capabilities import is_capability_active
    if is_capability_active(state, 12, EVENT_SHADED) and len({r for r, _ in groups}) > 1:
        raise ValueError("Card 12 restricts Scout Reveal to one Region")
    revealed = []
    for (region, faction), entries in groups.items():
        scouts = sum(e[2] for e in entries)
        if scouts > budget[(region, faction)] or sum(e[1] for e in entries) > scouts * 2:
            raise ValueError("Card 44 Scout may use only placed pieces, revealing at most two Warbands each")
        targets = Counter()
        for target, amount, _ in entries:
            targets[target] += amount
        for target, amount in targets.items():
            eligible = sum(count_pieces_by_state(state, region, target, WARBAND, ps)
                           for ps in (HIDDEN, REVEALED))
            if amount > eligible:
                raise ValueError("Card 44 Scout selected more unscouted enemy Warbands than present")
        kind = AUXILIA if faction == ROMANS else WARBAND
        if scouts:
            flip_piece(state, region, faction, kind, count=scouts,
                       from_state=HIDDEN, to_state=REVEALED)
        for target, amount in targets.items():
            hidden = min(amount, count_pieces_by_state(state, region, target, WARBAND, HIDDEN))
            if hidden:
                flip_piece(state, region, target, WARBAND, count=hidden,
                           from_state=HIDDEN, to_state=SCOUTED)
            if amount > hidden:
                flip_piece(state, region, target, WARBAND, count=amount-hidden,
                           from_state=REVEALED, to_state=SCOUTED)
            revealed.append({"region": region, "faction": target, "count": amount})
    return {"executed": bool(moved or revealed), "moves": moved, "revealed": revealed}


def derive_raids(state, cohort):
    """Use the published faction Raid priorities, restricted to this cohort."""
    from fs_bot.bots import arverni_bot, aedui_bot, belgae_bot, german_bot
    planners = {ARVERNI: arverni_bot._would_raid_gain_enough,
                AEDUI: aedui_bot._would_raid_gain_enough,
                BELGAE: belgae_bot._would_raid_gain_enough,
                GERMANS: german_bot._would_raid_gain_enough}
    by_faction = defaultdict(dict)
    for e in cohort:
        by_faction[e["faction"]][e["region"]] = e["count"]
    actions = []
    stage = _clone(state)
    for faction, regions in by_faction.items():
        if faction == GERMANS and state["scenario"] in BASE_SCENARIOS:
            # §6.2.3 player targets first, random among equal targets;
            # §3.4.3 Germans never gain Resources.
            from fs_bot.commands.raid import get_germans_phase_raid_targets
            for region, n in regions.items():
                for _ in range(min(n, 2)):
                    targets = get_germans_phase_raid_targets(stage, region)
                    players = [f for f in targets if f not in state.get("non_player_factions", set())]
                    if not targets:
                        break
                    action = {"region": region, "faction": faction,
                              "target_faction": stage["rng"].choice(players or targets)}
                    raid_cohort(stage, cohort, [action])
                    actions.append(action)
            continue
        _, plan = planners[faction](stage, stage["scenario"], raiders=regions)
        faction_actions = []
        for entry in plan:
            if faction == GERMANS and state["scenario"] in BASE_SCENARIOS and entry.get("target") is None:
                continue  # §3.4.3: game-run Germans never gain Resources.
            faction_actions.append({"region": entry["region"], "faction": faction,
                                    "target_faction": entry.get("target")})
        raid_cohort(stage, cohort, faction_actions)
        actions.extend(faction_actions)
    state["rng"].setstate(stage["rng"].getstate())
    return actions


def raid_cohort(state, cohort, actions):
    from fs_bot.commands.raid import raid_in_region, validate_raid_steal_target
    from fs_bot.cards.capabilities import is_capability_active, get_capability_owner
    budget = Counter({(e["region"], e["faction"]): e["count"] for e in cohort})
    groups = defaultdict(list)
    for entry in actions:
        region, faction = entry.get("region"), entry.get("faction")
        target = entry.get("target_faction")
        if target is not None and target not in FACTIONS:
            raise ValueError("Card 44 Raid target must be a faction or null")
        if (region, faction) not in budget:
            raise ValueError("Card 44 Raid may use only just-placed Warbands")
        groups[(region, faction)].append({"type": "gain"} if target is None else
                                         {"type": "steal", "target": target})
    results = []
    for (region, faction), plan in groups.items():
        limit = 3 if (is_capability_active(state, 8, EVENT_SHADED)
                      and get_capability_owner(state, 8) == faction) else 2
        if len(plan) > min(budget[(region, faction)], limit):
            raise ValueError("Card 44 Raid exceeds the placed cohort or per-Region Raid limit")
        if faction == GERMANS and state["scenario"] in BASE_SCENARIOS:
            # §3.4.3: Germans remove the enemy Resources without gaining any.
            for action in plan:
                target = action.get("target")
                if action["type"] != "steal":
                    raise ValueError("Base German Raid must target a faction")
                valid, reason = validate_raid_steal_target(state, region, faction, target)
                if not valid:
                    raise ValueError(reason)
                if state["resources"].get(target, 0) < 1:
                    raise ValueError("Card 44 Raid target has no Resources")
                flip_piece(state, region, faction, WARBAND, from_state=HIDDEN, to_state=REVEALED)
                state["resources"][target] -= 1
            results.append({"region": region, "faction": faction, "warbands_flipped": len(plan)})
        else:
            results.append(raid_in_region(state, region, faction, plan, free=True))
    return {"executed": bool(results), "regions": results}


def derive_scout_reveals(state, cohort, actor):
    """Aedui's card instruction: no movement; Hidden enemy priority order."""
    from fs_bot.cards.capabilities import is_capability_active
    if actor == ROMANS:
        from fs_bot.bots.bot_common import is_frost_active
        remaining = {e["region"]: e["count"] * 2 for e in cohort}
        ranked_targets = []
        for region in remaining:
            valid, _ = check_leader_proximity(state, region, ROMANS, CAESAR, "Scout Reveal")
            if not valid:
                continue
            for enemy in FACTIONS:
                if enemy == ROMANS:
                    continue
                hidden = count_pieces_by_state(state, region, enemy, WARBAND, HIDDEN)
                revealed = count_pieces_by_state(state, region, enemy, WARBAND, REVEALED)
                if hidden or revealed:
                    ranked_targets.append({"region": region, "enemy": enemy,
                        "hidden": hidden, "revealed": revealed,
                        "frost_priority": (enemy == GERMANS and is_frost_active(state)
                                           and state["scenario"] in BASE_SCENARIOS)})
        # §8.8.1: Hidden first, then Revealed; Frost prioritizes Germans
        # in the base game. A8.8.1 removes the Frost German preference.
        ranked_targets.sort(key=lambda e: (-e["frost_priority"], -e["hidden"], -e["revealed"]))
        by_region = defaultdict(list)
        for target in ranked_targets:
            region = target["region"]
            if (is_capability_active(state, 12, EVENT_SHADED)
                    and by_region and region not in by_region):
                continue
            amount = min(remaining.get(region, 0), target["hidden"] + target["revealed"])
            if amount:
                by_region[region].append({"region": region, "faction": ROMANS,
                                          "target_faction": target["enemy"],
                                          "count": amount, "scouts": 0})
                remaining[region] -= amount
        for entries in by_region.values():
            entries[0]["scouts"] = (sum(e["count"] for e in entries) + 1) // 2
        return [e for entries in by_region.values() for e in entries]
    if actor == AEDUI:
        targets = ((GERMANS, BELGAE, ARVERNI) if state["scenario"] in ARIOVISTUS_SCENARIOS
                   else (ARVERNI, BELGAE, GERMANS))
    else:
        targets = tuple(f for f in (ARVERNI, BELGAE, GERMANS, AEDUI) if f != actor)
    plan = []
    target_remaining = {}
    selected_region = None
    for e in cohort:
        region, faction, capacity = e["region"], e["faction"], e["count"] * 2
        valid, _ = check_leader_proximity(state, region, ROMANS, CAESAR, "Scout Reveal")
        if not valid or (is_capability_active(state, 12, EVENT_SHADED)
                         and selected_region not in (None, region)):
            continue
        local = []
        for target in targets:
            if target == faction:
                continue
            key = region, target
            target_remaining.setdefault(key, count_pieces_by_state(state, region, target, WARBAND, HIDDEN))
            amount = min(capacity, target_remaining[key])
            if amount:
                local.append({"region": region, "faction": faction,
                              "target_faction": target, "count": amount, "scouts": 0})
                target_remaining[key] -= amount
                capacity -= amount
        if local:
            local[0]["scouts"] = (sum(e["count"] for e in local) + 1) // 2
            selected_region = region
            plan.extend(local)
    return plan


def derive_params(state, actor, shaded):
    """NP Card 44 instructions, with every free action bounded to its cohort."""
    from fs_bot.bots.bot_common import get_faction_targeting_order
    from fs_bot.cards.edition import uses_second_edition
    playable = sorted(get_playable_regions_for_state(state))
    targets = [f for f in get_faction_targeting_order(actor, state["scenario"])
               if f != actor]
    candidates = []
    if not shaded:
        destination = AEDUI if actor == AEDUI else ROMANS
        destination_kind = WARBAND if destination == AEDUI else AUXILIA
        for region in playable:
            for target in targets:
                for ps in (HIDDEN, REVEALED, SCOUTED):
                    n = count_pieces_by_state(state, region, target, WARBAND, ps)
                    if n:
                        candidates.append((region, target, WARBAND, ps, n))
    else:
        destination = AEDUI if actor == ROMANS else actor
        destination_kind = WARBAND
        roman_regions = [r for r in playable if count_pieces(state, r, ROMANS, AUXILIA)]
        if actor == GERMANS and state["scenario"] in ARIOVISTUS_SCENARIOS:
            # A8.9 Card instructions: Roman pieces in Germania/Settlement
            # Regions, then adjacent; otherwise treat as No Germans.
            core = set(GERMANIA_REGIONS) | {
                r for r in playable if count_pieces(state, r, GERMANS, SETTLEMENT)}
            adjacent = {r for c in core for r in get_adjacent(c, state["scenario"])}
            roman_regions = sorted((r for r in roman_regions if r in core | adjacent),
                                   key=lambda r: (r not in core,
                                                  -count_pieces(state, r, ROMANS, AUXILIA), r))
        elif actor == ARVERNI:
            # Expose Legions in as many Regions as possible. Clearing the
            # smallest complete escorts first maximizes that count (cap 3).
            roman_regions.sort(key=lambda r: (
                not (count_pieces(state, r, ROMANS, LEGION) and
                     count_pieces(state, r, ROMANS, AUXILIA) <= 3),
                count_pieces(state, r, ROMANS, AUXILIA), r))
        for region in roman_regions:
            for ps in (HIDDEN, REVEALED):
                n = count_pieces_by_state(state, region, ROMANS, AUXILIA, ps)
                if n:
                    candidates.append((region, ROMANS, AUXILIA, ps, n))
        if actor not in (AEDUI, GERMANS):
            for region in playable:
                for ps in (HIDDEN, REVEALED, SCOUTED):
                    n = count_pieces_by_state(state, region, AEDUI, WARBAND, ps)
                    if n:
                        candidates.append((region, AEDUI, WARBAND, ps, n))
    reps, remaining = [], 3 if shaded else 4
    for region, target, kind, ps, available in candidates:
        n = min(remaining, available)
        if n:
            reps.append({"region": region, "from_faction": target,
                         "from_type": kind, "piece_state": ps,
                         "to_faction": destination, "to_type": destination_kind,
                         "count": n})
            remaining -= n
        if not remaining:
            break
    if not reps:
        return None
    params = {"replacements": reps}
    stage = _clone(state)
    stage["event_params"] = params
    stage["executing_faction"] = actor
    cohort = _replace(stage, _normalize_replacements(stage, shaded))
    if not shaded:
        moves = []
        if actor == ROMANS:
            from fs_bot.bots.roman_bot import _scout_auxilia_moves
            moves = _scout_auxilia_moves(stage, scouts={e["region"]: e["count"] for e in cohort})
            for move in moves:
                move["faction"] = ROMANS
            scout_cohort(stage, cohort, moves, [])
        # Aedui's explicit instruction is no movement; the Roman planner
        # only moves the newly placed Auxilia under its ordinary priorities.
        moved_cohort = Counter({(e["region"], e["faction"]): e["count"] for e in cohort})
        for move in moves:
            moved_cohort[(move["from_region"], move["faction"])] -= move["count"]
            moved_cohort[(move["to_region"], move["faction"])] += move["count"]
        reveal_cohort = [{"region": r, "faction": f, "count": n}
                        for (r, f), n in moved_cohort.items() if n]
        params["scout_moves"] = moves
        params["scout_reveals"] = derive_scout_reveals(stage, reveal_cohort, actor)
    elif not uses_second_edition(state):
        params["raid_actions"] = derive_raids(stage, cohort)
        state["rng"].setstate(stage["rng"].getstate())
    return params
