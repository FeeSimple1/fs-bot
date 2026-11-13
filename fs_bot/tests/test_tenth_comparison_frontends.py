"""UI10-01 and UI10-02 through card display, Enlist, and saved choices."""

from copy import deepcopy
from io import StringIO
from argparse import Namespace

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces, count_pieces_by_state, place_piece
from fs_bot.cards.card_effects import _ally_tribe
from fs_bot.cli.app import display_card_result
from fs_bot.cli.dispatcher import make_decision_func
from fs_bot.cli.display import HumanTurnDisplay, format_action
from fs_bot.cli.human_plan import _collect_enlist_details
from fs_bot.commands.common import CommandError
from fs_bot.commands.enlist_free import execute_free_enlist
from fs_bot.engine.execute import execute_decision
from fs_bot.engine.game_engine import ACTION_COMMAND_SA, play_card
from fs_bot.state.serialize import decode, encode, load_game, save_game
from fs_bot.state.state_schema import build_initial_state, check_structural_integrity, validate_state
from fs_bot.tools.seat_session import DecisionPending, SeatSession
from fs_bot.tools import llm_seat


def _position(scenario=rc.SCENARIO_GREAT_REVOLT):
    state = build_initial_state(scenario, seed=6)
    state.update(current_card=20, next_card=21, deck=[21, 22])
    place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.FORT)
    return state


def _integrity(state):
    assert validate_state(state) == check_structural_integrity(state) == []


@pytest.mark.parametrize('target,raid', [(True, True), (True, False), (False, True)])
def test_completed_card_reports_live_entreat_and_omits_refused_build(target, raid):
    state = _position()
    state['non_player_factions'] = set(rc.GALLIC_FACTIONS) | {rc.ROMANS}
    state['resources'].update(dict.fromkeys(state['non_player_factions'], 10))
    state['resources'][rc.ARVERNI] = 0 if raid else 10
    place_piece(state, rc.MANDUBII, rc.ARVERNI, rc.LEADER, leader_name=rc.VERCINGETORIX)
    assert _ally_tribe(state, rc.TRIBE_AULERCI, rc.ARVERNI)
    if target:
        place_piece(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA)
    if raid:
        state['rng'].seed(1)
        place_piece(state, rc.BITURIGES, rc.ARVERNI, rc.WARBAND, 2)
        place_piece(state, rc.CARNUTES, rc.ARVERNI, rc.WARBAND, 3)
    _integrity(state)
    forecast = StringIO()
    choose = make_decision_func({}, StringIO(), forecast, pause=False)
    result = play_card(state, choose, execute=True)
    actions = result['turn_result']['actions_taken']
    arverni = actions[rc.ARVERNI]
    assert arverni['bot_action']['sa'] == ('No SA' if raid else rc.SA_ENTREAT)
    assert bool((arverni['execution'].get('sa_execution') or {}).get('executed')) == target
    before = deepcopy(result)
    completed = StringIO()
    display_card_result(result, completed, scenario=state['scenario'])
    lines = completed.getvalue().splitlines()
    line = next(row for row in lines if row.startswith('  Arverni:'))
    assert ('(SA: Entreat in Carnutes)' in line) == target
    if raid and target:
        romans = actions[rc.ROMANS]
        assert romans['bot_action']['sa'] == rc.SA_BUILD
        assert not romans['execution']['sa_execution']['executed']
        assert '(SA: Build)' in forecast.getvalue()
        assert all('(SA: Build' not in row for row in lines)
    assert result == before
    assert count_pieces(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA) == 0
    _integrity(state)


def _render_human(state, faction, plan):
    result = execute_decision(state, faction, {'player_action': plan})
    assert result['executed'], result
    card = {'card': state['current_card'], 'turn_result': {'actions_taken': {
        faction: {'action': ACTION_COMMAND_SA, 'player_action': plan, 'execution': result}}}}
    out = StringIO()
    display_card_result(card, out, scenario=state['scenario'])
    _integrity(state)
    return result, out.getvalue()


def _ambush_plan():
    return {
        'command': rc.CMD_BATTLE, 'regions': [rc.CARNUTES, rc.MANDUBII],
        'sa': rc.SA_AMBUSH, 'sa_regions': [rc.CARNUTES, rc.MANDUBII],
        'details': {'battle_plan': [
            {'region': rc.CARNUTES, 'target': rc.ROMANS},
            {'region': rc.MANDUBII, 'target': rc.ROMANS}]},
    }


def _ambush_position():
    state = _position()
    place_piece(state, rc.CARNUTES, rc.ARVERNI, rc.LEADER, leader_name=rc.VERCINGETORIX)
    place_piece(state, rc.CARNUTES, rc.ARVERNI, rc.WARBAND, 3)
    place_piece(state, rc.MANDUBII, rc.ARVERNI, rc.WARBAND, 2)
    place_piece(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA)
    place_piece(state, rc.MANDUBII, rc.ROMANS, rc.AUXILIA, 2)
    state['resources'][rc.ARVERNI] = 10
    return state


def test_human_ambush_reports_regions_where_it_occurred():
    state, plan = _ambush_position(), _ambush_plan()
    result, summary = _render_human(state, rc.ARVERNI, plan)
    assert result['battle_sa_executed']
    assert '(SA: Ambush in Carnutes)' in summary
    assert '(SA: Ambush in Carnutes, Mandubii)' in format_action(plan)


def test_old_midcard_save_verifies_replay_after_battle_display_update(tmp_path, capsys):
    from fs_bot.state.player_ownership import install
    from fs_bot.tools.seat_session import board_copy

    state = _ambush_position()
    state.update(current_card=31, next_card=32, deck=[32, 33])
    install(state, {rc.ARVERNI: 'Player 1', rc.BELGAE: 'Player 1'})
    path = tmp_path / 'save.json'
    save_game(state, path, meta={'seat': rc.ARVERNI, 'player_id': 'Player 1',
                                 'scenario': state['scenario'], 'seed': 6}, log=[])
    args = Namespace(dir=str(tmp_path))
    choice = {'action': ACTION_COMMAND_SA, 'player_action': _ambush_plan()}
    for _ in range(20):
        assert llm_seat.cmd_play(args) == 0
        state, meta, log = load_game(path, validate=True)
        pending = meta['assistant_session']['pending']
        request = decode(pending['request'])
        if request['kind'] == 'turn' and request['faction'] == rc.BELGAE:
            break
        llm_seat._write_inbox(tmp_path / 'queue.json', {
            'decision_id': pending['id'],
            'response': choice if request['kind'] == 'turn' else {'use_default': True}})
    else:
        pytest.fail('The second Eligible Faction did not receive its turn')
    turn = state['_card_turn']['actions_taken'][rc.ARVERNI]['execution']
    assert turn.pop('battle_sa')['regions'] == [rc.CARNUTES]
    snapshot = decode(pending['board'])
    snapshot['_card_turn']['actions_taken'][rc.ARVERNI]['execution'].pop('battle_sa')
    pending['board'] = encode(snapshot)
    save_game(state, path, meta=meta, log=log)
    output = tmp_path / 'replayed'
    assert llm_seat.cmd_replay(Namespace(dir=str(tmp_path), output_dir=str(output))) == 0
    assert 'Replay verified' in capsys.readouterr().out
    replayed, replay_meta, _ = load_game(output / 'save.json', validate=True)
    replayed['_card_turn']['actions_taken'][rc.ARVERNI]['execution'].pop('battle_sa')
    assert encode(board_copy(replayed)) == encode(board_copy(state))
    assert replay_meta['assistant_session']['pending']['id'] == pending['id']


def _enlist_position(scenario, with_hidden=True):
    state = _position(scenario)
    state['current_card'] = 55
    leader = rc.BODUOGNATUS if scenario in rc.ARIOVISTUS_SCENARIOS else rc.AMBIORIX
    place_piece(state, rc.CARNUTES, rc.BELGAE, rc.LEADER, leader_name=leader)
    place_piece(state, rc.CARNUTES, rc.BELGAE, rc.WARBAND)
    if with_hidden:
        place_piece(state, rc.CARNUTES, rc.GERMANS, rc.WARBAND)
    place_piece(state, rc.CARNUTES, rc.GERMANS, rc.WARBAND, piece_state=rc.SCOUTED)
    return state


def _enlist_march(selection):
    plan = {'type': 'german_march', 'origin': rc.CARNUTES, 'destination': rc.MANDUBII}
    if selection is not None:
        plan['warbands'] = selection
    return plan


def _german_cohorts(state, region):
    return tuple(count_pieces_by_state(state, region, rc.GERMANS, rc.WARBAND, ps)
                 for ps in (rc.HIDDEN, rc.REVEALED, rc.SCOUTED))


@pytest.mark.parametrize('scenario', rc.ALL_SCENARIOS)
def test_saved_exact_scouted_enlist_march_moves_that_cohort(scenario, tmp_path):
    state = _enlist_position(scenario)
    original = deepcopy(state)
    _integrity(state)
    choice = {'action': ACTION_COMMAND_SA, 'player_action': {
        'command': rc.CMD_RAID, 'regions': [rc.CARNUTES], 'sa': rc.SA_ENLIST,
        'sa_regions': [rc.CARNUTES], 'sa_timing': 'before',
        'details': {'raid_plan': [{'region': rc.CARNUTES, 'target': None}],
                    'enlist': _enlist_march({rc.SCOUTED: 1})}}}
    request = {'kind': 'turn', 'faction': rc.BELGAE, 'options': [ACTION_COMMAND_SA],
               'position': '1st_eligible'}
    session = SeatSession(state, {'seat': rc.BELGAE}, [], HumanTurnDisplay(StringIO()))
    session.checkpoint()
    with pytest.raises(DecisionPending):
        session.ask(state, rc.BELGAE, request)
    pending = deepcopy(session.data['pending'])
    path = tmp_path / 'enlist.json'
    save_game(state, path, meta=session.meta, log=session.log)
    restored, meta, log = load_game(path, validate=True)
    session = SeatSession(restored, meta, log, HumanTurnDisplay(StringIO()))
    assert session.data['pending'] == pending
    session.import_inbox({'decision_id': pending['id'], 'response': choice})
    session.checkpoint()
    accepted = session.ask(restored, rc.BELGAE, request)
    result = execute_decision(restored, rc.BELGAE, accepted)
    assert result['executed'] and result['sa_execution']['executed'] and not result['errors']
    session.finish()
    recorded = decode(log[0]['assistant_response'])
    assert recorded == choice
    assert execute_decision(original, rc.BELGAE, recorded) == result
    assert encode(original) == encode(restored)
    assert _german_cohorts(restored, rc.CARNUTES) == (1, 0, 0)
    assert _german_cohorts(restored, rc.MANDUBII) == (0, 1, 0)
    _integrity(restored)


@pytest.mark.parametrize('selection,remaining,arrivals', [
    ({rc.SCOUTED: 1}, (2, 0, 0), (0, 1, 0)),
    ({rc.HIDDEN: 1}, (1, 1, 0), (1, 0, 0)),
    ({rc.REVEALED: 1}, (1, 1, 0), (1, 0, 0)),
    (2, (0, 1, 0), (2, 0, 0)),
    (None, (0, 0, 0), (2, 1, 0)),
])
def test_base_enlist_march_flips_stayers_and_preserves_legacy_totals(selection, remaining, arrivals):
    state = _enlist_position(rc.SCENARIO_GREAT_REVOLT)
    place_piece(state, rc.CARNUTES, rc.GERMANS, rc.WARBAND, piece_state=rc.REVEALED)
    before_rng = state['rng'].getstate()
    result = execute_free_enlist(state, _enlist_march(selection))
    assert result['flipped'] == {'flipped_to_hidden': 1, 'scouted_to_revealed': 1}
    assert _german_cohorts(state, rc.CARNUTES) == remaining
    assert _german_cohorts(state, rc.MANDUBII) == arrivals
    assert state['rng'].getstate() == before_rng
    _integrity(state)


def test_base_enlist_invalid_cohort_refused_before_origin_flips():
    state = _enlist_position(rc.SCENARIO_GREAT_REVOLT)
    before = encode(state)
    with pytest.raises(CommandError, match='not present'):
        execute_free_enlist(state, _enlist_march({rc.SCOUTED: 2}))
    assert encode(state) == before


def test_base_terminal_collects_exact_enlist_march_and_reprompts_empty_group():
    state = _enlist_position(rc.SCENARIO_GREAT_REVOLT)
    before = encode(state)
    out = StringIO()
    regions, details = _collect_enlist_details(
        state, rc.BELGAE, StringIO('Carnutes\nMandubii\n0\n0\n0\n1\n'), out,
        _sub='german_march')
    assert regions == [rc.CARNUTES]
    assert details['enlist']['warbands'] == {rc.HIDDEN: 0, rc.REVEALED: 0, rc.SCOUTED: 1}
    assert 'Scouted German Warbands' in out.getvalue()
    assert 'Choose at least one Warband' in out.getvalue()
    assert encode(state) == before
    execute_free_enlist(state, details['enlist'])
    assert _german_cohorts(state, rc.CARNUTES) == (1, 0, 0)
    assert _german_cohorts(state, rc.MANDUBII) == (0, 1, 0)
    _integrity(state)
