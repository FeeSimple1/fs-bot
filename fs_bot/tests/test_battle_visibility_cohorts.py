"""A28/Diviciacus use each physical counter once; Battle reveals Hidden only."""
from copy import deepcopy

import pytest

from fs_bot import rules_consts as rc
from fs_bot.battle.combined import COMBINED_KEY, combined_force
from fs_bot.battle.losses import resolve_losses
from fs_bot.battle.resolve import _reveal_survivors
from fs_bot.board.pieces import (
    PieceError, count_pieces, count_pieces_by_state, get_available, place_piece,
    remove_piece,
)
from fs_bot.cards.card_effects import execute_event
from fs_bot.cards.edition import CARD_EDITIONS
from fs_bot.engine.diviciacus import KEY, defense_scope, eligible_regions, force_scope
from fs_bot.engine.execute import _execute_battle, _execute_event
from fs_bot.state.state_schema import build_initial_state, validate_state


def _state(scenario=rc.SCENARIO_ARIOVISTUS, *, edition='original'):
    state = build_initial_state(scenario, seed=205)
    state['card_edition'] = edition
    state['non_player_factions'] = set()
    state['resources'][rc.AEDUI] = 10
    if scenario in rc.BASE_SCENARIOS:
        execute_event(state, 38)
    else:
        place_piece(state, rc.SEQUANI, rc.AEDUI, rc.LEADER,
                    leader_name=rc.DIVICIACUS)
    return state


def _cohorts(state, visibility=rc.HIDDEN):
    for faction, piece, count in ((rc.AEDUI, rc.WARBAND, 6),
                                  (rc.ARVERNI, rc.WARBAND, 4),
                                  (rc.ROMANS, rc.AUXILIA, 2)):
        place_piece(state, rc.MANDUBII, faction, piece, count,
                    piece_state=(rc.REVEALED if piece == rc.AUXILIA
                                 and visibility == rc.SCOUTED else visibility))


def _event(state):
    state['current_card'] = 'A28'
    return _execute_event(state, rc.AEDUI, {'details': {
        'card_id': 'A28', 'event_params': {'battle_plan': [{
            'region': rc.MANDUBII, 'target_faction': rc.ROMANS}]}}}, human=True)


@pytest.mark.parametrize('scenario', [rc.SCENARIO_GREAT_REVOLT, rc.SCENARIO_ARIOVISTUS])
@pytest.mark.parametrize('attacker,score,agrees', [
    (rc.AEDUI, 12, False), (rc.AEDUI, 13, False),
    (rc.BELGAE, 12, True), (rc.BELGAE, 13, False),
])
def test_np_aedui_defense_consent_rejects_self_target_and_retains_score_limit(
        monkeypatch, scenario, attacker, score, agrees):
    """§8.6.8's exception applies during Roman defense as well as Command."""
    state = _state(scenario)
    _cohorts(state)
    state['non_player_factions'] = {rc.AEDUI, rc.ROMANS}
    monkeypatch.setattr('fs_bot.engine.victory.calculate_victory_score',
                        lambda *_: score)
    before = deepcopy(state['spaces'])
    rng = state['rng'].getstate()
    with defense_scope(state, rc.MANDUBII, attacker, rc.ROMANS):
        assert (KEY in state) is agrees
        assert count_pieces(state, rc.MANDUBII, rc.ROMANS, rc.AUXILIA) == (
            8 if agrees else 2)
    assert state['spaces'] == before and state['rng'].getstate() == rng
    assert KEY not in state


@pytest.mark.parametrize('scenario', [rc.SCENARIO_ARIOVISTUS, rc.SCENARIO_GALLIC_WAR])
@pytest.mark.parametrize('edition', CARD_EDITIONS)
@pytest.mark.parametrize('human_lender', [False, True])
def test_a28_battle_against_romans_resolves_np_refusal_or_human_lending(
        monkeypatch, scenario, edition, human_lender):
    state = _state(scenario, edition=edition)
    _cohorts(state)
    state['non_player_factions'] = {rc.ROMANS}
    if not human_lender:
        state['non_player_factions'].add(rc.AEDUI)
    monkeypatch.setattr('fs_bot.engine.victory.calculate_victory_score',
                        lambda *_: 12)
    requests = []

    def choose(board, faction, request):
        requests.append((faction, request))
        return True if request['kind'] == 'agreement' else None

    state['decision_agent'] = choose
    result = _event(state)
    battle = result['free_actions'][0]['result']
    assert result['executed'] and battle['executed']
    assert battle['errors'] == [] and battle['count'] == 1
    # Without the forbidden NP loan the combined ten Warbands eliminate
    # the two Auxilia. A human's agreed loan remains legal and survives.
    assert count_pieces(state, rc.MANDUBII, rc.ROMANS, rc.AUXILIA) == (
        2 if human_lender else 0)
    if human_lender:
        agreements = [request for faction, request in requests
                      if faction == rc.AEDUI and request['kind'] == 'agreement']
        assert agreements[0]['context']['targets'] == {rc.MANDUBII: [rc.AEDUI]}
    else:
        assert not any(request['kind'] == 'agreement' for _, request in requests)
    assert KEY not in state and COMBINED_KEY not in state
    assert validate_state(state) == []


@pytest.mark.parametrize('scenario', [rc.SCENARIO_ARIOVISTUS, rc.SCENARIO_GALLIC_WAR])
@pytest.mark.parametrize('human_lender', [False, True])
def test_a28_prior_loan_cannot_be_reassigned_to_opposing_defense(
        monkeypatch, scenario, human_lender):
    """§1.5.2 binds Aedui's first agreement for the whole A28 Event."""
    state = _state(scenario)
    _cohorts(state)
    place_piece(state, rc.MANDUBII, rc.BELGAE, rc.WARBAND, 1)
    state['non_player_factions'] = {rc.ROMANS}
    if not human_lender:
        state['non_player_factions'].add(rc.AEDUI)
    monkeypatch.setattr('fs_bot.engine.victory.calculate_victory_score',
                        lambda *_: 12)
    agreements = []

    def agree(board, faction, request):
        if request['kind'] == 'agreement':
            agreements.append((faction, request['request_type']))
            return True

    state['decision_agent'] = agree
    result = _execute_event(state, rc.BELGAE, {'details': {
        'card_id': 'A28', 'event_params': {'battle_plan': [{
            'region': rc.MANDUBII, 'target_faction': rc.ROMANS}]}}}, human=True)
    battle = result['free_actions'][0]['result']
    assert result['executed'] and battle['executed']
    assert battle['errors'] == [] and battle['count'] == 1
    assert agreements == ([(rc.AEDUI, 'admagetobriga_warbands')] if human_lender else [])
    assert count_pieces(state, rc.MANDUBII, rc.ROMANS, rc.AUXILIA) == 0
    for faction, count in ((rc.BELGAE, 1), (rc.AEDUI, 6), (rc.ARVERNI, 4)):
        assert count_pieces_by_state(
            state, rc.MANDUBII, faction, rc.WARBAND, rc.REVEALED) == count
    assert KEY not in state and COMBINED_KEY not in state
    assert validate_state(state) == []


@pytest.mark.parametrize('actor,lenders,borrower,eligible', [
    (rc.BELGAE, [rc.ARVERNI, rc.AEDUI], rc.ROMANS, False),
    (rc.AEDUI, [rc.ARVERNI], rc.ROMANS, True),
    (rc.AEDUI, [rc.ARVERNI, rc.ROMANS], rc.AEDUI, True),
])
def test_prior_loan_eligibility_is_regional_and_preserves_other_compositions(
        actor, lenders, borrower, eligible):
    state = _state()
    _cohorts(state)
    for faction, piece in ((rc.AEDUI, rc.WARBAND), (rc.ROMANS, rc.AUXILIA)):
        place_piece(state, rc.SEQUANI, faction, piece)
    before = deepcopy(state['spaces'])
    rng = state['rng'].getstate()
    state['decision_agent'] = lambda *_: pytest.fail('eligibility consumed live input')
    with combined_force(state, actor, {rc.MANDUBII: lenders}):
        regions = eligible_regions(state, borrower, 'defense')
        assert (rc.MANDUBII in regions) is eligible
        assert rc.SEQUANI in regions
    assert rc.MANDUBII in eligible_regions(state, borrower, 'defense')
    assert state['spaces'] == before and state['rng'].getstate() == rng


@pytest.mark.parametrize('visibility', [rc.HIDDEN, rc.REVEALED, rc.SCOUTED])
def test_opposing_diviciacus_cohort_is_reserved_for_its_own_side(visibility):
    """A28 attackers may remove/reveal Arverni, never loaned Aedui counters."""
    state = _state()
    _cohorts(state, visibility)
    aedui_pool = get_available(state, rc.AEDUI, rc.WARBAND)
    arverni_pool = get_available(state, rc.ARVERNI, rc.WARBAND)
    with combined_force(state, rc.AEDUI, {rc.MANDUBII: [rc.ARVERNI]}):
        with force_scope(state, rc.ROMANS, [rc.MANDUBII], 'defense'):
            assert count_pieces(state, rc.MANDUBII, rc.AEDUI, rc.WARBAND) == 4
            assert count_pieces(state, rc.MANDUBII, rc.ROMANS, rc.AUXILIA) == 8
            before = deepcopy(state['spaces'])
            with pytest.raises(PieceError, match='Not enough combined'):
                remove_piece(state, rc.MANDUBII, rc.AEDUI, rc.WARBAND, 1,
                             piece_state=visibility, physical_owner=rc.AEDUI)
            assert state['spaces'] == before
            result = resolve_losses(state, rc.MANDUBII, rc.AEDUI, 1)
            assert result['losses_taken'] == 1
            assert get_available(state, rc.ARVERNI, rc.WARBAND) == arverni_pool + 1
            assert get_available(state, rc.AEDUI, rc.WARBAND) == aedui_pool
            # Exercise the aggregate mutation route as well as explicit
            # owner loss selection. Both must respect the same reservation.
            remove_piece(state, rc.MANDUBII, rc.AEDUI, rc.WARBAND, 1,
                         piece_state=visibility)
            rng = state['rng'].getstate()
            _reveal_survivors(state, rc.MANDUBII, rc.AEDUI, rc.ROMANS)
            assert state['rng'].getstate() == rng
            expected = rc.REVEALED if visibility == rc.HIDDEN else visibility
            assert state[KEY]['pieces'][rc.MANDUBII][expected] == 6
    for faction, piece, count in ((rc.AEDUI, rc.WARBAND, 6),
                                  (rc.ARVERNI, rc.WARBAND, 2),
                                  (rc.ROMANS, rc.AUXILIA, 2)):
        physical_state = rc.REVEALED if piece == rc.AUXILIA and expected == rc.SCOUTED else expected
        assert count_pieces_by_state(state, rc.MANDUBII, faction, piece, physical_state) == count
    assert get_available(state, rc.ARVERNI, rc.WARBAND) == arverni_pool + 2
    assert validate_state(state) == []


@pytest.mark.parametrize('visibility', [rc.HIDDEN, rc.REVEALED, rc.SCOUTED])
def test_same_side_combined_and_converted_cohorts_reveal_once(visibility):
    state = _state()
    _cohorts(state, visibility)
    available = deepcopy(state['available'])
    rng = state['rng'].getstate()
    with combined_force(state, rc.AEDUI, {rc.MANDUBII: [rc.ARVERNI, rc.ROMANS]}):
        with force_scope(state, rc.AEDUI, [rc.MANDUBII]):
            assert count_pieces(state, rc.MANDUBII, rc.AEDUI, rc.WARBAND) == 12
            assert count_pieces(state, rc.MANDUBII, rc.AEDUI, rc.AUXILIA) == 0
            _reveal_survivors(state, rc.MANDUBII, rc.AEDUI, rc.GERMANS)
            expected = rc.REVEALED if visibility == rc.HIDDEN else visibility
            assert state[KEY]['pieces'][rc.MANDUBII][rc.REVEALED] == 2
    for faction, piece, count in ((rc.AEDUI, rc.WARBAND, 6),
                                  (rc.ARVERNI, rc.WARBAND, 4),
                                  (rc.ROMANS, rc.AUXILIA, 2)):
        physical_state = rc.REVEALED if piece == rc.AUXILIA and expected == rc.SCOUTED else expected
        assert count_pieces_by_state(state, rc.MANDUBII, faction, piece, physical_state) == count
    assert state['available'] == available and state['rng'].getstate() == rng
    assert validate_state(state) == []


@pytest.mark.parametrize('owner,piece', [(rc.AEDUI, rc.WARBAND),
                                      (rc.ARVERNI, rc.WARBAND),
                                      (rc.ROMANS, rc.AUXILIA)])
def test_same_side_loss_choice_keeps_explicit_physical_owner(owner, piece):
    state = _state()
    _cohorts(state)
    pools = deepcopy(state['available'])
    with combined_force(state, rc.AEDUI, {rc.MANDUBII: [rc.ARVERNI, rc.ROMANS]}):
        with force_scope(state, rc.AEDUI, [rc.MANDUBII]):
            result = resolve_losses(state, rc.MANDUBII, rc.AEDUI, 1,
                loss_order=[(rc.WARBAND, rc.HIDDEN, owner)])
            assert result['losses_taken'] == 1
            _reveal_survivors(state, rc.MANDUBII, rc.AEDUI, rc.GERMANS)
    pools[owner][piece] += 1
    assert state['available'] == pools
    for faction, physical_type, count in ((rc.AEDUI, rc.WARBAND, 6),
                                         (rc.ARVERNI, rc.WARBAND, 4),
                                         (rc.ROMANS, rc.AUXILIA, 2)):
        assert count_pieces_by_state(
            state, rc.MANDUBII, faction, physical_type, rc.REVEALED
        ) == count - (faction == owner)
    assert validate_state(state) == []


@pytest.mark.parametrize('scenario', [rc.SCENARIO_GREAT_REVOLT, rc.SCENARIO_ARIOVISTUS])
@pytest.mark.parametrize('nonplayer', [False, True])
def test_battle_keeps_scouted_survivors_for_both_sides(scenario, nonplayer):
    """§3.3.4 Step5 flips Hidden only; §4.2.2 preserves other Scout markers."""
    state = build_initial_state(scenario, seed=205)
    state['resources'][rc.AEDUI] = 10
    state['non_player_factions'] = {rc.AEDUI, rc.BELGAE} if nonplayer else set()
    for faction in (rc.AEDUI, rc.BELGAE):
        place_piece(state, rc.MANDUBII, faction, rc.WARBAND, 5)
        place_piece(state, rc.MANDUBII, faction, rc.WARBAND, 4,
                    piece_state=rc.SCOUTED)
    result = _execute_battle(state, rc.AEDUI, {
        'command': rc.CMD_BATTLE, 'sa': 'No SA', 'details': {
            'battle_plan': [{'region': rc.MANDUBII, 'target': rc.BELGAE}],
            'no_retreat': True}})
    assert result['executed'] and result['errors'] == []
    for faction, revealed, scouted in (
            ((rc.AEDUI, 5, 2), (rc.BELGAE, 5, 0)) if nonplayer else
            ((rc.AEDUI, 3, 4), (rc.BELGAE, 1, 4))):
        # §8.4.1 removes NPC own Scouted Warbands first. Any Scouted
        # survivors still keep their marker; only Hidden survivors flip.
        assert count_pieces_by_state(state, rc.MANDUBII, faction, rc.WARBAND, rc.SCOUTED) == scouted
        assert count_pieces_by_state(state, rc.MANDUBII, faction, rc.WARBAND, rc.REVEALED) == revealed
        assert count_pieces_by_state(state, rc.MANDUBII, faction, rc.WARBAND, rc.HIDDEN) == 0
    assert validate_state(state) == []
