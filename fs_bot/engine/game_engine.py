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

import copy
from contextlib import contextmanager

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

    A5.1.1: Eligibility/Ineligibility Event effects have no impact on
    the Ariovistus Arverni — they act only via the Arverni Phase
    (A2.3.9), never through this Sequence of Play, so a stray
    eligibility entry for them is structurally inert. A5.4: free
    Special Abilities likewise cannot reach the game-run Arverni
    (no code path grants them Entreat or Devastate).

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
    # Bots read state["current_card_id"]; engine writes state["current_card"].
    # Keep both keys in sync so bots and engine agree on the active card.
    state["current_card_id"] = card_id
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
    """Sec.2.3.6 adjustment + event-imposed persistence: several Events
    make a Faction "Ineligible through next card" (6, 14, 18, 23, 46,
    A17, A18). The plain reset clobbered that when the Faction had not
    acted (found via a live playtest transcript audit: Rhenus Bridge
    docked Rome 6 Resources but Rome was offered the very next card).
    state["forced_ineligible"] = {faction: remaining_cards}.
    """
    _adjust_eligibility_base(state, actions_taken)
    forced = state.get("forced_ineligible")
    if forced:
        from fs_bot.rules_consts import INELIGIBLE
        for faction in list(forced):
            state["eligibility"][faction] = INELIGIBLE
            forced[faction] -= 1
            if forced[faction] <= 0:
                del forced[faction]
    # The mirror clause: several Events keep the *executing* Faction
    # Eligible despite having executed the Event ("Executing Faction
    # Eligible" on 6/14 shaded, "Stay Eligible" on 46 shaded, the
    # "or be Eligible" choice on 35 unshaded). The plain reset clobbered
    # these exactly as it clobbered "Ineligible through next card".
    # An explicit "Ineligible" clause on the same Faction wins the
    # conflict (the specific penalty beats the general retention).
    stay = state.pop("stay_eligible", None)
    if stay:
        from fs_bot.rules_consts import ELIGIBLE
        still_forced = state.get("forced_ineligible") or {}
        for faction in stay:
            if faction not in still_forced:
                state["eligibility"][faction] = ELIGIBLE


def _adjust_eligibility_base(state, actions_taken):
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

class ActionRejected(ValueError):
    """A human Command plan was missing, invalid, or had no legal effect."""

    def __init__(self, result):
        self.result = result
        super().__init__(result.get("reason") or result.get("error")
                         or "The chosen action produced no legal effect.")


def _maybe_execute(state, faction, decision, actions_taken):
    """Apply a recorded non-Pass decision to the board (opt-in).

    Delegates to engine.execute.execute_decision and stashes the result on
    the recorded action under "execution". Imported lazily to avoid a
    circular import (execute -> commands -> ...).
    """
    from fs_bot.engine.execute import execute_decision, \
        maybe_np_aedui_subsidy
    exec_result = execute_decision(state, faction, decision)
    if (not decision.get("bot_action")
            and decision.get("action") in (ACTION_COMMAND, ACTION_COMMAND_SA,
                                            ACTION_LIMITED_COMMAND)
            and isinstance(exec_result, dict)
            and not exec_result.get("executed")):
        raise ActionRejected(exec_result)
    # §8.6.6: the NP Aedui subsidy fires "at each instant" Roman
    # Resources drop below 2 — checked after every executed action.
    subsidy = maybe_np_aedui_subsidy(state)
    if subsidy and isinstance(exec_result, dict):
        exec_result["np_aedui_subsidy"] = subsidy
    rec = actions_taken.get(faction)
    if isinstance(rec, dict):
        rec["execution"] = exec_result
        # Effective action — §2.3.4 with the NP flowcharts' "If none ...
        # no Special Ability": when the declared Command + Special Ability
        # resolves with an SA that did nothing (the SA was withheld, or it
        # recomputed against the post-Command board and found no effect),
        # the Faction in fact took a Command only. Record that, so the 2nd
        # Eligible's options and Eligibility adjustment see the real turn.
        if rec.get("action") == ACTION_COMMAND_SA and isinstance(exec_result,
                                                                 dict):
            sx = exec_result.get("sa_execution")
            sa_did_nothing = not exec_result.get("battle_sa_executed") and (
                exec_result.get("sa_skipped")
                or not isinstance(sx, dict)
                or not sx.get("executed"))
            if sa_did_nothing:
                rec["action"] = ACTION_COMMAND
                rec["declared_action"] = ACTION_COMMAND_SA
    return exec_result


@contextmanager
def _action_transaction(state, decision_func):
    """Keep an interrupted action/phase from leaving half-applied effects.

    Completed faction actions are durable; an interrupted action is retried
    from its original board and RNG position. Frontends may attach matching
    checkpoint/restore hooks for their decision logs and input queues.
    """
    checkpoint = copy.deepcopy({k: v for k, v in state.items()
                                if k != "decision_agent"})
    agent = state.get("decision_agent")
    had_agent = "decision_agent" in state
    save_frontend = getattr(decision_func, "transaction_checkpoint", None)
    restore_frontend = getattr(decision_func, "transaction_restore", None)
    frontend_checkpoint = save_frontend() if save_frontend else None
    try:
        yield
    except BaseException:
        state.clear()
        state.update(checkpoint)
        if had_agent:
            state["decision_agent"] = agent
        if restore_frontend:
            restore_frontend(frontend_checkpoint)
        raise


def resolve_card_turn(state, decision_func, *, execute=False,
                      _save_result=False):
    """Resolve an Event card, resuming after its last completed action.

    ``_card_turn`` is serialized with the board: it records the faction
    cursor, completed actions and the first action's effective type. Thus a
    human prompt can halt and reload without re-executing earlier factions.
    Each action and the final mandatory phase are transactional, including
    human reactive decisions inside their resolution.
    """
    turn = state.get("_card_turn")
    if turn is None or turn["card"] != state["current_card"]:
        turn = {
            "card": state["current_card"],
            "frost": is_frost(state),
            "arverni_phase": None,
            "eligible": list(get_faction_order(state)),
            "idx": 0,
            "first_action": None,
            "actions_taken": {},
            "passes": [],
            "factions_done": False,
        }
        state["_card_turn"] = turn

    while not turn["factions_done"] and turn["idx"] < len(turn["eligible"]):
        faction = turn["eligible"][turn["idx"]]
        # Events can make a later faction Ineligible immediately (§5.0),
        # even though it was Eligible when this card began.
        if state["eligibility"].get(faction) != ELIGIBLE:
            turn["idx"] += 1
            continue
        first = turn["first_action"] is None
        options = (get_first_eligible_options() if first else
                   get_second_eligible_options(turn["first_action"]))
        position = "1st_eligible" if first else "2nd_eligible"
        try:
            with _action_transaction(state, decision_func):
                decision = decision_func(state, faction, options, position)
                action = decision["action"]
                if action == ACTION_PASS:
                    pass_result = execute_pass(state, faction)
                    turn["actions_taken"][faction] = {
                        "action": ACTION_PASS, **pass_result,
                    }
                    turn["passes"].append(faction)
                else:
                    turn["actions_taken"][faction] = decision
                    if execute:
                        _maybe_execute(state, faction, decision,
                                       turn["actions_taken"])
                    if first:
                        turn["first_action"] = decision["action"]
                    else:
                        turn["factions_done"] = True
                turn["idx"] += 1
        except ActionRejected as exc:
            # Interactive frontends can explain the failed plan and offer
            # the same faction a fresh choice; batch/API callers get an
            # explicit error and keep their original board and input queue.
            reject = getattr(decision_func, "decision_rejected", None)
            if reject is None:
                raise
            turn = state["_card_turn"]
            reject(state, faction, exc.result)


    # Even an all-Pass card (or one with no Eligible factions) has its
    # mandatory post-activation Arverni Phase, per A6.2/A2.3.9 errata.
    with _action_transaction(state, decision_func):
        if state["scenario"] in ARIOVISTUS_SCENARIOS:
            if card_has_carnyx_trigger(turn["card"], state["scenario"]):
                is_at_war, _triggering = check_arverni_at_war(state)
                if is_at_war:
                    turn["arverni_phase"] = run_arverni_phase(
                        state, is_frost=turn["frost"])
        adjust_eligibility(state, turn["actions_taken"])
        result = {key: turn[key] for key in (
            "card", "frost", "arverni_phase", "actions_taken", "passes")}
        if _save_result:
            state["_resolved_card"] = {
                "card": turn["card"], "type": "event",
                "game_over": False, "turn_result": result,
            }
        state.pop("_card_turn", None)
    return result


# ============================================================================
# WINTER CARD HANDLING — §2.4
# ============================================================================

def resolve_winter_card(state, britannia_decision=None,
                        roman_dispersed_keep=None):
    """Handle a Winter card — §2.4.

    Triggers a Winter Round (§6.0). The winter_count is tracked to
    determine final Winter (§2.4.1).

    For SCENARIO_GALLIC_WAR, the Gallic War Interlude (A2.1) replaces
    the rest of the 3rd Winter Round if no faction has won. Pass
    britannia_decision and roman_dispersed_keep to control Roman
    choices during the Interlude.

    Args:
        state: Game state dict. Modified in place.
        britannia_decision: Optional Roman decision (Interlude only).
        roman_dispersed_keep: Optional tribe constant (Interlude only).

    Returns:
        Dict with winter round results.
    """
    total_winters = _count_winter_cards_in_game(state)
    is_final = (state["winter_count"] + 1 >= total_winters)
    from fs_bot.rules_consts import SCENARIO_GALLIC_WAR
    if (state["scenario"] == SCENARIO_GALLIC_WAR
            and not state.get("interlude_completed", False)):
        # A2.1 (The Gallic War): the first half's 3rd Victory Phase does
        # NOT end the game on victory margins — "If the game does not end
        # by the 3rd Victory Phase", the Interlude resets the board and
        # the second half (Pax Gallica?-style deck) continues. Outright
        # victory still ends the first half inside victory_phase. Without
        # this, is_final=True at the 3rd Winter declared a margins winner
        # and the Interlude was UNREACHABLE — every Gallic War game was
        # byte-identical to Ariovistus (found by play_quality telemetry).
        is_final = False

    winter_result = run_winter_round(
        state, is_final=is_final,
        britannia_decision=britannia_decision,
        roman_dispersed_keep=roman_dispersed_keep,
    )
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
    # The Gallic War Interlude rebuilds the deck and clears played_cards,
    # losing the first half's Winters from the count above. winter_count
    # tracks every Winter actually resolved and survives the reset — take
    # the larger base so the second half's LAST Winter (not its second)
    # is final (A2.1).
    played_winters = sum(1 for c in state["played_cards"]
                         if is_winter_card(c))
    return count - played_winters + max(played_winters,
                                        state.get("winter_count", 0))


# ============================================================================
# GAME LOOP — §2.0
# ============================================================================

def play_card(state, decision_func, *, execute=False):
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
    completed = state.get("_resolved_card")
    if completed and completed["card"] == card_id:
        result = completed
    elif is_winter_card(card_id):
        # Winter contains reactive human choices too; an interrupted
        # phase must restart from the pre-Winter board and RNG position.
        with _action_transaction(state, decision_func):
            winter_result = resolve_winter_card(state)
            result = {"card": card_id, "game_over": False,
                      "type": "winter", "winter_result": winter_result}
            wr = winter_result.get("winter_result", {})
            victory = wr.get("phases", {}).get("victory", {})
            if victory.get("game_over", False):
                result.update(game_over=True, winner=victory.get("winner"),
                              final_ranking=victory.get("final_ranking"))
            # The Interlude rebuilds the deck and clears current_card.
            # Keep this completed Winter addressable until the first card
            # of the new half has actually been drawn (also after reload).
            if state["current_card"] is None:
                state["current_card"] = card_id
            state["_resolved_card"] = result
    else:
        resolve_card_turn(state, decision_func, execute=execute,
                          _save_result=True)
        result = state["_resolved_card"]

    if result["game_over"]:
        return result

    # Retain the completed result until advancing succeeds. An interrupt
    # between resolution and drawing must not repeat the completed card.
    with _action_transaction(state, decision_func):
        next_card = advance_to_next_card(state)
        if next_card is None:
            result["game_over"] = True
        result["next_card"] = next_card
        if next_card is not None:
            state.pop("_resolved_card", None)
    return result


def run_game(state, decision_func, *, execute=False):
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
        card_result = play_card(state, decision_func, execute=execute)
        results.append(card_result)

        if card_result["game_over"]:
            break

    return {
        "card_results": results,
        "game_over": True,
        # len(results), not len(played_cards): the Gallic War Interlude
        # rebuilds the deck and clears played_cards mid-game.
        "total_cards_played": len(results),
        "winter_count": state["winter_count"],
    }
