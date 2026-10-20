"""§8.4.4 applies to every possible loss-roll outcome of borrowed Battles."""
from copy import deepcopy
from itertools import product
from json import dumps

from fs_bot import rules_consts as rc
from fs_bot.battle.resolve import resolve_battle
from fs_bot.board.control import refresh_all_control
from fs_bot.board.pieces import count_pieces, place_piece
from fs_bot.cards.divination_np import _battle_frost_ok, _battle_frost_outcomes
from fs_bot.state.serialize import encode
from fs_bot.state.state_schema import build_initial_state


def position():
    st = build_initial_state(rc.SCENARIO_ARIOVISTUS, seed=4)
    st['non_player_factions'] = {rc.AEDUI, rc.BELGAE, rc.GERMANS}
    st['frost'] = True
    place_piece(st, rc.SEQUANI, rc.GERMANS, rc.WARBAND, 1)
    place_piece(st, rc.SEQUANI, rc.GERMANS, rc.LEADER, leader_name=rc.ARIOVISTUS_LEADER)
    place_piece(st, rc.SEQUANI, rc.GERMANS, rc.SETTLEMENT)
    place_piece(st, rc.SEQUANI, rc.ROMANS, rc.LEGION, 4, from_legions_track=True)
    refresh_all_control(st)
    return st


class Rolls:
    def __init__(self, rolls):
        self.rolls = iter(rolls)

    def randint(self, low, high):
        return next(self.rolls, high)


def signature(st):
    return dumps(encode({k: v for k, v in st.items() if k not in ('rng', 'decision_agent')}), sort_keys=True)


def test_failure_count_enumeration_matches_every_small_battle_roll_sequence():
    st = position()
    expected = set()
    # German Attack: at most three hard rolls; Counterattack: at most four.
    # Retreat is also available to the human defender, with no safe destination.
    for retreat in (False, True):
        for rolls in product((1, 6), repeat=7):
            sim = deepcopy(st)
            sim['rng'] = Rolls(rolls)
            resolve_battle(sim, rc.SEQUANI, rc.GERMANS, rc.ROMANS,
                           retreat_declaration=retreat)
            refresh_all_control(sim)
            expected.add(signature(sim))
    actual = {signature(sim) for sim in _battle_frost_outcomes(st, rc.SEQUANI, rc.ROMANS)}
    assert actual == expected


def test_frost_catches_surviving_defenders_then_removed_german_leader_and_settlement():
    st = position()
    from fs_bot.engine.victory import calculate_victory_margin
    before = calculate_victory_margin(st, rc.ROMANS)
    assert before >= 0
    # Both all-remove and all-survive miss this outcome: Roman Legions
    # survive the Attack, but Ariovistus fails his Counterattack save, letting
    # remaining Losses remove a Settlement and raise the Roman player's score.
    sim = deepcopy(st)
    sim['rng'] = Rolls([6, 6, 6, 1])
    resolve_battle(sim, rc.SEQUANI, rc.GERMANS, rc.ROMANS)
    assert count_pieces(sim, rc.SEQUANI, rc.GERMANS, rc.SETTLEMENT) == 0
    assert calculate_victory_margin(sim, rc.ROMANS) > before
    assert not _battle_frost_ok(st, rc.SEQUANI, rc.ROMANS)


def test_player_can_assign_losses_to_legion_before_auxilia():
    st = build_initial_state(rc.SCENARIO_ARIOVISTUS, seed=6)
    st['non_player_factions'] = {rc.GERMANS, rc.AEDUI, rc.BELGAE}
    place_piece(st, rc.SEQUANI, rc.GERMANS, rc.WARBAND, 4)
    place_piece(st, rc.SEQUANI, rc.ROMANS, rc.AUXILIA, 2)
    place_piece(st, rc.SEQUANI, rc.ROMANS, rc.LEGION, 1, from_legions_track=True)
    outcomes = list(_battle_frost_outcomes(st, rc.SEQUANI, rc.ROMANS))
    # A human may put both Attack Losses on a surviving Legion, preserving
    # Auxilia and producing a larger Counterattack than default Auxilia-first.
    assert any(count_pieces(s, rc.SEQUANI, rc.ROMANS, rc.AUXILIA) == 2
               and count_pieces(s, rc.SEQUANI, rc.ROMANS, rc.LEGION) == 1
               and count_pieces(s, rc.SEQUANI, rc.GERMANS, rc.WARBAND) == 2
               for s in outcomes)
    # Choosing one soft removal then one surviving save is covered as well.
    assert any(count_pieces(s, rc.SEQUANI, rc.ROMANS, rc.AUXILIA) == 1
               and count_pieces(s, rc.SEQUANI, rc.ROMANS, rc.LEGION) == 1
               and count_pieces(s, rc.SEQUANI, rc.GERMANS, rc.WARBAND) == 3
               for s in outcomes)


def test_player_loss_choice_search_keeps_mobile_before_static_and_diviciacus_last():
    from fs_bot.cards.divination_np import _legal_loss_choices
    st = build_initial_state(rc.SCENARIO_ARIOVISTUS, seed=6)
    place_piece(st, rc.SEQUANI, rc.AEDUI, rc.LEADER, leader_name=rc.DIVICIACUS)
    request = {'pieces': [(rc.LEADER, None), (rc.WARBAND, None), (rc.ALLY, None)],
               'is_retreat': False}
    assert _legal_loss_choices(st, rc.SEQUANI, rc.AEDUI, request) == [(rc.WARBAND, None)]
    request['is_retreat'] = True
    assert _legal_loss_choices(st, rc.SEQUANI, rc.AEDUI, request) == [(rc.ALLY, None)]


def test_game_run_arverni_cannot_supply_a_player_retreat_agreement():
    st = build_initial_state(rc.SCENARIO_ARIOVISTUS, seed=6)
    st['non_player_factions'] = {rc.GERMANS, rc.AEDUI, rc.BELGAE}
    place_piece(st, rc.SUGAMBRI, rc.GERMANS, rc.WARBAND, 4)
    place_piece(st, rc.SUGAMBRI, rc.ROMANS, rc.AUXILIA, 2)
    place_piece(st, rc.NERVII, rc.ARVERNI, rc.WARBAND, 4)
    refresh_all_control(st)
    assert all(count_pieces(sim, rc.NERVII, rc.ROMANS) == 0
               for sim in _battle_frost_outcomes(st, rc.SUGAMBRI, rc.ROMANS))


def test_frost_accounts_for_refusing_np_retreat_and_resulting_counterattack():
    from fs_bot.engine.victory import calculate_victory_margin
    from fs_bot.cards.divination_np import _frost_retreat_choices
    st = position()
    st['non_player_factions'] = {rc.ROMANS, rc.BELGAE, rc.GERMANS}
    place_piece(st, rc.AEDUI_REGION, rc.AEDUI, rc.ALLY)
    st['tribes'][rc.TRIBE_AEDUI]['allied_faction'] = rc.AEDUI
    place_piece(st, rc.AEDUI_REGION, rc.AEDUI, rc.WARBAND, 3)
    refresh_all_control(st)
    assert calculate_victory_margin(st, rc.AEDUI) == 0
    before, rng = signature(st), st['rng'].getstate()

    # 8.4.3: the NP Romans Retreat to reduce Legion Losses if the Aedui
    # grant a destination. Refusal leaves them in place to Counterattack.
    assert _frost_retreat_choices(st, rc.SEQUANI, rc.ROMANS) == [
        (False, None), (True, rc.AEDUI_REGION)]
    outcomes = list(_battle_frost_outcomes(st, rc.SEQUANI, rc.ROMANS))
    assert any(calculate_victory_margin(o, rc.AEDUI) == 1 for o in outcomes)
    assert not _battle_frost_ok(st, rc.SEQUANI, rc.ROMANS)
    assert signature(st) == before and st['rng'].getstate() == rng


def test_np_refuses_to_stand_when_it_always_has_own_retreat_destination():
    from fs_bot.cards.divination_np import _frost_retreat_choices
    st = position()
    st['non_player_factions'] = {rc.ROMANS, rc.BELGAE, rc.GERMANS}
    place_piece(st, rc.AEDUI_REGION, rc.ROMANS, rc.AUXILIA, 2)
    refresh_all_control(st)
    # Do not invent a stand-and-fight branch when 8.4.3 always requires
    # Retreat; only actual legal agreement/decision outcomes are explored.
    assert _frost_retreat_choices(st, rc.SEQUANI, rc.ROMANS) == [
        (True, rc.AEDUI_REGION)]


def test_possible_np_agreement_die_success_is_included_without_advancing_rng():
    from fs_bot.cards.divination_np import _frost_retreat_choices
    st = position()
    # NP Aedui sometimes agree for player Romans at score 10-12 (8.6.6).
    # Supply enough enemy Allies to lower the empty-map Roman score to 12.
    place_piece(st, rc.AEDUI_REGION, rc.AEDUI, rc.WARBAND, 3)
    from fs_bot.engine.victory import calculate_victory_score
    from fs_bot.board.pieces import get_available
    for tribe, info in st['tribes'].items():
        if calculate_victory_score(st, rc.ROMANS) <= 12:
            break
        region = rc.TRIBE_TO_REGION[tribe]
        owner = (rc.BELGAE if get_available(st, rc.BELGAE, rc.ALLY)
                 else rc.ARVERNI)
        place_piece(st, region, owner, rc.ALLY)
        info['allied_faction'] = owner
    refresh_all_control(st)
    assert 10 <= calculate_victory_score(st, rc.ROMANS) <= 12
    rng = st['rng'].getstate()
    assert (True, rc.AEDUI_REGION) in _frost_retreat_choices(st, rc.SEQUANI, rc.ROMANS)
    assert st['rng'].getstate() == rng
