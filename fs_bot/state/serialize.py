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
  {"fsbot_save": 1, "engine": {...}, "meta": {...}, "log": [...], "state": {...}}
``meta`` records scenario / seed / faction_modes; ``log`` is the CLI's
decision + reactive-response log (see cli/app.py) used by --replay.
The optional ``engine`` envelope field identifies the writer's version and
source digest. Older saves without it remain readable; it does not change
game state or assert replay compatibility with a different engine.
"""

import json
import os
import random
import tempfile

from fs_bot.version import engine_identity

SAVE_VERSION = 1


class SaveFileError(ValueError):
    """A save cannot be read safely; callers should show its message."""

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
        tags = set(obj).intersection(_TAGS)
        if tags:
            if len(obj) != 1:
                raise ValueError("Tagged value has extra fields")
            tag = next(iter(tags))
            if tag != "__rng__" and not isinstance(obj[tag], list):
                raise ValueError(f"{tag} must contain a list")
        if "__rng__" in obj and len(obj) == 1:
            rng = random.Random()
            rng.setstate(decode(obj["__rng__"]))
            return rng
        if "__tuple__" in obj and len(obj) == 1:
            return tuple(decode(x) for x in obj["__tuple__"])
        if "__set__" in obj and len(obj) == 1:
            return set(decode(x) for x in obj["__set__"])
        if "__dict__" in obj and len(obj) == 1:
            result = {}
            for pair in obj["__dict__"]:
                if not isinstance(pair, list) or len(pair) != 2:
                    raise ValueError("__dict__ entries must be key/value pairs")
                key, value = decode(pair[0]), decode(pair[1])
                if key in result:
                    raise ValueError("__dict__ contains a duplicate key")
                result[key] = value
            return result
        return {k: decode(v) for k, v in obj.items()}
    return obj


def save_game(state, path, *, meta=None, log=None):
    """Write ``state`` (minus decision_agent) + meta + log to ``path``."""
    to_save = {k: v for k, v in state.items() if k != "decision_agent"}
    payload = {"fsbot_save": SAVE_VERSION,
               "engine": engine_identity(),
               "meta": meta or {},
               "log": log or [],
               "state": encode(to_save)}
    # Replace only a completely written save. A serialization/I/O failure
    # must leave the preceding autosave available for recovery.
    body = json.dumps(payload, separators=(",", ":"))
    parent = os.path.dirname(os.path.abspath(path))
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", dir=parent,
                                         prefix=".fsbot-save-",
                                         delete=False) as fh:
            temporary = fh.name
            fh.write(body)
        os.replace(temporary, path)
    finally:
        if temporary is not None and os.path.exists(temporary):
            os.unlink(temporary)


def load_game(path, *, validate=False):
    """Read a version-1 save, returning ``(state, meta, log)``.

    Envelope and tagged-value shapes are always checked. Frontends must use
    ``validate=True`` to check the playable board and session metadata too.
    The default preserves the low-level serializer's partial-state use cases.
    Unknown save versions are refused, never silently converted. Optional
    version-1 fields remain optional, so older valid snapshots still load.
    The caller must reinstall ``state['decision_agent']`` for human seats.
    """
    try:
        with open(path, encoding="utf-8") as fh:
            payload = json.load(fh)
        if not isinstance(payload, dict):
            raise ValueError("Save must contain a JSON object")
        version = payload.get("fsbot_save")
        if type(version) is not int or version != SAVE_VERSION:
            raise ValueError(f"Unsupported save version: {version!r} "
                             f"(expected {SAVE_VERSION})")
        if "state" not in payload:
            raise ValueError("Save has no game state")
        if "engine" in payload:
            identity = payload["engine"]
            if (not isinstance(identity, dict)
                    or not isinstance(identity.get("version"), str)
                    or not identity["version"]
                    or not isinstance(identity.get("source_sha256"), str)
                    or len(identity["source_sha256"]) != 64
                    or any(c not in "0123456789abcdef" for c in identity["source_sha256"])):
                raise ValueError("Engine provenance must contain a version and SHA-256 digest")
        state = decode(payload["state"])
        if not isinstance(state, dict):
            raise ValueError("Saved state must be an object")
        meta = payload.get("meta", {})
        log = payload.get("log", [])
        # Historical writers occasionally supplied null optional fields.
        meta = {} if meta is None else meta
        log = [] if log is None else log
        if not isinstance(meta, dict):
            raise ValueError("Save metadata must be an object")
        if not isinstance(log, list) or not all(isinstance(e, dict) for e in log):
            raise ValueError("Decision log must be a list of objects")
        if validate:
            from fs_bot.state.save_validation import validate_saved_game
            validate_saved_game(state, meta, log)
        return state, meta, log
    except (ValueError, TypeError, KeyError, IndexError, AttributeError,
            RecursionError, OverflowError) as exc:
        raise SaveFileError(f"Invalid save: {exc}") from exc
