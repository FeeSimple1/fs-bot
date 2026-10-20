"""A34: the selected non-German player commands German pieces, at most 3 Regions."""
from copy import deepcopy
from io import StringIO

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import place_piece, count_pieces, count_pieces_by_state
from fs_bot.board.control import refresh_all_control
from fs_bot.cli.free_actions import collect_free_action
from fs_bot.engine.execute import execute_decision
from fs_bot.engine.free_actions import validate_free_action_response
from fs_bot.state.state_schema import build_initial_state, validate_state
from fs_bot.state.serialize import encode


def state():
    st = build_initial_state(rc.SCENARIO_ARIOVISTUS, seed=5)
    st['current_card'] = 'A34'
    st['non_player_factions'] = set()
    return st


def action(command, details):
    return {'command': command, 'sa': 'No SA', 'sa_regions': [],
            'regions': [], 'details': details}


def march(routes):
    return action('March', {'origins': list(routes),
                           'destinations': [route[-1] for route in routes.values()],
                           'routes': routes})


def battle(regions, target=rc.ROMANS):
    return action('Battle', {'battle_plan': [{'region': r, 'target': target} for r in regions]})


def event(st, executor, *, beneficiary=None, shaded=False):
    details = {'card_id': 'A34', 'text_preference': rc.EVENT_SHADED if shaded else rc.EVENT_UNSHADED}
    if beneficiary is not None:
        details['event_params'] = {'faction': beneficiary}
    return execute_decision(st, executor, {'player_action': {
        'command': 'Event', 'sa': 'No SA', 'details': details}})


def choose(st, selected, beneficiary):
    requests = []
    def agent(board, faction, request):
        if request['kind'] != 'free_action':
            return None
        requests.append((faction, request))
        assert faction == beneficiary
        assert request['acting_faction'] == rc.GERMANS
        return deepcopy(selected)
    st['decision_agent'] = agent
    return requests


@pytest.mark.parametrize('chooser', [rc.ROMANS, rc.AEDUI, rc.BELGAE])
def test_non_german_chooser_can_march_three_german_origins(chooser):
    st = state()
    routes = {rc.SUGAMBRI: [rc.MORINI], rc.UBII: [rc.SEQUANI], rc.TREVERI: [rc.MANDUBII]}
    for origin in routes:
        place_piece(st, origin, rc.GERMANS, rc.WARBAND, 2, piece_state=rc.REVEALED)
    pools = deepcopy(st['available'])
    requests = choose(st, march(routes), chooser)
    result = event(st, chooser)
    assert result['executed'] and requests
    report = result['free_actions'][0]
    assert report['result']['command'] == 'March'
    assert len(report['result']['marches']) == 3
    for origin, route in routes.items():
        assert count_pieces(st, origin, rc.GERMANS, rc.WARBAND) == 0
        assert count_pieces_by_state(st, route[0], rc.GERMANS, rc.WARBAND, rc.HIDDEN) == 2
        assert count_pieces(st, route[0], chooser, rc.WARBAND) == 0
    assert st['available'] == pools
    assert st['resources'][rc.GERMANS] == 0
    assert validate_state(st) == []
    assert not any(k.startswith('card_A34') for k in st['event_modifiers'])


def test_german_event_executor_can_select_a_non_german_beneficiary():
    st = state()
    place_piece(st, rc.SUGAMBRI, rc.GERMANS, rc.WARBAND, 2)
    requests = choose(st, march({rc.SUGAMBRI: [rc.NERVII]}), rc.AEDUI)
    result = event(st, rc.GERMANS, beneficiary=rc.AEDUI)
    assert result['executed'] and requests[0][0] == rc.AEDUI
    assert count_pieces(st, rc.NERVII, rc.GERMANS, rc.WARBAND) == 2


def test_battle_uses_all_german_pieces_without_enlist_four_piece_limit():
    st = state()
    for region in (rc.SUGAMBRI, rc.UBII, rc.TREVERI):
        place_piece(st, region, rc.GERMANS, rc.WARBAND, 6)
        place_piece(st, region, rc.ROMANS, rc.AUXILIA, 2)
    choose(st, battle([rc.SUGAMBRI, rc.UBII, rc.TREVERI]), rc.BELGAE)
    result = event(st, rc.BELGAE)
    assert result['executed']
    assert len(result['free_actions'][0]['result']['battles_resolved']) == 3
    assert st['resources'][rc.GERMANS] == 0
    assert sum(count_pieces(st, r, rc.ROMANS, rc.AUXILIA)
               for r in (rc.SUGAMBRI, rc.UBII, rc.TREVERI)) == 0
    assert validate_state(st) == []


@pytest.mark.parametrize('invalid', ['four_regions', 'two_steps', 'rally', 'special_ability', 'repeat_battle'])
def test_invalid_divination_is_atomic(invalid):
    st = state()
    regions = [rc.SUGAMBRI, rc.UBII, rc.TREVERI, rc.NERVII]
    for region in regions:
        place_piece(st, region, rc.GERMANS, rc.WARBAND, 2)
        place_piece(st, region, rc.ROMANS, rc.AUXILIA, 1)
    plans = {
        'four_regions': battle(regions),
        'two_steps': march({rc.SUGAMBRI: [rc.TREVERI, rc.MANDUBII]}),
        'rally': action('Rally', {'rally_plan': {'warbands': [rc.SUGAMBRI]}}),
        'special_ability': dict(battle([rc.SUGAMBRI]), sa='Intimidate'),
        'repeat_battle': battle([rc.SUGAMBRI, rc.SUGAMBRI]),
    }
    choose(st, plans[invalid], rc.AEDUI)
    before = encode({k: v for k, v in st.items() if k != 'decision_agent'})
    result = event(st, rc.AEDUI)
    assert not result['executed']
    assert encode({k: v for k, v in st.items() if k != 'decision_agent'}) == before


@pytest.mark.parametrize('beneficiary', [rc.GERMANS, rc.ARVERNI])
def test_unshaded_rejects_ineligible_beneficiary(beneficiary):
    st = state()
    before = encode(st)
    assert not event(st, rc.ROMANS, beneficiary=beneficiary)['executed']
    assert encode(st) == before


def test_divination_can_be_declined_without_moving():
    st = state()
    place_piece(st, rc.SUGAMBRI, rc.GERMANS, rc.WARBAND, 2)
    choose(st, {'decline': True}, rc.AEDUI)
    result = event(st, rc.AEDUI)
    assert result['executed']
    assert not result['free_actions'][0]['result']['executed']
    assert count_pieces(st, rc.SUGAMBRI, rc.GERMANS, rc.WARBAND) == 2


def test_terminal_collects_german_not_choosers_march_force():
    st = state()
    place_piece(st, rc.SUGAMBRI, rc.GERMANS, rc.WARBAND, 2)
    place_piece(st, rc.MORINI, rc.AEDUI, rc.WARBAND, 3)
    request = {'kind': 'free_action', 'request_type': 'event_command',
               'acting_faction': rc.GERMANS, 'allowed_commands': ['March', 'Battle'],
               'max_regions': 3, 'with_sa': False, 'free': True}
    out = StringIO()
    plan = collect_free_action(st, rc.AEDUI, request, StringIO('\n'.join([
        'Plan the action', 'March', rc.SUGAMBRI, rc.NERVII, 'all 2']) + '\n'), out)
    assert plan['details']['origins'] == [rc.SUGAMBRI]
    assert f'{rc.AEDUI}: choose a free action using {rc.GERMANS} pieces' in out.getvalue()
    assert not validate_free_action_response(st, rc.AEDUI, request, plan)


@pytest.mark.parametrize('beneficiary', [rc.GERMANS, rc.BELGAE])
def test_shaded_executor_can_grant_command_and_eligibility_to_allowed_faction(beneficiary):
    st = state()
    st['eligibility'][beneficiary] = rc.INELIGIBLE
    place_piece(st, rc.SUGAMBRI, beneficiary, rc.WARBAND, 2)
    asked = []
    def agent(board, faction, request):
        if request['kind'] != 'free_action':
            return None
        asked.append(faction)
        assert faction == beneficiary
        return march({rc.SUGAMBRI: [rc.NERVII]})
    st['decision_agent'] = agent
    result = event(st, rc.ROMANS, beneficiary=beneficiary, shaded=True)
    assert result['executed'] and asked == [beneficiary]
    assert result['free_actions'][0]['result']['executed']
    assert st['eligibility'][beneficiary] == rc.ELIGIBLE
    assert count_pieces(st, rc.NERVII, beneficiary, rc.WARBAND) == 2
    assert st['resources'][beneficiary] == 0
    assert not any(k.startswith('card_A34') for k in st['event_modifiers'])


def test_shaded_rejects_aedui_beneficiary_atomically():
    st = state()
    before = encode(st)
    assert not event(st, rc.ROMANS, beneficiary=rc.AEDUI, shaded=True)['executed']
    assert encode(st) == before


@pytest.mark.parametrize('shaded,beneficiary', [(False, rc.AEDUI), (True, rc.BELGAE)])
def test_terminal_event_params_choose_legal_divination_beneficiary(shaded, beneficiary):
    from fs_bot.cli.human_plan import _collect_event_params
    st = state()
    out = StringIO()
    params = _collect_event_params(st, rc.GERMANS, 'A34', shaded,
                                   StringIO(beneficiary + '\n'), out)
    assert params == {'faction': beneficiary}
    assert rc.ARVERNI not in out.getvalue()
    if not shaded:
        assert rc.GERMANS not in out.getvalue()
    else:
        assert rc.ROMANS not in out.getvalue() and rc.AEDUI not in out.getvalue()


def test_divination_free_march_ignores_frost_but_retains_german_distance():
    st = state()
    st['next_card'] = rc.WINTER_CARD
    place_piece(st, rc.SUGAMBRI, rc.GERMANS, rc.WARBAND, 2)
    choose(st, march({rc.SUGAMBRI: [rc.NERVII]}), rc.ROMANS)
    assert event(st, rc.ROMANS)['executed']
    assert count_pieces(st, rc.NERVII, rc.GERMANS, rc.WARBAND) == 2


def test_response_cannot_change_trusted_german_actor():
    st = state()
    place_piece(st, rc.SUGAMBRI, rc.ROMANS, rc.AUXILIA, 2)
    selected = march({rc.SUGAMBRI: [rc.NERVII]})
    selected['acting_faction'] = rc.ROMANS
    choose(st, selected, rc.AEDUI)
    before = encode({k: v for k, v in st.items() if k != 'decision_agent'})
    assert not event(st, rc.AEDUI)['executed']
    assert encode({k: v for k, v in st.items() if k != 'decision_agent'}) == before


@pytest.mark.parametrize('beneficiary', [rc.GERMANS, rc.BELGAE])
def test_shaded_self_beneficiary_stays_eligible_after_card_reset(beneficiary):
    from fs_bot.engine.game_engine import adjust_eligibility, ACTION_EVENT
    st = state()
    place_piece(st, rc.SUGAMBRI, beneficiary, rc.WARBAND, 2)
    st['decision_agent'] = lambda board, faction, request: (
        march({rc.SUGAMBRI: [rc.NERVII]})
        if request['kind'] == 'free_action' else None)
    assert event(st, beneficiary, shaded=True)['executed']
    adjust_eligibility(st, {beneficiary: {'action': ACTION_EVENT}})
    assert st['eligibility'][beneficiary] == rc.ELIGIBLE
    assert 'stay_eligible' not in st


def test_implicit_leader_origin_cannot_bypass_three_region_grant():
    st = state()
    origins = [rc.SUGAMBRI, rc.UBII, rc.TREVERI]
    for origin in origins:
        place_piece(st, origin, rc.GERMANS, rc.WARBAND, 3)
    place_piece(st, rc.MANDUBII, rc.GERMANS, rc.LEADER,
                leader_name=rc.ARIOVISTUS_LEADER)
    selected = action('March', {'march_plan': {
        'origins': origins,
        'control_destinations': [rc.MORINI, rc.SEQUANI, rc.ATREBATES],
        'leader_destination': rc.SEQUANI}})
    choose(st, selected, rc.BELGAE)
    before = encode({k: v for k, v in st.items() if k != 'decision_agent'})
    assert not event(st, rc.BELGAE)['executed']
    assert encode({k: v for k, v in st.items() if k != 'decision_agent'}) == before


@pytest.mark.parametrize('beneficiary', [rc.ROMANS, rc.AEDUI])
def test_gifted_np_action_executes_despite_no_event_selection_directive(beneficiary):
    st = state()
    st['non_player_factions'] = {beneficiary}
    place_piece(st, rc.SUGAMBRI, rc.GERMANS, rc.WARBAND, 4)
    place_piece(st, rc.NERVII, rc.BELGAE, rc.ALLY)
    st['tribes'][rc.TRIBE_NERVII]['allied_faction'] = rc.BELGAE
    refresh_all_control(st)
    pools = deepcopy(st['available'])
    result = event(st, rc.GERMANS, beneficiary=beneficiary)
    assert result['executed'], result
    outcome = result['free_actions'][0]['result']
    assert outcome['executed'] and outcome['command'] == 'March', outcome
    assert count_pieces(st, rc.SUGAMBRI, rc.GERMANS, rc.WARBAND) < 4
    assert sum(count_pieces(st, region, rc.GERMANS, rc.WARBAND)
               for region in st['spaces']) == 4
    assert st['available'] == pools
    assert st['resources'][rc.GERMANS] == 0
    assert not any(k.startswith('card_A34') for k in st['event_modifiers'])
    assert validate_state(st) == []
