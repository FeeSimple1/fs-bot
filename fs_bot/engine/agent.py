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
- ``drought_loss`` — each physical owner selects its exact Card 49 casualty.
- ``event_up_to`` — executor-owned A40/A51/A60 optional quantities/cohorts.
- ``devastate_losses`` — each physical owner chooses its exact §4.3.2 losses.
  Request carries faction, region, count and available cohort objects
  {piece_type,piece_state,count}. Return {"removals":[cohort objects]} totaling
  exactly count, or explicit default; no decline. Legions use piece_state None
  and go to Fallen. Leaders, Allies, Forts and Citadels are not candidates.

- Card 35 unshaded's Roman ``free_action`` request carries card_id 35,
  private_cards (the next two facedown cards, after the face-up next card),
  and alternative "eligible". Choose a legal free Limited Command, or
  {"decline": True} to take Eligible. Only the Roman beneficiary receives
  that private presentation, regardless of who executed the Event.

- ``harvest_legions`` — Pax first-Harvest placement, including after Interlude.
  Request carries count and legal_regions; respond with
  {"placements": {region: positive_count, ...}} totaling exactly count.
  No decline: all Winter Track Legions must be placed in Belgica.
  Raw None or explicit default preserves the established concentrated placement.

- ``besiege_target`` — the Roman's optional physical removal (§4.2.3/A4.2.3)
  immediately before Battle Losses. Request carries region, defender and
  ``targets`` objects {piece_type, tribe}; a Settlement has tribe None.
  Respond {"target": <one offered object>} or {"decline": True} to leave
  every piece. Raw None or explicit use_default retains the existing NPC
  type priority and deterministic Tribe identity. Durable human responses
  require a legal selection, decline or explicit delegation.

- ``ballistae_target`` — Card 10 shaded's owner may remove one surviving
  defending Fort/Citadel after Ambush. Request carries region, attacker,
  defender and targets {piece_type, tribe, owner}. Respond with one offered
  target, decline or explicit default. Provincia's permanent Fort is excluded.
  Raw None retains the existing Citadel-before-Fort default.

- ``raid_intimidate`` — A3.4.3 optional simultaneous Intimidate by the
  German Warbands that just Raided with Ariovistus. Request carries trusted
  region, raiders, max_removals, and physical target entries. Response is
  {"targets": [{"target_faction", "target_piece", "target_state"}, ...]}
  (empty targets places only the marker), or {"decline": True}. No normal
  Special Ability is spent and no additional Hidden Warband is revealed.

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

- ``HARASSMENT_LOSS`` — March or Seize Harassment choice (§3.2.2,
  §3.2.3, §3.3.2). Request carries region, harasser, loss_index, num_losses,
  departing_pieces (March) or pieces (Seize), phase and options.
  In phase "absorb", choose an offered soft piece type or "roll"; on a failed die roll, phase "remove" offers
  the remaining hard piece types and the roll. Seize phase "ally" offers the
  physical Allied Tribes when choosing which Ally to remove. Phase
  "piece_state" offers the available visibility states for a soft casualty.
  Response is {"choice": option}, {"use_default": True}, or None to use the first option (§8.4.1 priority).

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
    "diviciacus"             — card 38/A1.4 cooperation for one Command,
                               Special Ability (Leader only), or defense.
                               context includes phase, regions and action.
  ``diviciacus_pieces`` requests an allocation of a count between physical
  Roman/Aedui owners for placement, March formation, drop-off or a casualty. Respond
  with {"counts": {owner: count, ...}}, totaling the requested count and
  respecting the offered ``available`` counts.
  Voluntary Resource transfers (§1.5.2) are explicit ``details.transfers``
  entries on the acting Faction's plan, not a separate reactive request.
  See AGENT_INTERFACE.md for their response format and scope.

The ``RETREAT`` kind also carries ``context={"rampage": True, "num_pieces"}``
for a Rampage target (§4.5.2). Fresh requests include exact ``pieces`` pairs.
Respond with ``{"actions":[{"action":"remove" or "retreat", "piece_type":...,
"piece_state":...}, ...], "retreat_region": destination_or_None}``.
Choose one piece per affected Belgic Warband. All Retreating victims share the
one offered destination. Raw legacy adapters and verified old saved prompts
can retain their all-or-none ``{"retreat":bool,"region":...}`` contract.

"""

RETREAT = "retreat"
LOSS_ORDER = "loss_order"
AGREEMENT = "agreement"
HARASSMENT_LOSS = "harassment_loss"


def consult_agent(state, faction, request):
    """Consult the per-game decision agent for ``faction``'s reactive decision.

    Returns the agent's response, or ``None`` to mean "no agent / agent
    deferred — use the default NP/bot logic." An agent error defers to the
    default, but EOF means the human stopped responding and must pause play.
    """
    agent = state.get("decision_agent")
    if agent is None:
        return None
    try:
        return agent(state, faction, request)
    except EOFError:
        raise
    except Exception:
        return None
