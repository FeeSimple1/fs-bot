"""card_text — full printed card texts for display, parsed from the
Reference Documents card-reference transcriptions.

The engine implements card EFFECTS in card_effects.py; this module only
supplies the human-readable text (both sides + Tips) so the CLI can show
players what a card says. Parsed lazily, cached, and safe to use when the
Reference Documents are absent (returns "").
"""

import os
import re

from fs_bot.rules_consts import ARIOVISTUS_SCENARIOS

_CACHE = None

# Numeric amendments in A Card Reference delimit blocks just like A-prefix
# replacement cards. Preserve any printed carnyx suffix in a card's identity.
_HEADER_RE = re.compile(r"^((?:A\d{1,2}C?)|(?:O\d{1,2})|(?:\d{1,2}))\.\s+\S")


def _card_id(header_id):
    return int(header_id) if header_id.isdigit() else header_id


def _reference_dir():
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.dirname(os.path.dirname(here))
    return os.path.join(root, "Reference Documents")


def _parse_file(path, header_re, id_fn):
    """Split a card-reference file into {card_id: text_block}."""
    out = {}
    try:
        with open(path, encoding="utf-8") as reference:
            lines = reference.read().splitlines()
    except OSError:
        return out
    cur_id, cur = None, []
    for line in lines:
        m = header_re.match(line)
        if m:
            if cur_id is not None:
                out[cur_id] = "\n".join(cur).strip()
            cur_id = id_fn(m.group(1))
            cur = [line]
        elif cur_id is not None:
            cur.append(line)
    if cur_id is not None:
        out[cur_id] = "\n".join(cur).strip()
    return out


def _load():
    global _CACHE
    if _CACHE is not None:
        return _CACHE
    ref = _reference_dir()
    # Base cards: "1. Cicero Ro L Ar L Ae S Be L" ... headers are
    # "<int>. <Title...>" at column 0.
    base = _parse_file(
        os.path.join(ref, "Card Reference"),
        _HEADER_RE, _card_id)
    # Keep amendments separate: an integer card ID can have different text
    # depending on the scenario. They must neither overwrite base text nor be
    # swallowed into the preceding A-prefix card's block.
    expansion = _parse_file(
        os.path.join(ref, "Ariovistus", "A Card Reference"),
        _HEADER_RE, _card_id)
    _CACHE = base, expansion
    return _CACHE


def get_card_text(card_id, scenario=None):
    """Full printed text block for a card (title line, both sides, Tips),
    or "" when unknown/unavailable (e.g. Winter cards).

    Integer amendments use the same scenario selection as the Event engine;
    A-prefix and optional O-prefix cards have unambiguous printed identities.
    """
    base, expansion = _load()
    if scenario in ARIOVISTUS_SCENARIOS or isinstance(card_id, str):
        if card_id in expansion:
            return expansion[card_id]
    return base.get(card_id, "")


def format_card_text(card_id, indent="  ", scenario=None):
    """Indent the reference text without inventing missing side boundaries.

    The transcription does not consistently mark the boundary between sides,
    and some Events have only a single effect. Preserve its paragraphs and
    CAPABILITY/Tips/Rationale markers instead of labelling a nonexistent side.
    """
    txt = get_card_text(card_id, scenario=scenario)
    if not txt:
        return ""
    return "\n".join(indent + line for line in txt.splitlines())
