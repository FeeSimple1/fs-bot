"""Optional setup rules from §2.3.8, A Setup and Great Revolt Deck."""
import io
from collections import Counter
from itertools import product

import pytest

from fs_bot import rules_consts as rc
from fs_bot.cards.card_data import get_faction_order
from fs_bot.engine import game_engine as engine
from fs_bot.state.setup import setup_scenario, _select_events
from fs_bot.state.setup_options import setup_option_values
from fs_bot.state.serialize import encode, save_game, load_game
from fs_bot.state.state_schema import validate_state


def _combinations():
    for scenario in rc.ALL_SCENARIOS:
        for sudden, even, short in product((False, True), repeat=3):
            if even and scenario == rc.SCENARIO_PAX_GALLICA:
                continue
            if short and scenario != rc.SCENARIO_GREAT_REVOLT:
                continue
            yield scenario, sudden, even, short


@pytest.mark.parametrize('scenario,sudden,even,short', list(_combinations()))
def test_optional_decks_roundtrip_and_repeat(scenario, sudden, even, short, tmp_path):
    options = dict(sudden_frost=sudden, even_initiative=even,
                   short_great_revolt=short)
    state = setup_scenario(scenario, seed=9, **options)
    assert encode(state) == encode(setup_scenario(scenario, seed=9, **options))
    assert validate_state(state) == []
    assert setup_option_values(state) == options
    expected = {
        rc.SCENARIO_PAX_GALLICA: (70, {2, 5, 8, 11, 14}),
        rc.SCENARIO_RECONQUEST: (60, {3, 6, 9, 12}),
        rc.SCENARIO_GREAT_REVOLT: (30, {3, 6}) if short else (45, {3, 6, 9}),
        rc.SCENARIO_ARIOVISTUS: (45, {3, 6, 9}),
        rc.SCENARIO_GALLIC_WAR: (45, {3, 6, 9}),
    }
    count, winter_piles = expected[scenario]
    deck = list(state['deck'])
    events = [c for c in deck if c != rc.WINTER_CARD]
    assert len(events) == len(set(events)) == count
    assert deck.count(rc.WINTER_CARD) == len(winter_piles)
    for pile in range(1, count // 5 + 1):
        size = 6 if pile in winter_piles else 5
        chunk, deck = deck[:size], deck[size:]
        assert chunk.count(rc.WINTER_CARD) == (pile in winter_piles)
    assert deck == []
    if scenario in rc.BASE_SCENARIOS:
        assert all(isinstance(c, int) for c in events)
    else:
        assert 38 not in events and not any(c in range(19, 37) for c in events
                                               if isinstance(c, int))
    path = tmp_path / 'save.json'
    save_game(state, path)
    restored, _, _ = load_game(path, validate=True)
    assert encode(restored) == encode(state)


@pytest.mark.parametrize('scenario,count', [(rc.SCENARIO_RECONQUEST, 60),
    (rc.SCENARIO_GREAT_REVOLT, 30), (rc.SCENARIO_GREAT_REVOLT, 45),
    (rc.SCENARIO_ARIOVISTUS, 45), (rc.SCENARIO_GALLIC_WAR, 45)])
def test_even_initiative_balances_pool_before_trimming(scenario, count):
    """Inspect the actual pool handed to the final shuffle, before truncation."""
    state = setup_scenario(scenario, seed=4)
    if scenario in rc.BASE_SCENARIOS:
        cards = list(rc.CARD_NAMES_BASE)
    else:
        # The printed A replacements have the original card's numeric id.
        replacements = [c for c in rc.CARD_NAMES_ARIOVISTUS if isinstance(c, str)]
        removed = {int(c[1:].rstrip('C')) for c in replacements}
        cards = [c for c in rc.CARD_NAMES_BASE if c not in removed]
        cards += replacements
    class ObservedRng:
        def __init__(self, rng):
            self.rng = rng
            self.inputs = []
        def shuffle(self, sequence):
            self.inputs.append(list(sequence))
            self.rng.shuffle(sequence)
    observer = ObservedRng(state['rng'])
    state.update(rng=observer, even_initiative=True)
    chosen = _select_events(state, cards, count)
    assert len(observer.inputs) == 5
    pool = observer.inputs[-1]
    needed_per_symbol = (count + 3) // 4
    assert len(pool) == needed_per_symbol * 4
    counts = Counter(get_faction_order(c, scenario)[0] for c in pool)
    assert len(counts) == 4 and set(counts.values()) == {needed_per_symbol}
    assert len(chosen) == len(set(chosen)) == count
    assert set(chosen) <= set(pool)
    for pile in observer.inputs[:4]:
        assert len(pile) == 18
        assert len({get_faction_order(c, scenario)[0] for c in pile}) == 1


@pytest.mark.parametrize('edition', ['legacy', 'original', 'second-edition'])
def test_even_initiative_uses_optional_diviciacus_card(edition):
    state = setup_scenario(rc.SCENARIO_RECONQUEST, seed=9,
                          even_initiative=True, diviciacus_option=True,
                          card_edition=edition)
    assert rc.CARD_O38 in state['deck'] and 38 not in state['deck']
    assert state['card_edition'] == edition


@pytest.mark.parametrize('option', list(setup_option_values({})))
@pytest.mark.parametrize('bad', [1, 0, None, 'true', []])
def test_new_setup_rejects_non_boolean_options(option, bad):
    with pytest.raises(ValueError, match='must be true or false'):
        setup_scenario(rc.SCENARIO_GREAT_REVOLT, **{option: bad})


@pytest.mark.parametrize('scenario', [s for s in rc.ALL_SCENARIOS
                                     if s != rc.SCENARIO_GREAT_REVOLT])
def test_short_deck_rejects_other_scenarios(scenario):
    with pytest.raises(ValueError, match='requires The Great Revolt'):
        setup_scenario(scenario, short_great_revolt=True)


def test_even_initiative_rejects_pax():
    with pytest.raises(ValueError, match='not available'):
        setup_scenario(rc.SCENARIO_PAX_GALLICA, even_initiative=True)


@pytest.mark.parametrize('option', list(setup_option_values({})))
def test_saved_option_domain_checked(option):
    state = setup_scenario(rc.SCENARIO_GREAT_REVOLT)
    state[option] = 1
    assert f'{option} must be true or false' in validate_state(state)


@pytest.mark.parametrize('scenario', rc.ALL_SCENARIOS)
def test_sudden_frost_swaps_before_first_event_actions(scenario):
    state = setup_scenario(scenario, seed=1, sudden_frost=True)
    state['deck'] = [1, rc.WINTER_CARD, 2]
    assert engine.start_game(state) == rc.WINTER_CARD
    assert state['current_card_id'] == rc.WINTER_CARD
    assert state['played_cards'] == [rc.WINTER_CARD]
    assert state['deck'] == [1, 2] and state['next_card'] == 1
    assert not engine.is_frost(state)
    assert engine.advance_to_next_card(state) == 1
    assert state['played_cards'] == [rc.WINTER_CARD, 1]
    assert state['next_card'] == 2


def test_sudden_frost_defers_each_event_and_final_winter_ends_before_it(monkeypatch):
    state = setup_scenario(rc.SCENARIO_GREAT_REVOLT, seed=1, sudden_frost=True,
                          short_great_revolt=True)
    state['deck'] = [1, 2, rc.WINTER_CARD, 3, 4, rc.WINTER_CARD, 5]
    turns, winters = [], []
    def decision(st, faction, options, position):
        turns.append(st['current_card'])
        return {'action': engine.ACTION_PASS}
    def winter(st, is_final=False, **kwargs):
        winters.append((is_final, st['next_card']))
        st['winter_count'] += 1
        return {'phases': {'victory': {'game_over': is_final}}}
    monkeypatch.setattr(engine, 'run_winter_round', winter)
    result = engine.run_game(state, decision)
    assert result['game_over']
    assert state['played_cards'] == [1, rc.WINTER_CARD, 2, 3, rc.WINTER_CARD]
    assert set(turns) == {1, 2, 3}
    assert winters == [(False, 2), (True, 4)]
    assert state['deck'] == [4, 5] and state['next_card'] == 4


def test_standard_frost_still_plays_the_event_before_winter():
    state = setup_scenario(rc.SCENARIO_GREAT_REVOLT, seed=1)
    state['deck'] = [1, rc.WINTER_CARD, 2]
    assert engine.start_game(state) == 1
    assert engine.is_frost(state)
    assert engine.advance_to_next_card(state) == rc.WINTER_CARD
    assert state['next_card'] == 2
    assert not engine.is_frost(state)


def test_sudden_frost_has_no_swap_without_an_upcoming_winter():
    state = setup_scenario(rc.SCENARIO_GREAT_REVOLT, seed=1, sudden_frost=True)
    state['deck'] = [rc.WINTER_CARD, 1, 2]
    assert engine.start_game(state) == rc.WINTER_CARD
    assert engine.advance_to_next_card(state) == 1
    assert not engine.is_frost(state)
    assert engine.advance_to_next_card(state) == 2
    assert engine.advance_to_next_card(state) is None


def test_interlude_uses_printed_replacement_deck_and_retains_options():
    from fs_bot.engine.interlude import _build_pax_gallica_deck_for_interlude
    state = setup_scenario(rc.SCENARIO_GALLIC_WAR, seed=1,
                          sudden_frost=True, even_initiative=True)
    state['deck'] = [1, rc.WINTER_CARD]
    engine.start_game(state)
    assert state['deck'] == [1]
    result = _build_pax_gallica_deck_for_interlude(state)
    assert result['winters_in_piles'] == 5
    assert state['played_cards'] == [] and state['current_card'] is None
    assert state['sudden_frost'] and state['even_initiative']
    assert state['deck'].count(rc.WINTER_CARD) == 5
    # Even Initiative affects initial selection. The Interlude explicitly
    # rebuilds per Pax Gallica? and does not re-sort its replacement deck.
    state['deck'] = [2, rc.WINTER_CARD, 3]
    assert engine.advance_to_next_card(state) == rc.WINTER_CARD
    assert state['next_card'] == 2


def test_cli_options_complete_save_load_and_replay(tmp_path):
    from fs_bot.cli.app import main
    path, replay = tmp_path / 'save.json', tmp_path / 'replay.json'
    assert main(['--scenario', rc.SCENARIO_GREAT_REVOLT, '--seed', '9',
                 '--sudden-frost', '--even-initiative', '--short-great-revolt',
                 '--non-interactive', '--save', str(path)], stdout=io.StringIO()) == 0
    state, meta, _ = load_game(path, validate=True)
    assert all(setup_option_values(state).values())
    assert all(meta[k] for k in setup_option_values(state))
    assert state['winter_count'] <= 2
    assert main(['--replay', str(path), '--non-interactive', '--save', str(replay)],
                stdout=io.StringIO()) == 0
    replayed, _, _ = load_game(replay, validate=True)
    assert encode(replayed) == encode(state)
    assert main(['--load', str(path), '--non-interactive'], stdout=io.StringIO()) == 0
    for option in setup_option_values(state):
        for mode in ('--load', '--replay'):
            assert main([mode, str(path), '--no-' + option.replace('_', '-')],
                        stdout=io.StringIO()) == 2


@pytest.mark.parametrize('scenario,flag', [
    (rc.SCENARIO_PAX_GALLICA, '--even-initiative'),
    (rc.SCENARIO_ARIOVISTUS, '--short-great-revolt')])
def test_frontends_reject_scenario_invalid_options(scenario, flag, tmp_path, capsys):
    from fs_bot.cli.app import main
    from fs_bot.tools.llm_seat import main as assistant
    assert main(['--scenario', scenario, '--non-interactive', flag],
                stdout=io.StringIO()) == 2
    assert assistant(['init', '--scenario', scenario, '--seat', rc.ROMANS,
                      '--dir', str(tmp_path), flag]) == 2
    assert not (tmp_path / 'save.json').exists()


def test_assistant_options_pending_save_and_replay(tmp_path, capsys):
    from fs_bot.tools.llm_seat import main
    from fs_bot.cli.display import format_board
    folder, replay = tmp_path / 'game', tmp_path / 'replay'
    assert main(['init', '--scenario', rc.SCENARIO_GREAT_REVOLT, '--seed', '9',
                 '--seat', rc.ROMANS, '--dir', str(folder), '--sudden-frost',
                 '--even-initiative', '--short-great-revolt']) is None
    assert main(['play', '--dir', str(folder)]) == 0
    state, meta, _ = load_game(folder / 'save.json', validate=True)
    pending = meta['assistant_session']['pending']
    assert pending and all(setup_option_values(state).values())
    assert main(['submit', '--dir', str(folder), '--response',
                 '{"action":"pass"}' if pending['request']['kind'] == 'turn'
                 else '{"use_default":true}']) == 0
    assert main(['replay', '--dir', str(folder), '--output-dir', str(replay)]) == 0
    current, _, _ = load_game(folder / 'save.json', validate=True)
    replayed, replay_meta, _ = load_game(replay / 'save.json', validate=True)
    assert encode(current) == encode(replayed)
    assert all(replay_meta[k] for k in setup_option_values(current))
    board = format_board(current)
    assert 'Sudden Frost: enabled' in board
    assert 'Even Initiative (initial deck): enabled' in board
    assert 'Short Great Revolt: enabled' in board


def test_legacy_saves_default_to_standard_setup():
    state = setup_scenario(rc.SCENARIO_GREAT_REVOLT, seed=9)
    assert not any(k in state for k in setup_option_values(state))
    assert not any(setup_option_values(state).values())


def test_switched_winter_pending_resume_and_replay_preserve_deferred_event(tmp_path):
    from copy import deepcopy
    from fs_bot.cli.display import HumanTurnDisplay
    from fs_bot.tools.seat_session import SeatSession, DecisionPending, board_copy
    state = setup_scenario(rc.SCENARIO_GREAT_REVOLT, seed=9, sudden_frost=True,
                          even_initiative=True, short_great_revolt=True)
    state['non_player_factions'] = {rc.ARVERNI, rc.AEDUI, rc.BELGAE}
    state['deck'] = [1, rc.WINTER_CARD, 2, rc.WINTER_CARD]
    engine.start_game(state)
    before = encode(board_copy(state))
    session = SeatSession(state, {'seat': rc.ROMANS}, [], HumanTurnDisplay(io.StringIO()))
    def attach(current):
        def driver(st, faction, options, position):
            raise AssertionError('No Event action may precede the switched Winter')
        driver.transaction_checkpoint = current.checkpoint
        driver.transaction_restore = current.restore
        driver.transaction_complete = current.transaction_complete
        current.state['decision_agent'] = lambda board, faction, request: (
            current.reactive(board, faction, request) if faction == rc.ROMANS else None)
        return driver
    driver = attach(session)
    with pytest.raises(DecisionPending):
        engine.play_card(state, driver, execute=True)
    pending = deepcopy(session.data['pending'])
    assert encode(board_copy(state)) == before
    path = tmp_path / 'winter.json'
    save_game(state, path, meta=session.meta, log=session.log)
    restored, meta, log = load_game(path, validate=True)
    resumed = SeatSession(restored, meta, log, HumanTurnDisplay(io.StringIO()))
    driver = attach(resumed)
    with pytest.raises(DecisionPending):
        engine.play_card(restored, driver, execute=True)
    assert resumed.data['pending'] == pending
    for _ in range(30):
        resumed.import_inbox({'decision_id': resumed.data['pending']['id'],
                             'response': {'use_default': True}})
        try:
            result = engine.play_card(restored, driver, execute=True)
            resumed.finish()
            break
        except DecisionPending:
            continue
    else:
        pytest.fail('Winter never completed')
    assert result['type'] == 'winter' and not result['game_over']
    assert restored['current_card'] == 1 and restored['next_card'] == 2
    assert restored['played_cards'] == [rc.WINTER_CARD, 1]
    assert restored['winter_count'] == 1
    assert all(setup_option_values(restored).values())
    replay = setup_scenario(rc.SCENARIO_GREAT_REVOLT, seed=9, sudden_frost=True,
                           even_initiative=True, short_great_revolt=True)
    replay['non_player_factions'] = {rc.ARVERNI, rc.AEDUI, rc.BELGAE}
    replay['deck'] = [1, rc.WINTER_CARD, 2, rc.WINTER_CARD]
    engine.start_game(replay)
    assert engine.play_card(replay, lambda *args: None, execute=True) == result
    assert encode(board_copy(replay)) == encode(board_copy(restored))
