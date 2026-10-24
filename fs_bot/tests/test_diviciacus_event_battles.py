"""Event-granted Battles obtain real cooperation at their Command boundary."""
import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import place_piece, count_pieces, count_pieces_by_state
from fs_bot.engine.diviciacus import KEY
from fs_bot.engine.diviciacus_planning import CONFIRMATIONS
from fs_bot.engine.execute import (_resolve_card25_battle, _resolve_card36_battle,
                                   _resolve_card2_battle, execute_decision)
from fs_bot.tests.test_diviciacus_forces import board
from fs_bot.state.state_schema import validate_state


@pytest.mark.parametrize('card', [25, 36])
@pytest.mark.parametrize('request_loan', [False, True])
def test_human_fixed_battle_opts_in_before_lender_is_consulted(card, request_loan):
    st = board(region=rc.ARVERNI_REGION)
    place_piece(st, rc.ARVERNI_REGION, rc.BELGAE, rc.WARBAND, 3)
    requests = []
    def choose(state, faction, request):
        if request['kind'] != 'agreement':
            return None
        requests.append((faction, request['request_type']))
        return request_loan if request['request_type'] == 'diviciacus_command' else True
    st['decision_agent'] = choose
    result = (_resolve_card25_battle(st, rc.ROMANS, rc.ARVERNI_REGION, 0)
              if card == 25 else _resolve_card36_battle(st, rc.ROMANS))
    assert result[0]['result']['attack']['losses_taken'] == int(request_loan)
    assert requests == [(rc.ROMANS, 'diviciacus_command')] + (
        [(rc.AEDUI, 'diviciacus')] if request_loan else [])
    assert KEY not in st and CONFIRMATIONS not in st
    assert validate_state(st) == []


@pytest.mark.parametrize('card', [25, 36])
@pytest.mark.parametrize('lends', [False, True])
def test_np_fixed_battle_replans_refused_loan_without_reasking(card, lends):
    st = board(region=rc.ARVERNI_REGION)
    st['non_player_factions'] = {rc.ROMANS}
    place_piece(st, rc.ARVERNI_REGION, rc.BELGAE, rc.WARBAND, 3)
    requests = []
    def choose(state, faction, request):
        if request['kind'] == 'agreement':
            requests.append(request['request_type'])
            return lends
        return None
    st['decision_agent'] = choose
    result = (_resolve_card25_battle(st, rc.ROMANS, rc.ARVERNI_REGION, 0)
              if card == 25 else _resolve_card36_battle(st, rc.ROMANS))
    assert result[0]['result']['attack']['losses_taken'] == int(lends)
    assert requests == ['diviciacus']
    assert KEY not in st and CONFIRMATIONS not in st
    assert validate_state(st) == []


def test_card2_np_romans_never_lend_to_battle_against_themselves(monkeypatch):
    st = board(region=rc.CARNUTES)
    st['non_player_factions'] = {rc.AEDUI, rc.ROMANS}
    # The event removes the first Legion automatically; native Aedui
    # Warbands suffice, and Roman Auxilia must stay with their owner.
    place_piece(st, rc.CARNUTES, rc.ROMANS, rc.LEGION, from_legions_track=True)
    monkeypatch.setattr('fs_bot.engine.execute._decide_defender_retreat',
                        lambda *_: (False, None))
    result = _resolve_card2_battle(st, rc.AEDUI, rc.CARNUTES)
    assert result[0]['result']['attack']['auto_legion_removed'] == 1
    assert count_pieces(st, rc.CARNUTES, rc.ROMANS, rc.AUXILIA) == 1
    assert count_pieces(st, rc.CARNUTES, rc.AEDUI, rc.WARBAND) == 2
    assert KEY not in st and CONFIRMATIONS not in st
    assert validate_state(st) == []


def test_skipped_np_action_cannot_leave_agreement_for_a_later_turn():
    st = board()
    st['non_player_factions'] = {rc.ROMANS}
    st[CONFIRMATIONS] = [{'faction': rc.ROMANS, 'signature': 'stale',
                         'regions': [rc.CARNUTES]}]
    result = execute_decision(st, rc.ROMANS, {'bot_action': {'command': 'Pass'}})
    assert not result['executed']
    assert CONFIRMATIONS not in st
