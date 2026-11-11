"""Fourth comparison audit: Event Command timing, scope and beneficiaries."""
from copy import deepcopy
from io import StringIO

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces, place_piece, remove_piece
from fs_bot.cards.card_effects import _add_region_marker, _ally_tribe
from fs_bot.cli.display import HumanTurnDisplay
from fs_bot.cli.free_actions import collect_free_action
from fs_bot.engine.execute import execute_decision
from fs_bot.engine.free_actions import command_options, validate_free_action_response
from fs_bot.engine.game_engine import ACTION_EVENT, _action_transaction
from fs_bot.state.serialize import decode, encode, load_game, save_game
from fs_bot.state.state_schema import (
    build_initial_state, check_structural_integrity, validate_state,
)
from fs_bot.tools.seat_session import DecisionPending, SeatSession, board_copy


def board(card, edition='second-edition', scenario=rc.SCENARIO_GREAT_REVOLT):
    state = build_initial_state(scenario, seed=4)
    state.update(current_card=card, current_card_id=card, next_card=49,
                 card_edition=edition, executing_faction=None, event_params=None,
                 non_player_factions=set())
    place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.FORT)
    if card == 52:
        place_piece(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA)
        place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA, 4)
        place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.LEADER, leader_name=rc.CAESAR)
    assert validate_state(state) == check_structural_integrity(state) == []
    return state


def play(state, faction=rc.ROMANS, params=None, shaded=None):
    card = state['current_card']
    shaded = card == 52 if shaded is None else shaded
    return execute_decision(state, faction, {'action': ACTION_EVENT, 'player_action': {
        'command': rc.FIRST_DID_EVENT, 'sa': 'No SA', 'details': {
            'card_id': card, 'event_params': {} if params is None else params,
            'text_preference': rc.EVENT_SHADED if shaded else rc.EVENT_UNSHADED}}})


def scout(origin=rc.PROVINCIA, destination=rc.SEQUANI, count=1, timing='after'):
    return {'sa': rc.SA_SCOUT, 'sa_timing': timing, 'sa_regions': [],
            'details': {'scout_plan': {'auxilia_moves': [{
                'from_region': origin, 'to_region': destination,
                'count': count, 'piece_state': rc.HIDDEN}], 'scout_targets': []}}}


def build(timing='after', **fields):
    return {'sa': rc.SA_BUILD, 'sa_timing': timing, 'sa_regions': [],
            'details': {'build_plan': {'allies': [
                {'region': rc.PROVINCIA, 'tribe': rc.TRIBE_HELVII}]}}, **fields}


def recruit(*regions):
    return {'command': rc.CMD_RECRUIT, 'regions': list(regions), 'sa': 'No SA',
            'details': {'recruit_plan': [{'region': region, 'action': 'place_auxilia', 'count': 1}
                                         for region in regions]}}


def add_ability(command, ability):
    return dict(command, sa=ability['sa'], sa_timing=ability['sa_timing'],
                sa_regions=ability['sa_regions'], details={**command['details'], **ability['details']})


def respond(plan):
    return lambda state, actor, request: plan if request['kind'] == 'free_action' else None


@pytest.mark.parametrize('edition', ['original', 'second-edition'])
def test_granted_scout_can_supply_the_attacker_before_battle(edition):
    state = board(52, edition)
    place_piece(state, rc.SEQUANI, rc.BELGAE, rc.WARBAND, 2)
    resources = deepcopy(state['resources'])
    plan = add_ability(
        {'command': rc.CMD_BATTLE, 'regions': [rc.SEQUANI], 'details': {
            'battle_plan': [{'region': rc.SEQUANI, 'target': rc.BELGAE}]}},
        scout(count=2, timing='before'))
    state['decision_agent'] = respond(plan)
    result = play(state)
    assert result['executed'], result
    grant = result['free_actions'][0]['result']
    assert grant['battles_resolved'] == [(rc.SEQUANI, rc.BELGAE)]
    assert grant['sa_execution']['executed']
    assert count_pieces(state, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA) == 2
    assert state['resources'] == resources
    assert validate_state(state) == check_structural_integrity(state) == []


@pytest.mark.parametrize('bad', ['late-scout', 'no-defender'])
def test_granted_battle_with_missing_forces_rejects_without_scout_movement(bad):
    state = board(52)
    if bad == 'late-scout':
        place_piece(state, rc.SEQUANI, rc.BELGAE, rc.WARBAND, 2)
    before = encode(state)
    plan = add_ability(
        {'command': rc.CMD_BATTLE, 'regions': [rc.SEQUANI], 'details': {
            'battle_plan': [{'region': rc.SEQUANI, 'target': rc.BELGAE}]}},
        scout(count=2, timing='after' if bad == 'late-scout' else 'before'))
    state['decision_agent'] = respond(plan)
    result = play(state)
    assert result['rejected'], result
    assert 'not present' in result['reason']
    assert encode(board_copy(state)) == before


@pytest.mark.parametrize('form', ['top-level', 'nested', 'null-shadow'])
@pytest.mark.parametrize('outside', [False, True])
def test_mons_cevenna_scopes_the_scout_origins_the_executor_reads(form, outside):
    state = board(9)
    place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA, 3)
    place_piece(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA, 3)
    before = encode(state)
    origin, destination = ((rc.CARNUTES, rc.VENETI) if outside
                           else (rc.SEQUANI, rc.MANDUBII))
    plan = add_ability({'command': rc.CMD_SEIZE, 'regions': [rc.SEQUANI],
                        'details': {'disperse_tribes': {rc.SEQUANI: []}}},
                       scout(origin, destination))
    if form != 'top-level':
        details = plan['details']
        details['sa_details'] = {'scout_plan': details.pop('scout_plan')}
        if form == 'null-shadow':
            details['scout_plan'] = None

    def agent(live, actor, request):
        if request['kind'] == 'free_action':
            if request['request_type'] == 'mons_cevenna_march':
                return {'origin': rc.PROVINCIA, 'destination': rc.SEQUANI, 'group': {rc.AUXILIA: 2}}
            return plan

    state['decision_agent'] = agent
    result = play(state)
    if outside:
        assert result['rejected'] and 'leaves the Regions' in result['reason']
        assert encode(board_copy(state)) == before
    else:
        assert result['executed'], result
        assert count_pieces(state, destination, rc.ROMANS, rc.AUXILIA) == 1
    assert validate_state(state) == check_structural_integrity(state) == []


@pytest.mark.parametrize('timings', [('after', 'after'), ('before', 'before'), ('after', 'before')])
@pytest.mark.parametrize('edition', ['original', 'second-edition'])
def test_assembly_executes_two_free_abilities_and_only_one_recruit(timings, edition):
    state = board(52, edition)
    state['resources'][rc.ROMANS] = 0
    plan = dict(recruit(rc.PROVINCIA), special_abilities=[scout(timing=timings[0]), build(timings[1])])
    requests = []

    def agent(live, actor, request):
        if request['kind'] == 'free_action':
            requests.append((actor, request.get('max_special_abilities')))
            return plan

    state['decision_agent'] = agent
    result = play(state, rc.BELGAE)
    assert result['executed'], result
    grant = result['free_actions'][0]
    assert requests == [(rc.ROMANS, 2)] and grant['sa_count'] == 2
    assert len(grant['result']['placements']) == 1
    assert state['tribes'][rc.TRIBE_HELVII]['allied_faction'] == rc.ROMANS
    assert count_pieces(state, rc.SEQUANI, rc.ROMANS, rc.AUXILIA) == 1
    assert count_pieces(state, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA) == 4
    assert state['resources'][rc.ROMANS] == 0
    assert validate_state(state) == check_structural_integrity(state) == []


@pytest.mark.parametrize('second_step', [1, 2])
def test_assembly_resolves_two_independent_interruptions_within_one_march(second_step):
    state = board(52)
    # Caesar's group completes each hop before the corresponding ability.
    # Scout places an Auxilia in Sequani for the later Build.
    first = scout(rc.PROVINCIA, rc.SEQUANI, timing='during')
    first['after_step'] = {'group': 1, 'hop': 0}
    second = {'sa': rc.SA_BUILD, 'sa_timing': 'during', 'sa_regions': [],
              'after_step': {'group': 1, 'hop': second_step - 1},
              'details': {'build_plan': {'forts': [rc.SEQUANI]}}}
    plan = {'command': rc.CMD_MARCH, 'sa': 'No SA', 'regions': [rc.PROVINCIA],
            'details': {'march_plan': {'origins': [rc.PROVINCIA],
                'routes': {rc.PROVINCIA: [rc.SEQUANI, rc.MANDUBII]},
                'groups': {rc.PROVINCIA: {rc.LEADER: True, rc.AUXILIA: 2}}}},
            'special_abilities': [first, second]}
    state['decision_agent'] = respond(plan)
    result = play(state)
    assert result['executed'], result
    assert result['free_actions'][0]['sa_count'] == 2
    assert count_pieces(state, rc.SEQUANI, rc.ROMANS, rc.FORT) == 1
    assert count_pieces(state, rc.SEQUANI, rc.ROMANS, rc.AUXILIA) == 1
    assert count_pieces(state, rc.MANDUBII, rc.ROMANS, rc.AUXILIA) == 2
    assert validate_state(state) == check_structural_integrity(state) == []


def test_assembly_combines_besiege_in_battle_with_a_standalone_scout():
    state = board(52)
    assert _ally_tribe(state, rc.TRIBE_SEQUANI, rc.BELGAE)
    place_piece(state, rc.SEQUANI, rc.ROMANS, rc.LEGION, from_legions_track=True)
    plan = {'command': rc.CMD_BATTLE, 'sa': 'No SA', 'regions': [rc.SEQUANI],
            'details': {'battle_plan': [{'region': rc.SEQUANI, 'target': rc.BELGAE}]},
            'special_abilities': [scout(timing='before'), {
                'sa': rc.SA_BESIEGE, 'sa_timing': 'during', 'sa_regions': [rc.SEQUANI]}]}
    state['decision_agent'] = respond(plan)
    result = play(state)
    assert result['executed'], result
    assert result['free_actions'][0]['sa_count'] == 2
    assert state['tribes'][rc.TRIBE_SEQUANI]['allied_faction'] is None
    assert validate_state(state) == check_structural_integrity(state) == []


def test_assembly_can_interrupt_a_raid_between_flips_and_between_regions():
    state = board(52)
    place_piece(state, rc.CARNUTES, rc.ARVERNI, rc.LEADER, leader_name=rc.VERCINGETORIX)
    place_piece(state, rc.CARNUTES, rc.ARVERNI, rc.WARBAND, 5)
    place_piece(state, rc.ARVERNI_REGION, rc.ARVERNI, rc.WARBAND, 2)
    plan = {'command': rc.CMD_RAID, 'sa': 'No SA', 'details': {
        'raid_plan': [{'region': region} for region in (rc.CARNUTES, rc.CARNUTES, rc.ARVERNI_REGION)]},
        'special_abilities': [
            {'sa': rc.SA_ENTREAT, 'sa_timing': 'during', 'after_step': 1, 'sa_regions': [
                {'region': rc.CARNUTES, 'action': 'replace_piece', 'target_faction': rc.ROMANS,
                 'target_type': rc.AUXILIA, 'target_state': rc.HIDDEN}]},
            {'sa': rc.SA_DEVASTATE, 'sa_timing': 'during', 'after_step': 2,
             'sa_regions': [rc.CARNUTES]}]}
    state['decision_agent'] = respond(plan)
    result = play(state)
    assert result['executed'], result
    assert result['free_actions'][0]['sa_count'] == 2
    assert result['free_actions'][0]['result']['regions_resolved'] == [rc.CARNUTES, rc.ARVERNI_REGION]
    assert count_pieces(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA) == 0
    assert rc.MARKER_DEVASTATED in state['markers'][rc.CARNUTES]
    assert state['resources'][rc.ARVERNI] == 3
    assert validate_state(state) == check_structural_integrity(state) == []


@pytest.mark.parametrize('bad', ['same-ability', 'incompatible', 'outside-step', 'bad-build'])
def test_assembly_rejects_invalid_second_ability_without_executing_any_part(bad):
    state = board(52)
    before = encode(state)
    second = {'same-ability': scout(), 'incompatible': {'sa': rc.SA_BESIEGE, 'sa_timing': 'during'},
              'outside-step': build('during', after_step=2),
              'bad-build': {'sa': rc.SA_BUILD, 'sa_timing': 'after',
                            'details': {'build_plan': {'forts': [rc.PROVINCIA]}}}}[bad]
    state['decision_agent'] = respond(dict(recruit(rc.PROVINCIA), special_abilities=[scout(), second]))
    result = play(state)
    assert result['rejected'], result
    assert encode(board_copy(state)) == before


def test_a_different_event_cannot_authorize_two_abilities():
    state = board(52)
    request = {'kind': 'free_action', 'request_type': 'event_command',
               'allowed_commands': command_options(rc.ROMANS), 'with_sa': True, 'free': True}
    plan = dict(recruit(rc.PROVINCIA), special_abilities=[scout(), build()], max_special_abilities=2)
    assert 'Only the Assembly' in validate_free_action_response(state, rc.ROMANS, request, plan)


@pytest.mark.parametrize('ability', [None, 'Scout', 'Build'])
def test_assembly_keeps_ordinary_zero_and_one_ability_plans(ability):
    state = board(52)
    plan = recruit(rc.PROVINCIA)
    if ability:
        plan = add_ability(plan, scout() if ability == 'Scout' else build())
    state['decision_agent'] = respond(plan)
    result = play(state)
    assert result['executed'], result
    assert result['free_actions'][0]['sa_count'] == int(bool(ability))


HOME = {rc.AEDUI: rc.AEDUI_REGION, rc.ARVERNI: rc.ARVERNI_REGION, rc.BELGAE: rc.MORINI}


def rally(*regions):
    return {'command': rc.CMD_RALLY, 'sa': 'No SA', 'regions': list(regions),
            'details': {'rally_plan': {'steps': [
                {'region': region, 'action': 'place_warbands', 'count': 1} for region in regions]}}}


@pytest.mark.parametrize('edition', ['original', 'second-edition'])
@pytest.mark.parametrize('shaded', [False, True])
def test_druids_uses_printed_order_and_only_executor_stays_eligible(edition, shaded):
    state = board(48, edition)
    state['resources'] = dict.fromkeys(state['resources'], 0)
    state['eligibility'][rc.ARVERNI] = rc.INELIGIBLE
    order = []

    def agent(live, actor, request):
        if request['kind'] == 'free_action':
            order.append(actor)
            assert request['max_regions'] == 1 and request['with_sa'] and not request['allow_decline']
            return rally(HOME[actor])

    state['decision_agent'] = agent
    result = play(state, params={'target_factions': [rc.BELGAE, rc.ARVERNI, rc.AEDUI]}, shaded=shaded)
    assert result['executed'], result
    assert order == [rc.AEDUI, rc.ARVERNI, rc.BELGAE]
    assert [row['faction'] for row in result['free_actions']] == order
    assert state['eligibility'][rc.ARVERNI] == rc.INELIGIBLE
    assert state['stay_eligible'] == [rc.ROMANS]
    for actor, region in HOME.items():
        assert count_pieces(state, region, actor, rc.WARBAND) == 1
        assert state['resources'][actor] == 0
    assert validate_state(state) == check_structural_integrity(state) == []


@pytest.mark.parametrize('targets', [
    [], [rc.ROMANS], [rc.GERMANS], [rc.AEDUI, rc.AEDUI], [rc.AEDUI, []], rc.AEDUI, None,
])
def test_druids_rejects_invalid_beneficiaries_before_making_choices(targets):
    state = board(48)
    before = encode(state)
    result = play(state, params={'target_factions': targets})
    assert result['rejected'] and 'distinct Gallic Factions' in result['reason']
    assert encode(state) == before


@pytest.mark.parametrize('plan', [{'decline': True}, rally(rc.MORINI, rc.ATREBATES)])
def test_druids_recipient_cannot_waive_a_possible_command_or_select_two_regions(plan):
    state = board(48)
    before = encode(state)
    state['decision_agent'] = respond(plan)
    result = play(state, params={'target_factions': [rc.BELGAE]})
    assert result['rejected'], result
    assert encode(board_copy(state)) == before


def test_druids_default_without_a_legal_command_is_rejected_for_human_beneficiary(monkeypatch):
    from fs_bot.cards import gallic_event_grants
    state = board(48)
    before = encode(state)
    monkeypatch.setattr(gallic_event_grants, '_default_command',
                        lambda *args: {'executed': False})
    state['decision_agent'] = respond({'use_default': True})
    result = play(state, params={'target_factions': [rc.AEDUI]})
    assert result['rejected'] and 'No non-player default is available' in result['reason']
    assert encode(board_copy(state)) == before


def test_druids_non_player_selects_its_own_faction_even_when_others_are_non_player():
    state = board(48)
    state['non_player_factions'] = set(rc.FACTIONS)
    result = play(state, rc.BELGAE)
    assert result['executed'], result
    assert [row['faction'] for row in result['free_actions']] == [rc.BELGAE]


def test_druids_allows_an_optional_free_special_ability_in_a_different_region():
    state = board(48)
    place_piece(state, rc.PICTONES, rc.AEDUI, rc.WARBAND)
    plan = add_ability(rally(rc.AEDUI_REGION), {
        'sa': rc.SA_SUBORN, 'sa_timing': 'after', 'sa_regions': [rc.PICTONES],
        'details': {'suborn_plan': [{'region': rc.PICTONES,
                                    'actions': [{'action': 'place_warband'}]}]}})
    state['decision_agent'] = respond(plan)
    result = play(state, params={'target_factions': [rc.AEDUI]})
    assert result['executed'], result
    assert count_pieces(state, rc.PICTONES, rc.AEDUI, rc.WARBAND) == 2
    assert count_pieces(state, rc.AEDUI_REGION, rc.AEDUI, rc.WARBAND) == 1
    assert state['resources'][rc.AEDUI] == 0


def test_druids_skips_an_impossible_command_and_continues_to_next_beneficiary():
    state = board(48)
    _add_region_marker(state, rc.AEDUI_REGION, rc.MARKER_DEVASTATED)
    consulted = []

    def agent(live, actor, request):
        if request['kind'] == 'free_action':
            consulted.append(actor)
            return rally(HOME[actor])

    state['decision_agent'] = agent
    result = play(state, params={'target_factions': [rc.BELGAE, rc.AEDUI]})
    assert result['executed'], result
    aedui, belgae = result['free_actions']
    assert aedui['result']['declined_no_effect'] and belgae['result']['executed']
    assert consulted == [rc.BELGAE]
    assert state['stay_eligible'] == [rc.ROMANS]


@pytest.mark.parametrize('card', [48, 52])
@pytest.mark.parametrize('at_war', [False, True])
def test_automatic_arverni_receive_one_command_under_pr10(card, at_war):
    state = board(card, 'legacy', rc.SCENARIO_ARIOVISTUS)
    if card == 52:
        remove_piece(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA, piece_state=rc.HIDDEN)
        place_piece(state, rc.CARNUTES, rc.ARVERNI, rc.WARBAND, 3)
    if at_war:
        place_piece(state, rc.ARVERNI_REGION, rc.ROMANS, rc.AUXILIA)
    choices = []
    state['decision_agent'] = lambda live, actor, request: choices.append((actor, request['kind']))
    result = play(state, params={'target_factions': [rc.ARVERNI]} if card == 48 else None)
    assert result['executed'], result
    grant = result['free_actions'][0]['result']
    assert grant['provisional_ruling'] == 'PR-10' and grant['at_war'] == at_war
    assert grant['executed'] == at_war
    if at_war:
        assert grant['command'] == rc.CMD_RALLY
        assert len(grant['placements']) == 1
    assert (rc.ARVERNI, 'free_action') not in choices
    assert validate_state(state) == check_structural_integrity(state) == []


@pytest.mark.parametrize('actor,scenario', [(rc.ROMANS, rc.SCENARIO_GREAT_REVOLT),
                                            (rc.GERMANS, rc.SCENARIO_ARIOVISTUS)])
def test_druids_non_gallic_non_player_declines_event(actor, scenario):
    from fs_bot.cards.event_conditions import np_event_available
    state = board(48, 'legacy' if actor == rc.GERMANS else 'second-edition', scenario)
    state['non_player_factions'] = {actor}
    assert np_event_available(state, 48, actor, False) is False
    assert play(state, actor)['rejected']


def session(state, meta=None, log=None):
    seat = SeatSession(state, {'seat': rc.ROMANS, 'player_id': 'Player 1'} if meta is None else meta,
                       [] if log is None else log, HumanTurnDisplay(StringIO()))
    def agent(live, faction, request):
        if request['kind'] == 'free_action':
            return seat.reactive(live, faction, request)
    state['decision_agent'] = agent
    return seat


def step(seat):
    def driver(*args):
        pass
    driver.transaction_checkpoint = seat.checkpoint
    driver.transaction_restore = seat.restore
    with _action_transaction(seat.state, driver):
        return play(seat.state)


def submit(seat, response):
    seat.import_inbox({'decision_id': seat.data['pending']['id'], 'response': response})


@pytest.mark.parametrize('card', [48, 52])
def test_event_grant_save_resume_and_replay(tmp_path, card):
    from fs_bot.state import player_ownership
    state = board(card)
    player_ownership.install(state, {rc.ROMANS: 'Player 1', rc.AEDUI: 'Player 1'})
    initial = deepcopy(state)
    seat = session(state)
    with pytest.raises(DecisionPending):
        step(seat)
    if card == 48:
        request = decode(seat.data['pending']['request'])
        assert request['request_type'] == 'druids_beneficiaries' and request['faction'] == rc.ROMANS
        submit(seat, {'target_factions': [rc.AEDUI]})
        with pytest.raises(DecisionPending):
            step(seat)
        response = rally(rc.AEDUI_REGION)
    else:
        response = dict(recruit(rc.PROVINCIA), special_abilities=[scout(), build()])
    request = decode(seat.data['pending']['request'])
    assert request['request_type'] == 'event_command'
    assert request['faction'] == (rc.AEDUI if card == 48 else rc.ROMANS)
    assert encode(board_copy(state)) == encode(initial)
    pending = deepcopy(seat.data['pending'])
    submit(seat, {'decline': True} if card == 48 else dict(response, special_abilities=[scout(), scout()]))
    with pytest.raises(DecisionPending):
        step(seat)
    assert seat.error and seat.data['pending'] == pending
    assert encode(board_copy(state)) == encode(initial)
    save_game(state, tmp_path / 'save.json', meta=seat.meta, log=seat.log)
    restored, meta, log = load_game(tmp_path / 'save.json', validate=True)
    resumed = session(restored, meta, log)
    assert resumed.data['pending'] == seat.data['pending']
    submit(resumed, response)
    result = step(resumed)
    resumed.finish()
    assert result['executed'], result
    assert decode(log[-1]['assistant_response']) == response

    history = iter(log)

    def replay(live, actor, request):
        if request['kind'] == 'free_action':
            row = next(history)
            assert decode(row['assistant_request']) == dict(request, faction=actor)
            return decode(row['assistant_response'])

    initial['decision_agent'] = replay
    assert play(initial) == result
    assert next(history, None) is None
    assert encode(board_copy(initial)) == encode(board_copy(restored))


def test_druids_terminal_collects_distinct_beneficiaries():
    from fs_bot.cards.gallic_event_grants import druids_request
    state = board(48)
    choice = collect_free_action(state, rc.ROMANS, druids_request(), StringIO('3\n1\n2\n'), StringIO())
    assert choice == {'target_factions': [rc.BELGAE, rc.AEDUI]}


def test_assembly_terminal_collects_and_executes_scout_then_build():
    state = board(52)
    before = encode(state)
    request = {'kind': 'free_action', 'request_type': 'event_command',
               'allowed_commands': command_options(rc.ROMANS), 'with_sa': True,
               'free': True, 'max_special_abilities': 2}
    replies = [
        4, 1, 2, 3, 1, 3,  # Recruit with Scout and Build after it.
        2, 2, 1, 1,  # Recruit Auxilia in Provincia.
        3, 3, 1, 1, 1,  # Scout one from Provincia to Sequani.
        2, 2, 1, 1,  # Build an Ally at Helvii.
    ]
    output = StringIO()
    plan = collect_free_action(state, rc.ROMANS, request,
                               StringIO(''.join(f'{choice}\n' for choice in replies)), output)
    assert [ability['sa'] for ability in plan['special_abilities']] == [rc.SA_SCOUT, rc.SA_BUILD]
    assert encode(state) == before
    state['decision_agent'] = respond(plan)
    result = play(state)
    assert result['executed'], result
    assert result['free_actions'][0]['sa_count'] == 2
    assert state['tribes'][rc.TRIBE_HELVII]['allied_faction'] == rc.ROMANS
    assert count_pieces(state, rc.SEQUANI, rc.ROMANS, rc.AUXILIA) == 1
