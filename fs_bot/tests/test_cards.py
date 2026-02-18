"""
test_cards.py — Tests for card data, capabilities, and card effect stubs.

Verifies:
- Every base card (1-72) has metadata
- Every Ariovistus card has metadata
- Faction order length matches expected count per card
- All capability cards flagged correctly
- Winter cards have correct properties
- Capability tracker: activate/deactivate/query round-trip,
  shaded vs unshaded tracking, §5.1.2 override behavior
- Card effect stubs: dispatcher raises NotImplementedError for every card
"""

import pytest

from fs_bot.rules_consts import (
    ROMANS, ARVERNI, AEDUI, BELGAE, GERMANS,
    CARD_NAMES_BASE, CARD_NAMES_ARIOVISTUS,
    CAPABILITY_CARDS, CAPABILITY_CARDS_ARIOVISTUS,
    SECOND_EDITION_CARDS,
    SCENARIO_PAX_GALLICA, SCENARIO_ARIOVISTUS,
    EVENT_SHADED, EVENT_UNSHADED,
    NP_SYMBOL_CARNYX, NP_SYMBOL_LAURELS, NP_SYMBOL_SWORDS,
    WINTER_CARD,
)
from fs_bot.cards.card_data import (
    get_card, get_faction_order, is_capability_card,
    get_base_event_card_ids, get_ariovistus_event_card_ids,
    get_winter_card_ids, get_all_base_cards, get_all_ariovistus_cards,
    get_np_symbols,
)
from fs_bot.cards.capabilities import (
    activate_capability, deactivate_capability,
    is_capability_active, get_active_capabilities,
    is_valid_capability,
)
from fs_bot.cards.card_effects import (
    execute_event, get_all_card_ids,
)


# ===================================================================
# Card Data Tests
# ===================================================================

class TestBaseCardData:
    """Tests for base game card metadata."""

    def test_all_72_base_cards_have_metadata(self):
        """Every base event card (1-72) must have a CardData entry."""
        for card_id in range(1, 73):
            card = get_card(card_id)
            assert card is not None, f"Card {card_id} missing"
            assert card.card_id == card_id
            assert card.title == CARD_NAMES_BASE[card_id]

    def test_base_card_titles_match_rules_consts(self):
        """Card titles must match CARD_NAMES_BASE exactly."""
        for card_id in range(1, 73):
            card = get_card(card_id)
            assert card.title == CARD_NAMES_BASE[card_id], (
                f"Card {card_id}: expected {CARD_NAMES_BASE[card_id]!r}, "
                f"got {card.title!r}"
            )

    def test_base_faction_order_has_4_factions(self):
        """Base game cards should have exactly 4 factions in order.

        Base game has 4 factions: Romans, Arverni, Aedui, Belgae.
        """
        for card_id in range(1, 73):
            card = get_card(card_id)
            assert len(card.faction_order) == 4, (
                f"Card {card_id} ({card.title}): expected 4 factions, "
                f"got {len(card.faction_order)}: {card.faction_order}"
            )

    def test_base_faction_order_contains_only_base_factions(self):
        """Base game faction orders should only contain base factions."""
        base_factions = {ROMANS, ARVERNI, AEDUI, BELGAE}
        for card_id in range(1, 73):
            card = get_card(card_id)
            for faction in card.faction_order:
                assert faction in base_factions, (
                    f"Card {card_id} ({card.title}): unexpected faction "
                    f"{faction!r} in order"
                )

    def test_base_faction_order_no_duplicates(self):
        """Each faction appears exactly once in the order."""
        for card_id in range(1, 73):
            card = get_card(card_id)
            assert len(set(card.faction_order)) == len(card.faction_order), (
                f"Card {card_id} ({card.title}): duplicate factions in order"
            )

    def test_base_capability_cards_flagged(self):
        """All base capability cards must be flagged is_capability=True."""
        for card_id in CAPABILITY_CARDS:
            card = get_card(card_id)
            assert card.is_capability is True, (
                f"Card {card_id} ({card.title}): should be capability"
            )

    def test_base_non_capability_cards_not_flagged(self):
        """Non-capability base cards must be flagged is_capability=False."""
        for card_id in range(1, 73):
            if card_id not in CAPABILITY_CARDS:
                card = get_card(card_id)
                assert card.is_capability is False, (
                    f"Card {card_id} ({card.title}): should not be capability"
                )

    def test_base_event_cards_not_winter(self):
        """Event cards should not be flagged as Winter."""
        for card_id in range(1, 73):
            card = get_card(card_id)
            assert card.is_winter is False

    def test_winter_cards_exist(self):
        """5 Winter cards should exist."""
        winter_ids = get_winter_card_ids()
        assert len(winter_ids) == 5
        for wid in winter_ids:
            card = get_card(wid)
            assert card.is_winter is True
            assert card.title == WINTER_CARD
            assert card.faction_order == ()
            assert card.np_symbols == {}

    def test_base_card_count(self):
        """Base game should have 72 event cards + 5 winter = 77 total."""
        all_cards = get_all_base_cards()
        event_count = sum(1 for c in all_cards.values() if not c.is_winter)
        winter_count = sum(1 for c in all_cards.values() if c.is_winter)
        assert event_count == 72
        assert winter_count == 5

    def test_np_symbols_present(self):
        """Cards with NP symbols should have them in the card data."""
        # Card 1 (Cicero): Ro L Ar L Ae S Be L
        symbols = get_np_symbols(1)
        assert symbols[ROMANS] == NP_SYMBOL_LAURELS
        assert symbols[ARVERNI] == NP_SYMBOL_LAURELS
        assert symbols[AEDUI] == NP_SYMBOL_SWORDS
        assert symbols[BELGAE] == NP_SYMBOL_LAURELS

    def test_np_symbols_carnyx(self):
        """Verify Carnyx symbols are parsed correctly."""
        # Card 2: Ro L Ar C Ae L Be L
        symbols = get_np_symbols(2)
        assert symbols[ARVERNI] == NP_SYMBOL_CARNYX

    def test_cards_without_np_symbols(self):
        """Some factions on some cards have no NP symbol."""
        # Card 8: Ro Ae L Ar Be — Ar and Be have no symbol
        symbols = get_np_symbols(8)
        assert ROMANS not in symbols
        assert symbols[AEDUI] == NP_SYMBOL_LAURELS
        assert ARVERNI not in symbols
        assert BELGAE not in symbols

    def test_specific_faction_orders(self):
        """Spot-check specific faction orders from Card Reference."""
        # Card 1: Cicero — Ro L Ar L Ae S Be L → (Ro, Ar, Ae, Be)
        assert get_faction_order(1) == (ROMANS, ARVERNI, AEDUI, BELGAE)

        # Card 19: Lucterius — Ar C Ro L Ae L Be → (Ar, Ro, Ae, Be)
        assert get_faction_order(19) == (ARVERNI, ROMANS, AEDUI, BELGAE)

        # Card 55: Commius — Be Ro Ar S Ae L → (Be, Ro, Ar, Ae)
        assert get_faction_order(55) == (BELGAE, ROMANS, ARVERNI, AEDUI)

        # Card 37: Boii — Ae Ro Ar Be S → (Ae, Ro, Ar, Be)
        assert get_faction_order(37) == (AEDUI, ROMANS, ARVERNI, BELGAE)


class TestAriovistusCardData:
    """Tests for Ariovistus card metadata."""

    def test_ariovistus_event_cards_exist(self):
        """All Ariovistus deck event cards must have metadata."""
        event_ids = get_ariovistus_event_card_ids()
        assert len(event_ids) == 72, (
            f"Expected 72 Ariovistus event cards, got {len(event_ids)}"
        )
        for card_id in event_ids:
            card = get_card(card_id, SCENARIO_ARIOVISTUS)
            assert card is not None, f"Ariovistus card {card_id} missing"

    def test_a_prefix_cards_have_metadata(self):
        """All A-prefix cards from CARD_NAMES_ARIOVISTUS must exist."""
        for card_id in CARD_NAMES_ARIOVISTUS:
            if isinstance(card_id, str) and card_id.startswith("A"):
                card = get_card(card_id, SCENARIO_ARIOVISTUS)
                assert card is not None, f"Card {card_id} missing"
                assert card.title == CARD_NAMES_ARIOVISTUS[card_id]

    def test_ariovistus_capability_cards_flagged(self):
        """Ariovistus capability cards must be flagged."""
        for card_id in CAPABILITY_CARDS_ARIOVISTUS:
            assert is_capability_card(card_id, SCENARIO_ARIOVISTUS), (
                f"Card {card_id} should be capability in Ariovistus"
            )

    def test_base_capabilities_also_flagged_in_ariovistus(self):
        """Base capability cards remaining in Ariovistus deck are still capabilities."""
        # Cards like 8 (Baggage Trains), 12 (Titus Labienus) etc.
        # that remain in the Ariovistus deck should still be capabilities
        for card_id in CAPABILITY_CARDS:
            if card_id not in {5, 17, 18, 19, 20, 21, 22, 23, 24, 25,
                               26, 27, 28, 29, 30, 31, 32, 33, 34, 35,
                               36, 37, 38, 40, 43, 45, 51, 53, 56, 57,
                               58, 60, 63, 64, 65, 66, 67, 69, 70}:
                # This base capability card is in the Ariovistus deck
                assert is_capability_card(card_id, SCENARIO_ARIOVISTUS), (
                    f"Base capability card {card_id} should also be capability "
                    f"in Ariovistus"
                )

    def test_ariovistus_cards_with_germans(self):
        """A-prefix cards should include Germans in faction order."""
        # Card A5: Ro Ge Be L Ae L C → (Ro, Ge, Be, Ae)
        card = get_card("A5", SCENARIO_ARIOVISTUS)
        assert GERMANS in card.faction_order

    def test_ariovistus_faction_order_sizes(self):
        """Ariovistus cards have 4 factions each.

        Ariovistus has 4 player factions: Romans, Aedui, Belgae, Germans.
        """
        for card_id in get_ariovistus_event_card_ids():
            card = get_card(card_id, SCENARIO_ARIOVISTUS)
            assert len(card.faction_order) == 4, (
                f"Card {card_id} ({card.title}): expected 4 factions, "
                f"got {len(card.faction_order)}: {card.faction_order}"
            )

    def test_ariovistus_specific_faction_orders(self):
        """Spot-check Ariovistus faction orders."""
        # A5: Ro Ge Be L Ae L C → (Ro, Ge, Be, Ae)
        assert get_faction_order("A5", SCENARIO_ARIOVISTUS) == (
            ROMANS, GERMANS, BELGAE, AEDUI
        )

        # A19: Ge L Ro Ae S Be C → (Ge, Ro, Ae, Be)
        assert get_faction_order("A19", SCENARIO_ARIOVISTUS) == (
            GERMANS, ROMANS, AEDUI, BELGAE
        )

        # A37: Ae L Ro S Ge Be C → (Ae, Ro, Ge, Be)
        assert get_faction_order("A37", SCENARIO_ARIOVISTUS) == (
            AEDUI, ROMANS, GERMANS, BELGAE
        )

    def test_second_edition_cards_have_ariovistus_metadata(self):
        """2nd Edition text-change cards should have Ariovistus-specific data."""
        for card_id in SECOND_EDITION_CARDS:
            card = get_card(card_id, SCENARIO_ARIOVISTUS)
            assert card is not None

    def test_no_duplicate_cards_in_ariovistus_deck(self):
        """Ariovistus deck should not have duplicate entries.

        Per Dual-Purpose Data Structures rule: integer keys in
        CARD_NAMES_ARIOVISTUS are for text lookup, NOT deck composition.
        """
        event_ids = get_ariovistus_event_card_ids()
        # Check no exact duplicates
        assert len(event_ids) == len(set(str(x) for x in event_ids)), (
            "Duplicate card IDs in Ariovistus deck"
        )

    def test_replaced_base_cards_not_in_ariovistus_deck(self):
        """Base cards replaced by A-prefix should not be in Ariovistus deck."""
        event_ids = get_ariovistus_event_card_ids()
        # Cards 5, 17, 18, 19, 20, 21, etc. are replaced by A5, A17, A18...
        # So base card 5 should NOT be in the Ariovistus deck
        from fs_bot.cards.card_data import _REPLACED_BY_A_PREFIX
        for base_num in _REPLACED_BY_A_PREFIX:
            assert base_num not in event_ids, (
                f"Base card {base_num} should be replaced by A{base_num} "
                f"in Ariovistus deck"
            )


class TestCardLookupHelpers:
    """Tests for card lookup helper functions."""

    def test_get_card_base(self):
        card = get_card(1)
        assert card.title == "Cicero"

    def test_get_card_ariovistus(self):
        card = get_card("A5", SCENARIO_ARIOVISTUS)
        assert card.title == "Gallia Togata"

    def test_get_card_invalid(self):
        with pytest.raises(KeyError):
            get_card(999)

    def test_is_capability_card_base(self):
        assert is_capability_card(8) is True   # Baggage Trains
        assert is_capability_card(1) is False  # Cicero

    def test_is_capability_card_ariovistus(self):
        assert is_capability_card("A22", SCENARIO_ARIOVISTUS) is True  # Dread
        assert is_capability_card("A5", SCENARIO_ARIOVISTUS) is False

    def test_get_base_event_card_ids(self):
        ids = get_base_event_card_ids()
        assert ids == list(range(1, 73))

    def test_get_winter_card_ids(self):
        ids = get_winter_card_ids()
        assert len(ids) == 5
        assert all(wid.startswith("W") for wid in ids)


# ===================================================================
# Capability Tracker Tests
# ===================================================================

class TestCapabilityTracker:
    """Tests for the capability tracker module."""

    def _make_state(self):
        return {"scenario": SCENARIO_PAX_GALLICA}

    def test_activate_unshaded(self):
        state = self._make_state()
        activate_capability(state, 8, EVENT_UNSHADED)
        assert is_capability_active(state, 8) is True
        assert is_capability_active(state, 8, EVENT_UNSHADED) is True
        assert is_capability_active(state, 8, EVENT_SHADED) is False

    def test_activate_shaded(self):
        state = self._make_state()
        activate_capability(state, 8, EVENT_SHADED)
        assert is_capability_active(state, 8, EVENT_SHADED) is True
        assert is_capability_active(state, 8, EVENT_UNSHADED) is False

    def test_deactivate(self):
        state = self._make_state()
        activate_capability(state, 8, EVENT_UNSHADED)
        result = deactivate_capability(state, 8)
        assert result == EVENT_UNSHADED
        assert is_capability_active(state, 8) is False

    def test_deactivate_not_active(self):
        state = self._make_state()
        result = deactivate_capability(state, 8)
        assert result is None

    def test_override_side_per_5_1_2(self):
        """§5.1.2: A later Event can replace a capability's side."""
        state = self._make_state()
        activate_capability(state, 8, EVENT_UNSHADED)
        assert is_capability_active(state, 8, EVENT_UNSHADED) is True

        # Dueling Event flips to shaded
        activate_capability(state, 8, EVENT_SHADED)
        assert is_capability_active(state, 8, EVENT_SHADED) is True
        assert is_capability_active(state, 8, EVENT_UNSHADED) is False

    def test_get_active_capabilities(self):
        state = self._make_state()
        activate_capability(state, 8, EVENT_UNSHADED)
        activate_capability(state, 12, EVENT_SHADED)
        caps = get_active_capabilities(state)
        assert caps == {8: EVENT_UNSHADED, 12: EVENT_SHADED}

    def test_get_active_capabilities_empty(self):
        state = self._make_state()
        caps = get_active_capabilities(state)
        assert caps == {}

    def test_multiple_capabilities(self):
        state = self._make_state()
        activate_capability(state, 8, EVENT_UNSHADED)
        activate_capability(state, 15, EVENT_SHADED)
        activate_capability(state, 55, EVENT_UNSHADED)
        assert is_capability_active(state, 8) is True
        assert is_capability_active(state, 15) is True
        assert is_capability_active(state, 55) is True
        assert len(get_active_capabilities(state)) == 3

    def test_invalid_side_raises(self):
        state = self._make_state()
        with pytest.raises(ValueError):
            activate_capability(state, 8, "Invalid")

    def test_is_valid_capability_base(self):
        assert is_valid_capability(8) is True
        assert is_valid_capability(1) is False

    def test_is_valid_capability_ariovistus(self):
        assert is_valid_capability("A22", SCENARIO_ARIOVISTUS) is True
        assert is_valid_capability(8, SCENARIO_ARIOVISTUS) is True


# ===================================================================
# Card Effect Stub Tests
# ===================================================================

class TestCardEffectStubs:
    """Tests that the dispatcher raises NotImplementedError for unimplemented cards."""

    # Cards that have been implemented (no longer stubs).
    # Updated as cards are implemented in card_effects.py.
    _IMPLEMENTED_BASE = {1}
    _IMPLEMENTED_ARIOVISTUS = set()   # A-prefix card IDs (str)
    _IMPLEMENTED_2ND_ED = set()       # 2nd edition card IDs (int)

    def _make_state(self, scenario=None):
        return {"scenario": scenario or SCENARIO_PAX_GALLICA}

    def test_unimplemented_base_cards_raise(self):
        """Dispatcher raises NotImplementedError for unimplemented base cards."""
        state = self._make_state()
        for card_id in range(1, 73):
            if card_id in self._IMPLEMENTED_BASE:
                continue
            with pytest.raises(NotImplementedError):
                execute_event(state, card_id, shaded=False)
            with pytest.raises(NotImplementedError):
                execute_event(state, card_id, shaded=True)

    def test_unimplemented_ariovistus_cards_raise(self):
        """Dispatcher raises NotImplementedError for unimplemented A-prefix cards."""
        state = self._make_state(SCENARIO_ARIOVISTUS)
        a_prefix_ids = [k for k in CARD_NAMES_ARIOVISTUS
                        if isinstance(k, str) and k.startswith("A")]
        for card_id in a_prefix_ids:
            if card_id in self._IMPLEMENTED_ARIOVISTUS:
                continue
            with pytest.raises(NotImplementedError):
                execute_event(state, card_id, shaded=False)
            with pytest.raises(NotImplementedError):
                execute_event(state, card_id, shaded=True)

    def test_unimplemented_second_edition_cards_raise(self):
        """2nd Edition text-change cards raise in Ariovistus context."""
        state = self._make_state(SCENARIO_ARIOVISTUS)
        for card_id in SECOND_EDITION_CARDS:
            if card_id in self._IMPLEMENTED_2ND_ED:
                continue
            with pytest.raises(NotImplementedError):
                execute_event(state, card_id, shaded=False)

    def test_invalid_card_raises_key_error(self):
        state = self._make_state()
        with pytest.raises(KeyError):
            execute_event(state, 999)

    def test_get_all_card_ids(self):
        ids = get_all_card_ids()
        # Should have 72 base + 37 A-prefix
        base_count = sum(1 for i in ids if isinstance(i, int))
        a_count = sum(1 for i in ids if isinstance(i, str))
        assert base_count == 72
        assert a_count == len([k for k in CARD_NAMES_ARIOVISTUS
                               if isinstance(k, str) and k.startswith("A")])
