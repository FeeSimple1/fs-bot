"""A67 German Event instruction: gather maximum safe surplus to take Control."""
from copy import deepcopy

from fs_bot import rules_consts as rc
from fs_bot.board.control import is_controlled_by, refresh_all_control
from fs_bot.board.pieces import count_pieces, get_leader_in_region, place_piece
from fs_bot.engine.execute import _execute_event
from fs_bot.state.state_schema import build_initial_state, validate_state


def _state():
    state = build_initial_state(rc.SCENARIO_ARIOVISTUS, seed=7)
    state['current_card'] = 'A67'
    state['non_player_factions'] = {rc.GERMANS}
    return state


def _event(state):
    refresh_all_control(state)
    result = _execute_event(state, rc.GERMANS, {
        'command': 'Event', 'sa': 'No SA', 'sa_regions': [],
        'details': {'card_id': 'A67', 'text_preference': rc.EVENT_UNSHADED}})
    assert result['executed']
    assert validate_state(state) == []
    return result.get('free_actions', [])


def _gather(result):
    return next(item for item in result if item['free_action'] == 'march')


def test_controlled_origin_contributes_all_safe_surplus():
    state = _state()
    place_piece(state, rc.UBII, rc.GERMANS, rc.WARBAND, 5)
    place_piece(state, rc.UBII, rc.ROMANS, rc.AUXILIA, 1)
    place_piece(state, rc.TREVERI, rc.ROMANS, rc.AUXILIA, 1)
    result = _event(state)
    assert count_pieces(state, rc.UBII, rc.GERMANS, rc.WARBAND) == 2
    assert is_controlled_by(state, rc.UBII, rc.GERMANS)
    assert count_pieces(state, rc.TREVERI, rc.GERMANS, rc.WARBAND) == 3
    assert _gather(result)['target'] == rc.TREVERI
    assert state['resources'][rc.GERMANS] == 0


def test_departing_leader_counts_against_safe_surplus():
    state = _state()
    place_piece(state, rc.UBII, rc.GERMANS, rc.WARBAND, 5)
    place_piece(state, rc.UBII, rc.GERMANS, rc.LEADER,
                leader_name=rc.ARIOVISTUS_LEADER)
    place_piece(state, rc.UBII, rc.ROMANS, rc.AUXILIA, 2)
    place_piece(state, rc.TREVERI, rc.ROMANS, rc.AUXILIA, 1)
    _event(state)
    assert count_pieces(state, rc.UBII, rc.GERMANS, rc.WARBAND) == 3
    assert is_controlled_by(state, rc.UBII, rc.GERMANS)
    assert get_leader_in_region(state, rc.TREVERI, rc.GERMANS) == rc.ARIOVISTUS_LEADER
    assert count_pieces(state, rc.TREVERI, rc.GERMANS, rc.WARBAND) == 2


def test_settlement_preserves_control_without_an_unnecessary_warband():
    state = _state()
    place_piece(state, rc.UBII, rc.GERMANS, rc.SETTLEMENT)
    place_piece(state, rc.UBII, rc.GERMANS, rc.WARBAND, 3)
    place_piece(state, rc.TREVERI, rc.ROMANS, rc.AUXILIA, 1)
    _event(state)
    assert count_pieces(state, rc.UBII, rc.GERMANS, rc.WARBAND) == 0
    assert count_pieces(state, rc.UBII, rc.GERMANS, rc.SETTLEMENT) == 1
    assert is_controlled_by(state, rc.UBII, rc.GERMANS)
    assert count_pieces(state, rc.TREVERI, rc.GERMANS, rc.WARBAND) == 3


def test_unreachable_roman_target_does_not_hide_reachable_aedui_target():
    state = _state()
    place_piece(state, rc.NERVII, rc.ROMANS, rc.AUXILIA, 8)
    place_piece(state, rc.TREVERI, rc.AEDUI, rc.WARBAND, 1)
    place_piece(state, rc.UBII, rc.GERMANS, rc.WARBAND, 4)
    result = _event(state)
    assert _gather(result)['target'] == rc.TREVERI
    assert count_pieces(state, rc.UBII, rc.GERMANS, rc.WARBAND) == 1
    assert count_pieces(state, rc.TREVERI, rc.GERMANS, rc.WARBAND) == 3
    assert count_pieces(state, rc.NERVII, rc.ROMANS, rc.AUXILIA) == 8
    battle = next(item for item in result if item['free_action'] == 'battle')
    assert battle['defender'] == rc.AEDUI


def test_insufficient_safe_force_does_not_march_or_battle():
    state = _state()
    place_piece(state, rc.UBII, rc.GERMANS, rc.WARBAND, 4)
    place_piece(state, rc.UBII, rc.GERMANS, rc.LEADER,
                leader_name=rc.ARIOVISTUS_LEADER)
    place_piece(state, rc.UBII, rc.ROMANS, rc.AUXILIA, 2)
    place_piece(state, rc.TREVERI, rc.ROMANS, rc.AUXILIA, 2)
    refresh_all_control(state)
    before = deepcopy(state['spaces'])
    # Only Leader + 1 WB may leave, so the destination would merely tie.
    assert _event(state) == []
    assert state['spaces'] == before


def test_gathered_battle_still_consults_retreat_agreement_and_defender():
    state = _state()
    place_piece(state, rc.UBII, rc.GERMANS, rc.WARBAND, 8)
    place_piece(state, rc.TREVERI, rc.ROMANS, rc.LEGION, 2, from_legions_track=True)
    place_piece(state, rc.MANDUBII, rc.AEDUI, rc.WARBAND, 3)
    requests = []
    def agent(st, faction, request):
        requests.append((faction, request))
        if (request['kind'] == 'agreement' and faction == rc.AEDUI
                and request['request_type'] == 'retreat_into_control'):
            return True
        if request['kind'] == 'retreat' and faction == rc.ROMANS:
            assert rc.MANDUBII in request['legal_regions']
            return {'retreat': True, 'region': rc.MANDUBII}
        return None
    state['decision_agent'] = agent
    _event(state)
    assert any(f == rc.AEDUI and req['kind'] == 'agreement'
               and req['request_type'] == 'retreat_into_control'
               for f, req in requests)
    assert any(f == rc.ROMANS and req['kind'] == 'retreat'
               for f, req in requests)


def test_origin_control_counts_all_enemy_factions_combined():
    state = _state()
    place_piece(state, rc.UBII, rc.GERMANS, rc.WARBAND, 5)
    place_piece(state, rc.UBII, rc.ROMANS, rc.AUXILIA, 1)
    place_piece(state, rc.UBII, rc.AEDUI, rc.WARBAND, 1)
    place_piece(state, rc.TREVERI, rc.ROMANS, rc.AUXILIA, 1)
    _event(state)
    assert count_pieces(state, rc.UBII, rc.GERMANS, rc.WARBAND) == 3
    assert is_controlled_by(state, rc.UBII, rc.GERMANS)
    assert count_pieces(state, rc.TREVERI, rc.GERMANS, rc.WARBAND) == 2


def test_leader_cannot_abandon_the_only_piece_preserving_origin_control():
    state = _state()
    place_piece(state, rc.UBII, rc.GERMANS, rc.LEADER,
                leader_name=rc.ARIOVISTUS_LEADER)
    place_piece(state, rc.ATREBATES, rc.GERMANS, rc.WARBAND, 4)
    place_piece(state, rc.TREVERI, rc.ROMANS, rc.AUXILIA, 1)
    _event(state)
    assert get_leader_in_region(state, rc.UBII, rc.GERMANS) == rc.ARIOVISTUS_LEADER
    assert is_controlled_by(state, rc.UBII, rc.GERMANS)
    assert count_pieces(state, rc.TREVERI, rc.GERMANS, rc.WARBAND) == 3
