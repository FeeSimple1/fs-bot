"""Card Reference 47, §§1.5/2.2/2.3.5/5.1/5.4/8.2.3 and A1.5/A2.3.2."""
import copy

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces, place_piece
from fs_bot.cards.council import (
    choice_request, eligible_regions, faction_order, private_cards,
    resolve_council, validate_choice, validate_selection,
)
from fs_bot.bots.bot_common import should_decline_event
from fs_bot.cards.param_schema import card_param_schema, region_pool
from fs_bot.engine.execute import _derive_event_params, _execute_event
from fs_bot.engine.game_engine import adjust_eligibility, get_sop_factions
from fs_bot.state.serialize import encode
from fs_bot.state.state_schema import build_initial_state


def _state(scenario=rc.SCENARIO_GREAT_REVOLT, seed=47):
    state = build_initial_state(scenario, seed=seed)
    state['current_card'] = state['current_card_id'] = 47
    state['deck'], state['next_card'] = [1, 35, 62, 3], 1
    state['non_player_factions'] = set()
    state['resources'][rc.AEDUI] = state['resources'][rc.ROMANS] = 0
    place_piece(state, rc.SEQUANI, rc.AEDUI, rc.WARBAND, 1)
    place_piece(state, rc.SEQUANI, rc.ROMANS, rc.AUXILIA, 1)
    return state


def _selection(region=rc.SEQUANI, targets=None):
    return {'region': region, 'target_factions': targets or [rc.ROMANS, rc.AEDUI]}


def _event(state, selection):
    return _execute_event(state, rc.BELGAE, {'command': 'Event', 'details': {
        'card_id': 47, 'text_preference': rc.EVENT_UNSHADED,
        'event_params': selection}}, human=True)


def _march(origin, destination):
    return {'command': rc.CMD_MARCH, 'regions': [origin], 'sa': 'No SA',
            'sa_regions': [], 'details': {'march_plan': {
                'origins': [origin], 'destinations': [destination],
                'routes': {origin: [destination]},
                'groups': {origin: {rc.WARBAND: 1, rc.LEADER: False}}}}}


@pytest.mark.parametrize('scenario', tuple(rc.BASE_SCENARIOS) + tuple(rc.ARIOVISTUS_SCENARIOS))
def test_every_np_declines_selecting_council_in_each_scenario(scenario):
    state = _state(scenario)
    state['non_player_factions'] = set(get_sop_factions(state))
    for faction in get_sop_factions(state):
        assert should_decline_event(state, 47, faction)
        assert _derive_event_params(state, faction, 47, False) is None


def test_executor_selects_region_and_subset_and_beneficiaries_act_in_printed_order():
    state = _state()
    # The old heuristic selected the most crowded Region. The executor may
    # choose Sequani with fewer factions and need not invite every faction.
    place_piece(state, rc.SEQUANI, rc.BELGAE, rc.WARBAND, 1)
    for faction in (rc.ARVERNI, rc.AEDUI, rc.BELGAE):
        place_piece(state, rc.AEDUI_REGION, faction, rc.WARBAND, 1)
    place_piece(state, rc.AEDUI_REGION, rc.ROMANS, rc.AUXILIA, 1)
    state['non_player_factions'] = {rc.AEDUI}
    calls = []
    def agent(board, faction, request):
        calls.append((faction, request['region']))
        return {'choice': 'eligible'}
    state['decision_agent'] = agent
    result = _event(state, _selection())
    assert result['executed']
    assert calls == [(rc.AEDUI, rc.SEQUANI), (rc.ROMANS, rc.SEQUANI)]
    assert [entry['faction'] for entry in result['free_actions']] == [rc.AEDUI, rc.ROMANS]
    assert rc.BELGAE not in state.get('stay_eligible', [])


def test_germans_do_not_qualify_region_but_can_be_ariovistus_beneficiary():
    state = build_initial_state(rc.SCENARIO_ARIOVISTUS, seed=47)
    state['deck'] = [1, 'A34', 'A65']
    place_piece(state, rc.SEQUANI, rc.ROMANS, rc.AUXILIA, 1)
    place_piece(state, rc.SEQUANI, rc.GERMANS, rc.WARBAND, 1)
    assert rc.SEQUANI not in eligible_regions(state)
    place_piece(state, rc.SEQUANI, rc.ARVERNI, rc.WARBAND, 1)
    assert eligible_regions(state)[rc.SEQUANI] == [rc.GERMANS, rc.ROMANS]
    assert faction_order(state) == (rc.AEDUI, rc.GERMANS, rc.BELGAE, rc.ROMANS)
    calls = []
    state['decision_agent'] = lambda board, faction, request: (
        calls.append(faction) or {'choice': 'eligible'})
    resolve_council(state, rc.ROMANS, _selection(targets=[rc.ROMANS, rc.GERMANS]))
    assert calls == [rc.GERMANS, rc.ROMANS]
    assert rc.ARVERNI not in state.get('stay_eligible', [])
    with pytest.raises(ValueError):
        validate_selection(state, _selection(targets=[rc.ROMANS, rc.ARVERNI]))


@pytest.mark.parametrize('deck,expected', [
    ([], []), ([1], []), ([1, 35], [35]),
    ([1, rc.WINTER_CARD, 35, 62], [rc.WINTER_CARD, 35]),
    ([rc.WINTER_CARD, 35, 62], [35, 62]),
])
def test_peek_only_available_facedown_cards_including_winter_without_draw_or_rng(deck, expected):
    state = _state()
    state['deck'] = deck
    before = encode(state)
    cards = private_cards(state)
    assert [card['card_id'] for card in cards] == expected
    assert encode(state) == before


def test_base_game_germans_never_receive_council_benefit():
    state = _state()
    place_piece(state, rc.SEQUANI, rc.GERMANS, rc.WARBAND, 1)
    assert eligible_regions(state)[rc.SEQUANI] == [rc.AEDUI, rc.ROMANS]
    with pytest.raises(ValueError):
        validate_selection(state, _selection(targets=[rc.ROMANS, rc.GERMANS]))


def test_only_leader_or_static_piece_also_counts_as_faction_present():
    state = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=47)
    place_piece(state, rc.SEQUANI, rc.ROMANS, rc.LEADER, leader_name=rc.CAESAR)
    place_piece(state, rc.SEQUANI, rc.BELGAE, rc.LEADER, leader_name=rc.AMBIORIX)
    assert eligible_regions(state)[rc.SEQUANI] == [rc.BELGAE, rc.ROMANS]


def test_frozen_guests_still_act_after_first_command_removes_presence():
    state = _state()
    calls = []
    def agent(board, faction, request):
        calls.append(faction)
        return _march(rc.SEQUANI, rc.AEDUI_REGION) if faction == rc.AEDUI else {'decline': True}
    state['decision_agent'] = agent
    result = resolve_council(state, rc.BELGAE, _selection())
    assert result[0]['result']['executed']
    assert calls == [rc.AEDUI, rc.ROMANS]
    assert not count_pieces(state, rc.SEQUANI, rc.AEDUI)
    assert state['resources'][rc.AEDUI] == 0


def test_command_anywhere_free_during_frost_and_decline_does_not_grant_eligibility():
    state = _state()
    state['next_card'] = rc.WINTER_CARD
    state['deck'] = [rc.WINTER_CARD, 35, 62]
    place_piece(state, rc.PROVINCIA, rc.AEDUI, rc.WARBAND, 1)
    state['eligibility'][rc.AEDUI] = state['eligibility'][rc.ROMANS] = rc.INELIGIBLE
    state['decision_agent'] = lambda board, faction, request: (
        _march(rc.PROVINCIA, rc.AEDUI_REGION) if faction == rc.AEDUI else {'decline': True})
    result = resolve_council(state, rc.BELGAE, _selection())
    assert result[0]['result']['executed']
    assert not count_pieces(state, rc.PROVINCIA, rc.AEDUI)
    assert state['resources'][rc.AEDUI] == 0
    assert state['eligibility'][rc.AEDUI] == state['eligibility'][rc.ROMANS] == rc.INELIGIBLE
    assert not state.get('stay_eligible')


def test_eligible_overrides_prior_event_and_survives_executor_and_prior_actor_adjustment():
    state = _state()
    state['forced_ineligible'] = {rc.AEDUI: 2, rc.ROMANS: 2, rc.BELGAE: 2}
    state['decision_agent'] = lambda *args: {'choice': 'eligible'}
    resolve_council(state, rc.ROMANS, _selection())
    assert state['forced_ineligible'] == {rc.BELGAE: 2}
    adjust_eligibility(state, {rc.AEDUI: {'action': 'command'}, rc.ROMANS: {'action': 'event'}})
    assert state['eligibility'][rc.AEDUI] == state['eligibility'][rc.ROMANS] == rc.ELIGIBLE
    assert state['eligibility'][rc.BELGAE] == rc.INELIGIBLE


@pytest.mark.parametrize('response', [
    {'command': rc.CMD_RALLY, 'regions': [rc.SEQUANI, rc.PROVINCIA],
     'sa': 'No SA', 'details': {}},
    {'command': rc.CMD_RALLY, 'regions': [rc.SEQUANI], 'sa': rc.SA_SUBORN,
     'sa_regions': [rc.SEQUANI], 'details': {}},
    {'choice': 'eligible', 'command': rc.CMD_RALLY},
])
def test_council_rejects_extra_regions_sa_or_combined_benefit_without_mutation(response):
    state = _state()
    before = encode(state)
    with pytest.raises(ValueError):
        validate_choice(state, rc.AEDUI, response)
    assert encode(state) == before


def test_invalid_second_benefit_rolls_back_first_and_rng():
    state = _state()
    before = encode(state)
    state['decision_agent'] = lambda board, faction, request: (
        {'choice': 'eligible'} if faction == rc.AEDUI else {'choice': 'invalid'})
    with pytest.raises(ValueError):
        resolve_council(state, rc.BELGAE, _selection())
    assert encode({k: v for k, v in state.items() if k != 'decision_agent'}) == before


@pytest.mark.parametrize('selection', [
    {'region': rc.SEQUANI},
    _selection(targets=[rc.AEDUI]),
    _selection(targets=[rc.AEDUI, rc.AEDUI]),
    _selection(targets=[rc.AEDUI, rc.ARVERNI]),
    _selection(region=rc.PROVINCIA),
])
def test_invalid_explicit_selection_rejects_before_peek(selection):
    state = _state()
    state['decision_agent'] = lambda *args: pytest.fail('Invalid selection exposed a beneficiary request')
    before = encode({k: v for k, v in state.items() if k != 'decision_agent'})
    result = _event(state, selection)
    assert not result['executed']
    # Event execution normalizes its two transient caller fields on rejection.
    state.pop('event_params', None)
    state.pop('executing_faction', None)
    assert encode({k: v for k, v in state.items() if k != 'decision_agent'}) == before


def test_default_modes_are_seeded_and_command_does_not_reprompt_or_auto_choose_eligible():
    state = _state(seed=0)
    state['non_player_factions'] = {rc.AEDUI, rc.ROMANS}
    requests = []
    def agent(board, faction, request):
        requests.append(request['kind'])
        return {'use_default': True}
    state['decision_agent'] = agent
    before = copy.deepcopy({k: v for k, v in state.items() if k != 'decision_agent'})
    result = resolve_council(state, rc.BELGAE, _selection())
    assert requests == ['council_choice', 'council_choice']
    assert result[0]['free_action'] == 'free_command'  # Random(0) chooses Command.
    assert rc.AEDUI not in state.get('stay_eligible', [])
    assert state['resources'][rc.AEDUI] == 0
    repeat = resolve_council(before, rc.BELGAE, _selection())
    assert result == repeat
    assert state['rng'].getstate() == before['rng'].getstate()


def test_schema_exposes_only_public_executor_choices_and_state_legal_regions():
    state = _state()
    schema = card_param_schema(47, state['scenario'])
    assert set(schema) == {'region', 'target_factions'}
    assert region_pool(state, schema['region']['region_pool']) == [rc.SEQUANI]
    request = choice_request(state, rc.AEDUI, _selection())
    assert request['allowed_regions'] is None
    assert request['max_regions'] == 1 and not request['with_sa']


def test_private_base_card_in_ariovistus_has_actual_seat_order_and_np_symbols():
    state = _state(rc.SCENARIO_ARIOVISTUS)
    state['deck'] = [1, 47, 'A5']
    council, expansion = private_cards(state)
    assert council['faction_order'] == [rc.AEDUI, rc.GERMANS, rc.BELGAE, rc.ROMANS]
    assert council['np_symbols'][rc.GERMANS] == rc.NP_SYMBOL_SWORDS
    assert rc.ARVERNI not in council['np_symbols']
    assert expansion['faction_order'] == [rc.ROMANS, rc.GERMANS, rc.BELGAE, rc.AEDUI]


@pytest.mark.parametrize('params', [[], [rc.SEQUANI], False, 'invalid'])
def test_malformed_event_param_container_rejects_before_any_decision(params):
    state = _state()
    before = encode(state)
    state['decision_agent'] = lambda *args: pytest.fail('Malformed params exposed Council')
    result = _event(state, params)
    assert not result['executed']
    assert encode({k: v for k, v in state.items() if k != 'decision_agent'}) == before
