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
    warbands, allies, citadels = [], [], []
    for r in picked:
        opts = [("Warbands", "warbands"),
                ("an Ally at a Subdued Tribe", "ally")]
        upgradable = _citadel_upgrade_tribes(state, r, faction)
        if upgradable:
            opts.append(("a Citadel (replace your Ally at a City)",
                         "citadel"))
        what = prompt_choice(stdin, stdout, f"  In {r}, place:", opts)
        if what == "ally":
            subdued = _subdued_tribes(state, r)
            if subdued:
                tribe = prompt_choice(stdin, stdout,
                                      f"  Ally which Tribe in {r}?",
                                      [(t, t) for t in subdued])
                allies.append({"region": r, "tribe": tribe})
                continue
        elif what == "citadel":
            tribe = prompt_choice(stdin, stdout,
                                  f"  Citadel at which City in {r}?",
                                  [(t, t) for t in upgradable])
            citadels.append({"region": r, "tribe": tribe})
            continue
        warbands.append(r)
    return {"rally_plan": {"citadels": citadels, "allies": allies,
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


def _citadel_upgrade_tribes(state, region, faction):
    """City Tribes in ``region`` holding ``faction``'s Ally — Citadel
    upgrade candidates (§3.3.1, Aedui/Arverni only)."""
    from fs_bot.rules_consts import TRIBE_TO_CITY
    if faction not in (AEDUI, ARVERNI):
        return []
    from fs_bot.map.map_data import get_tribes_in_region
    out = []
    for t in get_tribes_in_region(region, state["scenario"]):
        ti = state.get("tribes", {}).get(t, {})
        if ti.get("allied_faction") == faction and t in TRIBE_TO_CITY:
            out.append(t)
    return out


def _enemy_ally_tribes(state, region, faction):
    """(tribe, owner) pairs for enemy Allied Tribes in ``region``."""
    from fs_bot.map.map_data import get_tribes_in_region
    out = []
    for t in get_tribes_in_region(region, state["scenario"]):
        owner = state.get("tribes", {}).get(t, {}).get("allied_faction")
        if owner and owner != faction:
            out.append((t, owner))
    return out


# --------------------------------------------------------------------- #
# Special Activity plan collectors — one per SA whose executor needs a
# concrete plan (engine/execute.py shapes). SAs absent here either need
# no plan (Trade; Build/Scout recompute §8.8-faithful plans against the
# board) or only Region names (Devastate, Settle), which the generic
# picker in _collect_command covers.
# --------------------------------------------------------------------- #

def _collect_suborn(state, faction, stdin, stdout):
    """Aedui Suborn (§4.4.2): up to 3 pieces in one Region, max 1 Ally."""
    regions = _regions_with_pieces(state, faction)
    if not regions:
        return None, None
    region = _pick_regions(stdin, stdout, "Suborn in which Region?",
                           regions, single=True)
    if not region:
        return None, None
    region = region[0]
    actions, ally_used = [], False
    while len(actions) < 3:
        opts = []
        subdued = _subdued_tribes(state, region)
        if not ally_used and subdued:
            opts.append(("place your Ally at a Subdued Tribe",
                         "place_ally"))
        enemy_allies = _enemy_ally_tribes(state, region, faction)
        if not ally_used and enemy_allies:
            opts.append(("remove an enemy Ally", "remove_ally"))
        opts.append(("place a Warband", "place_warband"))
        for f in _enemies_in_region(state, region, faction):
            if count_pieces(state, region, f, WARBAND) > 0:
                opts.append((f"remove a {f} Warband",
                             ("remove_warband", f)))
            if count_pieces(state, region, f, AUXILIA) > 0:
                opts.append((f"remove a {f} Auxilia",
                             ("remove_auxilia", f)))
        if actions:
            opts.append(("(done)", None))
        pick = prompt_choice(stdin, stdout,
                             f"Suborn action {len(actions) + 1} of up to 3:",
                             opts)
        if pick is None:
            break
        if pick == "place_ally":
            tribe = prompt_choice(stdin, stdout, "Ally which Tribe?",
                                  [(t, t) for t in subdued])
            actions.append({"action": "place_ally", "tribe": tribe})
            ally_used = True
        elif pick == "remove_ally":
            tribe, owner = prompt_choice(
                stdin, stdout, "Remove which enemy Ally?",
                [(f"{t} ({owner})", (t, owner)) for t, owner in
                 enemy_allies])
            actions.append({"action": "remove_ally", "tribe": tribe,
                            "target_faction": owner})
            ally_used = True
        elif pick == "place_warband":
            actions.append({"action": "place_warband"})
        else:
            act, target = pick
            actions.append({"action": act, "target_faction": target})
    if not actions:
        return None, None
    return [region], {"suborn_plan": [{"region": region,
                                       "actions": actions}]}


def _collect_entreat(state, faction, stdin, stdout):
    """Arverni Entreat (§4.3.1): replace/remove enemy Allies or pieces in
    Arverni-Controlled Regions (1 Resource each)."""
    entries = []
    while True:
        regions = _regions_with_pieces(state, faction)
        opts = [(r, r) for r in regions]
        if entries:
            opts.append(("(done)", None))
        region = prompt_choice(stdin, stdout,
                               "Entreat in which Region?", opts)
        if region is None:
            break
        enemy_allies = _enemy_ally_tribes(state, region, faction)
        acts = []
        for t, owner in enemy_allies:
            acts.append((f"replace {owner} Ally at {t} with yours",
                         {"action": "replace_ally", "region": region,
                          "tribe": t, "target_faction": owner}))
            acts.append((f"remove {owner} Ally at {t}",
                         {"action": "remove_ally", "region": region,
                          "tribe": t, "target_faction": owner}))
        for f in _enemies_in_region(state, region, faction):
            for pt in (WARBAND, AUXILIA):
                if count_pieces(state, region, f, pt) > 0:
                    acts.append(
                        (f"replace a {f} {pt} with your Warband",
                         {"action": "replace_piece", "region": region,
                          "piece_type": pt, "target_faction": f}))
        if not acts:
            stdout.write(f"  (no Entreat target in {region})\n")
            if entries:
                break
            return None, None
        acts.append(("(cancel this Region)", None))
        pick = prompt_choice(stdin, stdout, f"Entreat action in {region}:",
                             acts)
        if pick is not None:
            entries.append(pick)
        if not prompt_yes_no(stdin, stdout, "Entreat in another Region?",
                             default=False):
            break
    if not entries:
        return None, None
    return entries, None      # plan rides in sa_regions


def _collect_rampage(state, faction, stdin, stdout):
    """Belgic Rampage (§4.5.2): Regions with Hidden Belgic Warbands and an
    enemy; each entry names the target Faction."""
    from fs_bot.rules_consts import HIDDEN
    from fs_bot.board.pieces import count_pieces_by_state
    cands = [r for r in _regions_with_pieces(state, faction)
             if count_pieces_by_state(state, r, faction, WARBAND,
                                      HIDDEN) > 0
             and _enemies_in_region(state, r, faction)]
    if not cands:
        return None, None
    picked = _pick_regions(stdin, stdout, "Rampage in which Region(s)?",
                           cands)
    entries = []
    for r in picked:
        target = prompt_choice(stdin, stdout, f"  Rampage target in {r}?",
                               [(f, f) for f in
                                _enemies_in_region(state, r, faction)])
        entries.append({"region": r, "target": target})
    if not entries:
        return None, None
    return entries, None      # plan rides in sa_regions


def _collect_intimidate(state, faction, stdin, stdout):
    """German Intimidate (A4.6.2): flip Hidden Warbands to remove that many
    pieces of ONE Faction per Region (1-2 per Region)."""
    from fs_bot.rules_consts import HIDDEN, ALLY
    from fs_bot.board.pieces import count_pieces_by_state
    cands = [r for r in _regions_with_pieces(state, faction)
             if count_pieces_by_state(state, r, faction, WARBAND,
                                      HIDDEN) > 0
             and _enemies_in_region(state, r, faction)]
    if not cands:
        return None, None
    picked = _pick_regions(stdin, stdout,
                           "Intimidate in which Region(s)?", cands)
    plan = []
    for r in picked:
        target = prompt_choice(stdin, stdout,
                               f"  Intimidate which Faction in {r}?",
                               [(f, f) for f in
                                _enemies_in_region(state, r, faction)])
        flips = min(2, count_pieces_by_state(state, r, faction, WARBAND,
                                             HIDDEN))
        for _ in range(flips):
            pts = [(pt, pt) for pt in (WARBAND, AUXILIA, ALLY)
                   if count_pieces(state, r, target, pt) > 0]
            if not pts:
                break
            pts.append(("(stop here)", None))
            pt = prompt_choice(stdin, stdout,
                               f"  Remove which {target} piece in {r}?",
                               pts)
            if pt is None:
                break
            plan.append({"region": r, "target_faction": target,
                         "target_piece": pt, "target_state": None})
    if not plan:
        return None, None
    return picked, {"intimidate_plan": plan}


def _collect_enlist(state, faction, stdin, stdout):
    """Belgic Enlist (§4.5.1): one free Germanic sub-Command."""
    sub = prompt_choice(stdin, stdout, "Enlist the Germans to:",
                        [("Battle", "german_battle"),
                         ("March", "german_march"),
                         ("hide (flip Warbands Hidden)",
                          "german_march_hide"),
                         ("Rally", "german_rally"),
                         ("Raid", "german_raid")])
    german_regions = _regions_with_pieces(state, GERMANS)
    if not german_regions:
        return None, None
    ed = {"type": sub}
    if sub == "german_march":
        origin = prompt_choice(stdin, stdout, "March Germans FROM:",
                               [(r, r) for r in german_regions])
        dests = list(get_adjacent(origin, state["scenario"]))
        ed["origin"] = origin
        ed["destination"] = prompt_choice(stdin, stdout,
                                          "March Germans TO:",
                                          [(r, r) for r in dests])
        region = origin
    else:
        region = prompt_choice(stdin, stdout, "In which Region?",
                               [(r, r) for r in german_regions])
        ed["region"] = region
    if sub in ("german_battle", "german_raid"):
        enemies = _enemies_in_region(state, region, GERMANS)
        opts = [(f, f) for f in enemies]
        if sub == "german_raid":
            opts.append(("(just gain 1 Resource)", None))
        if not opts:
            return None, None
        ed["target"] = prompt_choice(stdin, stdout,
                                     f"  Target in {region}?", opts)
    if sub == "german_rally":
        subdued = _subdued_tribes(state, region)
        if subdued and prompt_yes_no(stdin, stdout,
                                     "Place a German Ally (else Warbands)?",
                                     default=False):
            ed["place"] = "ally"
            ed["tribe"] = prompt_choice(stdin, stdout,
                                        "Ally which Tribe?",
                                        [(t, t) for t in subdued])
        else:
            ed["place"] = "warbands"
    return [region], {"enlist": ed}


_SA_COLLECTORS = {
    "Suborn": _collect_suborn,
    "Entreat": _collect_entreat,
    "Rampage": _collect_rampage,
    "Intimidate": _collect_intimidate,
    "Enlist": _collect_enlist,
}


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
            collector = _SA_COLLECTORS.get(sa)
            if collector is not None:
                sa_regions, extra = collector(state, faction, stdin, stdout)
                if sa_regions is None:
                    stdout.write(f"  (no legal {sa} plan — Command only)\n")
                    return action
                action["sa"] = sa
                action["sa_regions"] = sa_regions
                if extra:
                    action["details"].update(extra)
            else:
                action["sa"] = sa
                cand = _regions_with_pieces(state, faction)
                if cand:
                    action["sa_regions"] = _pick_regions(
                        stdin, stdout,
                        f"{sa} in which Region(s)? (optional)",
                        cand, at_least_one=False)
    return action


# --------------------------------------------------------------------- #
# Event parameter collection — the human analogue of the NP derivers
# (§8.2.3). Keys a card's handler reads from event_params are extracted
# from its source, then prompted with typed pickers; every key may be
# skipped (the executor reports 'not applicable' and the validation loop
# in menus.prompt_action lets the player re-plan).
# --------------------------------------------------------------------- #

import re as _re

_PARAM_KEY_RE = _re.compile(r'params\.get\("([a-z_0-9]+)"')
_LIST_KEY_RE = _re.compile(
    r"(placement|removal|replacement|move|upgrade)s?$")


def _card_param_keys(state, card_id):
    """Ordered event_params keys the card's handler reads (from source)."""
    import inspect
    from fs_bot.cards import card_effects as ce
    scenario = state.get("scenario")
    handler = None
    try:
        if isinstance(card_id, str) and card_id.startswith("A"):
            handler = ce._ARIOVISTUS_HANDLERS.get(card_id)
        elif isinstance(card_id, int):
            if (scenario in ARIOVISTUS_SCENARIOS
                    and card_id in ce._ARIOVISTUS_TEXT_CHANGE_HANDLERS):
                handler = ce._ARIOVISTUS_TEXT_CHANGE_HANDLERS[card_id]
            else:
                handler = ce._BASE_HANDLERS.get(card_id)
        if handler is None:
            return []
        keys, seen = [], set()
        for k in _PARAM_KEY_RE.findall(inspect.getsource(handler)):
            if k not in seen:
                seen.add(k)
                keys.append(k)
        return keys
    except Exception:
        return []


def _prompt_event_param(state, key, stdin, stdout):
    """Prompt a typed value for one event_params key; None to skip."""
    from fs_bot.rules_consts import (SENATE_UP, SENATE_DOWN, ALLY, CITADEL,
                                     FORT, LEADER)
    regions = get_playable_regions(state["scenario"],
                                   state.get("capabilities"))
    k = key.lower()
    skip = ("(skip)", "__skip__")

    def _pick(prompt, opts):
        v = prompt_choice(stdin, stdout, prompt, list(opts) + [skip])
        return None if v == "__skip__" else v

    if "direction" in k:
        return _pick(f"{key}:", [("Uproar (up)", SENATE_UP),
                                 ("Adulation (down)", SENATE_DOWN)])
    if "factions" in k:
        out = []
        while True:
            v = _pick(f"{key} (add one):", [(f, f) for f in FACTIONS
                                            if f not in out])
            if v is None:
                break
            out.append(v)
        return out or None
    if "faction" in k:
        return _pick(f"{key}:", [(f, f) for f in FACTIONS])
    if "tribe" in k or "city" in k or "colony" in k:
        tribes = sorted(state.get("tribes", {}))
        return _pick(f"{key}:", [(t, t) for t in tribes])
    if ("count" in k or "to_remove" in k or k.startswith("legions_")
            or "from_track" in k or "from_fallen" in k):
        return _pick(f"{key}:", [(str(n), n) for n in range(9)])
    if _LIST_KEY_RE.search(k):
        entries = []
        is_move = "move" in k
        while prompt_yes_no(stdin, stdout,
                            f"Add a {key} entry?", default=not entries):
            e = {}
            if is_move:
                e["from_region"] = prompt_choice(
                    stdin, stdout, "  from Region:",
                    [(r, r) for r in regions])
                e["to_region"] = prompt_choice(
                    stdin, stdout, "  to Region:",
                    [(r, r) for r in regions])
            else:
                e["region"] = prompt_choice(
                    stdin, stdout, "  Region:", [(r, r) for r in regions])
            e["piece_type"] = prompt_choice(
                stdin, stdout, "  piece type:",
                [(pt, pt) for pt in (WARBAND, AUXILIA, LEGION, ALLY,
                                     CITADEL, FORT, LEADER)])
            e["count"] = prompt_choice(
                stdin, stdout, "  count:", [(str(n), n) for n in
                                            range(1, 9)])
            entries.append(e)
        return entries or None
    if "regions" in k:
        picked = _pick_regions(stdin, stdout, f"{key}:", list(regions),
                               at_least_one=False)
        return picked or None
    # Default: a single Region (the most common scalar param).
    return _pick(f"{key}:", [(r, r) for r in regions])


def _collect_event_params(state, faction, card_id, shaded, stdin, stdout):
    """event_params for a human Event: standard (derived) choices when
    available and accepted, else per-key typed prompts."""
    from fs_bot.engine.execute import _derive_event_params
    derived = None
    try:
        derived = _derive_event_params(state, faction, card_id, shaded)
    except Exception:
        derived = None
    if derived:
        stdout.write(f"Standard choices for this Event: {derived}\n")
        if prompt_yes_no(stdin, stdout, "Use them?", default=True):
            return dict(derived)
    keys = _card_param_keys(state, card_id)
    params = {}
    for key in keys:
        try:
            v = _prompt_event_param(state, key, stdin, stdout)
        except EOFError:
            break
        if v is not None:
            params[key] = v
    return params


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
        details = {"card_id": card_id, "text_preference": side}
        params = _collect_event_params(
            state, faction, card_id, side == EVENT_SHADED, stdin, stdout)
        if params:
            details["event_params"] = params
        return {"command": "Event", "regions": [], "sa": _SA_NONE,
                "sa_regions": [], "details": details}
    if engine_action in (ACTION_COMMAND, ACTION_COMMAND_SA,
                         ACTION_LIMITED_COMMAND):
        return _collect_command(state, faction, engine_action, stdin, stdout)
    return None
