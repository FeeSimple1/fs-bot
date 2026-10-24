"""A Setup/A1.4: the original-scenario Diviciacus Leader option.

This option replaces card 38, adds only the Aedui Leader, and applies his
printed rules. It does not select the five revised cards or expansion rules.
"""
import io
from argparse import Namespace

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import (find_leader, get_available, place_piece,
                                  remove_piece, _get_caps)
from fs_bot.cards.card_effects import execute_event
from fs_bot.cards.edition import CARD_EDITIONS
from fs_bot.state.setup import setup_scenario
from fs_bot.state.state_schema import build_initial_state, validate_state
from fs_bot.state.serialize import save_game, load_game, encode


def empty_option(seed=4):
    return build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=seed,
                               diviciacus_option=True)


def place_diviciacus(state, region=rc.CARNUTES):
    state['event_params'] = {'region': region}
    execute_event(state, rc.CARD_O38)


@pytest.mark.parametrize('scenario', rc.BASE_SCENARIOS)
@pytest.mark.parametrize('edition', CARD_EDITIONS)
def test_option_replaces_only_card_38_and_only_adds_the_leader(scenario, edition):
    ordinary = setup_scenario(scenario, seed=9, card_edition=edition)
    optional = setup_scenario(scenario, seed=9, card_edition=edition,
                              diviciacus_option=True)
    assert optional['deck'] == [rc.CARD_O38 if c == 38 else c
                               for c in ordinary['deck']]
    assert ordinary['rng'].getstate() == optional['rng'].getstate()
    assert optional['spaces'] == ordinary['spaces']
    assert optional['available'] == ordinary['available']
    assert optional['removed_pieces'] == {rc.AEDUI: {rc.LEADER: 1}}
    assert get_available(optional, rc.AEDUI, rc.LEADER) == 0
    assert _get_caps(optional)[rc.GERMANS] == rc.CAPS_BASE[rc.GERMANS]
    assert _get_caps(optional)[rc.ARVERNI] == rc.CAPS_BASE[rc.ARVERNI]
    assert _get_caps(optional)[rc.AEDUI][rc.LEADER] == 1
    assert validate_state(optional) == []
    assert optional['card_edition'] == edition


@pytest.mark.parametrize('scenario', rc.ARIOVISTUS_SCENARIOS)
def test_optional_setup_rejects_expansion_scenarios(scenario):
    with pytest.raises(ValueError, match='only to original scenarios'):
        setup_scenario(scenario, diviciacus_option=True)


@pytest.mark.parametrize('bad', [1, 'yes', None])
def test_optional_setup_requires_a_boolean(bad):
    with pytest.raises(ValueError, match='true or false'):
        setup_scenario(rc.SCENARIO_PAX_GALLICA, diviciacus_option=bad)


def test_o38_places_and_removes_a_never_available_leader():
    state = empty_option()
    place_diviciacus(state, rc.BRITANNIA)
    assert find_leader(state, rc.AEDUI) == rc.BRITANNIA
    assert state['diviciacus_in_play'] is True
    assert get_available(state, rc.AEDUI, rc.LEADER) == 0
    assert state['removed_pieces'][rc.AEDUI][rc.LEADER] == 0
    assert validate_state(state) == []
    with pytest.raises(ValueError, match='already in play'):
        place_diviciacus(state)
    remove_piece(state, rc.BRITANNIA, rc.AEDUI, rc.LEADER)
    assert get_available(state, rc.AEDUI, rc.LEADER) == 0
    assert state['removed_pieces'][rc.AEDUI][rc.LEADER] == 1
    assert not state['diviciacus_in_play']
    assert validate_state(state) == []


def test_o38_rejects_an_unplayable_region_before_changing_the_pool():
    state = empty_option()
    state['event_params'] = {'region': rc.CISALPINA}
    before = encode(state)
    with pytest.raises(ValueError, match='playable Region'):
        execute_event(state, rc.CARD_O38)
    assert encode(state) == before


def test_o38_bot_effect_checks_distinguish_placement_from_shaded_capability():
    from fs_bot.cards.event_eval import (get_event_flags, PLACES_LEADER,
                                        should_skip_event)
    state = empty_option()
    state['deck'] = [rc.WINTER_CARD]
    assert get_event_flags(rc.CARD_O38) == frozenset({PLACES_LEADER})
    assert not should_skip_event(state, rc.CARD_O38, rc.AEDUI)
    assert should_skip_event(state, rc.CARD_O38, rc.BELGAE)
    place_diviciacus(state)
    assert should_skip_event(state, rc.CARD_O38, rc.AEDUI)


def test_optional_leader_limits_suborn_and_ambush_until_removed():
    from fs_bot.commands.sa_suborn import validate_suborn_region
    from fs_bot.commands.sa_ambush import validate_ambush_region
    state = empty_option()
    place_diviciacus(state)
    for region in (rc.CARNUTES, rc.MORINI):
        place_piece(state, region, rc.AEDUI, rc.WARBAND, 2)
        place_piece(state, region, rc.BELGAE, rc.WARBAND, 1,
                     piece_state=rc.REVEALED)
    assert validate_suborn_region(state, rc.CARNUTES)[0]
    assert not validate_suborn_region(state, rc.MORINI)[0]
    assert validate_ambush_region(state, rc.CARNUTES, rc.AEDUI, rc.BELGAE)[0]
    assert not validate_ambush_region(state, rc.MORINI, rc.AEDUI, rc.BELGAE)[0]
    remove_piece(state, rc.CARNUTES, rc.AEDUI, rc.LEADER)
    assert validate_suborn_region(state, rc.MORINI)[0]
    assert validate_ambush_region(state, rc.MORINI, rc.AEDUI, rc.BELGAE)[0]


def test_optional_leader_limits_trade_until_removed():
    from fs_bot.commands.sa_trade import trade
    state = empty_option()
    place_diviciacus(state)
    place_piece(state, rc.MORINI, rc.AEDUI, rc.ALLY)
    state['tribes'][rc.TRIBE_MORINI]['allied_faction'] = rc.AEDUI
    state['card_edition'] = 'second-edition'
    execute_event(state, 39)
    assert not any(item[:2] == ('aedui_ally', rc.MORINI)
                   for item in trade(state)['per_item'])
    remove_piece(state, rc.CARNUTES, rc.AEDUI, rc.LEADER)
    assert ('aedui_ally', rc.MORINI, 1) in trade(state)['per_item']


@pytest.mark.parametrize('margin,allowed', [(-1, False), (0, True), (1, True)])
def test_roman_bot_obeys_printed_diviciacus_battle_restriction(monkeypatch, margin, allowed):
    import fs_bot.bots.roman_bot as roman
    state = empty_option()
    place_diviciacus(state)
    monkeypatch.setattr(roman, 'calculate_victory_margin', lambda s, f: margin)
    targets = roman._rank_battle_targets(state, rc.CARNUTES, state['scenario'])
    assert (rc.AEDUI in targets) is allowed
    # The restriction protects the Leader's Region, not every Aedui force.
    place_piece(state, rc.MORINI, rc.AEDUI, rc.WARBAND)
    assert rc.AEDUI in roman._rank_battle_targets(state, rc.MORINI, state['scenario'])


@pytest.mark.parametrize('seed,survives', [(2, False), (1, True)])
def test_optional_diviciacus_uses_one_only_saving_roll_and_no_successor(seed, survives):
    from fs_bot.battle.losses import resolve_losses
    state = empty_option(seed=seed)
    place_diviciacus(state)
    resolve_losses(state, rc.CARNUTES, rc.AEDUI, 1)
    assert (find_leader(state, rc.AEDUI) is not None) is survives
    assert get_available(state, rc.AEDUI, rc.LEADER) == 0
    assert validate_state(state) == []


def test_diviciacus_is_last_casualty_in_original_scenario():
    from fs_bot.battle.losses import resolve_losses
    state = empty_option()
    place_diviciacus(state)
    place_piece(state, rc.CARNUTES, rc.AEDUI, rc.WARBAND, 2)
    resolve_losses(state, rc.CARNUTES, rc.AEDUI, 2)
    assert find_leader(state, rc.AEDUI) == rc.CARNUTES


def test_optional_state_roundtrips_and_displays_both_card_sides(tmp_path):
    from fs_bot.cli.display import format_board
    state = setup_scenario(rc.SCENARIO_PAX_GALLICA, seed=9, diviciacus_option=True)
    state['current_card'] = rc.CARD_O38
    path = tmp_path / 'option.json'
    save_game(state, path)
    restored, _, _ = load_game(path, validate=True)
    assert encode(restored) == encode(state)
    text = format_board(restored)
    assert 'Diviciacus Leader option: enabled' in text
    assert 'Place Diviciacus piece in any Region' in text
    assert 'Pro-Roman sidelined' in text


def test_cli_option_completes_and_replays_exactly(tmp_path):
    from fs_bot.cli.app import main
    save = tmp_path / 'option.json'
    replay = tmp_path / 'replay.json'
    output = io.StringIO()
    assert main(['--scenario', rc.SCENARIO_PAX_GALLICA, '--seed', '9',
                 '--diviciacus-option', '--non-interactive', '--save', str(save)],
                stdout=output) == 0
    assert main(['--replay', str(save), '--non-interactive', '--save', str(replay)],
                stdout=io.StringIO()) == 0
    original, meta, _ = load_game(save, validate=True)
    replayed, _, _ = load_game(replay, validate=True)
    assert meta['diviciacus_option'] is True
    assert encode(original) == encode(replayed)
    for mode in ('--load', '--replay'):
        assert main([mode, str(save), '--no-diviciacus-option'],
                     stdout=io.StringIO()) == 2


def test_assistant_init_saves_the_separate_option(tmp_path, capsys):
    from fs_bot.tools.llm_seat import cmd_init
    args = Namespace(dir=str(tmp_path), scenario=rc.SCENARIO_PAX_GALLICA,
                     seed=9, seat=rc.AEDUI, card_edition='original',
                     diviciacus_option=True)
    cmd_init(args)
    state, meta, _ = load_game(tmp_path / 'save.json', validate=True)
    assert state['diviciacus_option'] and meta['diviciacus_option']
    assert meta['card_edition'] == 'original'
    assert 38 not in [state['current_card'], state['next_card'], *state['deck']]
