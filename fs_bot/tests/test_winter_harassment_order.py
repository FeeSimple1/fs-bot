"""Winter Campaign Harassment must not look up the Winter marker as an Event.

Card63 permits after-Harvest Commands; §6.0's current Winter card has no
printed Faction order. Preserve the existing fallback pending source guidance.
"""
import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import place_piece, count_pieces, get_leader_in_region
from fs_bot.cards.capabilities import activate_capability, set_capability_owner
from fs_bot.engine.agent import HARASSMENT_LOSS
from fs_bot.engine.game_engine import get_sop_factions
from fs_bot.engine.winter_campaign import winter_campaign_after_harvest
from fs_bot.state.state_schema import build_initial_state, validate_state
from fs_bot.tools.run_batch import play_one


@pytest.mark.parametrize('current_card', [rc.WINTER_CARD, 'W1'])
def test_actual_after_harvest_campaign_marches_through_harassment_without_event_order(current_card):
    st = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=75)
    st['current_card'], st['next_card'] = current_card, 4
    st['non_player_factions'] = set(get_sop_factions(st)) - {rc.ARVERNI, rc.BELGAE}
    st['resources'][rc.ARVERNI] = 10
    activate_capability(st, 63, rc.EVENT_SHADED)
    set_capability_owner(st, 63, rc.ARVERNI)
    place_piece(st, rc.MORINI, rc.ARVERNI, rc.LEADER, leader_name=rc.VERCINGETORIX)
    place_piece(st, rc.MORINI, rc.ARVERNI, rc.WARBAND, 5)
    place_piece(st, rc.NERVII, rc.ROMANS, rc.AUXILIA, 3)
    place_piece(st, rc.NERVII, rc.AEDUI, rc.WARBAND, 3)
    place_piece(st, rc.NERVII, rc.BELGAE, rc.WARBAND, 3)
    plan = {'command': rc.CMD_MARCH, 'sa': 'No SA', 'details': {
        'origins': [rc.MORINI], 'destinations': [rc.ATREBATES],
        'routes': {rc.MORINI: [rc.NERVII, rc.ATREBATES]}}}
    campaigns, harassers = [], []
    def agent(board, faction, request):
        if request['kind'] == 'winter_campaign':
            campaigns.append(request)
            return plan if len(campaigns) == 1 else {'decline': True}
        if request.get('request_type') == 'harassment':
            return True
        if request['kind'] == HARASSMENT_LOSS:
            harassers.append(request['harasser'])
            return {'choice': rc.WARBAND}
        return None
    st['decision_agent'] = agent
    result = winter_campaign_after_harvest(st)
    assert result['result']['executed'] and result['remaining_actions'] == 1
    assert len(campaigns) == 2
    # Compatibility fallback, not a newly inferred Winter timing rule.
    assert harassers == [rc.ROMANS, rc.AEDUI, rc.BELGAE]
    assert st['current_card'] == current_card
    assert count_pieces(st, rc.ATREBATES, rc.ARVERNI, rc.WARBAND) == 2
    assert get_leader_in_region(st, rc.ATREBATES, rc.ARVERNI) == rc.VERCINGETORIX
    assert st['resources'][rc.ARVERNI] == 9
    assert validate_state(st) == []


@pytest.mark.parametrize('scenario,seed', [
    (rc.SCENARIO_RECONQUEST, 75),
    (rc.SCENARIO_GREAT_REVOLT, 92),
    (rc.SCENARIO_GREAT_REVOLT, 96),
])
def test_batch_winter_campaign_harassment_crash_seeds_complete(scenario, seed):
    result = play_one((scenario, seed))
    assert result['completed'], result['errors']
    assert result['game_completed'] and result['audit_completed']
    assert result['errors'] == [] and result['integrity_findings'] == []
