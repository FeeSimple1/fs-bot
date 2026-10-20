"""Source-derived Card54 limits and human choice, both printed editions."""
from copy import deepcopy
import pytest
from fs_bot import rules_consts as rc
from fs_bot.board.pieces import place_piece, count_pieces, get_leader_in_region
from fs_bot.state.state_schema import build_initial_state, check_structural_integrity
from fs_bot.cards.joined_ranks import resolve_joined_ranks


def state():
    s = build_initial_state(rc.SCENARIO_PAX_GALLICA, seed=54)
    s['non_player_factions'] = {rc.BELGAE, rc.ARVERNI}
    place_piece(s, rc.AEDUI_REGION, rc.BELGAE, rc.WARBAND, 3)
    place_piece(s, rc.AEDUI_REGION, rc.ARVERNI, rc.WARBAND, 3)
    s['event_params'] = {'region': rc.AEDUI_REGION, 'target_faction': rc.ARVERNI,
                         'first_battle': False}
    return s


def record_battles(monkeypatch):
    calls = []
    def battle(s, faction, action):
        calls.append((faction, deepcopy(action)))
        return {'executed': True}
    monkeypatch.setattr('fs_bot.engine.execute._execute_battle', battle)
    return calls


def test_card54_caps_default_march_at_eight_and_counts_leader(monkeypatch):
    s = state()
    place_piece(s, rc.SEQUANI, rc.ROMANS, rc.LEADER, leader_name=rc.CAESAR)
    place_piece(s, rc.SEQUANI, rc.ROMANS, rc.AUXILIA, 12)
    s['event_params']['origin_region'] = rc.SEQUANI
    calls = record_battles(monkeypatch)
    resolve_joined_ranks(s, rc.ROMANS)
    assert count_pieces(s, rc.AEDUI_REGION, rc.ROMANS, rc.AUXILIA) == 7
    assert count_pieces(s, rc.SEQUANI, rc.ROMANS, rc.AUXILIA) == 5
    assert get_leader_in_region(s, rc.AEDUI_REGION, rc.ROMANS) == rc.CAESAR
    assert calls == []
    assert check_structural_integrity(s) == []


@pytest.mark.parametrize('count', [9, -1, 1.5, True])
def test_bad_march_count_rejected_before_board_or_rng_changes(count):
    s = state()
    place_piece(s, rc.SEQUANI, rc.AEDUI, rc.WARBAND, 12)
    s['event_params'].update(origin_region=rc.SEQUANI, march_warbands=count)
    before = deepcopy(s)
    with pytest.raises(ValueError):
        resolve_joined_ranks(s, rc.AEDUI)
    assert s['spaces'] == before['spaces']
    assert s['rng'].getstate() == before['rng'].getstate()


def test_explicit_two_region_roman_march_is_available():
    s = state()
    place_piece(s, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA, 2)
    s['event_params'].update(origin_region=rc.PROVINCIA,
                            march_regions=[rc.SEQUANI, rc.AEDUI_REGION], march_auxilia=2)
    resolve_joined_ranks(s, rc.ROMANS)
    assert count_pieces(s, rc.AEDUI_REGION, rc.ROMANS, rc.AUXILIA) == 2


def test_gallic_march_cannot_claim_roman_distance():
    s = state()
    place_piece(s, rc.PROVINCIA, rc.AEDUI, rc.WARBAND, 2)
    s['event_params'].update(origin_region=rc.PROVINCIA,
                            march_regions=[rc.SEQUANI, rc.AEDUI_REGION], march_warbands=2)
    with pytest.raises(ValueError, match='distance'):
        resolve_joined_ranks(s, rc.AEDUI)
    assert count_pieces(s, rc.PROVINCIA, rc.AEDUI, rc.WARBAND) == 2


def test_second_nonplayer_never_battles(monkeypatch):
    s = state()
    place_piece(s, rc.AEDUI_REGION, rc.ROMANS, rc.AUXILIA, 2)
    calls = record_battles(monkeypatch)
    s['event_params']['first_battle'] = True
    s['decision_agent'] = lambda *a: True
    resolve_joined_ranks(s, rc.ROMANS)
    assert [f for f, _ in calls] == [rc.ROMANS]


@pytest.mark.parametrize('edition,first,expected', [
    ('original', False, True), ('second-edition', False, False),
    ('original', True, False), ('second-edition', True, False)])
def test_second_player_decides_and_retreat_is_allowed_not_forced(monkeypatch, edition, first, expected):
    s = state()
    place_piece(s, rc.AEDUI_REGION, rc.ROMANS, rc.AUXILIA, 2)
    s['non_player_factions'] = {rc.ARVERNI}
    s['card_edition'] = edition
    s['event_params'].update(first_battle=first, second_faction=rc.BELGAE)
    requests = []
    def decide(st, faction, request):
        requests.append((faction, request))
        return True
    s['decision_agent'] = decide
    calls = record_battles(monkeypatch)
    resolve_joined_ranks(s, rc.ROMANS)
    assert requests[0][0] == rc.BELGAE
    assert requests[0][1]['request_type'] == 'joined_ranks_battle'
    f, action = calls[-1]
    assert f == rc.BELGAE
    assert action['details']['no_retreat'] is expected
    assert not action['details'].get('force_retreat')
    assert action['details']['battle_plan'][0]['target'] == rc.ARVERNI


def test_second_player_can_refuse(monkeypatch):
    s = state()
    place_piece(s, rc.AEDUI_REGION, rc.ROMANS, rc.AUXILIA, 2)
    s['non_player_factions'] = {rc.ARVERNI}
    s['decision_agent'] = lambda *a: False
    calls = record_battles(monkeypatch)
    resolve_joined_ranks(s, rc.ROMANS)
    assert calls == []


@pytest.mark.parametrize('edition,valid', [('original', False), ('second-edition', True)])
def test_revised_destination_counts_game_run_germans(edition, valid):
    s = build_initial_state(rc.SCENARIO_PAX_GALLICA, seed=54)
    place_piece(s, rc.AEDUI_REGION, rc.ROMANS, rc.AUXILIA, 1)
    place_piece(s, rc.AEDUI_REGION, rc.BELGAE, rc.WARBAND, 1)
    place_piece(s, rc.AEDUI_REGION, rc.GERMANS, rc.WARBAND, 1)
    s['card_edition'] = edition
    s['non_player_factions'] = {rc.BELGAE}
    s['event_params'] = {'region': rc.AEDUI_REGION, 'first_battle': False}
    if valid:
        resolve_joined_ranks(s, rc.ROMANS)
    else:
        with pytest.raises(ValueError, match='two other'):
            resolve_joined_ranks(s, rc.ROMANS)


def test_second_battle_cannot_switch_to_a_different_defender(monkeypatch):
    s = state()
    place_piece(s, rc.AEDUI_REGION, rc.ROMANS, rc.AUXILIA, 2)
    place_piece(s, rc.AEDUI_REGION, rc.GERMANS, rc.WARBAND, 2)
    s['event_params']['first_battle'] = True
    s['non_player_factions'] = {rc.ARVERNI}
    s['decision_agent'] = lambda *a: True
    calls = []
    def destroy(st, faction, action):
        from fs_bot.board.pieces import remove_piece
        calls.append(faction)
        remove_piece(st, rc.AEDUI_REGION, rc.ARVERNI, rc.WARBAND, count=3,
                     piece_state=rc.HIDDEN)
        return {'executed': True}
    monkeypatch.setattr('fs_bot.engine.execute._execute_battle', destroy)
    resolve_joined_ranks(s, rc.ROMANS)
    assert calls == [rc.ROMANS]


def test_invalid_follow_up_is_reported_and_rolls_back_entire_event():
    from fs_bot.engine.execute import _execute_event
    s = state()
    place_piece(s, rc.SEQUANI, rc.AEDUI, rc.WARBAND, 12)
    s['event_params'] = None
    before = deepcopy(s)
    result = _execute_event(s, rc.AEDUI, {'details': {'card_id': 54,
        'event_params': {'region': rc.AEDUI_REGION, 'origin_region': rc.SEQUANI,
                         'march_warbands': 9}}}, human=True)
    assert result['executed'] is False
    assert 'Card 54' in result['reason']
    assert s['spaces'] == before['spaces']
    assert s.get('event_modifiers') == before.get('event_modifiers')
    assert s['rng'].getstate() == before['rng'].getstate()
