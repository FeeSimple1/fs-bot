"""card_text — full printed card texts for display, parsed from the
Reference Documents card-reference transcriptions.

The engine implements card EFFECTS in card_effects.py; this module only
supplies the human-readable text (both sides + Tips) so the CLI can show
players what a card says. Parsed lazily, cached, and safe to use when the
Reference Documents are absent (returns "").
"""

import os
import re

from fs_bot.cards.edition import uses_second_edition
from fs_bot.version import reference_directory

_CACHE = None

# Numeric amendments in A Card Reference delimit blocks just like A-prefix
# replacement cards. Preserve any printed carnyx suffix in a card's identity.
_HEADER_RE = re.compile(r"^((?:A\d{1,2}C?)|(?:O\d{1,2})|(?:\d{1,2}))\.\s+\S")

# Two transcribed NP-symbol headers conflict with the Ariovistus faction
# Event Instructions (Seduni Uprising! and Nervii). The corrected §8.2.1
# cues agree with those instructions and the physical card faces inspected
# in Vassal 4.0.0. Correct only these known header suffixes; preserve every
# effect paragraph and leave the read-only Reference Documents untouched.
_HEADER_CUE_CORRECTIONS = {
    "A24": ("Ge Ro Be S Ae L", "Ge L Ro S Be Ae S"),
    "A70": ("Be Ae Ge S Ro C", "Be Ae L Ge S Ro L C"),
}


def _card_id(header_id):
    return int(header_id) if header_id.isdigit() else header_id


def _reference_dir():
    return str(reference_directory())


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
    for card_id, (old_cues, new_cues) in _HEADER_CUE_CORRECTIONS.items():
        if card_id in expansion:
            header, separator, body = expansion[card_id].partition("\n")
            if header.endswith(old_cues):
                expansion[card_id] = (
                    header[:-len(old_cues)] + new_cues + separator + body)
    _CACHE = base, expansion
    return _CACHE


def get_card_text(card_id, scenario=None, card_edition=None):
    """Full printed text block for a card (title line, both sides, Tips),
    or "" when unknown/unavailable (e.g. Winter cards).

    Integer amendments use the same saved edition selection as the Event engine;
    A-prefix and optional O-prefix cards have unambiguous printed identities.
    """
    base, expansion = _load()
    if uses_second_edition(scenario, card_edition) or isinstance(card_id, str):
        if card_id in expansion:
            return expansion[card_id]
    return base.get(card_id, "")


def format_card_text(card_id, indent="  ", scenario=None, card_edition=None):
    """Indent the reference text without inventing missing side boundaries.

    The transcription does not consistently mark the boundary between sides,
    and some Events have only a single effect. Preserve its paragraphs and
    CAPABILITY/Tips/Rationale markers instead of labelling a nonexistent side.
    """
    txt = get_card_text(card_id, scenario=scenario, card_edition=card_edition)
    if not txt:
        return ""
    return "\n".join(indent + line for line in txt.splitlines())
