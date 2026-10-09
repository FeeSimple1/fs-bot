"""Region eligibility is a set; persist it in stable order for replay hashes."""
import pytest

import fs_bot.rules_consts as rc
from fs_bot.board.pieces import place_piece
from fs_bot.cards.card_effects import execute_card_44_ariovistus
from fs_bot.state.state_schema import build_initial_state, validate_state


@pytest.mark.parametrize("regions", [
    (rc.PROVINCIA, rc.ATREBATES), (rc.ATREBATES, rc.PROVINCIA),
])
def test_card44a_region_set_is_persisted_in_canonical_order(regions):
    state = build_initial_state(rc.SCENARIO_ARIOVISTUS, seed=55)
    for region in regions:
        place_piece(state, region, rc.ROMANS, rc.AUXILIA)
    state["event_params"] = {"replacements": [
        {"region": region, "from_faction": rc.ROMANS,
         "from_type": rc.AUXILIA, "to_faction": rc.ARVERNI}
        for region in regions
    ]}
    execute_card_44_ariovistus(state, shaded=True)
    assert state["event_modifiers"]["card_44a_command_regions"] == sorted(regions)
    assert not validate_state(state)
