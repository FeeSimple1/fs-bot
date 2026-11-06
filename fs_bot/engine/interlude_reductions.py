"""German player force reductions in the Gallic War Interlude (A2.1)."""
from collections import Counter

from fs_bot import rules_consts as rc
from fs_bot.board import pieces
from fs_bot.cards.card_effects import _tribe_region
from fs_bot.engine.agent import consult_agent

KIND = 'interlude_reduction'
PERMANENT = 'german_permanent'
QUARTER = 'german_quarter'


def reduction_request(state, stage):
    cohorts = []
    if stage == PERMANENT:
        available = pieces.get_available(state, rc.GERMANS, rc.WARBAND)
        if available:
            cohorts.append(dict(region=None, piece_type=rc.WARBAND,
                                piece_state=None, tribe=None, count=available))
    elif stage == QUARTER:
        for tribe, info in sorted(state['tribes'].items()):
            region = _tribe_region(state, tribe)
            if (info.get('allied_faction') == rc.GERMANS and region in state['spaces']
                    and pieces.tribe_has_ally_disc(state, region, tribe, rc.GERMANS)):
                cohorts.append(dict(region=region, piece_type=rc.ALLY,
                                    piece_state=None, tribe=tribe, count=1))
    else:
        raise ValueError('Unknown German Interlude reduction stage.')

    for region in sorted(state['spaces']):
        for visibility in (rc.HIDDEN, rc.REVEALED, rc.SCOUTED):
            count = pieces.count_pieces_by_state(state, region, rc.GERMANS, rc.WARBAND, visibility)
            if count:
                cohorts.append(dict(region=region, piece_type=rc.WARBAND,
                                    piece_state=visibility, tribe=None, count=count))

    totals = Counter()
    for row in cohorts:
        totals[row['piece_type']] += row['count']
    if stage == PERMANENT:
        minimums = {rc.WARBAND: min(rc.INTERLUDE_GERMAN_WARBANDS_REMOVED, totals[rc.WARBAND])}
    else:
        minimums = {kind: (totals[kind] + 3) // 4 for kind in (rc.ALLY, rc.WARBAND)}
    return dict(kind=KIND, stage=stage, minimums=minimums, cohorts=cohorts)


def eligible_cohorts(stage, remaining):
    """List the cohorts still selectable at this point in the allocation."""
    outside = {row['piece_type'] for row in remaining
               if row['count'] and row['region'] not in rc.GERMANIA_REGIONS}
    return [row for row in remaining if row['count'] and (
        stage == PERMANENT or row['region'] not in rc.GERMANIA_REGIONS
        or row['piece_type'] not in outside)]


def validate_response(state, request, response):
    if (isinstance(response, dict) and set(response) == {'use_default'}
            and response['use_default'] is True):
        return response
    if (not isinstance(response, dict) or set(response) != {'removals'}
            or not isinstance(response['removals'], list)):
        raise ValueError('Allocate the required German pieces or delegate to the bot.')
    stage = request['stage']
    current = reduction_request(state, stage)
    if current != {key: value for key, value in request.items() if key != 'faction'}:
        raise ValueError('The offered German Interlude force has changed.')

    remaining = [dict(row) for row in current['cohorts']]
    selected = Counter()
    for removal in response['removals']:
        count = removal.get('count') if isinstance(removal, dict) else None
        if type(count) is not int or count <= 0:
            raise ValueError('Choose an offered cohort and a positive count.')
        cohort = next((row for row in eligible_cohorts(stage, remaining)
                       if count <= row['count'] and dict(row, count=count) == removal), None)
        if cohort is None:
            raise ValueError('Choose offered pieces within their counts, taking Germania last for each type.')
        cohort['count'] -= count
        selected[cohort['piece_type']] += count

    for kind, required in current['minimums'].items():
        if stage == PERMANENT and selected[kind] != required:
            raise ValueError(f'Remove exactly {required} German Warbands from play.')
        if selected[kind] < required:
            raise ValueError(f'Return at least {required} German {kind} pieces to Available.')
    return response


def choose_reduction(state, stage):
    if (rc.GERMANS in state.get('non_player_factions', ())
            or state.get('decision_agent') is None):
        return None
    request = reduction_request(state, stage)
    if any(request['minimums'].values()):
        response = consult_agent(state, rc.GERMANS, request)
        if response is not None:
            return validate_response(state, request, response).get('removals')
    return None
