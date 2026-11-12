"""Final Winter after the Gallic War Interlude and standard solitaire victory."""

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces
from fs_bot.cards.card_effects import _ally_tribe, _unally_tribe
from fs_bot.engine.game_engine import (
    draw_card, get_sop_factions, play_card, resolve_winter_card,
)
from fs_bot.engine.victory import check_any_victory, check_victory
from fs_bot.state.serialize import load_game, save_game
from fs_bot.state.setup import setup_scenario
from fs_bot.state.state_schema import check_structural_integrity, validate_state


def _draw_to_winter(state, ordinal):
    while state['played_cards'].count(rc.WINTER_CARD) < ordinal:
        draw_card(state)
    assert state['current_card'] == rc.WINTER_CARD
    return state


def _play_winter(state):
    def unexpected_turn(*args):
        pytest.fail('An Event turn was requested during Winter resolution')

    assert not validate_state(state)
    assert not check_structural_integrity(state)
    result = play_card(state, unexpected_turn, execute=True)
    assert not validate_state(state)
    assert not check_structural_integrity(state)
    return result


@pytest.mark.parametrize('ordinal,sudden_frost', [(4, False), (5, True)])
def test_post_interlude_winter_uses_the_rebuilt_deck(tmp_path, ordinal, sudden_frost):
    state = setup_scenario(rc.SCENARIO_GALLIC_WAR, seed=21, sudden_frost=sudden_frost)
    _draw_to_winter(state, 3)
    state['winter_count'] = 2
    first_half = resolve_winter_card(state, britannia_decision=False)
    assert not first_half['is_final']
    assert 'interlude' in first_half['winter_result']
    assert state['deck'].count(rc.WINTER_CARD) == 5

    # Model a later board where no Faction passes a victory check. These
    # placements keep the cumulative Winter count and real Interlude deck.
    for tribe in (rc.TRIBE_BITURIGES, rc.TRIBE_NAMNETES, rc.TRIBE_VENETI,
                  rc.TRIBE_SENONES, rc.TRIBE_CARNUTES, rc.TRIBE_PICTONES):
        assert _ally_tribe(state, tribe, rc.ARVERNI)
    for tribe in (rc.TRIBE_SUEBI_SOUTH, rc.TRIBE_NERVII):
        assert _ally_tribe(state, tribe, rc.GERMANS)
    assert check_any_victory(state) is None
    state.pop('first_winter_special', None)
    state['first_harvest_after_interlude_pending'] = False
    state['first_senate_after_interlude_pending'] = False
    _draw_to_winter(state, ordinal)
    state['winter_count'] = 3 + ordinal - 1
    remaining_winters = state['deck'].count(rc.WINTER_CARD)
    assert remaining_winters == 5 - ordinal
    # Sudden Frost leaves the preceding Event to be played next if the
    # game continues. The fifth Winter still ends the game.
    assert state['deck'] and state['deck'][0] != rc.WINTER_CARD

    path = tmp_path / 'winter.json'
    save_game(state, path)
    loaded, _, _ = load_game(path, validate=True)
    result = _play_winter(state)
    assert _play_winter(loaded) == result
    assert state['winter_count'] == 3 + ordinal
    assert result['game_over'] == result['winter_result']['is_final'] == (ordinal == 5)
    if ordinal == 4:
        assert result['next_card'] != rc.WINTER_CARD
        assert state['deck'].count(rc.WINTER_CARD) == 1
        assert 'spring' in result['winter_result']['winter_result']['phases']
    else:
        assert len(result['final_ranking']) == 4
        assert state['current_card'] == rc.WINTER_CARD


def _roman_threshold_board(scenario, humans, *, legacy=False):
    owners = None if legacy else {faction: faction for faction in humans}
    state = setup_scenario(scenario, seed=21, faction_owners=owners)
    if legacy:
        state['non_player_factions'] = set(get_sop_factions(state)).difference(humans)
        assert 'faction_owners' not in state
    if scenario == rc.SCENARIO_RECONQUEST:
        _unally_tribe(state, rc.TRIBE_MENAPII)
    _unally_tribe(state, rc.TRIBE_MORINI)
    assert check_victory(state, rc.ROMANS)
    assert check_any_victory(state) == rc.ROMANS
    return state


@pytest.mark.parametrize('scenario,legacy', [
    (rc.SCENARIO_RECONQUEST, False),
    (rc.SCENARIO_RECONQUEST, True),
    (rc.SCENARIO_ARIOVISTUS, False),
])
def test_solo_threshold_keeps_nonfinal_winter_open(tmp_path, scenario, legacy):
    state = _roman_threshold_board(scenario, (rc.ROMANS,), legacy=legacy)
    _draw_to_winter(state, 1)
    path = tmp_path / 'solo.json'
    save_game(state, path)
    loaded, _, _ = load_game(path, validate=True)

    result = _play_winter(loaded)

    assert not result['winter_result']['is_final']
    assert not result['game_over']
    assert not result.get('winner')
    assert 'spring' in result['winter_result']['winter_result']['phases']


@pytest.mark.parametrize('humans', [(), (rc.ARVERNI,), (rc.ROMANS, rc.ARVERNI)],
                         ids=['all-bots', 'solo-opponent', 'two-players'])
def test_roman_threshold_still_ends_nonfinal_winter_for_other_seats(humans):
    state = _roman_threshold_board(rc.SCENARIO_RECONQUEST, humans)
    result = _play_winter(_draw_to_winter(state, 1))

    assert not result['winter_result']['is_final']
    assert result['game_over'] and result['winner'] == rc.ROMANS


def test_solo_final_winter_awards_highest_margin_without_a_threshold():
    state = _roman_threshold_board(rc.SCENARIO_RECONQUEST, (rc.ROMANS,))
    assert _ally_tribe(state, rc.TRIBE_NAMNETES, rc.ARVERNI)
    assert check_any_victory(state) is None
    _draw_to_winter(state, 4)
    state['winter_count'] = 3

    result = _play_winter(state)

    assert result['winter_result']['is_final']
    assert result['game_over'] and result['winner'] == rc.ROMANS
    assert result['final_ranking'][0] == (rc.ROMANS, 0)


def test_optimates_can_end_solo_play_at_an_earlier_winter():
    state = _roman_threshold_board(rc.SCENARIO_RECONQUEST, (rc.ROMANS,))
    _draw_to_winter(state, 2)
    state['winter_count'] = 1
    state['event_modifiers'] = {'optimates_active': True}

    result = _play_winter(state)

    assert not result['winter_result']['is_final']
    assert result['game_over']
    assert result['winter_result']['winter_result']['phases']['victory']['optimates_end']
    assert not any(count_pieces(state, region, rc.ROMANS, rc.LEGION)
                   for region in state['spaces'])
