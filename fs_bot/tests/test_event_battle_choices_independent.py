"""Independent source checks for numeric Event Battle ownership and limits.

Card Reference 11, 25, 36, 45, 70; revised 11 in A Card Reference;
Chapter 5 §§5.1, 5.1.1, 5.1.3 and 5.4. Free Battle target choices do
not grant additional Commands, optional Special Abilities or new modifiers.
"""
import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces, count_pieces_by_state, place_piece
from fs_bot.engine import execute as ex
from fs_bot.state.serialize import encode
from fs_bot.state.state_schema import build_initial_state, validate_state


def board():
    state = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=11)
    state['non_player_factions'] = set()
    return state


def physical(state):
    return encode({k: v for k, v in state.items() if k != 'decision_agent'})


def choose(state, region, defender, *, response=None):
    seen = []
    def agent(current, actor, request):
        if (request.get('kind') == 'free_action'
                and request.get('request_type') == 'fixed_event_battle'):
            seen.append((actor, request))
            return response if response is not None else {'region': region, 'defender': defender}
        if request.get('kind') == 'retreat':
            return {'retreat': False}
        return None
    state['decision_agent'] = agent
    return seen


@pytest.mark.parametrize('flag,expected_remaining', [('card_11', 2), ('card_11a', 3)])
def test_numidians_roman_human_chooses_defender_and_keeps_edition_loss_rules(flag, expected_remaining):
    state = board()
    state['executing_faction'] = rc.BELGAE
    place_piece(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA, 2)
    place_piece(state, rc.CARNUTES, rc.ROMANS, rc.LEGION, from_legions_track=True)
    place_piece(state, rc.CARNUTES, rc.ARVERNI, rc.WARBAND, 6)
    place_piece(state, rc.CARNUTES, rc.AEDUI, rc.WARBAND, 5)
    seen = choose(state, rc.CARNUTES, rc.AEDUI)

    result = ex._resolve_double_aux_battle_card(state, rc.CARNUTES, flag)

    assert [actor for actor, request in seen] == [rc.ROMANS]
    assert count_pieces(state, rc.CARNUTES, rc.AEDUI, rc.WARBAND) == expected_remaining
    assert count_pieces(state, rc.CARNUTES, rc.ARVERNI, rc.WARBAND) == 6
    assert result[0]['result']
    assert state['resources'][rc.ROMANS] == 0
    assert validate_state(state) == []


def test_aquitani_human_can_choose_second_region_and_battle_without_own_forces():
    state = board()
    place_piece(state, rc.PICTONES, rc.ARVERNI, rc.WARBAND, 5)
    place_piece(state, rc.ARVERNI_REGION, rc.AEDUI, rc.WARBAND, 3)
    seen = choose(state, rc.ARVERNI_REGION, rc.AEDUI)

    result = ex._resolve_card25_battle(state, rc.ROMANS, None, 3)

    assert seen and seen[0][0] == rc.ROMANS
    assert set(seen[0][1]['allowed_regions']) == {rc.PICTONES, rc.ARVERNI_REGION}
    assert result[0]['region'] == rc.ARVERNI_REGION
    assert result[0]['defender'] == rc.AEDUI
    assert count_pieces(state, rc.ARVERNI_REGION, rc.AEDUI) == 0
    assert count_pieces(state, rc.PICTONES, rc.ARVERNI, rc.WARBAND) == 5
    assert count_pieces(state, rc.ARVERNI_REGION, rc.ROMANS) == 0
    assert validate_state(state) == []


def test_aquitani_explicit_region_is_binding_for_later_defender_choice():
    state = board()
    place_piece(state, rc.PICTONES, rc.AEDUI, rc.WARBAND, 3)
    place_piece(state, rc.ARVERNI_REGION, rc.BELGAE, rc.WARBAND, 3)
    choose(state, rc.ARVERNI_REGION, rc.BELGAE)
    before = physical(state)
    with pytest.raises(ValueError):
        ex._resolve_card25_battle(state, rc.ROMANS, rc.PICTONES, 3)
    assert physical(state) == before


def test_morasses_human_selects_smaller_target_keeps_hidden_and_no_counterattack():
    state = board()
    for region in (rc.CARNUTES, rc.MANDUBII):
        place_piece(state, region, rc.BELGAE, rc.WARBAND, 4)
    place_piece(state, rc.CARNUTES, rc.ARVERNI, rc.WARBAND, 8)
    place_piece(state, rc.MANDUBII, rc.AEDUI, rc.WARBAND, 4)
    seen = choose(state, rc.MANDUBII, rc.AEDUI)

    result = ex._resolve_card36_battle(state, rc.BELGAE)

    assert seen and seen[0][0] == rc.BELGAE
    assert result[0]['region'] == rc.MANDUBII and result[0]['defender'] == rc.AEDUI
    assert count_pieces(state, rc.CARNUTES, rc.ARVERNI, rc.WARBAND) == 8
    assert count_pieces(state, rc.MANDUBII, rc.AEDUI, rc.WARBAND) == 2
    assert count_pieces_by_state(state, rc.MANDUBII, rc.BELGAE, rc.WARBAND, rc.HIDDEN) == 4
    assert validate_state(state) == []


@pytest.mark.parametrize('illegal', [
    {'region': rc.CARNUTES, 'defender': rc.ROMANS},
    {'region': rc.CARNUTES, 'defender': rc.AEDUI, 'extra_losses': 9},
    {'region': rc.CARNUTES, 'defender': rc.AEDUI, 'sa': 'Ambush'},
])
def test_morasses_rejects_outside_target_and_forged_event_power_without_mutation(illegal):
    state = board()
    place_piece(state, rc.CARNUTES, rc.BELGAE, rc.WARBAND, 4)
    place_piece(state, rc.CARNUTES, rc.AEDUI, rc.WARBAND, 3)
    place_piece(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA, 3)
    choose(state, rc.CARNUTES, rc.AEDUI, response=illegal)
    before = physical(state)
    with pytest.raises(ValueError):
        ex._resolve_card36_battle(state, rc.BELGAE)
    assert physical(state) == before


def test_litaviccus_human_selects_aedui_only_region_and_uses_combined_ambush():
    state = board()
    place_piece(state, rc.CARNUTES, rc.BELGAE, rc.WARBAND, 4)
    place_piece(state, rc.CARNUTES, rc.BELGAE, rc.LEADER, leader_name=rc.AMBIORIX)
    place_piece(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA, 5)
    place_piece(state, rc.MANDUBII, rc.AEDUI, rc.WARBAND, 3)
    place_piece(state, rc.MANDUBII, rc.ROMANS, rc.AUXILIA, 1)
    seen = choose(state, rc.MANDUBII, rc.ROMANS)

    result = ex._resolve_card45_battle(state, rc.BELGAE)

    assert seen and seen[0][0] == rc.BELGAE
    assert result[0]['region'] == rc.MANDUBII
    assert result[0]['ambush'] is True
    assert count_pieces(state, rc.MANDUBII, rc.ROMANS) == 0
    assert count_pieces(state, rc.MANDUBII, rc.AEDUI, rc.WARBAND) == 3
    assert count_pieces(state, rc.MANDUBII, rc.BELGAE) == 0
    assert count_pieces(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA) == 5
    assert validate_state(state) == []


def test_camulogenus_roman_defender_choice_follows_existing_march_destination():
    state = board()
    place_piece(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA, 2)
    place_piece(state, rc.MANDUBII, rc.ARVERNI, rc.WARBAND, 6)
    place_piece(state, rc.MANDUBII, rc.AEDUI, rc.WARBAND, 2)
    seen = choose(state, rc.MANDUBII, rc.AEDUI)

    result = ex._resolve_card70_march_battle(state, [rc.MANDUBII], 4)

    assert seen and seen[0][0] == rc.ROMANS
    assert seen[0][1]['allowed_regions'] == [rc.MANDUBII]
    assert result[0]['defender'] == rc.AEDUI
    assert count_pieces(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA) == 0
    assert count_pieces(state, rc.MANDUBII, rc.ARVERNI, rc.WARBAND) == 6
    assert validate_state(state) == []


@pytest.mark.parametrize('card', [11, 25, 36, 45, 70])
def test_possible_required_battle_cannot_be_independently_declined(card):
    state = board()
    region = rc.PICTONES
    place_piece(state, region, rc.BELGAE, rc.WARBAND, 4)
    place_piece(state, region, rc.ROMANS, rc.AUXILIA, 4)
    place_piece(state, region, rc.AEDUI, rc.WARBAND, 4)
    choose(state, region, rc.AEDUI, response={'decline': True})
    before = physical(state)
    with pytest.raises(ValueError):
        if card == 11:
            ex._resolve_double_aux_battle_card(state, region, 'card_11')
        elif card == 25:
            ex._resolve_card25_battle(state, rc.BELGAE, region, 3)
        elif card == 36:
            ex._resolve_card36_battle(state, rc.BELGAE)
        elif card == 45:
            ex._resolve_card45_battle(state, rc.BELGAE)
        else:
            # No March occurs here; only the already selected destination's
            # Battle remains, so a rejected response must change no board.
            ex._resolve_card70_march_battle(state, [region], 4)
    assert physical(state) == before


@pytest.mark.parametrize('flag,legions_remaining', [('card_11', 0), ('card_11a', 1)])
def test_only_auxilia_battle_cannot_lose_a_nonparticipating_legion(flag, legions_remaining):
    """Revised11 restricts attackers;3.2.4 Counterattack hits attacking Forces."""
    state = board()
    state['rng'].seed(1)
    place_piece(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA, 2)
    place_piece(state, rc.CARNUTES, rc.ROMANS, rc.LEGION, from_legions_track=True)
    place_piece(state, rc.CARNUTES, rc.BELGAE, rc.WARBAND, 9)
    choose(state, rc.CARNUTES, rc.BELGAE)

    result = ex._resolve_double_aux_battle_card(state, rc.CARNUTES, flag)

    assert count_pieces(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA) == 0
    assert count_pieces(state, rc.CARNUTES, rc.ROMANS, rc.LEGION) == legions_remaining
    if flag == 'card_11a':
        assert result[0]['result']['counterattack']['rolls'] == []
    assert validate_state(state) == []


def test_litaviccus_aedui_executor_does_not_double_its_own_warbands():
    """Using Aedui pieces as own does not duplicate the Aedui's own force."""
    state = board()
    place_piece(state, rc.CARNUTES, rc.AEDUI, rc.WARBAND, 4)
    place_piece(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA, 3)
    choose(state, rc.CARNUTES, rc.ROMANS)

    result = ex._resolve_card45_battle(state, rc.AEDUI)

    assert result[0]['ambush'] is True
    assert count_pieces(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA) == 1
    assert count_pieces(state, rc.CARNUTES, rc.AEDUI, rc.WARBAND) == 4
    assert validate_state(state) == []


def test_revised_numidians_without_auxilia_cannot_borrow_an_ineligible_force():
    """Card38 requires physical Auxilia and Aedui Warbands together first."""
    from fs_bot.cards.card_effects import execute_card_38
    state = board()
    place_piece(state, rc.CARNUTES, rc.ROMANS, rc.LEGION, from_legions_track=True)
    place_piece(state, rc.CARNUTES, rc.AEDUI, rc.WARBAND, 2)
    place_piece(state, rc.CARNUTES, rc.BELGAE, rc.WARBAND, 2)
    execute_card_38(state)
    seen = []
    def agent(current, actor, request):
        seen.append((actor, request['kind']))
        if request['kind'] == 'free_action':
            return {'region': rc.CARNUTES, 'defender': rc.BELGAE}
        if request['kind'] == 'agreement':
            return True
        if request['kind'] == 'retreat':
            return {'retreat': False}
        return None
    state['decision_agent'] = agent

    result = ex._resolve_double_aux_battle_card(state, rc.CARNUTES, 'card_11a')

    assert (rc.ROMANS, 'free_action') not in seen
    assert (rc.AEDUI, 'agreement') not in seen
    assert count_pieces(state, rc.CARNUTES, rc.BELGAE) == 2
    assert count_pieces(state, rc.CARNUTES, rc.ROMANS, rc.LEGION) == 1
    assert count_pieces(state, rc.CARNUTES, rc.AEDUI, rc.WARBAND) == 2
    assert count_pieces(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA) == 0
    assert result[0]['declined_no_effect'] is True
    assert validate_state(state) == []
