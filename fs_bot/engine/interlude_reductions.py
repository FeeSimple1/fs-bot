"""Player force reductions in the Gallic War Interlude (A2.1)."""
from collections import Counter

from fs_bot import rules_consts as rc
from fs_bot.board import pieces
from fs_bot.cards.card_effects import _tribe_region
from fs_bot.engine.agent import consult_agent

KIND = 'interlude_reduction'
PERMANENT = 'german_permanent'
QUARTER = 'german_quarter'
BELGIC_HALF = 'belgic_half'
AEDUI_HALF = 'aedui_half'
ARVERNI_HALF = 'arverni_half'
ROMAN_HALF = 'roman_half'
ARVERNI_EARLY_ALLIES = (rc.TRIBE_CADURCI, rc.TRIBE_VOLCAE)

STAGE_RULES = {
    PERMANENT: dict(faction=rc.GERMANS, home_regions=()),
    QUARTER: dict(faction=rc.GERMANS, divisor=4, home_regions=rc.GERMAN_HOME_REGIONS_BASE),
    BELGIC_HALF: dict(faction=rc.BELGAE, divisor=2, home_regions=rc.BELGAE_HOME_REGIONS),
    AEDUI_HALF: dict(faction=rc.AEDUI, divisor=2, home_regions=rc.AEDUI_HOME_REGIONS),
    ARVERNI_HALF: dict(faction=rc.ARVERNI, controller=rc.GERMANS, divisor=2,
                       home_regions=rc.ARVERNI_HOME_REGIONS_BASE),
    ROMAN_HALF: dict(faction=rc.ROMANS, divisor=2, home_regions=rc.ROMAN_HOME_REGIONS),
}


def reduction_request(state, stage):
    rules = STAGE_RULES[stage]
    faction = rules['faction']
    roman = stage == ROMAN_HALF
    troop_type = rc.AUXILIA if roman else rc.WARBAND
    cohorts = []
    if stage == PERMANENT:
        available = pieces.get_available(state, faction, rc.WARBAND)
        if available:
            cohorts.append(dict(region=None, piece_type=rc.WARBAND,
                                piece_state=None, tribe=None, count=available))
    else:
        for tribe, info in sorted(state['tribes'].items()):
            region = _tribe_region(state, tribe)
            if (info.get('allied_faction') == faction and region in state['spaces']
                    and pieces.tribe_has_ally_disc(state, region, tribe, faction)):
                cohorts.append(dict(region=region, piece_type=rc.ALLY,
                                    piece_state=None, tribe=tribe, count=1))

    for region in sorted(state['spaces']):
        if roman and region != rc.PROVINCIA:
            count = pieces.count_pieces(state, region, faction, rc.FORT)
            if count:
                cohorts.append(dict(region=region, piece_type=rc.FORT,
                                    piece_state=None, tribe=None, count=count))
        for visibility in (rc.HIDDEN, rc.REVEALED, rc.SCOUTED):
            count = pieces.count_pieces_by_state(state, region, faction, troop_type, visibility)
            if count:
                cohorts.append(dict(region=region, piece_type=troop_type,
                                    piece_state=visibility, tribe=None, count=count))

    totals = Counter()
    for row in cohorts:
        totals[row['piece_type']] += row['count']
    if stage == PERMANENT:
        minimums = {rc.WARBAND: min(rc.INTERLUDE_GERMAN_WARBANDS_REMOVED, totals[rc.WARBAND])}
    else:
        divisor = rules['divisor']
        kinds = (rc.FORT, rc.ALLY, troop_type) if roman else (rc.ALLY, troop_type)
        minimums = {kind: (totals[kind] + divisor - 1) // divisor for kind in kinds}
    return dict(kind=KIND, stage=stage, minimums=minimums, cohorts=cohorts)


def is_home_last(stage, row):
    """Apply the Cadurci and Volcae exception to their Ally discs only."""
    return (row['region'] in STAGE_RULES[stage]['home_regions']
            and not (stage == ARVERNI_HALF and row['piece_type'] == rc.ALLY
                     and row['tribe'] in ARVERNI_EARLY_ALLIES))


def eligible_cohorts(stage, remaining):
    """List the cohorts still selectable at this point in the allocation."""
    home = STAGE_RULES[stage]['home_regions']
    outside = {row['piece_type'] for row in remaining
               if row['count'] and row['region'] not in home}
    return [row for row in remaining if row['count']
            and (not is_home_last(stage, row) or row['piece_type'] not in outside)]


def validate_response(state, request, response):
    if (isinstance(response, dict) and set(response) == {'use_default'}
            and response['use_default'] is True):
        return response
    if (not isinstance(response, dict) or set(response) != {'removals'}
            or not isinstance(response['removals'], list)):
        raise ValueError('Allocate the required Interlude pieces or delegate to the bot.')
    stage = request['stage']
    rules = STAGE_RULES[stage]
    controller = rules.get('controller', rules['faction'])
    current = reduction_request(state, stage)
    if (request.get('faction', controller) != controller
            or current != {key: value for key, value in request.items() if key != 'faction'}):
        raise ValueError('The offered Interlude force has changed.')

    remaining = [dict(row) for row in current['cohorts']]
    selected = Counter()
    for removal in response['removals']:
        count = removal.get('count') if isinstance(removal, dict) else None
        if type(count) is not int or count <= 0:
            raise ValueError('Choose an offered cohort and a positive count.')
        cohort = next((row for row in eligible_cohorts(stage, remaining)
                       if count <= row['count'] and dict(row, count=count) == removal), None)
        if cohort is None:
            raise ValueError('Choose offered pieces within their counts, taking Home Regions last for each type.')
        cohort['count'] -= count
        selected[cohort['piece_type']] += count

    for kind, required in current['minimums'].items():
        if stage == PERMANENT and selected[kind] != required:
            raise ValueError(f'Remove exactly {required} German Warbands from play.')
        if selected[kind] < required:
            raise ValueError(f'Return at least {required} {kind} pieces to Available.')
    return response


def choose_reduction(state, stage):
    rules = STAGE_RULES[stage]
    controller = rules.get('controller', rules['faction'])
    if (controller in state.get('non_player_factions', ())
            or state.get('decision_agent') is None):
        return None
    request = reduction_request(state, stage)
    if any(request['minimums'].values()):
        response = consult_agent(state, controller, request)
        if response is not None:
            return validate_response(state, request, response).get('removals')
    return None
