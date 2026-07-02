"""Per-card event_params schemas, derived from the card handlers' own source.

Each handler reads its choices from ``state["event_params"]`` — scalar keys
(``params.get("region")``) and list keys iterated entry by entry
(``for m in params.get("moves", []): m["from_region"] ...``). This module
walks a handler's AST and produces a typed schema:

    {key: {"kind": <kind>, "entry_fields": {subkey: <kind>} | None,
           "values": tuple | None, "region_pool": name | None}}

Kinds: region, regions, faction, factions, tribe, count, direction,
piece_type, piece_state, leader_name, entries, value.

Because the schema is extracted from source, it tracks new/changed cards
automatically. ``_OVERRIDES`` refines the few cards whose handlers enforce
value constraints (so UIs offer, and fuzzers generate, only card-legal
choices); the handlers remain the validators.

Consumers: cli/human_plan.py (typed prompts for a human's Event) and
tools/player_fuzz.py (success-path param generation for cards without an
NP deriver).
"""

import ast
import inspect
import textwrap
from functools import lru_cache

from fs_bot.rules_consts import (
    ARIOVISTUS_SCENARIOS, FACTIONS, GERMANS, ROMANS, AEDUI,
    WARBAND, AUXILIA, LEGION, ALLY, CITADEL, FORT, LEADER,
    HIDDEN, REVEALED, SCOUTED,
    SENATE_UP, SENATE_DOWN,
    CAESAR, VERCINGETORIX, AMBIORIX, ARIOVISTUS_LEADER, DIVICIACUS,
    SUCCESSOR,
    ARVERNI_REGION, PICTONES, BRITANNIA,
)

PIECE_TYPES = (WARBAND, AUXILIA, LEGION, ALLY, CITADEL, FORT, LEADER)
PIECE_STATES = (HIDDEN, REVEALED, SCOUTED, None)
LEADER_NAMES = (CAESAR, VERCINGETORIX, AMBIORIX, ARIOVISTUS_LEADER,
                DIVICIACUS, SUCCESSOR)

# Piece-type constant NAMES seen as .get() defaults in handler source.
_PIECE_TYPE_NAMES = {"WARBAND", "AUXILIA", "LEGION", "ALLY", "CITADEL",
                     "FORT", "LEADER"}
_PIECE_STATE_NAMES = {"HIDDEN", "REVEALED", "SCOUTED"}


def infer_kind(name, default_node=None):
    """Infer a param kind from a key name (+ its .get() default, if any)."""
    k = name.lower()
    if default_node is not None:
        if isinstance(default_node, ast.Name):
            if default_node.id in _PIECE_TYPE_NAMES:
                return "piece_type"
            if default_node.id in _PIECE_STATE_NAMES:
                return "piece_state"
        if (isinstance(default_node, ast.Constant)
                and isinstance(default_node.value, int)
                and not isinstance(default_node.value, bool)):
            return "count"
    if "direction" in k:
        return "direction"
    if "factions" in k:
        return "factions"
    if "regions" in k:
        return "regions"
    if k.endswith("s"):
        # Plural of a scalar kind -> list of that kind (target_tribes,
        # ally_removals of tribe names, ...). Dict-entry lists (moves,
        # placements) resolve to "entries" via loop analysis instead.
        inner = infer_kind(k[:-1])
        if inner in ("tribe", "leader_name", "piece_state", "piece_type"):
            return "list:" + inner
    if "faction" in k:
        return "faction"
    if "tribe" in k or "city" in k or "colony" in k:
        return "tribe"
    if "leader" in k:
        return "leader_name"
    if "state" in k:
        return "piece_state"
    if "type" in k:
        return "piece_type"
    if ("count" in k or "to_remove" in k or k.startswith("legions_")
            or "from_track" in k or "from_fallen" in k or "num" in k):
        return "count"
    if "region" in k:
        return "region"
    return "value"


def _resolve_handler(card_id, scenario):
    """The handler execute_event would dispatch to (or None)."""
    from fs_bot.cards import card_effects as ce
    ario = scenario in ARIOVISTUS_SCENARIOS
    if isinstance(card_id, str) and card_id.startswith("A"):
        return ce._ARIOVISTUS_HANDLERS.get(card_id)
    if isinstance(card_id, int):
        if ario and card_id in ce._ARIOVISTUS_TEXT_CHANGE_HANDLERS:
            return ce._ARIOVISTUS_TEXT_CHANGE_HANDLERS[card_id]
        return ce._BASE_HANDLERS.get(card_id)
    return None


def _params_get_call(node):
    """(key, default_node) if node is params.get("key"[, default])."""
    if (isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "get"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "params"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)):
        default = node.args[1] if len(node.args) > 1 else None
        return node.args[0].value, default
    return None


def _entry_reads(body_nodes, var):
    """{subkey: kind} for reads of ``var`` inside a loop body:
    var["sub"], var.get("sub"[, default])."""
    fields = {}
    for stmt in body_nodes:
        for node in ast.walk(stmt):
            key = default = None
            if (isinstance(node, ast.Subscript)
                    and isinstance(node.value, ast.Name)
                    and node.value.id == var
                    and isinstance(node.slice, ast.Constant)
                    and isinstance(node.slice.value, str)):
                key = node.slice.value
            elif (isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "get"
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id == var
                    and node.args
                    and isinstance(node.args[0], ast.Constant)
                    and isinstance(node.args[0].value, str)):
                key = node.args[0].value
                default = node.args[1] if len(node.args) > 1 else None
            if key is not None and key not in fields:
                fields[key] = infer_kind(key, default)
    return fields


@lru_cache(maxsize=None)
def _schema_uncached(card_id, ario):
    handler = None
    from fs_bot.cards import card_effects as ce
    if isinstance(card_id, str) and card_id.startswith("A"):
        handler = ce._ARIOVISTUS_HANDLERS.get(card_id)
    elif isinstance(card_id, int):
        if ario and card_id in ce._ARIOVISTUS_TEXT_CHANGE_HANDLERS:
            handler = ce._ARIOVISTUS_TEXT_CHANGE_HANDLERS[card_id]
        else:
            handler = ce._BASE_HANDLERS.get(card_id)
    if handler is None:
        return {}
    try:
        tree = ast.parse(textwrap.dedent(inspect.getsource(handler)))
    except Exception:
        return {}
    fn = tree.body[0]

    schema = {}          # key -> spec (insertion-ordered = source order)
    var_to_key = {}      # local name -> params key it holds

    for node in ast.walk(fn):
        # x = params.get("key"[, default])
        if isinstance(node, ast.Assign) and len(node.targets) == 1 \
                and isinstance(node.targets[0], ast.Name):
            got = _params_get_call(node.value)
            if got:
                var_to_key[node.targets[0].id] = got[0]
        got = _params_get_call(node)
        if got:
            key, default = got
            if key not in schema:
                schema[key] = {"kind": infer_kind(key, default),
                               "entry_fields": None, "values": None,
                               "region_pool": None}

    # Loops over a params list: for v in params.get("k", []) / for v in x
    for node in ast.walk(fn):
        if not isinstance(node, ast.For) or not isinstance(node.target,
                                                           ast.Name):
            continue
        key = None
        it = node.iter
        # Unwrap slicing: for x in removals[:2] -> removals
        if isinstance(it, ast.Subscript):
            it = it.value
        got = _params_get_call(it)
        if got:
            key = got[0]
        elif isinstance(it, ast.Name) and it.id in var_to_key:
            key = var_to_key[it.id]
        if key is None or key not in schema:
            continue
        fields = _entry_reads(node.body, node.target.id)
        if fields:
            schema[key]["kind"] = "entries"
            existing = schema[key]["entry_fields"] or {}
            existing.update(fields)
            schema[key]["entry_fields"] = existing
        else:
            # A list of scalars: infer the element kind from the loop
            # variable's name (for tribe_name in removals -> tribe).
            item = infer_kind(node.target.id)
            if item == "value":
                item = infer_kind(key[:-1] if key.endswith("s") else key)
            if item != "value":
                schema[key]["kind"] = "list:" + item

    for key, spec in (_OVERRIDES.get(card_id) or {}).items():
        if key in schema:
            schema[key].update(spec)
    return schema


def card_param_schema(card_id, scenario):
    """The typed event_params schema for ``card_id`` in ``scenario``."""
    return {k: dict(v) for k, v in _schema_uncached(
        card_id, scenario in ARIOVISTUS_SCENARIOS).items()}


# Card-legal value constraints the handlers enforce (ValueError on
# violation). Offering/generating only these keeps humans out of dead ends
# and points the fuzzer at success paths; the handlers stay authoritative.
_OVERRIDES = {
    "A35": {"piece_type": {"values": (WARBAND, AUXILIA)},
            "ally_faction": {"values": tuple(f for f in FACTIONS
                                             if f != GERMANS)}},
    "A51": {"piece_type": {"values": (AUXILIA, WARBAND)}},
    "A69": {"piece_type": {"values": (WARBAND, AUXILIA)},
            "ally_faction": {"values": (ROMANS, AEDUI)},
            "piece_faction": {"values": (ROMANS, AEDUI)}},
    62: {"moves": {"region_pool": "card62_coastal"}},
    26: {"place_faction": {"values": (ROMANS, AEDUI)},
         "place_type": {"values": (ALLY, CITADEL)}},
    # Card 71 Colony: the colony name must be NEW — never an existing
    # Tribe. Omit it from generated/prompted params; the handler's
    # per-Region default ("Colony_<region>") is always safe.
    71: {"colony_tribe_name": {"kind": "omit"}},
    # Card 22 Hostages unshaded: "remove or replace ... Warbands or
    # Auxilia" — entry piece_type takes those two only.
    22: {"replacements": {"values": (WARBAND, AUXILIA)}},
}


def region_pool(state, name):
    """Named region pools for constrained cards."""
    if name == "card62_coastal":
        from fs_bot.map.map_data import get_adjacent
        return sorted({ARVERNI_REGION, PICTONES, BRITANNIA,
                       *get_adjacent(BRITANNIA, state["scenario"])})
    from fs_bot.map.map_data import get_playable_regions
    return sorted(get_playable_regions(state["scenario"],
                                       state.get("capabilities")))


def kind_values(state, kind, spec=None):
    """Candidate values for a kind — the shared vocabulary for CLI menus
    and fuzz generation. Returns a list (may contain None for optional
    piece_state)."""
    if spec and spec.get("values"):
        return list(spec["values"])
    if kind in ("region", "regions"):
        return region_pool(state, (spec or {}).get("region_pool"))
    if kind in ("faction", "factions"):
        return list(FACTIONS)
    if kind == "tribe":
        return sorted(state.get("tribes", {}))
    if kind == "count":
        return list(range(9))
    if kind == "direction":
        return [SENATE_UP, SENATE_DOWN]
    if kind == "piece_type":
        return list(PIECE_TYPES)
    if kind == "piece_state":
        return list(PIECE_STATES)
    if kind == "leader_name":
        return list(LEADER_NAMES)
    return region_pool(state, None)     # "value" fallback


def _list_item_kind(kind):
    """The element kind for 'list:<kind>' keys, else None."""
    return kind[5:] if kind.startswith("list:") else None


def generate_params(state, card_id, rng, *, include_p=0.9):
    """Random-but-typed event_params drawn from the card's schema (the
    fuzzer's success-path generator). Every entry field the handler reads
    is populated (subscript reads raise KeyError otherwise)."""
    schema = card_param_schema(card_id, state.get("scenario"))
    params = {}
    for key, spec in schema.items():
        kind = spec["kind"]
        if kind == "omit":
            continue
        if rng.random() > include_p:
            continue
        if kind == "entries":
            fields = spec.get("entry_fields") or {}
            entries = []
            for _ in range(rng.randrange(1, 3)):
                e = {}
                for sub, sk in fields.items():
                    vals = kind_values(state, sk, spec)
                    e[sub] = vals[rng.randrange(len(vals))]
                entries.append(e)
            params[key] = entries
        elif kind in ("regions", "factions") or kind.startswith("list:"):
            item = _list_item_kind(kind) or kind[:-1]
            vals = kind_values(state, item, spec)
            n = rng.randrange(1, min(4, len(vals) + 1))
            picks = []
            for _ in range(n):
                v = vals[rng.randrange(len(vals))]
                if v not in picks:
                    picks.append(v)
            params[key] = picks
        else:
            vals = kind_values(state, kind, spec)
            params[key] = vals[rng.randrange(len(vals))]
    return params
