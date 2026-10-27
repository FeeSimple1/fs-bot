"""The two Aedui instruction sheets condition specified Roman benefits."""
import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces, clear_allied_tribe, place_piece, remove_piece
from fs_bot.bots.aedui_bot import node_a3
from fs_bot.bots.bot_common import should_decline_event
from fs_bot.bots.bot_dispatch import dispatch_bot_turn
from fs_bot.cards.bot_instructions import get_bot_instruction
from fs_bot.cards.card_data import get_all_base_cards, get_all_ariovistus_cards
from fs_bot.engine.execute import _execute_event
from fs_bot.engine.victory import calculate_victory_score
from fs_bot.state.serialize import encode
from fs_bot.state.setup import setup_scenario


# The named groups in general/"No Aedui if Roman player or Roman victory
# exceeds 12" of the base and Ariovistus Aedui Event instruction sheets.
BASE_CONDITIONAL = {2, 3, 4, 5, 6, 7, 11, 12, 13, 14, 15, 16, 21, 31, 55, 56}
ARIO_CONDITIONAL = {2, 3, 4, 6, 7, 11, 12, 13, 14, 15, 16, 55,
                    'A5', 'A17', 'A22', 'A25', 'A60'}
SCENARIOS = (rc.SCENARIO_GREAT_REVOLT, rc.SCENARIO_ARIOVISTUS)


def _state(scenario, score=12, romans_np=True, card_id=16):
    state = setup_scenario(scenario, seed=3)
    state['non_player_factions'] = {rc.ROMANS, rc.AEDUI, rc.BELGAE,
        rc.GERMANS if scenario in rc.ARIOVISTUS_SCENARIOS else rc.ARVERNI}
    if not romans_np:
        state['non_player_factions'].remove(rc.ROMANS)
    if scenario in rc.ARIOVISTUS_SCENARIOS:
        # Setup Roman score is 15. Three physical Settlements lower it to
        # 12 under A7.2; no score field or victory helper is substituted.
        for region in (rc.MORINI, rc.NERVII, rc.TREVERI):
            place_piece(state, region, rc.GERMANS, rc.SETTLEMENT)
    assert calculate_victory_score(state, rc.ROMANS) == 12
    while calculate_victory_score(state, rc.ROMANS) < score:
        if scenario in rc.ARIOVISTUS_SCENARIOS:
            region = next(region for region in sorted(state['spaces'])
                          if count_pieces(state, region, rc.GERMANS, rc.SETTLEMENT))
            remove_piece(state, region, rc.GERMANS, rc.SETTLEMENT)
        else:
            # A removed non-Roman Ally leaves its physical Tribe Subdued,
            # increasing the Roman total by one (§7.2).
            tribe = next(tribe for tribe, info in sorted(state['tribes'].items())
                         if info['allied_faction'] not in (None, rc.ROMANS)
                         and count_pieces(state, rc.TRIBE_TO_REGION[tribe],
                                          info['allied_faction'], rc.ALLY)
                         and not (tribe in rc.TRIBE_TO_CITY and count_pieces(
                             state, rc.TRIBE_TO_REGION[tribe], info['allied_faction'], rc.CITADEL)))
            owner = state['tribes'][tribe]['allied_faction']
            region = rc.TRIBE_TO_REGION[tribe]
            remove_piece(state, region, owner, rc.ALLY)
            assert clear_allied_tribe(state, region, owner, rc.ALLY, tribe=tribe) == tribe
    assert calculate_victory_score(state, rc.ROMANS) == score
    state['current_card'] = state['current_card_id'] = card_id
    state['can_play_event'] = True
    state['is_second_eligible'] = False
    state['current_card_faction_order'] = [rc.ROMANS, rc.BELGAE, rc.AEDUI]
    state['next_card_faction_order'] = [rc.ROMANS, rc.AEDUI]
    return state


@pytest.mark.parametrize('scenario,expected', [
    (rc.SCENARIO_GREAT_REVOLT, BASE_CONDITIONAL),
    (rc.SCENARIO_ARIOVISTUS, ARIO_CONDITIONAL),
])
def test_typed_conditional_metadata_matches_each_supplied_instruction_group(scenario, expected):
    cards = get_all_ariovistus_cards() if scenario in rc.ARIOVISTUS_SCENARIOS else get_all_base_cards()
    flagged = {card_id for card_id, card in cards.items() if not card.is_winter
               and get_bot_instruction(card_id, rc.AEDUI, scenario).conditional_no_event}
    assert flagged == expected


@pytest.mark.parametrize('scenario', SCENARIOS)
@pytest.mark.parametrize('score,romans_np', [(13, True), (12, False)])
def test_all_flagged_events_decline_without_consuming_board_or_rng(scenario, score, romans_np):
    state = _state(scenario, score, romans_np)
    cards = ARIO_CONDITIONAL if scenario in rc.ARIOVISTUS_SCENARIOS else BASE_CONDITIONAL
    before = encode(state)
    for card_id in sorted(cards, key=str):
        assert should_decline_event(state, card_id, rc.AEDUI), card_id
    assert encode(state) == before


@pytest.mark.parametrize('scenario,card_id', [
    (rc.SCENARIO_GREAT_REVOLT, 16), (rc.SCENARIO_ARIOVISTUS, 16),
    (rc.SCENARIO_GREAT_REVOLT, 21),
])
@pytest.mark.parametrize('score,romans_np,allowed', [
    (12, True, True), (13, True, False), (16, True, False), (12, False, False),
])
def test_actual_aedui_node_and_dispatch_enforce_score_and_player_condition(
        scenario, card_id, score, romans_np, allowed):
    state = _state(scenario, score, romans_np, card_id)
    before = encode(state)
    assert should_decline_event(state, card_id, rc.AEDUI) is not allowed
    assert node_a3(state) == ('No' if allowed else 'Yes')
    assert encode(state) == before
    action = dispatch_bot_turn(state, rc.AEDUI)
    assert (action['command'] == 'Event') is allowed
    if allowed:
        assert action['details']['card_id'] == card_id


def test_ariovistus_settlement_deduction_controls_the_boundary():
    state = _state(rc.SCENARIO_ARIOVISTUS)
    assert sum(count_pieces(state, region, rc.GERMANS, rc.SETTLEMENT)
               for region in state['spaces']) == 4
    assert should_decline_event(state, 16, rc.AEDUI) is False
    remove_piece(state, rc.MORINI, rc.GERMANS, rc.SETTLEMENT)
    assert calculate_victory_score(state, rc.ROMANS) == 13
    assert should_decline_event(state, 16, rc.AEDUI) is True


@pytest.mark.parametrize('scenario', SCENARIOS)
def test_condition_does_not_spread_to_unflagged_cards_or_other_factions(scenario):
    state = _state(scenario, 16, romans_np=False)
    assert not get_bot_instruction(10, rc.AEDUI, scenario).conditional_no_event
    assert should_decline_event(state, 10, rc.AEDUI) is False
    assert should_decline_event(state, 16, rc.ROMANS) is False
    assert should_decline_event(state, 16, rc.BELGAE) is False


@pytest.mark.parametrize('scenario', SCENARIOS)
def test_human_aedui_can_choose_ambacti_roman_benefit_despite_np_condition(scenario):
    state = _state(scenario, 16, romans_np=False)
    state['non_player_factions'].remove(rc.AEDUI)
    before = count_pieces(state, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA)
    result = _execute_event(state, rc.AEDUI, {'details': {
        'card_id': 16, 'text_preference': rc.EVENT_UNSHADED,
        'event_params': {'target_region': rc.PROVINCIA}}}, human=True)
    assert result['executed']
    assert count_pieces(state, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA) == before + 6


def test_human_aedui_can_choose_province_resources_despite_np_condition():
    state = _state(rc.SCENARIO_GREAT_REVOLT, 16, romans_np=False, card_id=21)
    state['non_player_factions'].remove(rc.AEDUI)
    before = state['resources'][rc.ROMANS]
    result = _execute_event(state, rc.AEDUI, {'details': {
        'card_id': 21, 'text_preference': rc.EVENT_UNSHADED,
        'event_params': {'province_choice': 'resources'}}}, human=True)
    assert result['executed']
    assert state['resources'][rc.ROMANS] == min(rc.MAX_RESOURCES, before + 10)
