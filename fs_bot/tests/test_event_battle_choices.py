"""Source-based target selection for the numeric Event Battle grants."""
from copy import deepcopy

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import place_piece, count_pieces
from fs_bot.engine import execute as ex
from fs_bot.engine.free_actions import validate_free_action_response
from fs_bot.state.state_schema import build_initial_state, validate_state
from fs_bot.state.serialize import encode


def board():
    state = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=7)
    state['non_player_factions'] = set()
    return state


def choice_agent(choice, requests):
    def choose(state, faction, request):
        if request.get('request_type') == 'fixed_event_battle':
            requests.append((faction, deepcopy(request)))
            return choice
        if request['kind'] == 'retreat':
            return {'retreat': False, 'region': None}
        return None
    return choose


def test_aquitani_can_choose_either_region_without_attacking_forces():
    state = board()
    place_piece(state, rc.PICTONES, rc.BELGAE, rc.WARBAND, 4)
    place_piece(state, rc.ARVERNI_REGION, rc.ARVERNI, rc.WARBAND, 5)
    requests = []
    state['decision_agent'] = choice_agent({'region': rc.PICTONES, 'defender': rc.BELGAE}, requests)
    result = ex._resolve_card25_battle(state, rc.AEDUI, None, 3)[0]
    assert result['region'] == rc.PICTONES and result['defender'] == rc.BELGAE
    assert requests[0][0] == rc.AEDUI
    assert set(requests[0][1]['defenders_by_region']) == {rc.PICTONES, rc.ARVERNI_REGION}
    assert count_pieces(state, rc.PICTONES, rc.BELGAE, rc.WARBAND) == 1
    assert count_pieces(state, rc.ARVERNI_REGION, rc.ARVERNI, rc.WARBAND) == 5
    assert validate_state(state) == []


def test_aquitani_supplied_region_is_preserved_but_defender_is_chosen():
    state = board()
    place_piece(state, rc.ARVERNI_REGION, rc.BELGAE, rc.WARBAND, 2)
    place_piece(state, rc.ARVERNI_REGION, rc.ARVERNI, rc.WARBAND, 4)
    requests = []
    state['decision_agent'] = choice_agent({'region': rc.ARVERNI_REGION, 'defender': rc.BELGAE}, requests)
    result = ex._resolve_card25_battle(state, rc.AEDUI, rc.ARVERNI_REGION, 3)[0]
    assert result['defender'] == rc.BELGAE
    assert requests[0][1]['allowed_regions'] == [rc.ARVERNI_REGION]
    assert count_pieces(state, rc.ARVERNI_REGION, rc.ARVERNI, rc.WARBAND) == 4


def test_morasses_human_can_choose_smaller_target_and_static_attacking_force():
    state = board()
    place_piece(state, rc.MANDUBII, rc.ROMANS, rc.AUXILIA, 6)
    place_piece(state, rc.MANDUBII, rc.ARVERNI, rc.WARBAND, 8)
    place_piece(state, rc.CARNUTES, rc.ROMANS, rc.FORT)
    place_piece(state, rc.CARNUTES, rc.BELGAE, rc.WARBAND)
    requests = []
    state['decision_agent'] = choice_agent({'region': rc.CARNUTES, 'defender': rc.BELGAE}, requests)
    result = ex._resolve_card36_battle(state, rc.ROMANS)[0]
    assert result['region'] == rc.CARNUTES and result['defender'] == rc.BELGAE
    assert result['result']['counterattack'] is None
    assert requests[0][1]['default_available']
    assert validate_state(state) == []


def test_litaviccus_human_chooses_region_with_only_aedui_forces():
    state = board()
    place_piece(state, rc.MANDUBII, rc.BELGAE, rc.WARBAND, 4)
    place_piece(state, rc.MANDUBII, rc.ROMANS, rc.AUXILIA, 4)
    place_piece(state, rc.CARNUTES, rc.AEDUI, rc.WARBAND, 4)
    place_piece(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA, 2)
    requests = []
    state['decision_agent'] = choice_agent({'region': rc.CARNUTES, 'defender': rc.ROMANS}, requests)
    result = ex._resolve_card45_battle(state, rc.BELGAE)[0]
    assert result['region'] == rc.CARNUTES
    assert count_pieces(state, rc.MANDUBII, rc.ROMANS, rc.AUXILIA) == 4
    assert count_pieces(state, rc.CARNUTES, rc.AEDUI, rc.WARBAND) == 4
    assert state['resources'][rc.BELGAE] == 0


def test_litaviccus_aedui_does_not_double_its_own_force():
    state = board()
    state['resources'][rc.AEDUI] = 10
    place_piece(state, rc.CARNUTES, rc.AEDUI, rc.WARBAND, 4)
    place_piece(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA, 3)
    requests = []
    state['decision_agent'] = choice_agent({'region': rc.CARNUTES, 'defender': rc.ROMANS}, requests)
    result = ex._resolve_card45_battle(state, rc.AEDUI)[0]
    assert result['result']['executed']
    assert count_pieces(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA) == 1


@pytest.mark.parametrize('profile', ['card_11', 'card_11a'])
def test_numidians_roman_beneficiary_selects_defender(profile):
    state = board()
    place_piece(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA, 3)
    place_piece(state, rc.CARNUTES, rc.ARVERNI, rc.WARBAND, 6)
    place_piece(state, rc.CARNUTES, rc.BELGAE, rc.WARBAND, 2)
    requests = []
    state['decision_agent'] = choice_agent({'region': rc.CARNUTES, 'defender': rc.BELGAE}, requests)
    result = ex._resolve_double_aux_battle_card(state, rc.CARNUTES, profile)[0]
    assert requests[0][0] == rc.ROMANS
    assert result['result']['attack']['losses_taken'] == 2
    assert count_pieces(state, rc.CARNUTES, rc.ARVERNI, rc.WARBAND) == 6


def test_camulogenus_battle_defender_selected_at_its_march_destination():
    state = board()
    place_piece(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA, 4)
    place_piece(state, rc.CARNUTES, rc.ARVERNI, rc.WARBAND, 6)
    place_piece(state, rc.CARNUTES, rc.BELGAE, rc.WARBAND, 2)
    requests = []
    state['decision_agent'] = choice_agent({'region': rc.CARNUTES, 'defender': rc.BELGAE}, requests)
    result = ex._resolve_card70_march_battle(state, [rc.CARNUTES], 4)[0]
    assert result['defender'] == rc.BELGAE
    assert requests[0][1]['allowed_regions'] == [rc.CARNUTES]
    assert not requests[0][1]['allow_decline']


@pytest.mark.parametrize('invalid', [
    {'decline': True}, {'decline': 1},
    {'region': rc.PICTONES, 'defender': rc.BELGAE},
    {'region': rc.ARVERNI_REGION, 'defender': rc.AEDUI},
    {'region': rc.ARVERNI_REGION, 'defender': rc.BELGAE, 'extra_losses': 99},
    {'command': rc.CMD_BATTLE, 'sa': rc.SA_AMBUSH, 'details': {'battle_plan': []}},
])
def test_invalid_fixed_event_response_cannot_mutate_board_or_rng(invalid):
    state = board()
    place_piece(state, rc.ARVERNI_REGION, rc.BELGAE, rc.WARBAND, 4)
    requests = []
    state['decision_agent'] = choice_agent(invalid, requests)
    before = encode({k:v for k,v in state.items() if k != 'decision_agent'})
    with pytest.raises(ValueError):
        ex._resolve_card25_battle(state, rc.AEDUI, rc.ARVERNI_REGION, 3)
    assert encode({k:v for k,v in state.items() if k != 'decision_agent'}) == before


def test_live_validator_rejects_a_now_absent_target_without_prompting():
    state = board()
    request = {'kind': 'free_action', 'request_type': 'fixed_event_battle',
               'card_id': 25, 'allowed_regions': [rc.PICTONES],
               'defenders_by_region': {rc.PICTONES: [rc.BELGAE]},
               'default_available': False, 'allow_decline': False}
    before = encode(state)
    error = validate_free_action_response(state, rc.AEDUI, request,
                                         {'region': rc.PICTONES, 'defender': rc.BELGAE})
    assert error
    assert encode(state) == before


def test_mandatory_battle_without_default_requires_explicit_target():
    state = board()
    place_piece(state, rc.CARNUTES, rc.ROMANS, rc.FORT)
    place_piece(state, rc.CARNUTES, rc.BELGAE, rc.WARBAND)
    requests = []
    state['decision_agent'] = choice_agent({'use_default': True}, requests)
    before = encode({k:v for k,v in state.items() if k != 'decision_agent'})
    with pytest.raises(ValueError, match='No legal default'):
        ex._resolve_card36_battle(state, rc.ROMANS)
    assert not requests[0][1]['default_available']
    assert encode({k:v for k,v in state.items() if k != 'decision_agent'}) == before


@pytest.mark.parametrize('profile', ['card_11', 'card_11a'])
def test_numidians_np_retreat_accounts_for_doubled_auxilia(profile):
    """§8.4.3: six doubled Auxilia would wipe six Warbands; Retreat saves three."""
    from fs_bot.board.control import refresh_all_control
    state = board()
    state['non_player_factions'] = {rc.ROMANS, rc.BELGAE}
    place_piece(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA, 6)
    place_piece(state, rc.CARNUTES, rc.BELGAE, rc.WARBAND, 6)
    place_piece(state, rc.ATREBATES, rc.BELGAE, rc.WARBAND)
    refresh_all_control(state)
    result = ex._resolve_double_aux_battle_card(state, rc.CARNUTES, profile)[0]['result']
    assert result['defender_retreated']
    assert result['attack']['losses_taken'] == 3
    assert (count_pieces(state, rc.ATREBATES, rc.BELGAE, rc.WARBAND)
            + count_pieces(state, rc.CARNUTES, rc.BELGAE, rc.WARBAND)) == 4
    assert validate_state(state) == []


@pytest.mark.parametrize('profile,expected_legions,expected_leader', [
    ('card_11', 1, rc.CAESAR), ('card_11a', 0, None),
])
def test_numidians_retreat_callback_sees_actual_attacking_cohort(
        profile, expected_legions, expected_leader):
    from fs_bot.board.pieces import get_leader_in_region
    state = board()
    place_piece(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA, 2)
    place_piece(state, rc.CARNUTES, rc.ROMANS, rc.LEGION, from_legions_track=True)
    place_piece(state, rc.CARNUTES, rc.ROMANS, rc.LEADER, leader_name=rc.CAESAR)
    place_piece(state, rc.CARNUTES, rc.BELGAE, rc.WARBAND, 4)
    seen = []
    def agent(current, actor, request):
        if request.get('request_type') == 'fixed_event_battle':
            return {'region': rc.CARNUTES, 'defender': rc.BELGAE}
        if request['kind'] == 'retreat':
            seen.append((count_pieces(current, rc.CARNUTES, rc.ROMANS, rc.LEGION),
                         get_leader_in_region(current, rc.CARNUTES, rc.ROMANS)))
            return {'retreat': False}
        return None
    state['decision_agent'] = agent
    ex._resolve_double_aux_battle_card(state, rc.CARNUTES, profile)
    assert seen == [(expected_legions, expected_leader)]
    assert '_battle_auxilia_only' not in state


def test_revised_numidians_np_cannot_battle_with_only_excluded_forces():
    state = board()
    state['non_player_factions'] = {rc.ROMANS}
    place_piece(state, rc.CARNUTES, rc.ROMANS, rc.LEGION, from_legions_track=True)
    place_piece(state, rc.CARNUTES, rc.BELGAE, rc.WARBAND, 4)
    seen = []
    state['decision_agent'] = lambda current, actor, request: seen.append(request)
    before = encode({k:v for k,v in state.items() if k != 'decision_agent'})
    result = ex._resolve_double_aux_battle_card(state, rc.CARNUTES, 'card_11a')[0]
    assert result.get('executed') is False
    assert not seen
    assert encode({k:v for k,v in state.items() if k != 'decision_agent'}) == before


def test_aquitani_np_retreat_accounts_for_extra_losses_after_halving():
    """25: Attack causes five Losses; Retreat causes four, saving the last piece."""
    from fs_bot.board.control import refresh_all_control
    state = board()
    state['non_player_factions'] = {rc.AEDUI, rc.BELGAE}
    place_piece(state, rc.PICTONES, rc.AEDUI, rc.WARBAND, 4)
    place_piece(state, rc.PICTONES, rc.BELGAE, rc.WARBAND, 5)
    place_piece(state, rc.CARNUTES, rc.BELGAE, rc.WARBAND)
    refresh_all_control(state)
    result = ex._resolve_card25_battle(state, rc.AEDUI, rc.PICTONES, 3)[0]['result']
    assert result['defender_retreated']
    assert result['attack']['losses_taken'] == 4
    assert count_pieces(state, rc.CARNUTES, rc.BELGAE, rc.WARBAND) == 2
    assert validate_state(state) == []


def test_aquitani_first_ally_absorbs_one_loss_when_outmatched_belgae_retreat():
    """Standing would leave Ambiorix inflicting one Loss against four."""
    from fs_bot.board.control import refresh_all_control
    state = board()
    state['non_player_factions'] = {rc.ROMANS, rc.BELGAE}
    place_piece(state, rc.PICTONES, rc.ROMANS, rc.AUXILIA, 2)
    place_piece(state, rc.PICTONES, rc.BELGAE, rc.WARBAND, 3)
    place_piece(state, rc.PICTONES, rc.BELGAE, rc.LEADER, leader_name=rc.AMBIORIX)
    place_piece(state, rc.PICTONES, rc.BELGAE, rc.ALLY)
    state['tribes'][rc.TRIBE_PICTONES]['allied_faction'] = rc.BELGAE
    place_piece(state, rc.CARNUTES, rc.BELGAE, rc.WARBAND)
    refresh_all_control(state)
    result = ex._resolve_card25_battle(state, rc.ROMANS, rc.PICTONES, 3)[0]['result']
    assert result['defender_retreated']
    assert result['attack']['ally_first_removed'] == 1
    assert result['attack']['losses_taken'] == 3
    assert result['counterattack'] is None
    assert count_pieces(state, rc.PICTONES, rc.BELGAE, rc.WARBAND) == 1
    assert validate_state(state) == []


def test_aquitani_first_ally_loss_does_not_falsely_expose_a_roman_legion():
    """§8.4.3: neither standing nor Retreat exposes the Legion after Ally + 2 Auxilia."""
    from fs_bot.board.control import refresh_all_control
    state = board()
    state['non_player_factions'] = {rc.AEDUI, rc.ROMANS}
    place_piece(state, rc.PICTONES, rc.ROMANS, rc.AUXILIA, 2)
    place_piece(state, rc.PICTONES, rc.ROMANS, rc.LEGION, from_legions_track=True)
    # Rule out the separate poor-Counterattack reason to Retreat.
    place_piece(state, rc.PICTONES, rc.ROMANS, rc.FORT)
    place_piece(state, rc.PICTONES, rc.ROMANS, rc.ALLY)
    state['tribes'][rc.TRIBE_PICTONES]['allied_faction'] = rc.ROMANS
    place_piece(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA)
    refresh_all_control(state)
    result = ex._resolve_card25_battle(state, rc.AEDUI, rc.PICTONES, 3)[0]['result']
    assert not result['defender_retreated']
    assert result['attack']['ally_first_removed'] == 1
    assert result['attack']['rolls'] == []
    assert count_pieces(state, rc.PICTONES, rc.ROMANS, rc.LEGION) == 1
    assert validate_state(state) == []
