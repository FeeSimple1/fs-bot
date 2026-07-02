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
  - Card 38 shaded (Diviciacus): Romans and Aedui may not transfer
    Resources to one another while active
  - the giver must hold the full amount; the receiver caps at
    MAX_RESOURCES (§1.8) — the giver pays only what is received

NOT enforced (documented in QUESTIONS.md): the four-Resource cap per
execution between two Factions run by the SAME player (§1.5.1/§1.5.2) —
this implementation has no concept of one player running two Factions.
"""

from fs_bot.rules_consts import (
    ROMANS, AEDUI, GERMANS, FACTIONS,
    MAX_RESOURCES, BASE_SCENARIOS, EVENT_SHADED,
)
from fs_bot.commands.common import CommandError


def transfer_resources(state, giver, receiver, amount):
    """Move Resources from ``giver`` to ``receiver``. Returns
    {"given": actual} (actual may be below ``amount`` only when the
    receiver hits MAX_RESOURCES).

    Raises CommandError on rule violations.
    """
    if giver == receiver:
        raise CommandError("Cannot transfer Resources to oneself")
    if giver not in FACTIONS or receiver not in FACTIONS:
        raise CommandError(f"Unknown faction: {giver!r}/{receiver!r}")
    if not isinstance(amount, int) or isinstance(amount, bool) \
            or amount <= 0:
        raise CommandError(f"Transfer amount must be a positive integer, "
                           f"got {amount!r}")
    if state["scenario"] in BASE_SCENARIOS and GERMANS in (giver, receiver):
        raise CommandError(
            "Germans neither give nor receive Resources in the base game "
            "(§1.5.2/§1.8)")
    from fs_bot.cards.capabilities import is_capability_active
    if ({giver, receiver} == {ROMANS, AEDUI}
            and is_capability_active(state, 38, EVENT_SHADED)):
        raise CommandError(
            "Card 38 shaded (Diviciacus): Romans and Aedui may not "
            "transfer Resources to one another")
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
