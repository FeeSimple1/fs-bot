"""A65's printed participants, scope, complete Battle and human choices."""
from copy import deepcopy
from io import StringIO

import pytest

from fs_bot import rules_consts as rc
from fs_bot.battle.excluded_leader import EXCLUDED_LEADER_KEY, without_attacker_leader
from fs_bot.board.control import calculate_control
from fs_bot.board.pieces import place_piece, count_pieces, get_leader_in_region
from fs_bot.bots.bot_common import should_decline_event
from fs_bot.cards.event_conditions import np_event_available
from fs_bot.cards.kinship import default_plan, legal_regions, resolve_kinship, validate_response
from fs_bot.cli.display import _physical_piece_view, _active_force_context
from fs_bot.cli.reactive import make_cli_reactive
from fs_bot.engine.execute import _execute_event
from fs_bot.state.serialize import encode
from fs_bot.state.state_schema import build_initial_state, validate_state


def state():
    st = build_initial_state(rc.SCENARIO_ARIOVISTUS, seed=65)
    st['current_card'] = st['current_card_id'] = 'A65'
    st['non_player_factions'] = set()
    st['event_params'] = st['executing_faction'] = None
    return st


def opposing(st, region=rc.MORINI, attacker=rc.BELGAE, own=6, enemy=4):
    target = rc.GERMANS if attacker == rc.BELGAE else rc.BELGAE
    place_piece(st, region, attacker, rc.WARBAND, own)
    place_piece(st, region, target, rc.WARBAND, enemy)
    return target


def event(st, chooser=rc.AEDUI):
    return _execute_event(st, chooser, {'command': 'Event', 'sa': 'No SA',
        'details': {'card_id': 'A65', 'text_preference': rc.EVENT_UNSHADED}}, human=True)


@pytest.mark.parametrize('chooser', [rc.ROMANS, rc.AEDUI, rc.BELGAE, rc.GERMANS])
@pytest.mark.parametrize('attacker', [rc.BELGAE, rc.GERMANS])
def test_human_executor_selects_either_side_in_all_selected_regions(chooser, attacker):
    st = state()
    regions = [rc.NERVII, rc.MORINI, rc.TREVERI]
    for region in regions:
        target = opposing(st, region, attacker, enemy=1)
    requests = []
    def agent(board, faction, request):
        if request['kind'] == 'kinship':
            requests.append((faction, deepcopy(request)))
            return {'faction': attacker, 'regions': regions}
        if request['kind'] == 'retreat':
            return {'retreat': False, 'region': None}
        return None
    st['decision_agent'] = agent
    treasury = dict(st['resources'])
    result = event(st, chooser)
    assert result['executed']
    battle = result['free_actions'][0]
    assert battle['chooser'] == chooser and battle['faction'] == attacker
    assert battle['result']['count'] == 3 and not battle['result']['errors']
    assert requests[0][0] == chooser
    assert all(count_pieces(st, r, target, rc.WARBAND) == 0 for r in regions)
    assert st['resources'] == treasury
    assert EXCLUDED_LEADER_KEY not in st and validate_state(st) == []


@pytest.mark.parametrize('attacker,leader', [(rc.BELGAE, rc.BODUOGNATUS),
                                           (rc.GERMANS, rc.ARIOVISTUS_LEADER)])
def test_excluded_leader_stays_physical_and_cannot_absorb_counterattack(attacker, leader):
    st = state()
    target = opposing(st, attacker=attacker, own=1, enemy=8)
    place_piece(st, rc.MORINI, attacker, rc.LEADER, leader_name=leader)
    losses = []
    def agent(board, faction, request):
        if request['kind'] == 'kinship':
            return {'faction': attacker, 'regions': [rc.MORINI]}
        if request['kind'] == 'retreat':
            return {'retreat': False, 'region': None}
        if request['kind'] == 'loss_order' and faction == attacker:
            losses.append(request)
            assert all(piece[0] != rc.LEADER for piece in request['pieces'])
            assert get_leader_in_region(board, rc.MORINI, attacker) is None
            physical = _physical_piece_view(board)
            assert get_leader_in_region(physical, rc.MORINI, attacker) == leader
            assert calculate_control(board, rc.MORINI) == calculate_control(physical, rc.MORINI)
            assert any('remains on the board' in line for line in _active_force_context(board))
        return None
    st['decision_agent'] = agent
    assert event(st)['executed']
    assert losses and count_pieces(st, rc.MORINI, attacker, rc.WARBAND) == 0
    assert count_pieces(st, rc.MORINI, target, rc.WARBAND) == 8  # 1 Warband causes 0 Losses
    assert get_leader_in_region(st, rc.MORINI, attacker) == leader
    assert EXCLUDED_LEADER_KEY not in st and validate_state(st) == []


def test_one_command_applies_germanic_horse_only_once_and_never_grants_ambush():
    from fs_bot.cards.capabilities import activate_capability, set_capability_owner
    st = state()
    for region in (rc.MORINI, rc.NERVII):
        opposing(st, region, own=4, enemy=6)
    activate_capability(st, 59, rc.EVENT_SHADED)
    set_capability_owner(st, 59, rc.BELGAE)
    st['decision_agent'] = lambda _st, _f, req: (
        {'faction': rc.BELGAE, 'regions': [rc.NERVII, rc.MORINI]} if req['kind'] == 'kinship'
        else {'retreat': False, 'region': None} if req['kind'] == 'retreat' else None)
    result = event(st)
    assert result['executed'] and result['free_actions'][0]['result']['count'] == 2
    assert not result['free_actions'][0]['result']['battle_sa_executed']
    assert sorted(count_pieces(st, r, rc.GERMANS, rc.WARBAND) for r in (rc.MORINI, rc.NERVII)) == [2, 4]


@pytest.mark.parametrize('response', [
    {'faction': rc.ROMANS, 'regions': [rc.MORINI]},
    {'faction': rc.BELGAE, 'regions': [rc.MORINI, rc.MORINI]},
    {'faction': rc.BELGAE, 'regions': [rc.MORINI, rc.NERVII]},
    {'faction': rc.BELGAE, 'regions': [rc.BRITANNIA]},
    {'faction': rc.BELGAE, 'regions': [rc.MORINI], 'sa': rc.SA_AMBUSH},
    {'faction': rc.BELGAE, 'regions': []},
])
def test_invalid_whole_plan_rejected_before_board_or_rng_changes(response):
    st = state(); opposing(st)
    before = encode(st)
    assert validate_response(st, response)
    assert encode(st) == before
    st['decision_agent'] = lambda _s, _f, _r: response
    assert not event(st)['executed']
    assert encode({k:v for k,v in st.items() if k != 'decision_agent'}) == before


@pytest.mark.parametrize('faction', [rc.AEDUI, rc.ROMANS])
def test_nonplayer_cannot_choose_the_other_factions_benefit(faction):
    st = state(); opposing(st, own=10)
    st['non_player_factions'] = {faction}
    st['decision_agent'] = lambda *_: pytest.fail('Availability must not ask a human')
    before = encode({k:v for k,v in st.items() if k != 'decision_agent'})
    assert np_event_available(st, 'A65', faction, False) is False
    assert should_decline_event(st, 'A65', faction)
    assert encode({k:v for k,v in st.items() if k != 'decision_agent'}) == before


@pytest.mark.parametrize('faction,other', [(rc.BELGAE, rc.GERMANS), (rc.GERMANS, rc.BELGAE)])
def test_printed_opponent_nonplayer_condition_applies_to_shaded_selection(faction, other):
    st = state(); opposing(st)
    st['non_player_factions'] = {faction, other}
    assert should_decline_event(st, 'A65', faction)


@pytest.mark.parametrize('attacker', [rc.BELGAE, rc.GERMANS])
def test_default_applies_actual_flowchart_only_against_printed_enemy(attacker):
    st = state()
    st['non_player_factions'] = {attacker}
    for region in (rc.MORINI, rc.NERVII):
        opposing(st, region, attacker, own=10, enemy=4)
        place_piece(st, region, rc.ROMANS, rc.AUXILIA, 1)
    plan = default_plan(st, attacker)
    assert plan and plan['faction'] == attacker and set(plan['regions']) == {rc.MORINI, rc.NERVII}
    result = resolve_kinship(st, attacker)
    assert result[0]['result']['count'] == 2
    assert all(count_pieces(st, r, rc.ROMANS, rc.AUXILIA) == 1 for r in (rc.MORINI, rc.NERVII))


def test_leader_only_force_never_qualifies_and_scope_restores_on_interruption():
    st = state()
    place_piece(st, rc.MORINI, rc.BELGAE, rc.LEADER, leader_name=rc.BODUOGNATUS)
    place_piece(st, rc.MORINI, rc.GERMANS, rc.WARBAND, 4)
    assert not legal_regions(st, rc.BELGAE)
    before = encode(st)
    with pytest.raises(EOFError):
        with without_attacker_leader(st, rc.BELGAE, [rc.MORINI]):
            raise EOFError()
    assert encode(st) == before


@pytest.mark.parametrize('attacker,leader', [(rc.BELGAE, rc.BODUOGNATUS),
                                           (rc.GERMANS, rc.ARIOVISTUS_LEADER)])
def test_physical_leader_satisfies_trigger_but_cannot_supply_battle_strength(attacker, leader):
    st = state()
    target = opposing(st, attacker=attacker, own=3, enemy=1)
    place_piece(st, rc.MORINI, attacker, rc.LEADER, leader_name=leader)
    # An enemy Ally triggers the diamond, even with fewer than four/six
    # attacking Warbands. The Leader remains in the Region but does not fight.
    place_piece(st, rc.MORINI, target, rc.ALLY)
    st['non_player_factions'] = {attacker}
    assert default_plan(st, attacker) == {'faction': attacker, 'regions': [rc.MORINI]}
    from fs_bot.battle.resolve import _calculate_attack_losses
    with without_attacker_leader(st, attacker, [rc.MORINI]):
        assert _calculate_attack_losses(st, rc.MORINI, attacker, target,
            is_retreat=False, had_citadel_at_start=False, had_fort_at_start=False) == 1


def test_leader_still_decides_physical_control_while_excluded():
    st = state(); opposing(st, own=2, enemy=2)
    place_piece(st, rc.MORINI, rc.BELGAE, rc.LEADER, leader_name=rc.BODUOGNATUS)
    with without_attacker_leader(st, rc.BELGAE, [rc.MORINI]):
        assert count_pieces(st, rc.MORINI, rc.BELGAE) == 2
        assert calculate_control(st, rc.MORINI) == rc.BELGIC_CONTROL
        assert count_pieces(_physical_piece_view(st), rc.MORINI, rc.BELGAE) == 3


def test_cli_can_choose_enemy_faction_and_multiple_regions_without_mutation():
    st = state()
    opposing(st, rc.MORINI); opposing(st, rc.NERVII)
    before = encode(st)
    agent = make_cli_reactive([rc.AEDUI], StringIO(
        f'Choose the attacker and Regions\n{rc.GERMANS}\n{rc.NERVII}\n{rc.MORINI}\n'), StringIO())
    st['decision_agent'] = agent
    assert resolve_kinship(st, rc.AEDUI)[0]['result']['count'] == 2
    assert before != encode({k:v for k,v in st.items() if k != 'decision_agent'})


@pytest.mark.parametrize('scenario', list(rc.BASE_SCENARIOS))
def test_expansion_event_has_no_base_regions(scenario):
    st = build_initial_state(scenario, seed=65)
    opposing(st)
    assert legal_regions(st, rc.BELGAE) == []
