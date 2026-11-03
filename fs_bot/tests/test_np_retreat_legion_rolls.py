"""§8.4.3: Roman Retreat must lower Legion exposure, not merely total Losses."""
from copy import deepcopy

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.control import refresh_all_control
from fs_bot.board.pieces import place_piece
from fs_bot.engine.execute import _decide_defender_retreat
from fs_bot.state.state_schema import build_initial_state


def position(*, warbands, auxilia, legions, fort=False, abatis=False,
             attacker=rc.ARVERNI, scenario=rc.SCENARIO_GREAT_REVOLT):
    state = build_initial_state(scenario, seed=84)
    state['non_player_factions'] = {rc.ROMANS, attacker}
    place_piece(state, rc.NERVII, attacker, rc.WARBAND, warbands)
    if auxilia:
        place_piece(state, rc.NERVII, rc.ROMANS, rc.AUXILIA, auxilia)
    if legions:
        place_piece(state, rc.NERVII, rc.ROMANS, rc.LEGION, legions, from_legions_track=True)
    if fort:
        place_piece(state, rc.NERVII, rc.ROMANS, rc.FORT)
    if abatis:
        state['markers'].setdefault(rc.NERVII, {})[rc.MARKER_ABATIS] = rc.ROMANS
    place_piece(state, rc.TREVERI, rc.ROMANS, rc.AUXILIA)
    refresh_all_control(state)
    return state


def decision(state):
    return _decide_defender_retreat(
        state, rc.NERVII, rc.ARVERNI, rc.ROMANS, False)


def test_auxilia_shielded_legions_do_not_cause_retreat():
    state = position(warbands=2, auxilia=2, legions=1)
    before = deepcopy(state)
    assert decision(state) == (False, None)
    assert state['rng'].getstate() == before['rng'].getstate()
    assert state['spaces'] == before['spaces']


def test_retreat_when_it_reduces_loss_rolls_on_legions():
    state = position(warbands=6, auxilia=2, legions=2)
    assert decision(state) == (True, rc.TREVERI)


@pytest.mark.parametrize('fort,abatis', [(True, False), (False, True)])
def test_retreat_static_absorber_shields_legions_even_when_total_losses_equal(fort, abatis):
    # Both stances suffer two Losses. Standing: Auxilia, then Legion.
    # Retreating: Fort/Abatis, then Auxilia, so no Legion roll is projected.
    state = position(warbands=8, auxilia=1, legions=2, fort=fort, abatis=abatis)
    assert decision(state) == (True, rc.TREVERI)


def test_lower_total_losses_with_unchanged_legion_exposure_do_not_force_retreat():
    state = position(warbands=4, auxilia=3, legions=1)
    assert decision(state) == (False, None)


def test_last_piece_survival_still_triggers_retreat_without_legions():
    state = position(warbands=2, auxilia=1, legions=0)
    assert decision(state) == (True, rc.TREVERI)


def test_attacker_abatis_does_not_reduce_roman_counterattack():
    # Romans take five Losses, inflict four, so ordinary half-loss criterion
    # does not apply. Reduce their counterattack with Abatis owned by attacker.
    state = position(warbands=10, auxilia=8, legions=0)
    state['markers'].setdefault(rc.NERVII, {})[rc.MARKER_ABATIS] = rc.ARVERNI
    # Counterattack ignores Abatis (it only protects a defender), so no
    # independent Retreat condition applies; this does not invent shielding.
    assert decision(state) == (False, None)


def test_ambush_still_forbids_retreat():
    state = position(warbands=6, auxilia=2, legions=2)
    assert _decide_defender_retreat(
        state, rc.NERVII, rc.ARVERNI, rc.ROMANS, True) == (False, None)


def test_german_phalanx_cancels_abatis_in_retreat_prediction():
    state = position(warbands=16, auxilia=1, legions=2, fort=True,
                     abatis=True, attacker=rc.GERMANS,
                     scenario=rc.SCENARIO_ARIOVISTUS)
    state['capabilities']['A31'] = rc.EVENT_SHADED
    # Four Losses in either stance. The Fort moves ahead of mobile pieces
    # on Retreat, but both Legions still roll; cancelled Abatis adds no shield.
    assert _decide_defender_retreat(
        state, rc.NERVII, rc.GERMANS, rc.ROMANS, False) == (False, None)
