"""Pluggable per-Faction decision agent — lets a human/LLM play by its own
judgment instead of (or alongside) the NP bot flowcharts.

A *decision agent* is a single callable stored at ``state["decision_agent"]``::

    agent(state, faction, request) -> response | None

It is consulted at every reactive decision a Faction faces during resolution —
the points the top-level Sequence-of-Play decision_func does NOT cover. The
agent may control any subset of Factions and decision kinds: returning ``None``
(or raising) DEFERS that decision to the default NP/bot logic. With no agent set
(the all-bot harness), nothing changes and play stays byte-for-byte
deterministic.

The agent is given the live ``state`` (read-only by convention) plus a typed
``request`` dict describing the decision and its legal options, and returns a
typed response.

Request kinds
-------------
- ``RETREAT`` — a Defender's Retreat choice (§3.2.4/§8.4.3).
  request: ``{"kind": RETREAT, "region", "attacker", "defender",
              "is_ambush", "legal_regions": [region, ...]}``
  response: ``{"retreat": bool, "region": dest_or_None}`` or ``None`` to defer.
  ``region`` must be one of ``legal_regions`` (else treated as "no retreat").

- ``LOSS_ORDER`` — the order in which a Faction absorbs Battle Losses
  (§3.2.4: which pieces to lose; hard pieces still roll).
  request: ``{"kind": LOSS_ORDER, "region", "faction", "num_losses",
              "is_retreat", "is_ambush",
              "pieces": [(piece_type, piece_state_or_None), ...]}``
  response: an ordered subset/permutation of ``pieces`` (the loss priority), or
  ``None`` to defer. Entries not currently present are skipped safely.

- ``AGREEMENT`` — an inter-Faction agreement or opt-in (§1.5.2/§3.2.2).
  request: ``{"kind": AGREEMENT, "request_type", "requesting_faction",
              "context": {...}}``
  response: ``bool`` (agree / opt in?) or a details ``dict``, or ``None``
  to defer.
  Wired request_types:
    "supply_line"            — §3.2.1 (commands/rally.py)
    "trade_roman_agreement"  — §4.4.1 (execute._trade_roman_agreement)
    "quarters"               — §6.3.3 (execute._quarters_host_agrees)
    "retreat_into_control"   — §3.2.4 (execute, Battle retreat)
    "harassment"             — §3.2.2 opt-in (execute._np_harassers; the
                               §8.4.2 table remains the NP default).
                               requesting_faction is the marching/seizing
                               Faction being harassed.
  Voluntary resource transfers (§1.5.2 deal-making) have no engine
  mechanism and are NOT consulted — documented in QUESTIONS.md.

The ``RETREAT`` kind also carries ``context={"rampage": True, "num_pieces"}``
for a Rampage target's remove-vs-Retreat choice (§4.5.2): respond
``{"retreat": True, "region": <legal>}`` to Retreat the affected pieces or
``{"retreat": False}`` to remove them; defer for the NP default.
"""

RETREAT = "retreat"
LOSS_ORDER = "loss_order"
AGREEMENT = "agreement"


def consult_agent(state, faction, request):
    """Consult the per-game decision agent for ``faction``'s reactive decision.

    Returns the agent's response, or ``None`` to mean "no agent / agent
    deferred — use the default NP/bot logic." Never raises: an agent error
    defers to the default.
    """
    agent = state.get("decision_agent")
    if agent is None:
        return None
    try:
        return agent(state, faction, request)
    except Exception:
        return None
