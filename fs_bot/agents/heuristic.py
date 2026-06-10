"""Heuristic strategy profiles for the agent interface.

Each profile encodes a falsifiable strategy hypothesis (priors: the Reference
Documents' victory conditions and NP guidelines; flavor: the designer's
InsideGMT faction-strategy articles -- used for strategy priors only, never for
rules decisions) as a plan-building policy that occupies a "human" seat via
``decision_func`` while the NP bots play the other Factions.

Every candidate plan is dry-run through ``moves.validate_player_action`` before
being committed; on failure the policy degrades (next command, drop the SA,
finally Pass), so a profile can never wedge a game.
"""
from __future__ import annotations

import random

import fs_bot.rules_consts as rc
from fs_bot.board.pieces import count_pieces
from fs_bot.engine import moves
from fs_bot.map.map_data import get_adjacent, get_playable_regions

WB, LEG, AUX, ALLY, CIT, FORT, LDR = (rc.WARBAND, rc.LEGION, rc.AUXILIA,
                                      rc.ALLY, rc.CITADEL, rc.FORT, rc.LEADER)


# --------------------------------------------------------------------------- #
# Board arithmetic
# --------------------------------------------------------------------------- #
def force(state, region, faction):
    """Crude force level: Legions heavy, leader bonus, foot pieces 1."""
    f = (count_pieces(state, region, faction, WB)
         + count_pieces(state, region, faction, AUX)
         + 3 * count_pieces(state, region, faction, LEG))
    if count_pieces(state, region, faction, LDR):
        f += 2
    return f


def defense(state, region, faction):
    return (force(state, region, faction)
            + 2 * count_pieces(state, region, faction, CIT)
            + 2 * count_pieces(state, region, faction, FORT))


def _subdued(state, region):
    return moves.subdued_tribes(state, region)


def _mobile(state, region, faction):
    return sum(count_pieces(state, region, faction, t)
               for t in (WB, AUX, LEG))


# --------------------------------------------------------------------------- #
# Plan builders -- mirror fs_bot/cli/human_plan.py collector shapes
# --------------------------------------------------------------------------- #
def build_rally(state, faction, p, single):
    regions = moves.regions_with_pieces(state, faction)
    if not regions:
        return None
    prefer_allies = p.get("rally_allies", True)
    scored = sorted(regions, key=lambda r: (
        -len(_subdued(state, r)) if prefer_allies else 0,
        -count_pieces(state, r, faction, WB),
    ))
    picked = scored[:1 if single else p.get("max_regions", 3)]
    warbands, allies = [], []
    for r in picked:
        sub = _subdued(state, r)
        if prefer_allies and sub:
            allies.append({"region": r, "tribe": sub[0]})
        else:
            warbands.append(r)
    return {"command": "Rally", "regions": [],
            "details": {"rally_plan": {"citadels": [], "allies": allies,
                                       "warbands": warbands}}}


def build_battle(state, faction, p, single):
    cands = []
    for r in moves.battle_regions(state, faction):
        for enemy in moves.enemies_in_region(state, r, faction):
            if enemy in p.get("battle_avoid", ()):
                continue
            edge = force(state, r, faction) - p.get("battle_edge", 2) \
                - defense(state, r, enemy)
            pref = p.get("battle_pref", ())
            bonus = (len(pref) - pref.index(enemy)) * 2 if enemy in pref else 0
            if edge >= 0:
                cands.append((edge + bonus, r, enemy))
    if not cands:
        return None
    cands.sort(reverse=True)
    plan = [{"region": r, "target": t} for _, r, t in cands[:1]]
    return {"command": "Battle", "regions": [],
            "details": {"battle_plan": plan}}


def build_march(state, faction, p, single):
    origins = [r for r in moves.regions_with_pieces(state, faction)
               if _mobile(state, r, faction) > 0]
    if not origins:
        return None
    # Move the single biggest stack toward the highest-scoring destination.
    origin = max(origins, key=lambda r: _mobile(state, r, faction))
    dests = [a for a in get_adjacent(origin, state["scenario"])]
    if not dests:
        return None

    def dest_score(d):
        s = len(_subdued(state, d)) * p.get("march_subdue_w", 1)
        s -= defense(state, d, p["march_foe"]) if p.get("march_foe") else 0
        s += p.get("march_empty_w", 0) * (0 if _mobile(state, d, faction) else 1)
        return s

    dest = max(dests, key=dest_score)
    return {"command": "March", "regions": [],
            "details": {"origins": [origin], "destinations": [dest]}}


def build_raid(state, faction, p, single):
    regions = [r for r in moves.regions_with_pieces(state, faction)
               if count_pieces(state, r, faction, WB) > 0]
    if not regions:
        return None
    plan = []
    for r in regions[:1 if single else 2]:
        enemies = [e for e in moves.enemies_in_region(state, r, faction)
                   if state.get("resources", {}).get(e, 0) > 0]
        plan.append({"region": r, "target": enemies[0] if enemies else None})
    return {"command": "Raid", "regions": [], "details": {"raid_plan": plan}}


def build_recruit(state, faction, p, single):
    cand = [r for r in get_playable_regions(state["scenario"],
                                            state.get("capabilities"))
            if count_pieces(state, r, rc.ROMANS) > 0]
    if not cand:
        return None
    cand.sort(key=lambda r: -len(_subdued(state, r)))
    plan = []
    for r in cand[:1 if single else p.get("max_regions", 2)]:
        sub = _subdued(state, r)
        if sub and p.get("recruit_allies", True):
            plan.append({"region": r, "action": "place_ally", "tribe": sub[0]})
        else:
            plan.append({"region": r, "action": "place_auxilia"})
    return {"command": "Recruit", "regions": [],
            "details": {"recruit_plan": plan}}


def build_seize(state, faction, p, single):
    from fs_bot.commands.seize import get_dispersible_tribes
    cand = [r for r in get_playable_regions(state["scenario"],
                                            state.get("capabilities"))
            if count_pieces(state, r, rc.ROMANS) > 0]
    if not cand:
        return None
    cand.sort(key=lambda r: -(len(_subdued(state, r))
                              + len(get_dispersible_tribes(state, r))))
    picked = cand[:1 if single else p.get("max_regions", 2)]
    disperse = [r for r in picked if get_dispersible_tribes(state, r)
                and p.get("disperse", True)]
    return {"command": "Seize", "regions": [],
            "details": {"_regions": picked, "disperse_regions": disperse}}


_BUILDERS = {"Rally": build_rally, "Battle": build_battle, "March": build_march,
             "Raid": build_raid, "Recruit": build_recruit, "Seize": build_seize}


# --------------------------------------------------------------------------- #
# SA attachment
# --------------------------------------------------------------------------- #
def _sa_regions_for(state, faction, sa, p):
    if sa in ("Devastate",):
        own = [r for r in moves.regions_with_pieces(state, faction)
               if count_pieces(state, r, faction, WB) >= 2]
        return own[:1]
    if sa in ("Build", "Trade"):
        return []
    if sa in ("Suborn", "Entreat"):
        cands = [r for r in moves.regions_with_pieces(state, faction)
                 if moves.enemies_in_region(state, r, faction)]
        return cands[:1]
    if sa in ("Rampage", "Enlist", "Scout", "Ambush"):
        return []
    return []


# --------------------------------------------------------------------------- #
# Profiles
# --------------------------------------------------------------------------- #
PROFILES = {
    # Romans -- methodical pacification vs army-hunting
    "R-PACIFY": {
        "faction": rc.ROMANS,
        "commands": ["Seize", "Recruit", "March", "Battle"],
        "sa": "Build", "battle_edge": 3, "recruit_allies": True,
        "disperse": True, "march_foe": rc.ARVERNI, "march_subdue_w": 2,
        "battle_pref": (rc.ARVERNI, rc.BELGAE),
    },
    "R-HUNT": {
        "faction": rc.ROMANS,
        "commands": ["Battle", "March", "Seize", "Recruit"],
        "sa": "Scout", "battle_edge": 0,
        "battle_pref": (rc.ARVERNI, rc.BELGAE, rc.GERMANS),
        "march_foe": rc.ARVERNI, "march_subdue_w": 0,
    },
    # Arverni -- devastate/attrition vs direct battle
    "A-DEVASTATE": {
        "faction": rc.ARVERNI,
        "commands": ["Rally", "Raid", "March", "Battle"],
        "sa": "Devastate", "rally_allies": True, "battle_edge": 4,
        "battle_pref": (rc.ROMANS, rc.AEDUI), "march_foe": rc.ROMANS,
    },
    "A-BATTLE": {
        "faction": rc.ARVERNI,
        "commands": ["Battle", "Rally", "March", "Raid"],
        "sa": "Entreat", "rally_allies": False, "battle_edge": 0,
        "battle_pref": (rc.ROMANS, rc.AEDUI), "march_foe": rc.ROMANS,
    },
    # Aedui -- quiet suborn growth vs militarized play
    "AE-SUBORN": {
        "faction": rc.AEDUI,
        "commands": ["Rally", "Raid", "March", "Battle"],
        "sa": "Suborn", "rally_allies": True, "battle_edge": 4,
        "battle_avoid": (rc.ROMANS,), "battle_pref": (rc.ARVERNI,),
        "march_foe": rc.ARVERNI,
    },
    "AE-ARMY": {
        "faction": rc.AEDUI,
        "commands": ["Battle", "Rally", "March", "Raid"],
        "sa": "Trade", "rally_allies": False, "battle_edge": 1,
        "battle_avoid": (rc.ROMANS,), "battle_pref": (rc.ARVERNI, rc.BELGAE),
        "march_foe": rc.ARVERNI,
    },
    # Belgae -- control spread vs rampage aggression
    "B-CONTROL": {
        "faction": rc.BELGAE,
        "commands": ["Rally", "March", "Raid", "Battle"],
        "sa": "Enlist", "rally_allies": True, "battle_edge": 3,
        "battle_pref": (rc.ROMANS, rc.AEDUI),
        "march_foe": rc.ROMANS, "march_empty_w": 3, "march_subdue_w": 2,
    },
    "B-RAMPAGE": {
        "faction": rc.BELGAE,
        "commands": ["Battle", "March", "Rally", "Raid"],
        "sa": "Rampage", "rally_allies": False, "battle_edge": 0,
        "battle_pref": (rc.ROMANS, rc.AEDUI),
        "march_foe": rc.ROMANS,
    },
}


# --------------------------------------------------------------------------- #
# Policy: candidate plans -> validate -> degrade -> Pass
# --------------------------------------------------------------------------- #
def plan_turn(state, faction, profile, options, position):
    """Return a decision dict for decision_func."""
    from fs_bot.engine.game_engine import ACTION_PASS, ACTION_COMMAND, \
        ACTION_COMMAND_SA, ACTION_LIMITED_COMMAND
    cmd_action = None
    single = False
    if ACTION_COMMAND_SA in options or ACTION_COMMAND in options:
        cmd_action = ACTION_COMMAND
    elif ACTION_LIMITED_COMMAND in options:
        cmd_action = ACTION_LIMITED_COMMAND
        single = True
    if cmd_action is None:
        return {"action": ACTION_PASS}
    can_sa = ACTION_COMMAND_SA in options

    legal = set(moves.legal_commands(faction))
    for cmd in profile["commands"]:
        if cmd not in legal:
            continue
        pa = _BUILDERS[cmd](state, faction, profile, single)
        if pa is None:
            continue
        # Try with the profile's SA first, then without.
        sa = profile.get("sa")
        attempts = []
        if sa and can_sa and not single:
            attempts.append(({**pa, "sa": sa,
                              "sa_regions": _sa_regions_for(state, faction,
                                                            sa, profile)},
                             ACTION_COMMAND_SA))
        attempts.append(({**pa, "sa": "No SA", "sa_regions": []}, cmd_action))
        for cand, act in attempts:
            try:
                ok, info = moves.validate_player_action(state, faction, cand)
            except Exception:
                ok = False
            if ok:
                return {"action": act, "player_action": cand}
    return {"action": ACTION_PASS}


class RandomPlanPolicy:
    """Control policy: random command, random regions, validated; else Pass."""

    def __init__(self, faction, seed=0):
        self.faction = faction
        self.rng = random.Random(seed)

    def plan_turn(self, state, faction, options, position):
        from fs_bot.engine.game_engine import ACTION_PASS, ACTION_COMMAND, \
            ACTION_LIMITED_COMMAND
        cmd_action = (ACTION_COMMAND if ACTION_COMMAND in options else
                      ACTION_LIMITED_COMMAND if ACTION_LIMITED_COMMAND
                      in options else None)
        if cmd_action is None:
            return {"action": ACTION_PASS}
        single = cmd_action == ACTION_LIMITED_COMMAND
        cmds = list(moves.legal_commands(faction))
        self.rng.shuffle(cmds)
        for cmd in cmds:
            p = {"rally_allies": self.rng.random() < 0.5,
                 "battle_edge": -99, "disperse": self.rng.random() < 0.5,
                 "march_foe": None,
                 "march_subdue_w": 1, "max_regions": self.rng.randint(1, 3)}
            builder = _BUILDERS.get(cmd)
            pa = builder(state, faction, p, single) if builder else None
            if pa is None:
                continue
            pa = {**pa, "sa": "No SA", "sa_regions": []}
            try:
                ok, _ = moves.validate_player_action(state, faction, pa)
            except Exception:
                ok = False
            if ok:
                return {"action": cmd_action, "player_action": pa}
        return {"action": ACTION_PASS}


def make_reactive(agent_faction):
    """Sensible reactive defaults: retreat per NP-like caution, refuse help."""
    from fs_bot.engine.agent import RETREAT, AGREEMENT

    def reactive(state, faction, request):
        if faction != agent_faction:
            return None
        if request["kind"] == RETREAT:
            legal = request.get("legal_regions") or []
            return {"retreat": bool(legal), "region": legal[0] if legal else None}
        if request["kind"] == AGREEMENT:
            return False
        return None
    return reactive


# --------------------------------------------------------------------------- #
# AE-DEEP: state-scored, Suborn-centric Aedui planner.
#
# Aedui victory (7.2): own Allies+Citadels must exceed EVERY other Faction's.
# The seat therefore plays a positional race: grow own Allies/Citadels via
# Rally, and use Suborn (4.4.2 -- accompanies Rally/March/Raid, one Region
# with a Hidden Aedui Warband; 2 Resources per Ally, 1 per Warband/Auxilia,
# max 3 pieces, max 1 Ally) to simultaneously add own Allies and strip the
# current leader's. Targeting follows the NP priorities (8.6.3): place own
# Ally; else remove an Ally of the enemy with the most Allies+Citadels;
# place own Warbands; remove enemy Warbands (Arverni, Belgae, Germans);
# remove Auxilia. Trade is the fallback SA when no Suborn Region exists.
# --------------------------------------------------------------------------- #
from fs_bot.board.pieces import count_pieces_by_state
from fs_bot.rules_consts import (HIDDEN as _HIDDEN, TRIBE_TO_CITY,
                                 GERMANS as _GERMANS)


def _ac_by_faction(state):
    """Allies + Citadels per faction (Forts don't count -- 7.2).

    Uses the engine's own victory counter: ``state["tribes"]`` is the
    authoritative record of alliances (space ALLY pieces can drift out of
    sync with it -- see the tribe/piece sync issue in QUESTIONS.md).
    """
    from fs_bot.engine.victory import _count_allies_and_citadels
    out = {}
    for fac in (rc.ROMANS, rc.ARVERNI, rc.AEDUI, rc.BELGAE, _GERMANS):
        try:
            out[fac] = _count_allies_and_citadels(state, fac)
        except Exception:
            out[fac] = 0
    return out


def _allied_tribes_in_region(state, region, faction):
    """Tribes in *region* currently allied to *faction* (tribes dict)."""
    from fs_bot.map.map_data import get_tribes_in_region
    out = []
    try:
        tribes = get_tribes_in_region(region, state["scenario"])
    except Exception:
        return out
    for t in tribes:
        if state.get("tribes", {}).get(t, {}).get("allied_faction") == faction:
            out.append(t)
    return out


def _hidden_wb(state, region, faction):
    try:
        return count_pieces_by_state(state, region, faction, WB, _HIDDEN)
    except Exception:
        return 0


def _enemy_ally_factions(state, region, exclude=(rc.AEDUI,)):
    out = []
    for fac in (rc.ARVERNI, rc.BELGAE, rc.ROMANS, _GERMANS):
        if fac in exclude:
            continue
        if _allied_tribes_in_region(state, region, fac):
            out.append(fac)
    return out


def build_suborn_plan(state, budget):
    """Best single-region Suborn: (region, actions, cost, score) or None."""
    ac = _ac_by_faction(state)
    rivals = sorted((f for f in ac if f != rc.AEDUI),
                    key=lambda f: -ac[f])
    best = None
    for region in moves.regions_with_pieces(state, rc.AEDUI):
        if _hidden_wb(state, region, rc.AEDUI) < 1:
            continue
        actions, cost, score, pieces = [], 0, 0, 0
        # 1. Place own Ally at a Subdued Tribe (2 Resources).
        sub = _subdued(state, region)
        if sub and cost + 2 <= budget:
            actions.append({"action": "place_ally", "tribe": sub[0]})
            cost += 2; score += 30; pieces += 1
        else:
            # 2. Remove the leading rival's Ally here (max 1 Ally total).
            present = _enemy_ally_factions(state, region)
            for rival in rivals:
                if rival in present and cost + 2 <= budget:
                    rt = _allied_tribes_in_region(state, region, rival)
                    actions.append({"action": "remove_ally",
                                    "target_faction": rival,
                                    "tribe": rt[0] if rt else None})
                    cost += 2; score += 20 + ac[rival]; pieces += 1
                    break
        # 3/4. Fill remaining slots: own Warbands in, rival Warbands out.
        while pieces < 3 and cost + 1 <= budget:
            placed = False
            if state.get("available", {}).get(rc.AEDUI, {}).get(WB, 1) or True:
                actions.append({"action": "place_warband"})
                cost += 1; score += 2; pieces += 1
                placed = True
            if not placed:
                break
        for rival in (rc.ARVERNI, rc.BELGAE, _GERMANS):
            if pieces >= 3 or cost + 1 > budget:
                break
            if count_pieces(state, region, rival, WB) > 0:
                actions.append({"action": "remove_warband",
                                "target_faction": rival})
                cost += 1; score += 4; pieces += 1
        if actions and (best is None or score > best[3]):
            best = (region, actions, cost, score)
    return best


def build_rally_deep(state, budget, max_regions=3):
    """Citadel upgrades first, then Allies at Subdued Tribes, then Warbands."""
    citadels, allies, warbands = [], [], []
    spent = 0
    regions = moves.regions_with_pieces(state, rc.AEDUI)
    # 1. Citadel: replace an Aedui-Allied City Tribe (score +0 net Ally->
    #    Citadel keeps the count but hardens it; prefer when safe budget).
    for region in regions:
        if spent + 1 > budget or len(citadels) >= 1:
            break
        for tribe, city in TRIBE_TO_CITY.items():
            tin = state["tribes"].get(tribe, {})
            if (tin.get("allied_faction") == rc.AEDUI
                    and count_pieces(state, region, rc.AEDUI, CIT) == 0
                    and tribe in (moves.subdued_tribes(state, region) or [tribe])
                    or tin.get("allied_faction") == rc.AEDUI):
                from fs_bot.map.map_data import get_tribes_in_region
                try:
                    if tribe in get_tribes_in_region(region,
                                                     state["scenario"]):
                        citadels.append({"region": region, "tribe": tribe})
                        spent += 1
                        break
                except Exception:
                    continue
    # 2. Allies at Subdued Tribes, highest-value regions first.
    scored = sorted(regions, key=lambda r: -len(_subdued(state, r)))
    for region in scored:
        if len(citadels) + len(allies) >= max_regions or spent + 1 > budget:
            break
        sub = _subdued(state, region)
        if sub and not any(a["region"] == region for a in allies):
            allies.append({"region": region, "tribe": sub[0]})
            spent += 1
    # 3. Warbands where cap allows, to seed future Suborn.
    for region in scored:
        total = len(citadels) + len(allies) + len(warbands)
        if total >= max_regions or spent + 1 > budget:
            break
        if (count_pieces(state, region, rc.AEDUI, ALLY)
                + count_pieces(state, region, rc.AEDUI, CIT)) > 0 \
                and region not in warbands \
                and not any(a["region"] == region for a in allies) \
                and not any(c["region"] == region for c in citadels):
            warbands.append(region)
            spent += 1
    if not (citadels or allies or warbands):
        return None, 0
    return {"citadels": citadels, "allies": allies,
            "warbands": warbands}, spent


def build_march_seed(state):
    """March one Hidden Warband stack toward the leading rival's Allies,
    to create future Suborn Regions."""
    ac = _ac_by_faction(state)
    rivals = sorted((f for f in ac if f != rc.AEDUI), key=lambda f: -ac[f])
    origins = [r for r in moves.regions_with_pieces(state, rc.AEDUI)
               if count_pieces(state, r, rc.AEDUI, WB) > 1]
    best = None
    for origin in origins:
        for dest in get_adjacent(origin, state["scenario"]):
            if _hidden_wb(state, dest, rc.AEDUI) > 0:
                continue
            score = 0
            for rank, rival in enumerate(rivals):
                if _allied_tribes_in_region(state, dest, rival):
                    score += 10 - 2 * rank
            score += len(_subdued(state, dest)) * 3
            if score > 0 and (best is None or score > best[2]):
                best = (origin, dest, score)
    if best is None:
        return None
    return {"command": "March", "regions": [],
            "details": {"origins": [best[0]], "destinations": [best[1]]}}


def plan_turn_aedui_deep(state, faction, options, position):
    """Decision function body for the AE-DEEP profile."""
    from fs_bot.engine.game_engine import ACTION_PASS, ACTION_COMMAND, \
        ACTION_COMMAND_SA, ACTION_LIMITED_COMMAND
    cmd_action = None
    single = False
    if ACTION_COMMAND_SA in options or ACTION_COMMAND in options:
        cmd_action = ACTION_COMMAND
    elif ACTION_LIMITED_COMMAND in options:
        cmd_action = ACTION_LIMITED_COMMAND
        single = True
    if cmd_action is None:
        return {"action": ACTION_PASS}
    can_sa = ACTION_COMMAND_SA in options and not single

    res = state.get("resources", {}).get(rc.AEDUI, 0)
    # Suborn gets the full budget: a Suborned Ally both scores for the Aedui
    # and denies Rome a Subdued tribe, and Raid (the fallback carrier) costs
    # nothing.
    suborn = build_suborn_plan(state, res) if can_sa else None
    # Only Suborn when it moves the Ally race (places own Ally or removes a
    # rival's). Warband-only Suborns burn Resources without touching any
    # victory margin -- and the score encodes that: ally actions are >= 20.
    if suborn and suborn[3] < 20:
        suborn = None

    candidates = []
    rally_budget = max(0, res - (suborn[2] if suborn else 0))
    rally_plan, _ = build_rally_deep(state, rally_budget,
                                     max_regions=1 if single else 3)
    rally_scores = bool(rally_plan and (rally_plan["citadels"]
                                        or rally_plan["allies"]))
    p = {"rally_allies": True, "battle_edge": 99, "march_foe": None,
         "march_subdue_w": 1}
    raid = build_raid(state, rc.AEDUI, p, single)
    m = build_march_seed(state)

    # Carrier order. With a scoring Suborn in hand: Rally (if it also
    # scores) > March > Raid. Without one: March Hidden Warbands toward the
    # next Suborn target (Raid would Reveal them, killing future Suborns),
    # with Trade as the income SA; Raid only as a last resort when broke.
    rally_cand = ({"command": "Rally", "regions": [],
                   "details": {"rally_plan": rally_plan}}
                  if rally_plan else None)
    if suborn:
        if rally_scores:
            candidates.append(rally_cand)
        if m:
            candidates.append(m)
        if raid:
            candidates.append(raid)
        if rally_cand and not rally_scores:
            candidates.append(rally_cand)
    else:
        if rally_scores:
            candidates.append(rally_cand)
        if m:
            candidates.append(m)
        if res <= 2 and raid:
            candidates.append(raid)
        if rally_cand and not rally_scores:
            candidates.append(rally_cand)
        if raid and raid not in candidates:
            candidates.append(raid)

    for cand in candidates:
        attempts = []
        if can_sa and suborn and cand["command"] in ("Rally", "March", "Raid"):
            attempts.append(({**cand, "sa": "Suborn",
                              "sa_regions": [suborn[0]],
                              "details": {**cand["details"],
                                          "suborn_plan": [
                                              {"region": suborn[0],
                                               "actions": suborn[1]}]}},
                             ACTION_COMMAND_SA))
        if can_sa:
            attempts.append(({**cand, "sa": "Trade", "sa_regions": []},
                             ACTION_COMMAND_SA))
        attempts.append(({**cand, "sa": "No SA", "sa_regions": []},
                         cmd_action))
        for pa, act in attempts:
            try:
                ok, _info = moves.validate_player_action(state, rc.AEDUI, pa)
            except Exception:
                ok = False
            if ok:
                return {"action": act, "player_action": pa}
    return {"action": ACTION_PASS}


PROFILES["AE-DEEP"] = {
    "faction": rc.AEDUI,
    "planner": plan_turn_aedui_deep,
    "commands": ["Rally", "Raid", "March", "Battle"],   # for tooling display
    "sa": "Suborn",
}
