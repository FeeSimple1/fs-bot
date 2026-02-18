"""Game Engine — Sequence of Play orchestrator per §2.0-§2.4 and A2.0-A2.3.9.

Manages the deck, eligibility, faction turns, and triggers Winter Rounds
and Arverni Phase activations. Does NOT implement bot decision logic
(Phase 5) or card event effects — it provides the framework they plug into.

Reference:
  §2.0-§2.4   Sequence of Play (base game)
  A2.0-A2.3.9 Ariovistus Sequence of Play modifications
  §2.3.1      Eligibility
  §2.3.2      Faction Order
  §2.3.3      Passing
  §2.3.4      Options for Eligible Factions
  §2.3.5      Limited Command
  §2.3.6      Adjust Eligibility
  §2.3.7      Next Card
  §2.3.8      Frost
  §2.4        Winter Card
  A2.3.2      German faction order on base cards
  A2.3.3      German pass resources
  A2.3.9      Arverni Activation (carnyx trigger)
"""

from fs_bot.rules_consts import (
    # Factions
    ROMANS, ARVERNI, AEDUI, BELGAE, GERMANS,
    FACTIONS, GALLIC_FACTIONS,
    # Scenarios
    BASE_SCENARIOS, ARIOVISTUS_SCENARIOS,
    # Eligibility
    ELIGIBLE, INELIGIBLE,
    # Pass resources — §2.3.3, A2.3.3
    PASS_RESOURCES_GALLIC, PASS_RESOURCES_ROMAN,
    PASS_RESOURCES_GERMAN_ARIOVISTUS,
    # Winter
    WINTER_CARD,
    # Resources cap
    MAX_RESOURCES,
)
from fs_bot.cards.card_data import (
    get_card,
    get_faction_order as _card_get_faction_order,
    card_has_carnyx_trigger,
)
from fs_bot.engine.winter import run_winter_round
from fs_bot.engine.arverni_phase import (
    check_arverni_at_war,
    run_arverni_phase,
)


# ---------------------------------------------------------------------------
# Action constants for turn decisions
# ---------------------------------------------------------------------------

ACTION_COMMAND = "command"               # Command only — §2.3.4
ACTION_COMMAND_SA = "command_sa"         # Command + Special Ability — §2.3.4
ACTION_LIMITED_COMMAND = "limited_command"  # Limited Command — §2.3.5
ACTION_EVENT = "event"                   # Event — §2.3.4
ACTION_PASS = "pass"                     # Pass — §2.3.3

# Actions that make a faction Ineligible — §2.3.6
_INELIGIBLE_ACTIONS = {
    ACTION_COMMAND,
    ACTION_COMMAND_SA,
    ACTION_LIMITED_COMMAND,
    ACTION_EVENT,
}


# ---------------------------------------------------------------------------
# SoP faction lists — who participates in the Sequence of Play
# ---------------------------------------------------------------------------

# Base game: Germans are NP procedure (§6.2), NOT in SoP — §2.3
_SOP_FACTIONS_BASE = (ROMANS, ARVERNI, AEDUI, BELGAE)

# Ariovistus: Arverni are game-run (A6.2), Germans join SoP — A2.0
_SOP_FACTIONS_ARIOVISTUS = (ROMANS, GERMANS, AEDUI, BELGAE)


def get_sop_factions(state):
    """Return the factions that participate in the Sequence of Play.

    Base game: Romans, Arverni, Aedui, Belgae (Germans are §6.2 NP).
    Ariovistus: Romans, Germans, Aedui, Belgae (Arverni are A6.2 NP).

    Args:
        state: Game state dict.

    Returns:
        Tuple of faction constants.
    """
    if state["scenario"] in ARIOVISTUS_SCENARIOS:
        return _SOP_FACTIONS_ARIOVISTUS
    return _SOP_FACTIONS_BASE


# ============================================================================
# DECK MANAGEMENT
# ============================================================================

def is_winter_card(card_id):
    """Check if card_id is a Winter card — §2.4.

    Winter cards are stored in the deck as the WINTER_CARD constant.
    """
    return card_id == WINTER_CARD


def draw_card(state):
    """Draw the top card from the deck — §2.3.7.

    Moves the top card from state["deck"] to state["played_cards"].
    Sets state["current_card"] to the drawn card.
    Sets state["next_card"] to the new top of deck (or None if empty).

    Returns:
        The drawn card_id.

    Raises:
        IndexError: If the deck is empty.
    """
    deck = state["deck"]
    if not deck:
        raise IndexError("Deck is empty — cannot draw")

    card_id = deck.pop(0)
    state["played_cards"].append(card_id)
    state["current_card"] = card_id
    state["next_card"] = deck[0] if deck else None
    return card_id


def start_game(state):
    """Set up the first card display — §2.2.

    §2.2: Reveal the top card of the draw deck onto the played cards pile,
    then reveal the next card on top of the draw deck. All factions start
    Eligible.

    Args:
        state: Game state dict. Modified in place.

    Returns:
        The first current_card id.
    """
    # Draw the first card → becomes the current card
    card_id = draw_card(state)

    # Mark all SoP factions Eligible — §2.3.1: "All Factions start the
    # game Eligible"
    for faction in FACTIONS:
        state["eligibility"][faction] = ELIGIBLE

    return card_id


def advance_to_next_card(state):
    """Move the draw deck's top card onto the played pile — §2.3.7.

    After adjusting eligibility, the upcoming card becomes the current
    card and the next card in the deck is revealed.

    Returns:
        The new current card_id, or None if deck is empty.
    """
    deck = state["deck"]
    if not deck:
        return None
    return draw_card(state)


# ============================================================================
# FROST — §2.3.8
# ============================================================================

def is_frost(state):
    """Check if Frost applies on the current card — §2.3.8.

    Frost applies on the last Event card before each Winter card.
    This is true when the upcoming card (state["next_card"]) is a
    Winter card and the current card is NOT a Winter card.

    Returns:
        True if Frost is active.
    """
    current = state["current_card"]
    upcoming = state["next_card"]
    if current is None or upcoming is None:
        return False
    # Frost applies when the current card is an Event card and the
    # upcoming card is a Winter card
    return not is_winter_card(current) and is_winter_card(upcoming)


# ============================================================================
# FACTION ORDER AND ELIGIBILITY — §2.3.1, §2.3.2, A2.3.2
# ============================================================================

def get_faction_order(state):
    """Get the faction initiative order for the current card — §2.3.2.

    Returns the factions in card order, filtered to only those in the
    Sequence of Play for the current scenario. In Ariovistus, Germans
    use the Arverni symbol position on base game cards (A2.3.2).

    Args:
        state: Game state dict.

    Returns:
        Tuple of faction constants in card initiative order,
        containing only SoP factions.
    """
    card_id = state["current_card"]
    scenario = state["scenario"]
    sop = set(get_sop_factions(state))

    # Get raw faction order from card metadata
    raw_order = _card_get_faction_order(card_id, scenario)

    # A2.3.2: In Ariovistus, Germans use the Arverni symbol position
    # on base game cards (cards "from Falling Sky"). On new A-prefix
    # cards, Germans have their own "Ge" symbol.
    if scenario in ARIOVISTUS_SCENARIOS:
        mapped = []
        for faction in raw_order:
            if faction == ARVERNI:
                # Arverni symbol → Germans position in Ariovistus
                mapped.append(GERMANS)
            else:
                mapped.append(faction)
        raw_order = tuple(mapped)

    # Filter to only SoP factions, preserving card order
    return tuple(f for f in raw_order if f in sop)


def get_eligible_factions(state):
    """Return factions whose eligibility is ELIGIBLE, in card order — §2.3.2.

    Args:
        state: Game state dict.

    Returns:
        List of faction constants, ordered by the current card's
        faction initiative order.
    """
    card_order = get_faction_order(state)
    return [f for f in card_order
            if state["eligibility"].get(f) == ELIGIBLE]


def determine_eligible_order(state):
    """Determine 1st Eligible, 2nd Eligible, and remaining — §2.3.2.

    The leftmost Eligible faction in card order is 1st Eligible.
    The next leftmost Eligible is 2nd Eligible.

    Args:
        state: Game state dict.

    Returns:
        (first_eligible, second_eligible, remaining_eligible)
        where first/second may be None if not enough Eligible factions,
        and remaining_eligible is a list of any beyond the 2nd.
    """
    eligible = get_eligible_factions(state)
    first = eligible[0] if len(eligible) >= 1 else None
    second = eligible[1] if len(eligible) >= 2 else None
    remaining = eligible[2:] if len(eligible) >= 3 else []
    return first, second, remaining


# ============================================================================
# TURN OPTIONS — §2.3.4
# ============================================================================

def get_first_eligible_options():
    """Return the options available to the 1st Eligible Faction — §2.3.4.

    1st Eligible may:
    - Execute a Command (with or without a Special Ability)
    - Execute the Event
    - Pass

    Returns:
        List of action strings.
    """
    return [ACTION_COMMAND, ACTION_COMMAND_SA, ACTION_EVENT, ACTION_PASS]


def get_second_eligible_options(first_action):
    """Return the options for the 2nd Eligible Faction — §2.3.4.

    Options depend on what the 1st Eligible did:
    - 1st did Command only → 2nd may: Limited Command or Pass
    - 1st did Command + SA → 2nd may: Limited Command, Event, or Pass
    - 1st did Event → 2nd may: Command, Command + SA, or Pass

    Args:
        first_action: The action the 1st Eligible took.

    Returns:
        List of action strings.

    Raises:
        ValueError: If first_action is not a valid 1st Eligible action.
    """
    if first_action == ACTION_COMMAND:
        return [ACTION_LIMITED_COMMAND, ACTION_PASS]
    elif first_action == ACTION_COMMAND_SA:
        return [ACTION_LIMITED_COMMAND, ACTION_EVENT, ACTION_PASS]
    elif first_action == ACTION_EVENT:
        return [ACTION_COMMAND, ACTION_COMMAND_SA, ACTION_PASS]
    else:
        raise ValueError(
            f"Invalid first_action for 2nd Eligible options: "
            f"{first_action!r}"
        )


# ============================================================================
# PASS — §2.3.3
# ============================================================================

def _pass_resources_amount(faction, scenario):
    """Return the Resources gained from Passing — §2.3.3, A2.3.3.

    Gallic factions: +1
    Romans: +2
    Germans (Ariovistus only): +1
    """
    if faction == ROMANS:
        return PASS_RESOURCES_ROMAN
    if faction in GALLIC_FACTIONS:
        return PASS_RESOURCES_GALLIC
    if faction == GERMANS and scenario in ARIOVISTUS_SCENARIOS:
        return PASS_RESOURCES_GERMAN_ARIOVISTUS
    return 0


def execute_pass(state, faction):
    """Execute a Pass for the given faction — §2.3.3.

    The faction remains Eligible for the next card and receives Resources:
    +1 if Gallic, +2 if Roman, +1 if German in Ariovistus.

    Args:
        state: Game state dict. Modified in place.
        faction: The faction that is Passing.

    Returns:
        Dict with {"resources_gained": int}.
    """
    scenario = state["scenario"]
    amount = _pass_resources_amount(faction, scenario)

    old = state["resources"].get(faction, 0)
    new = min(old + amount, MAX_RESOURCES)
    state["resources"][faction] = new
    gained = new - old

    # Faction remains Eligible — §2.3.3
    # (We do NOT mark it INELIGIBLE; adjust_eligibility handles this.)

    return {"resources_gained": gained}


# ============================================================================
# ELIGIBILITY ADJUSTMENT — §2.3.6
# ============================================================================

def adjust_eligibility(state, actions_taken):
    """Adjust eligibility after 1st and 2nd Eligible complete — §2.3.6.

    Rules:
    - Any faction that did NOT execute a Command or Event → Eligible
    - Any faction that executed a Command (including Limited) or Event
      → Ineligible
    - EXCEPTIONS: Events §5.0 free Actions §3.1.2, §5.4
      (handled via "free_action" flag in actions_taken)

    Args:
        state: Game state dict. Modified in place.
        actions_taken: Dict {faction: {"action": str, ...}}
            May contain a "free_action" flag set to True for actions
            that should NOT cause Ineligibility (§3.1.2, §5.4).
    """
    sop = get_sop_factions(state)

    for faction in sop:
        if faction in actions_taken:
            info = actions_taken[faction]
            action = info.get("action")

            # §2.3.6 EXCEPTION: free Actions don't cause Ineligibility
            if info.get("free_action", False):
                state["eligibility"][faction] = ELIGIBLE
                continue

            if action in _INELIGIBLE_ACTIONS:
                state["eligibility"][faction] = INELIGIBLE
            else:
                # Pass or no action → Eligible
                state["eligibility"][faction] = ELIGIBLE
        else:
            # Faction did not act → Eligible
            state["eligibility"][faction] = ELIGIBLE


# ============================================================================
# CARD TURN RESOLUTION — §2.3
# ============================================================================

def resolve_card_turn(state, decision_func):
    """Orchestrate one full Event card turn — §2.3.

    Steps per §2.3:
    1. Check Frost (§2.3.8)
    2. If Ariovistus and card has carnyx trigger: check At War,
       run Arverni Phase if needed BEFORE normal SoP (A2.3.9)
    3. Determine 1st and 2nd Eligible
    4. Execute 1st Eligible's decision (with cascading passes)
    5. Execute 2nd Eligible's decision (with cascading passes)
    6. Adjust eligibility
    7. Return result dict

    The decision_func callback is called when a faction needs to choose.
    It receives (state, faction, options, position) where position is
    "1st_eligible" or "2nd_eligible", and must return a dict with at
    least {"action": action_string}.

    For Phase 4b, the actual command/event execution is NOT performed
    here — the engine records what was decided, and execution is
    delegated to the caller or future phases.

    Args:
        state: Game state dict. Modified in place.
        decision_func: Callable(state, faction, options, position) → dict
            Must return {"action": str, ...}.

    Returns:
        Dict with turn results including frost, arverni_phase,
        actions_taken, etc.
    """
    scenario = state["scenario"]
    result = {
        "card": state["current_card"],
        "frost": False,
        "arverni_phase": None,
        "actions_taken": {},
        "passes": [],
    }

    # Step 1: Frost — §2.3.8
    frost = is_frost(state)
    result["frost"] = frost

    # Step 2: Arverni Phase — A2.3.9
    # If Ariovistus and card has carnyx trigger, check At War.
    # If At War, run Arverni Phase BEFORE normal SoP.
    if scenario in ARIOVISTUS_SCENARIOS:
        card_id = state["current_card"]
        if card_has_carnyx_trigger(card_id, scenario):
            is_at_war, triggering = check_arverni_at_war(state)
            if is_at_war:
                arverni_result = run_arverni_phase(state, is_frost=frost)
                result["arverni_phase"] = arverni_result

    # Steps 3-5: Faction play — §2.3.2, §2.3.3, §2.3.4
    eligible = get_eligible_factions(state)
    actions_taken = {}
    first_action = None

    # --- 1st Eligible (with cascading passes) ---
    first_options = get_first_eligible_options()
    idx = 0
    while idx < len(eligible):
        faction = eligible[idx]
        decision = decision_func(state, faction, first_options,
                                 "1st_eligible")
        action = decision["action"]

        if action == ACTION_PASS:
            pass_result = execute_pass(state, faction)
            actions_taken[faction] = {
                "action": ACTION_PASS, **pass_result,
            }
            result["passes"].append(faction)
            idx += 1
            continue  # Next eligible becomes new 1st — §2.3.3
        else:
            # 1st Eligible chose to act
            actions_taken[faction] = decision
            first_action = action
            # Remove this faction from the eligible pool for 2nd slot
            idx += 1
            break
    else:
        # All eligible factions passed — §2.3.3
        result["actions_taken"] = actions_taken
        adjust_eligibility(state, actions_taken)
        return result

    # --- 2nd Eligible (with cascading passes) ---
    if first_action is not None:
        second_options = get_second_eligible_options(first_action)
        while idx < len(eligible):
            faction = eligible[idx]
            decision = decision_func(state, faction, second_options,
                                     "2nd_eligible")
            action = decision["action"]

            if action == ACTION_PASS:
                pass_result = execute_pass(state, faction)
                actions_taken[faction] = {
                    "action": ACTION_PASS, **pass_result,
                }
                result["passes"].append(faction)
                idx += 1
                continue  # Next eligible becomes new 2nd — §2.3.3
            else:
                actions_taken[faction] = decision
                break

    # Step 6: Adjust eligibility — §2.3.6
    result["actions_taken"] = actions_taken
    adjust_eligibility(state, actions_taken)

    return result


# ============================================================================
# WINTER CARD HANDLING — §2.4
# ============================================================================

def resolve_winter_card(state):
    """Handle a Winter card — §2.4.

    Triggers a Winter Round (§6.0). The winter_count is tracked to
    determine final Winter (§2.4.1).

    Args:
        state: Game state dict. Modified in place.

    Returns:
        Dict with winter round results.
    """
    total_winters = _count_winter_cards_in_game(state)
    is_final = (state["winter_count"] + 1 >= total_winters)

    winter_result = run_winter_round(state, is_final=is_final)
    return {
        "type": "winter",
        "is_final": is_final,
        "winter_result": winter_result,
    }


def _count_winter_cards_in_game(state):
    """Count total Winter cards in the game (played + remaining in deck).

    Used to determine if the current Winter is the final one.
    """
    count = 0
    for card_id in state["played_cards"]:
        if is_winter_card(card_id):
            count += 1
    for card_id in state["deck"]:
        if is_winter_card(card_id):
            count += 1
    return count


# ============================================================================
# GAME LOOP — §2.0
# ============================================================================

def play_card(state, decision_func):
    """Play the current card — either an Event card or a Winter card.

    For Event cards: resolve the card turn via resolve_card_turn.
    For Winter cards: run a Winter Round.
    Then advance to the next card.

    Args:
        state: Game state dict. Modified in place.
        decision_func: Callable for faction decisions (Event cards only).
            Signature: (state, faction, options, position) → dict.

    Returns:
        Dict with card result. Includes "game_over" if the game ended.
    """
    card_id = state["current_card"]
    result = {"card": card_id, "game_over": False}

    if is_winter_card(card_id):
        winter_result = resolve_winter_card(state)
        result["type"] = "winter"
        result["winter_result"] = winter_result

        # Check if game ended during Winter — §2.4.1, §6.1
        wr = winter_result.get("winter_result", {})
        phases = wr.get("phases", {})
        victory = phases.get("victory", {})
        if victory.get("game_over", False):
            result["game_over"] = True
            result["winner"] = victory.get("winner")
            result["final_ranking"] = victory.get("final_ranking")
            return result
    else:
        turn_result = resolve_card_turn(state, decision_func)
        result["type"] = "event"
        result["turn_result"] = turn_result

    # Advance to next card — §2.3.7
    next_card = advance_to_next_card(state)
    if next_card is None:
        result["game_over"] = True
    result["next_card"] = next_card

    return result


def run_game(state, decision_func):
    """Run the full game from start to finish — §2.0.

    Calls start_game, then repeatedly plays cards until the game ends.
    The decision_func callback is called whenever a faction must choose
    during an Event card turn.

    Args:
        state: Game state dict. Modified in place.
        decision_func: Callable(state, faction, options, position) → dict.

    Returns:
        Dict with game results including all card results and final
        outcome.
    """
    start_game(state)
    results = []

    while state["current_card"] is not None:
        card_result = play_card(state, decision_func)
        results.append(card_result)

        if card_result["game_over"]:
            break

    return {
        "card_results": results,
        "game_over": True,
        "total_cards_played": len(state["played_cards"]),
        "winter_count": state["winter_count"],
    }
