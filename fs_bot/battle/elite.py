"""Physical Warbands picked for shaded Vercingetorix's Elite (card 30).

The human choice lasts for this Battle, including its Counterattack. A normal
Warband and a picked Warband remain separate casualty/removal choices even
when they have the same visibility. Legacy non-player resolution is unchanged.
"""
from contextlib import contextmanager
from functools import wraps

from fs_bot import rules_consts as rc

KIND = 'battle_elite'
KEY = '_battle_elite_warbands'
COHORT = 'battle_elite'
STATES = (rc.HIDDEN, rc.REVEALED, rc.SCOUTED)


def context(state, region):
    value = state.get(KEY)
    return value if value and value['region'] == region else None


@contextmanager
def scope(state, region, *factions):
    from fs_bot.cards.capabilities import is_capability_active
    from fs_bot.engine.action_windows import enabled
    old = state.get(KEY)
    if (old is not None or rc.ARVERNI not in factions
            or rc.ARVERNI in state.get('non_player_factions', ())
            or not enabled(state)
            or not is_capability_active(state, 30, rc.EVENT_SHADED)):
        yield
        return
    state[KEY] = {'region': region, 'selected': False}
    try:
        yield
    finally:
        from fs_bot.engine.action_windows import clear_cohorts
        clear_cohorts(state, KEY)
        state.pop(KEY, None)


def battle_scope(function):
    @wraps(function)
    def wrapped(state, region, attacking_faction, defending_faction, **kwargs):
        with scope(state, region, attacking_faction, defending_faction):
            return function(state, region, attacking_faction, defending_faction, **kwargs)
    return wrapped


def loss_scope(function):
    @wraps(function)
    def wrapped(state, region, faction, *args, **kwargs):
        with scope(state, region, faction):
            return function(state, region, faction, *args, **kwargs)
    return wrapped


def _available(state, region):
    from fs_bot.commands.sa_enlist import FREE_FORCE_KEY
    raw = state['spaces'][region].get('pieces', {}).get(rc.ARVERNI, {})
    free = state.get(FREE_FORCE_KEY, {})
    if free.get('faction', rc.GERMANS) == rc.ARVERNI and region in free.get('pieces', {}):
        return {ps: free['pieces'][region].get(ps, 0) for ps in STATES}
    return {ps: raw.get(ps, {}).get(rc.WARBAND, 0) for ps in STATES}


def validate_response(state, request, response):
    if (isinstance(response, dict) and set(response) == {'use_default'}
            and response['use_default'] is True):
        return response
    if (not isinstance(response, dict) or set(response) != {'counts'}
            or not isinstance(response['counts'], dict)
            or set(response['counts']) - set(STATES)):
        raise ValueError('Choose the visibility of the Warbands picked as Legions.')
    counts = response['counts']
    if (any(type(n) is not int or n < 0 for n in counts.values())
            or sum(counts.values()) != request['count']
            or any(n > request['available'].get(ps, 0) for ps, n in counts.items())):
        raise ValueError('Pick exactly the offered number of participating Warbands.')
    return response


def ensure_selected(state, region):
    """Pick once when the Battle first has both the Leader and Warbands."""
    current = context(state, region)
    if current is None or current['selected'] or current.get('legacy'):
        return
    from fs_bot.board.pieces import get_leader_in_region
    if get_leader_in_region(state, region, rc.ARVERNI) is None:
        return
    from fs_bot.cards.edition import uses_second_edition
    available = _available(state, region)
    count = min(4 if uses_second_edition(state) else 2, sum(available.values()))
    if not count:
        return
    request = {'kind': KIND, 'faction': rc.ARVERNI, 'region': region,
               'count': count, 'available': available,
               'window': {'stage': 'battle_elite', 'region': region}}
    from fs_bot.engine.agent import consult_agent
    response = (None if state.get('_diviciacus_preview') else
                consult_agent(state, rc.ARVERNI, request))
    if response is None:
        # Old saved Battles had no picked-counter request or tagged casualty
        # choices. An opted-in frontend can explicitly retain that replay path;
        # new delegation returns use_default, choosing a real physical cohort.
        current['legacy'] = True
        return
    if response is not None:
        validate_response(state, request, response)
    if response.get('use_default'):
        # Explicit delegation retains the existing Hidden-first casualty order.
        remaining, selected = count, {}
        for ps in STATES:
            selected[ps] = min(remaining, available[ps])
            remaining -= selected[ps]
    else:
        selected = {ps: response['counts'].get(ps, 0) for ps in STATES}
    from fs_bot.commands.sa_enlist import FREE_FORCE_KEY
    from fs_bot.engine.action_windows import set_cohorts
    free = state.get(FREE_FORCE_KEY, {})
    cohorts = []
    for ps, number in selected.items():
        if not number:
            continue
        cohort = {'id': COHORT, 'label': 'picked as Legions', 'region': region,
                  'piece_type': rc.WARBAND, 'piece_state': ps, 'count': number}
        if free.get('faction', rc.GERMANS) == rc.ARVERNI and region in free.get('pieces', {}):
            cohort['loan_kind'] = 'free_force'
        cohorts.append(cohort)
    set_cohorts(state, KEY, rc.ARVERNI, cohorts)
    current['selected'] = True


def count(state, region):
    current = context(state, region)
    from fs_bot.engine.action_windows import get_cohorts
    return (sum(piece['count'] for piece in get_cohorts(state, KEY))
            if current is not None and current['selected'] else None)


def loss_choices(state, region, faction, choices):
    if faction != rc.ARVERNI or count(state, region) is None:
        return choices
    from fs_bot.engine.action_windows import get_cohorts
    picked_by_state = {piece['piece_state']: piece['count']
                       for piece in get_cohorts(state, KEY)}
    available = _available(state, region)
    mobile = []
    for ps in STATES:
        picked = picked_by_state.get(ps, 0)
        if picked > available[ps]:
            raise ValueError('Picked Elite Warbands exceed their physical cohort.')
        mobile.extend([(rc.WARBAND, ps, None, 'elite')] * picked)
        mobile.extend([(rc.WARBAND, ps)] * (available[ps] - picked))
    others = [choice for choice in choices if choice[0] != rc.WARBAND]
    index = next((i for i, choice in enumerate(choices) if choice[0] == rc.WARBAND), 0)
    return others[:index] + mobile + others[index:]


def record_loss(state, region, visibility):
    from fs_bot.engine.action_windows import get_cohorts, set_cohorts
    cohorts = get_cohorts(state, KEY)
    selected = next((piece for piece in cohorts if piece['piece_state'] == visibility), None)
    if context(state, region) is None or selected is None or selected['count'] < 1:
        raise ValueError('The selected Elite casualty is no longer present.')
    selected['count'] -= 1
    set_cohorts(state, KEY, rc.ARVERNI, cohorts)


def window(state, stage, *, region, **details):
    """Keep optional removals attached to the picked physical cohort."""
    from fs_bot.engine import action_windows
    return action_windows.window(state, stage, region=region, **details)


def collect_selection(state, faction, request, stdin, stdout):
    from fs_bot.cli.menus import prompt_choice
    stdout.write(f"\n{faction}: pick {request['count']} Warbands in {request['region']} "
                 "to take and inflict Battle Losses as Legions.\n")
    remaining, selected = request['count'], {}
    for index, ps in enumerate(STATES):
        available = request['available'][ps]
        other = sum(request['available'][later] for later in STATES[index + 1:])
        low, high = max(0, remaining - other), min(remaining, available)
        value = (low if low == high else prompt_choice(stdin, stdout,
            f'How many {ps} Warbands?', [(str(n), n) for n in range(low, high + 1)]))
        selected[ps] = value
        remaining -= value
    return {'counts': selected}
