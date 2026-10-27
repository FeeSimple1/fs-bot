"""Durable human decisions for the file-based assistant interface.

The engine rolls an interrupted action back to its starting board/RNG. The
journal retains choices already made within that action and verifies their
requests before replaying them. Board, inbox consumption, journal and committed
history are written together by save_game; queue.json is only an input inbox.
"""

import copy
import hashlib
import json
import sys

from fs_bot.engine.agent import RETREAT, LOSS_ORDER, AGREEMENT, HARASSMENT_LOSS
from fs_bot.engine.game_engine import ActionRejected, ACTION_PASS
from fs_bot.state.serialize import encode, decode


class DecisionPending(BaseException):
    """Control flow, deliberately not caught as an engine/bot Exception."""


def board_copy(state):
    return copy.deepcopy({k: v for k, v in state.items()
                          if k != "decision_agent"})


def fingerprint(value):
    return hashlib.sha256(json.dumps(encode(value), sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


def validate_response(state, request, response):
    """Reject malformed human input instead of falling back to bot choices."""
    kind = request["kind"]
    if (kind != "turn" and isinstance(response, dict)
            and set(response) == {"use_default"} and response["use_default"] is True):
        return None
    if kind == "turn":
        if not isinstance(response, dict):
            raise ValueError("A turn response must be an action object.")
        if response.get("action") not in request["options"]:
            raise ValueError("Choose one of the pending turn's legal actions.")
        if "bot_action" in response:
            raise ValueError("Human responses must use player_action, not bot_action.")
        if response["action"] != ACTION_PASS and not isinstance(
                response.get("player_action"), dict):
            raise ValueError("This action needs a player_action plan.")
        return response
    if kind in ("council_selection", "council_choice"):
        from fs_bot.cards.council import validate_response as validate_council
        return validate_council(state, request, response)
    if kind == "march_cohort":
        from fs_bot.engine.march_choices import validate_response as validate_cohort
        return validate_cohort(request, response)
    if kind == "diviciacus_pieces":
        from fs_bot.engine.diviciacus import validate_response as validate_pieces
        return validate_pieces(request, response)
    if kind == HARASSMENT_LOSS:
        from fs_bot.commands.march import validate_harassment_response
        return validate_harassment_response(request, response)
    if kind == RETREAT:
        if not isinstance(response, dict) or type(response.get("retreat")) is not bool:
            raise ValueError("Retreat requires {retreat: true/false, region: ...}.")
        destination = response.get("region")
        if response["retreat"]:
            if destination not in request.get("legal_regions", []):
                raise ValueError("Retreat destination is not a legal region.")
        elif destination is not None:
            raise ValueError("A no-Retreat response must have region null or omit it.")
        return response
    if kind == LOSS_ORDER:
        if not isinstance(response, list):
            raise ValueError("Loss order must be a list of the offered piece entries.")
        offered = [list(p) for p in request.get("pieces", [])]
        # These are priorities among offered piece types/states (possibly with
        # a physical owner for Enlist), not arbitrary newly invented pieces.
        for entry in response:
            if not isinstance(entry, (list, tuple)) or list(entry) not in offered:
                raise ValueError("Loss order contains a piece not offered by this request.")
            offered.remove(list(entry))
        return response
    if kind == AGREEMENT:
        if type(response) is not bool:
            raise ValueError("An agreement or harassment response must be true or false.")
        return response
    if kind in ("winter_uprising_timing", "winter_uprising_placement"):
        from fs_bot.cards.winter_uprising_resolution import validate_response as validate_uprising
        return validate_uprising(state, request, response)
    if kind == "ambacti_removal":
        from fs_bot.cards.ambacti import validate_response as validate_ambacti
        return validate_ambacti(state, request, response)
    if kind == "raid_intimidate":
        from fs_bot.engine.raid_intimidate import validate_response as validate_raid
        validate_raid(state, request, response)
        return response
    if kind == "kinship":
        from fs_bot.cards.kinship import validate_response as validate_kinship
        error = validate_kinship(state, response)
        if error:
            raise ValueError(error)
        return response
    if kind == "free_action":
        from fs_bot.engine.free_actions import validate_free_action_response
        error = validate_free_action_response(state, request["faction"], request, response)
        if error:
            raise ValueError(error)
        return response
    if kind in ("frumentum_amount", "frumentum_action"):
        from fs_bot.engine.frumentum import validate_response as validate_frumentum
        validate_frumentum(state, request, response)
        return response
    if kind == "quarters_plan":
        if not isinstance(response, dict):
            raise ValueError("Quarters requires a relocation/payment object.")
        from fs_bot.engine.quarters import validate_quarters_plan
        errors = validate_quarters_plan(state, response, faction=request["faction"])
        if errors:
            raise ValueError("; ".join(errors))
        return response
    if kind == "winter_campaign":
        from fs_bot.engine.winter_campaign import validate_human_plan
        validate_human_plan(state, request["faction"], response,
                            request.get("remaining_actions", 2))
        return response
    raise ValueError("Unknown decision kind; use_default must be chosen explicitly.")


class SeatSession:
    """One authoritative saved inbox, pending decision and action journal."""

    def __init__(self, state, meta, log, display):
        self.state, self.meta, self.log, self.display = state, meta, log, display
        self.data = meta.setdefault("assistant_session", {
            "version": 1, "queue": [], "receipts": [], "journal": [],
            "pending": None, "origin": encode(board_copy(state)),
            "origin_seat": meta["seat"], "origin_log_count": len(log),
        })
        if not isinstance(self.data, dict) or self.data.get("version") != 1:
            raise ValueError("Unsupported assistant session version.")
        if any(not isinstance(self.data.get(key), list)
               for key in ("queue", "receipts", "journal")):
            raise ValueError("Assistant save has invalid inbox/journal containers.")
        if any(not isinstance(e, dict) or not all(k in e for k in (
                "assistant_id", "assistant_signature", "assistant_response"))
               for e in self.data["journal"]):
            raise ValueError("Assistant save has an invalid decision journal.")
        pending = self.data.get("pending")
        if pending is not None and (not isinstance(pending, dict)
                or not all(k in pending for k in ("id", "request", "board"))):
            raise ValueError("Assistant save has an invalid pending decision.")
        self.cursor = 0
        self.active = False
        self.error = None

    def __deepcopy__(self, memo):
        # This is a live frontend, not game state. Bot previews copy the
        # agent too; reactive() rejects their copied board by identity.
        return self

    @property
    def seat(self):
        return self.meta["seat"]

    def import_inbox(self, payload):
        """Import once. Re-reading an unchanged inbox cannot repeat a move."""
        receipt = fingerprint(payload)
        if receipt in self.data["receipts"]:
            return False
        if isinstance(payload, dict):
            pending = self.data.get("pending")
            if (not pending or payload.get("decision_id") != pending["id"]
                    or "response" not in payload):
                raise ValueError("Submission must identify the current pending decision.")
            queue = [payload]
        elif isinstance(payload, list):
            queue = payload
        else:
            raise ValueError("queue.json must be a decision list or a decision_id/response object.")
        self.data["queue"] = copy.deepcopy(queue)
        self.data["receipts"].append(receipt)
        return True

    def checkpoint(self):
        # A new engine transaction means the preceding one completed.
        self.finish()
        self.active = True
        self.cursor = 0
        return copy.deepcopy(self.data["queue"]), copy.deepcopy(self.data["journal"])

    def restore(self, token):
        self.active = False
        if isinstance(sys.exc_info()[1], ActionRejected):
            # A rejected action can be corrected, including its top-level
            # plan. Restore inputs, but do not force replay of that bad plan.
            queue, old_journal = token
            self.data["queue"] = [self._inbox_entry(e) for e in old_journal] + queue
            first = (self.data["journal"] or [None])[0]
            self.data["journal"] = []
            # A rejected own-turn Command still has a concrete pending turn
            # so the normal submit command can correct it immediately.
            self.data["pending"] = ({
                "id": first["assistant_id"], "request": first["assistant_request"],
                "board": encode(board_copy(self.state)),
            } if first and decode(first["assistant_request"])["kind"] == "turn"
                else None)
        self.cursor = 0

    def finish(self):
        if not self.active:
            return
        if self.cursor != len(self.data["journal"]):
            raise RuntimeError("Saved decision journal did not replay completely.")
        self.log.extend(self.data["journal"])
        self.data["journal"] = []
        self.data["pending"] = None
        self.cursor = 0
        self.active = False

    @staticmethod
    def _inbox_entry(entry):
        return {"decision_id": entry["assistant_id"],
                "response": (decode(entry["assistant_response"])
                             if entry["assistant_response"] is not None
                             else {"use_default": True})}

    def ask(self, state, faction, request):
        request = dict(request, faction=faction)
        signature = fingerprint({"board": board_copy(state), "request": request})
        journal = self.data["journal"]
        if self.cursor < len(journal):
            entry = journal[self.cursor]
            if entry["assistant_signature"] != signature:
                self.error = "Saved decision no longer matches its board/request; replay stopped."
                raise DecisionPending()
            self.cursor += 1
            return decode(entry["assistant_response"])

        decision_id = f"d{len(self.log) + self.cursor + 1:06d}"
        for expected in self.data.get("expected", []):
            if expected["id"] == decision_id and expected["signature"] != signature:
                self.error = "Replay request differs from the recorded board/request."
                raise DecisionPending()
        self.display.before_decision(state, faction)
        pending = {"id": decision_id, "request": encode(request),
                   "board": encode(board_copy(state))}
        self.data["pending"] = pending
        queue = self.data["queue"]
        if not queue:
            raise DecisionPending()
        item = queue[0]
        try:
            if isinstance(item, dict) and "response" in item:
                if item.get("decision_id", decision_id) != decision_id:
                    raise ValueError("Response decision_id does not match the pending decision.")
                if "reactive" in item and item["reactive"] != request["kind"]:
                    raise ValueError("Response reactive kind does not match the pending decision.")
                response = item["response"]
            elif request["kind"] == "turn":
                response = item  # compatible original action-only list queue
            else:
                raise ValueError("A reactive response needs a response field (and decision_id).")
            response = validate_response(state, request, response)
        except (ValueError, TypeError) as exc:
            self.error = str(exc)
            raise DecisionPending() from exc
        queue.pop(0)
        entry = {"card": state.get("current_card"), "faction": faction,
                 "assistant_id": decision_id, "assistant_signature": signature,
                 "assistant_request": encode(request),
                 "assistant_response": encode(response)}
        if request["kind"] == "turn":
            entry.update(response)
            entry["position"] = request["position"]
        else:
            entry.update(reactive=request["kind"], response=encode(response))
        journal.append(entry)
        self.cursor += 1
        self.data["pending"] = None
        return response

    def reactive(self, state, faction, request):
        if faction != self.seat or state is not self.state:
            return None
        return self.ask(state, faction, request)
