"""
Trade Special Ability — §4.4.1 (Aedui).

Trade garners Aedui Resources via Supply Lines.
May accompany any type of Command.

Selection (§4.4.1):
  - Occurs in Regions that are part of any Supply Lines to Cisalpina.
  - No Leader requirement in base game.
  - Ariovistus with Diviciacus: within 1 of Diviciacus — A4.4, A4.1.2.

Procedure:
  - Player Factions declare agreement for Supply Lines.
  - Aedui receive +1 Resource (or +2 if Romans agreed) for each:
    - Aedui Allied Tribe and Aedui Citadel within Supply Lines.
    - Where Aedui Control only: each Subdued Tribe and, only if Romans
      agreed, each Roman Allied Tribe.

Reference: §4.4.1, A4.4
"""

from contextlib import contextmanager, nullcontext
from copy import deepcopy

from fs_bot.rules_consts import (
    # Factions
    ROMANS, AEDUI,
    # Piece types
    ALLY, CITADEL,
    # Leaders
    DIVICIACUS,
    # Resources
    MAX_RESOURCES,
    # Scenarios
    ARIOVISTUS_SCENARIOS,
    # Tribe restrictions
    TRIBE_FACTION_RESTRICTION,
)
from fs_bot.board.pieces import (
    count_pieces, find_leader, get_leader_in_region,
)
from fs_bot.board.control import is_controlled_by
from fs_bot.map.map_data import (
    is_adjacent, get_tribes_in_region, get_playable_regions,
)
from fs_bot.commands.common import CommandError
from fs_bot.commands.rally import (has_supply_line, supply_agreement_scope,
                                    supply_query_scope)


_ROMAN_DECLARATION = (AEDUI, ROMANS, None)
UNSELECTED = object()
TRADE_REGION = 'trade_region'


def selection_from_action(action):
    """An optional authored Region; absence defers the choice until SA time."""
    details = (action or {}).get('details') or {}
    nested = details.get('sa_details') or {}
    if TRADE_REGION in details:
        return details[TRADE_REGION]
    return nested.get(TRADE_REGION, UNSELECTED)


def validate_trade_plan(action):
    """Check the new field without predicting future Supply declarations."""
    details = action.get('details') or {}
    if not isinstance(details, dict):
        return 'Command details must be an object'
    nested = details.get('sa_details') or {}
    if not isinstance(nested, dict):
        return 'Special Ability details must be an object'
    if TRADE_REGION not in details and TRADE_REGION not in nested:
        return None
    if action.get('sa') != 'Trade':
        return 'trade_region requires a Trade Special Ability'
    selection = selection_from_action(action)
    if not isinstance(selection, str):
        return 'trade_region must name one Region'
    if (TRADE_REGION in details and TRADE_REGION in nested
            and details[TRADE_REGION] != nested[TRADE_REGION]):
        return 'Conflicting Trade Region selections'
    return None


def validate_trade_response(request, response):
    """A durable human answer chooses one offered Region or explicitly declines."""
    if not isinstance(response, dict):
        raise ValueError('Choose a Trade Region or decline Trade.')
    for sentinel in ('decline', 'use_default'):
        if set(response) == {sentinel} and response[sentinel] is True:
            return response
    if (set(response) != {'region'} or not isinstance(response['region'], str)
            or response['region'] not in request['legal_regions']):
        raise ValueError('Choose one of the offered Trade Regions.')
    return response


def _choose_trade_region(state, region_items, roman_agreed, selection, choose_region):
    """Declare Supply first, then let the human choose the restricted Region."""
    regions = list(region_items)
    if selection is not UNSELECTED:
        if not isinstance(selection, str) or selection not in regions:
            raise CommandError('The selected Trade Region has no legal Supply Line or is outside the allowed range.')
        return selection
    if not regions:
        return None
    if AEDUI in state.get('non_player_factions', ()):
        # Preserve the existing map-order policy; its interpretation of
        # §§8.3.3/8.6.3 is tracked separately from this human interface.
        return regions[0]
    if not choose_region or state.get('_diviciacus_preview'):
        # A pure planning copy must allow any income a human could choose.
        # In particular Subdued/Roman-Allied Tribes also finance the following
        # Command; counting blue pieces alone can hide affordable plans.
        return max(regions, key=lambda region: sum(item[2] for item in region_items[region]))
    if choose_region:
        from fs_bot.engine.agent import consult_agent
        room = MAX_RESOURCES - state['resources'].get(AEDUI, 0)
        request = {'kind': TRADE_REGION, 'faction': AEDUI,
                   'legal_regions': regions, 'roman_agreed': bool(roman_agreed),
                   'choices': [{'region': region,
                                'resources_gained': min(room, sum(item[2] for item in items)),
                                'per_item': items}
                               for region, items in region_items.items()]}
        response = consult_agent(state, AEDUI, request)
        if response is not None:
            validate_trade_response(request, response)
            if response.get('decline') is True:
                return None
            if 'region' in response:
                return response['region']
    # The raw callback's explicit/default contract retains its old proxy.
    # Durable sessions never reach this branch for a missing human answer.
    def blue_pieces(region):
        pieces = state['spaces'][region].get('pieces', {}).get(AEDUI, {})
        return pieces.get(ALLY, 0) + pieces.get(CITADEL, 0)
    return max(sorted(regions), key=blue_pieces)


@contextmanager
def trade_declarations(state):
    """Share one Trade's declarations across its threshold check and effects."""
    with supply_agreement_scope(state):
        scope = (nullcontext() if '_supply_line_query' in state
                 else supply_query_scope(state))
        with scope:
            yield


def roman_agreement(state):
    """The §4.4.1 Roman declaration governs both Supply and the Trade rate."""
    accepted = state.get('_supply_line_agreements', {})
    replies = state.get('_supply_line_query', {})
    if accepted.get(_ROMAN_DECLARATION):
        return True
    if _ROMAN_DECLARATION in replies:
        return replies[_ROMAN_DECLARATION]
    if ROMANS in state.get('non_player_factions', ()):
        from fs_bot.bots.bot_common import np_agrees_to_supply_line
        answer = np_agrees_to_supply_line(ROMANS, AEDUI, state)
    else:
        from fs_bot.engine.agent import consult_agent, AGREEMENT
        response = consult_agent(state, ROMANS, {
            'kind': AGREEMENT, 'request_type': 'trade_roman_agreement',
            'requesting_faction': AEDUI, 'context': {}})
        if response is not None and type(response) is not bool:
            raise ValueError('Roman Trade agreement requires true or false')
        answer = True if response is None else response
    replies[_ROMAN_DECLARATION] = answer
    if answer:
        accepted[_ROMAN_DECLARATION] = True
    return answer


def forecast_trade(state, *, allowed_regions=None, confirm=False):
    """Calculate the exact yield on a copy; confirm only at actual SA time."""
    with trade_declarations(state) if confirm else nullcontext():
        sim = deepcopy({k: v for k, v in state.items() if k != 'decision_agent'})
        if confirm:
            # These are real declarations, before any Resources change.
            # The callback sees the live board, while Trade changes a copy.
            from fs_bot.engine.agent import consult_agent
            sim['_supply_line_query'] = state['_supply_line_query']
            sim['_supply_line_agreements'] = state['_supply_line_agreements']
            sim['decision_agent'] = lambda _board, faction, request: consult_agent(
                state, faction, request)
        else:
            sim['_diviciacus_preview'] = True
        with trade_declarations(sim):
            agreed = roman_agreement(sim)
            return trade(sim, roman_agreed=agreed,
                         allowed_regions=allowed_regions, choose_region=False)['resources_gained']


def trade(state, agreements=None, roman_agreed=False, *, allowed_regions=None,
          trade_region=UNSELECTED, choose_region=True):
    """Execute Trade — Aedui gain Resources from Supply Lines.

    §4.4.1: Aedui receive +1 Resource (or +2 if Romans agreed) for each
    qualifying piece/tribe within Supply Lines.

    Args:
        state: Game state dict. Modified in place.
        agreements: Dict of {faction: bool} for Supply Line agreement.
        roman_agreed: True if Romans agreed to Supply Lines. This
            determines whether +1 or +2 Resources per qualifying item.

    Returns:
        dict with:
            "resources_gained": Total resources gained.
            "per_item": List of (item_type, region/tribe, amount) details.

    Raises:
        CommandError: On rule violations.
    """
    with trade_declarations(state):
        agreed = (state['_supply_line_agreements'].get(_ROMAN_DECLARATION)
                  or roman_agreed)
        # Rome declares even without Control. The same reply applies to
        # every Roman-controlled Region and to the +1/+2 yield (§4.4.1).
        state['_supply_line_query'][_ROMAN_DECLARATION] = agreed
        for region in state['spaces']:
            state['_supply_line_query'][(AEDUI, ROMANS, region)] = agreed
        if agreed:
            state['_supply_line_agreements'][_ROMAN_DECLARATION] = True
        if agreements is not None:
            agreements = dict(agreements, **{ROMANS: agreed})
        return _trade(state, agreements, agreed, allowed_regions=allowed_regions,
                      trade_region=trade_region, choose_region=choose_region)


def _trade(state, agreements, roman_agreed, *, allowed_regions, trade_region, choose_region):
    scenario = state["scenario"]
    result = {"resources_gained": 0, "per_item": []}

    from fs_bot.cards.capabilities import is_capability_active
    from fs_bot.cards.edition import uses_second_edition
    from fs_bot.rules_consts import EVENT_UNSHADED as _EU, EVENT_SHADED as _ESh
    # Subdued & Roman-Allied Tribes under Aedui Control: +1, or +2 only if
    # Romans agreed (§4.4.1).
    base_value = 2 if roman_agreed else 1
    # Card 39 (River Commerce) unshaded: Aedui Allies & Citadels in Supply Lines
    # "always yield +2 Resources each" — that boost applies to those two item
    # types only, not to Subdued/Roman-Allied Tribes.
    commerce = is_capability_active(state, 39, _EU)
    revised_commerce = commerce and uses_second_edition(state)
    aedui_value = 2 if (roman_agreed or (commerce and not revised_commerce)) else 1

    # Find all regions on Supply Lines
    supply_line_regions = set()
    for region in get_playable_regions(scenario, state.get("capabilities")):
        # Revised card 39 removes Supply Lines, rather than retaining the
        # original card's guaranteed +2 for blue pieces. Normal Roman
        # agreement still determines the +1/+2 yield (A Card Reference 39).
        if revised_commerce or has_supply_line(state, region, AEDUI, agreements):
            supply_line_regions.add(region)

    if allowed_regions is not None:
        supply_line_regions.intersection_update(allowed_regions)

    # Ariovistus Diviciacus proximity filter — A4.4, A4.1.2
    # "If the Diviciacus piece is on the map, Suborn, Trade, and Aedui Ambush
    # may occur only within a distance of one Region from Diviciacus."
    # If Diviciacus removed, no filtering (revert to base rules per A4.1.2).
    # Keyed on the PIECE, not the scenario: base-game Aedui never have a
    # Leader, and card O38 can return Diviciacus (with his Ariovistus
    # Leader rules) in The Gallic War second half.
    leader_region = find_leader(state, AEDUI)
    if leader_region is not None:
        supply_line_regions = {
            r for r in supply_line_regions
            if r == leader_region or is_adjacent(r, leader_region)
        }

    # Card A38 (Vergobret) shaded CAPABILITY: "If no Diviciacus, Suborn and
    # Trade only within 1 Region of Bibracte." (With Diviciacus on map the
    # card restricts only Suborn; the A4.1.2 within-1-of-Diviciacus filter
    # above already applies to Trade.) Source: A Card Reference, card A38.
    if leader_region is None and is_capability_active(state, "A38", _ESh):
        from fs_bot.rules_consts import AEDUI_REGION
        supply_line_regions = {
            r for r in supply_line_regions
            if r == AEDUI_REGION or is_adjacent(r, AEDUI_REGION)
        }

    restricted = is_capability_active(state, 39, _ESh)
    if trade_region is not UNSELECTED and not restricted:
        raise CommandError('trade_region is only used with shaded River Commerce (39).')
    if not supply_line_regions:
        if trade_region is not UNSELECTED:
            raise CommandError('The selected Trade Region has no legal Supply Line or is outside the allowed range.')
        return result

    region_items = {}

    # The membership set must not determine the order of the visible/replayed
    # earnings breakdown. Use the board's stable Region order.
    for region in get_playable_regions(scenario, state.get("capabilities")):
        if region not in supply_line_regions:
            continue
        items = []
        # Aedui Allied Tribes and Citadels — §4.4.1
        space = state["spaces"][region]
        aedui_pieces = space.get("pieces", {}).get(AEDUI, {})

        # Aedui Allies
        aedui_allies = aedui_pieces.get(ALLY, 0)
        if aedui_allies > 0:
            gain = aedui_allies * aedui_value
            items.append(("aedui_ally", region, gain))

        # Aedui Citadels
        aedui_citadels = aedui_pieces.get(CITADEL, 0)
        if aedui_citadels > 0:
            gain = aedui_citadels * aedui_value
            items.append(("aedui_citadel", region, gain))

        # Where Aedui Control: Subdued Tribes
        if is_controlled_by(state, region, AEDUI):
            tribes = get_tribes_in_region(region, scenario)
            for tribe in tribes:
                tribe_info = state["tribes"].get(tribe, {})
                allied_faction = tribe_info.get("allied_faction")

                if allied_faction is None and tribe_info.get('status') is None:
                    # Subdued Tribe
                    gain = base_value
                    items.append(
                        ("subdued_tribe", tribe, gain)
                    )
                elif allied_faction == ROMANS and roman_agreed:
                    # Roman Allied Tribe — only if Romans agreed
                    gain = base_value
                    items.append(
                        ("roman_ally", tribe, gain)
                    )

        region_items[region] = items

    if restricted:
        selected = _choose_trade_region(state, region_items, roman_agreed,
                                         trade_region, choose_region)
        result['trade_region'] = selected
        if selected is None:
            result['declined'] = True
            return result
        result['per_item'] = region_items[selected]
    else:
        result['per_item'] = [item for items in region_items.values() for item in items]
    total = sum(item[2] for item in result['per_item'])

    # Cap at MAX_RESOURCES
    current = state["resources"].get(AEDUI, 0)
    actual_gain = min(total, MAX_RESOURCES - current)
    state["resources"][AEDUI] = current + actual_gain

    result["resources_gained"] = actual_gain
    return result
