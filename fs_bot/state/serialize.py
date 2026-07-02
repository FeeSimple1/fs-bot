"""JSON save/load for game state — exact, deterministic round-trip.

The state dict contains values plain JSON cannot represent faithfully:
sets (non_player_factions, marker region-sets), tuples (piece/loss entries),
dicts with non-string keys (capabilities keyed by int card id), and the
``random.Random`` rng whose position must survive a save so a resumed game
continues byte-for-byte identically (CLAUDE.md replay determinism).

Encoding: containers needing it are tagged —
  {"__set__": [...]}     set/frozenset (elements sorted for stable files)
  {"__tuple__": [...]}   tuple
  {"__dict__": [[k, v], ...]}  dict with any non-str key or a key that
                               would collide with a tag
  {"__rng__": [...]}     random.Random (via getstate/setstate)

``decision_agent`` (a live callable) is never saved; the CLI reinstalls it
on load.

Save-file shape (SAVE_VERSION 1):
  {"fsbot_save": 1, "meta": {...}, "log": [...], "state": {...}}
``meta`` records scenario / seed / faction_modes; ``log`` is the CLI's
decision + reactive-response log (see cli/app.py) used by --replay.
"""

import json
import random

SAVE_VERSION = 1

_TAGS = ("__set__", "__tuple__", "__dict__", "__rng__")


def encode(obj):
    """Encode ``obj`` into JSON-safe primitives (tagged where needed)."""
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, random.Random):
        return {"__rng__": encode(obj.getstate())}
    if isinstance(obj, tuple):
        return {"__tuple__": [encode(x) for x in obj]}
    if isinstance(obj, list):
        return [encode(x) for x in obj]
    if isinstance(obj, (set, frozenset)):
        items = [encode(x) for x in obj]
        items.sort(key=lambda e: json.dumps(e, sort_keys=True))
        return {"__set__": items}
    if isinstance(obj, dict):
        plain = (all(isinstance(k, str) for k in obj)
                 and not any(k in _TAGS for k in obj))
        if plain:
            return {k: encode(v) for k, v in obj.items()}
        return {"__dict__": [[encode(k), encode(v)]
                             for k, v in obj.items()]}
    raise TypeError(f"Cannot serialize {type(obj).__name__}: {obj!r}")


def decode(obj):
    """Inverse of :func:`encode`."""
    if isinstance(obj, list):
        return [decode(x) for x in obj]
    if isinstance(obj, dict):
        if "__rng__" in obj and len(obj) == 1:
            rng = random.Random()
            rng.setstate(decode(obj["__rng__"]))
            return rng
        if "__tuple__" in obj and len(obj) == 1:
            return tuple(decode(x) for x in obj["__tuple__"])
        if "__set__" in obj and len(obj) == 1:
            return set(decode(x) for x in obj["__set__"])
        if "__dict__" in obj and len(obj) == 1:
            return {decode(k): decode(v) for k, v in obj["__dict__"]}
        return {k: decode(v) for k, v in obj.items()}
    return obj


def save_game(state, path, *, meta=None, log=None):
    """Write ``state`` (minus decision_agent) + meta + log to ``path``."""
    to_save = {k: v for k, v in state.items() if k != "decision_agent"}
    payload = {"fsbot_save": SAVE_VERSION,
               "meta": meta or {},
               "log": log or [],
               "state": encode(to_save)}
    with open(path, "w") as fh:
        json.dump(payload, fh, separators=(",", ":"), sort_keys=True)


def load_game(path):
    """Read a save file. Returns (state, meta, log).

    The caller must reinstall ``state['decision_agent']`` if the game has
    human seats.
    """
    with open(path) as fh:
        payload = json.load(fh)
    version = payload.get("fsbot_save")
    if version != SAVE_VERSION:
        raise ValueError(f"Unsupported save version: {version!r} "
                         f"(expected {SAVE_VERSION})")
    return (decode(payload["state"]), payload.get("meta") or {},
            payload.get("log") or [])
