"""Card 65 shaded: exact German removals/replacements (5.1–5.1.3)."""
from collections import Counter
from copy import deepcopy

from fs_bot import rules_consts as rc
from fs_bot.board.control import is_controlled_by, refresh_all_control
from fs_bot.board.pieces import (
    count_pieces_by_state, get_available, place_piece, remove_piece,
)
from fs_bot.map.map_data import get_playable_regions_for_state


def planning_copy(state):
    result = deepcopy({key: value for key, value in state.items()
                       if key != 'decision_agent'})
    result['_diviciacus_preview'] = True
    return result


def targets(state, faction):
    """One entry per physical state cohort or exact Allied Tribe."""
    from fs_bot.cards.card_effects import _tribe_region, _tribe_piece_type
    regions = sorted(region for region in get_playable_regions_for_state(state)
                     if is_controlled_by(state, region, faction))
    result = []
    for region in regions:
        for visibility in (rc.HIDDEN, rc.REVEALED, rc.SCOUTED):
            number = count_pieces_by_state(state, region, rc.GERMANS,
                                          rc.WARBAND, visibility)
            if number:
                result.append({'region': region, 'piece_type': rc.WARBAND,
                               'piece_state': visibility, 'available': number})
        for tribe in sorted(state['tribes']):
            if (_tribe_region(state, tribe) == region
                    and state['tribes'][tribe].get('allied_faction') == rc.GERMANS
                    and _tribe_piece_type(state, tribe) == rc.ALLY):
                result.append({'region': region, 'piece_type': rc.ALLY,
                               'tribe': tribe, 'available': 1})
    return result


def required_counts(state, faction):
    available = Counter()
    for target in targets(state, faction):
        available[target['piece_type']] += target['available']
    return {rc.WARBAND: min(5, available[rc.WARBAND]),
            rc.ALLY: min(1, available[rc.ALLY])}


def _identity(entry):
    return (entry['region'], entry['piece_type'],
            entry.get('piece_state'), entry.get('tribe'))


def _validate_entry(entry):
    if not isinstance(entry, dict):
        raise ValueError('German Allegiances requires physical replacement entries')
    kind = entry.get('piece_type')
    if kind not in (rc.WARBAND, rc.ALLY):
        raise ValueError('German Allegiances affects only German Warbands and Allies')
    fields = {'region', 'piece_type', 'replace'}
    fields.add('piece_state' if kind == rc.WARBAND else 'tribe')
    if set(entry) - {'timing_actions'} != fields:
        raise ValueError('German Allegiances requires exact physical targets and a replace Boolean')
    if (not isinstance(entry['region'], str) or type(entry['replace']) is not bool
            or (kind == rc.WARBAND and entry['piece_state'] not in
                (rc.HIDDEN, rc.REVEALED, rc.SCOUTED))
            or (kind == rc.ALLY and not isinstance(entry['tribe'], str))):
        raise ValueError('German Allegiances target or replace Boolean is invalid')


def validate_params(state, faction, params):
    """Validate all targets and mandatory quotas before any piece changes."""
    if faction not in (rc.ROMANS, *rc.GALLIC_FACTIONS):
        raise ValueError('German Allegiances requires a Roman or Gallic executor')
    if (not isinstance(params, dict)
            or set(params) - {'replacements', 'stage_timing_actions'}
            or not isinstance(params.get('replacements'), list)):
        raise ValueError('German Allegiances requires a replacements list')
    available = {_identity(target): target['available'] for target in targets(state, faction)}
    chosen = Counter()
    for entry in params['replacements']:
        _validate_entry(entry)
        identity = _identity(entry)
        if available.get(identity, 0) < 1:
            raise ValueError('Choose an existing German piece where the executor has Control')
        available[identity] -= 1
        chosen[entry['piece_type']] += 1
    if any(chosen[kind] != count for kind, count in required_counts(state, faction).items()):
        raise ValueError('German Allegiances must affect five Warbands and one Ally, to the extent possible')


def can_replace_ally(state, faction, target):
    """§5.1.1: failed replacement leaves only the printed removal."""
    return (rc.TRIBE_FACTION_RESTRICTION.get(target['tribe'], faction) == faction
            and target['region'] in get_playable_regions_for_state(state, faction)
            and get_available(state, faction, rc.ALLY) > 0)


def apply_entry(state, faction, entry):
    """Remove one exact enemy counter; place only the executor's native piece."""
    from fs_bot.cards.card_effects import _ally_tribe, _unally_tribe
    if entry['piece_type'] == rc.WARBAND:
        remove_piece(state, entry['region'], rc.GERMANS, rc.WARBAND,
                     piece_state=entry['piece_state'])
        troop = rc.AUXILIA if faction == rc.ROMANS else rc.WARBAND
        if (entry['replace'] and get_available(state, faction, troop) > 0
                and entry['region'] in get_playable_regions_for_state(state, faction)):
            place_piece(state, entry['region'], faction, troop)
    else:
        _unally_tribe(state, entry['tribe'])
        if entry['replace'] and can_replace_ally(state, faction, entry):
            _ally_tribe(state, entry['tribe'], faction)
    refresh_all_control(state)


def execute(state):
    from fs_bot.cards.card_effects import _event_entries
    faction, params = state.get('executing_faction'), state.get('event_params')
    validate_params(state, faction, params)
    for entry in _event_entries(state, '65.replacements', params['replacements']):
        # A genuine §1.4.1 interruption may change Control. Never silently
        # substitute a different physical target after the player's choice.
        if _identity(entry) not in {_identity(t) for t in targets(state, faction)}:
            raise ValueError('German Allegiances target is no longer eligible')
        apply_entry(state, faction, entry)


def _random_target(state, candidates):
    """§8.3.4: equal Region, then equal Tribe chances."""
    from fs_bot.bots.bot_common import random_select
    region = random_select(state, sorted({entry['region'] for entry in candidates}))
    return random_select(state, [entry for entry in candidates if entry['region'] == region])


def derive_params(state, faction, shaded):
    """§§8.2.3/8.3.1/8.4.1: benefit self, exact targets, maximum effects."""
    if not shaded:
        return None
    from fs_bot.bots.bot_common import random_select, is_ally_in_city_or_remi
    candidates = targets(state, faction)
    result = []
    allies = [entry for entry in candidates if entry['piece_type'] == rc.ALLY]
    if allies:
        beneficial = [entry for entry in allies if can_replace_ally(state, faction, entry)]
        pool = beneficial or allies
        preferred = [entry for entry in pool if is_ally_in_city_or_remi(
            entry['tribe'], state['scenario'])]
        target = _random_target(state, preferred or pool)
        result.append({key: value for key, value in target.items() if key != 'available'} | {'replace': True})
    warbands = [entry for entry in candidates if entry['piece_type'] == rc.WARBAND]
    remaining = min(5, sum(entry['available'] for entry in warbands))
    while remaining:
        totals = Counter()
        for entry in warbands:
            totals[entry['region']] += entry['available']
        maximum = max(min(remaining, number) for number in totals.values())
        region = random_select(state, sorted(region for region, number in totals.items()
                                             if min(remaining, number) == maximum))
        for entry in [entry for entry in warbands if entry['region'] == region]:
            count = min(remaining, entry['available'])
            choice = {key: value for key, value in entry.items() if key != 'available'}
            result.extend(dict(choice, replace=True) for _ in range(count))
            remaining -= count
        warbands = [entry for entry in warbands if entry['region'] != region]
    return {'replacements': result}


def np_available(state, faction):
    candidates = targets(state, faction)
    if faction == rc.BELGAE:
        # The Belgic sheet requires adding an Ally/Citadel. Removing a
        # restricted Suebi Ally or placing only Warbands is insufficient.
        return any(entry['piece_type'] == rc.ALLY
                   and can_replace_ally(state, faction, entry) for entry in candidates)
    return bool(candidates)
