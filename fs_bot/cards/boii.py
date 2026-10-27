"""Boii's bounded placement choices (Card Reference 37, §§5.1.1–5.1.3)."""
from fs_bot import rules_consts as rc
from fs_bot.board.control import calculate_control
from fs_bot.board.pieces import get_available, place_piece
from fs_bot.map.map_data import (get_adjacent_for_state,
                                  get_playable_regions_for_state)


def eligible_regions(state, control_faction):
    """Freeze the Event's geographic scope before its placements change Control."""
    playable = set(get_playable_regions_for_state(state))
    controlled = {r for r in playable if calculate_control(state, r)
                  == rc.FACTION_CONTROL[control_faction]}
    return sorted(controlled | {adjacent for region in controlled
                                for adjacent in get_adjacent_for_state(state, region)})


def eligible_allies(state, regions, faction=None):
    from fs_bot.cards.card_effects import _tribe_region
    return sorted(tribe for tribe, info in state['tribes'].items()
                  if _tribe_region(state, tribe) in regions
                  and info.get('allied_faction') is None
                  and info.get('status') in (None, rc.ALLIED)
                  and (faction is None or
                       rc.TRIBE_FACTION_RESTRICTION.get(tribe, faction) == faction)
                  and (faction is None or _tribe_region(state, tribe)
                       in get_playable_regions_for_state(state, faction)))


def replacement_targets(state, regions):
    from fs_bot.cards.card_effects import _tribe_piece_type, _tribe_region
    return sorted(tribe for tribe, info in state['tribes'].items()
                  if _tribe_region(state, tribe) in regions
                  and info.get('allied_faction') == rc.AEDUI
                  and _tribe_piece_type(state, tribe) == rc.ALLY)


def _entries(params, key):
    values = params.get(key, [])
    if not isinstance(values, list) or any(not isinstance(e, dict) for e in values):
        raise ValueError(f'Boii {key} must be a list of entries')
    return values


def execute(state, shaded=False):
    """Validate the whole plan before mutation; apply only Available pieces."""
    from fs_bot.cards.card_effects import _ally_tribe, _unally_tribe, _tribe_region
    params = state.get('event_params')
    if params is None:
        params = {}
    if not isinstance(params, dict):
        raise ValueError('Boii choices must be an object')
    regions = eligible_regions(state, rc.ARVERNI if shaded else rc.AEDUI)
    if shaded:
        replacements = _entries(params, 'replacements')
        targets = replacement_targets(state, regions)
        chosen = []
        for entry in replacements:
            tribe = entry.get('tribe')
            if (tribe not in targets or tribe in chosen or len(chosen) == 2
                    or entry.get('region', _tribe_region(state, tribe))
                    != _tribe_region(state, tribe)):
                raise ValueError('Boii replaces one or two distinct Aedui Allies within one Region of Arverni Control')
            chosen.append(tribe)
        if targets and not chosen:
            raise ValueError('Boii requires at least one eligible Aedui Ally')
        for tribe in chosen:
            _unally_tribe(state, tribe)
            # §5.1.1: remove rather than replace if unavailable or stacking
            # prohibits the new disc (notably the Aedui Home Tribe).
            if (rc.TRIBE_FACTION_RESTRICTION.get(tribe, rc.ARVERNI) == rc.ARVERNI
                    and _tribe_region(state, tribe)
                    in get_playable_regions_for_state(state, rc.ARVERNI)):
                _ally_tribe(state, tribe, rc.ARVERNI)
        return

    faction = params.get('place_faction', rc.AEDUI)
    if faction not in (rc.AEDUI, rc.ROMANS):
        raise ValueError('Boii places Aedui or Roman pieces only')
    troop = rc.AUXILIA if faction == rc.ROMANS else rc.WARBAND
    regions = [r for r in regions if r in get_playable_regions_for_state(state, faction)]
    targets = eligible_allies(state, regions, faction)
    placements = _entries(params, 'placements')
    chosen_allies = []
    troops = []
    total_troops = 0
    for entry in placements:
        region, kind = entry.get('region'), entry.get('piece_type')
        count = entry.get('count', 1)
        if (region not in regions or kind not in (rc.ALLY, troop)
                or entry.get('faction', faction) != faction):
            raise ValueError('Boii places only the selected Faction\'s Allies and native troops within one Region of Aedui Control')
        if type(count) is not int or count <= 0:
            raise ValueError('Boii placement count must be a positive integer')
        if kind == rc.ALLY:
            tribe = entry.get('tribe')
            if (count != 1 or tribe not in targets or tribe in chosen_allies
                    or _tribe_region(state, tribe) != region or len(chosen_allies) == 2):
                raise ValueError('Boii places at most two Allies, each at one distinct eligible Subdued Tribe')
            chosen_allies.append(tribe)
        else:
            total_troops += count
            if total_troops > 2:
                raise ValueError('Boii places at most two Warbands or Auxilia in total')
            troops.append((region, count))

    # The card says "2", not "up to 2": only availability/stacking can
    # reduce its required placements (§5.1.3). Preserve explicit over-
    # requests up to the printed limit when the pool runs short.
    required_allies = min(2, len(targets), get_available(state, faction, rc.ALLY))
    required_troops = min(2, get_available(state, faction, troop)) if regions else 0
    if len(chosen_allies) < required_allies or total_troops < required_troops:
        raise ValueError('Boii must place all available legal pieces up to its two-Allies/two-troops limits')
    for tribe in chosen_allies:
        _ally_tribe(state, tribe, faction)
    for region, count in troops:
        count = min(count, get_available(state, faction, troop))
        if count:
            place_piece(state, region, faction, troop, count=count)


def collect_params(state, faction, shaded, stdin, stdout):
    """Offer the printed choices, maintaining aggregate limits across Regions."""
    from fs_bot.cards.card_effects import _tribe_region
    from fs_bot.cli.menus import prompt_choice
    if shaded:
        targets = replacement_targets(state, eligible_regions(state, rc.ARVERNI))
        replacements = []
        while targets and len(replacements) < 2:
            options = [(f'{t} ({_tribe_region(state, t)})', t) for t in targets]
            if replacements:
                options.append(('Done', None))
            choice = prompt_choice(stdin, stdout, 'Boii: replace which Aedui Ally?', options)
            if choice is None:
                break
            replacements.append({'tribe': choice})
            targets.remove(choice)
        return {'replacements': replacements}

    beneficiary = prompt_choice(stdin, stdout, 'Boii: place whose pieces?',
                                [(f, f) for f in (rc.AEDUI, rc.ROMANS)])
    regions = [r for r in eligible_regions(state, rc.AEDUI)
               if r in get_playable_regions_for_state(state, beneficiary)]
    targets = eligible_allies(state, regions, beneficiary)
    placements = []
    for _ in range(min(2, len(targets), get_available(state, beneficiary, rc.ALLY))):
        tribe = prompt_choice(stdin, stdout, 'Boii: place an Ally at which Tribe?',
                              [(f'{t} ({_tribe_region(state, t)})', t) for t in targets])
        placements.append({'region': _tribe_region(state, tribe), 'piece_type': rc.ALLY,
                           'tribe': tribe, 'count': 1})
        targets.remove(tribe)
    troop = rc.AUXILIA if beneficiary == rc.ROMANS else rc.WARBAND
    remaining = min(2, get_available(state, beneficiary, troop)) if regions else 0
    while remaining:
        region = prompt_choice(stdin, stdout, f'Boii: place {troop} in which Region?',
                               [(r, r) for r in regions])
        count = prompt_choice(stdin, stdout, f'Boii: how many {troop}?',
                              [(str(n), n) for n in range(1, remaining + 1)])
        placements.append({'region': region, 'piece_type': troop, 'count': count})
        remaining -= count
    return {'place_faction': beneficiary, 'placements': placements}
