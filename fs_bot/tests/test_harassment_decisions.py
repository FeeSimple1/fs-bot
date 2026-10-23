"""Human Harassment choices follow §§3.2.2, 3.2.3, 3.3.2, and replay exactly."""
from copy import deepcopy
from io import StringIO

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import place_piece, count_pieces, get_leader_in_region
from fs_bot.cards.card_text import get_card_text
from fs_bot.cli import app
from fs_bot.cli.display import HumanTurnDisplay
from fs_bot.commands.march import resolve_harassment
from fs_bot.engine.agent import HARASSMENT_LOSS
from fs_bot.engine.execute import _march_with_harassment, _resolve_seize_harassment
from fs_bot.engine.game_engine import _action_transaction, get_sop_factions
from fs_bot.state.serialize import encode, decode, save_game, load_game
from fs_bot.state.state_schema import build_initial_state
from fs_bot.tools.seat_session import SeatSession, DecisionPending, board_copy


def board(seed=1, scenario=rc.SCENARIO_ARIOVISTUS, faction=rc.ROMANS):
    st = build_initial_state(scenario, seed=seed)
    st['non_player_factions'] = set(get_sop_factions(st)) - {faction}
    st['current_card'], st['next_card'] = (4, 5)
    return st


def romans(st, region=rc.SEQUANI, aux=1, legions=1, leader=True):
    if aux:
        place_piece(st, region, rc.ROMANS, rc.AUXILIA, aux)
    if legions:
        place_piece(st, region, rc.ROMANS, rc.LEGION, legions, from_legions_track=True)
    if leader:
        place_piece(st, region, rc.ROMANS, rc.LEADER, leader_name=rc.CAESAR)
    return {rc.AUXILIA: aux, rc.LEGION: legions,
            rc.LEADER: rc.CAESAR if leader else None}


def answers(st, choices):
    pending, seen = iter(choices), []
    def agent(state, faction, request):
        if request['kind'] != HARASSMENT_LOSS:
            return None
        seen.append((faction, deepcopy(request)))
        return {'choice': next(pending)}
    st['decision_agent'] = agent
    return seen


def harassment(st, group, warbands=3, faction=rc.ROMANS):
    return resolve_harassment(st, rc.SEQUANI, faction, group,
                             harassing_factions=[(rc.GERMANS, warbands)])


@pytest.mark.parametrize('scenario', [rc.SCENARIO_GREAT_REVOLT, rc.SCENARIO_ARIOVISTUS])
@pytest.mark.parametrize('target', [rc.LEGION, rc.LEADER])
def test_human_rolls_despite_auxilia_then_selects_failed_hard_casualty(scenario, target):
    st = board(scenario=scenario)
    group = romans(st)
    seen = answers(st, ['roll', target])
    result = harassment(st, group)
    assert result['losses_by_faction'][0]['removals'] == [(target, 1, 2)]
    assert [r['phase'] for _, r in seen] == ['absorb', 'remove']
    assert seen[0][1]['options'] == [rc.AUXILIA, 'roll']
    assert seen[1][1]['options'] == [rc.LEGION, rc.LEADER]
    assert count_pieces(st, rc.SEQUANI, rc.ROMANS, rc.AUXILIA) == 1
    assert count_pieces(st, rc.SEQUANI, rc.ROMANS, target) == 0
    assert st['fallen_legions'] == (1 if target == rc.LEGION else 0)
    assert group[target] == (None if target == rc.LEADER else 0)


def test_successful_roll_keeps_all_pieces_and_never_requests_a_casualty():
    st = board(seed=5)
    group = romans(st)
    seen = answers(st, ['roll'])
    result = harassment(st, group)
    assert result['total_pieces_removed'] == 0
    assert result['losses_by_faction'][0]['removals'] == [(rc.LEGION, 0, 5)]
    assert len(seen) == 1 and group == {rc.AUXILIA: 1, rc.LEGION: 1, rc.LEADER: rc.CAESAR}


def test_np_and_explicit_default_keep_soft_before_roll_without_rng_draw():
    for mode in ('np', 'none', 'default'):
        st = board()
        group = romans(st)
        before_rng = st['rng'].getstate()
        seen = []
        if mode == 'np':
            st['non_player_factions'].add(rc.ROMANS)
            st['decision_agent'] = lambda *args: seen.append(args)
        elif mode == 'default':
            st['decision_agent'] = lambda *args: {'use_default': True}
        result = harassment(st, group)
        assert result['losses_by_faction'][0]['removals'] == [(rc.AUXILIA, 1, None)]
        assert st['rng'].getstate() == before_rng and not seen


def test_vercingetorix_may_roll_for_leader_instead_of_warband():
    st = board(faction=rc.ARVERNI, scenario=rc.SCENARIO_GREAT_REVOLT)
    place_piece(st, rc.SEQUANI, rc.ARVERNI, rc.LEADER, leader_name=rc.VERCINGETORIX)
    place_piece(st, rc.SEQUANI, rc.ARVERNI, rc.WARBAND, 1)
    group = {rc.WARBAND: 1, rc.LEADER: rc.VERCINGETORIX}
    seen = answers(st, ['roll'])
    harassment(st, group, faction=rc.ARVERNI)
    assert seen[0][1]['options'] == [rc.WARBAND, 'roll']
    assert count_pieces(st, rc.SEQUANI, rc.ARVERNI, rc.WARBAND) == 1
    assert get_leader_in_region(st, rc.SEQUANI, rc.ARVERNI) is None


def driver(session):
    def callback(*args):
        pass
    callback.transaction_checkpoint = session.checkpoint
    callback.transaction_restore = session.restore
    return callback


def march_state():
    st = board()
    romans(st, rc.PROVINCIA, aux=2)
    place_piece(st, rc.SEQUANI, rc.ARVERNI, rc.WARBAND, 6)
    return st


def march(st):
    return _march_with_harassment(st, rc.ROMANS, rc.PROVINCIA,
                                  [rc.SEQUANI, rc.AEDUI_REGION])


def test_actual_march_save_after_roll_resumes_and_replays_exact_rng(tmp_path):
    st = march_state()
    output = StringIO()
    view = HumanTurnDisplay(output)
    view.remember(st, [rc.ROMANS])
    session = SeatSession(st, {'seat': rc.ROMANS}, [], view)
    st['decision_agent'] = session.reactive
    session.import_inbox([{'response': {'choice': 'roll'}}])
    before = encode(board_copy(st))
    with pytest.raises(DecisionPending):
        with _action_transaction(st, driver(session)):
            march(st)
    assert encode(board_copy(st)) == before
    request = decode(session.data['pending']['request'])
    assert request['kind'] == HARASSMENT_LOSS
    assert request['phase'] == 'remove' and request['roll'] == 2
    assert len(session.data['journal']) == 1
    text = output.getvalue()
    assert 'changes since your last decision' in text
    for card in (4, 5):
        for line in get_card_text(card, st['scenario']).splitlines():
            assert line in text
    save_game(st, tmp_path / 'harassment.json', meta=session.meta, log=session.log)
    restored, meta, log = load_game(tmp_path / 'harassment.json')
    resumed = SeatSession(restored, meta, log, HumanTurnDisplay(StringIO()))
    restored['decision_agent'] = resumed.reactive
    resumed.import_inbox([{'response': {'choice': rc.LEADER}},
                          {'response': {'choice': 'roll'}}])
    with _action_transaction(restored, driver(resumed)):
        assert march(restored) == rc.AEDUI_REGION
    resumed.finish()
    assert len(log) == 3
    assert count_pieces(restored, rc.AEDUI_REGION, rc.ROMANS, rc.AUXILIA) == 2
    assert count_pieces(restored, rc.AEDUI_REGION, rc.ROMANS, rc.LEGION) == 1
    assert get_leader_in_region(restored, rc.AEDUI_REGION, rc.ROMANS) is None
    replay, entries = march_state(), iter(log)
    seen = []
    def recorded(board, faction, request):
        if faction != rc.ROMANS:
            return None
        entry = next(entries)
        seen.append((decode(entry['assistant_request']), dict(request, faction=faction)))
        return decode(entry['assistant_response'])
    replay['decision_agent'] = recorded
    march(replay)
    assert all(expected == actual for expected, actual in seen)
    assert len(seen) == 3 and next(entries, None) is None
    assert encode(board_copy(replay)) == encode(board_copy(restored))


@pytest.mark.parametrize('choice', [rc.FORT, rc.ALLY, rc.LEADER, None, {'bad': 1}])
def test_invalid_assistant_loss_preserves_board_rng_pending_and_inbox(choice):
    st = march_state()
    session = SeatSession(st, {'seat': rc.ROMANS}, [], HumanTurnDisplay(StringIO()))
    st['decision_agent'] = session.reactive
    response = {'choice': choice}
    session.import_inbox([{'response': response}])
    before = encode(board_copy(st))
    with pytest.raises(DecisionPending):
        with _action_transaction(st, driver(session)):
            march(st)
    assert session.error and not session.data['journal']
    assert session.data['pending']['id'] == 'd000001'
    assert session.data['queue'] == [{'response': response}]
    assert encode(board_copy(st)) == before


@pytest.mark.parametrize('choice', ['roll', rc.AUXILIA, None])
def test_terminal_choice_displays_cards_changes_board_and_replays(monkeypatch, tmp_path, choice):
    seen = []
    def card(st, decision, *, execute):
        # Fixed isolated board allows the real engine's Harassment decisions
        # to be exercised through the terminal's journaling and display.
        agent = st['decision_agent']
        cards = st['current_card'], st['next_card']
        st.clear()
        st.update(board())
        st['decision_agent'] = agent
        st['current_card'], st['next_card'] = cards
        st['resources'][rc.ROMANS] += 1
        group = romans(st, leader=False)
        seen.append((st['current_card'], st['next_card']))
        harassment(st, group)
        return {'card': st['current_card'], 'game_over': True}
    monkeypatch.setattr(app, 'play_card', card)
    saved, output = tmp_path / 'terminal.json', StringIO()
    label = ('Use bot default' if choice is None else
             'Roll for a hard piece' if choice == 'roll' else f'Remove {choice}')
    assert app.main(['--scenario', rc.SCENARIO_ARIOVISTUS, '--seed', '1',
                     '--bots', 'Aedui,Belgae,Germans', '--save', str(saved)],
                    stdin=StringIO('board\n' + label + '\n'), stdout=output) == 0
    _, _, log = load_game(saved)
    assert len(log) == 1 and log[0]['reactive'] == HARASSMENT_LOSS
    text = output.getvalue().split('Harassment Loss?')[0]
    assert 'changes since your last decision' in text
    for card_id in seen[0]:
        for line in get_card_text(card_id, rc.SCENARIO_ARIOVISTUS).splitlines():
            assert line in text
    assert output.getvalue().count('AVAILABLE PIECES') >= 2
    assert app.main(['--replay', str(saved)], stdin=StringIO(''), stdout=StringIO()) == 0


def seize_board(region=rc.SEQUANI, seed=1):
    st = board(seed=seed)
    romans(st, region)
    place_piece(st, region, rc.ARVERNI, rc.WARBAND, 3)
    place_piece(st, region, rc.ROMANS, rc.FORT)
    return st


@pytest.mark.parametrize('target', [rc.FORT, rc.LEGION, rc.LEADER])
def test_seize_human_chooses_roll_then_any_removable_hard_target(target):
    st = seize_board()
    seen = answers(st, ['roll', target])
    result = _resolve_seize_harassment(st, rc.SEQUANI)
    assert result == [{'by': rc.ARVERNI, 'choice': 'roll', 'removed': target}]
    assert seen[1][1]['options'] == [rc.FORT, rc.LEGION, rc.LEADER]
    assert count_pieces(st, rc.SEQUANI, rc.ROMANS, rc.AUXILIA) == 1
    assert count_pieces(st, rc.SEQUANI, rc.ROMANS, target) == 0


def test_seize_can_select_which_ally_instead_of_auxilia_and_keeps_tribes_in_sync():
    st = board()
    romans(st, rc.NERVII, leader=False)
    tribes = sorted(t for t, region in rc.TRIBE_TO_REGION.items() if region == rc.NERVII)
    assert len(tribes) >= 2
    for tribe in tribes[:2]:
        place_piece(st, rc.NERVII, rc.ROMANS, rc.ALLY)
        st['tribes'][tribe]['allied_faction'] = rc.ROMANS
    place_piece(st, rc.NERVII, rc.ARVERNI, rc.WARBAND, 3)
    seen = answers(st, [rc.ALLY, tribes[1]])
    _resolve_seize_harassment(st, rc.NERVII)
    assert seen[0][1]['options'] == [rc.AUXILIA, rc.ALLY, 'roll']
    assert seen[1][1]['phase'] == 'ally'
    assert st['tribes'][tribes[1]]['allied_faction'] is None
    assert st['tribes'][tribes[0]]['allied_faction'] == rc.ROMANS
    assert count_pieces(st, rc.NERVII, rc.ROMANS, rc.ALLY) == 1
    assert count_pieces(st, rc.NERVII, rc.ROMANS, rc.AUXILIA) == 1


def test_seize_permanent_provincia_fort_allows_roll_but_is_never_offered_as_casualty():
    st = seize_board(rc.PROVINCIA)
    seen = answers(st, ['roll', rc.LEADER])
    _resolve_seize_harassment(st, rc.PROVINCIA)
    assert seen[1][1]['options'] == [rc.LEGION, rc.LEADER]
    assert count_pieces(st, rc.PROVINCIA, rc.ROMANS, rc.FORT) == 1
    lone = board()
    place_piece(lone, rc.PROVINCIA, rc.ROMANS, rc.FORT)
    place_piece(lone, rc.PROVINCIA, rc.ARVERNI, rc.WARBAND, 3)
    result = _resolve_seize_harassment(lone, rc.PROVINCIA)
    assert result[0]['choice'] == 'roll' and result[0]['removed'] is None
    assert count_pieces(lone, rc.PROVINCIA, rc.ROMANS, rc.FORT) == 1


@pytest.mark.parametrize('piece,faction,scenario', [
    (rc.AUXILIA, rc.ROMANS, rc.SCENARIO_ARIOVISTUS),
    (rc.WARBAND, rc.ARVERNI, rc.SCENARIO_GREAT_REVOLT),
])
def test_human_selects_actual_soft_visibility_and_np_removes_reverse_priority(piece, faction, scenario):
    for human in (True, False):
        st = board(scenario=scenario, faction=faction)
        for visibility in (rc.HIDDEN, rc.REVEALED, rc.SCOUTED):
            place_piece(st, rc.SEQUANI, faction, piece, piece_state=visibility)
        group = {piece: 3}
        if human:
            seen = answers(st, [rc.HIDDEN])
        else:
            st['non_player_factions'].add(faction)
        harassment(st, group, faction=faction)
        from fs_bot.board.pieces import count_pieces_by_state
        removed = rc.HIDDEN if human else rc.SCOUTED
        assert count_pieces_by_state(st, rc.SEQUANI, faction, piece, removed) == 0
        assert group[piece] == 2
        if human:
            assert seen[0][1]['phase'] == 'piece_state'
            assert seen[0][1]['options'] == [rc.SCOUTED, rc.REVEALED, rc.HIDDEN]


def test_march_soft_casualty_uses_carried_visibility_and_never_resident_piece():
    st = board(scenario=rc.SCENARIO_GREAT_REVOLT, faction=rc.ARVERNI)
    place_piece(st, rc.SEQUANI, rc.ARVERNI, rc.WARBAND, 3, piece_state=rc.HIDDEN)
    place_piece(st, rc.SEQUANI, rc.ARVERNI, rc.WARBAND, 2, piece_state=rc.REVEALED)
    group = {rc.WARBAND: 2, '_march_visibility': {
        rc.WARBAND: {rc.HIDDEN: 0, rc.REVEALED: 2, rc.SCOUTED: 0}}}
    seen = answers(st, [])
    harassment(st, group, faction=rc.ARVERNI)
    from fs_bot.board.pieces import count_pieces_by_state
    assert not seen  # only one legal physical casualty state, no human choice
    assert count_pieces_by_state(st, rc.SEQUANI, rc.ARVERNI, rc.WARBAND, rc.HIDDEN) == 3
    assert count_pieces_by_state(st, rc.SEQUANI, rc.ARVERNI, rc.WARBAND, rc.REVEALED) == 1
    assert group[rc.WARBAND] == 1 and group['_march_visibility'][rc.WARBAND][rc.REVEALED] == 1


def test_seize_selects_revealed_auxilia_instead_of_hidden():
    st = seize_board()
    place_piece(st, rc.SEQUANI, rc.ROMANS, rc.AUXILIA, piece_state=rc.REVEALED)
    seen = answers(st, [rc.AUXILIA, rc.REVEALED])
    _resolve_seize_harassment(st, rc.SEQUANI)
    from fs_bot.board.pieces import count_pieces_by_state
    assert seen[1][1]['phase'] == 'piece_state'
    assert count_pieces_by_state(st, rc.SEQUANI, rc.ROMANS, rc.AUXILIA, rc.HIDDEN) == 1
    assert count_pieces_by_state(st, rc.SEQUANI, rc.ROMANS, rc.AUXILIA, rc.REVEALED) == 0


def test_np_seize_loses_other_ally_before_city_ally():
    st = board()
    st['non_player_factions'].add(rc.ROMANS)
    tribes = [t for t, region in rc.TRIBE_TO_REGION.items() if region == rc.CARNUTES]
    city = next(t for t in tribes if t in rc.TRIBE_TO_CITY)
    other = next(t for t in tribes if t not in rc.TRIBE_TO_CITY)
    for tribe in (city, other):
        place_piece(st, rc.CARNUTES, rc.ROMANS, rc.ALLY)
        st['tribes'][tribe]['allied_faction'] = rc.ROMANS
    place_piece(st, rc.CARNUTES, rc.ARVERNI, rc.WARBAND, 3)
    _resolve_seize_harassment(st, rc.CARNUTES)
    assert st['tribes'][city]['allied_faction'] == rc.ROMANS
    assert st['tribes'][other]['allied_faction'] is None


def test_seize_failed_roll_pause_save_and_exact_replay(tmp_path):
    st = seize_board()
    session = SeatSession(st, {'seat': rc.ROMANS}, [], HumanTurnDisplay(StringIO()))
    st['decision_agent'] = session.reactive
    session.import_inbox([{'response': {'choice': 'roll'}}])
    before = encode(board_copy(st))
    with pytest.raises(DecisionPending):
        with _action_transaction(st, driver(session)):
            _resolve_seize_harassment(st, rc.SEQUANI)
    assert encode(board_copy(st)) == before
    assert decode(session.data['pending']['request'])['phase'] == 'remove'
    save_game(st, tmp_path / 'seize.json', meta=session.meta, log=session.log)
    restored, meta, log = load_game(tmp_path / 'seize.json')
    resumed = SeatSession(restored, meta, log, HumanTurnDisplay(StringIO()))
    restored['decision_agent'] = resumed.reactive
    resumed.import_inbox([{'response': {'choice': rc.FORT}}])
    with _action_transaction(restored, driver(resumed)):
        _resolve_seize_harassment(restored, rc.SEQUANI)
    resumed.finish()
    replay = seize_board()
    seen = answers(replay, [decode(entry['assistant_response'])['choice'] for entry in log])
    _resolve_seize_harassment(replay, rc.SEQUANI)
    assert [dict(request, faction=faction) for faction, request in seen] == [
        decode(entry['assistant_request']) for entry in log]
    assert encode(board_copy(replay)) == encode(board_copy(restored))


def test_actual_vercingetorix_casualty_stops_surviving_warbands_before_leader_only_hop():
    st = board(scenario=rc.SCENARIO_GREAT_REVOLT, faction=rc.ARVERNI)
    place_piece(st, rc.MORINI, rc.ARVERNI, rc.LEADER, leader_name=rc.VERCINGETORIX)
    place_piece(st, rc.MORINI, rc.ARVERNI, rc.WARBAND, 2)
    place_piece(st, rc.NERVII, rc.ROMANS, rc.AUXILIA, 3)
    seen = answers(st, ['roll'])
    destination = _march_with_harassment(st, rc.ARVERNI, rc.MORINI,
                                        [rc.NERVII, rc.ATREBATES])
    assert len(seen) == 1
    assert destination == rc.NERVII
    assert get_leader_in_region(st, rc.NERVII, rc.ARVERNI) is None
    assert count_pieces(st, rc.NERVII, rc.ARVERNI, rc.WARBAND) == 2
    assert count_pieces(st, rc.ATREBATES, rc.ARVERNI, rc.WARBAND) == 0


def test_actual_caesar_casualty_stops_survivors_before_third_hop():
    st = board()
    romans(st, rc.PROVINCIA, aux=2)
    place_piece(st, rc.SEQUANI, rc.ARVERNI, rc.WARBAND, 3)
    place_piece(st, rc.MANDUBII, rc.ARVERNI, rc.WARBAND, 3)
    seen = answers(st, ['roll', rc.LEADER])
    destination = _march_with_harassment(st, rc.ROMANS, rc.PROVINCIA,
                                        [rc.SEQUANI, rc.MANDUBII, rc.CARNUTES])
    assert len(seen) == 2
    assert destination == rc.MANDUBII
    assert count_pieces(st, rc.MANDUBII, rc.ROMANS, rc.AUXILIA) == 2
    assert count_pieces(st, rc.MANDUBII, rc.ROMANS, rc.LEGION) == 1
    assert get_leader_in_region(st, rc.MANDUBII, rc.ROMANS) is None
    assert count_pieces(st, rc.CARNUTES, rc.ROMANS) == 0


def test_actual_human_march_keeps_residents_separate_from_selected_soft_casualty():
    from fs_bot.board.pieces import count_pieces_by_state
    st = board(scenario=rc.SCENARIO_GREAT_REVOLT, faction=rc.ARVERNI)
    place_piece(st, rc.MORINI, rc.ARVERNI, rc.LEADER, leader_name=rc.VERCINGETORIX)
    place_piece(st, rc.MORINI, rc.ARVERNI, rc.WARBAND, 2, piece_state=rc.SCOUTED)
    place_piece(st, rc.NERVII, rc.ARVERNI, rc.WARBAND, 3)
    place_piece(st, rc.NERVII, rc.ROMANS, rc.AUXILIA, 3)
    seen = answers(st, [rc.WARBAND])
    destination = _march_with_harassment(st, rc.ARVERNI, rc.MORINI,
                                        [rc.NERVII, rc.ATREBATES])
    assert len(seen) == 1 and destination == rc.ATREBATES
    assert seen[0][1]['departing_pieces']['_march_visibility'][rc.WARBAND][rc.REVEALED] == 2
    assert count_pieces_by_state(st, rc.NERVII, rc.ARVERNI, rc.WARBAND, rc.HIDDEN) == 3
    assert count_pieces_by_state(st, rc.NERVII, rc.ARVERNI, rc.WARBAND, rc.REVEALED) == 0
    assert count_pieces_by_state(st, rc.ATREBATES, rc.ARVERNI, rc.WARBAND, rc.HIDDEN) == 0
    assert count_pieces_by_state(st, rc.ATREBATES, rc.ARVERNI, rc.WARBAND, rc.REVEALED) == 1


def test_terminal_eof_after_roll_interrupts_and_rolls_back_instead_of_using_np_choice():
    from fs_bot.cli.reactive import make_cli_reactive
    st = board()
    group = romans(st)
    before = encode(board_copy(st))
    st['decision_agent'] = make_cli_reactive(
        [rc.ROMANS], StringIO('Roll for a hard piece\n'), StringIO())
    with pytest.raises(EOFError):
        with _action_transaction(st, lambda *args: None):
            harassment(st, group)
    assert encode(board_copy(st)) == before
    st['decision_agent'] = make_cli_reactive(
        [rc.ROMANS], StringIO('Roll for a hard piece\nRemove Leader\n'), StringIO())
    result = harassment(st, group)
    assert result['losses_by_faction'][0]['removals'] == [(rc.LEADER, 1, 2)]
    assert count_pieces(st, rc.SEQUANI, rc.ROMANS, rc.AUXILIA) == 1


@pytest.mark.parametrize('marching', [True, False])
@pytest.mark.parametrize('auxilia', [1, 3])
def test_base_harassers_announce_and_inflict_in_card_order_after_previous_losses(marching, auxilia):
    st = board(scenario=rc.SCENARIO_GREAT_REVOLT)
    st['non_player_factions'] = set()
    # Card4 puts Belgae before Aedui, unlike the global FACTIONS tuple.
    st['current_card'] = 4
    origin = rc.PROVINCIA if marching else rc.SEQUANI
    romans(st, origin, aux=auxilia, legions=0, leader=False)
    for faction in (rc.BELGAE, rc.AEDUI, rc.GERMANS):
        place_piece(st, rc.SEQUANI, faction, rc.WARBAND, 3)
    seen = []
    def agent(state, faction, request):
        if request.get('request_type') == 'harassment':
            seen.append((faction, count_pieces(state, rc.SEQUANI, rc.ROMANS, rc.AUXILIA)))
            return True
        return None
    st['decision_agent'] = agent
    if marching:
        destination = _march_with_harassment(st, rc.ROMANS, origin,
                                            [rc.SEQUANI, rc.AEDUI_REGION])
        assert destination == rc.SEQUANI
    else:
        result = _resolve_seize_harassment(st, rc.SEQUANI)
        assert [loss['by'] for loss in result] == (
            [rc.BELGAE] if auxilia == 1 else [rc.BELGAE, rc.AEDUI, rc.GERMANS])
    assert seen == ([(rc.BELGAE, 1)] if auxilia == 1 else
                    [(rc.BELGAE, 3), (rc.AEDUI, 2)])
    assert count_pieces(st, rc.SEQUANI, rc.ROMANS, rc.AUXILIA) == 0


@pytest.mark.parametrize('scenario,automatic', [
    (rc.SCENARIO_GREAT_REVOLT, rc.GERMANS),
    (rc.SCENARIO_ARIOVISTUS, rc.ARVERNI),
])
def test_game_run_harassers_cannot_be_overridden_by_human_callback(scenario, automatic):
    from fs_bot.engine.execute import _np_harassers
    st = board(scenario=scenario)
    st['non_player_factions'] = set()
    place_piece(st, rc.SEQUANI, automatic, rc.WARBAND, 3)
    seen = []
    def refusing_agent(state, faction, request):
        seen.append((faction, request))
        return False
    st['decision_agent'] = refusing_agent
    assert _np_harassers(st, rc.SEQUANI, rc.ROMANS, {rc.AUXILIA: 1}) == [(automatic, 3)]
    assert not seen


def test_ariovistus_np_germans_harass_romans_per_a8_4_substitution():
    st = board()
    romans(st, rc.PROVINCIA, aux=1, legions=0, leader=False)
    place_piece(st, rc.SEQUANI, rc.GERMANS, rc.WARBAND, 3)
    _march_with_harassment(st, rc.ROMANS, rc.PROVINCIA, [rc.SEQUANI, rc.AEDUI_REGION])
    assert count_pieces(st, rc.SEQUANI, rc.ROMANS, rc.AUXILIA) == 0
    assert count_pieces(st, rc.AEDUI_REGION, rc.ROMANS, rc.AUXILIA) == 0


def test_human_roman_auxilia_harassment_can_be_declined_with_correct_piece_information():
    st = board(scenario=rc.SCENARIO_GREAT_REVOLT)
    place_piece(st, rc.MORINI, rc.ARVERNI, rc.LEADER, leader_name=rc.VERCINGETORIX)
    place_piece(st, rc.MORINI, rc.ARVERNI, rc.WARBAND, 2)
    place_piece(st, rc.NERVII, rc.ROMANS, rc.AUXILIA, 3)
    seen = []
    def refuse(state, faction, request):
        seen.append((faction, deepcopy(request)))
        return False
    st['decision_agent'] = refuse
    _march_with_harassment(st, rc.ARVERNI, rc.MORINI, [rc.NERVII, rc.ATREBATES])
    assert len(seen) == 1 and seen[0][0] == rc.ROMANS
    assert seen[0][1]['context']['harassing_piece'] == rc.AUXILIA
    assert count_pieces(st, rc.ATREBATES, rc.ARVERNI, rc.WARBAND) == 2
    from fs_bot.cli.reactive import make_cli_reactive
    output = StringIO()
    make_cli_reactive([rc.ROMANS], StringIO('no\n'), output)(st, rc.ROMANS, seen[0][1])
    assert '3 Hidden Auxilia' in output.getvalue()
