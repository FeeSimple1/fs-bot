"""§6.3/A6.3 human choices, relocation legality and exact Roman protection."""
import io
import pytest
from fs_bot import rules_consts as rc
from fs_bot.board.pieces import place_piece, count_pieces, count_pieces_by_state
from fs_bot.board.control import refresh_all_control
from fs_bot.state.state_schema import build_initial_state
from fs_bot.state.serialize import encode
from fs_bot.engine.quarters import (
    QuartersError, validate_quarters_plan, preview_relocations, quartering_allocations,
)
from fs_bot.engine.winter import quarters_phase, _apply_relocations, _quarters_roman_pay_or_roll


def state(scenario=rc.SCENARIO_GREAT_REVOLT, seed=1):
    st = build_initial_state(scenario, seed)
    st['non_player_factions'] = set(rc.FACTIONS)
    st['resources'][rc.ROMANS] = 20
    return st


def body(st):
    return encode({k:v for k,v in st.items() if k != 'decision_agent'})


@pytest.mark.parametrize('piece,count,destination', [
    (rc.ALLY, 1, rc.ATREBATES), (rc.CITADEL, 1, rc.ATREBATES),
    (rc.WARBAND, -1, rc.ATREBATES), (rc.WARBAND, True, rc.ATREBATES),
    (rc.WARBAND, 1.5, rc.ATREBATES), (rc.WARBAND, 999, rc.ATREBATES),
    (rc.WARBAND, 1, rc.PROVINCIA), (rc.WARBAND, 1, rc.CISALPINA),
    (rc.WARBAND, 1, rc.MORINI),
])
def test_illegal_relocation_never_mutates(piece, count, destination):
    st = state()
    place_piece(st, rc.MORINI, rc.BELGAE, rc.WARBAND, 2)
    place_piece(st, rc.ATREBATES, rc.BELGAE, rc.WARBAND, 1)
    before = body(st)
    moves = [(piece, rc.MORINI, destination, count)]
    assert validate_quarters_plan(st, {rc.BELGAE:moves}, faction=rc.BELGAE)
    with pytest.raises(QuartersError):
        _apply_relocations(st, rc.BELGAE, moves)
    assert body(st) == before


def test_later_bad_relocation_does_not_apply_earlier_valid_move():
    st = state()
    place_piece(st, rc.MORINI, rc.BELGAE, rc.WARBAND, 2)
    place_piece(st, rc.ATREBATES, rc.BELGAE, rc.WARBAND, 1)
    before = body(st)
    with pytest.raises(QuartersError):
        _apply_relocations(st, rc.BELGAE, [(rc.WARBAND, rc.MORINI, rc.ATREBATES, 1),
                                          (rc.ALLY, rc.ATREBATES, rc.PROVINCIA, 1)])
    assert body(st) == before


def test_arrivals_cannot_take_another_adjacent_relocation():
    st = state()
    place_piece(st, rc.MORINI, rc.BELGAE, rc.WARBAND, 2)
    place_piece(st, rc.ATREBATES, rc.BELGAE, rc.LEADER, leader_name=rc.AMBIORIX)
    place_piece(st, rc.MANDUBII, rc.BELGAE, rc.WARBAND, 1)
    moves = [(rc.WARBAND, rc.MORINI, rc.ATREBATES, 2),
             (rc.WARBAND, rc.ATREBATES, rc.MANDUBII, 2)]
    assert validate_quarters_plan(st, {rc.BELGAE:moves})


@pytest.mark.parametrize('marker', [None, rc.MARKER_DEVASTATED])
def test_destination_requires_control_and_no_devastation(marker):
    st = state()
    place_piece(st, rc.MORINI, rc.BELGAE, rc.WARBAND, 2)
    if marker:
        place_piece(st, rc.ATREBATES, rc.BELGAE, rc.WARBAND, 1)
        st['markers'][rc.ATREBATES] = {marker: True}
    assert validate_quarters_plan(st, {rc.BELGAE:[(rc.WARBAND, rc.MORINI, rc.ATREBATES, 1)]})


def test_preview_never_requests_agreement_and_rejection_is_atomic():
    st = state()
    place_piece(st, rc.MORINI, rc.BELGAE, rc.WARBAND, 1)
    place_piece(st, rc.ATREBATES, rc.AEDUI, rc.WARBAND, 5)
    calls = []
    def agent(board, faction, request):
        calls.append((faction, request['request_type']))
        return False
    st['decision_agent'] = agent
    before = body(st)
    moves = [(rc.WARBAND, rc.MORINI, rc.ATREBATES, 1)]
    assert validate_quarters_plan(st, {rc.BELGAE:moves}) == []
    assert calls == [] and body(st) == before
    with pytest.raises(QuartersError, match='did not agree'):
        _apply_relocations(st, rc.BELGAE, moves)
    assert calls == [(rc.AEDUI, 'quarters')] and body(st) == before


def test_agreed_relocation_preserves_piece_visibility():
    st = state()
    place_piece(st, rc.MORINI, rc.BELGAE, rc.WARBAND, 2, piece_state=rc.REVEALED)
    place_piece(st, rc.ATREBATES, rc.AEDUI, rc.WARBAND, 5)
    st['decision_agent'] = lambda *_: True
    _apply_relocations(st, rc.BELGAE, [(rc.WARBAND, rc.MORINI, rc.ATREBATES, 2)])
    assert count_pieces_by_state(st, rc.ATREBATES, rc.BELGAE, rc.WARBAND, rc.REVEALED) == 2


def test_roman_adjacent_step_then_supply_line_to_provincia():
    st = state()
    place_piece(st, rc.MANDUBII, rc.ROMANS, rc.LEGION, 1, from_legions_track=True)
    place_piece(st, rc.AEDUI_REGION, rc.ROMANS, rc.AUXILIA, 1)
    place_piece(st, rc.PROVINCIA, rc.ROMANS, rc.FORT)
    moves = [(rc.LEGION, rc.MANDUBII, rc.AEDUI_REGION, 1),
             (rc.LEGION, rc.AEDUI_REGION, rc.PROVINCIA, 1)]
    _apply_relocations(st, rc.ROMANS, moves)
    assert count_pieces(st, rc.PROVINCIA, rc.ROMANS, rc.LEGION) == 1


def test_roman_leader_may_relocate_to_provincia_without_supply():
    st = state()
    place_piece(st, rc.MORINI, rc.ROMANS, rc.LEADER, leader_name=rc.CAESAR)
    place_piece(st, rc.MORINI, rc.BELGAE, rc.WARBAND, 5)
    _apply_relocations(st, rc.ROMANS, [(rc.LEADER, rc.MORINI, rc.PROVINCIA, 1)])
    assert count_pieces(st, rc.PROVINCIA, rc.ROMANS, rc.LEADER) == 1


@pytest.mark.parametrize('faction,scenario', [(rc.GERMANS,rc.SCENARIO_GREAT_REVOLT),
                                           (rc.ARVERNI,rc.SCENARIO_ARIOVISTUS)])
def test_game_run_faction_cannot_submit_quarters_plan(faction, scenario):
    assert validate_quarters_plan(state(scenario), {faction:[]})


def test_human_cannot_choose_other_factions_quarters():
    st = state()
    assert validate_quarters_plan(st, {rc.ROMANS:[]}, faction=rc.BELGAE)


@pytest.mark.parametrize('decisions', [
    {rc.MORINI:{'pay':-1}}, {rc.MORINI:{'pay':True}},
    {rc.MORINI:{'roll':-1}}, {rc.MORINI:{'pay':1.5}},
    {'_pay_order':[rc.MORINI,rc.MORINI]},
    {rc.MORINI:{'pay_pieces':[(rc.LEGION,None,99)]}},
])
def test_invalid_payment_is_rejected_without_resources_or_rng_changes(decisions):
    st = state()
    place_piece(st, rc.MORINI, rc.ROMANS, rc.LEGION, 2, from_legions_track=True)
    before = body(st)
    with pytest.raises(QuartersError):
        _quarters_roman_pay_or_roll(st, decisions)
    assert body(st) == before


def test_paid_legion_is_not_removed_when_unpaid_auxilia_fails_its_roll():
    st = state(seed=1)  # first roll=2
    place_piece(st, rc.MORINI, rc.ROMANS, rc.LEGION, 1, from_legions_track=True)
    place_piece(st, rc.MORINI, rc.ROMANS, rc.AUXILIA, 1, piece_state=rc.REVEALED)
    res = _quarters_roman_pay_or_roll(st, {rc.MORINI:{'pay_pieces':[(rc.LEGION,None,1)]}})
    assert count_pieces(st, rc.MORINI, rc.ROMANS, rc.LEGION) == 1
    assert count_pieces(st, rc.MORINI, rc.ROMANS, rc.AUXILIA) == 0
    assert res['rolls'][rc.MORINI]['pieces'] == [(rc.AUXILIA,rc.REVEALED)]
    assert st['resources'][rc.ROMANS] == 18


def test_free_legion_is_not_removed_when_unprotected_auxilia_rolls():
    st = state(seed=1)
    place_piece(st, rc.MORINI, rc.ROMANS, rc.LEGION, 1, from_legions_track=True)
    place_piece(st, rc.MORINI, rc.ROMANS, rc.AUXILIA, 1)
    place_piece(st, rc.MORINI, rc.ROMANS, rc.FORT)
    _quarters_roman_pay_or_roll(st, {rc.MORINI:{'free_pieces':[(rc.LEGION,None,1)]}})
    assert count_pieces(st, rc.MORINI, rc.ROMANS, rc.LEGION) == 1
    assert count_pieces(st, rc.MORINI, rc.ROMANS, rc.AUXILIA) == 0


def test_failed_legion_roll_goes_to_fallen():
    st = state(seed=1)
    place_piece(st, rc.MORINI, rc.ROMANS, rc.LEGION, 1, from_legions_track=True)
    _quarters_roman_pay_or_roll(st)
    assert st['fallen_legions'] == 1


@pytest.mark.parametrize('scenario,expected', [
    (rc.SCENARIO_GREAT_REVOLT,[rc.BELGAE,rc.AEDUI,rc.ARVERNI,rc.ROMANS]),
    (rc.SCENARIO_ARIOVISTUS,[rc.BELGAE,rc.AEDUI,rc.GERMANS,rc.ROMANS]),
])
def test_every_human_receives_quarters_decision_in_rule_order(scenario, expected):
    st = state(scenario)
    st['non_player_factions'] = set()
    calls = []
    def agent(board, faction, request):
        if request['kind'] == 'quarters_plan':
            calls.append(faction)
            return {faction:[]}
    st['decision_agent'] = agent
    quarters_phase(st)
    assert calls == expected


def test_terminal_quarters_menu_allows_explicit_stay_and_paid_legion():
    from fs_bot.cli.reactive import make_cli_reactive
    st = state()
    place_piece(st, rc.MORINI, rc.ROMANS, rc.LEGION, 1, from_legions_track=True)
    place_piece(st, rc.MORINI, rc.ROMANS, rc.AUXILIA, 1)
    out = io.StringIO()
    agent = make_cli_reactive([rc.ROMANS], io.StringIO('3\n2\n1\n'), out)
    plan = agent(st, rc.ROMANS, {'kind':'quarters_plan','faction':rc.ROMANS})
    assert plan[rc.ROMANS] == []
    assert plan[rc.ROMANS+'_quartering'][rc.MORINI]['pay_pieces'] == [(rc.LEGION,None,1)]
    assert validate_quarters_plan(st, plan, faction=rc.ROMANS) == []


def test_terminal_quarters_eof_still_interrupts():
    from fs_bot.cli.reactive import make_cli_reactive
    with pytest.raises(EOFError):
        make_cli_reactive([rc.BELGAE], io.StringIO(''), io.StringIO())(
            state(), rc.BELGAE, {'kind':'quarters_plan','faction':rc.BELGAE})


def test_roman_leader_exception_does_not_supply_other_pieces_in_same_origin():
    st = state()
    place_piece(st, rc.MORINI, rc.ROMANS, rc.LEADER, leader_name=rc.CAESAR)
    place_piece(st, rc.MORINI, rc.ROMANS, rc.LEGION, 1, from_legions_track=True)
    place_piece(st, rc.MORINI, rc.BELGAE, rc.WARBAND, 5)
    st['decision_agent'] = lambda *_: False
    before = body(st)
    with pytest.raises(QuartersError, match='Supply Line'):
        _apply_relocations(st, rc.ROMANS, [(rc.LEADER,rc.MORINI,rc.PROVINCIA,1),
                                          (rc.LEGION,rc.MORINI,rc.PROVINCIA,1)])
    assert body(st) == before


def test_full_phase_plan_does_not_revalidate_already_completed_faction_moves():
    st = state()
    place_piece(st, rc.MORINI, rc.BELGAE, rc.WARBAND, 2)
    place_piece(st, rc.ATREBATES, rc.BELGAE, rc.WARBAND, 1)
    quarters_phase(st, {rc.BELGAE:[(rc.WARBAND,rc.MORINI,rc.ATREBATES,2)]})
    assert count_pieces(st, rc.MORINI, rc.BELGAE, rc.WARBAND) == 0
    assert count_pieces(st, rc.ATREBATES, rc.BELGAE, rc.WARBAND) == 3


def test_gallia_togata_marker_allows_quarters_out_of_cisalpina():
    st = state()
    st['markers'][rc.CISALPINA] = {rc.MARKER_GALLIA_TOGATA:True}
    place_piece(st, rc.CISALPINA, rc.ROMANS, rc.LEADER, leader_name=rc.CAESAR)
    _apply_relocations(st, rc.ROMANS, [(rc.LEADER,rc.CISALPINA,rc.PROVINCIA,1)])
    assert count_pieces(st, rc.PROVINCIA, rc.ROMANS, rc.LEADER) == 1


def test_execution_consumes_agreement_rng_but_validation_does_not():
    st = state(seed=1)
    place_piece(st, rc.MORINI, rc.BELGAE, rc.WARBAND, 1)
    place_piece(st, rc.ATREBATES, rc.AEDUI, rc.WARBAND, 5)
    calls = []
    def rolled_consent(board, faction, request):
        calls.append(board['rng'].randint(1,6))
        return True
    st['decision_agent'] = rolled_consent
    rng_before = st['rng'].getstate()
    moves = [(rc.WARBAND,rc.MORINI,rc.ATREBATES,1)]
    assert validate_quarters_plan(st,{rc.BELGAE:moves}) == []
    assert st['rng'].getstate() == rng_before and calls == []
    _apply_relocations(st,rc.BELGAE,moves)
    assert len(calls) == 1 and st['rng'].getstate() != rng_before
