"""card_text — full printed card texts for display, parsed from the
Reference Documents card-reference transcriptions.

The engine implements card EFFECTS in card_effects.py; this module only
supplies the human-readable text (both sides + Tips) so the CLI can show
players what a card says. Parsed lazily, cached, and safe to use when the
Reference Documents are absent (returns "").
"""

import os
import re

_CACHE = None


def _reference_dir():
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.dirname(os.path.dirname(here))
    return os.path.join(root, "Reference Documents")


def _parse_file(path, header_re, id_fn):
    """Split a card-reference file into {card_id: text_block}."""
    out = {}
    try:
        lines = open(path, encoding="utf-8").read().splitlines()
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
    texts = {}
    # Base cards: "1. Cicero Ro L Ar L Ae S Be L" ... headers are
    # "<int>. <Title...>" at column 0.
    texts.update(_parse_file(
        os.path.join(ref, "Card Reference"),
        re.compile(r"^(\d{1,2})\.\s+\S"), int))
    # Ariovistus cards: "A31. German Phalanx ..." plus "O38. Diviciacus".
    texts.update(_parse_file(
        os.path.join(ref, "Ariovistus", "A Card Reference"),
        re.compile(r"^((?:A\d{1,2})|(?:O38))\.\s+\S"), str))
    _CACHE = texts
    return texts


def get_card_text(card_id):
    """Full printed text block for a card (title line, both sides, Tips),
    or "" when unknown/unavailable (e.g. Winter cards)."""
    return _load().get(card_id, "")


def format_card_text(card_id, indent="  "):
    txt = get_card_text(card_id)
    if not txt:
        return ""
    return "\n".join(indent + l for l in txt.splitlines())
