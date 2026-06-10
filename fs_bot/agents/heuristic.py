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
