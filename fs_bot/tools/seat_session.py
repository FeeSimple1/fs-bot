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
                          if k not in ("decision_agent", '_action_window_scope',
                                       '_action_window_busy', '_action_window_cohorts',
                                       '_battle_elite_warbands')})


def fingerprint(value):
    return hashlib.sha256(json.dumps(encode(value), sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


def _decision_signatures(state, request):
    """Accept old empty Supply scopes without ignoring any actual agreement.

    An absent cache and an empty dictionary both mean no accepted Supply
    promises. Older writers used both shapes, depending on the enclosing
    action. Keep their signatures replayable; every nonempty cache, other
    board field and request field still has to match exactly.
    """
    board = board_copy(state)
    # Engine re-entrancy/authority frames are transient call-stack state,
    # never a game fact. The request's actual window remains fingerprinted.
    board.pop('_action_window_scope', None)
    board.pop('_action_window_busy', None)
    key = "_supply_line_agreements"
    if key not in board or (type(board[key]) is dict and not board[key]):
        board.pop(key, None)
        signature = fingerprint({"board": board, "request": request})
        with_empty = dict(board, **{key: {}})
        return signature, (signature, fingerprint({
            "board": with_empty, "request": request}))
    signature = fingerprint({"board": board, "request": request})
    return signature, (signature,)


def validate_response(state, request, response):
    """Reject malformed human input instead of falling back to bot choices."""
    kind = request["kind"]
    if (kind != "turn" and isinstance(response, dict)
            and set(response) == {"use_default"} and response["use_default"] is True):
        if kind in ('spring_leader', 'battle_elite') and 'window' in request:
            # None defers optional mid-action entry; explicit default places
            # using the established priorities and must retain its meaning.
            return response
        if kind == 'supply_refusal' and request.get('action_type') == 'command':
            from fs_bot.engine.supply_reconsideration import validate_response as validate_supply
            validate_supply(state, request, {'continue': True})
        return None
    if kind == "turn":
        if not isinstance(response, dict):
            raise ValueError("A turn response must be an action object.")
        if any(key in response for key in ("assistant_rejected", "supply_reconsideration")):
            raise ValueError("Supply refusal receipts are engine history, not player choices.")
        if response.get("action") not in request["options"]:
            raise ValueError("Choose one of the pending turn's legal actions.")
        if "bot_action" in response:
            raise ValueError("Human responses must use player_action, not bot_action.")
        if response["action"] != ACTION_PASS and not isinstance(
                response.get("player_action"), dict):
            raise ValueError("This action needs a player_action plan.")
        if response["action"] != ACTION_PASS:
            from fs_bot.engine.action_validation import validate_human_structure
            from fs_bot.engine.game_engine import ACTION_LIMITED_COMMAND
            error = validate_human_structure(
                state, request["faction"], response["player_action"],
                limited=response["action"] == ACTION_LIMITED_COMMAND)
            if error:
                raise ValueError(error)
        return response
    if kind == "supply_refusal":
        from fs_bot.engine.supply_reconsideration import validate_response as validate_supply
        validate_supply(state, request, response)
        return response
    if kind == "trade_region":
        from fs_bot.commands.sa_trade import validate_trade_response
        return validate_trade_response(request, response)
    if kind == "spring_leader":
        from fs_bot.engine.spring import validate_response as validate_spring
        return validate_spring(state, request, response)
    if kind == "voluntary_removal":
        from fs_bot.engine.voluntary_removal import validate_response as validate_removal
        return validate_removal(state, request, response,
                                cohorts=request.get('cohorts'))
    if kind in ("council_selection", "council_choice"):
        from fs_bot.cards.council import validate_response as validate_council
        return validate_council(state, request, response)
    if kind == "march_cohort":
        from fs_bot.engine.march_choices import validate_response as validate_cohort
        return validate_cohort(request, response)
    if kind == "diviciacus_pieces":
        from fs_bot.engine.diviciacus import validate_response as validate_pieces
        return validate_pieces(request, response)
    if kind == 'force_cohort':
        from fs_bot.engine.diviciacus import validate_force_cohort_response
        return validate_force_cohort_response(request, response)
    if kind == 'battle_elite':
        from fs_bot.battle.elite import validate_response as validate_elite
        return validate_elite(state, request, response)
    if kind == 'quarters_provincia':
        from fs_bot.engine.quarters import validate_provincia_response
        return validate_provincia_response(state, request, response)
    if kind == 'quarters_payment':
        from fs_bot.engine.quarters import validate_payment_response
        return validate_payment_response(state, request, response)
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

    supports_action_windows = True

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
        self.replayed_rejection = False
        self._legacy_replay_tail = False

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
        receipts = self.data['receipts']
        decision_receipt = None
        if isinstance(payload, dict):
            pending = self.data.get("pending")
            if (not pending or payload.get("decision_id") != pending["id"]
                    or "response" not in payload):
                # A consumed inbox may remain on disk after the engine has
                # advanced. It is still an acknowledged old submission.
                if receipt in receipts:
                    return False
                raise ValueError("Submission must identify the current pending decision.")
            # Ordinary rejected plans reuse decision IDs. A later response
            # can have the same board/request as the rejected attempt while
            # belonging to a different corrected top-level plan. Include
            # accepted response ancestry, not merely the request or its ID.
            versioned = (pending.get('action_windows_version')
                         or any(entry.get('assistant_action_windows_version')
                                for entry in self.data['journal']))
            if versioned:
                lineage = [(entry['assistant_id'], entry['assistant_signature'],
                            entry['assistant_response']) for entry in self.data['journal']]
                decision_receipt = fingerprint({'payload': payload, 'pending': pending,
                                                'lineage': lineage})
                if decision_receipt in receipts:
                    return False
            elif receipt in receipts:
                # Preserve older transcripts byte-for-byte until a newly
                # introduced decision starts the versioned timing protocol.
                return False
            queue = [payload]
        elif isinstance(payload, list):
            if receipt in receipts:
                return False
            queue = payload
        else:
            raise ValueError("queue.json must be a decision list or a decision_id/response object.")
        self.data["queue"] = copy.deepcopy(queue)
        if receipt not in receipts:
            receipts.append(receipt)
        if decision_receipt is not None:
            receipts.append(decision_receipt)
        return True

    def checkpoint(self):
        # A new engine transaction means the preceding one completed.
        self.finish()
        self.active = True
        self.cursor = 0
        self.replayed_rejection = False
        self._legacy_replay_tail = False
        return copy.deepcopy(self.data["queue"]), copy.deepcopy(self.data["journal"])

    def transaction_complete(self):
        """A recorded Supply refusal must fail again during verified replay."""
        expected = {entry["id"]: entry for entry in self.data.get("expected", [])}
        if any(expected.get(entry["assistant_id"], {}).get("assistant_rejected")
               for entry in self.data["journal"]):
            raise RuntimeError("Replay expected a Supply-refused attempt, but it completed.")

    def restore(self, token):
        self.active = False
        error = sys.exc_info()[1]
        if isinstance(error, ActionRejected):
            receipt = error.result.get("supply_reconsideration")
            if isinstance(receipt, dict):
                # PR-07: this is a resolved random refusal, not a malformed
                # submission. Its attempted plan is necessary replay evidence
                # for the retained die. Keep it and assign the correction a
                # fresh ID instead of erasing the event that produced the die.
                journal = self.data["journal"]
                first = journal[0] if journal else None
                if (not first or decode(first["assistant_request"])["kind"] != "turn"
                        or self.cursor != len(journal)):
                    raise RuntimeError("Supply reconsideration has no complete turn transcript.")
                marker = encode(receipt)
                expected = next((entry for entry in self.data.get("expected", [])
                                 if entry["id"] == first["assistant_id"]), None)
                if expected is not None:
                    if expected.get("assistant_rejected") != marker:
                        raise RuntimeError("Replay Supply refusal differs from its recorded result.")
                    self.replayed_rejection = True
                first["assistant_rejected"] = marker
                self.log.extend(journal)
                self.data["journal"] = []
                self.data["pending"] = {
                    "id": f"d{len(self.log) + 1:06d}",
                    "request": copy.deepcopy(first["assistant_request"]),
                    "board": encode(board_copy(self.state)),
                }
                self.cursor = 0
                return
            first = (self.data["journal"] or [None])[0]
            if first and any(entry["id"] == first["assistant_id"]
                             and entry.get("assistant_rejected")
                             for entry in self.data.get("expected", [])):
                raise RuntimeError("Replay expected a Supply refusal, but the rejection differed.")
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
        self._legacy_replay_tail = False

    @staticmethod
    def _inbox_entry(entry):
        return {"decision_id": entry["assistant_id"],
                "response": (decode(entry["assistant_response"])
                             if entry["assistant_response"] is not None
                             else {"use_default": True})}

    def ask(self, state, faction, request):
        request = dict(request, faction=faction)
        if self._skip_legacy_window(state, request):
            return None
        signature, compatible_signatures = _decision_signatures(state, request)
        journal = self.data["journal"]
        if self.cursor < len(journal):
            entry = journal[self.cursor]
            if entry["assistant_signature"] not in compatible_signatures:
                self.error = "Saved decision no longer matches its board/request; replay stopped."
                raise DecisionPending()
            self.cursor += 1
            return decode(entry["assistant_response"])

        decision_id = f"d{len(self.log) + self.cursor + 1:06d}"
        record_version = int('_action_window_scope' in state or 'window' in request)
        for expected in self.data.get("expected", []):
            if expected["id"] == decision_id:
                if expected["signature"] not in compatible_signatures:
                    self.error = "Replay request differs from the recorded board/request."
                    raise DecisionPending()
                # Replaying an accepted decision retains its original record,
                # including the older writer's equivalent empty-cache shape.
                signature = expected["signature"]
                record_version = expected.get('action_windows_version', record_version)
                self._legacy_replay_tail = not record_version
        self.display.before_decision(state, faction)
        pending = {"id": decision_id, "request": encode(request),
                   "board": encode(board_copy(state)),
                   **({'action_windows_version': 1} if record_version else {})}
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
                 **({'assistant_action_windows_version': record_version}
                    if record_version else {}),
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

    def _skip_legacy_window(self, state, request):
        """Do not inject choices into an already-recorded old transaction.

        Only saved evidence permits compatibility. A fresh inbox, or a new
        pending window, always requires a real human response.
        """
        if request.get('kind') not in ('voluntary_removal', 'spring_leader', 'battle_elite') or 'window' not in request:
            return False
        journal = self.data['journal']
        if self.cursor < len(journal):
            entry = journal[self.cursor]
            old_request = decode(entry.get('assistant_request', {}))
            return (not entry.get('assistant_action_windows_version')
                    and 'window' not in old_request)
        decision_id = f'd{len(self.log) + self.cursor + 1:06d}'
        expected = next((entry for entry in self.data.get('expected', [])
                         if entry['id'] == decision_id), None)
        if expected is not None:
            # Older integrations supplied only IDs/signatures. An exact
            # match is still an explicitly recorded window, never a reason
            # to skip it merely because those integrations omitted metadata.
            _, signatures = _decision_signatures(state, request)
            if expected['signature'] in signatures:
                return False
            old_request = decode(expected.get('request', {}))
            return (not expected.get('action_windows_version')
                    and 'window' not in old_request)
        pending = self.data.get('pending')
        if pending is not None:
            old_request = decode(pending['request'])
            return (not pending.get('action_windows_version')
                    and 'window' not in old_request)
        return self._legacy_replay_tail

    def reactive(self, state, faction, request):
        if faction != self.seat or state is not self.state:
            return None
        return self.ask(state, faction, request)
