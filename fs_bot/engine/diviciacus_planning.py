"""Plan NP Commands with agreed forces, without prompting from simulations.

Command choices may depend on borrowed counters. A refusal therefore restarts
the same flowchart from the same RNG state with those Regions unavailable for
borrowing. Only the final plan's RNG position is committed. A private,
single-use confirmation carries a live agreement into actual execution.
"""
from contextlib import contextmanager
from copy import deepcopy
from functools import wraps
import hashlib
import json

from fs_bot import rules_consts as rc
from fs_bot.engine.diviciacus import (KEY, PIECES, eligible_regions, force_scope,
                                     partner, _np_agrees, consent_regions)

CONFIRMATIONS = '_diviciacus_confirmations'


def _signature(action):
    from fs_bot.state.serialize import encode
    # An Event may remove an accompanying SA after planning, but it does not
    # change the agreed Command's executable details or selected Regions.
    body = {key: action.get(key) for key in ('command', 'regions', 'details')}
    return hashlib.sha256(json.dumps(encode(body), sort_keys=True).encode()).hexdigest()


def clear_confirmation(state, faction, action=None):
    saved = state.get(CONFIRMATIONS, [])
    signature = _signature(action) if action is not None else None
    kept = [entry for entry in saved if not (entry['faction'] == faction and
            (signature is None or entry['signature'] == signature))]
    if kept:
        state[CONFIRMATIONS] = kept
    else:
        state.pop(CONFIRMATIONS, None)


def confirm_plan(state, faction, action):
    """Confirm the concrete NP Command; return Regions requiring a replan."""
    if faction not in PIECES or faction not in state.get('non_player_factions', set()):
        return []
    regions = list((action.get('details') or {}).get('diviciacus_regions') or [])
    if not regions:
        return []
    accepted = consent_regions(state, faction, regions, action, 'command')
    denied = [region for region in regions if region not in accepted]
    if not denied and not state.get('_diviciacus_preview'):
        clear_confirmation(state, faction, action)
        state.setdefault(CONFIRMATIONS, []).append({
            'faction': faction, 'signature': _signature(action), 'regions': accepted})
    return denied


def take_confirmation(state, faction, action, phase='command'):
    """Consume an engine-created confirmation, never a player-supplied flag."""
    if phase != 'command' or faction not in state.get('non_player_factions', set()):
        return None
    signature = _signature(action)
    for entry in state.get(CONFIRMATIONS, []):
        if entry['faction'] == faction and entry['signature'] == signature:
            regions = list(entry['regions'])
            clear_confirmation(state, faction, action)
            return regions
    return None


def plan_with_diviciacus(state, faction, planner):
    """Run the published NP planner with applicable Command/SA force views."""
    if (faction not in PIECES or faction not in state.get('non_player_factions', set())
            or state.get(KEY)):
        return planner(state)
    clear_confirmation(state, faction)
    candidates = eligible_regions(state, faction)
    scope = state.get('_command_region_scope')
    if scope is not None:
        candidates = [region for region in candidates if region in scope]
    denied = set(state.get('_diviciacus_refused', {}).get(faction, []))
    lender = partner(faction)
    if lender in state.get('non_player_factions', set()):
        candidates = [region for region in candidates
                      if _np_agrees(state, lender, faction, region, {}, 'command')]
    if not candidates:
        return planner(state)
    initial = deepcopy({key: value for key, value in state.items() if key != 'decision_agent'})
    while True:
        sim = deepcopy(initial)
        sim['_diviciacus_preview'] = True
        sim['_diviciacus_planning_faction'] = faction
        regions = [region for region in candidates if region not in denied]
        with force_scope(sim, faction, regions):
            action = planner(sim)
        if action.get('command') not in (rc.CMD_RECRUIT, rc.CMD_MARCH, rc.CMD_SEIZE,
                                         rc.CMD_BATTLE, rc.CMD_RALLY, rc.CMD_RAID):
            # Event evaluation has its own physical-board view below.
            regions = []
        if lender in state.get('non_player_factions', set()):
            refused = {region for region in regions
                       if not _np_agrees(state, lender, faction, region, action, 'command')}
            if refused - denied:
                denied.update(refused)
                continue
        if action.get('command') in (rc.CMD_RECRUIT, rc.CMD_MARCH, rc.CMD_SEIZE,
                                      rc.CMD_BATTLE, rc.CMD_RALLY, rc.CMD_RAID):
            action.setdefault('details', {})['diviciacus_regions'] = regions
        elif 'diviciacus_regions' in (action.get('details') or {}):
            action['details']['diviciacus_regions'] = []
        if not state.get('_diviciacus_preview'):
            refused = confirm_plan(state, faction, action)
            if set(refused) - denied:
                denied.update(refused)
                continue
        state['rng'].setstate(sim['rng'].getstate())
        return action


@contextmanager
def _sa_planning_view(state):
    """The original card's Command loan cannot affect SA target selection."""
    faction = state.get('_diviciacus_planning_faction')
    if faction not in PIECES:
        yield
        return
    previous = state.pop(KEY, None)
    try:
        regions = eligible_regions(state, faction, 'special_ability')
        lender = partner(faction)
        if lender in state.get('non_player_factions', set()):
            regions = [region for region in regions
                       if _np_agrees(state, lender, faction, region, {}, 'special_ability')]
        with force_scope(state, faction, regions, 'special_ability'):
            yield
    finally:
        if previous is not None:
            state[KEY] = previous


def planning_sa_view(function):
    @wraps(function)
    def wrapped(state, *args, **kwargs):
        with _sa_planning_view(state):
            return function(state, *args, **kwargs)
    return wrapped


def planning_event_view(function):
    """Event criteria inspect real pieces; any granted Command scopes itself."""
    @wraps(function)
    def wrapped(state, *args, **kwargs):
        previous = state.pop(KEY, None) if state.get('_diviciacus_planning_faction') else None
        try:
            return function(state, *args, **kwargs)
        finally:
            if previous is not None:
                state[KEY] = previous
    return wrapped
