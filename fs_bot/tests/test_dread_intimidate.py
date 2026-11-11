"""A22/A4.6.2, including A3.4.3's simultaneous Raid participants."""
from copy import deepcopy
from io import StringIO
import random

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces, count_pieces_by_state, flip_piece, place_piece
from fs_bot.cards.capabilities import activate_capability, deactivate_capability, set_capability_owner
from fs_bot.commands.common import CommandError
from fs_bot.commands.raid import raid_in_region
from fs_bot.commands.sa_intimidate import intimidate, intimidate_capacity, romans_immune
from fs_bot.engine.execute import _execute_intimidate, _resolve_card_A45_intimidate
from fs_bot.engine.raid_intimidate import resolve_raid_intimidate, target_options, validate_response
from fs_bot.state.serialize import encode
from fs_bot.tests.test_raid_intimidate import position, removal


def dread(*, hidden=3, targets=3):
    state = position(hidden=hidden)
    activate_capability(state, 'A22', rc.EVENT_SHADED)
    if targets:
        place_piece(state, rc.UBII, rc.ROMANS, rc.AUXILIA, targets)
    return state


def plan(count, **extra):
    return {'details': {'intimidate_plan': [dict(removal(), region=rc.UBII, **extra)
                                           for _ in range(count)]}}


def after_raid(raiders=2, hidden=1):
    state = dread(hidden=hidden + raiders)
    flip_piece(state, rc.UBII, rc.GERMANS, rc.WARBAND, raiders,
               from_state=rc.HIDDEN, to_state=rc.REVEALED)
    request = {'region': rc.UBII, 'raiders': raiders}
    return state, request


@pytest.mark.parametrize('count', [1, 2, 3])
def test_ordinary_dread_preserves_selected_quantity_and_physical_visibility(count):
    state = dread(targets=0)
    for visibility in (rc.HIDDEN, rc.REVEALED, rc.SCOUTED):
        place_piece(state, rc.UBII, rc.ROMANS, rc.AUXILIA, piece_state=visibility)
    before_rng = state['rng'].getstate()
    action = {'details': {'intimidate_plan': [dict(removal(visibility=v), region=rc.UBII)
        for v in (rc.SCOUTED, rc.HIDDEN, rc.REVEALED)[:count]]}}
    result = _execute_intimidate(state, rc.GERMANS, action)
    assert result['executed'] and not result['errors']
    assert result['intimidations'][0]['warbands_flipped'] == count
    assert count_pieces_by_state(state, rc.UBII, rc.GERMANS, rc.WARBAND, rc.HIDDEN) == 3-count
    for index, visibility in enumerate((rc.SCOUTED, rc.HIDDEN, rc.REVEALED)):
        assert count_pieces_by_state(state, rc.UBII, rc.ROMANS, rc.AUXILIA, visibility) == int(index >= count)
    assert state['rng'].getstate() == before_rng


@pytest.mark.parametrize('mutation', ['absent', 'unshaded', 'removed', 'four', 'insufficient', 'leader', 'mixed', 'legion'])
def test_dread_does_not_override_ordinary_restrictions(mutation):
    state = dread(hidden=4, targets=4)
    action = plan(3)
    if mutation == 'absent':
        state['capabilities'].clear()
    elif mutation == 'unshaded':
        activate_capability(state, 'A22', rc.EVENT_UNSHADED)
    elif mutation == 'removed':
        deactivate_capability(state, 'A22')
    elif mutation == 'four':
        action = plan(4)
    elif mutation == 'insufficient':
        flip_piece(state, rc.UBII, rc.GERMANS, rc.WARBAND, 2,
                   from_state=rc.HIDDEN, to_state=rc.REVEALED)
    elif mutation == 'leader':
        place_piece(state, rc.UBII, rc.ROMANS, rc.LEADER, leader_name=rc.CAESAR)
    elif mutation == 'mixed':
        place_piece(state, rc.UBII, rc.BELGAE, rc.WARBAND)
        action['details']['intimidate_plan'][2] = dict(removal(rc.BELGAE, rc.WARBAND), region=rc.UBII)
    else:
        place_piece(state, rc.UBII, rc.ROMANS, rc.LEGION, from_legions_track=True)
        action['details']['intimidate_plan'][2]['target_piece'] = rc.LEGION
    before = encode(state)
    result = _execute_intimidate(state, rc.GERMANS, action)
    assert not result['executed'] and result['errors']
    assert encode(state) == before


def test_capability_side_and_legacy_immunity_are_consistent():
    state = dread()
    state.setdefault('event_modifiers', {})['card_A22_no_intimidate_romans'] = True
    assert not romans_immune(state)  # explicit side outranks an old stale companion
    activate_capability(state, 'A22', rc.EVENT_UNSHADED)
    assert romans_immune(state) and intimidate_capacity(state, rc.UBII) == 2
    assert not target_options(state, rc.UBII)
    deactivate_capability(state, 'A22')
    assert not romans_immune(state) and target_options(state, rc.UBII)
    state.setdefault('event_modifiers', {})['card_A22_no_intimidate_romans'] = True
    assert romans_immune(state)


def test_added_reveal_cannot_be_used_for_marker_only():
    state = dread()
    before = encode(state)
    with pytest.raises(CommandError, match='extra piece'):
        intimidate(state, rc.UBII, 3, None, [])
    assert encode(state) == before
    assert intimidate(state, rc.UBII, 1, None, [])['warbands_flipped'] == 1


@pytest.mark.parametrize('raiders', [1, 2, 3])
@pytest.mark.parametrize('explicit', [False, True])
def test_intrinsic_dread_extra_or_third_actual_raider(raiders, explicit):
    # The three-Raider case has NO fresh counter: Raid and Intimidate
    # simultaneously use the same third Reveal, never demand a fourth.
    extra = int(raiders < 3)
    state = dread(hidden=raiders+extra, targets=raiders+extra)
    if raiders == 3:
        activate_capability(state, 8, rc.EVENT_SHADED)
        set_capability_owner(state, 8, rc.GERMANS)
    if explicit:
        response = {'targets': [removal()] * (raiders+extra)}
        if extra:
            response['extra_warband'] = True
        state['decision_agent'] = lambda *args: response
    result = raid_in_region(state, rc.UBII, rc.GERMANS, [{'type': 'gain'}] * raiders)
    assert result['warbands_flipped'] == raiders
    effect = result['raid_intimidate']['intimidations'][0]
    assert effect['warbands_flipped'] == extra
    assert effect['raiding_warbands_used'] == raiders
    assert count_pieces(state, rc.UBII, rc.ROMANS, rc.AUXILIA) == 0
    assert count_pieces_by_state(state, rc.UBII, rc.GERMANS, rc.WARBAND, rc.REVEALED) == raiders+extra
    assert state['resources'][rc.GERMANS] == raiders


@pytest.mark.parametrize('response', [
    {'targets': [], 'extra_warband': True},
    {'targets': [removal()], 'extra_warband': True},
    {'targets': [removal()]*3},
    {'targets': [removal()]*4, 'extra_warband': True},
    {'targets': [removal()]*2, 'extra_warband': 1},
    {'targets': [removal()]*2, 'extra_warband': 'yes'},
    {'targets': [removal()]*2, 'raiders': 3},
])
def test_intrinsic_invalid_bonus_is_atomic_and_does_not_spend_rng(response):
    state, request = after_raid()
    before = encode(state)
    with pytest.raises(ValueError):
        validate_response(state, request, response)
    assert encode(state) == before


@pytest.mark.parametrize('available', [False, True])
def test_explicit_extra_choice_requires_and_spends_a_fresh_counter(available):
    state, request = after_raid(hidden=int(available))
    response = {'targets': [removal()]*2, 'extra_warband': True}
    before = encode(state)
    if not available:
        with pytest.raises(ValueError):
            validate_response(state, request, response)
        assert encode(state) == before
        return
    validate_response(state, request, response)
    assert encode(state) == before
    state['decision_agent'] = lambda *args: response
    result = resolve_raid_intimidate(state, rc.UBII, 2)
    assert result['intimidations'][0]['raiding_warbands_used'] == 1
    assert result['intimidations'][0]['warbands_flipped'] == 1
    assert count_pieces(state, rc.UBII, rc.ROMANS, rc.AUXILIA) == 1


def test_caller_free_flag_cannot_forge_raid_credit_or_extra():
    state = dread(hidden=0)
    place_piece(state, rc.UBII, rc.GERMANS, rc.WARBAND, 3, piece_state=rc.REVEALED)
    before = encode(state)
    result = _execute_intimidate(state, rc.GERMANS, plan(3, free=True, extra_warband=True))
    assert not result['executed'] and result['errors']
    assert encode(state) == before


def test_np_ordinary_and_a45_default_share_dread_limit():
    from fs_bot.bots.german_bot import _select_intimidate_targets
    state = dread()
    before = encode(state)
    assert len(_select_intimidate_targets(state, rc.UBII, 3)) == 3
    assert encode(state) == before
    result = _resolve_card_A45_intimidate(state)[0]['result']
    assert result['executed'] and not result['errors']
    assert count_pieces(state, rc.UBII, rc.ROMANS, rc.AUXILIA) == 0


@pytest.mark.parametrize('timing', [False, True])
def test_ordinary_cli_can_select_three_without_mutating_live_state(timing):
    from fs_bot.cli.human_plan import _collect_intimidate
    state = dread()
    state['non_player_factions'] = set()
    if timing:
        state['_cli_action_windows'] = True
        done = 'Finish voluntary removal'
        answers = [done, rc.UBII, rc.ROMANS] + [f'{rc.AUXILIA} {rc.HIDDEN}']*3 + [done]
    else:
        answers = [rc.UBII, rc.ROMANS] + [rc.AUXILIA]*3
    before = encode(state)
    regions, extra = _collect_intimidate(state, rc.GERMANS,
        StringIO('\n'.join(answers)+'\n'), StringIO())
    assert regions == [rc.UBII] and len(extra['intimidate_plan']) == 3
    assert encode(state) == before
    state['_diviciacus_preview'] = True
    from fs_bot.cli.human_plan import _preview_sa
    result = _preview_sa(state, rc.GERMANS, {'command': rc.CMD_RAID,
        'sa': rc.SA_INTIMIDATE, 'sa_regions': regions, 'details': extra})
    assert result['executed'] and not result['errors']


@pytest.mark.parametrize('extra', [False, True])
def test_raid_cli_exposes_optional_extra_and_keeps_old_raider_choice(extra):
    from fs_bot.cli.reactive import make_cli_reactive
    state, _ = after_raid()
    before = encode(state)
    request = {'kind': 'raid_intimidate', 'region': rc.UBII, 'raiders': 2,
        'max_removals': 3, 'max_raider_removals': 2,
        'extra_warband_available': True, 'max_with_extra': 3,
        'targets': target_options(state, rc.UBII)}
    choice = ('Reveal one additional Hidden Warband for an extra removal' if extra
              else 'Use only the Warbands that Raided')
    answers = [f'Remove {rc.ROMANS} pieces and place the marker', choice] + [f'{rc.AUXILIA} ({rc.HIDDEN})']*(2+extra)
    response = make_cli_reactive([rc.GERMANS], StringIO('\n'.join(answers)+'\n'), StringIO())(
        state, rc.GERMANS, request)
    assert len(response['targets']) == 2+extra
    assert response.get('extra_warband', False) == extra
    validate_response(state, request, response)
    assert encode(state) == before


def test_random_reactive_policy_samples_valid_bonus_and_decline_choices():
    from fs_bot.tools.player_fuzz import make_random_reactive
    state, request = after_raid()
    request.update(kind='raid_intimidate', max_removals=3, max_raider_removals=2,
                   extra_warband_available=True, max_with_extra=3,
                   targets=target_options(state, rc.UBII))
    agent = make_random_reactive([rc.GERMANS], random.Random(27))
    before = encode(state)
    responses = [agent(state, rc.GERMANS, request) for _ in range(100)]
    assert {'decline': True} in responses and {'targets': []} in responses
    assert any(r.get('extra_warband') and len(r['targets']) == 3 for r in responses)
    for response in responses:
        validate_response(state, request, response)
    assert encode(state) == before


@pytest.mark.parametrize('new_warbands', [2, 4])
def test_a29_bonus_uses_surviving_placed_cohort_and_executor(new_warbands):
    from fs_bot.tests.test_harudes_bellovaci_choices import board, placements, play, raid
    from fs_bot.cards.harudes_bellovaci import HARUDES, RAID_CHOOSER
    state = board()
    activate_capability(state, 'A22', rc.EVENT_SHADED)
    place_piece(state, rc.TREVERI, rc.GERMANS, rc.LEADER, leader_name=rc.ARIOVISTUS_LEADER)
    place_piece(state, rc.TREVERI, rc.GERMANS, rc.WARBAND, 3)  # residents excluded
    place_piece(state, rc.TREVERI, rc.BELGAE, rc.WARBAND, 3)
    if new_warbands < 4:
        # A two-Warband reinforcement is legal only when the remaining
        # German supply is scarce; the Event still places its Settlement.
        from fs_bot.board.pieces import get_available
        surplus = get_available(state, rc.GERMANS, rc.WARBAND) - new_warbands
        place_piece(state, rc.SUGAMBRI, rc.GERMANS, rc.WARBAND, surplus)
    seen = []
    target = removal(rc.BELGAE, rc.WARBAND)
    def agent(current, chooser, request):
        if request.get('request_type') == HARUDES:
            return raid(count=2)
        if request['kind'] == 'raid_intimidate':
            seen.append(request)
            assert chooser == rc.ROMANS and request['acting_faction'] == rc.GERMANS
            assert request['extra_warband_available'] == (new_warbands > 2)
            if new_warbands == 2:
                before = encode(current)
                with pytest.raises(ValueError):
                    validate_response(current, request, {'targets': [target]*3, 'extra_warband': True})
                assert encode(current) == before
                return {'targets': [target]*2}
            return {'targets': [target]*3, 'extra_warband': True}
    state['decision_agent'] = agent
    result = play(state, rc.ROMANS, placements(new_warbands))
    assert result['executed'], result
    assert len(seen) == 1
    assert count_pieces_by_state(state, rc.TREVERI, rc.GERMANS, rc.WARBAND, rc.HIDDEN) == (3 if new_warbands == 2 else 4)
    assert RAID_CHOOSER not in state


@pytest.mark.parametrize('hidden,remaining', [(3, 0), (4, 1), (6, 3)])
def test_np_raid_then_ordinary_sa_recomputes_remaining_hidden(hidden, remaining):
    from fs_bot.bots.german_bot import node_g_raid
    from fs_bot.engine.execute import _execute_decision
    state = dread(hidden=hidden, targets=6)
    before = encode(state)
    action = node_g_raid(state)
    assert encode(state) == before  # includes RNG and detached intrinsic preview
    assert len(action.get('details', {}).get('intimidate_plan', [])) == remaining
    result = _execute_decision(state, rc.GERMANS, {'bot_action': action})
    assert result['executed'] and not result.get('errors'), result
    assert not result.get('sa_execution', {}).get('errors'), result
    assert count_pieces_by_state(state, rc.UBII, rc.GERMANS, rc.WARBAND, rc.HIDDEN) == 0
    assert count_pieces(state, rc.UBII, rc.ROMANS, rc.AUXILIA) == 6-hidden


def test_dread_pending_invalid_save_resume_exact_choice_and_journal(tmp_path):
    from fs_bot.tests.test_raid_intimidate_decisions import _session, _driver
    from fs_bot.engine.game_engine import _action_transaction
    from fs_bot.state.serialize import decode, save_game, load_game
    from fs_bot.tools.seat_session import SeatSession, DecisionPending, board_copy
    from fs_bot.cli.display import HumanTurnDisplay
    from fs_bot.cards.card_text import get_card_text
    state = dread()
    state['non_player_factions'].remove(rc.GERMANS)
    state['current_card'], state['next_card'] = 'A22', 'A29'
    session, output = _session(state)
    initial = encode(board_copy(state))
    def run(board, active_session):
        with _action_transaction(board, _driver(active_session)):
            return raid_in_region(board, rc.UBII, rc.GERMANS, [{'type': 'gain'}]*2)
    with pytest.raises(DecisionPending):
        run(state, session)
    pending = deepcopy(session.data['pending'])
    request = decode(pending['request'])
    assert request['max_removals'] == 3 and request['extra_warband_available']
    assert encode(board_copy(state)) == initial
    for card in (state['current_card'], state['next_card']):
        for line in get_card_text(card, state['scenario']).splitlines():
            assert line in output.getvalue()
    assert f'{rc.GERMANS} Resources: 0 -> 2' in output.getvalue()
    session.import_inbox({'decision_id': pending['id'],
                          'response': {'targets': [removal()]*3}})
    with pytest.raises(DecisionPending):
        run(state, session)
    assert session.error and session.data['pending']['id'] == pending['id']
    assert encode(board_copy(state)) == initial and session.data['journal'] == []
    # Replace the rejected queued answer, then persist the still-pending decision.
    session.data['queue'].clear()
    save_game(state, tmp_path/'dread.json', meta=session.meta, log=session.log)
    restored, meta, log = load_game(tmp_path/'dread.json')
    resumed = SeatSession(restored, meta, log, HumanTurnDisplay(StringIO()))
    restored['decision_agent'] = resumed.reactive
    chosen = {'targets': [removal()]*3, 'extra_warband': True}
    resumed.import_inbox({'decision_id': pending['id'], 'response': chosen})
    result = run(restored, resumed)
    resumed.finish()
    assert result['raid_intimidate']['executed']
    assert count_pieces(restored, rc.UBII, rc.ROMANS, rc.AUXILIA) == 0
    assert count_pieces_by_state(restored, rc.UBII, rc.GERMANS, rc.WARBAND, rc.REVEALED) == 3
    assert len(log) == 1 and decode(log[0]['assistant_response']) == chosen
    # Replaying the recorded explicit response spends precisely the same counters/RNG.
    replay = dread()
    replay['non_player_factions'].remove(rc.GERMANS)
    replay['current_card'], replay['next_card'] = 'A22', 'A29'
    replay['decision_agent'] = lambda *args: decode(log[0]['assistant_response'])
    raid_in_region(replay, rc.UBII, rc.GERMANS, [{'type': 'gain'}]*2)
    assert encode(board_copy(replay)) == encode(board_copy(restored))


@pytest.mark.parametrize('side', [None, rc.EVENT_SHADED, rc.EVENT_UNSHADED, 'removed'])
def test_unshaded_dread_also_protects_recruit_from_intimidated_marker(side):
    from fs_bot.commands.rally import validate_recruit_region, validate_rally_region
    state = position(hidden=0)
    place_piece(state, rc.UBII, rc.ROMANS, rc.FORT)
    place_piece(state, rc.UBII, rc.AEDUI, rc.ALLY)
    state['markers'][rc.UBII] = {rc.MARKER_INTIMIDATED: True}
    if side:
        activate_capability(state, 'A22', rc.EVENT_UNSHADED if side == 'removed' else side)
    if side == 'removed':
        deactivate_capability(state, 'A22')
    before = encode(state)
    valid, reason = validate_recruit_region(state, rc.UBII)
    assert valid == (side == rc.EVENT_UNSHADED), reason
    # A22 never makes the marker ineffective on another non-German Faction.
    assert not validate_rally_region(state, rc.UBII, rc.AEDUI)[0]
    assert encode(state) == before
    if valid:
        state['markers'][rc.UBII][rc.MARKER_DEVASTATED] = True
        assert not validate_recruit_region(state, rc.UBII)[0]
