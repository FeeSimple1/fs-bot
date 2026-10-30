"""Voluntary Resource transfers — §1.5.2 / A1.5.2.

§1.5.2: a Faction may transfer Resources to another during either's
execution (by the Sequence of Play, §2.3.4) of a Command or Event, and
Factions may transfer any Resources to any non-German Factions during the
Quarters and Harvest Phases of the Winter Round (§6.3-6.4). A1.5.2: in
Ariovistus the Germans give and receive transfers just as other Factions.

Constraints enforced here:
  - distinct factions, positive integer amount
  - base game: Germans neither give nor receive (they have no Resources
    track, §1.8; §1.5.2 says "non-German Factions")
  - Ariovistus: Arverni neither give nor receive (A1.5.2 forbids
    receiving Resources, and A1.8 gives them no Resources track)
  - Card 38 shaded (Diviciacus): Romans and Aedui may not transfer
    Resources to one another while active
  - the giver must hold the full amount; the receiver caps at
    MAX_RESOURCES (§1.8) — the giver pays only what is received

NOT enforced (documented in QUESTIONS.md): the four-Resource cap per
execution between two Factions run by the SAME player (§1.5.1/§1.5.2) —
this implementation has no concept of one player running two Factions.
"""

from fs_bot.rules_consts import (
    ROMANS, AEDUI, ARVERNI, GERMANS, FACTIONS,
    MAX_RESOURCES, BASE_SCENARIOS, ARIOVISTUS_SCENARIOS, EVENT_SHADED,
)
from fs_bot.commands.common import CommandError


def transfer_eligibility_error(state, giver, receiver):
    """Return the rule barring these parties, or None when they may transfer.

    Use the current scenario: after the Gallic War Interlude the Arverni
    regain their Resources track and the Germans lose theirs. Amounts and
    available stock are checked separately when the transfer resolves.
    """
    if giver == receiver:
        return "Cannot transfer Resources to oneself"
    if giver not in FACTIONS or receiver not in FACTIONS:
        return f"Unknown faction: {giver!r}/{receiver!r}"
    if state["scenario"] in BASE_SCENARIOS and GERMANS in (giver, receiver):
        return (
            "Germans neither give nor receive Resources in the base game "
            "(§1.5.2/§1.8)")
    if (state["scenario"] in ARIOVISTUS_SCENARIOS
            and ARVERNI in (giver, receiver)):
        return (
            "Arverni neither give nor receive Resources in Ariovistus "
            "(A1.5.2/A1.8)")
    from fs_bot.cards.capabilities import is_capability_active
    if ({giver, receiver} == {ROMANS, AEDUI}
            and is_capability_active(state, 38, EVENT_SHADED)):
        return (
            "Card 38 shaded (Diviciacus): Romans and Aedui may not "
            "transfer Resources to one another")
    return None


def transfer_plan_error(state, giver, action):
    """Validate a typed human plan's transfer parties without moving Resources.

    Durable decisions must stay pending when a gift names an ineligible
    faction. The raw executor retains its report-and-continue contract for
    transfer errors; both paths use the same participant rules above.
    """
    if not isinstance(action, dict):
        return "The Command plan must be an object"
    details = action.get("details")
    if details is None:
        return None
    if not isinstance(details, dict):
        return "Command details must be an object"
    transfers = details.get("transfers")
    if transfers is None:
        return None
    if not isinstance(transfers, list):
        return "Resource transfers must be a list"
    for transfer in transfers:
        if not isinstance(transfer, dict):
            return "Each Resource transfer must be an object"
        error = transfer_eligibility_error(state, giver, transfer.get("to"))
        if error:
            return error
    return None


def transfer_resources(state, giver, receiver, amount):
    """Move Resources from ``giver`` to ``receiver``. Returns
    {"given": actual} (actual may be below ``amount`` only when the
    receiver hits MAX_RESOURCES).

    Raises CommandError on rule violations.
    """
    error = transfer_eligibility_error(state, giver, receiver)
    if error:
        raise CommandError(error)
    if not isinstance(amount, int) or isinstance(amount, bool) \
            or amount <= 0:
        raise CommandError(f"Transfer amount must be a positive integer, "
                           f"got {amount!r}")
    stock = state["resources"].get(giver, 0)
    if stock < amount:
        raise CommandError(
            f"{giver} has {stock} Resources, cannot give {amount}")
    room = MAX_RESOURCES - state["resources"].get(receiver, 0)
    actual = max(0, min(amount, room))
    state["resources"][giver] = stock - actual
    state["resources"][receiver] = (
        state["resources"].get(receiver, 0) + actual)
    return {"given": actual, "from": giver, "to": receiver}
