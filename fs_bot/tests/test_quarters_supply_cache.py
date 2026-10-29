"""Quarters planning and application share actual-seat Supply declarations."""
from copy import deepcopy

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces, count_pieces_by_state, move_piece, place_piece
from fs_bot.bots.roman_bot import build_np_winter_relocations
from fs_bot.commands.rally import has_supply_line
from fs_bot.engine.quarters import (
    agreement_cache, apply_relocations, preview_relocations,
    validate_quarters_plan,
)
from fs_bot.engine.victory import calculate_victory_score
from fs_bot.state.serialize import encode
from fs_bot.state.setup import setup_scenario
from fs_bot.state.state_schema import build_initial_state, check_structural_integrity


def _player_roman_state(seed):
    state = setup_scenario(rc.SCENARIO_GREAT_REVOLT, seed=1)
    state['non_player_factions'] = {rc.AEDUI, rc.ARVERNI, rc.BELGAE}
    # Keep the published victory-score position, but concentrate all other
    # Roman mobile counters in Provincia to isolate one selected Supply route.
    for region in state['spaces']:
        if region == rc.PROVINCIA:
            continue
        for piece in (rc.LEADER, rc.LEGION):
            n = count_pieces(state, region, rc.ROMANS, piece)
            if n:
                move_piece(state, region, rc.PROVINCIA, rc.ROMANS, piece, n)
        for visibility in (rc.HIDDEN, rc.REVEALED):
            n = count_pieces_by_state(state, region, rc.ROMANS, rc.AUXILIA, visibility)
            if n:
                move_piece(state, region, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA,
                           n, piece_state=visibility)
    place_piece(state, rc.SEQUANI, rc.ROMANS, rc.AUXILIA)
    place_piece(state, rc.SEQUANI, rc.AEDUI, rc.WARBAND, 6)
    assert calculate_victory_score(state, rc.ROMANS) == 12
    assert check_structural_integrity(state) == []
    state['rng'].seed(seed)
    return state


def test_player_default_plan_and_actual_application_use_one_live_np_die():
    state = _player_roman_state(1)
    expected_rng = deepcopy(state['rng'])
    assert expected_rng.randint(1, 6) <= 4
    before = encode(state)
    with agreement_cache(state):
        plan = build_np_winter_relocations(state)
        assert plan[rc.ROMANS] == [(rc.AUXILIA, rc.SEQUANI, rc.PROVINCIA, 1)]
        after_plan_rng = state['rng'].getstate()
        assert after_plan_rng == expected_rng.getstate()
        # Pure validation neither resolves another declaration nor moves pieces.
        assert validate_quarters_plan(state, plan, faction=rc.ROMANS) == []
        assert state['rng'].getstate() == after_plan_rng
        assert encode(state['spaces']) == before['spaces']
        apply_relocations(state, rc.ROMANS, plan[rc.ROMANS])
        assert state['rng'].getstate() == after_plan_rng
    assert count_pieces(state, rc.SEQUANI, rc.ROMANS, rc.AUXILIA) == 0
    assert 'decision_agent' not in state
    assert check_structural_integrity(state) == []


@pytest.mark.parametrize('seed,accepted', [(1, True), (5, False)])
def test_confirmation_first_on_detached_board_advances_live_rng_once(seed, accepted):
    state = _player_roman_state(seed)
    moves = [(rc.AUXILIA, rc.SEQUANI, rc.PROVINCIA, 1)]
    before = encode(state)
    expected_rng = deepcopy(state['rng'])
    assert (expected_rng.randint(1, 6) <= 4) is accepted
    with agreement_cache(state):
        assert validate_quarters_plan(state, {rc.ROMANS: moves}) == []
        assert encode(state['rng']) == before['rng']
        assert encode(state['spaces']) == before['spaces']
        # Sequani is also adjacent to Roman-controlled Provincia, so this
        # relocation remains legal even when the separate Supply declaration
        # is refused. That refusal still must not be rerolled by planning.
        preview_relocations(state, rc.ROMANS, moves, confirm=True)
        # The detached confirmation shares the authoritative RNG; later
        # live planning sees its exact answer rather than rolling again.
        assert state['rng'].getstate() == expected_rng.getstate()
        assert has_supply_line(state, rc.SEQUANI) is accepted
        assert state['rng'].getstate() == expected_rng.getstate()
    assert encode(state['spaces']) == before['spaces']
    assert 'decision_agent' not in state


def test_np_roman_default_does_not_apply_player_score_die():
    state = _player_roman_state(5)
    state['non_player_factions'].add(rc.ROMANS)
    before_rng = state['rng'].getstate()
    with agreement_cache(state):
        plan = build_np_winter_relocations(state)
        apply_relocations(state, rc.ROMANS, plan[rc.ROMANS])
    assert count_pieces(state, rc.SEQUANI, rc.ROMANS, rc.AUXILIA) == 0
    assert state['rng'].getstate() == before_rng


@pytest.mark.parametrize('host,expected', [(rc.BELGAE, False), (rc.GERMANS, False),
                                          (rc.AEDUI, True)])
def test_external_agent_cannot_override_np_supply_policy_in_trusted_cache(host, expected):
    state = build_initial_state(rc.SCENARIO_ARIOVISTUS, seed=1)
    state['non_player_factions'] = {rc.ROMANS, host}
    place_piece(state, rc.SEQUANI, host, rc.WARBAND)
    calls = []

    def external(board, faction, request):
        calls.append(request)
        return not expected

    state['decision_agent'] = external
    with agreement_cache(state):
        assert has_supply_line(state, rc.SEQUANI) is expected
        assert has_supply_line(state, rc.SEQUANI) is expected
    assert calls == [] and state['decision_agent'] is external
