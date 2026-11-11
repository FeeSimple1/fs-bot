"""A31 Stalwart cancels Card 59's additional Losses to Germans in Battle."""
import pytest

from fs_bot import rules_consts as rc
from fs_bot.battle.losses import calculate_losses
from fs_bot.battle.resolve import _calculate_attack_losses
from fs_bot.board.pieces import count_pieces, place_piece
from fs_bot.cards.capabilities import deactivate_capability, get_capability_owner
from fs_bot.engine.execute import execute_decision
from fs_bot.tests.test_colony_consumers import board, clean, play


def battle_board(horse, stalwart, *, roman=False, target=rc.GERMANS):
    state = board(rc.SCENARIO_ARIOVISTUS)
    actor = rc.ROMANS if roman else rc.BELGAE
    place_piece(state, rc.ATREBATES, actor, rc.AUXILIA if roman else rc.WARBAND, 6)
    place_piece(state, rc.ATREBATES, target, rc.WARBAND, 8)
    if horse:
        play(state, 59, actor, shaded=not roman)
    if stalwart:
        play(state, 'A31', rc.GERMANS, shaded=True)
    # Full authored Battle must retain the trusted per-Command Region selection.
    state['decision_agent'] = lambda _s, _f, req: (
        {'retreat': False} if req['kind'] == 'RETREAT' else None)
    return state, actor


@pytest.mark.parametrize('horse,stalwart,expected', [
    (False, False, 3), (False, True, 3), (True, False, 6), (True, True, 3)])
@pytest.mark.parametrize('roman', [False, True])
def test_full_battle_stalwart_cancels_both_sides_of_horse(horse, stalwart, expected, roman):
    state, actor = battle_board(horse, stalwart, roman=roman)
    result = execute_decision(state, actor, {'action': 'command', 'player_action': {
        'command': rc.CMD_BATTLE, 'regions': [rc.ATREBATES], 'sa': 'No SA', 'sa_regions': [],
        'details': {'battle_plan': [{'region': rc.ATREBATES, 'target': rc.GERMANS}]}}})
    assert result['executed'] and not result['errors'], result
    assert count_pieces(state, rc.ATREBATES, rc.GERMANS, rc.WARBAND) == 8 - expected
    clean(state)


@pytest.mark.parametrize('counterattack', [False, True])
@pytest.mark.parametrize('roman', [False, True])
@pytest.mark.parametrize('target', [rc.GERMANS, rc.AEDUI])
def test_loss_calculators_and_capability_removal_keep_target_scope(counterattack, roman, target):
    state, actor = battle_board(True, True, roman=roman, target=target)
    key = 'card59_unshaded_region' if roman else 'card59_shaded_region'
    state.setdefault('event_modifiers', {})[key] = rc.ATREBATES
    kwargs = {'is_retreat': False, 'had_fort_at_start': False, 'had_citadel_at_start': False}
    expected = 3 if target == rc.GERMANS else 6
    assert calculate_losses(state, rc.ATREBATES, actor, target,
                            is_counterattack=counterattack) == expected
    if not counterattack:
        assert _calculate_attack_losses(state, rc.ATREBATES, actor, target, **kwargs) == expected
    assert state['event_modifiers'][key] == rc.ATREBATES
    if not roman:
        assert get_capability_owner(state, 59) == actor
    deactivate_capability(state, 'A31')
    assert calculate_losses(state, rc.ATREBATES, actor, target,
                            is_counterattack=counterattack) == 6
    if not counterattack:
        assert _calculate_attack_losses(state, rc.ATREBATES, actor, target, **kwargs) == 6
