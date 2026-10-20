"""A20 'as if there' must not display a physical March during human reactions."""
from io import StringIO

from fs_bot import rules_consts as rc
from fs_bot.board.control import refresh_all_control
from fs_bot.board.pieces import place_piece, count_pieces, count_pieces_by_state
from fs_bot.cards.morbihan_display import PROJECTION_KEY
from fs_bot.cli.display import HumanTurnDisplay, format_board, snapshot_state
from fs_bot.cli.reactive import make_cli_reactive
from fs_bot.engine.agent import LOSS_ORDER
from fs_bot.engine.execute import _execute_event, _resolve_a20_arverni_ambush
from fs_bot.state.serialize import encode
from fs_bot.state.state_schema import build_initial_state


def board(caesar=False):
    state = build_initial_state(rc.SCENARIO_ARIOVISTUS, seed=0)
    state['current_card'] = state['current_card_id'] = 'A20'
    state['non_player_factions'] = {rc.GERMANS, rc.AEDUI, rc.BELGAE}
    place_piece(state, rc.VENETI, rc.ARVERNI, rc.ALLY)
    state['tribes'][rc.TRIBE_VENETI]['allied_faction'] = rc.ARVERNI
    place_piece(state, rc.VENETI, rc.ARVERNI, rc.WARBAND, 2)
    place_piece(state, rc.PICTONES, rc.ARVERNI, rc.WARBAND, 2)
    if caesar:
        place_piece(state, rc.CARNUTES, rc.ROMANS, rc.LEGION, 2,
                    from_legions_track=True)
        place_piece(state, rc.CARNUTES, rc.ROMANS, rc.LEADER, leader_name=rc.CAESAR)
    else:
        place_piece(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA, 3,
                    piece_state=rc.REVEALED)
    refresh_all_control(state)
    return state


def event(state):
    return _execute_event(state, rc.GERMANS, {'command': 'Event', 'details': {
        'card_id': 'A20', 'text_preference': rc.EVENT_SHADED}}, human=True)


def next_delta(display, state, faction):
    display.stdout.seek(0)
    display.stdout.truncate()
    display.before_decision(state, faction, show_context=False)
    return display.stdout.getvalue()


def test_actual_a20_human_loss_menus_keep_physical_origins_and_real_roman_losses():
    state = board()
    display = HumanTurnDisplay(StringIO())
    display.remember(state, (rc.ROMANS, rc.GERMANS))
    initial = snapshot_state(state)
    observed = []
    reactive = make_cli_reactive({rc.ROMANS},
        StringIO('1\n(default order for the rest)\n1\n(default order for the rest)\n'),
        StringIO())

    def human(live, faction, request):
        if faction != rc.ROMANS or request['kind'] != LOSS_ORDER:
            return None
        before = encode({k: v for k, v in live.items() if k != 'decision_agent'})
        observed.append({
            'board': format_board(live), 'snapshot': snapshot_state(live),
            'delta': next_delta(display, live, faction),
            'gathered': count_pieces(live, rc.CARNUTES, rc.ARVERNI, rc.WARBAND),
            'unchanged': before == encode({k: v for k, v in live.items() if k != 'decision_agent'}),
        })
        return reactive(live, faction, request)

    state['decision_agent'] = human
    result = event(state)
    assert result['executed'] and len(observed) == 2
    for step in observed:
        assert step['gathered'] == 4 and step['unchanged']
        for region in (rc.VENETI, rc.PICTONES):
            assert step['snapshot']['pieces'][region, rc.ARVERNI, rc.WARBAND] == 2
            assert step['snapshot']['piece_states'][region, rc.ARVERNI, rc.WARBAND, rc.HIDDEN] == 2
        assert (rc.CARNUTES, rc.ARVERNI, rc.WARBAND) not in step['snapshot']['pieces']
        assert step['snapshot']['controls'] == initial['controls']
        assert 'Morbihan: Arverni Warbands fight Romans in Carnutes as if there' in step['board']
        assert 'Veneti: 2 Warband [H2/R0/S0]' in step['board']
        assert 'Pictones: 2 Warband [H2/R0/S0]' in step['board']
        assert 'Arverni Hidden Warband:' not in step['delta']
    assert observed[0]['snapshot']['pieces'] == initial['pieces']
    assert observed[0]['snapshot']['piece_states'] == initial['piece_states']
    assert 'Carnutes: Romans Revealed Auxilia: 3 -> 2' in observed[1]['delta']
    assert PROJECTION_KEY not in state and 'Morbihan:' not in format_board(state)
    delta = next_delta(display, state, rc.ROMANS)
    assert 'Carnutes: Romans Revealed Auxilia: 2 -> 1' in delta
    assert 'Veneti: Arverni Hidden Warband: 2 -> 0' in delta
    assert 'Veneti: Arverni Revealed Warband: 0 -> 2' in delta
    assert 'Carnutes: Arverni' not in delta
    # The other seat has an independent baseline from before the whole Event.
    assert 'Carnutes: Romans Revealed Auxilia: 3 -> 1' in next_delta(display, state, rc.GERMANS)


def test_caesar_counterattack_casualties_use_existing_return_allocation():
    state = board(caesar=True)
    display = HumanTurnDisplay(StringIO())
    display.remember(state, (rc.ROMANS,))
    snapshots = []

    def human(live, faction, request):
        if faction == rc.ROMANS and request['kind'] == LOSS_ORDER:
            snapshots.append(snapshot_state(live))
            next_delta(display, live, faction)
            return request['pieces']
        return None

    state['decision_agent'] = human
    result = event(state)
    ambush = result['free_actions'][0]['result']
    assert ambush['caesar_roll'][1] and ambush['counterattack']['losses_taken'] == 2
    assert snapshots
    for snap in snapshots:
        assert snap['pieces'][rc.VENETI, rc.ARVERNI, rc.WARBAND] == 2
        assert snap['pieces'][rc.PICTONES, rc.ARVERNI, rc.WARBAND] == 2
        assert (rc.CARNUTES, rc.ARVERNI, rc.WARBAND) not in snap['pieces']
    assert PROJECTION_KEY not in state
    assert count_pieces(state, rc.CARNUTES, rc.ARVERNI, rc.WARBAND) == 0
    assert sum(count_pieces(state, region, rc.ARVERNI, rc.WARBAND)
               for region in (rc.VENETI, rc.PICTONES)) == 2
    final = snapshot_state(state)
    for region in (rc.VENETI, rc.PICTONES):
        assert final['pieces'].get((region, rc.ARVERNI, rc.WARBAND), 0) == count_pieces(
            state, region, rc.ARVERNI, rc.WARBAND)
        assert count_pieces_by_state(state, region, rc.ARVERNI, rc.WARBAND, rc.HIDDEN) == 0
    delta = next_delta(display, state, rc.ROMANS)
    assert 'Carnutes: Arverni' not in delta
    assert 'Arverni Hidden Warband: 2 -> 0' in delta
    assert 'Arverni Revealed Warband: 0 -> 2' in delta


def test_failed_battle_clears_projection_and_keeps_existing_restore_behavior(monkeypatch):
    from fs_bot.commands.common import CommandError
    state = board()
    initial = snapshot_state(state)
    def fail(*args, **kwargs):
        raise CommandError('test Battle interruption')
    monkeypatch.setattr('fs_bot.battle.resolve.resolve_battle', fail)
    result = _resolve_a20_arverni_ambush(state)
    assert result[0]['executed'] is False
    assert PROJECTION_KEY not in state
    assert snapshot_state(state) == initial
