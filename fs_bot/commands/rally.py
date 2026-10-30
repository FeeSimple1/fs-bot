"""Rally and Recruit commands — Mechanical execution of piece placement.

This module implements the Rally (Gallic/Germanic) and Recruit (Roman)
commands as mechanical execution: given a faction, region, and chosen
action, place the correct pieces per the rules. Bot target selection
(Phase 5) and human input (Phase 6) are NOT implemented here.

Reference: §3.2.1 (Recruit), §3.3.1 (Rally), §3.4.1 (Germanic Rally),
           §3.1.2 (Free Actions), §6.2.1 (Germans Phase Rally),
           A3.2.1, A3.3.1, A3.4.1
"""

from contextlib import contextmanager
from functools import wraps

from fs_bot.rules_consts import (
    # Factions
    ROMANS, ARVERNI, AEDUI, BELGAE, GERMANS,
    FACTIONS, GALLIC_FACTIONS,
    # Piece types
    LEADER, LEGION, AUXILIA, WARBAND, FORT, ALLY, CITADEL, SETTLEMENT,
    FLIPPABLE_PIECES,
    # Piece states
    HIDDEN,
    # Control
    ROMAN_CONTROL, NO_CONTROL,
    FACTION_CONTROL,
    # Scenarios
    BASE_SCENARIOS, ARIOVISTUS_SCENARIOS,
    # Regions
    PROVINCIA, CISALPINA, UBII, SEQUANI,
    BELGICA_REGIONS, GERMANIA_REGIONS,
    # Home regions
    ROMAN_HOME_REGIONS,
    ARVERNI_HOME_REGIONS_BASE, ARVERNI_HOME_REGIONS_ARIOVISTUS,
    AEDUI_HOME_REGIONS, BELGAE_HOME_REGIONS,
    GERMAN_HOME_REGIONS_BASE, GERMAN_HOME_REGIONS_ARIOVISTUS_STATIC,
    # Costs
    RECRUIT_COST, RALLY_COST,
    BELGAE_RALLY_OUTSIDE_BELGICA,
    ARVERNI_RALLY_DEVASTATED_WITH_VERCINGETORIX,
    GERMAN_RALLY_COST_OUTSIDE_GERMANIA_NO_SETTLEMENT,
    GERMAN_RALLY_COST_AT_SETTLEMENT,
    GERMAN_RALLY_COST_IN_GERMANIA,
    GERMAN_COMMAND_COST_BASE,
    # Misc
    ARVERNI_RALLY_EXTRA_WARBAND,
    # Markers
    MARKER_DEVASTATED, MARKER_INTIMIDATED,
    # Leaders
    VERCINGETORIX,
    # Tribes
    TRIBE_FACTION_RESTRICTION,
    TRIBE_SUEBI_NORTH, TRIBE_SUEBI_SOUTH,
    SUEBI_TRIBES,
    # Senate
    ADULATION,
)

from fs_bot.board.pieces import (
    place_piece, remove_piece, count_pieces, get_available,
    get_leader_in_region, PieceError,
)
from fs_bot.board.control import (
    is_controlled_by, refresh_all_control, calculate_control,
)
from fs_bot.map.map_data import (
    get_adjacent, get_tribes_in_region, get_tribe_data,
    get_region_data, get_region_group, is_city_tribe,
    ALL_REGION_DATA, is_region_playable, get_gallia_togata_card,
)
from fs_bot.commands.common import (CommandError, _is_devastated, _is_intimidated,
                                    is_free_action)


# ============================================================================
# SUPPLY LINE (§3.2.1, A3.2.1)
# ============================================================================

@contextmanager
def supply_agreement_scope(state):
    """Keep human promises and PR-07 NP Aedui replies through one action."""
    key = '_supply_line_agreements'
    if key in state:
        yield
        return
    state[key] = {}
    try:
        yield
    finally:
        state.pop(key, None)


def preserve_supply_agreements(function):
    """Share an outer action's accepted agreements with nested execution."""
    @wraps(function)
    def wrapped(state, *args, **kwargs):
        with supply_agreement_scope(state):
            return function(state, *args, **kwargs)
    return wrapped


@contextmanager
def supply_query_scope(state):
    """One Recruit entry's precheck and execution use the same replies.

    A human refusal is not binding on distinct later requests. PR-07 keeps
    the NP Aedui's answer, including refusal, for the whole outer action.
    """
    key = '_supply_line_query'
    previous = state.get(key)
    state[key] = {}
    try:
        yield
    finally:
        if previous is None:
            state.pop(key, None)
        else:
            state[key] = previous


def np_aedui_supply_key(state, requester, controller):
    """PR-07: the automated Aedui answer for human Rome has no Region key.

    Human-controlled factions retain their independent Region declarations.
    This adopted project ruling remains subject to authoritative correction.
    The final None distinguishes the action answer from every physical Region.
    """
    non_players = state.get('non_player_factions', ())
    if (requester == ROMANS and controller == AEDUI
            and AEDUI in non_players and ROMANS not in non_players):
        return (ROMANS, AEDUI, None)
    return None


def _borders_cisalpina_or_provincia(region, scenario):
    """Check if a region borders Cisalpina and/or Provincia for Supply Line.

    Base game: Supply Line must reach a border with Cisalpina — §3.2.1.
    NOTE: Ubii, Sequani, and Provincia border Cisalpina.
    One alone under friendly or No Control qualifies.

    Ariovistus: Supply Line must include Provincia and/or Cisalpina — A3.2.1.
    Cisalpina is always playable in Ariovistus.
    """
    if scenario in ARIOVISTUS_SCENARIOS:
        # A3.2.1: chain must include Provincia and/or Cisalpina
        return region in (PROVINCIA, CISALPINA)
    else:
        # §3.2.1: chain must reach a border with Cisalpina
        # Ubii, Sequani, and Provincia border Cisalpina — §3.2.1 NOTE
        # Cisalpina is unplayable in base game so BFS won't reach it,
        # but these three regions qualify as endpoints.
        return region in (UBII, SEQUANI, PROVINCIA, CISALPINA)


def _region_allows_supply_line(state, region, faction, agreements=None):
    """Check if a region can be part of a Supply Line.

    Per §3.2.1 (and A3.1's general note that Ariovistus Germanic
    Commands can cost or add to German Resources — the per-Command
    A3.4.x citations carry the specifics): each region in the chain
    must have No Control OR be under
    Control of a faction that agrees. Germans never agree (§3.4.5).
    In Ariovistus: Arverni never agree (A1.5.2).

    Args:
        state: Game state dict.
        region: Region to check.
        faction: The faction executing the Recruit.
        agreements: Dict of {faction: bool} for agreement declarations.
            If None, use recorded replies, NP rules, or the player agent.
    """
    space = state["spaces"].get(region, {})
    control = space.get("control", NO_CONTROL)

    if control == NO_CONTROL:
        return True

    # Own control always OK
    if control == FACTION_CONTROL.get(faction):
        return True

    # Check who controls and whether they agree
    for fac in FACTIONS:
        if FACTION_CONTROL.get(fac) == control:
            controlling_faction = fac
            break
    else:
        return False

    # Germans never agree in base game — §3.4.5
    # In Ariovistus, Germans are a full faction and may agree — A3.2.1
    if controlling_faction == GERMANS:
        if state["scenario"] in BASE_SCENARIOS:
            return False
        # Ariovistus: fall through to agreements check below

    # In Ariovistus, Arverni never agree — A1.5.2
    if (state["scenario"] in ARIOVISTUS_SCENARIOS
            and controlling_faction == ARVERNI):
        return False

    # Check explicit agreements
    if agreements is not None:
        return agreements.get(controlling_faction, False)

    # Agent hook: a human/LLM-controlled controlling Faction decides whether to
    # agree to the Supply Line through its Region (§3.2.1/§1.5.2).
    from fs_bot.engine.agent import consult_agent, AGREEMENT
    key = (faction, controlling_faction, region)
    accepted = state.get('_supply_line_agreements')
    queries = state.get('_supply_line_query')
    action_key = np_aedui_supply_key(state, faction, controlling_faction)
    # Historical confirmations can be Region-keyed. A new action-wide
    # refusal cannot revoke a permission already granted for this Region.
    from fs_bot.engine.recruit_planning import ANSWERS, forecast_answer
    if accepted is not None and accepted.get(key) is True:
        return True
    if state.get(ANSWERS, {}).get(key) is True:
        # Keep this dependency attached to a forecast's resulting plan so
        # confirmation is installed for actual execution after replanning.
        forecast_answer(state, faction, controlling_faction, region)
        return True
    if action_key is not None:
        from fs_bot.engine.supply_retry import current_receipt
        receipt = current_receipt(state)
        if receipt is not None:
            return receipt['answer']
    if action_key is not None and accepted is not None and action_key in accepted:
        return accepted[action_key]
    if accepted is not None and key in accepted:
        return True
    # Recruit forecasts record dependencies without consulting a human.
    # Actual execution uses only the engine's confirmed replies for that
    # concrete plan, including its preceding Build/Scout.
    forecast = forecast_answer(state, faction, controlling_faction, region)
    if forecast is not None:
        return forecast
    if queries is not None and key in queries:
        return queries[key]
    if controlling_faction in state.get('non_player_factions', ()):
        before_rng = state['rng'].getstate()
        # A human plan preview may consider a possible Aedui agreement, but
        # must not resolve its real §8.6.6 die or hide an option on that
        # speculative result. Known answers above still take precedence.
        from fs_bot.engine.victory import calculate_victory_score
        uncertain = (state.get('_diviciacus_preview')
                     and controlling_faction == AEDUI and faction == ROMANS
                     and ROMANS not in state.get('non_player_factions', ())
                     and 10 <= calculate_victory_score(state, ROMANS) <= 12)
        if uncertain:
            answer = True
        else:
            from fs_bot.engine.quarters import cached_np_supply_answer
            answer = cached_np_supply_answer(state, faction, controlling_faction, region)
            if answer is None:
                from fs_bot.engine.supply_retry import resolve_np_supply
                answer = resolve_np_supply(state, controlling_faction, faction)
    else:
        _a = consult_agent(state, controlling_faction, {
            "kind": AGREEMENT, "request_type": "supply_line",
            "requesting_faction": faction, "context": {"region": region}})
        # Raw callers without a player callback retain their default. A
        # missing callback never overrides a Non-player's printed refusal.
        answer = True if _a is None else bool(_a)
    # Record the resolved answer, not a second consult on an unchanged board.
    if queries is not None:
        queries[key] = answer
    if answer and accepted is not None:
        accepted[key] = True
    if (action_key is not None and accepted is not None
            and not state.get('_diviciacus_preview')
            and (answer or state['rng'].getstate() != before_rng)):
        accepted[action_key] = answer
    return answer


@preserve_supply_agreements
def has_supply_line(state, region, faction=ROMANS, agreements=None):
    """Check if a region is within a Supply Line.

    A Supply Line is a chain of adjacent Regions reaching a border with
    Cisalpina (base) or including Provincia/Cisalpina (Ariovistus), each
    region in the chain having No Control or friendly/agreed Control.

    Args:
        state: Game state dict.
        region: Region to check for Supply Line.
        faction: Faction executing the command (default ROMANS).
        agreements: Dict of {faction: bool} for agreement declarations.

    Returns:
        True if a valid Supply Line exists to this region.
    """
    scenario = state["scenario"]

    # BFS to find path to Cisalpina border
    visited = set()
    queue = [region]

    while queue:
        current = queue.pop(0)
        if current in visited:
            continue
        visited.add(current)

        # Check if current region allows the supply line to pass
        if not _region_allows_supply_line(state, current, faction, agreements):
            continue

        # Check if we've reached a border with Cisalpina/Provincia
        if _borders_cisalpina_or_provincia(current, scenario):
            return True

        # Expand to adjacent regions
        for adj in get_adjacent(current, scenario,
                                state.get("capabilities")):
            if adj not in visited:
                queue.append(adj)

    return False


# ============================================================================
# COST CALCULATIONS
# ============================================================================

def recruit_cost(state, region, faction=ROMANS, agreements=None):
    """Calculate the Resource cost for Recruit in a region.

    §3.2.1: 2 Resources per Region; 0 if within a Supply Line.

    Args:
        state: Game state dict.
        region: Region to recruit in.
        faction: Faction (default ROMANS).
        agreements: Supply Line agreement dict.

    Returns:
        Integer Resource cost.
    """
    if is_free_action(state, faction):
        return 0
    from fs_bot.cards.capabilities import is_capability_active
    from fs_bot.rules_consts import EVENT_SHADED as _ES13
    # Card 13 shaded: "Recruit only where Supply Line, paying 2
    # Resources per Region" — the Supply-Line discount is gone.
    if is_capability_active(state, 13, _ES13):
        return RECRUIT_COST
    if has_supply_line(state, region, faction, agreements):
        return 0
    return RECRUIT_COST


def _commius_shaded_rally_control(state, region, faction):
    """Card 55 shaded CAPABILITY "Conspirator": "Belgic Rally costs 0 and
    treats any Region with Belgic pieces as Belgic Controlled." Rally-scoped
    as-if-Control when the Belgae have any piece in the Region.
    Source: Card Reference, card 55 + Tip.
    """
    from fs_bot.cards.capabilities import is_capability_active
    from fs_bot.rules_consts import EVENT_SHADED
    return (faction == BELGAE
            and is_capability_active(state, 55, EVENT_SHADED)
            and count_pieces(state, region, BELGAE) > 0)


def _commius_unshaded_recruit(state, region):
    """Card 55 unshaded CAPABILITY "Atrebatian friend": "Belgica Regions
    for Roman Recruit count as Roman Controlled and +1 Roman Ally." Recruit-
    scoped: as-if-Control in Belgica (even with no Roman pieces) and one
    virtual Ally for the Auxilia cap. Source: Card Reference, card 55 + Tip.
    """
    from fs_bot.cards.capabilities import is_capability_active
    from fs_bot.rules_consts import EVENT_UNSHADED, BELGICA
    return (is_capability_active(state, 55, EVENT_UNSHADED)
            and get_region_group(region) == BELGICA)


def rally_cost(state, region, faction):
    """Calculate the Resource cost for Rally in a region.

    §3.3.1: 1 Resource per Region.
    Belgae outside Belgica: 2 Resources — §3.3.1.
    Arverni in Devastated with Vercingetorix: 2 Resources — §3.3.1.
    Germans base game: 0 (free) — §3.4.
    Germans Ariovistus: 0 in Germania, 1 at Settlement, 2 outside — A3.4.1.

    Args:
        state: Game state dict.
        region: Region to rally in.
        faction: Faction executing Rally.

    Returns:
        Integer Resource cost.
    """
    if is_free_action(state, faction):
        return 0
    scenario = state["scenario"]

    if faction == GERMANS:
        if scenario in BASE_SCENARIOS:
            return GERMAN_COMMAND_COST_BASE
        # Ariovistus — A3.4.1
        if region in GERMANIA_REGIONS:
            return GERMAN_RALLY_COST_IN_GERMANIA
        # Check for Settlement
        if count_pieces(state, region, GERMANS, SETTLEMENT) > 0:
            return GERMAN_RALLY_COST_AT_SETTLEMENT
        return GERMAN_RALLY_COST_OUTSIDE_GERMANIA_NO_SETTLEMENT

    if faction == BELGAE:
        # Card 55 shaded: "Belgic Rally costs 0"
        from fs_bot.cards.capabilities import is_capability_active
        from fs_bot.rules_consts import EVENT_SHADED
        if is_capability_active(state, 55, EVENT_SHADED):
            return 0
        region_group = get_region_group(region)
        from fs_bot.rules_consts import BELGICA
        if region_group != BELGICA:
            return BELGAE_RALLY_OUTSIDE_BELGICA

    if faction == ARVERNI:
        # Check for Devastated + Vercingetorix exception — §3.3.1
        markers = state.get("markers", {}).get(region, {})
        is_devastated = MARKER_DEVASTATED in markers
        has_vercingetorix = (
            get_leader_in_region(state, region, ARVERNI) == VERCINGETORIX
        )
        if is_devastated and has_vercingetorix:
            return ARVERNI_RALLY_DEVASTATED_WITH_VERCINGETORIX

    # Card 43 shaded (Convictolitavis): Aedui Command costs doubled.
    if faction == AEDUI:
        from fs_bot.cards.capabilities import is_capability_active
        from fs_bot.rules_consts import EVENT_SHADED
        if is_capability_active(state, 43, EVENT_SHADED):
            return RALLY_COST * 2

    return RALLY_COST


# ============================================================================
# VALIDATION
# ============================================================================

def _get_home_regions(faction, scenario):
    """Get the home regions (Rally/Recruit symbol) for a faction.

    Args:
        faction: Faction constant.
        scenario: Scenario identifier.

    Returns:
        Tuple of region name constants.
    """
    if faction == ROMANS:
        return ROMAN_HOME_REGIONS
    if faction == ARVERNI:
        if scenario in ARIOVISTUS_SCENARIOS:
            return ARVERNI_HOME_REGIONS_ARIOVISTUS
        return ARVERNI_HOME_REGIONS_BASE
    if faction == AEDUI:
        return AEDUI_HOME_REGIONS
    if faction == BELGAE:
        return BELGAE_HOME_REGIONS
    if faction == GERMANS:
        if scenario in ARIOVISTUS_SCENARIOS:
            return GERMAN_HOME_REGIONS_ARIOVISTUS_STATIC
        return GERMAN_HOME_REGIONS_BASE
    return ()


def _event_rally_option(state, region, faction, option):
    grant = state.get("_rally_event_grant") or {}
    regions = grant.get("regions")
    return (grant.get("faction") == faction and grant.get(option, False)
            and (regions is None or region in regions))


def has_rally_control(state, region, faction):
    """Control for Rally/Recruit only; an Event cannot alter actual Control."""
    return (is_controlled_by(state, region, faction)
            or _event_rally_option(state, region, faction, "as_if_control"))


def validate_recruit_region(state, region):
    """Validate that a region is eligible for Roman Recruit.

    §3.2.1: Not Devastated, and must have Roman Control OR a Roman
    Leader, Ally, or Fort.
    A3.2.1: Not Intimidated unless Roman Leader present.

    Args:
        state: Game state dict.
        region: Region to validate.

    Returns:
        (valid, reason) tuple. valid is True if region is eligible.
    """
    scenario = state["scenario"]

    if not is_region_playable(state, region, ROMANS):
        return False, "Region is not playable for Romans"

    # Not Devastated — §3.2.1
    if (_is_devastated(state, region)
            and not _event_rally_option(state, region, ROMANS, "allow_devastated")):
        return False, "Region is Devastated"

    # Ariovistus: not Intimidated unless Roman Leader — A3.2.1
    if scenario in ARIOVISTUS_SCENARIOS:
        if _is_intimidated(state, region):
            if get_leader_in_region(state, region, ROMANS) is None:
                return False, "Region is Intimidated and has no Roman Leader"

    # Card 13 shaded: "Recruit only where Supply Line".
    from fs_bot.cards.capabilities import is_capability_active as _ica13
    from fs_bot.rules_consts import EVENT_SHADED as _ES13b
    if _ica13(state, 13, _ES13b):
        if not has_supply_line(state, region, ROMANS):
            return False, "Card 13 shaded: Recruit only where Supply Line"

    # Must have Roman Control OR Roman Leader/Ally/Fort — §3.2.1
    has_roman_control = has_rally_control(state, region, ROMANS)
    has_roman_leader = get_leader_in_region(state, region, ROMANS) is not None
    has_roman_ally = count_pieces(state, region, ROMANS, ALLY) > 0
    has_roman_fort = count_pieces(state, region, ROMANS, FORT) > 0

    if not (has_roman_control or has_roman_leader
            or has_roman_ally or has_roman_fort
            or _commius_unshaded_recruit(state, region)
            or (region == CISALPINA and get_gallia_togata_card(state) is not None)):
        return False, "Region has no Roman Control, Leader, Ally, or Fort"

    return True, None


def validate_rally_region(state, region, faction):
    """Validate that a region is eligible for Rally.

    §3.3.1: Not Devastated, and must have faction's Control, Ally,
    Citadel, Arverni Leader, or Rally symbol.
    Exception: Arverni can rally in Devastated if Vercingetorix present.
    A3.3.1/A3.4.1: Intimidation check (Gallic blocked, Germans exempt).

    Args:
        state: Game state dict.
        region: Region to validate.
        faction: Faction executing Rally.

    Returns:
        (valid, reason) tuple.
    """
    scenario = state["scenario"]

    if not is_region_playable(state, region, faction):
        return False, f"Region is not playable for {faction}"

    # Devastated check — §3.3.1, with Vercingetorix exception
    is_devastated = _is_devastated(state, region)
    if (is_devastated
            and not _event_rally_option(state, region, faction, "allow_devastated")):
        # Arverni exception: can rally if Vercingetorix present — §3.3.1
        if (faction == ARVERNI
                and scenario in BASE_SCENARIOS
                and get_leader_in_region(state, region, ARVERNI)
                == VERCINGETORIX):
            pass  # Allowed
        else:
            return False, "Region is Devastated"

    # Intimidation check (Ariovistus only)
    if scenario in ARIOVISTUS_SCENARIOS:
        if faction != GERMANS:
            # Gallic Rally blocked by Intimidation — A3.3.1
            # Unless faction's Leader is present
            if _is_intimidated(state, region):
                if get_leader_in_region(state, region, faction) is None:
                    return (False,
                            "Region is Intimidated and has no "
                            f"{faction} Leader")
        # Germans immune to Intimidation for Rally — A3.4.1

    # Must have effect: faction's Control, Ally, Citadel, Leader,
    # or Rally symbol — §3.3.1
    has_control = (has_rally_control(state, region, faction)
                   or _commius_shaded_rally_control(state, region, faction))
    has_ally = count_pieces(state, region, faction, ALLY) > 0
    has_citadel = count_pieces(state, region, faction, CITADEL) > 0

    # Leader check — Arverni Leader counts in base game
    has_leader = False
    if faction == ARVERNI and scenario in BASE_SCENARIOS:
        has_leader = (get_leader_in_region(state, region, ARVERNI)
                      is not None)

    # Rally symbol = home region
    home_regions = _get_home_regions(faction, scenario)
    has_rally_symbol = region in home_regions

    # Germans in Ariovistus: Settlement regions are also home — A3.4.1
    if (faction == GERMANS and scenario in ARIOVISTUS_SCENARIOS):
        if count_pieces(state, region, GERMANS, SETTLEMENT) > 0:
            has_rally_symbol = True

    # These normal prerequisites are expressly "to have effect" (§3.3.1).
    # A printed addition can supply that effect even in an empty Region;
    # the geography and marker restrictions above still apply (Card 25 tip).
    has_event_addition = _rally_bonus(
        state, region, faction, include_home_bonus=False, include_bonuses=True) > 0
    if not (has_control or has_ally or has_citadel
            or has_leader or has_rally_symbol or has_event_addition):
        return (False,
                f"Region has no {faction} Control, Ally, Citadel, "
                f"Leader, or Rally symbol")

    return True, None


# ============================================================================
# RECRUIT (§3.2.1, A3.2.1)
# ============================================================================

def can_recruit_auxilia(state, region):
    """The normal Recruit base, or an Event that supplies Auxilia there."""
    return (get_leader_in_region(state, region, ROMANS) is not None
            or count_pieces(state, region, ROMANS, ALLY) > 0
            or count_pieces(state, region, ROMANS, FORT) > 0
            or _commius_unshaded_recruit(state, region)
            or (region == CISALPINA and get_gallia_togata_card(state) is not None))


def _count_recruit_auxilia_cap(state, region):
    """Calculate Auxilia placement cap for Recruit in a region.

    §3.2.1: Available Auxilia up to the number of Roman Allied Tribes
    plus one per Leader and Fort there.

    HOME REGION: +1 extra in Provincia — §3.2.1.

    Args:
        state: Game state dict.
        region: Region to recruit in.

    Returns:
        Integer cap.
    """
    gallia = get_gallia_togata_card(state) if region == CISALPINA else None
    if gallia == 5:
        return 2  # Card 5: each Recruit places 2 Auxilia.

    allies = count_pieces(state, region, ROMANS, ALLY)
    leader_count = 1 if get_leader_in_region(state, region, ROMANS) else 0
    forts = count_pieces(state, region, ROMANS, FORT)

    cap = allies + leader_count + forts

    # Card 55 unshaded: Belgica counts "+1 Roman Ally" for Recruit — the
    # Tip allows one more Auxilia than normal, even from a base of none.
    if _commius_unshaded_recruit(state, region):
        cap += 1

    # Home Region bonus: +1 in Provincia — §3.2.1
    if region in ROMAN_HOME_REGIONS:
        cap += 1

    if gallia:
        cap += 1  # A5: Recruit there places +1 Auxilia.

    return cap


def _find_subdued_tribe_for_ally(state, region, faction):
    """Find a valid Subdued tribe for Ally placement in a region.

    §3.2.1 / §3.3.1: Place at a Subdued Tribe, not at faction-restricted
    tribes of other factions, not at Suebi (for non-Germans), not at
    Dispersed tribes.

    Args:
        state: Game state dict.
        region: Region containing tribes.
        faction: Faction placing the Ally.

    Returns:
        List of eligible tribe names.
    """
    scenario = state["scenario"]
    tribes = list(get_tribes_in_region(region, scenario))
    # Card 71's player-named Colony is a real Tribe in its recorded Region,
    # and remains recruitable/rallyable after its original Ally is removed.
    tribes.extend(name for name, info in state.get('tribes', {}).items()
                  if info.get('region') == region and name not in tribes)
    eligible = []

    for tribe_name in tribes:
        try:
            tribe_info = get_tribe_data(tribe_name)
        except KeyError:
            tribe_info = None  # Card 71 player-named Colony, recorded above.

        # Check tribe status — must be Subdued (no existing Ally)
        tribe_state = state.get("tribes", {}).get(tribe_name, {})
        status = tribe_state.get("status")
        allied_faction = tribe_state.get("allied_faction")

        # A tribe with an existing Ally is not Subdued
        if allied_faction is not None:
            continue

        # Check for Dispersed marker
        from fs_bot.rules_consts import DISPERSED, DISPERSED_GATHERING, MARKER_RAZED
        if status in (DISPERSED, DISPERSED_GATHERING, MARKER_RAZED):
            continue

        # Check faction restriction — §1.4.2
        restriction = tribe_info.faction_restriction if tribe_info is not None else None
        if restriction is not None and restriction != faction:
            continue

        # Suebi: only Germans can place there — §1.4.2
        if tribe_name in SUEBI_TRIBES and faction != GERMANS:
            continue

        eligible.append(tribe_name)

    return eligible


def _validate_count(count):
    if type(count) is not int or count < 0:
        raise CommandError('Placement count must be a non-negative integer')


def _chosen_count(count, limits):
    if count is None:
        return limits['max']
    _validate_count(count)
    if not limits['min'] <= count <= limits['max']:
        raise CommandError(f"Placement count must be between {limits['min']} and {limits['max']}")
    return count


def recruit_count_limits(state, region):
    """Total Auxilia, including any compulsory Gallia addition; no mutations."""
    from fs_bot.engine.diviciacus import placement_available
    available = placement_available(state, region, ROMANS, AUXILIA,
                                    get_available(state, ROMANS, AUXILIA))
    cap = _count_recruit_auxilia_cap(state, region)
    gallia = get_gallia_togata_card(state) if region == CISALPINA else None
    minimum = 2 if gallia == 5 else (1 if gallia else 0)
    return {'min': min(minimum, available), 'max': min(cap, available), 'cap': cap}


def _validate_entry_count(entry, troop_action):
    if 'placement_owners' in entry:
        owners = entry['placement_owners']
        if (not isinstance(owners, dict) or set(owners) - {ROMANS, AEDUI}
                or any(type(number) is not int or number < 0 for number in owners.values())):
            raise CommandError('Placement owners require non-negative Roman/Aedui counts')
        if 'warband_mix' in entry:
            raise CommandError('Choose Diviciacus owners or an Enlist mix, not both')
    if 'count' in entry:
        _validate_count(entry['count'])
        if entry.get('action') != troop_action:
            raise CommandError('A placement count is only valid for the troop option')
        if 'warband_mix' in entry:
            raise CommandError('Choose a count or a physical Warband mix, not both')


def recruit_plan_entries(plan):
    if not isinstance(plan, list):
        raise CommandError('Recruit plan must be a list')
    selected = set()
    for entry in plan:
        if (not isinstance(entry, dict) or not isinstance(entry.get('region'), str)
                or entry.get('action') not in ('place_ally', 'place_auxilia')):
            raise CommandError('Recruit entries require a Region and legal option')
        _validate_entry_count(entry, 'place_auxilia')
        if entry['region'] in selected:
            raise CommandError('Recruit selects one option per Region')
        selected.add(entry['region'])
    return plan


def rally_plan_steps(plan):
    """Normalize ordered human steps or the legacy NP lists without changing order."""
    if not isinstance(plan, dict):
        raise CommandError('Rally plan must be an object')
    if 'steps' in plan:
        if set(plan) != {'steps'} or not isinstance(plan['steps'], list):
            raise CommandError('Ordered Rally steps cannot be mixed with legacy lists')
        steps = plan['steps']
        for entry in steps:
            if (not isinstance(entry, dict)
                    or set(entry) - {'region', 'action', 'tribe', 'count', 'warband_mix',
                                     'placement_owners', 'timing_actions'}):
                raise CommandError('Invalid ordered Rally step')
    else:
        steps = []
        for key, action in (('citadels', 'place_citadel'), ('allies', 'place_ally'),
                            ('warbands', 'place_warbands')):
            entries = plan.get(key) or []
            if not isinstance(entries, list):
                raise CommandError('Rally options must be lists')
            for entry in entries:
                if isinstance(entry, str):
                    steps.append({'region': entry, 'action': action})
                elif isinstance(entry, dict):
                    steps.append(dict(entry, action=action))
                else:
                    raise CommandError('Invalid Rally option entry')
    for entry in steps:
        if (not isinstance(entry, dict) or not isinstance(entry.get('region'), str)
                or entry.get('action') not in ('place_ally', 'place_citadel', 'place_warbands')):
            raise CommandError('Rally entries require a Region and legal option')
        _validate_entry_count(entry, 'place_warbands')
    return steps


def recruit_in_region(state, region, action, *, tribe=None, free=False,
                      agreements=None, count=None):
    """Execute Roman Recruit in a single region.

    This is the mechanical execution. The caller decides which region
    and which action.

    Args:
        state: Game state dict. Modified in place.
        region: Region to recruit in.
        action: One of:
            "place_ally" — Place 1 Roman Ally at a Subdued Tribe.
            "place_auxilia" — Place Auxilia up to the cap.
        tribe: For "place_ally", the specific tribe to place at.
            Must be a valid Subdued tribe.
        free: If True, no Resource cost (Event-granted, §3.1.2).
        agreements: Supply Line agreement dict for cost calculation.

    Returns:
        Dict with results:
            "action": action taken
            "pieces_placed": {piece_type: count}
            "cost": Resources spent
            "tribe_allied": tribe name if ally placed, else None

    Raises:
        CommandError: If the action violates rules.
    """
    scenario = state["scenario"]
    if count is not None:
        _validate_count(count)
        if action != 'place_auxilia':
            raise CommandError('A Recruit count is only valid for Auxilia')

    # Validate region
    valid, reason = validate_recruit_region(state, region)
    if not valid:
        raise CommandError(f"Cannot Recruit in {region}: {reason}")

    # Calculate cost
    cost = 0 if free else recruit_cost(state, region, ROMANS, agreements)

    # Check resources
    if not free and cost > 0:
        current_resources = state["resources"].get(ROMANS, 0)
        if current_resources < cost:
            raise CommandError(
                f"Romans have {current_resources} Resources, "
                f"need {cost} to Recruit in {region}"
            )

    result = {
        "action": action,
        "pieces_placed": {},
        "cost": cost,
        "tribe_allied": None,
        "region": region,
    }

    if action == "place_ally":
        # §3.2.1: If under Roman Control, or if Caesar is there, place
        # one Available Roman Ally at a Subdued Tribe
        has_roman_control = (has_rally_control(state, region, ROMANS)
                             or _commius_unshaded_recruit(state, region))
        from fs_bot.rules_consts import CAESAR
        has_caesar = (get_leader_in_region(state, region, ROMANS) == CAESAR)

        if not (has_roman_control or has_caesar):
            raise CommandError(
                "Place Ally requires Roman Control or Caesar in region"
            )

        if tribe is None:
            raise CommandError("Must specify tribe for Ally placement")

        # Validate the tribe
        eligible = _find_subdued_tribe_for_ally(state, region, ROMANS)
        if tribe not in eligible:
            raise CommandError(
                f"Tribe {tribe} is not eligible for Roman Ally placement"
            )

        # Check Available
        if get_available(state, ROMANS, ALLY) < 1:
            raise CommandError("No Roman Allies Available")

        # Deduct cost
        if not free and cost > 0:
            state["resources"][ROMANS] -= cost

        # Place the Ally
        place_piece(state, region, ROMANS, ALLY)

        # Update tribe status
        state["tribes"][tribe]["allied_faction"] = ROMANS
        state["tribes"][tribe]["status"] = None  # Allied now

        result["pieces_placed"][ALLY] = 1
        result["tribe_allied"] = tribe

    elif action == "place_auxilia":
        # §3.2.1: If Region has Roman Leader, Allied Tribe, or Fort,
        # place Auxilia up to cap
        if not can_recruit_auxilia(state, region):
            raise CommandError(
                "Place Auxilia requires Roman Leader, Ally, or Fort in region"
            )

        cap = _count_recruit_auxilia_cap(state, region)
        from fs_bot.engine.diviciacus import placement_available
        available = placement_available(state, region, ROMANS, AUXILIA,
                                        get_available(state, ROMANS, AUXILIA))
        to_place = _chosen_count(count, recruit_count_limits(state, region))

        if to_place <= 0:
            # Deduct cost even if nothing placed (region was selected)
            if not free and cost > 0:
                state["resources"][ROMANS] -= cost
            result["pieces_placed"][AUXILIA] = 0
            return result

        # Deduct cost
        if not free and cost > 0:
            state["resources"][ROMANS] -= cost

        # Place Auxilia (Hidden per §1.4.3)
        place_piece(state, region, ROMANS, AUXILIA, to_place)

        result["pieces_placed"][AUXILIA] = to_place

    else:
        raise CommandError(f"Unknown Recruit action: {action}")

    # A5 adds an Auxilia to Recruit, including the Allied-Tribe option.
    if action == 'place_ally' and region == CISALPINA and get_gallia_togata_card(state):
        from fs_bot.engine.diviciacus import placement_available
        bonus = min(2 if get_gallia_togata_card(state) == 5 else 1,
                    placement_available(state, region, ROMANS, AUXILIA,
                                          get_available(state, ROMANS, AUXILIA)))
        if bonus:
            place_piece(state, region, ROMANS, AUXILIA, bonus)
            result['pieces_placed'][AUXILIA] = bonus

    # Refresh control
    refresh_all_control(state)

    return result


# ============================================================================
# RALLY — GALLIC (§3.3.1, A3.3.1)
# ============================================================================

def _gallic_warband_cap(state, region, faction):
    """Calculate Warband placement cap for Gallic Rally.

    §3.3.1:
    - Aedui/Belgae: up to number of Allied Tribes and Citadels there.
    - Arverni: up to Allies + Citadels + Leaders + 1.

    Args:
        state: Game state dict.
        region: Region.
        faction: Faction.

    Returns:
        Integer cap.
    """
    allies = count_pieces(state, region, faction, ALLY)
    citadels = count_pieces(state, region, faction, CITADEL)

    if faction == ARVERNI:
        # Card 30 (Vercingetorix's Elite) unshaded capability: "Arverni Rally
        # places Warbands up to Allies+Citadels (not Leader+1)."
        from fs_bot.cards.capabilities import is_capability_active
        from fs_bot.rules_consts import EVENT_UNSHADED as _EU
        if is_capability_active(state, 30, _EU):
            return allies + citadels
        leader_count = (
            1 if get_leader_in_region(state, region, ARVERNI) else 0
        )
        return allies + citadels + leader_count + ARVERNI_RALLY_EXTRA_WARBAND
    else:
        return allies + citadels


def _german_warband_cap(state, region):
    """Calculate Warband placement cap for Germanic Rally.

    §3.4.1 (base): up to number of Germanic Allied Tribes.
    A3.4.1 (Ariovistus): up to Germanic Allies plus Settlements.

    Args:
        state: Game state dict.
        region: Region.

    Returns:
        Integer cap.
    """
    allies = count_pieces(state, region, GERMANS, ALLY)
    if state["scenario"] in ARIOVISTUS_SCENARIOS:
        settlements = count_pieces(state, region, GERMANS, SETTLEMENT)
        return allies + settlements
    return allies


def _rally_bonus(state, region, faction, *, include_home_bonus, include_bonuses):
    if not include_bonuses:
        return 0
    from fs_bot.cards.capabilities import is_capability_active, get_capability_owner
    from fs_bot.rules_consts import EVENT_SHADED, PICTONES, ARVERNI_REGION, NERVII
    bonus = 0
    if (is_capability_active(state, 25, EVENT_SHADED)
            and get_capability_owner(state, 25) == faction
            and region in (PICTONES, ARVERNI_REGION)):
        bonus += 2
    if faction == BELGAE and region == NERVII and is_capability_active(state, 'A70', EVENT_SHADED):
        bonus += 2
    if (include_home_bonus and faction == GERMANS and state['scenario'] in ARIOVISTUS_SCENARIOS
            and (region in GERMANIA_REGIONS or count_pieces(state, region, faction, SETTLEMENT))):
        bonus += 1
    return bonus


def _ordinary_rally_cap(state, region, faction, *, include_home_bonus, bonus):
    scenario = state['scenario']
    ally = count_pieces(state, region, faction, ALLY)
    if faction == GERMANS:
        settlement = (count_pieces(state, region, faction, SETTLEMENT)
                      if scenario in ARIOVISTUS_SCENARIOS else 0)
        home = region in _get_home_regions(faction, scenario) or bool(settlement)
        cap = _german_warband_cap(state, region)
        if not ally and not settlement and not home and not bonus:
            raise CommandError('Place Warbands requires a Germanic Ally or Settlement')
        if home and not (include_home_bonus and scenario in ARIOVISTUS_SCENARIOS):
            cap = max(1, cap)
        return cap
    home = region in _get_home_regions(faction, scenario)
    base = ally or count_pieces(state, region, faction, CITADEL)
    if faction == ARVERNI:
        base = base or get_leader_in_region(state, region, faction) is not None
    if base:
        cap = _gallic_warband_cap(state, region, faction)
    elif home:
        cap = 1
    elif bonus:
        cap = 0
    else:
        raise CommandError('Place Warbands requires an Ally or Citadel, eligible Leader, or Home Region')
    return max(1, cap) if home else cap


def rally_count_limits(state, region, faction, *, include_home_bonus=False,
                       include_bonuses=True, max_pieces=None):
    """Total Warbands for this option; cap excludes physical pool limits."""
    if max_pieces is not None and (type(max_pieces) is not int or max_pieces < 1):
        raise CommandError('Rally piece limit must be a positive integer')
    from fs_bot.engine.diviciacus import placement_available
    available = placement_available(state, region, faction, WARBAND,
                                    get_available(state, faction, WARBAND))
    bonus = _rally_bonus(state, region, faction, include_home_bonus=include_home_bonus,
                         include_bonuses=include_bonuses)
    ordinary = _ordinary_rally_cap(state, region, faction,
        include_home_bonus=include_home_bonus, bonus=bonus)
    cap = ordinary + bonus
    if max_pieces is not None:
        cap = min(cap, max_pieces)
    minimum = bonus
    if faction == GERMANS and state['scenario'] in BASE_SCENARIOS and region in GERMANIA_REGIONS:
        minimum = max(1, minimum)
    return {'min': min(minimum, available, cap), 'max': min(cap, available), 'cap': cap}


def _place_rally_mix(state, region, mix, result):
    from fs_bot.commands.sa_enlist import BORROW_KEY
    for owner, number in mix.items():
        if number:
            place_piece(state, region, owner, WARBAND, number)
    context = state[BORROW_KEY]
    context['affected'] += mix[GERMANS]
    if mix[GERMANS]:
        ledger = context['pieces'].setdefault(region, {})
        ledger[HIDDEN] = ledger.get(HIDDEN, 0) + mix[GERMANS]
    result['warband_owners'] = mix


def _mixed_warband_available(state):
    """An Enlist placement cannot exceed the remaining four-piece allowance."""
    from fs_bot.commands.sa_enlist import BORROW_KEY
    from fs_bot.rules_consts import ENLIST_MAX_GERMAN_PIECES_ARIOVISTUS
    germans = get_available(state, GERMANS, WARBAND)
    if state['scenario'] in ARIOVISTUS_SCENARIOS:
        affected = state.get(BORROW_KEY, {}).get('affected', 0)
        germans = min(germans, max(0, ENLIST_MAX_GERMAN_PIECES_ARIOVISTUS - affected))
    return get_available(state, BELGAE, WARBAND) + germans


def validate_rally_sequence(state, faction, steps):
    """Check an ordered plan's structure without predicting later board state.

    A Special Activity or a legal Vercingetorix entry can change which option
    is available. The live option check still applies when each step resolves.
    A two-option Region must remain one contiguous selection (§§3.1, 3.3.1).
    """
    selected = {}
    previous = None
    for entry in steps:
        region, action = entry['region'], entry['action']
        prior = selected.get(region, set())
        if prior:
            if region != previous:
                raise CommandError("Select a Region only once for the Command (§3.1)")
            static = {"place_ally", "place_citadel"}
            pair = (faction == ARVERNI and state['scenario'] in BASE_SCENARIOS
                    and len(prior) == 1 and action not in prior
                    and ((action == 'place_warbands' and prior <= static)
                         or (action in static and prior == {'place_warbands'})))
            german_pair = (faction == GERMANS and state['scenario'] in BASE_SCENARIOS
                           and prior == {'place_ally'} and action == 'place_warbands')
            if not (pair or german_pair):
                raise CommandError("Rally selects one option per Region (§3.3.1/A3.4.1)")
        selected.setdefault(region, set()).add(action)
        previous = region


def validate_rally_option(state, region, faction, action, prior):
    """§3.3.1/A3.4.1: one option per Region, with Vercingetorix's exception.

    ``prior`` contains options already completed in this Region during this
    Command. Vercingetorix permits one Ally OR Citadel and one Warband option,
    in either order. The Region's Resource cost is paid only once.
    """
    if not prior:
        return
    # Base German Rally places an Ally, then Warbands in that Region (§3.4.1).
    if (faction == GERMANS and state["scenario"] in BASE_SCENARIOS
            and prior == {"place_ally"} and action == "place_warbands"):
        return
    vercingetorix = (faction == ARVERNI and state["scenario"] in BASE_SCENARIOS
                    and get_leader_in_region(state, region, faction) == VERCINGETORIX)
    static = {"place_ally", "place_citadel"}
    if (vercingetorix and len(prior) == 1 and action not in prior
            and ((action == "place_warbands" and prior <= static)
                 or (action in static and prior == {"place_warbands"}))):
        return
    raise CommandError("Rally selects one option per Region (§3.3.1/A3.4.1)")


def rally_in_region(state, region, faction, action, *, tribe=None,
                    free=False, warband_mix=None, include_home_bonus=False,
                    max_pieces=None, count=None, include_bonuses=True):
    """Execute Rally in a single region.

    This is the mechanical execution for ONE option in ONE region.
    The caller decides which region and action.

    EXCEPTION: Arverni with Vercingetorix may do BOTH place_ally/citadel
    AND place_warbands — §3.3.1. The caller should make two separate
    calls in that case, one for each action.

    Args:
        state: Game state dict. Modified in place.
        region: Region to rally in.
        faction: Faction executing Rally.
        action: One of:
            "place_ally" — Place 1 Ally at a Subdued Tribe.
            "place_warbands" — Place Warbands up to cap.
            "place_citadel" — Replace Ally with Citadel at a City.
        tribe: For "place_ally", the tribe to place at.
            For "place_citadel", the tribe at the City.
        free: If True, no Resource cost (Event-granted, §3.1.2).

    Returns:
        Dict with results:
            "action": action taken
            "faction": faction
            "region": region
            "pieces_placed": {piece_type: count}
            "pieces_removed": {piece_type: count}
            "cost": Resources spent (0 if free or if cost already paid)
            "tribe_allied": tribe name if ally placed

    Raises:
        CommandError: If the action violates rules.
    """
    scenario = state["scenario"]
    if count is not None:
        _validate_count(count)
        if action != 'place_warbands':
            raise CommandError('A Rally count is only valid for Warbands')
        if warband_mix is not None:
            raise CommandError('Choose a count or a physical Warband mix, not both')

    if max_pieces is not None and (type(max_pieces) is not int
                                    or max_pieces < 1):
        raise CommandError("Rally piece limit must be a positive integer")
    # A3.4.1's extra Warband belongs to the full German Rally, after its
    # chosen Ally/Warbands option. The low-level default remains a single
    # option for callers that explicitly orchestrate a whole procedure.
    home_bonus = (include_bonuses and include_home_bonus and faction == GERMANS
                  and scenario in ARIOVISTUS_SCENARIOS
                  and (region in GERMANIA_REGIONS
                       or count_pieces(state, region, GERMANS, SETTLEMENT) > 0))
    bonus_count = _rally_bonus(state, region, faction,
        include_home_bonus=include_home_bonus, include_bonuses=include_bonuses)
    static_mix = None
    if warband_mix is not None and action != 'place_warbands':
        from fs_bot.commands.sa_enlist import enlist_rally_mix
        if faction != BELGAE or action not in ('place_ally', 'place_citadel'):
            raise CommandError('A physical Warband mix requires a Belgic Rally option')
        available = _mixed_warband_available(state)
        required = min(bonus_count, available)
        if max_pieces is not None:
            required = min(required, max(0, max_pieces - 1))
        static_mix = enlist_rally_mix(state, region, warband_mix, required)
        if sum(static_mix.values()) != required:
            raise CommandError('The static Rally option must place its compulsory bonus Warbands')

    # Validate region
    valid, reason = validate_rally_region(state, region, faction)
    if not valid:
        raise CommandError(f"Cannot Rally in {region}: {reason}")

    # Calculate cost
    cost = 0 if free else rally_cost(state, region, faction)

    result = {
        "action": action,
        "faction": faction,
        "region": region,
        "pieces_placed": {},
        "pieces_removed": {},
        "cost": cost,
        "tribe_allied": None,
    }

    if action == "place_ally":
        # §3.3.1: If faction Controls the region, place one Ally at
        # a Subdued Tribe.
        # Vercingetorix exception: Arverni may place Ally without Control
        has_control = (has_rally_control(state, region, faction)
                       or _commius_shaded_rally_control(state, region,
                                                        faction))

        # Vercingetorix exception — §3.3.1
        has_vercingetorix = False
        if (faction == ARVERNI and scenario in BASE_SCENARIOS):
            has_vercingetorix = (
                get_leader_in_region(state, region, ARVERNI)
                == VERCINGETORIX
            )

        if not (has_control or has_vercingetorix):
            raise CommandError(
                f"Place Ally requires {faction} Control "
                f"(or Vercingetorix for Arverni)"
            )

        if tribe is None:
            raise CommandError("Must specify tribe for Ally placement")

        eligible = _find_subdued_tribe_for_ally(state, region, faction)
        if tribe not in eligible:
            raise CommandError(
                f"Tribe {tribe} is not eligible for {faction} Ally placement"
            )

        if get_available(state, faction, ALLY) < 1:
            raise CommandError(f"No {faction} Allies Available")

        # Deduct cost
        if not free and cost > 0:
            if state["resources"].get(faction, 0) < cost:
                raise CommandError(
                    f"{faction} has {state['resources'].get(faction, 0)} "
                    f"Resources, need {cost}"
                )
            state["resources"][faction] -= cost

        # Place the Ally
        place_piece(state, region, faction, ALLY)

        # Update tribe status
        state["tribes"][tribe]["allied_faction"] = faction
        state["tribes"][tribe]["status"] = None

        result["pieces_placed"][ALLY] = 1
        result["tribe_allied"] = tribe

    elif action == "place_warbands":
        limits = rally_count_limits(state, region, faction,
            include_home_bonus=include_home_bonus, include_bonuses=include_bonuses,
            max_pieces=max_pieces)
        cap = limits['cap']
        to_place = _chosen_count(count, limits)
        mix = None
        if warband_mix is not None:
            from fs_bot.commands.sa_enlist import enlist_rally_mix
            if faction != BELGAE:
                raise CommandError("Only Belgic Enlist can borrow Rally Warbands")
            mix = enlist_rally_mix(state, region, warband_mix, cap)
            to_place = sum(mix.values())
            if to_place < min(bonus_count, cap, _mixed_warband_available(state)):
                raise CommandError('Rally composition omits compulsory additional Warbands')

        # Found via play: an empty Available pool (or zero cap) made the
        # Rally charge Resources while placing nothing. A no-effect
        # selection is refused before payment, like other no-effect cases.
        if to_place <= 0 and count is None and warband_mix is None:
            raise CommandError(
                f"Rally would place no Warbands in {region} "
                f"(maximum {limits['max']})"
            )

        # Deduct cost
        if not free and cost > 0:
            if state["resources"].get(faction, 0) < cost:
                raise CommandError(
                    f"{faction} has {state['resources'].get(faction, 0)} "
                    f"Resources, need {cost}"
                )
            state["resources"][faction] -= cost

        if to_place > 0:
            if mix is None:
                place_piece(state, region, faction, WARBAND, to_place)
            else:
                _place_rally_mix(state, region, mix, result)

        result["pieces_placed"][WARBAND] = to_place
        if home_bonus:
            result['home_bonus'] = min(1, to_place)

    elif action == "place_citadel":
        # §3.3.1: If the Faction has an Allied Tribe at a City,
        # replace the Ally with that Faction's Citadel.
        if tribe is None:
            raise CommandError("Must specify tribe for Citadel placement")

        # Validate tribe is a city
        if not is_city_tribe(tribe):
            raise CommandError(f"Tribe {tribe} does not have a City")

        # Validate faction has Ally at this tribe
        tribe_state = state.get("tribes", {}).get(tribe, {})
        if tribe_state.get("allied_faction") != faction:
            raise CommandError(
                f"Tribe {tribe} does not have a {faction} Ally"
            )

        # §3.3.1: a Citadel is placed by replacing a City ALLY. A Region's one
        # City holds at most one Citadel, so if the Faction already has a
        # Citadel here the City is Citadel-backed (no Ally to replace) — reject,
        # else a 2nd Citadel would be placed in the Region (and a different
        # tribe's Ally removed in its stead).
        if count_pieces(state, region, faction, CITADEL) >= 1:
            raise CommandError(
                f"{faction} already has a Citadel in {region} "
                f"(City has no Ally to replace)"
            )
        # There must be an actual Ally disc of the Faction in the Region (the
        # City tribe's Ally) to replace.
        if count_pieces(state, region, faction, ALLY) < 1:
            raise CommandError(
                f"No {faction} Ally in {region} to replace with a Citadel"
            )

        # Check Available Citadels
        if get_available(state, faction, CITADEL) < 1:
            raise CommandError(f"No {faction} Citadels Available")

        # Deduct cost
        if not free and cost > 0:
            if state["resources"].get(faction, 0) < cost:
                raise CommandError(
                    f"{faction} has {state['resources'].get(faction, 0)} "
                    f"Resources, need {cost}"
                )
            state["resources"][faction] -= cost

        # Remove the Ally, place the Citadel — §1.4.1
        remove_piece(state, region, faction, ALLY, to_available=True)
        place_piece(state, region, faction, CITADEL)

        # Tribe remains allied to the faction (now via Citadel)
        # The tribe status doesn't change — still controlled by faction

        result["pieces_placed"][CITADEL] = 1
        result["pieces_removed"][ALLY] = 1

    else:
        raise CommandError(f"Unknown Rally action: {action}")

    if bonus_count and action != 'place_warbands':
        placed = sum(result["pieces_placed"].values())
        if max_pieces is None or placed < max_pieces:
            from fs_bot.engine.diviciacus import placement_available
            available = placement_available(state, region, faction, WARBAND,
                                            get_available(state, faction, WARBAND))
            bonus = sum(static_mix.values()) if static_mix is not None else min(bonus_count, available)
            if max_pieces is not None:
                bonus = min(bonus, max_pieces - placed)
            if bonus:
                if static_mix is not None:
                    _place_rally_mix(state, region, static_mix, result)
                else:
                    place_piece(state, region, faction, WARBAND, bonus)
            result['home_bonus' if home_bonus else 'bonus_warbands'] = bonus
            if bonus:
                result["pieces_placed"][WARBAND] = (
                    result["pieces_placed"].get(WARBAND, 0) + bonus)

    # Refresh control
    refresh_all_control(state)

    return result


# ============================================================================
# GERMANIC RALLY — ARIOVISTUS HOME BONUS (A3.4.1)
# ============================================================================

def german_rally_home_bonus(state, region):
    """Place the Germanic home region bonus Warband.

    A3.4.1: At the end of Germanic Rally in each Region that has a
    Settlement or is in Germania, place one additional German Warband
    there, regardless of whether the Rally placed an Ally, Warbands,
    or nothing.

    This should be called AFTER the main rally_in_region() call.

    Args:
        state: Game state dict. Modified in place.
        region: Region to check for bonus.

    Returns:
        1 if bonus Warband placed, 0 otherwise.
    """
    scenario = state["scenario"]
    if scenario not in ARIOVISTUS_SCENARIOS:
        return 0

    is_germania = region in GERMANIA_REGIONS
    has_settlement = count_pieces(state, region, GERMANS, SETTLEMENT) > 0

    if not (is_germania or has_settlement):
        return 0

    # Check Available
    if get_available(state, GERMANS, WARBAND) < 1:
        return 0

    place_piece(state, region, GERMANS, WARBAND)
    refresh_all_control(state)
    return 1


# ============================================================================
# GERMANS PHASE RALLY (§6.2.1) — Base Game Only
# ============================================================================

def germans_phase_rally(state):
    """Execute the Germans Phase Rally procedure — §6.2.1.

    This is the base-game-only deterministic rally for the Germanic
    non-player faction during Winter. It uses state["rng"] for random
    choices among equal candidates.

    §6.2.1:
    1. Rally to place as many Germanic Allied Tribes as possible,
       starting with Suebi, then others in Germania, then elsewhere.
    2. Rally to place as many Warbands as possible (including where
       Allies were just placed, and in un-Devastated Germania even
       if no Germanic Allies).
    3. Choose among equal locations randomly.
    4. Adjust Control.

    Args:
        state: Game state dict. Modified in place.

    Returns:
        Dict with results:
            "allies_placed": [(region, tribe), ...]
            "warbands_placed": {region: count, ...}
    """
    scenario = state["scenario"]
    if scenario not in BASE_SCENARIOS:
        raise CommandError("Germans Phase Rally is base game only")

    result = {
        "allies_placed": [],
        "warbands_placed": {},
    }
    rng = state["rng"]

    # Step 1: Place as many Germanic Allies as possible — §6.2.1
    # Priority: Suebi first, then other Germania, then elsewhere
    # Per §3.4.1: Germanic Ally only if region has Germanic Control
    # Never at Aedui [Bibracte] or Arverni [Gergovia] — §1.4.2

    # Build ordered list of candidate regions/tribes
    suebi_candidates = []
    germania_candidates = []
    elsewhere_candidates = []

    for region in state["spaces"]:
        region_data = ALL_REGION_DATA.get(region)
        if region_data is None:
            continue
        if not region_data.is_playable(scenario, state.get("capabilities")):
            continue
        if _is_devastated(state, region):
            continue
        if not is_controlled_by(state, region, GERMANS):
            continue

        eligible_tribes = _find_subdued_tribe_for_ally(
            state, region, GERMANS)
        for tribe_name in eligible_tribes:
            entry = (region, tribe_name)
            if tribe_name in SUEBI_TRIBES:
                suebi_candidates.append(entry)
            elif region in GERMANIA_REGIONS:
                germania_candidates.append(entry)
            else:
                elsewhere_candidates.append(entry)

    # Place in priority order, choosing randomly among equals
    for candidate_list in [suebi_candidates, germania_candidates,
                           elsewhere_candidates]:
        while candidate_list and get_available(state, GERMANS, ALLY) > 0:
            # Choose randomly among equal candidates — §6.2.1
            rng.shuffle(candidate_list)
            chosen_region, chosen_tribe = candidate_list.pop(0)

            # Verify still valid (control may have changed)
            if not is_controlled_by(state, chosen_region, GERMANS):
                continue
            eligible = _find_subdued_tribe_for_ally(
                state, chosen_region, GERMANS)
            if chosen_tribe not in eligible:
                continue

            # Place the Ally
            place_piece(state, chosen_region, GERMANS, ALLY)
            state["tribes"][chosen_tribe]["allied_faction"] = GERMANS
            state["tribes"][chosen_tribe]["status"] = None
            result["allies_placed"].append((chosen_region, chosen_tribe))
            refresh_all_control(state)

    # Step 2: Place as many Warbands as possible — §6.2.1
    # Including where Allies were just placed, and in un-Devastated
    # Germania even if no Germanic Allies there.

    # Collect all regions where Warbands can be placed
    warband_regions = []
    for region in state["spaces"]:
        region_data = ALL_REGION_DATA.get(region)
        if region_data is None:
            continue
        if not region_data.is_playable(scenario, state.get("capabilities")):
            continue
        if _is_devastated(state, region):
            continue

        german_allies = count_pieces(state, region, GERMANS, ALLY)
        is_home = region in GERMANIA_REGIONS

        if german_allies > 0 or is_home:
            cap = german_allies  # §3.4.1: up to Germanic Allies
            if is_home:
                cap = max(cap, 1)  # Home: at least 1
            if cap > 0:
                warband_regions.append((region, cap))

    # Place Warbands, choosing randomly among equal regions
    rng.shuffle(warband_regions)
    for region, cap in warband_regions:
        available = get_available(state, GERMANS, WARBAND)
        if available <= 0:
            break
        to_place = min(cap, available)
        if to_place > 0:
            place_piece(state, region, GERMANS, WARBAND, to_place)
            result["warbands_placed"][region] = to_place

    refresh_all_control(state)
    return result
