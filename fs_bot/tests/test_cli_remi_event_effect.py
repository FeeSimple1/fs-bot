"""Remi's owner chooses a printed City using detached, inspectable previews."""
from io import StringIO

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces, find_leader, get_available, place_piece
from fs_bot.cards import remi_event_effect as rules
from fs_bot.cards.card_effects import _ally_tribe, execute_event
from fs_bot.cli import remi_event_effect as cli
from fs_bot.cli.free_actions import collect_free_action
from fs_bot.cli.reactive import make_cli_reactive
from fs_bot.engine.action_windows import scope
from fs_bot.state.serialize import encode
from fs_bot.state.state_schema import build_initial_state, validate_state


def state(owner=rc.AEDUI, executor=rc.ROMANS):
    st = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=168)
    st.update(current_card=68, next_card=3, executing_faction=executor,
              non_player_factions=set())
    assert _ally_tribe(st, rc.TRIBE_REMI, owner)
    return st


def run(st, response):
    st['event_params'] = {}
    st['decision_agent'] = lambda _s, _f, request: (
        response if request.get('request_type') == 'remi_event_effect' else None)
    with scope(st, actor=st['executing_faction'], force=True):
        execute_event(st, 68, shaded=True)
    assert validate_state(st) == []


@pytest.mark.parametrize('owner', list(rc.GALLIC_FACTIONS))
@pytest.mark.parametrize('city', [rc.CITY_ALESIA, rc.CITY_CENABUM])
def test_remi_owner_can_choose_either_city_with_actual_retry_and_board(owner, city):
    st, output = state(owner), StringIO()
    before = encode(st)
    response = collect_free_action(st, owner, rules.request(st),
        StringIO(f'not a choice\nb\nChoose the City\nboard\n{city}\n'), output)
    assert response == {'target_city': city} and encode(st) == before
    text = output.getvalue()
    assert 'Please enter' in text and text.count('AVAILABLE PIECES') == 2
    assert f') {rc.CITY_ALESIA}' in text and f') {rc.CITY_CENABUM}' in text
    run(st, response)
    region = rc.TRIBE_TO_REGION[rc.CITY_TO_TRIBE[city]]
    assert count_pieces(st, region, owner, rc.CITADEL) == 1
    assert count_pieces(st, region, owner, rc.WARBAND) == 4
    assert count_pieces(st, region, rc.ROMANS) == 0


@pytest.mark.parametrize('line,response', [
    ('Use bot default', {'use_default': True}),
    ('Decline this effect', {'decline': True}),
])
def test_remi_optional_default_and_decline_are_distinct_and_pure(line, response):
    st, output = state(), StringIO()
    before = encode(st)
    assert collect_free_action(st, rc.AEDUI, rules.request(st),
        StringIO(f'board\n{line}\n'), output) == response
    assert 'AVAILABLE PIECES' in output.getvalue() and encode(st) == before


@pytest.mark.parametrize('input_text', ['', 'Choose the City\n'])
def test_remi_eof_keeps_live_state_and_randomness_untouched(input_text):
    st = state()
    before = encode(st)
    with pytest.raises(EOFError):
        make_cli_reactive([rc.AEDUI], StringIO(input_text), StringIO())(
            st, rc.AEDUI, rules.request(st))
    assert encode(st) == before


def test_foreign_remi_owner_cannot_reclaim_either_seats_pieces(monkeypatch):
    from fs_bot.cli import voluntary_removal
    st = state()
    st['_cli_action_windows'] = True
    place_piece(st, rc.SEQUANI, rc.ROMANS, rc.AUXILIA)
    place_piece(st, rc.SEQUANI, rc.AEDUI, rc.WARBAND)
    before = encode(st)
    monkeypatch.setattr(voluntary_removal, 'collect_removals',
        lambda *_: pytest.fail('A foreign beneficiary cannot reclaim either seat\'s pieces'))
    response = cli.collect_response(st, rc.AEDUI, rules.request(st),
        StringIO(f'Choose the City\n{rc.CITY_ALESIA}\n'), StringIO())
    assert response == {'target_city': rc.CITY_ALESIA} and encode(st) == before


def test_remi_staged_menu_reclaims_before_warbands_on_correct_preview(monkeypatch):
    from fs_bot.cli.voluntary_removal import _label
    from fs_bot.engine.voluntary_removal import options
    st = state(executor=rc.AEDUI)
    st['_cli_action_windows'] = True
    assert _ally_tribe(st, rc.TRIBE_MANDUBII, rc.BELGAE)
    total = get_available(st, rc.AEDUI, rc.WARBAND)
    place_piece(st, rc.SEQUANI, rc.AEDUI, rc.WARBAND, total)
    before, output, seen = encode(st), StringIO(), []
    original = cli.prepare

    def prepare(board, faction, stdin, stdout, **kwargs):
        seen.append((kwargs['step'], count_pieces(board, rc.MANDUBII, rc.BELGAE, rc.ALLY),
                     count_pieces(board, rc.MANDUBII, rc.AEDUI, rc.CITADEL)))
        return original(board, faction, stdin, stdout, **kwargs)

    monkeypatch.setattr(cli, 'prepare', prepare)
    removal = next(choice for choice in options(st, rc.AEDUI)
                   if choice['region'] == rc.SEQUANI and choice['piece_type'] == rc.WARBAND)
    lines = ['Choose the City', rc.CITY_ALESIA, 'Finish voluntary removal',
             'board', _label(removal), '1', 'Finish voluntary removal']
    response = cli.collect_response(st, rc.AEDUI, rules.request(st),
        StringIO('\n'.join(lines) + '\n'), output)
    assert seen == [('68.citadel', 0, 0), ('68.warbands', 0, 1)]
    assert encode(st) == before and 'AVAILABLE PIECES' in output.getvalue()
    assert response['stage_timing_actions']['68.warbands'][0]['response']['operations'][0]['count'] == 1
    run(st, response)
    assert count_pieces(st, rc.SEQUANI, rc.AEDUI, rc.WARBAND) == total - 1
    assert count_pieces(st, rc.MANDUBII, rc.AEDUI, rc.WARBAND) == 1
    assert count_pieces(st, rc.MANDUBII, rc.AEDUI, rc.CITADEL) == 1


def test_foreign_arverni_remi_owner_retains_spring_entry(monkeypatch):
    from fs_bot.cli import voluntary_removal
    from fs_bot.engine.spring import UNLOCK_KEY
    st = build_initial_state(rc.SCENARIO_PAX_GALLICA, seed=168)
    st.update(current_card=68, next_card=3, executing_faction=rc.ROMANS,
              non_player_factions=set(), spring_box_leaders=[rc.VERCINGETORIX])
    assert _ally_tribe(st, rc.TRIBE_REMI, rc.ARVERNI)
    st['available'][rc.ARVERNI][rc.LEADER] -= 1
    st[UNLOCK_KEY] = st['_cli_action_windows'] = True
    assert validate_state(st) == []
    before = encode(st)
    monkeypatch.setattr(voluntary_removal, 'collect_removals',
        lambda *_: pytest.fail('Foreign Arverni may enter their Leader, not reclaim pieces'))
    response = cli.collect_response(st, rc.ARVERNI, rules.request(st),
        StringIO(f'Choose the City\n{rc.CITY_ALESIA}\n{rc.ATREBATES}\n'), StringIO())
    assert encode(st) == before
    assert response['stage_timing_actions']['68.citadel'] == [
        {'kind': 'spring_leader', 'response': {'region': rc.ATREBATES}}]
    run(st, response)
    assert find_leader(st, rc.ARVERNI) == rc.ATREBATES
    assert rc.VERCINGETORIX not in st['spring_box_leaders']
