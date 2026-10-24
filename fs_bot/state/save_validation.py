"""Validation at the boundary between saved data and a playable session.

Version-1 saves remain readable; optional fields added later are not required.
This checks structure and existing board invariants, without repairing a save
or drawing random numbers. Low-level serialization can still round-trip small
partial states without opting into this playable-session validation.
"""

import random

from fs_bot import rules_consts as rc
from fs_bot.cards.card_data import get_card
from fs_bot.state.state_schema import validate_state, check_structural_integrity


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _mapping(value, name):
    _require(isinstance(value, dict), f"{name} must be an object")


def _count(value, name):
    _require(type(value) is int and value >= 0,
             f"{name} must be a nonnegative integer")


def _card(value, name, *, nullable=False):
    if value == rc.WINTER_CARD:
        return
    if nullable and value is None:
        return
    _require(type(value) in (str, int), f"{name} has an invalid card identifier")
    try:
        get_card(value)
    except KeyError:
        raise ValueError(f"{name} has an unknown card identifier") from None


def validate_saved_game(state, meta, log):
    """Raise ValueError for malformed or inconsistent playable save data."""
    _require(state.get("scenario") in rc.ALL_SCENARIOS, "Unknown saved scenario")
    for name in ("spaces", "available", "resources", "senate", "legions_track",
                 "eligibility", "capabilities", "markers", "tribes"):
        _mapping(state.get(name), f"state.{name}")
    _require(isinstance(state.get("rng"), random.Random),
             "state.rng is missing or invalid; deterministic resume is unavailable")
    for name in ("fallen_legions", "removed_legions", "winter_count"):
        _count(state.get(name), f"state.{name}")
    for name in ("winter_track_legions",):
        if name in state:
            _count(state[name], f"state.{name}")
    for name in ("deck", "played_cards"):
        _require(isinstance(state.get(name), list), f"state.{name} must be a list")
        for index, card in enumerate(state[name]):
            _card(card, f"state.{name}[{index}]")
    for name in ("current_card", "next_card"):
        _require(name in state, f"state.{name} is missing")
        _card(state[name], f"state.{name}", nullable=True)
    for name in ("at_war", "diviciacus_in_play", "diviciacus_option", "interlude_completed",
                 "first_senate_after_interlude_pending",
                 "first_harvest_after_interlude_pending"):
        if name in state:
            _require(type(state[name]) is bool, f"state.{name} must be true or false")
    if state.get("diviciacus_option"):
        _require(state["scenario"] in rc.BASE_SCENARIOS,
                 "The Diviciacus Leader option applies only to original scenarios")
    if "scenario_phase" in state:
        _require(state["scenario_phase"] in ("first_half", "second_half"),
                 "state.scenario_phase is invalid")
    if "card_edition" in state:
        # The edition-profile module is optional for older version-1 saves.
        from fs_bot.cards.edition import validate_card_edition
        validate_card_edition(state["card_edition"])
    if "non_player_factions" in state:
        factions = state["non_player_factions"]
        _require(isinstance(factions, (set, list, tuple))
                 and all(f in rc.FACTIONS for f in factions),
                 "state.non_player_factions contains an invalid faction")
    _require(set(state["spaces"]) == set(rc.ALL_REGIONS),
             "state.spaces must contain every board Region exactly once")
    count_types = (rc.LEGION, rc.FORT, rc.ALLY, rc.CITADEL, rc.SETTLEMENT)
    states = (rc.HIDDEN, rc.REVEALED, rc.SCOUTED)
    for region, space in state["spaces"].items():
        _mapping(space, f"space {region}")
        _require(space.get("control") in (*rc.FACTION_CONTROL.values(), rc.NO_CONTROL),
                 f"space {region} has invalid Control")
        _mapping(space.get("pieces"), f"pieces in {region}")
        for faction, pieces in space["pieces"].items():
            _require(faction in rc.FACTIONS, f"pieces in {region} have an unknown faction")
            _mapping(pieces, f"{region}/{faction} pieces")
            for kind, value in pieces.items():
                label = f"{region}/{faction}/{kind}"
                if kind == rc.LEADER:
                    _require(value is None or value == rc.SUCCESSOR
                             or rc.LEADER_FACTION.get(value) == faction,
                             f"{label} has an invalid Leader")
                elif kind in states:
                    _mapping(value, label)
                    for piece, number in value.items():
                        _require(piece in rc.FLIPPABLE_PIECES,
                                 f"{label} has an invalid piece type")
                        _count(number, f"{label}/{piece}")
                else:
                    _require(kind in count_types, f"{label} has an invalid piece type")
                    _count(value, label)
    pool_types = (*count_types, *rc.FLIPPABLE_PIECES, rc.LEADER)
    for name in ("available", "removed_pieces"):
        pools = state.get(name, {})
        _mapping(pools, f"state.{name}")
        for faction, pieces in pools.items():
            _require(faction in rc.FACTIONS, f"state.{name} has an invalid faction")
            _mapping(pieces, f"state.{name}/{faction}")
            for piece, number in pieces.items():
                _require(piece in pool_types, f"state.{name} has an invalid piece type")
                _count(number, f"state.{name}/{faction}/{piece}")
    for faction, number in state["resources"].items():
        _require(faction in rc.FACTIONS, "state.resources has an invalid faction")
        _count(number, f"state.resources/{faction}")
        _require(number <= rc.MAX_RESOURCES,
                 f"state.resources/{faction} exceeds the Resource limit")
    for faction, eligibility in state["eligibility"].items():
        _require(faction in rc.FACTIONS and eligibility in (rc.ELIGIBLE, rc.INELIGIBLE),
                 "state.eligibility has an invalid faction or status")
    senate = state["senate"]
    _require(senate.get("position") in (None, rc.UPROAR, rc.INTRIGUE, rc.ADULATION)
             and type(senate.get("firm")) is bool, "state.senate is invalid")
    for row in rc.LEGIONS_ROWS:
        _count(state["legions_track"].get(row), f"state.legions_track/{row}")
    for tribe, info in state["tribes"].items():
        _mapping(info, f"tribe {tribe}")
        # Card 71 adds a player-named Colony with its own Region field.
        _require(isinstance(tribe, str) and (tribe in (*rc.BASE_TRIBES, *rc.ARIOVISTUS_TRIBES)
                 or info.get("region") in rc.ALL_REGIONS),
                 "state.tribes has an unknown Tribe without a valid Colony Region")
        _require(info.get("allied_faction") in (None, *rc.FACTIONS),
                 f"tribe {tribe} has an invalid allegiance")
    if "spring_box_leaders" in state:
        leaders = state["spring_box_leaders"]
        _require(isinstance(leaders, list)
                 and all(isinstance(name, str) and name in rc.LEADER_FACTION
                         for name in leaders), "state.spring_box_leaders is invalid")
    _validate_turn(state)
    _validate_metadata(state, meta, log)
    errors = validate_state(state) + check_structural_integrity(state)
    if errors:
        raise ValueError("Saved board is inconsistent: " + "; ".join(errors[:3]))


def _validate_turn(state):
    turn = state.get("_card_turn")
    if turn is not None:
        _mapping(turn, "state._card_turn")
        from fs_bot.engine.game_engine import (
            ACTION_PASS, ACTION_EVENT, ACTION_COMMAND, ACTION_COMMAND_SA,
            ACTION_LIMITED_COMMAND,
        )
        actions = (ACTION_PASS, ACTION_EVENT, ACTION_COMMAND, ACTION_COMMAND_SA,
                   ACTION_LIMITED_COMMAND)
        _require(all(key in turn for key in ("card", "frost", "arverni_phase",
                     "eligible", "idx", "first_action", "actions_taken", "passes",
                     "factions_done")), "Pending turn is missing required fields")
        _require(type(turn["frost"]) is bool, "Pending turn Frost status is invalid")
        _require(turn["arverni_phase"] is None or isinstance(turn["arverni_phase"], dict),
                 "Pending turn Arverni Phase result is invalid")
        _require(turn["first_action"] in (None, ACTION_EVENT, ACTION_COMMAND, ACTION_COMMAND_SA),
                 "Pending turn first action is invalid")
        _require(turn.get("card") == state["current_card"],
                 "Pending turn does not match the current card")
        for name in ("eligible", "passes"):
            values = turn.get(name)
            _require(isinstance(values, list)
                     and all(value in rc.FACTIONS for value in values),
                     f"Pending turn {name} is invalid")
        _count(turn.get("idx"), "Pending turn cursor")
        _require(turn["idx"] <= len(turn["eligible"]),
                 "Pending turn cursor is outside its faction order")
        _mapping(turn.get("actions_taken"), "Pending turn actions")
        for faction, action in turn["actions_taken"].items():
            _require(faction in rc.FACTIONS and isinstance(action, dict)
                     and action.get("action") in actions, "Pending turn action is invalid")
        _require(type(turn.get("factions_done")) is bool,
                 "Pending turn completion status is invalid")
    resolved = state.get("_resolved_card")
    if resolved is not None:
        _mapping(resolved, "state._resolved_card")
        _require(resolved.get("card") == state["current_card"],
                 "Resolved card does not match the current card")
        _require(type(resolved.get("game_over")) is bool,
                 "Resolved card completion status is invalid")
        _require(resolved.get("type") in ("event", "winter"),
                 "Resolved card type is invalid")
        key = "turn_result" if resolved["type"] == "event" else "winter_result"
        _mapping(resolved.get(key), f"Resolved card {key}")


def _validate_metadata(state, meta, log):
    if meta.get("scenario") is not None:
        _require(meta["scenario"] in rc.ALL_SCENARIOS, "Saved setup scenario is invalid")
    if meta.get("seed") is not None:
        _require(type(meta["seed"]) in (int, float, str), "Saved replay seed is invalid")
    for name in ("faction_modes", "initial_faction_modes"):
        if name in meta:
            _mapping(meta[name], f"meta.{name}")
            _require(all(f in rc.FACTIONS and mode in ("human", "bot")
                         for f, mode in meta[name].items()),
                     f"meta.{name} has an invalid faction or mode")
    if "human_snapshots" in meta:
        from fs_bot.state.serialize import decode
        from fs_bot.cli.display import snapshot_state, format_state_delta
        snapshots = decode(meta["human_snapshots"])
        _mapping(snapshots, "meta.human_snapshots")
        current = snapshot_state(state)
        for faction, snapshot in snapshots.items():
            _require(faction in rc.FACTIONS, "Saved display has an invalid faction")
            _mapping(snapshot, f"Saved display for {faction}")
            # Exercise the read-only consumer to catch malformed tuple keys,
            # absent fields and invalid types without changing the saved view.
            format_state_delta(snapshot, current)
    for entry in log:
        if "faction" in entry:
            _require(entry["faction"] in rc.FACTIONS, "Decision log has an invalid faction")
        if "card" in entry:
            _card(entry["card"], "Decision log card", nullable=True)
