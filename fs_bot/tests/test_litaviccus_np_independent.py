"""Source-derived Litaviccus checks, independent of the selector's search.

Card45, Belgic Event Instructions, §§8.2.3/8.3.4/8.5.1 and provisional
PR-12. Forecast assertions count printed Losses, never expected die deaths.
"""
from random import Random

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces, count_pieces_by_state, place_piece
from fs_bot.bots.bot_common import should_decline_event
from fs_bot.bots.belgae_bot import node_b3b
from fs_bot.cards.event_conditions import np_event_available
from fs_bot.engine import execute as ex
from fs_bot.state.serialize import encode
from fs_bot.state.state_schema import build_initial_state, validate_state


def board(scenario=rc.SCENARIO_GREAT_REVOLT, *, roman_bot=True):
    state = build_initial_state(scenario, seed=45)
    state.update(current_card=45, current_card_id=45, next_card=3,
                 non_player_factions={rc.BELGAE, rc.ARVERNI, rc.AEDUI})
    if scenario in rc.ARIOVISTUS_SCENARIOS:
        state['non_player_factions'].discard(rc.ARVERNI)
        state['non_player_factions'].add(rc.GERMANS)
    if roman_bot:
        state['non_player_factions'].add(rc.ROMANS)
    return state


def romans(state, region, legions=1, auxilia=0):
    if legions:
        place_piece(state, region, rc.ROMANS, rc.LEGION, legions,
                    from_legions_track=True)
    if auxilia:
        place_piece(state, region, rc.ROMANS, rc.AUXILIA, auxilia)


def snapshot(state):
    return encode({key:value for key,value in state.items() if key!='decision_agent'})


@pytest.mark.parametrize('scenario', sorted(rc.BASE_SCENARIOS))
def test_np_selects_exposed_legion_instead_of_largest_roman_stack(scenario):
    state = board(scenario)
    place_piece(state, rc.CARNUTES, rc.BELGAE, rc.LEADER, leader_name=rc.AMBIORIX)
    place_piece(state, rc.CARNUTES, rc.BELGAE, rc.WARBAND, 10)
    romans(state, rc.CARNUTES, legions=0, auxilia=10)
    place_piece(state, rc.MANDUBII, rc.BELGAE, rc.WARBAND, 2)
    romans(state, rc.MANDUBII)

    result = ex._resolve_card45_battle(state, rc.BELGAE)[0]

    assert result['region'] == rc.MANDUBII
    assert result['ambush']
    assert count_pieces(state, rc.MANDUBII, rc.ROMANS, rc.LEGION) == 0
    assert count_pieces(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA) == 10
    assert validate_state(state) == []


@pytest.mark.parametrize('roman_bot', [False, True])
def test_zero_legion_loss_is_no_belgae_before_the_event_is_selected(roman_bot):
    state = board(roman_bot=roman_bot)
    place_piece(state, rc.CARNUTES, rc.BELGAE, rc.LEADER, leader_name=rc.AMBIORIX)
    place_piece(state, rc.CARNUTES, rc.BELGAE, rc.WARBAND, 4)
    romans(state, rc.CARNUTES, legions=0, auxilia=2)
    before = snapshot(state)

    assert np_event_available(state, 45, rc.BELGAE, True) is False
    assert should_decline_event(state, 45, rc.BELGAE)
    assert node_b3b(state) == 'Yes'
    assert snapshot(state) == before


def test_granted_aedui_only_small_force_can_force_legion_losses_with_ambush():
    state = board()
    place_piece(state, rc.CARNUTES, rc.BELGAE, rc.LEADER, leader_name=rc.AMBIORIX)
    place_piece(state, rc.CARNUTES, rc.BELGAE, rc.WARBAND, 4)
    romans(state, rc.CARNUTES, legions=0, auxilia=6)
    place_piece(state, rc.MANDUBII, rc.AEDUI, rc.WARBAND, 2)
    romans(state, rc.MANDUBII)

    assert not should_decline_event(state, 45, rc.BELGAE)
    result = ex._resolve_card45_battle(state, rc.BELGAE)[0]

    assert result['region'] == rc.MANDUBII and result['ambush']
    assert count_pieces(state, rc.MANDUBII, rc.ROMANS, rc.LEGION) == 0
    assert count_pieces(state, rc.MANDUBII, rc.AEDUI, rc.WARBAND) == 2
    assert count_pieces_by_state(state, rc.MANDUBII, rc.AEDUI, rc.WARBAND, rc.HIDDEN) == 0
    assert validate_state(state) == []


@pytest.mark.parametrize('actor', [rc.BELGAE, rc.ARVERNI])
def test_human_granted_aedui_force_takes_counterattack_and_reveals(actor):
    state = board()
    state['non_player_factions'].discard(actor)
    state['non_player_factions'].discard(rc.ROMANS)
    place_piece(state, rc.CARNUTES, rc.AEDUI, rc.WARBAND, 2)
    romans(state, rc.CARNUTES, legions=0, auxilia=4)
    def agent(current, faction, request):
        if request.get('request_type') == 'fixed_event_battle':
            return {'region':rc.CARNUTES, 'defender':rc.ROMANS}
        if request['kind'] == 'retreat':
            return {'retreat':False}
        return None
    state['decision_agent'] = agent

    result = ex._resolve_card45_battle(state, actor)[0]

    assert not result['ambush']
    assert count_pieces(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA) == 3
    assert count_pieces(state, rc.CARNUTES, rc.AEDUI, rc.WARBAND) == 1
    assert count_pieces_by_state(state, rc.CARNUTES, rc.AEDUI, rc.WARBAND, rc.REVEALED) == 1
    assert validate_state(state) == []


@pytest.mark.parametrize('roman_bot', [False, True])
def test_retreat_forecast_counts_one_legion_loss_not_two(roman_bot):
    from fs_bot.cards import litaviccus_np as policy
    state = board(roman_bot=roman_bot)
    place_piece(state, rc.NERVII, rc.BELGAE, rc.WARBAND, 4)
    romans(state, rc.NERVII, legions=3)
    romans(state, rc.MORINI, legions=0, auxilia=1)
    before = snapshot(state)

    assert policy.predicted_legion_losses(state, rc.NERVII) == 1
    assert snapshot(state) == before


def test_fort_and_auxilia_absorb_losses_before_legions():
    from fs_bot.cards import litaviccus_np as policy
    state = board()
    place_piece(state, rc.NERVII, rc.BELGAE, rc.WARBAND, 8)
    romans(state, rc.NERVII, legions=2, auxilia=2)
    assert policy.predicted_legion_losses(state, rc.NERVII) == 2
    place_piece(state, rc.NERVII, rc.ROMANS, rc.FORT)
    assert policy.predicted_legion_losses(state, rc.NERVII) == 0


def test_printed_battle_safety_rejects_equal_losses_despite_exposed_legion():
    from fs_bot.cards import litaviccus_np as policy
    state = board()
    place_piece(state, rc.NERVII, rc.BELGAE, rc.WARBAND, 2)
    romans(state, rc.NERVII, legions=2)
    # No Ambiorix means no Ambush. One Legion is removed in the forecast;
    # the survivor Counterattacks for one Loss, so 1 is not greater than 1.
    assert not policy.available(state)
    assert should_decline_event(state, 45, rc.BELGAE)


class NoPredictionRolls(Random):
    def random(self):
        pytest.fail('Litaviccus prediction sampled future randomness')
    def getrandbits(self, bits):
        pytest.fail('Litaviccus prediction sampled future randomness')


def test_forecast_and_availability_never_query_humans_or_sample_live_future_rolls():
    from fs_bot.cards import litaviccus_np as policy
    state = board(roman_bot=False)
    place_piece(state, rc.NERVII, rc.BELGAE, rc.WARBAND, 4)
    romans(state, rc.NERVII, legions=3)
    romans(state, rc.MORINI, legions=0, auxilia=1)
    rng = NoPredictionRolls()
    rng.setstate(state['rng'].getstate())
    state['rng'] = rng
    def reject_input(*args):
        pytest.fail('Litaviccus forecast queried a real decision agent')
    state['decision_agent'] = reject_input
    before = snapshot(state)

    assert policy.predicted_legion_losses(state, rc.NERVII) == 1
    assert policy.available(state)
    assert policy.plan(state, choose=False) is not None
    assert not should_decline_event(state, 45, rc.BELGAE)
    assert snapshot(state) == before


@pytest.mark.parametrize('scenario', sorted(rc.ARIOVISTUS_SCENARIOS))
def test_base_litaviccus_policy_does_not_apply_to_expansion_scenarios(scenario):
    from fs_bot.cards import litaviccus_np as policy
    state = board(scenario)
    place_piece(state, rc.CARNUTES, rc.BELGAE, rc.LEADER, leader_name=rc.AMBIORIX)
    place_piece(state, rc.MANDUBII, rc.AEDUI, rc.WARBAND, 2)
    romans(state, rc.MANDUBII)
    before = snapshot(state)
    assert not policy.available(state)
    assert policy.plan(state, choose=False) is None
    assert snapshot(state) == before


def test_equal_best_targets_use_seeded_choice_only_when_committed():
    from fs_bot.cards import litaviccus_np as policy
    seen = set()
    for seed in range(8):
        state = board()
        state['rng'].seed(seed)
        place_piece(state, rc.CARNUTES, rc.BELGAE, rc.LEADER, leader_name=rc.AMBIORIX)
        for region in (rc.ATREBATES, rc.MANDUBII):
            place_piece(state, region, rc.BELGAE, rc.WARBAND, 2)
            romans(state, region)
        before = snapshot(state)
        assert policy.plan(state, choose=False)['predicted_legion_losses'] == 1
        assert snapshot(state) == before
        chosen = policy.plan(state, choose=True)
        seen.add(chosen['region'])
        after = snapshot(state)
        assert after['rng'] != before['rng']
        assert {k:v for k,v in after.items() if k!='rng'} == {
            k:v for k,v in before.items() if k!='rng'}
    assert seen == {rc.ATREBATES, rc.MANDUBII}


class FirstRollRemoves(Random):
    def randint(self, low, high):
        return low


def test_conservative_forecast_does_not_bind_actual_human_retreat_choice():
    from fs_bot.cards import litaviccus_np as policy
    state = board(roman_bot=False)
    state['rng'] = FirstRollRemoves(45)
    place_piece(state, rc.NERVII, rc.BELGAE, rc.WARBAND, 4)
    romans(state, rc.NERVII, legions=3)
    romans(state, rc.MORINI, legions=0, auxilia=1)
    seen = []
    def agent(current, actor, request):
        if request['kind'] == 'retreat':
            seen.append(actor)
            return {'retreat': False}
        return None
    state['decision_agent'] = agent
    assert policy.predicted_legion_losses(state, rc.NERVII) == 1
    assert seen == []

    result = ex._resolve_card45_battle(state, rc.BELGAE)[0]

    assert result['region'] == rc.NERVII
    assert seen == [rc.ROMANS]
    # The human stands despite the forecasted safer Retreat. Both real
    # Legion rolls remove their pieces; the actual result is two, not one.
    assert count_pieces(state, rc.NERVII, rc.ROMANS, rc.LEGION) == 1
    assert validate_state(state) == []


def test_slingers_prefire_does_not_erase_caesars_already_valid_ambush_escape():
    """The forecast must retain the Ambush status already set by execution."""
    from fs_bot.cards import litaviccus_np as policy
    from fs_bot.cards.capabilities import activate_capability
    state = board()
    place_piece(state, rc.CARNUTES, rc.BELGAE, rc.LEADER, leader_name=rc.AMBIORIX)
    place_piece(state, rc.CARNUTES, rc.BELGAE, rc.WARBAND, 3)
    romans(state, rc.CARNUTES, legions=3, auxilia=2)
    place_piece(state, rc.CARNUTES, rc.ROMANS, rc.LEADER, leader_name=rc.CAESAR)
    activate_capability(state, 13, rc.EVENT_UNSHADED)
    before = snapshot(state)
    # Slingers remove one Warband, then the still-valid Ambush causes3
    # Losses (two Auxilia and one Legion). Caesar's5–6 escape permits the
    # two surviving Legions + Caesar to Counterattack for3, touching
    # Ambiorix after the two Warbands. Safety cannot be guaranteed.
    assert not policy.available(state)
    assert should_decline_event(state, 45, rc.BELGAE)
    assert snapshot(state) == before
