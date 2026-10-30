"""PR-08: bonus troops do not authorize the same ordinary Ally placement.

Owner-adopted 29 October 2026; subject to later authoritative correction.
The printed bonus quantities and named-Leader exceptions still apply.
"""

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.control import is_controlled_by
from fs_bot.board.pieces import count_pieces, place_piece
from fs_bot.cards.capabilities import activate_capability, set_capability_owner
from fs_bot.commands.common import CommandError
from fs_bot.commands.rally import recruit_in_region, rally_in_region
from fs_bot.state.serialize import encode
from fs_bot.state.state_schema import build_initial_state, check_structural_integrity


@pytest.mark.parametrize('card', [25, 'A70', 'A5'])
def test_bonus_cannot_create_control_for_the_same_ordinary_ally_option(card):
    scenario = rc.SCENARIO_GREAT_REVOLT if card == 25 else rc.SCENARIO_ARIOVISTUS
    state = build_initial_state(scenario, seed=73)
    state['resources'] = {f: 20 for f in rc.FACTIONS}
    if card == 25:
        region, tribe, faction, amount = rc.PICTONES, rc.TRIBE_PICTONES, rc.AEDUI, 2
        activate_capability(state, card, rc.EVENT_SHADED)
        set_capability_owner(state, card, faction)
    elif card == 'A70':
        region, tribe, faction, amount = rc.NERVII, rc.TRIBE_EBURONES, rc.BELGAE, 2
        activate_capability(state, card, rc.EVENT_SHADED)
    else:
        region, tribe, faction, amount = rc.CISALPINA, rc.TRIBE_NORI, rc.ROMANS, 1
        state['markers'].setdefault(region, {})[rc.MARKER_GALLIA_TOGATA] = {'card_id': card}

    assert not is_controlled_by(state, region, faction)
    before = encode(state)
    with pytest.raises(CommandError, match='Place Ally requires'):
        if faction == rc.ROMANS:
            recruit_in_region(state, region, 'place_ally', tribe=tribe)
        else:
            rally_in_region(state, region, faction, 'place_ally', tribe=tribe)
    # No bonus is placed, payment made, or RNG consumed by the invalid choice.
    assert encode(state) == before

    # The legal troop option still receives its compulsory addition when the
    # ordinary quantity is zero. It establishes Control for later actions.
    if faction == rc.ROMANS:
        result = recruit_in_region(state, region, 'place_auxilia', count=amount)
        piece = rc.AUXILIA
    else:
        result = rally_in_region(state, region, faction, 'place_warbands', count=amount)
        piece = rc.WARBAND
    assert result['pieces_placed'][piece] == amount
    assert count_pieces(state, region, faction, piece) == amount
    assert is_controlled_by(state, region, faction)
    assert state['tribes'][tribe]['allied_faction'] is None
    assert check_structural_integrity(state) == []


def test_aquitani_does_not_remove_vercingetorix_explicit_no_control_exception():
    state = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=73)
    state['resources'][rc.ARVERNI] = 20
    activate_capability(state, 25, rc.EVENT_SHADED)
    set_capability_owner(state, 25, rc.ARVERNI)
    place_piece(state, rc.PICTONES, rc.ARVERNI, rc.LEADER, leader_name=rc.VERCINGETORIX)
    place_piece(state, rc.PICTONES, rc.ROMANS, rc.AUXILIA, 4)
    assert not is_controlled_by(state, rc.PICTONES, rc.ARVERNI)
    result = rally_in_region(state, rc.PICTONES, rc.ARVERNI,
                             'place_ally', tribe=rc.TRIBE_PICTONES)
    assert result['pieces_placed'] == {rc.ALLY: 1, rc.WARBAND: 2}
    # Even the complete placement is insufficient to obtain Control: the
    # independent named-Leader permission, not the bonus, authorizes the Ally.
    assert not is_controlled_by(state, rc.PICTONES, rc.ARVERNI)
    assert check_structural_integrity(state) == []
