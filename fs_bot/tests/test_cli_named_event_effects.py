"""Card 2/18/A18/23/26 owner choices use legal current-board menus."""
from io import StringIO

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces, find_leader, get_available, place_piece, remove_piece
from fs_bot.cards.card_effects import _ally_tribe, execute_event
from fs_bot.cli import named_event_effects as cli
from fs_bot.cli import voluntary_removal
from fs_bot.cli.free_actions import collect_free_action
from fs_bot.cli.human_plan import _collect_event_params
from fs_bot.cli.reactive import make_cli_reactive
from fs_bot.engine.action_windows import scope
from fs_bot.state.serialize import encode
from fs_bot.state.state_schema import build_initial_state, validate_state


SIDES = [(2, False), (18, False), ('A18', False), (23, False), (26, True)]


def state(card, executor=rc.BELGAE):
    st = build_initial_state(rc.SCENARIO_ARIOVISTUS if card == 'A18'
                             else rc.SCENARIO_GREAT_REVOLT, seed=138)
    st.update(current_card=card, next_card=3, executing_faction=executor,
              non_player_factions=set())
    st['senate'] = {'position': rc.INTRIGUE, 'firm': False}
    if card in (18, 'A18'):
        place_piece(st, rc.SEQUANI, rc.ROMANS, rc.AUXILIA, 2)
        place_piece(st, rc.UBII, rc.GERMANS, rc.WARBAND)
    if card == 23:
        place_piece(st, rc.SEQUANI, rc.ROMANS, rc.AUXILIA, 2)
    return st


def request(card):
    return {'kind': 'free_action', 'request_type': 'named_event_effect',
            'card_id': card, 'acting_faction': rc.ARVERNI if card == 26 else rc.ROMANS,
            'allow_decline': True, 'validate_default_response': True}


def run(st, card, params):
    st['event_params'] = params
    with scope(st, actor=st['executing_faction'], plan=params, force=True):
        execute_event(st, card, shaded=card == 26)
    assert validate_state(st) == []


@pytest.mark.parametrize('card,shaded', SIDES)
@pytest.mark.parametrize('own_executor', [False, True])
def test_initial_turn_does_not_choose_for_named_owner(card, shaded, own_executor):
    owner = request(card)['acting_faction']
    executor = owner if own_executor else rc.BELGAE
    st = state(card, executor)
    before, out = encode(st), StringIO()
    assert _collect_event_params(st, executor, card, shaded, StringIO(), out) == {}
    assert out.getvalue() == '' and encode(st) == before


@pytest.mark.parametrize('card,shaded', SIDES)
@pytest.mark.parametrize('selected,result', [('default', {'use_default': True}),
                                             ('decline', {'decline': True})])
def test_explicit_delegation_or_decline_and_board_are_pure(monkeypatch, card, shaded, selected, result):
    st = state(card)
    before, out = encode(st), StringIO()
    original = cli.prompt_choice

    def choose(stdin, stdout, prompt, choices):
        index = [value for _, value in choices].index(selected) + 1
        return original(StringIO(f'board\n{index}\n'), stdout, prompt, choices)

    monkeypatch.setattr(cli, 'prompt_choice', choose)
    assert collect_free_action(st, request(card)['acting_faction'], request(card), StringIO(), out) == result
    assert 'AVAILABLE PIECES' in out.getvalue() and rc.SEQUANI in out.getvalue()
    assert encode(st) == before


@pytest.mark.parametrize('card,shaded', SIDES)
def test_real_reactive_route_propagates_eof_without_mutation(card, shaded):
    st = state(card)
    before = encode(st)
    owner = request(card)['acting_faction']
    reactive = make_cli_reactive([owner], StringIO(), StringIO())
    with pytest.raises(EOFError):
        reactive(st, owner, request(card))
    assert encode(st) == before


def test_legion_source_split_is_a_roman_choice_and_preview_is_detached(monkeypatch):
    st = state(2, rc.ROMANS)
    place_piece(st, rc.PROVINCIA, rc.ROMANS, rc.LEGION, 2, from_legions_track=True)
    remove_piece(st, rc.PROVINCIA, rc.ROMANS, rc.LEGION, 2, to_fallen=True)
    before = encode(st)
    seen = []

    def choose(stdin, stdout, prompt, choices):
        options = [value for _, value in choices]
        if 'optional Event' in prompt:
            return 'choose'
        seen.append(options)
        assert options == [0, 1, 2]
        return 1

    monkeypatch.setattr(cli, 'prompt_choice', choose)
    response = collect_free_action(st, rc.ROMANS, request(2), StringIO(), StringIO())
    assert response == {'legions_from_track': 1, 'legions_from_fallen': 1}
    assert seen and encode(st) == before
    run(st, 2, response)
    assert count_pieces(st, rc.PROVINCIA, rc.ROMANS, rc.LEGION) == 2
    assert st['fallen_legions'] == 1 and st['senate']['position'] == rc.UPROAR


@pytest.mark.parametrize('senate', [{'position': None, 'firm': False},
                                   {'position': rc.UPROAR, 'firm': True}])
def test_no_senate_shift_does_not_offer_the_placement_choice(monkeypatch, senate):
    st = state(2)
    st['senate'] = senate

    def choose(stdin, stdout, prompt, choices):
        assert 'choose' not in [value for _, value in choices]
        return 'decline'

    monkeypatch.setattr(cli, 'prompt_choice', choose)
    assert collect_free_action(st, rc.ROMANS, request(2), StringIO(), StringIO()) == {'decline': True}


@pytest.mark.parametrize('card', [18, 'A18'])
def test_rhenus_menu_offers_only_current_legal_germania_targets(monkeypatch, card):
    st = state(card, rc.ROMANS)
    before = encode(st)

    def choose(stdin, stdout, prompt, choices):
        options = [value for _, value in choices]
        if 'optional Event' in prompt:
            return 'choose'
        assert rc.UBII in options and rc.SEQUANI not in options and rc.BRITANNIA not in options
        return rc.UBII

    monkeypatch.setattr(cli, 'prompt_choice', choose)
    response = collect_free_action(st, rc.ROMANS, request(card), StringIO(), StringIO())
    assert response == {'target_region': rc.UBII} and encode(st) == before
    run(st, card, response)
    assert count_pieces(st, rc.UBII, rc.GERMANS) == 0


def test_a18_does_not_offer_ariovistus_region(monkeypatch):
    st = state('A18', rc.ROMANS)
    place_piece(st, rc.SUGAMBRI, rc.GERMANS, rc.LEADER, leader_name=rc.ARIOVISTUS_LEADER)
    place_piece(st, rc.SUGAMBRI, rc.ROMANS, rc.AUXILIA, 3)

    def choose(stdin, stdout, prompt, choices):
        options = [value for _, value in choices]
        if 'optional Event' in prompt:
            return 'choose'
        assert rc.UBII in options and rc.SUGAMBRI not in options
        return rc.UBII

    monkeypatch.setattr(cli, 'prompt_choice', choose)
    assert cli.collect_response(st, rc.ROMANS, request('A18'), StringIO(), StringIO()) == {'target_region': rc.UBII}


def test_sacking_offers_city_identity_instead_of_region(monkeypatch):
    st = state(23, rc.ROMANS)
    assert _ally_tribe(st, rc.TRIBE_SEQUANI, rc.BELGAE)
    before = encode(st)

    def choose(stdin, stdout, prompt, choices):
        options = [value for _, value in choices]
        if 'optional Event' in prompt:
            return 'choose'
        assert options == [rc.CITY_VESONTIO]
        return rc.CITY_VESONTIO

    monkeypatch.setattr(cli, 'prompt_choice', choose)
    response = cli.collect_response(st, rc.ROMANS, request(23), StringIO(), StringIO())
    assert response == {'target_city': rc.CITY_VESONTIO} and encode(st) == before
    resources = st['resources'][rc.ROMANS]
    run(st, 23, response)
    assert st['resources'][rc.ROMANS] == resources + 8
    assert st['tribes'][rc.TRIBE_SEQUANI]['status'] == rc.MARKER_RAZED
    assert count_pieces(st, rc.SEQUANI, rc.BELGAE, rc.ALLY) == 0


def test_gobannitio_removals_then_placements_show_current_exact_tribes(monkeypatch):
    st = state(26, rc.ARVERNI)
    assert _ally_tribe(st, rc.TRIBE_CADURCI, rc.BELGAE)
    place_piece(st, rc.ARVERNI_REGION, rc.ARVERNI, rc.CITADEL)
    st['tribes'][rc.TRIBE_ARVERNI]['allied_faction'] = rc.ARVERNI
    st['tribes'][rc.TRIBE_VOLCAE]['status'] = rc.DISPERSED
    before, removed, placed = encode(st), False, False
    original, out = cli.prompt_choice, StringIO()

    def choose(stdin, stdout, prompt, choices):
        nonlocal removed, placed
        options = [value for _, value in choices]
        if 'optional Event' in prompt:
            return 'choose'
        assert rc.TRIBE_ARVERNI not in options and rc.TRIBE_VOLCAE not in options
        if 'remove' in prompt:
            if not removed:
                removed = True
                assert rc.TRIBE_CADURCI in options
                return rc.TRIBE_CADURCI
            assert rc.TRIBE_CADURCI not in options
            return None
        if not placed:
            placed = True
            index = options.index(rc.TRIBE_CADURCI) + 1
            choice = original(StringIO(f'b\n{index}\n'), stdout, prompt, choices)
            line = next(line for line in out.getvalue().splitlines()
                        if line.startswith(rc.ARVERNI_REGION) and rc.TRIBE_CADURCI in line)
            assert rc.BELGAE not in line
            return choice
        assert rc.TRIBE_CADURCI not in options
        return None

    monkeypatch.setattr(cli, 'prompt_choice', choose)
    response = cli.collect_response(st, rc.ARVERNI, request(26), StringIO(), out)
    assert response == {'ally_removals': [rc.TRIBE_CADURCI], 'ally_placements': [rc.TRIBE_CADURCI]}
    assert removed and placed and encode(st) == before
    run(st, 26, response)
    assert st['tribes'][rc.TRIBE_CADURCI]['allied_faction'] == rc.ARVERNI
    assert count_pieces(st, rc.ARVERNI_REGION, rc.ARVERNI, rc.CITADEL) == 1


def test_gobannitio_zero_changes_are_an_explicit_valid_selection(monkeypatch):
    st = state(26, rc.ARVERNI)
    monkeypatch.setattr(cli, 'prompt_choice', lambda i, o, prompt, choices:
                        'choose' if 'optional Event' in prompt else None)
    assert cli.collect_response(st, rc.ARVERNI, request(26), StringIO(), StringIO()) == {
        'ally_removals': [], 'ally_placements': []}


def test_gobannitio_direct_skip_leaves_the_separate_rally_choice_available():
    st = state(26, rc.ARVERNI)
    place_piece(st, rc.ARVERNI_REGION, rc.ARVERNI, rc.LEADER, leader_name=rc.VERCINGETORIX)
    response = cli.collect_response(st, rc.ARVERNI, request(26), StringIO('3\n'), StringIO())
    assert response == {'ally_removals': [], 'ally_placements': []}
    run(st, 26, response)
    assert st['event_modifiers']['card_26_arverni_rally'] is True


def test_reclamation_can_supply_a_later_gobannitio_placement(monkeypatch):
    st = state(26, rc.ARVERNI)
    st['_cli_action_windows'] = True
    occupied = []
    for tribe in st['tribes']:
        if rc.TRIBE_TO_REGION.get(tribe) != rc.ARVERNI_REGION and get_available(st, rc.ARVERNI, rc.ALLY):
            if _ally_tribe(st, tribe, rc.ARVERNI):
                occupied.append(tribe)
    assert get_available(st, rc.ARVERNI, rc.ALLY) == 0
    before, reclaimed, placed = encode(st), False, False

    def choose(stdin, stdout, prompt, choices):
        nonlocal reclaimed, placed
        options = [value for _, value in choices]
        if prompt == 'Voluntary removal?':
            if not reclaimed:
                reclaimed = True
                return next(e for e in options if isinstance(e, dict) and e.get('tribe') == occupied[0])
            return 'done'
        if 'optional Event' in prompt:
            return 'choose'
        if 'remove' in prompt:
            return None
        if not placed:
            placed = True
            assert rc.TRIBE_CADURCI in options
            return rc.TRIBE_CADURCI
        return None

    monkeypatch.setattr(cli, 'prompt_choice', choose)
    monkeypatch.setattr(voluntary_removal, 'prompt_choice', choose)
    response = cli.collect_response(st, rc.ARVERNI, request(26), StringIO(), StringIO())
    assert reclaimed and placed and encode(st) == before
    assert response['stage_timing_actions']['26.removals:0'][0]['kind'] == 'voluntary_removal'
    run(st, 26, response)
    assert st['tribes'][occupied[0]]['allied_faction'] is None
    assert st['tribes'][rc.TRIBE_CADURCI]['allied_faction'] == rc.ARVERNI


@pytest.mark.parametrize('card', [2, 26])
def test_foreign_owner_menu_does_not_offer_either_factions_voluntary_removals(monkeypatch, card):
    st = state(card, rc.BELGAE)
    st['_cli_action_windows'] = True
    owner = request(card)['acting_faction']
    kind = rc.AUXILIA if owner == rc.ROMANS else rc.WARBAND
    place_piece(st, rc.SEQUANI, owner, kind)
    place_piece(st, rc.SEQUANI, rc.BELGAE, rc.WARBAND)
    before = encode(st)

    def choose(stdin, stdout, prompt, choices):
        if 'optional Event' in prompt:
            return 'choose'
        if card == 2:
            return 2
        return None

    monkeypatch.setattr(cli, 'prompt_choice', choose)
    monkeypatch.setattr(voluntary_removal, 'collect_removals',
                        lambda *args: pytest.fail('A foreign beneficiary cannot reclaim either faction\'s pieces'))
    response = cli.collect_response(st, owner, request(card), StringIO(), StringIO())
    assert 'stage_timing_actions' not in response
    assert encode(st) == before


def test_foreign_arverni_owner_keeps_its_independent_spring_entry(monkeypatch):
    from fs_bot.cli import action_windows
    from fs_bot.engine.spring import UNLOCK_KEY
    st = build_initial_state(rc.SCENARIO_PAX_GALLICA, seed=138)
    st.update(current_card=26, next_card=3, executing_faction=rc.BELGAE,
              non_player_factions=set(), spring_box_leaders=[rc.VERCINGETORIX])
    st['available'][rc.ARVERNI][rc.LEADER] -= 1
    st[UNLOCK_KEY] = st['_cli_action_windows'] = True
    assert validate_state(st) == []
    before, entered = encode(st), []

    def choose_entry(stdin, stdout, prompt, choices):
        assert prompt == 'Vercingetorix entry before this next step?'
        assert rc.ARVERNI_REGION in [value for _, value in choices]
        entered.append(rc.ARVERNI_REGION)
        return rc.ARVERNI_REGION

    monkeypatch.setattr(cli, 'prompt_choice', lambda i, o, prompt, choices:
                        'choose' if 'optional Event' in prompt else None)
    monkeypatch.setattr(action_windows.menus, 'prompt_choice', choose_entry)
    monkeypatch.setattr(voluntary_removal, 'collect_removals',
                        lambda *args: pytest.fail('Foreign Arverni may enter their Leader, not reclaim pieces'))
    response = cli.collect_response(st, rc.ARVERNI, request(26), StringIO(), StringIO())
    assert entered == [rc.ARVERNI_REGION] and encode(st) == before
    assert response['stage_timing_actions']['26.removals:0'] == [
        {'kind': 'spring_leader', 'response': {'region': rc.ARVERNI_REGION}}]
    st['decision_agent'] = lambda *_: response
    run(st, 26, {})
    assert find_leader(st, rc.ARVERNI) == rc.ARVERNI_REGION
    assert rc.VERCINGETORIX not in st['spring_box_leaders']


def test_late_legion_reclamation_refreshes_source_counts_without_retiming(monkeypatch):
    from fs_bot.cards.named_event_effects import validate_response
    st = state(2, rc.ROMANS)
    st['_cli_action_windows'] = True
    place_piece(st, rc.PROVINCIA, rc.ROMANS, rc.LEGION, 12, from_legions_track=True)
    remove_piece(st, rc.PROVINCIA, rc.ROMANS, rc.LEGION, to_fallen=True)
    before, removal_windows = encode(st), []

    def removals(board, faction, req, stdin, stdout):
        removal_windows.append(req['window']['step'])
        if req['window']['step'] == '2.legions':
            return {'done': True}
        return {'operations': [{'action': 'remove', 'region': rc.PROVINCIA,
                                'piece_type': rc.LEGION, 'count': 1}]}

    def choose(stdin, stdout, prompt, choices):
        if 'optional Event' in prompt:
            return 'choose'
        return max(value for _, value in choices)

    monkeypatch.setattr(cli, 'prompt_choice', choose)
    monkeypatch.setattr(voluntary_removal, 'collect_removals', removals)
    response = cli.collect_response(st, rc.ROMANS, request(2), StringIO(), StringIO())
    assert removal_windows == ['2.legions', '2.fallen_legions']
    assert encode(st) == before
    assert response['legions_from_track'] == response['legions_from_fallen'] == 1
    assert response['stage_timing_actions']['2.legions'][0]['response'] == {'done': True}
    assert 'operations' in response['stage_timing_actions']['2.fallen_legions'][0]['response']
    validate_response(st, rc.ROMANS, request(2), response)
    run(st, 2, response)
    assert count_pieces(st, rc.PROVINCIA, rc.ROMANS, rc.LEGION) == 12
    assert st['fallen_legions'] == 0


@pytest.mark.parametrize('reclaim', [False, True])
def test_late_legion_pool_exposes_new_source_mix_even_when_original_mix_is_complete(monkeypatch, reclaim):
    from fs_bot.cards.named_event_effects import validate_response
    st = state(2, rc.ROMANS)
    st['_cli_action_windows'] = True
    place_piece(st, rc.PROVINCIA, rc.ROMANS, rc.LEGION, 11, from_legions_track=True)
    remove_piece(st, rc.PROVINCIA, rc.ROMANS, rc.LEGION, to_fallen=True)
    before, source_choices, removal_windows = encode(st), [], []

    def removals(board, faction, req, stdin, stdout):
        removal_windows.append(req['window']['step'])
        if not reclaim or req['window']['step'] == '2.legions':
            return {'done': True}
        return {'operations': [{'action': 'remove', 'region': rc.PROVINCIA,
                                'piece_type': rc.LEGION, 'count': 1}]}

    def choose(stdin, stdout, prompt, choices):
        if 'optional Event' in prompt:
            return 'choose'
        offered = [value for _, value in choices]
        source_choices.append(offered)
        return max(offered)

    monkeypatch.setattr(cli, 'prompt_choice', choose)
    monkeypatch.setattr(voluntary_removal, 'collect_removals', removals)
    response = cli.collect_response(st, rc.ROMANS, request(2), StringIO(), StringIO())
    assert source_choices == ([[1], [1, 2]] if reclaim else [[1]])
    assert removal_windows == ['2.legions', '2.fallen_legions']
    assert encode(st) == before
    assert response['legions_from_track'] == (2 if reclaim else 1)
    assert response['legions_from_fallen'] == (0 if reclaim else 1)
    assert response['stage_timing_actions']['2.legions'][0]['response'] == {'done': True}
    if reclaim:
        assert 'operations' in response['stage_timing_actions']['2.fallen_legions'][0]['response']
    validate_response(st, rc.ROMANS, request(2), response)
    run(st, 2, response)
    assert count_pieces(st, rc.PROVINCIA, rc.ROMANS, rc.LEGION) == (11 if reclaim else 12)
    assert st['fallen_legions'] == (1 if reclaim else 0)
