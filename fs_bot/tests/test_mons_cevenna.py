"""Card Reference 9: human adjacent March, origin flips, scoped follow-on."""
from copy import deepcopy
from io import StringIO

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces, count_pieces_by_state, place_piece
from fs_bot.engine import execute as ex
from fs_bot.state.serialize import encode
from fs_bot.state.state_schema import build_initial_state, validate_state


def position(scenario=rc.SCENARIO_GREAT_REVOLT, faction=rc.ROMANS):
    state = build_initial_state(scenario, seed=9)
    state.update(current_card=9, next_card=35, executing_faction=faction,
                 non_player_factions=set(), event_params={})
    state['resources'][faction] = 0
    return state


def plan(piece=rc.AUXILIA, number=1):
    return {'origin': rc.PROVINCIA, 'destination': rc.SEQUANI, 'group': {piece: number}}


def onward(piece=rc.AUXILIA):
    return {'command': rc.CMD_MARCH, 'sa': 'No SA', 'sa_regions': [],
            'regions': [rc.SEQUANI], 'details': {'explicit_moves': [
                {'origin': rc.SEQUANI, 'path': [rc.MANDUBII], 'group': {piece: 1}}]}}


def install(state, selected, following=None):
    seen = []
    def agent(board, actor, request):
        seen.append((actor, deepcopy(request)))
        if request.get('request_type') == 'mons_cevenna_march':
            return selected
        if request.get('request_type') == 'event_command':
            return following
    state['decision_agent'] = agent
    return seen


@pytest.mark.parametrize('scenario,faction,piece', [
    (rc.SCENARIO_GREAT_REVOLT, rc.ROMANS, rc.AUXILIA),
    (rc.SCENARIO_GREAT_REVOLT, rc.AEDUI, rc.WARBAND),
    (rc.SCENARIO_GREAT_REVOLT, rc.ARVERNI, rc.WARBAND),
    (rc.SCENARIO_GREAT_REVOLT, rc.BELGAE, rc.WARBAND),
    (rc.SCENARIO_ARIOVISTUS, rc.GERMANS, rc.WARBAND),
])
def test_human_selects_partial_group_and_next_command_can_march_out(scenario, faction, piece):
    state = position(scenario, faction)
    place_piece(state, rc.PROVINCIA, faction, piece, 3, piece_state=rc.REVEALED)
    seen = install(state, plan(piece), onward(piece))
    result = ex._resolve_card9_march_command(state, faction, None, None)
    assert any(r.get('request_type') == 'mons_cevenna_march' for _, r in seen)
    assert all(actor == faction for actor, _ in seen)
    assert count_pieces(state, rc.PROVINCIA, faction, piece) == 2
    assert count_pieces_by_state(state, rc.PROVINCIA, faction, piece, rc.HIDDEN) == 2
    assert count_pieces(state, rc.MANDUBII, faction, piece) == 1
    assert count_pieces(state, rc.SEQUANI, faction, piece) == 0
    follow = next(r for _, r in seen if r.get('request_type') == 'event_command')
    assert follow['allowed_regions'] == [rc.SEQUANI]
    assert follow['with_sa'] and follow['allow_decline'] is False
    assert result[1]['result']['executed']
    assert state['resources'][faction] == 0
    assert validate_state(state) == []


@pytest.mark.parametrize('bad', [
    {'origin': rc.PROVINCIA, 'destination': rc.MANDUBII, 'group': {rc.AUXILIA: 1}},
    {'origin': rc.PROVINCIA, 'destination': rc.PROVINCIA, 'group': {rc.AUXILIA: 1}},
    {'origin': rc.PROVINCIA, 'destination': rc.SEQUANI, 'group': {rc.AUXILIA: 4}},
    {'origin': rc.PROVINCIA, 'destination': rc.SEQUANI, 'group': {rc.AUXILIA: True}},
    {'origin': rc.PROVINCIA, 'destination': rc.SEQUANI, 'group': {rc.FORT: 1}},
    {'origin': rc.PROVINCIA, 'destination': rc.SEQUANI, 'group': {rc.LEADER: True}},
    {'origin': None, 'destination': rc.SEQUANI, 'group': {}},
    {'decline': True},
])
def test_illegal_first_march_is_rejected_atomically(bad):
    state = position()
    place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA, 3)
    install(state, bad)
    before = encode({k: v for k, v in state.items() if k != 'decision_agent'})
    with pytest.raises(ValueError):
        ex._resolve_card9_march_command(state, rc.ROMANS, None, None)
    assert encode({k: v for k, v in state.items() if k != 'decision_agent'}) == before


@pytest.mark.parametrize('following', [
    {'decline': True},
    {'command': rc.CMD_MARCH, 'sa': 'No SA', 'sa_regions': [], 'regions': [rc.PROVINCIA],
     'details': {'explicit_moves': [{'origin': rc.PROVINCIA, 'path': [rc.SEQUANI],
                                     'group': {rc.AUXILIA: 1}}]}},
])
def test_invalid_follow_on_rolls_back_the_first_march(following):
    state = position()
    place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA, 3, piece_state=rc.REVEALED)
    install(state, plan(), following)
    before = encode({k: v for k, v in state.items() if k != 'decision_agent'})
    with pytest.raises(ValueError):
        ex._resolve_card9_march_command(state, rc.ROMANS, None, None)
    assert encode({k: v for k, v in state.items() if k != 'decision_agent'}) == before


def test_no_moving_pieces_still_selects_one_follow_on_region():
    state = position()
    seen = install(state, {'origin': None, 'destination': rc.ARVERNI_REGION, 'group': {}})
    ex._resolve_card9_march_command(state, rc.ROMANS, None, None)
    follow = next(r for _, r in seen if r.get('request_type') == 'event_command')
    assert follow['allowed_regions'] == [rc.ARVERNI_REGION]


@pytest.mark.parametrize('params', [
    {'march_from': rc.MANDUBII, 'march_to': rc.SEQUANI},
    {'march_from': rc.PROVINCIA, 'march_to': rc.MANDUBII},
    {'march_from': rc.PROVINCIA},
])
def test_event_handler_rejects_legacy_routes_outside_the_printed_grant(params):
    from fs_bot.cards.card_effects import execute_event
    state = position()
    state['event_params'] = params
    with pytest.raises(ValueError):
        execute_event(state, 9)


def test_terminal_can_inspect_and_choose_exact_pieces():
    from fs_bot.cards.mons_cevenna import make_request
    from fs_bot.cli.free_actions import collect_free_action
    state = position()
    place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA, 3)
    before = encode(state)
    out = StringIO()
    selected = collect_free_action(state, rc.ROMANS, make_request(state, rc.ROMANS),
        StringIO('board\nChoose March pieces and destination\nb\nProvincia\n2\nSequani\n'), out)
    assert selected == plan()
    assert out.getvalue().count('AVAILABLE PIECES') == 2
    assert encode(state) == before


def test_durable_pending_save_resume_and_invalid_response_preserve_identity(tmp_path):
    from fs_bot.cli.display import HumanTurnDisplay
    from fs_bot.tools.seat_session import DecisionPending, SeatSession
    from fs_bot.state.serialize import decode
    from fs_bot.engine.game_engine import _action_transaction
    state = position()
    place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA, 3, piece_state=rc.REVEALED)
    ses = SeatSession(state, {'seat': rc.ROMANS}, [], HumanTurnDisplay(StringIO()))
    state['decision_agent'] = ses.reactive
    before = encode({k: v for k, v in state.items() if k != 'decision_agent'})
    def step():
        def driver(*args):
            pass
        driver.transaction_checkpoint = ses.checkpoint
        driver.transaction_restore = ses.restore
        with _action_transaction(state, driver):
            return ex._resolve_card9_march_command(state, rc.ROMANS, None, None)
    with pytest.raises(DecisionPending):
        step()
    first = deepcopy(ses.data['pending'])
    assert decode(first['request'])['request_type'] == 'mons_cevenna_march'
    assert encode({k: v for k, v in state.items() if k != 'decision_agent'}) == before
    ses.import_inbox({'decision_id': first['id'], 'response': {'decline': True}})
    with pytest.raises(DecisionPending):
        step()
    assert ses.error
    assert ses.data['pending']['id'] == first['id']
    ses.import_inbox({'decision_id': first['id'], 'response': plan()})
    with pytest.raises(DecisionPending):
        step()
    follow = decode(ses.data['pending']['request'])
    assert follow['request_type'] == 'event_command'
    assert follow['allowed_regions'] == [rc.SEQUANI]
    assert encode({k: v for k, v in state.items() if k != 'decision_agent'}) == before

    from fs_bot.state.serialize import save_game, load_game
    save_game(state, tmp_path / 'save.json', meta=ses.meta, log=ses.log)
    state, meta, log = load_game(tmp_path / 'save.json', validate=True)
    ses = SeatSession(state, meta, log, HumanTurnDisplay(StringIO()))
    state['decision_agent'] = ses.reactive
    assert decode(ses.data['pending']['request']) == follow
    ses.import_inbox({'decision_id': ses.data['pending']['id'], 'response': onward()})
    assert step()[1]['result']['executed']
    assert count_pieces(state, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA) == 2
    assert count_pieces(state, rc.MANDUBII, rc.ROMANS, rc.AUXILIA) == 1


def test_event_both_texts_reach_live_march_choice_before_moving():
    for side in (rc.EVENT_UNSHADED, rc.EVENT_SHADED):
        state = position()
        place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA, 3)
        seen = install(state, plan(), onward())
        action = {'command': 'Event', 'sa': 'No SA', 'sa_regions': [],
                  'details': {'card_id': 9, 'text_preference': side, 'event_params': {}}}
        result = ex._execute_event(state, rc.ROMANS, action, human=True)
        assert result['executed']
        assert any(r.get('request_type') == 'mons_cevenna_march' for _, r in seen)
        assert count_pieces(state, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA) == 2
        assert count_pieces(state, rc.MANDUBII, rc.ROMANS, rc.AUXILIA) == 1


def test_origin_scouted_counters_lose_only_one_visibility_step():
    state = position()
    place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA, 3, piece_state=rc.SCOUTED)
    install(state, plan(), onward())
    ex._resolve_card9_march_command(state, rc.ROMANS, None, None)
    assert count_pieces_by_state(state, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA, rc.REVEALED) == 2
    assert count_pieces_by_state(state, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA, rc.HIDDEN) == 0


def test_live_diviciacus_refusal_reoffers_march_then_moves_native_force():
    from fs_bot.cards.card_effects import execute_event
    state = position()
    execute_event(state, 38)
    place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA, 2)
    place_piece(state, rc.PROVINCIA, rc.AEDUI, rc.WARBAND, 2)
    requests = []
    def agent(board, actor, request):
        if request.get('request_type') == 'mons_cevenna_march':
            requests.append(request)
            return dict(plan(), diviciacus_regions=[rc.PROVINCIA] if len(requests) == 1 else [])
        if request['kind'] == 'agreement':
            return False
        if request.get('request_type') == 'event_command':
            return onward()
    state['decision_agent'] = agent
    ex._resolve_card9_march_command(state, rc.ROMANS, None, None)
    assert len(requests) == 2 and requests[1]['attempt'] == 2
    assert count_pieces(state, rc.PROVINCIA, rc.AEDUI, rc.WARBAND) == 2
    assert count_pieces(state, rc.MANDUBII, rc.ROMANS, rc.AUXILIA) == 1
    assert validate_state(state) == []


def test_fuzz_policy_authors_legal_repeatable_marches_without_changing_live_rng():
    import random
    from fs_bot.cards.mons_cevenna import make_request, validate_response
    from fs_bot.tools.player_fuzz import make_random_reactive
    state = position()
    for origin in (rc.PROVINCIA, rc.SEQUANI, rc.ARVERNI_REGION):
        place_piece(state, origin, rc.ROMANS, rc.AUXILIA, 3)
    request = make_request(state, rc.ROMANS)
    before = encode(state)
    for seed in range(20):
        one = make_random_reactive([rc.ROMANS], random.Random(seed))(state, rc.ROMANS, request)
        two = make_random_reactive([rc.ROMANS], random.Random(seed))(state, rc.ROMANS, request)
        assert one == two
        assert validate_response(state, rc.ROMANS, request, one) is None
    assert encode(state) == before


@pytest.mark.parametrize('timing', ['before', 'after'])
def test_follow_on_build_and_march_keeps_selected_order(timing):
    state = position()
    place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA, 3)
    place_piece(state, rc.SEQUANI, rc.ROMANS, rc.LEADER, leader_name=rc.CAESAR)
    action = onward()
    action.update(sa=rc.SA_BUILD, sa_regions=[rc.SEQUANI], sa_timing=timing)
    action['details']['build_plan'] = {'forts': [rc.SEQUANI], 'subdue': [], 'allies': []}
    install(state, plan(), action)
    result = ex._resolve_card9_march_command(state, rc.ROMANS, None, None)
    assert result[1]['result']['executed']
    assert count_pieces(state, rc.SEQUANI, rc.ROMANS, rc.FORT) == 1
    assert count_pieces(state, rc.MANDUBII, rc.ROMANS, rc.AUXILIA) == 1
    assert state['resources'][rc.ROMANS] == 0
    assert validate_state(state) == []


def test_cooperating_force_retains_physical_owner_after_two_separate_marches():
    from fs_bot.cards.card_effects import execute_event
    state = position()
    execute_event(state, 38)
    place_piece(state, rc.SEQUANI, rc.ROMANS, rc.AUXILIA, 1)
    place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA, 2)
    place_piece(state, rc.PROVINCIA, rc.AEDUI, rc.WARBAND, 2, piece_state=rc.REVEALED)
    action = onward()
    action['details']['diviciacus_regions'] = [rc.SEQUANI]
    def agent(board, actor, request):
        if request.get('request_type') == 'mons_cevenna_march':
            return dict(plan(), diviciacus_regions=[rc.PROVINCIA])
        if request['kind'] == 'agreement':
            return True
        if request['kind'] == 'diviciacus_pieces':
            return {'counts': {rc.ROMANS: 0, rc.AEDUI: 1}}
        if request.get('request_type') == 'event_command':
            return action
    state['decision_agent'] = agent
    ex._resolve_card9_march_command(state, rc.ROMANS, None, None)
    assert count_pieces(state, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA) == 2
    assert count_pieces(state, rc.PROVINCIA, rc.AEDUI, rc.WARBAND) == 1
    assert count_pieces(state, rc.MANDUBII, rc.AEDUI, rc.WARBAND) == 1
    assert validate_state(state) == []
