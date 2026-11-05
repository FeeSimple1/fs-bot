"""§4.2.2: one Auxilia allocation may Scout exact cohorts across factions."""
from copy import deepcopy
from io import StringIO

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import place_piece, count_pieces_by_state
from fs_bot.commands.sa_scout import scout_reveal
from fs_bot.commands.common import CommandError
from fs_bot.engine.execute import _execute_scout
from fs_bot.state.state_schema import build_initial_state, validate_state
from fs_bot.state.serialize import encode, decode, save_game, load_game

REGION = rc.MORINI


def position(scenario=rc.SCENARIO_GREAT_REVOLT, auxilia=2):
    state = build_initial_state(scenario, seed=21)
    state['non_player_factions'] = set()
    state['resources'][rc.ROMANS] = 20
    place_piece(state, REGION, rc.ROMANS, rc.LEADER, leader_name=rc.CAESAR)
    place_piece(state, REGION, rc.ROMANS, rc.AUXILIA, auxilia)
    for faction in (rc.BELGAE, rc.ARVERNI, rc.AEDUI, rc.GERMANS):
        for ps in (rc.HIDDEN, rc.REVEALED, rc.SCOUTED):
            place_piece(state, REGION, faction, rc.WARBAND, 2, piece_state=ps)
    return state


def target(faction=rc.BELGAE, visibility=rc.HIDDEN, count=1):
    return {'faction': faction, 'piece_state': visibility, 'count': count}


def group(targets=None, auxilia=1, region=REGION):
    return {'region': region, 'auxilia_count': auxilia,
            'targets': targets if targets is not None else [target(), target(rc.ARVERNI, rc.REVEALED)]}


def action(rows=None, moves=None):
    return {'command': rc.CMD_MARCH, 'sa': rc.SA_SCOUT, 'sa_regions': [REGION],
            'sa_timing': 'after', 'details': {'scout_plan': {
                'auxilia_moves': moves or [], 'scout_targets': rows if rows is not None else [group()]}}}


def count(state, faction, piece=rc.WARBAND, ps=rc.SCOUTED, region=REGION):
    return count_pieces_by_state(state, region, faction, piece, ps)


@pytest.mark.parametrize('scenario', [rc.SCENARIO_GREAT_REVOLT, rc.SCENARIO_ARIOVISTUS])
def test_dispatcher_uses_one_auxilia_for_two_factions(scenario):
    state = position(scenario, auxilia=1)
    result = _execute_scout(state, rc.ROMANS, action())
    assert result['executed'] and not result['errors']
    assert count(state, rc.ROMANS, rc.AUXILIA, rc.REVEALED) == 1
    assert count(state, rc.BELGAE) == 3 and count(state, rc.ARVERNI) == 3
    assert count(state, rc.ARVERNI, ps=rc.HIDDEN) == 2
    assert count(state, rc.ARVERNI, ps=rc.REVEALED) == 1
    assert validate_state(state) == []


@pytest.mark.parametrize('visibility', [rc.HIDDEN, rc.REVEALED, rc.SCOUTED])
@pytest.mark.parametrize('faction', [rc.ARVERNI, rc.AEDUI, rc.BELGAE, rc.GERMANS])
def test_native_selects_exact_target_visibility(faction, visibility):
    state = position()
    result = scout_reveal(state, REGION, 1, [target(faction, visibility)])
    for ps in (rc.HIDDEN, rc.REVEALED):
        assert count(state, faction, ps=ps) == 2 - (ps == visibility)
    assert count(state, faction) == (2 if visibility == rc.SCOUTED else 3)
    assert result['warbands_revealed'] == [(faction, 1)]
    assert result['scouted_placed'] == ([] if visibility == rc.SCOUTED else [(faction, 1)])
    assert validate_state(state) == []


@pytest.mark.parametrize('auxilia,targets', [
    (True, [target()]), (-1, []), (1.5, []), (None, []), (3, [target()]),
    (1, [target(count=3)]), (1, [target(count=True)]), (1, [target(count=0)]),
    (1, [target(count=-1)]), (1, [target(count=1.5)]),
    (1, [target(visibility=None)]), (1, [target(visibility='invisible')]),
    (1, [target(faction=rc.ROMANS)]), (1, [target(faction='outsider')]),
    (1, [dict(target(), extra=1)]), (1, [target(), target(faction=rc.ROMANS)]),
    (2, [target(count=2), target()]), (1, None), (1, [None]),
])
def test_invalid_native_allocation_is_atomic(auxilia, targets):
    state = position(); before = encode(state)
    with pytest.raises(CommandError): scout_reveal(state, REGION, auxilia, targets)
    assert encode(state) == before


def test_legacy_count_only_targets_retain_hidden_first_partial_fulfillment():
    state = position()
    result = scout_reveal(state, REGION, 2, [{'faction': rc.BELGAE, 'count': 3}])
    assert count(state, rc.BELGAE, ps=rc.HIDDEN) == 0
    assert count(state, rc.BELGAE, ps=rc.REVEALED) == 1
    assert result['warbands_revealed'] == [(rc.BELGAE, 3)]
    state = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=1)
    place_piece(state, REGION, rc.ROMANS, rc.LEADER, leader_name=rc.CAESAR)
    place_piece(state, REGION, rc.ROMANS, rc.AUXILIA, 2)
    place_piece(state, REGION, rc.BELGAE, rc.WARBAND)
    assert scout_reveal(state, REGION, 2, [{'faction': rc.BELGAE, 'count': 3}])['warbands_revealed'] == [(rc.BELGAE, 1)]


def test_native_legacy_multi_faction_control_already_works():
    state = position(auxilia=1)
    scout_reveal(state, REGION, 1, [{'faction': rc.BELGAE, 'count': 1}, {'faction': rc.ARVERNI, 'count': 1}])
    assert count(state, rc.BELGAE) == count(state, rc.ARVERNI) == 3


@pytest.mark.parametrize('row', [
    {'region': REGION, 'auxilia_count': 1},
    {'region': REGION, 'targets': [target()]},
    {'region': REGION, 'auxilia_count': 1, 'targets': [{'faction': rc.BELGAE, 'count': 1}]},
    {'region': REGION, 'auxilia_count': True, 'targets': [target()]},
    {'region': [], 'auxilia_count': 1, 'targets': [target()]},
    {'region': REGION, 'auxilia_count': 1, 'targets': [target()], 'enemy': rc.BELGAE},
])
def test_grouped_contract_rejects_malformed_or_mixed_shapes(row):
    state = position(); before = encode(state)
    result = _execute_scout(state, rc.ROMANS, action([row]))
    assert not result['executed'] and result['errors']
    assert encode(state) == before


def test_later_invalid_group_restores_prior_reveal_and_scout_movement():
    state = position(); before = encode(state)
    result = _execute_scout(state, rc.ROMANS, action(
        [group([target()], auxilia=1), group([target(count=9)])],
        [{'from_region': REGION, 'to_region': rc.NERVII, 'count': 1, 'piece_state': rc.HIDDEN}]))
    assert not result['executed'] and result['errors'] and encode(state) == before


def test_two_groups_cannot_reuse_the_same_hidden_auxilia():
    state = position(auxilia=1); before = encode(state)
    result = _execute_scout(state, rc.ROMANS, action([group([target()]), group([target(rc.ARVERNI)])]))
    assert not result['executed'] and result['errors'] and encode(state) == before


def test_shaded_labienus_rejects_multiple_exact_regions_atomically():
    from fs_bot.cards.capabilities import activate_capability
    state = position(); activate_capability(state, 12, rc.EVENT_SHADED)
    place_piece(state, rc.NERVII, rc.ROMANS, rc.AUXILIA)
    place_piece(state, rc.NERVII, rc.BELGAE, rc.WARBAND)
    before = encode(state)
    result = _execute_scout(state, rc.ROMANS, action([group([target()]), group([target()], region=rc.NERVII)]))
    assert not result['executed'] and result['errors'] and encode(state) == before


def test_successor_proximity_still_applies():
    state = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=3)
    place_piece(state, REGION, rc.ROMANS, rc.LEADER, leader_name=rc.SUCCESSOR)
    place_piece(state, rc.NERVII, rc.ROMANS, rc.AUXILIA)
    place_piece(state, rc.NERVII, rc.BELGAE, rc.WARBAND)
    before = encode(state)
    with pytest.raises(CommandError): scout_reveal(state, rc.NERVII, 1, [target()])
    assert encode(state) == before


def test_scout_reveal_can_work_in_britannia_without_scout_movement():
    state = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=3)
    place_piece(state, rc.BRITANNIA, rc.ROMANS, rc.LEADER, leader_name=rc.CAESAR)
    place_piece(state, rc.BRITANNIA, rc.ROMANS, rc.AUXILIA)
    place_piece(state, rc.BRITANNIA, rc.BELGAE, rc.WARBAND)
    scout_reveal(state, rc.BRITANNIA, 1, [target()])
    assert count(state, rc.BELGAE, region=rc.BRITANNIA) == 1


@pytest.mark.parametrize('owner', [rc.ROMANS, rc.AEDUI])
def test_explicit_physical_scout_owner_retains_counter_colour(owner):
    from fs_bot.engine.diviciacus import force_scope
    state = position(rc.SCENARIO_ARIOVISTUS, auxilia=1)
    with force_scope(state, rc.ROMANS, [REGION], phase='special_ability'):
        scout_reveal(state, REGION, 1, [target()], physical_owners={owner: 1})
    assert count(state, rc.ROMANS, rc.AUXILIA, rc.REVEALED) == (owner == rc.ROMANS)
    assert count(state, rc.AEDUI, ps=rc.REVEALED) == 2 + (owner == rc.AEDUI)
    assert validate_state(state) == []


def test_grouped_targets_are_visible_to_cooperation_consent(monkeypatch):
    from fs_bot.engine.diviciacus import _targets, _np_agrees
    state = position(rc.SCENARIO_ARIOVISTUS)
    from fs_bot.engine import victory
    monkeypatch.setattr(victory, 'calculate_victory_score', lambda *a: 0)
    assert _np_agrees(state, rc.AEDUI, rc.ROMANS, REGION, action(), 'special_ability')
    plan = action([group([target(rc.AEDUI)])])
    assert _targets(plan, REGION) == [rc.AEDUI]
    # Source §8.6.8: Aedui do not lend to a Scout directed against themselves.
    assert not _np_agrees(state, rc.AEDUI, rc.ROMANS, REGION, plan, 'special_ability')


def test_public_preview_accepts_grouped_choice_without_input_or_rng_changes():
    from fs_bot.engine.moves import validate_player_action
    from fs_bot.tools.seat_session import board_copy
    state = position(auxilia=1); state['decision_agent'] = lambda *a: pytest.fail('Preview consulted live agent')
    plan = action(); plan['regions'] = [REGION]
    plan['details'].update(origins=[REGION], destinations=[], routes={REGION: []})
    before = encode(board_copy(state))
    assert validate_player_action(state, rc.ROMANS, plan)[0]
    assert encode(board_copy(state)) == before


@pytest.mark.parametrize('timed', [False, True])
def test_both_terminal_paths_author_one_auxilia_split_across_factions(monkeypatch, timed):
    from fs_bot.cli import roman_timing
    from fs_bot.cli.human_plan import _collect_scout
    from fs_bot.tools.seat_session import board_copy
    state = position(auxilia=1); output = StringIO()
    state['_cli_action_windows'] = timed
    # The timing fixture declines optional removal windows, keeping this test
    # focused on the legal allocation emitted by either frontend path.
    monkeypatch.setattr(roman_timing, 'prepare', lambda st,*a,**kw: (st, []))
    picks = [0]
    def pick(stdin, stdout, prompt, choices):
        if prompt == 'Scout movement?': return None
        if prompt == 'Scout Reveal?':
            picks[0] += 1
            return (REGION, 1) if picks[0] == 1 else None
        if prompt == 'How many Hidden Auxilia to Reveal?': return 1
        if prompt == 'How many Warbands?': return 1
        if prompt == 'Scout which Warbands?':
            if any(v and v[0] == rc.BELGAE and v[1] == rc.HIDDEN for _,v in choices):
                if not hasattr(pick, 'belgae'):
                    pick.belgae = True
                    return next(v for _,v in choices if v and v[:2] == (rc.BELGAE, rc.HIDDEN))
            return next(v for _,v in choices if v and v[:2] == (rc.ARVERNI, rc.REVEALED))
        raise AssertionError(prompt)
    monkeypatch.setattr(roman_timing, 'prompt_choice', pick)
    start = encode(board_copy(state))
    regions, extra = _collect_scout(state, rc.ROMANS, StringIO(), output)
    assert encode(board_copy(state)) == start
    assert regions == [REGION] and extra['scout_plan']['scout_targets'] == [group()]
    assert _execute_scout(state, rc.ROMANS, dict(action(), details=extra))['executed']


@pytest.mark.parametrize('bad', [None, {'counts': {rc.AEDUI: 99}}])
def test_later_physical_owner_pending_save_resume_and_identical_replay(tmp_path, bad):
    from fs_bot.cli.display import HumanTurnDisplay
    from fs_bot.engine.diviciacus import force_scope
    from fs_bot.engine.game_engine import _action_transaction
    from fs_bot.tools.seat_session import SeatSession, DecisionPending, board_copy
    state = position(rc.SCENARIO_ARIOVISTUS, auxilia=1)
    place_piece(state, rc.NERVII, rc.ROMANS, rc.AUXILIA)
    place_piece(state, rc.NERVII, rc.AEDUI, rc.WARBAND)
    place_piece(state, rc.NERVII, rc.BELGAE, rc.WARBAND)
    rows = [group([target()]), group([target()], region=rc.NERVII)]
    origin = deepcopy(state); before = encode(state)
    def session_for(board, meta=None, log=None):
        session = SeatSession(board, meta or {'seat': rc.ROMANS}, log if log is not None else [], HumanTurnDisplay(StringIO()))
        board['decision_agent'] = session.reactive
        return session
    def attempt(session):
        def driver(*a): pass
        driver.transaction_checkpoint = session.checkpoint; driver.transaction_restore = session.restore
        with _action_transaction(session.state, driver):
            with force_scope(session.state, rc.ROMANS, [REGION, rc.NERVII], phase='special_ability'):
                return _execute_scout(session.state, rc.ROMANS, action(rows))
    session = session_for(state)
    with pytest.raises(DecisionPending): attempt(session)
    first = deepcopy(session.data['pending']); answer = {'counts': {rc.ROMANS: 1}}
    assert decode(first['request'])['phase'] == 'scout_reveal'
    session.import_inbox({'decision_id': first['id'], 'response': answer})
    with pytest.raises(DecisionPending): attempt(session)
    pending = deepcopy(session.data['pending'])
    assert pending['id'] != first['id'] and len(session.data['journal']) == 1
    session.import_inbox({'decision_id': pending['id'], 'response': bad})
    with pytest.raises(DecisionPending): attempt(session)
    assert session.data['pending'] == pending and encode(board_copy(state)) == before
    path = tmp_path / 'scout.json'; save_game(state, path, meta=session.meta, log=session.log)
    restored, meta, log = load_game(path, validate=True); resumed = session_for(restored, meta, log)
    resumed.import_inbox({'decision_id': pending['id'], 'response': answer})
    result = attempt(resumed); resumed.finish(); assert result['executed'] and not result['errors']
    replay = session_for(origin)
    replay.data['queue'] = [SeatSession._inbox_entry(e) for e in resumed.log]
    replay.data['expected'] = [
        {'id': e['assistant_id'], 'signature': e['assistant_signature'], 'request': e['assistant_request'],
         'action_windows_version': e.get('assistant_action_windows_version', 0)} for e in resumed.log]
    assert attempt(replay) == result
    replay.finish()
    assert replay.log == resumed.log and encode(board_copy(origin)) == encode(board_copy(restored))
    assert validate_state(restored) == []


@pytest.mark.parametrize('allocation', [{rc.ROMANS: 0}, {rc.ROMANS: True}, {rc.AEDUI: 1}, []])
def test_invalid_physical_owner_selection_is_atomic(allocation):
    state = position(); before = encode(state)
    with pytest.raises(CommandError): scout_reveal(state, REGION, 1, [target()], physical_owners=allocation)
    assert encode(state) == before


def test_grouped_plan_rejects_incomplete_movement_instead_of_ignoring_it():
    state = position(); before = encode(state)
    result = _execute_scout(state, rc.ROMANS, action(moves=[{'to_region': rc.NERVII, 'count': 1}]))
    assert not result['executed'] and result['errors'] and encode(state) == before


def test_actual_terminal_menus_support_board_inspection_and_split_targets():
    from fs_bot.cli.human_plan import _collect_scout
    state = position(auxilia=1); before = encode(state); output = StringIO()
    inputs = (f'board\n1\nScout in {REGION} (1 Hidden Auxilia)\n1\n'
              f'{rc.BELGAE} {rc.HIDDEN} Warbands (up to 2)\n1\n'
              f'{rc.ARVERNI} {rc.REVEALED} Warbands (up to 1)\n1\n1\n')
    regions, details = _collect_scout(state, rc.ROMANS, StringIO(inputs), output)
    assert regions == [REGION] and details['scout_plan']['scout_targets'] == [group()]
    assert encode(state) == before and 'Romans' in output.getvalue()
