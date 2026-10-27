"""A33/A70 are two-sided Capabilities (A Card Reference, §5.3 banner)."""
from copy import deepcopy

import pytest

from fs_bot import rules_consts as rc
from fs_bot.battle.resolve import resolve_battle
from fs_bot.board.control import refresh_all_control
from fs_bot.board.pieces import place_piece
from fs_bot.cards.capabilities import get_active_capabilities
from fs_bot.cards.event_eval import is_event_effective
from fs_bot.engine.execute import _execute_event, _decide_defender_retreat
from fs_bot.state.setup import setup_scenario
from fs_bot.state.state_schema import build_initial_state
from fs_bot.state.serialize import save_game, load_game, encode


CASES = [
    ('A33', rc.GERMANS, ('card_A33_no_german_retreat',
                        'card_A33_remove_outnumbered')),
    ('A70', rc.BELGAE, ('card_A70_no_belgae_retreat',)),
]


def event(state, card, *, shaded=False, params=None):
    result = _execute_event(state, rc.ROMANS, {'details': {
        'card_id': card,
        'text_preference': rc.EVENT_SHADED if shaded else rc.EVENT_UNSHADED,
        'event_params': params or {},
    }}, human=True)
    assert result['executed'], result


@pytest.mark.parametrize('card,faction,flags', CASES)
@pytest.mark.parametrize('legacy', [False, True])
@pytest.mark.parametrize('explicit_target', [False, True])
def test_saved_capability_is_listed_and_shifting_loyalties_removes_it(
        tmp_path, card, faction, flags, legacy, explicit_target):
    state = setup_scenario(rc.SCENARIO_ARIOVISTUS, seed=21)
    event(state, card)
    if legacy:
        del state['capabilities'][card]
    path = tmp_path / 'capability.json'
    save_game(state, path)
    resumed, _, _ = load_game(path, validate=True)
    before = encode(resumed)
    assert get_active_capabilities(resumed)[card] == rc.EVENT_UNSHADED
    assert encode(resumed) == before  # Old-save lookup never mutates a preview.
    assert is_event_effective(resumed, 50)
    event(resumed, 50, params={'target_capability': card}
          if explicit_target else {})
    assert card not in get_active_capabilities(resumed)
    assert all(key not in resumed['event_modifiers'] for key in flags)
    assert not is_event_effective(resumed, 50)


@pytest.mark.parametrize('card,faction,flags', CASES)
@pytest.mark.parametrize('legacy', [False, True])
def test_shaded_replaces_unshaded_and_unshaded_can_return(
        card, faction, flags, legacy):
    state = setup_scenario(rc.SCENARIO_ARIOVISTUS, seed=21)
    event(state, card)
    if legacy:
        del state['capabilities'][card]
    event(state, card, shaded=True)
    assert get_active_capabilities(state)[card] == rc.EVENT_SHADED
    assert all(key not in state['event_modifiers'] for key in flags)
    event(state, card)
    assert get_active_capabilities(state)[card] == rc.EVENT_UNSHADED
    assert all(state['event_modifiers'][key] for key in flags)


@pytest.mark.parametrize('card,faction,flags', CASES)
@pytest.mark.parametrize('condition', ['unshaded', 'removed', 'shaded', 'old_stale'])
def test_actual_battle_and_retreat_choice_follow_active_side(
        card, faction, flags, condition):
    state = build_initial_state(rc.SCENARIO_ARIOVISTUS, seed=21)
    place_piece(state, rc.SEQUANI, rc.ROMANS, rc.AUXILIA, count=2)
    place_piece(state, rc.SEQUANI, faction, rc.WARBAND, count=6)
    place_piece(state, rc.UBII, faction, rc.WARBAND, count=2)
    refresh_all_control(state)
    event(state, card)
    if condition == 'removed':
        event(state, 50, params={'target_capability': card})
    elif condition == 'shaded':
        event(state, card, shaded=True)
    elif condition == 'old_stale':
        # A pre-fix save could record shaded while retaining unshaded flags.
        state['capabilities'][card] = rc.EVENT_SHADED

    requests = []

    def agent(board, who, request):
        requests.append(request)
        return {'retreat': True, 'region': rc.UBII}

    state['decision_agent'] = agent
    decision = _decide_defender_retreat(
        state, rc.SEQUANI, rc.ROMANS, faction, False)
    allowed = condition != 'unshaded'
    assert decision == ((True, rc.UBII) if allowed else (False, None))
    assert bool(requests) == allowed
    result = resolve_battle(
        deepcopy(state), rc.SEQUANI, rc.ROMANS, faction,
        retreat_declaration=True, retreat_region=rc.UBII)
    assert result['defender_retreated'] == allowed


@pytest.mark.parametrize('leader', [None, rc.SUCCESSOR, rc.ARIOVISTUS_LEADER])
def test_a33_counterattack_exemption_requires_named_ariovistus_on_map(leader):
    state = build_initial_state(rc.SCENARIO_ARIOVISTUS, seed=21)
    place_piece(state, rc.SEQUANI, rc.GERMANS, rc.WARBAND, count=4)
    place_piece(state, rc.SEQUANI, rc.ARVERNI, rc.WARBAND, count=5)
    if leader:
        # The exemption is map-wide, but a Successor is not Ariovistus.
        place_piece(state, rc.UBII, rc.GERMANS, rc.LEADER, leader_name=leader)
    refresh_all_control(state)
    event(state, 'A33')
    result = resolve_battle(
        state, rc.SEQUANI, rc.ARVERNI, rc.GERMANS, retreat_declaration=False)
    assert bool(result.get('a33_outnumbered_removed')) == (leader != rc.ARIOVISTUS_LEADER)


@pytest.mark.parametrize('order', [('A33', 'A31'), ('A31', 'A33')])
@pytest.mark.parametrize('phalanx', ['active', 'removed', 'unshaded'])
@pytest.mark.parametrize('retreat', [False, True])
def test_a31_cancels_a33_harm_while_active_and_a33_returns_after_removal(
        order, phalanx, retreat):
    """A31 shaded cancels harmful Event effects in Battle, including A33."""
    state = build_initial_state(rc.SCENARIO_ARIOVISTUS, seed=21)
    if retreat:
        attacker = rc.ROMANS
        place_piece(state, rc.SEQUANI, attacker, rc.AUXILIA, count=2)
        place_piece(state, rc.SEQUANI, rc.GERMANS, rc.WARBAND, count=6)
        place_piece(state, rc.UBII, rc.GERMANS, rc.WARBAND, count=2)
    else:
        attacker = rc.ARVERNI
        place_piece(state, rc.SEQUANI, attacker, rc.WARBAND, count=5)
        place_piece(state, rc.SEQUANI, rc.GERMANS, rc.WARBAND, count=4)
    refresh_all_control(state)
    for card in order:
        event(state, card, shaded=(card == 'A31'))
    if phalanx == 'removed':
        event(state, 50, params={'target_capability': 'A31'})
    elif phalanx == 'unshaded':
        event(state, 'A31')
    # Cancellation suppresses the harmful effect, not the capability itself.
    assert get_active_capabilities(state)['A33'] == rc.EVENT_UNSHADED
    if retreat:
        requests = []

        def agent(board, who, request):
            requests.append(request)
            return {'retreat': True, 'region': rc.UBII}

        state['decision_agent'] = agent
        decision = _decide_defender_retreat(
            state, rc.SEQUANI, attacker, rc.GERMANS, False)
        assert decision == ((True, rc.UBII) if phalanx == 'active' else (False, None))
        assert bool(requests) == (phalanx == 'active')
    result = resolve_battle(
        state, rc.SEQUANI, attacker, rc.GERMANS,
        retreat_declaration=retreat, retreat_region=rc.UBII if retreat else None)
    if retreat:
        assert result['defender_retreated'] == (phalanx == 'active')
    else:
        assert bool(result.get('a33_outnumbered_removed')) == (phalanx != 'active')
