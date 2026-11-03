"""Card 45's Aedui pieces join the entire Battle, retaining their owners.

Card Reference 45 grants pieces "as your own", not merely extra Attack
Losses. §§3.2.4/3.3.4 Counterattack and Reveal therefore affect that force;
A1.4/A3.3.4 preserve an optional Diviciacus's identity and special losses.
"""
from copy import deepcopy

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import (
    count_pieces, count_pieces_by_state, get_available, get_leader_in_region,
    place_piece,
)
from fs_bot.engine.execute import _resolve_card45_battle
from fs_bot.state.state_schema import build_initial_state, validate_state
from fs_bot.tests.test_diviciacus_option import place_diviciacus


def board(scenario=rc.SCENARIO_GREAT_REVOLT, *, optional_leader=False, seed=1):
    state = build_initial_state(scenario, seed=seed,
                               diviciacus_option=optional_leader)
    state['current_card'] = 45
    state['non_player_factions'] = set()
    return state


def event(state, faction=rc.BELGAE, region=rc.CARNUTES, *, choose=None):
    requests = []

    def agent(current, actor, request):
        requests.append((actor, request))
        if choose:
            response = choose(current, actor, request)
            if response is not None:
                return response
        if request.get('request_type') == 'fixed_event_battle':
            return {'region': region, 'defender': rc.ROMANS}
        if request['kind'] == 'retreat':
            return {'retreat': False}
        return None

    state['decision_agent'] = agent
    result = _resolve_card45_battle(state, faction)[0]
    assert result['result']['executed'], result
    return result, requests


@pytest.mark.parametrize('scenario', rc.BASE_SCENARIOS)
@pytest.mark.parametrize('actor', [rc.BELGAE, rc.ARVERNI, rc.AEDUI])
def test_aedui_only_warbands_take_counterattack_and_reveal_once(scenario, actor):
    state = board(scenario)
    place_piece(state, rc.CARNUTES, rc.AEDUI, rc.WARBAND, 2)
    place_piece(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA, 4)
    available = get_available(state, rc.AEDUI, rc.WARBAND)
    result, requests = event(state, actor)
    assert not result['ambush']
    assert count_pieces(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA) == 3
    assert count_pieces(state, rc.CARNUTES, rc.AEDUI, rc.WARBAND) == 1
    assert count_pieces_by_state(state, rc.CARNUTES, rc.AEDUI,
                                 rc.WARBAND, rc.REVEALED) == 1
    assert get_available(state, rc.AEDUI, rc.WARBAND) == available + 1
    assert not any(request['kind'] == 'agreement' for _, request in requests)
    assert '_combined_battle_force' not in state
    assert validate_state(state) == []


@pytest.mark.parametrize('actor', [rc.BELGAE, rc.ARVERNI])
@pytest.mark.parametrize('piece', [rc.ALLY, rc.CITADEL])
def test_aedui_static_force_takes_losses_and_clears_its_own_tribe(actor, piece):
    state = board()
    region, tribe = rc.AEDUI_REGION, rc.TRIBE_AEDUI
    place_piece(state, region, rc.AEDUI, piece)
    state['tribes'][tribe]['allied_faction'] = rc.AEDUI
    place_piece(state, region, rc.ROMANS, rc.AUXILIA, 2)
    available = get_available(state, rc.AEDUI, piece)
    _, requests = event(state, actor, region)
    assert count_pieces(state, region, rc.AEDUI, piece) == 0
    assert get_available(state, rc.AEDUI, piece) == available + 1
    assert state['tribes'][tribe]['allied_faction'] is None
    casualties = [request for who, request in requests
                  if who == actor and request['kind'] == 'loss_order']
    assert casualties and casualties[0]['pieces'] == [(piece, None, rc.AEDUI)]
    assert validate_state(state) == []


def test_human_can_choose_which_owners_warband_absorbs_a_counterattack():
    state = board()
    place_piece(state, rc.CARNUTES, rc.BELGAE, rc.WARBAND, 2)
    place_piece(state, rc.CARNUTES, rc.AEDUI, rc.WARBAND, 2)
    place_piece(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA, 4)
    options = []

    def choose(_state, actor, request):
        if actor == rc.BELGAE and request['kind'] == 'loss_order':
            options.extend(request['pieces'])
            return [(rc.WARBAND, rc.HIDDEN, rc.AEDUI)]

    event(state, choose=choose)
    assert (rc.WARBAND, rc.HIDDEN, rc.AEDUI) in options
    assert (rc.WARBAND, rc.HIDDEN, rc.BELGAE) in options
    assert count_pieces(state, rc.CARNUTES, rc.BELGAE, rc.WARBAND) == 2
    assert count_pieces(state, rc.CARNUTES, rc.AEDUI, rc.WARBAND) == 1
    assert count_pieces_by_state(state, rc.CARNUTES, rc.BELGAE,
                                 rc.WARBAND, rc.REVEALED) == 2
    assert count_pieces_by_state(state, rc.CARNUTES, rc.AEDUI,
                                 rc.WARBAND, rc.REVEALED) == 1
    assert validate_state(state) == []


def test_optional_diviciacus_keeps_save_roll_and_removal_identity():
    state = board(optional_leader=True)
    place_diviciacus(state)
    place_piece(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA, 8)
    expected_rng = deepcopy(state['rng'])
    assert [expected_rng.randint(1, 6) for _ in range(3)] == [2, 5, 1]
    event(state)
    assert count_pieces(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA) == 7
    assert state['rng'].getstate() == expected_rng.getstate()
    assert get_leader_in_region(state, rc.CARNUTES, rc.AEDUI) is None
    assert state['removed_pieces'][rc.AEDUI][rc.LEADER] == 1
    assert get_available(state, rc.AEDUI, rc.LEADER) == 0
    assert get_available(state, rc.BELGAE, rc.LEADER) == 1
    assert validate_state(state) == []


@pytest.mark.parametrize('actor,leader', [(rc.BELGAE, rc.AMBIORIX),
                                        (rc.ARVERNI, rc.VERCINGETORIX)])
def test_two_leaders_each_contribute_but_diviciacus_absorbs_last(actor, leader):
    state = board(optional_leader=True)
    place_diviciacus(state)
    place_piece(state, rc.CARNUTES, actor, rc.LEADER, leader_name=leader)
    place_piece(state, rc.CARNUTES, rc.AEDUI, rc.ALLY)
    state['tribes'][rc.TRIBE_CARNUTES]['allied_faction'] = rc.AEDUI
    place_piece(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA, 8)
    observed = []

    def choose(_state, faction, request):
        if faction == actor and request['kind'] == 'loss_order':
            observed.append(request['pieces'])

    expected_rng = deepcopy(state['rng'])
    assert [expected_rng.randint(1, 6) for _ in range(2)] == [2, 5]
    event(state, actor, choose=choose)
    assert count_pieces(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA) == 6
    assert observed[0] == [(rc.LEADER, None, actor)]
    assert observed[1] == [(rc.ALLY, None, rc.AEDUI)]
    assert observed[2] == [(rc.LEADER, None, rc.AEDUI)]
    assert state['rng'].getstate() == expected_rng.getstate()
    assert get_leader_in_region(state, rc.CARNUTES, actor) is None
    assert get_leader_in_region(state, rc.CARNUTES, rc.AEDUI) == rc.DIVICIACUS
    assert validate_state(state) == []


@pytest.mark.parametrize('actor', [rc.BELGAE, rc.ARVERNI])
def test_borrowed_diviciacus_does_not_become_an_executors_ambush_leader(actor):
    state = board(optional_leader=True)
    place_diviciacus(state)
    place_piece(state, rc.CARNUTES, rc.AEDUI, rc.WARBAND, 4)
    place_piece(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA, 3)
    result, _ = event(state, actor)
    assert not result['ambush']
    # 4 Warbands + Diviciacus cause 3 Losses, without becoming Ambiorix.
    assert count_pieces(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA) == 0
    assert get_leader_in_region(state, rc.CARNUTES, rc.AEDUI) == rc.DIVICIACUS
    assert validate_state(state) == []


@pytest.mark.parametrize('seed', range(1, 6))
@pytest.mark.parametrize('valuable_owner', [rc.BELGAE, rc.AEDUI])
@pytest.mark.parametrize('region,valuable,ordinary', [
    (rc.MANDUBII, rc.TRIBE_MANDUBII, rc.TRIBE_SENONES),
    (rc.ATREBATES, rc.TRIBE_REMI, rc.TRIBE_BELLOVACI),
])
def test_np_combined_losses_preserve_city_and_remi_allies_across_owners(
        seed, valuable_owner, region, valuable, ordinary):
    from fs_bot.battle.combined import litaviccus_force
    from fs_bot.battle.losses import resolve_losses
    state = board(seed=seed)
    state['non_player_factions'] = {rc.BELGAE}
    ordinary_owner = rc.AEDUI if valuable_owner == rc.BELGAE else rc.BELGAE
    for owner, tribe in ((valuable_owner, valuable), (ordinary_owner, ordinary)):
        place_piece(state, region, owner, rc.ALLY)
        state['tribes'][tribe]['allied_faction'] = owner
    with litaviccus_force(state, rc.BELGAE, region):
        resolve_losses(state, region, rc.BELGAE, 1)
    assert state['tribes'][valuable]['allied_faction'] == valuable_owner
    assert state['tribes'][ordinary]['allied_faction'] is None
    assert count_pieces(state, region, valuable_owner, rc.ALLY) == 1
    assert count_pieces(state, region, ordinary_owner, rc.ALLY) == 0
    assert validate_state(state) == []


def test_np_combined_loss_clears_ordinary_tribe_when_owner_has_both_tiers():
    from fs_bot.battle.combined import litaviccus_force
    from fs_bot.battle.losses import resolve_losses
    state = board()
    state['non_player_factions'] = {rc.BELGAE}
    place_piece(state, rc.MANDUBII, rc.AEDUI, rc.ALLY, 2)
    state['tribes'][rc.TRIBE_MANDUBII]['allied_faction'] = rc.AEDUI
    state['tribes'][rc.TRIBE_SENONES]['allied_faction'] = rc.AEDUI
    with litaviccus_force(state, rc.BELGAE, rc.MANDUBII):
        resolve_losses(state, rc.MANDUBII, rc.BELGAE, 1)
    assert state['tribes'][rc.TRIBE_MANDUBII]['allied_faction'] == rc.AEDUI
    assert state['tribes'][rc.TRIBE_SENONES]['allied_faction'] is None
    assert validate_state(state) == []
