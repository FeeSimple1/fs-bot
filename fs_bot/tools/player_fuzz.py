"""Player-action fuzzer — random-legal players in random seats vs the NP bots.

The error census exercises only BOT decisions. This tool fuzzes the
human-facing surface: each game seats a random subset of factions as
"players" driven by RandomPlanPolicy (random command, random regions,
pre-validated via moves.validate_player_action) with fully randomized
reactive decisions (Retreat, Loss order, Agreements) through the
decision-agent hook. Seated factions are removed from
state["non_player_factions"], so player-vs-NP code paths (e.g. the Aedui
Trade Roman-agreement consult, German player-target priorities, the Quarters
roll-all default for a player Rome) are genuinely exercised.

Oracles, per game:
  crash          — run_game raised. Hard defect.
  structural     — check_structural_integrity violation at any turn boundary
                   or at game end (silent-corruption class). Hard defect.
  divergence     — a seated player's chosen plan was dry-run at decision
                   time (moves.validate_player_action) and the LIVE execution
                   produced a different outcome signature (executed flag,
                   error set, SA outcome). Dry-run and live see the same
                   state and rng, so any divergence means hidden global
                   state or set-iteration nondeterminism. Hard defect.
                   (Sub-action errors present in BOTH dry-run and live are
                   the random policy's own sloppiness — partial-execution
                   semantics, reported as the soft "partial" count.)
                   Rejected Commands are compared at the rejection callback
                   and replanned without consuming a turn. Matching dry/live
                   refusals are policy mistakes, not engine crashes.
                   The dry-run installs a CLONE of the reactive agent with a
                   cloned rng state — moves.validate_player_action's own
                   agent-stripped dry-run would legitimately diverge wherever
                   resolution consults an agreement (e.g. Recruit supply-line
                   cost, Harassment), which is table-accurate behaviour, not
                   a defect.
  nondeterminism — the same (scenario, seed) replayed from scratch produced a
                   different end digest. Hard defect (CLAUDE.md determinism).
  bot-event-rejected — an NPC-selected Event was explicitly rejected by its
                   executor. Hard defect even if state is unchanged and
                   replay agrees: NPCs must avoid ineffective/forbidden
                   Events (§8.1.1/8.2.1). Optional declines are not rejections.

All seat/reactive randomness derives from random.Random(str) (sha512-based),
so results are reproducible across processes and PYTHONHASHSEED values; the
printed batch digest must be identical across hashseeds.

Player EVENT fuzzing: seated players also play Events (~50% of turns where
the SoP allows) with fuzzed ``event_params``: NP-derived (well-formed),
mutated-derived, SCHEMA-generated (typed values for every key and entry
field the handler reads, via cards.param_schema — the success-path
generator for the ~90 cards without an NP deriver), or generated from
scratch against the param-key inventory harvested from card_effects.py
source (the failure-path generator). Every generated param set is dry-run
in an isolated sim first with two extra oracles:
  event-crash — the handler raised outside the _EVENT_SAFE_ERRORS contract
                ("report, do not crash"). Hard defect.
  dirty-event — the handler reported not-applicable (executed=False) but
                MUTATED the board (half-applied event). Hard defect: the
                report-don't-crash contract requires validate-before-mutate.
Dud param sets (dry-run not-applicable) are still submitted live ~30% of
the time to fuzz the live not-applicable path; otherwise the policy falls
back to a random Command.

    python -m fs_bot.tools.player_fuzz --seeds 1-20
    python -m fs_bot.tools.player_fuzz --seeds 1-20 --scenario "The Great Revolt"
"""
from __future__ import annotations

import argparse
import contextlib
import copy
import hashlib
import io
import json
import random
from collections import Counter

import re

import fs_bot.rules_consts as rc
from fs_bot.state.setup import setup_scenario
from fs_bot.engine.game_engine import (
    run_game, ACTION_EVENT, ACTION_PASS, get_sop_factions,
)
from fs_bot.engine.agent import RETREAT, LOSS_ORDER, AGREEMENT, HARASSMENT_LOSS
from fs_bot.bots.bot_dispatch import dispatch_bot_turn
from fs_bot.cli.dispatcher import _translate_bot_action
from fs_bot.agents.heuristic import RandomPlanPolicy
from fs_bot.state.state_schema import check_structural_integrity
from fs_bot.cards.edition import CARD_EDITIONS
from fs_bot.tools.validation_metadata import parse_seed_range, validation_metadata

ALL_SCENARIOS = (rc.SCENARIO_PAX_GALLICA, rc.SCENARIO_GREAT_REVOLT,
                 rc.SCENARIO_RECONQUEST, rc.SCENARIO_ARIOVISTUS,
                 rc.SCENARIO_GALLIC_WAR)

# Deliberately malformed plans must not trap a fuzzed game in a replan loop.
_MAX_REJECTED_PLANS = 8


def _pick_seats(factions, rng):
    """Random non-empty subset of ``factions`` (order-stable draw)."""
    seats = [f for f in factions if rng.random() < 0.5]
    if not seats:
        seats = [factions[rng.randrange(len(factions))]]
    return seats


def make_random_reactive(seats, rng):
    """Randomized reactive decisions for the seated factions.

    RETREAT: uniformly no-retreat or one of the legal regions.
    LOSS_ORDER: a random permutation; 25% of the time a random truncation
        (exercises the engine's fill-in default for unlisted pieces).
    AGREEMENT: coin flip (exercises both branches of every negotiation).
    HARASSMENT_LOSS: uniformly choose among the current legal options.
    DIVICIACUS_PIECES: random legal counts of each physical owner's counters.
    FIXED_EVENT_BATTLE: a random offered Region/defender pair, retaining the
        Event's mandatory follow-on and engine-owned modifiers.
    CAMULOGENUS: Roman acceptance and legal native groups/routes, with a
        shared four-Legion budget; physical formation choices remain separate.
    """
    def reactive(state, faction, request):
        if faction not in seats:
            return None
        kind = request.get("kind")
        if (kind == "free_action" and request.get("request_type") == "roman_event_accept"
                and request.get("card_id") == 70):
            return {"accept": True} if rng.random() >= 0.25 else {"decline": True}
        if kind == "free_action" and request.get("request_type") == "german_guided_march":
            from fs_bot.cards.german_guidance import destinations
            sources=list(request['origins'].items())
            rng.shuffle(sources)
            marches=[]
            for origin,maximum in sources[:rng.randint(0,min(len(sources),request['max_origins']))]:
                n=rng.randint(1 if request.get('moving_groups_only') else 0,maximum)
                legal=destinations(state,origin,n) if n else []
                if n and not legal:
                    if request.get('moving_groups_only'):
                        continue
                    n=0
                marches.append({'origin':origin,'warbands':n,'destination':rng.choice(legal) if n else None})
            return {'marches':marches}
        if kind == "free_action" and request.get("request_type") == "german_guided_ambush":
            region=rng.choice(sorted(request['defenders_by_region']))
            return {'region':region,'defender':rng.choice(request['defenders_by_region'][region])}
        if kind == "free_action" and request.get("request_type") == "circumvallation_march":
            from fs_bot.cards.circumvallation import pools,routes
            if rng.random()<0.25:
                return {'decline':True}
            destination=rng.choice(request['destinations'])
            sources=list(pools(state).items());rng.shuffle(sources)
            marches=[]
            for origin,pool in sources:
                legions=rng.randint(0,pool[rc.LEGION]);auxilia=rng.randint(0,pool[rc.AUXILIA])
                leader=bool(pool[rc.LEADER] and rng.random()<0.5)
                selected={rc.LEGION:legions,rc.AUXILIA:auxilia,rc.LEADER:pool[rc.LEADER] if leader else None}
                if (legions or auxilia or leader) and routes(state,origin,destination,selected):
                    marches.append({'origin':origin,'legions':legions,'auxilia':auxilia,'leader':leader})
            return {'destination':destination,'marches':marches}
        if kind == "free_action" and request.get("request_type") == "aduatuca_march":
            destination = rng.choice(request['destinations'])
            sources = list(request['origins_by_destination'][destination].items())
            rng.shuffle(sources)
            return {'destination': destination, 'marches': [
                {'origin': origin, 'warbands': rng.randint(0, maximum)}
                for origin, maximum in sources if rng.random() < 0.7]}
        if kind == "free_action" and request.get("request_type") == "mons_cevenna_march":
            from fs_bot.cards.mons_cevenna import pools, routes
            options = []
            for origin, pool in pools(state, faction).items():
                if not any(pool.values()):
                    continue
                group = {piece: rng.randint(0, pool[piece])
                         for piece in (rc.LEGION, rc.AUXILIA, rc.WARBAND)}
                group[rc.LEADER] = bool(pool[rc.LEADER] and rng.random() < 0.5)
                if not any(group.values()):
                    group = {piece: pool[piece] for piece in
                             (rc.LEGION, rc.AUXILIA, rc.WARBAND)}
                    group[rc.LEADER] = bool(pool[rc.LEADER])
                actual = dict(group, **{rc.LEADER: pool[rc.LEADER] if group[rc.LEADER] else None})
                options.extend({'origin': origin, 'destination': path[0], 'group': group}
                               for path in routes(state, faction, origin, actual))
            if options:
                return rng.choice(options)
            return {'origin': None, 'destination': rng.choice(request['allowed_regions']), 'group': {}}
        if kind == "free_action" and request.get("request_type") == "camulogenus_march":
            from fs_bot.cards.camulogenus import origin_groups, march_routes
            destination = rng.choice(sorted(request["destinations"]))
            pools = origin_groups(state)
            origins = sorted(pools)
            rng.shuffle(origins)
            remaining = request["legion_limit"]
            marches = []
            for origin in origins:
                pool = pools[origin]
                legions = rng.randint(0, min(pool['legions'], remaining))
                auxilia = rng.randint(0, pool['auxilia'])
                caesar = bool(pool['caesar'] and rng.random() < 0.5)
                if not (legions or auxilia or caesar):
                    continue
                group = {rc.LEGION: legions, rc.AUXILIA: auxilia,
                         rc.LEADER: rc.CAESAR if caesar else None}
                routes = march_routes(state, origin, group, destination)
                if not routes:
                    continue
                marches.append({'origin': origin, 'route': rng.choice(routes),
                                'legions': legions, 'auxilia': auxilia, 'caesar': caesar})
                remaining -= legions
            return {'destination': destination, 'marches': marches}
        if kind == "free_action" and request.get("request_type") == "fixed_event_battle":
            # Exercise the human selection instead of deferring to the NPC
            # default. The trusted request contains the card's legal pairs,
            # including Aquitani's Battle without friendly Forces.
            choices = [(region, defender)
                       for region, defenders in sorted(request["defenders_by_region"].items())
                       for defender in sorted(defenders)]
            region, defender = rng.choice(choices)
            return {"region": region, "defender": defender}
        if kind == 'drought_loss':
            return {'piece': rng.choice(request['targets'])}
        if kind == 'event_piece_choice':
            if request['card_id'] == 31:
                return {'tribe': rng.choice(request['targets'])['tribe']}
            if request['card_id'] == 61 and request['step'] == 'allies':
                faction = rng.choice(request['targets'])['target_faction']
                tribes = [row['tribe'] for row in request['targets'] if row['target_faction'] == faction]
                return {'tribes': rng.sample(tribes, rng.randint(1, len(tribes)))}
            target = {}
            if 'required_by_region' in request:
                amounts = request['required_by_region']
                allies = request.get('ally_tribes_by_region', {})
                candidates = [name for name, count in amounts.items() if count or allies.get(name)]
                region = rng.choice(candidates or list(amounts))
                target['region'] = region
                if request['card_id'] == 'A58':
                    target['ally_tribe'] = rng.choice(allies[region]) if allies[region] else None
                kind = {24: None, 58: rc.WARBAND, 60: None}.get(request['card_id'], rc.AUXILIA)
                request = dict(request, required={kind: amounts[region]},
                               available=[row for row in request['available'] if row['region'] == region])
            if 'required' in request:
                selections = []
                for piece_type, count in request['required'].items():
                    cohorts = [index for index, row in enumerate(request['available'])
                               if piece_type is None or row['piece_type'] == piece_type
                               for _ in range(row['count'])]
                    picked = rng.sample(cohorts, count)
                    for index in dict.fromkeys(picked):
                        selections.append(dict(request['available'][index], count=picked.count(index)))
                return {**target, 'selections': selections}
            if request['card_id'] == 19 and rng.random() < 0.5:
                return {'choice': 'auxilia', 'count': rng.randrange(6)}
            from fs_bot.cards.base_piece_choices import optional_room
            entries, remaining = [], request['max_count']
            for cohort in request['available']:
                room = optional_room(request, entries, cohort['region'], remaining)
                count = rng.randrange(min(room, cohort['count']) + 1)
                if count:
                    entries.append(dict(cohort, count=count))
                    if request['card_id'] == 22:
                        entries[-1]['action'] = rng.choice(('remove', 'replace'))
                    remaining -= count
            return ({'choice': 'warbands', 'removals': entries} if request['card_id'] == 19
                    else {'selections': entries})
        if kind == 'event_up_to':
            if request['card_id'] == 'A40':
                regions = list(request['legal_regions'])
                rng.shuffle(regions)
                return {'regions': regions[:rng.randint(0, request['max_count'])]}
            if request['card_id'] == 'A60':
                return {'count': rng.randint(0, min(4, request['available_count']))}
            remaining, entries = request['max_count'], []
            for entry in request['available']:
                count = rng.randint(0, min(remaining, entry['count']))
                if count:
                    entries.append(dict(entry, count=count))
                    remaining -= count
            return {'removals': entries}
        if kind == 'devastate_losses':
            pieces=[(entry['piece_type'],entry['piece_state']) for entry in request['available']
                    for _ in range(entry['count'])]
            rng.shuffle(pieces);counts={}
            for cell in pieces[:request['count']]:counts[cell]=counts.get(cell,0)+1
            return {'removals':[{'piece_type':cell[0],'piece_state':cell[1],'count':count}
                                for cell,count in counts.items()]}
        if kind == 'interlude_reduction':
            cohorts = list(request['cohorts'])
            rng.shuffle(cohorts)
            from fs_bot.engine.interlude_reductions import is_home_last

            cohorts.sort(key=lambda row: is_home_last(request['stage'], row))
            needed, removals = dict(request['minimums']), []
            for row in cohorts:
                piece_type = row['piece_type']
                count = min(needed[piece_type], row['count'])
                if count:
                    removals.append(dict(row, count=count))
                    needed[piece_type] -= count
            return {'removals': removals}
        if kind == 'interlude_arverni_citadels':
            regions = list(request['regions'])
            rng.shuffle(regions)
            regions.sort(key=lambda region: region == rc.ARVERNI_REGION)
            return {'regions': regions[:request['count']]}
        if kind == 'interlude_aedui_citadel':
            return {'region': rng.choice(request['regions'])}
        if kind == 'interlude_settlements':
            options = request['options']
            regions = rng.sample(list(options), request['required_allies'])
            return {'allies': {region: rng.choice(options[region]) for region in regions}}
        if kind == 'interlude_marker':
            return {'tribe': rng.choice([None] + [row['tribe'] for row in request['markers']])}
        if kind == 'interlude_expedition':
            if not request['can_conduct'] or rng.random() < 0.5:
                return {'conduct': False}
            origins = [region for region, count in request['legions'].items() for _ in range(count)]
            rng.shuffle(origins)
            harvest, legions = {}, {}
            for region in origins[:request['harvest_count']]:
                harvest[region] = harvest.get(region, 0) + 1
            available = origins[request['harvest_count']:]
            count = rng.randint(request['minimum_legions'], len(available))
            for region in available[:count]:
                legions[region] = legions.get(region, 0) + 1
            cohorts = [index for index, row in enumerate(request['auxilia']) for _ in range(row['count'])]
            rng.shuffle(cohorts)
            selected = {}
            for index in cohorts[:rng.randint(request['minimum_auxilia'], len(cohorts))]:
                selected[index] = selected.get(index, 0) + 1
            return {'conduct': True, 'harvest': harvest, 'legions': legions,
                    'auxilia': [dict(request['auxilia'][index], count=count)
                                for index, count in selected.items()]}
        if kind == 'harvest_legions':
            placements = {}
            for _ in range(request['count']):
                region = rng.choice(request['legal_regions'])
                placements[region] = placements.get(region, 0) + 1
            return {'placements': placements}
        if kind == 'besiege_target':
            return {'target': rng.choice(request['targets'])}
        if kind == 'ballistae_target':
            return ({'decline': True} if rng.random() < 0.5
                    else {'target': rng.choice(request['targets'])})
        if kind == 'slingers_region':
            return {'region': rng.choice(request['legal_regions'])}
        if kind == 'horse_region':
            return ({'decline': True} if request['may_decline'] and rng.random() < 0.25
                    else {'region': rng.choice(request['legal_regions'])})
        if kind in ('horse_window', 'capability_window'):
            return {'action': rng.choice(request['actions'])}
        if kind == "raid_intimidate":
            if rng.random() < 0.25:
                return {"decline": True}
            offered = list(request.get("targets") or [])
            if not offered or rng.random() < 0.25:
                return {"targets": []}
            faction = offered[rng.randrange(len(offered))]["target_faction"]
            pieces = []
            for target in offered:
                if target["target_faction"] == faction:
                    pieces.extend([{key: target[key] for key in
                                    ("target_faction", "target_piece", "target_state", "target_tribe")
                                    if key in target}]
                                  * target["available"])
            rng.shuffle(pieces)
            maximum = min(request["max_removals"], len(pieces))
            targets = pieces[:rng.randrange(1, maximum + 1)]
            response = {"targets": targets}
            if (len(targets) > request.get("max_raider_removals", maximum)
                    or (request.get("extra_warband_available") and len(targets) >= 2
                        and rng.random() < 0.5)):
                response["extra_warband"] = True
            return response
        from fs_bot.engine.diviciacus import DIVICIACUS_PIECES
        if kind in ("march_cohort", DIVICIACUS_PIECES):
            from fs_bot.engine.march_choices import VISIBILITIES
            available = request["available"]
            order = VISIBILITIES if kind == "march_cohort" else sorted(available)
            groups = [key for key in order if available.get(key, 0)]
            remaining, counts = request["count"], {}
            for index, key in enumerate(groups):
                minimum = max(0, remaining - sum(available[k] for k in groups[index + 1:]))
                n = rng.randint(minimum, min(remaining, available[key]))
                if n:
                    counts[key] = n
                remaining -= n
            return {"counts": counts}
        if kind == HARASSMENT_LOSS:
            return {"choice": rng.choice(request["options"])}
        if kind == RETREAT:
            legal = list(request.get("legal_regions") or [])
            if request.get('context', {}).get('rampage') and 'pieces' in request:
                pool = list(request['pieces'])
                rng.shuffle(pool)
                destination = rng.choice(legal) if legal else None
                actions = [{'piece_type': piece, 'piece_state': visibility,
                            'action': 'retreat' if destination is not None and rng.random() < 0.5 else 'remove'}
                           for piece, visibility in pool[:request['context']['num_pieces']]]
                if not any(action['action'] == 'retreat' for action in actions):
                    destination = None
                return {'actions': actions, 'retreat_region': destination}
            choices = [None] + legal
            pick = choices[rng.randrange(len(choices))]
            return {"retreat": pick is not None, "region": pick}
        if kind == LOSS_ORDER:
            pieces = list(request.get("pieces") or [])
            rng.shuffle(pieces)
            if pieces and rng.random() < 0.25:
                pieces = pieces[:rng.randrange(1, len(pieces) + 1)]
            return pieces
        if kind == AGREEMENT:
            return rng.random() < 0.5
        return None

    return reactive


def _sanitize(obj):
    """Recursively convert state into JSON-stable primitives (sets sorted,
    unknown leaves stringified) for digesting."""
    if isinstance(obj, dict):
        return {str(k): _sanitize(v) for k, v in sorted(
            obj.items(), key=lambda kv: str(kv[0]))}
    if isinstance(obj, (set, frozenset)):
        return sorted(str(x) for x in obj)
    if isinstance(obj, (list, tuple)):
        return [_sanitize(v) for v in obj]
    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj
    return f"<{type(obj).__name__}>"


def _digest(state, res):
    """Hash the complete saved state, RNG position, and returned trajectory.

    Tagged encoding preserves non-string keys and tuple/set identity. Sort
    encoded dictionary entries as well as ordinary JSON keys so insertion
    order cannot manufacture cross-process differences.
    """
    from fs_bot.state.serialize import encode

    def canonical(value):
        if isinstance(value, list):
            return [canonical(v) for v in value]
        if isinstance(value, dict):
            result = {k: canonical(v) for k, v in value.items()}
            if set(result) == {"__dict__"}:
                result["__dict__"].sort(key=lambda pair: json.dumps(pair[0], sort_keys=True))
            return result
        return value

    persistent = {k: v for k, v in state.items() if k != "decision_agent"}
    body = canonical(encode({"state": persistent, "trajectory": res}))
    blob = json.dumps(body, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


def _sig(ex):
    """Outcome signature of an execution result: executed flag, refusal
    reason, sorted error strings, and the SA execution's flag + errors."""
    if not isinstance(ex, dict):
        return None
    sa = ex.get("sa_execution")
    return (bool(ex.get("executed")),
            str(ex.get("reason") or ""),
            tuple(str(t) for t in ex.get("transfers") or []),
            tuple(sorted(str(e) for e in ex.get("errors") or [])),
            None if not isinstance(sa, dict) else
            (bool(sa.get("executed")),
             tuple(sorted(str(e) for e in sa.get("errors") or []))))


# --------------------------------------------------------------------- #
# Event-param fuzzing
# --------------------------------------------------------------------- #

_PARAM_KEY_RE = re.compile(r'params\.get\("([a-z_0-9]+)"')


def _param_key_pool():
    """Harvest the event-param key inventory from card_effects.py source,
    so the from-scratch generator tracks new cards automatically."""
    import inspect
    import fs_bot.cards.card_effects as ce
    try:
        keys = sorted(set(_PARAM_KEY_RE.findall(inspect.getsource(ce))))
    except Exception:
        keys = []
    return keys or ["region", "target_region", "placements", "removals"]


def _value_pools(state):
    """(regions, factions, tribes) value pools for param generation."""
    return (sorted(state.get("spaces") or ()),
            sorted(rc.FACTIONS),
            sorted(state.get("tribes") or ()))


_PIECE_TYPES = (rc.WARBAND, rc.AUXILIA, rc.LEGION, rc.ALLY, rc.CITADEL,
                rc.FORT)


def _rand_value(key, pools, rng):
    """A random value plausibly typed for ``key`` (by name heuristics)."""
    regions, factions, tribes = pools

    def region():
        return regions[rng.randrange(len(regions))]

    def faction():
        return factions[rng.randrange(len(factions))]

    def tribe():
        return tribes[rng.randrange(len(tribes))]

    k = key.lower()
    if "direction" in k:
        return (rc.SENATE_UP if rng.random() < 0.5 else rc.SENATE_DOWN)
    if "factions" in k:
        return [faction() for _ in range(rng.randrange(1, 3))]
    if "faction" in k:
        return faction()
    if "tribe" in k or "city" in k or "colony" in k:
        return tribe()
    if "piece_type" in k or "place_type" in k:
        return _PIECE_TYPES[rng.randrange(len(_PIECE_TYPES))]
    if ("count" in k or "to_remove" in k or k.startswith("legions_")
            or "from_track" in k or "from_fallen" in k):
        return rng.randrange(0, 5)
    if k.endswith("s") and ("placement" in k or "removal" in k
                            or "replacement" in k or "move" in k
                            or "upgrade" in k):
        return [{"region": region(), "faction": faction(),
                 "piece_type": _PIECE_TYPES[rng.randrange(len(_PIECE_TYPES))],
                 "count": rng.randrange(1, 3), "tribe": tribe()}
                for _ in range(rng.randrange(1, 3))]
    if "regions" in k:
        return [region() for _ in range(rng.randrange(1, 4))]
    return region()


def _scratch_params(key_pool, pools, rng):
    """1-4 random keys with random typed values."""
    n = rng.randrange(1, 5)
    keys = list(key_pool)
    out = {}
    for _ in range(n):
        k = keys[rng.randrange(len(keys))]
        out[k] = _rand_value(k, pools, rng)
    return out


def _mutate_params(params, key_pool, pools, rng):
    """Drop / retype / extend keys of a derived param dict."""
    out = dict(params)
    for k in list(out):
        r = rng.random()
        if r < 0.25:
            out.pop(k)
        elif r < 0.5:
            out[k] = _rand_value(k, pools, rng)
    if rng.random() < 0.25 and key_pool:
        k = key_pool[rng.randrange(len(key_pool))]
        out[k] = _rand_value(k, pools, rng)
    return out


_BOARD_KEYS = ("spaces", "tribes", "resources", "markers", "available",
               "capabilities", "eligibility", "fallen_legions",
               "legions_track", "removed_legions", "removed_pieces",
               "senate", "at_war", "diviciacus_in_play",
               "winter_track_legions", "spring_box_leaders",
               "event_modifiers")


def _board_digest(state):
    """Digest of the persistent board (dirty-failure oracle)."""
    body = {k: _sanitize(state.get(k)) for k in _BOARD_KEYS}
    blob = json.dumps(body, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


def _build_event_action(state, faction, frng, key_pool):
    """A fuzzed Event player_action for the current card."""
    from fs_bot.engine.execute import _derive_event_params
    card = state.get("current_card")
    shaded = frng.random() < 0.5
    pools = _value_pools(state)
    mode = frng.random()
    derived = None
    try:
        derived = _derive_event_params(state, faction, card, shaded)
    except Exception:
        derived = None
    if derived is not None and mode < 0.35:
        params = dict(derived)
    elif derived is not None and mode < 0.6:
        params = _mutate_params(derived, key_pool, pools, frng)
    elif mode < 0.85:
        # Schema mode: typed values for every key + entry field the
        # handler reads — the success-path generator.
        from fs_bot.cards.param_schema import generate_params
        try:
            params = generate_params(state, card, frng)
        except Exception:
            params = {}
        if not params:
            params = _scratch_params(key_pool, pools, frng)
    else:
        params = _scratch_params(key_pool, pools, frng)
    return {"command": "Event", "regions": [], "sa": "No SA",
            "sa_regions": [],
            "details": {"card_id": card,
                        "text_preference": (rc.EVENT_SHADED if shaded
                                            else rc.EVENT_UNSHADED),
                        "event_params": params}}


def _compare_dry_vs_live(res, seats, expected):
    """Divergences ((faction, card, message)) and the soft partial count."""
    divergences, partial = [], 0
    if res is None:
        return divergences, partial
    seatset = set(seats)
    walk_seen = Counter()
    for cr in res.get("card_results", ()):
        tr = cr.get("turn_result") or {}
        for faction, rec in (tr.get("actions_taken") or {}).items():
            if faction not in seatset:
                continue
            k = (cr.get("card"), faction)
            key = k + (walk_seen[k],)
            walk_seen[k] += 1
            if key not in expected:
                continue
            live = _sig(rec.get("execution"))
            if live is None:
                continue
            want = expected[key]
            if live != want:
                divergences.append(
                    (faction, cr.get("card"),
                     f"dry-run {want} != live {live}"))
            elif want[3] or (want[4] and want[4][1]):
                partial += 1
    return divergences, partial


def _rejected_bot_events(res):
    """Find explicit NPC Event failures without classifying legal declines.

    Use each recorded decision's authoring path, not the ending human seats:
    those seats can change at the Gallic War Interlude. Human deliberately
    malformed plans remain covered by the dry/live and rollback oracles.
    """
    rejected = []
    for cr in (res or {}).get("card_results", ()):
        for faction, rec in ((cr.get("turn_result") or {}).get("actions_taken") or {}).items():
            action = rec.get("bot_action")
            execution = rec.get("execution")
            if (isinstance(action, dict)
                    and action.get("command") == rc.FIRST_DID_EVENT
                    and isinstance(execution, dict)
                    and execution.get("executed") is False
                    and execution.get("rejected") is True):
                reason = execution.get("reason") or execution.get("errors") or execution
                rejected.append((faction, cr.get("card"), str(reason)))
    return rejected


def play_game(scenario, seed, *, reactive=True, events=True, card_edition="legacy"):
    """One fuzzed game. Returns a result dict incl. findings and digest."""
    sop = sorted(get_sop_factions({"scenario": scenario}))
    frng = random.Random(f"player_fuzz|{scenario}|{seed}")
    seats = _pick_seats(sop, frng)
    st = setup_scenario(scenario, seed=seed, card_edition=card_edition,
                        human_factions=seats)
    st["non_player_factions"] = set(sop) - set(seats)
    if reactive:
        st["decision_agent"] = make_random_reactive(seats, frng)
    policies = {f: RandomPlanPolicy(f, seed=seed * 1000 + i)
                for i, f in enumerate(seats)}
    key_pool = _param_key_pool() if events else []

    findings = []
    human_turns = [0]
    event_turns = [0]
    events_ok = [0]
    # (card, faction, occurrence) -> dry-run outcome signature. The
    # occurrence index matters: The Gallic War plays TWO decks (A2.1),
    # so the same card id can come up in both halves.
    expected = {}
    seen_keys = Counter()
    attempt_boards = {}
    rejected = Counter()

    def _maybe_attach_sa_plans(state, faction, pa, frng):
        """Fuzz the player-plan executor paths added for human seats:
        Roman Build/Scout plans (sometimes deliberately invalid) and
        March per-origin routes. Invalid entries must be refused cleanly
        (the dirty-command oracle checks failed plans mutate nothing)."""
        import fs_bot.rules_consts as _rc
        from fs_bot.map.map_data import (get_playable_regions as _gpr,
                                         get_adjacent as _gadj)
        det = pa.setdefault("details", {})
        playable = sorted(_gpr(state["scenario"], state.get("capabilities")))
        if not playable:
            return
        def _r():
            return frng.choice(playable)
        if pa.get("sa") == "Build" and frng.random() < 0.6:
            tribes = sorted(state.get("tribes", {}))
            det["build_plan"] = {
                "forts": [_r()] if frng.random() < 0.7 else [],
                "subdue": ([{"region": _r(),
                             "tribe": frng.choice(tribes)}]
                           if tribes and frng.random() < 0.5 else []),
                "allies": ([{"region": _r(),
                             "tribe": frng.choice(tribes)}]
                           if tribes and frng.random() < 0.5 else []),
            }
        elif pa.get("sa") == "Scout" and frng.random() < 0.6:
            src = _r()
            adj = sorted(_gadj(src, state["scenario"]))
            dst = (frng.choice(adj) if adj and frng.random() < 0.8
                   else _r())  # sometimes non-adjacent (must refuse)
            det["scout_plan"] = {
                "auxilia_moves": [{"from_region": src, "to_region": dst,
                                   "count": frng.randint(1, 3),
                                   "piece_state": frng.choice(
                                       [_rc.HIDDEN, _rc.REVEALED])}],
                "scout_targets": [],
            }
        if (pa.get("command") == "March" and frng.random() < 0.3):
            origins = (det.get("origins") or [])
            routes = {}
            for o in origins:
                adj = sorted(_gadj(o, state["scenario"]))
                if adj:
                    routes[o] = [frng.choice(adj)]
            if routes:
                det["routes"] = routes

    def _inject_transfer(pa, faction):
        """Occasionally ride a §1.5.2 Resource gift on the plan."""
        if frng.random() < 0.12:
            others = [f for f in rc.FACTIONS if f != faction]
            pa.setdefault("details", {})["transfers"] = [
                {"to": others[frng.randrange(len(others))],
                 "amount": frng.randrange(1, 6)}]

    def _dry_run(state, faction, pa):
        """Execute ``pa`` on an isolated sim under IDENTICAL reactive
        decisions (cloned fuzz rng). Returns (info, dirty) where dirty is
        True when a FAILED action mutated the persistent board. Human
        rejection rolls back the complete plan, including any transfers."""
        from fs_bot.engine.execute import execute_decision
        sim = copy.deepcopy(state)
        sim.pop("decision_agent", None)
        if reactive:
            clone_rng = random.Random()
            clone_rng.setstate(frng.getstate())
            sim["decision_agent"] = make_random_reactive(seats, clone_rng)
        pre = _board_digest(sim)
        try:
            info = execute_decision(sim, faction, {"player_action": pa})
        except Exception as exc:
            findings.append(("event-crash" if pa.get("command") == "Event"
                             else "crash",
                             state.get("current_card"), repr(exc)))
            return None, False
        dirty = (not info.get("executed")
                 and _board_digest(sim) != pre)
        return info, dirty

    def decision_func(state, faction, options, position):
        for e in check_structural_integrity(state)[:3]:
            findings.append(("structural", state.get("current_card"), e))
        # Gallic War Interlude seat swap (A2.1): a seated German player
        # takes on the Arverni role for the second half.
        if (state.get("interlude_completed")
                and rc.GERMANS in policies):
            policies[rc.ARVERNI] = policies.pop(rc.GERMANS)
            seats[:] = [rc.ARVERNI if f == rc.GERMANS else f
                        for f in seats]
        if faction in policies:
            human_turns[0] += 1
            k = (state.get("current_card"), faction)
            key = k + (seen_keys[k],)
            if rejected[key] >= _MAX_REJECTED_PLANS:
                seen_keys[k] += 1
                return {"action": ACTION_PASS}
            dec = None
            info = None
            if events and ACTION_EVENT in options and frng.random() < 0.5:
                pa = _build_event_action(state, faction, frng, key_pool)
                _inject_transfer(pa, faction)
                info, dirty = _dry_run(state, faction, pa)
                if dirty:
                    findings.append(
                        ("dirty-event", state.get("current_card"),
                         f"{faction} failed Event mutated the board: "
                         f"params={pa['details']['event_params']}"))
                if info is not None and info.get("executed"):
                    events_ok[0] += 1
                if info is not None and (info.get("executed")
                                         or frng.random() < 0.3):
                    event_turns[0] += 1
                    dec = {"action": ACTION_EVENT, "player_action": pa}
            if dec is None:
                dec = policies[faction].plan_turn(
                    state, faction, options, position)
                pa = (dec or {}).get("player_action")
                if pa is not None:
                    _inject_transfer(pa, faction)
                    _maybe_attach_sa_plans(state, faction, pa, frng)
                    info, dirty = _dry_run(state, faction, pa)
                    if dirty:
                        findings.append(
                            ("dirty-command", state.get("current_card"),
                             f"{faction} failed Command mutated the board"))
            # Count completed decisions, including Pass, so repeated card
            # IDs after the Gallic War Interlude match the result walk.
            # The rejection callback undoes this increment for a retry.
            if (dec or {}).get("player_action") is not None:
                if info is not None:
                    expected[key] = _sig(info)
                attempt_boards[key] = _board_digest(state)
            seen_keys[k] += 1
            return dec
        state["current_card_id"] = state.get("current_card")
        state["is_second_eligible"] = (position == "2nd_eligible")
        state["can_play_event"] = (ACTION_EVENT in options)
        ba = dispatch_bot_turn(state, faction)
        return {"action": _translate_bot_action(ba, options),
                "bot_action": ba}

    def decision_rejected(state, faction, result):
        """Check the refused live attempt, then let the policy replan.

        A validated plan can become invalid after fuzzed transfers or SA
        parameters are injected. The final dry-run detects this, but we
        still submit it to exercise live refusal and rollback. Never hide a
        dry/live mismatch merely because the engine correctly rejected it.
        """
        k = (state.get("current_card"), faction)
        key = k + (seen_keys[k] - 1,)
        want = expected.pop(key, None)
        live = _sig(result)
        if want != live:
            findings.append(("divergence", k[0],
                             f"{faction}: rejected dry-run {want} != live {live}"))
        before = attempt_boards.pop(key, None)
        if before != _board_digest(state):
            findings.append(("dirty-command", k[0],
                             f"{faction} rejected Command mutated the board"))
        rejected[key] += 1
        seen_keys[k] -= 1

    decision_func.decision_rejected = decision_rejected

    res, crash = None, None
    with contextlib.redirect_stdout(io.StringIO()):
        try:
            res = run_game(st, decision_func=decision_func, execute=True)
        except Exception as exc:
            crash = f"{type(exc).__name__}: {exc}"
    if crash:
        findings.append(("crash", st.get("current_card"), crash))
    from fs_bot.tools.error_census import game_completion_error
    completion_error = game_completion_error(res, st["scenario"])
    if completion_error and not crash:
        findings.append(("incomplete-game", st.get("current_card"), completion_error))
    for e in check_structural_integrity(st)[:3]:
        findings.append(("structural", "end", e))
    comparable = res if (isinstance(res, dict)
                         and isinstance(res.get("card_results"), list)
                         and all(isinstance(c, dict) for c in res["card_results"])) else None
    divergences, partial = _compare_dry_vs_live(comparable, seats, expected)
    for f, card, msg in divergences:
        findings.append(("divergence", card, f"{f}: {msg}"))
    for f, card, msg in _rejected_bot_events(comparable):
        findings.append(("bot-event-rejected", card, f"{f}: {msg}"))
    try:
        digest = _digest(st, res)
    except (TypeError, ValueError) as exc:
        findings.append(("serialization", "end", str(exc)))
        digest = None

    return {"scenario": scenario, "seed": seed, "seats": seats,
            "card_edition": card_edition,
            "game_completed": not crash and completion_error is None,
            "ending_scenario": st["scenario"],
            "human_turns": human_turns[0], "event_turns": event_turns[0],
            "events_ok": events_ok[0],
            "rejected": sum(rejected.values()),
            "findings": findings, "partial": partial,
            "digest": digest}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", choices=ALL_SCENARIOS, default=None,
                    help="single scenario (default: all five)")
    ap.add_argument("--seeds", type=parse_seed_range, default="1-10")
    ap.add_argument("--card-edition", choices=CARD_EDITIONS, default="legacy")
    ap.add_argument("--out", default=None, help="write settings, summary and per-game findings as JSON")
    ap.add_argument("--no-reactive", action="store_true",
                    help="skip the randomized reactive decision agent")
    ap.add_argument("--no-events", action="store_true",
                    help="skip player Event fuzzing")
    ap.add_argument("--no-determinism", action="store_true",
                    help="skip the replay determinism double-run")
    args = ap.parse_args(argv)

    seeds = args.seeds
    scenarios = (args.scenario,) if args.scenario else ALL_SCENARIOS

    metadata = validation_metadata("player_fuzz", scenarios, seeds, args.card_edition,
                                   reactive=not args.no_reactive, events=not args.no_events,
                                   replay=not args.no_determinism)
    print("metadata=" + json.dumps(metadata, sort_keys=True))
    records = []
    games, turns, ev_turns, ev_ok, partial = 0, 0, 0, 0, 0
    by_kind = Counter()
    examples = []
    batch = hashlib.sha256()
    for sc in scenarios:
        for seed in seeds:
            r = play_game(sc, seed, reactive=not args.no_reactive,
                          events=not args.no_events, card_edition=args.card_edition)
            games += 1
            turns += r["human_turns"]
            ev_turns += r["event_turns"]
            ev_ok += r["events_ok"]
            partial += r["partial"]
            if not args.no_determinism:
                r2 = play_game(sc, seed, reactive=not args.no_reactive,
                               events=not args.no_events, card_edition=args.card_edition)
                for kind, card, message in r2["findings"]:
                    if (kind, card, message) not in r["findings"]:
                        r["findings"].append(("replay-" + kind, card, message))
                if r2["digest"] != r["digest"]:
                    r["findings"].append(
                        ("nondeterminism", "-",
                         f"replay digest {r['digest']} != {r2['digest']}"))
            records.append(r)
            for kind, card, msg in r["findings"]:
                by_kind[kind] += 1
                if len(examples) < 40:
                    examples.append((sc, seed, r["seats"], kind, card, msg))
            batch.update(f"{sc}|{seed}|{args.card_edition}|{r['digest']}".encode())

    hard = sum(by_kind.values())
    print(f"games={games}  human-turns={turns}  event-turns={ev_turns}  "
          f"events-ok={ev_ok}  hard-findings={hard}  "
          f"(soft: partial={partial})")
    print("findings: " + ("  ".join(
        f"{k}={n}" for k, n in sorted(by_kind.items())) or "none"))
    print(f"batch-digest={batch.hexdigest()[:16]}  "
          f"(must match across PYTHONHASHSEED values)")
    for sc, seed, seats, kind, card, msg in examples:
        print(f"  [{kind}] {sc} seed={seed} seats={','.join(seats)} "
              f"card={card}: {str(msg)[:140]}")
    if args.out:
        with open(args.out, "w", encoding="utf-8") as stream:
            json.dump({"metadata": metadata, "games": games, "human_turns": turns,
                       "event_turns": ev_turns, "events_ok": ev_ok, "partial": partial,
                       "hard_findings": hard, "by_kind": dict(by_kind),
                       "batch_digest": batch.hexdigest(), "records": records}, stream, indent=2)
            stream.write("\n")
    return min(hard, 250)


if __name__ == "__main__":
    raise SystemExit(main())
