"""PR-10, provisionally adopted: one automatic Command using A6.2 priorities."""
from copy import deepcopy

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import place_piece, count_pieces, count_pieces_by_state, get_available
from fs_bot.cards.card_effects import _ally_tribe
from fs_bot.cards.gallic_arverni_np import resolve_command
from fs_bot.cards.gallic_event_grants import command_request
from fs_bot.engine.free_actions import validate_free_action_response
from fs_bot.state.state_schema import build_initial_state, validate_state
from fs_bot.state.serialize import encode


def board(seed=10):
    state = build_initial_state(rc.SCENARIO_ARIOVISTUS, seed=seed)
    state['at_war'] = False
    state['non_player_factions'] = {rc.AEDUI, rc.ROMANS, rc.BELGAE, rc.GERMANS}
    state['resources'].update({rc.ROMANS: 10, rc.AEDUI: 10, rc.BELGAE: 10, rc.GERMANS: 10})
    return state


def request(*commands, limited=False):
    grant = command_request(rc.ARVERNI, 46, limited=limited)
    if commands:
        grant['allowed_commands'] = list(commands)
    return grant


def war(state, region=rc.ARVERNI_REGION, faction=rc.ROMANS):
    place_piece(state, region, faction, rc.AUXILIA if faction == rc.ROMANS else rc.WARBAND)


def devastated(state, region):
    state.setdefault('markers', {}).setdefault(region, {})[rc.MARKER_DEVASTATED] = True


def test_at_peace_consumes_no_target_rng_and_has_no_effect():
    state = board(); before = encode(state)
    result = resolve_command(state, request())
    assert not result['executed'] and result['at_war'] is False
    assert result['provisional_ruling'] == 'PR-10'
    assert encode(state) == before


@pytest.mark.parametrize('limited', [False, True])
def test_rally_first_citadel_before_ally_before_warbands_one_option_per_region(limited):
    state = board()
    for region in (rc.ARVERNI_REGION, rc.PICTONES, rc.CARNUTES):
        war(state, region)
    _ally_tribe(state, rc.TRIBE_ARVERNI, rc.ARVERNI)
    place_piece(state, rc.ARVERNI_REGION, rc.ARVERNI, rc.WARBAND, 3)
    place_piece(state, rc.PICTONES, rc.ARVERNI, rc.WARBAND, 3)
    result = resolve_command(state, request(limited=limited))
    assert result['executed'] and result['command'] == rc.CMD_RALLY
    entries = result['placements']
    assert entries[0]['region'] == rc.ARVERNI_REGION and entries[0]['action'] == 'place_citadel'
    assert len({e['region'] for e in entries}) == len(entries)
    assert count_pieces(state, rc.ARVERNI_REGION, rc.ARVERNI, rc.CITADEL) == 1
    if limited:
        assert len(entries) == 1
        assert count_pieces(state, rc.PICTONES, rc.ARVERNI, rc.ALLY) == 0
    else:
        assert any(e['action'] == 'place_ally' and e['region'] == rc.PICTONES for e in entries)
        assert count_pieces(state, rc.PICTONES, rc.ARVERNI, rc.WARBAND) == 3
        assert count_pieces(state, rc.CARNUTES, rc.ARVERNI, rc.WARBAND) == 1
    assert validate_state(state) == []


def test_rally_cannot_place_ally_without_control_or_in_untriggered_home():
    state = board(); war(state)
    result = resolve_command(state, request(rc.CMD_RALLY))
    assert result['executed']
    assert result['placements'] == [{'region': rc.ARVERNI_REGION, 'action': 'place_warbands',
                                     'tribe': None, 'count': 1}]
    assert count_pieces(state, rc.PICTONES, rc.ARVERNI) == 0
    assert count_pieces(state, rc.ARVERNI_REGION, rc.ARVERNI, rc.ALLY) == 0
    assert validate_state(state) == []


def test_first_possible_skips_blocked_rally_and_hides_in_place_before_raiding():
    state = board(); war(state); devastated(state, rc.ARVERNI_REGION)
    place_piece(state, rc.PICTONES, rc.ARVERNI, rc.WARBAND, piece_state=rc.SCOUTED)
    result = resolve_command(state, request())
    assert result['command'] == rc.CMD_MARCH and result['executed']
    assert count_pieces_by_state(state, rc.PICTONES, rc.ARVERNI, rc.WARBAND, rc.REVEALED) == 1
    assert count_pieces_by_state(state, rc.PICTONES, rc.ARVERNI, rc.WARBAND, rc.HIDDEN) == 0
    assert state['resources'][rc.ROMANS] == 10


def test_march_uses_largest_surplus_limited_origin_ignores_event_frost():
    state = board(); war(state, rc.ARVERNI_REGION)
    place_piece(state, rc.PICTONES, rc.ARVERNI, rc.WARBAND, 6)
    place_piece(state, rc.BITURIGES, rc.ARVERNI, rc.WARBAND, 3)
    state['next_card'] = rc.WINTER_CARD
    result = resolve_command(state, request(rc.CMD_MARCH, limited=True))
    assert result['command'] == rc.CMD_MARCH and result['executed']
    assert count_pieces(state, rc.PICTONES, rc.ARVERNI, rc.WARBAND) == 1
    assert count_pieces(state, rc.BITURIGES, rc.ARVERNI, rc.WARBAND) == 3
    assert count_pieces(state, rc.ARVERNI_REGION, rc.ARVERNI, rc.WARBAND) == 5
    assert validate_state(state) == []


def test_march_hides_original_target_residents_before_arrivals_only_once():
    state = board(); war(state)
    place_piece(state, rc.ARVERNI_REGION, rc.ARVERNI, rc.WARBAND, piece_state=rc.SCOUTED)
    place_piece(state, rc.ARVERNI_REGION, rc.ARVERNI, rc.WARBAND, piece_state=rc.REVEALED)
    place_piece(state, rc.PICTONES, rc.ARVERNI, rc.WARBAND, 3)
    result = resolve_command(state, request(rc.CMD_MARCH))
    assert result['executed']
    assert count_pieces_by_state(state, rc.ARVERNI_REGION, rc.ARVERNI, rc.WARBAND, rc.SCOUTED) == 0
    assert count_pieces_by_state(state, rc.ARVERNI_REGION, rc.ARVERNI, rc.WARBAND, rc.REVEALED) == 1
    assert count_pieces_by_state(state, rc.ARVERNI_REGION, rc.ARVERNI, rc.WARBAND, rc.HIDDEN) == 3
    assert validate_state(state) == []


def test_limited_in_place_hiding_selects_one_region_only():
    state = board(); war(state)
    for region in (rc.PICTONES, rc.VENETI):
        place_piece(state, region, rc.ARVERNI, rc.WARBAND, piece_state=rc.REVEALED)
    result = resolve_command(state, request(rc.CMD_MARCH, limited=True))
    assert result['executed'] and len(result['in_place']) == 1
    assert sum(count_pieces_by_state(state, r, rc.ARVERNI, rc.WARBAND, rc.HIDDEN)
               for r in (rc.PICTONES, rc.VENETI)) == 1


def test_secondary_march_must_actually_remove_aedui_control():
    state = board(); war(state, rc.VENETI)
    place_piece(state, rc.UBII, rc.ARVERNI, rc.WARBAND, 3)
    place_piece(state, rc.TREVERI, rc.AEDUI, rc.WARBAND, 5)
    before = deepcopy(state['spaces'])
    result = resolve_command(state, request(rc.CMD_MARCH))
    assert not result['executed']
    assert state['spaces'] == before


def test_secondary_march_can_remove_control_with_combined_adjacent_groups():
    state = board(); war(state, rc.VENETI)
    place_piece(state, rc.UBII, rc.ARVERNI, rc.WARBAND, 3)
    place_piece(state, rc.SEQUANI, rc.ARVERNI, rc.WARBAND, 3)
    place_piece(state, rc.TREVERI, rc.AEDUI, rc.WARBAND, 4)
    result = resolve_command(state, request(rc.CMD_MARCH))
    assert result['executed']
    assert count_pieces(state, rc.TREVERI, rc.ARVERNI, rc.WARBAND) == 4
    assert validate_state(state) == []


def test_raid_caps_two_reserves_ambush_and_does_not_track_arverni_resources():
    state = board(); war(state)
    place_piece(state, rc.ARVERNI_REGION, rc.ARVERNI, rc.WARBAND, 6)
    resources = state['resources'].get(rc.ARVERNI)
    result = resolve_command(state, request(rc.CMD_RAID))
    assert result['executed'] and result['command'] == rc.CMD_RAID
    assert result['raids'][0]['warbands_flipped'] == 2
    assert state['resources'][rc.ROMANS] == 8
    assert state['resources'].get(rc.ARVERNI) == resources
    assert count_pieces_by_state(state, rc.ARVERNI_REGION, rc.ARVERNI, rc.WARBAND, rc.HIDDEN) == 4
    assert validate_state(state) == []


def test_raid_uses_only_hidden_surplus_above_ambush_requirement():
    state = board(); war(state)
    place_piece(state, rc.ARVERNI_REGION, rc.ARVERNI, rc.WARBAND, 3)
    # Roman Hidden Auxilia require two Hidden Arverni for Ambush.
    result = resolve_command(state, request(rc.CMD_RAID))
    assert result['executed'] and result['raids'][0]['warbands_flipped'] == 1
    assert count_pieces_by_state(state, rc.ARVERNI_REGION, rc.ARVERNI, rc.WARBAND, rc.HIDDEN) == 2


def test_raid_cannot_gain_resources_without_an_unfortified_resource_target():
    state = board(); war(state)
    place_piece(state, rc.ARVERNI_REGION, rc.ARVERNI, rc.WARBAND, 3)
    place_piece(state, rc.ARVERNI_REGION, rc.ROMANS, rc.FORT)
    result = resolve_command(state, request(rc.CMD_RAID))
    assert not result['executed'] and state['resources'][rc.ROMANS] == 10


def test_battle_has_inherent_ambush_without_optional_special_activity_or_owner_prompt():
    state = board(); war(state)
    place_piece(state, rc.ARVERNI_REGION, rc.ARVERNI, rc.WARBAND, 4)
    seen = []
    state['decision_agent'] = lambda s, f, q: seen.append((f, q.get('request_type'))) or None
    result = resolve_command(state, request(rc.CMD_BATTLE))
    assert result['executed'] and result['intrinsic_special_activity'] == rc.SA_AMBUSH
    assert result['count'] == 1
    assert not any(f == rc.ARVERNI for f, _ in seen)
    assert validate_state(state) == []


def test_battle_needs_hidden_superiority_and_card35_exclusion_wins():
    state = board(); war(state)
    place_piece(state, rc.ARVERNI_REGION, rc.ARVERNI, rc.WARBAND)
    assert not resolve_command(state, request(rc.CMD_BATTLE))['executed']
    grant = command_request(rc.ARVERNI, 35)
    assert rc.CMD_BATTLE not in grant['allowed_commands']
    # Direct planner selection must respect its exclusions even if Battle
    # becomes possible; with no permitted Commands it carries out none.
    grant['allowed_commands'] = []
    place_piece(state, rc.ARVERNI_REGION, rc.ARVERNI, rc.WARBAND, 3)
    assert not resolve_command(state, grant)['executed']


def test_explicit_default_validation_is_detached_and_seeded():
    state = board(); war(state); twin = deepcopy(state); before = encode(state)
    grant = command_request(rc.ARVERNI, 46)
    assert validate_free_action_response(state, rc.ARVERNI, grant, {'use_default': True}) is None
    assert encode(state) == before
    assert resolve_command(state, grant) == resolve_command(twin, grant)
    assert encode(state) == encode(twin)


def test_raid_reserves_nothing_when_hidden_superiority_makes_every_ambush_impossible():
    state = board(); war(state)
    place_piece(state, rc.ARVERNI_REGION, rc.ROMANS, rc.AUXILIA, 2)
    place_piece(state, rc.ARVERNI_REGION, rc.ARVERNI, rc.WARBAND)
    place_piece(state, rc.ARVERNI_REGION, rc.ARVERNI, rc.WARBAND, 3, piece_state=rc.REVEALED)
    result = resolve_command(state, request(rc.CMD_RAID))
    assert result['executed'] and result['raids'][0]['warbands_flipped'] == 1


def test_raid_reserves_minimum_for_one_possible_enemy_not_an_impossible_enemy():
    state = board(); war(state)
    place_piece(state, rc.ARVERNI_REGION, rc.ROMANS, rc.AUXILIA, 4)
    place_piece(state, rc.ARVERNI_REGION, rc.AEDUI, rc.WARBAND, piece_state=rc.REVEALED)
    place_piece(state, rc.ARVERNI_REGION, rc.ARVERNI, rc.WARBAND, 3)
    result = resolve_command(state, request(rc.CMD_RAID))
    assert result['executed'] and result['raids'][0]['warbands_flipped'] == 2
    assert count_pieces_by_state(state, rc.ARVERNI_REGION, rc.ARVERNI, rc.WARBAND, rc.HIDDEN) == 1


@pytest.mark.parametrize('cooperation', [False, True])
def test_raid_reservation_accounts_for_eligible_combined_diviciacus_defense_without_prompt(cooperation):
    from fs_bot.cards.capabilities import activate_capability
    state = board(); war(state)
    place_piece(state, rc.ARVERNI_REGION, rc.AEDUI, rc.WARBAND)
    place_piece(state, rc.ARVERNI_REGION, rc.ARVERNI, rc.WARBAND, 4)
    if cooperation:
        activate_capability(state, 38, rc.EVENT_UNSHADED)
    consulted = []
    state['decision_agent'] = lambda *args: consulted.append(args) or None
    result = resolve_command(state, request(rc.CMD_RAID))
    assert result['executed']
    assert result['raids'][0]['warbands_flipped'] == (1 if cooperation else 2)
    assert not consulted
    assert '_diviciacus_force' not in state and validate_state(state) == []


def test_automatic_actor_forwards_defender_choices_and_restores_original_objects():
    from fs_bot.engine.action_windows import scope
    state = board(); war(state)
    place_piece(state, rc.ARVERNI_REGION, rc.ARVERNI, rc.WARBAND, 4)
    original_nps = state['non_player_factions']
    seen = []

    class Agent:
        supports_action_windows = True

        def __call__(self, position, faction, question):
            seen.append((faction, question.get('kind')))
            assert faction != rc.ARVERNI
            assert rc.ARVERNI in position['non_player_factions']
            return None

    agent = state['decision_agent'] = Agent()
    with scope(state, actor=rc.ROMANS, force=True):
        result = resolve_command(state, request(rc.CMD_BATTLE))
    assert result['executed']
    assert (rc.ROMANS, 'loss_order') in seen
    assert not any(f == rc.ARVERNI for f, _ in seen)
    assert state['decision_agent'] is agent
    assert state['non_player_factions'] is original_nps
    assert rc.ARVERNI not in original_nps


@pytest.mark.parametrize('agent_present', [False, True])
def test_automatic_actor_restores_agent_and_np_set_when_human_input_pauses(monkeypatch, agent_present):
    from fs_bot.cards import gallic_arverni_np as adapter
    from fs_bot.engine.agent import consult_agent
    state = board(); war(state)
    original_nps = state['non_player_factions']

    def pause(board, faction, question):
        raise EOFError('human defender paused')

    if agent_present:
        state['decision_agent'] = pause

    def interrupt(position, *args):
        assert rc.ARVERNI in position['non_player_factions']
        assert consult_agent(position, rc.ARVERNI, {}) is None
        if agent_present:
            consult_agent(position, rc.ROMANS, {})
        raise EOFError('pause')

    monkeypatch.setattr(adapter, '_execute', interrupt)
    with pytest.raises(EOFError):
        resolve_command(state, request(rc.CMD_RALLY))
    assert state['non_player_factions'] is original_nps
    assert rc.ARVERNI not in original_nps
    assert ('decision_agent' in state) is agent_present
    if agent_present:
        assert state['decision_agent'] is pause
