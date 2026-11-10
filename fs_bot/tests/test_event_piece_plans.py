"""Physical Event targets, required quantities, and transactional retry."""

from io import StringIO

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.control import is_controlled_by
from fs_bot.board.pieces import count_pieces, count_pieces_by_state, get_available, place_piece
from fs_bot.cards.card_effects import _ally_tribe, _tribe_region
from fs_bot.cards.event_piece_plans import derive_params, np_available
from fs_bot.map.map_data import get_playable_regions_for_state
from fs_bot.state.serialize import encode
from fs_bot.tests.test_event_targets import board, citadel, play


def expansion():
    return board(rc.SCENARIO_ARIOVISTUS)


def spend_allies(state, faction, remaining, exclude=()):
    playable = set(get_playable_regions_for_state(state, faction))
    for tribe in state['tribes']:
        if get_available(state, faction, rc.ALLY) == remaining:
            break
        region = _tribe_region(state, tribe)
        if (region in playable and region not in exclude
                and rc.TRIBE_FACTION_RESTRICTION.get(tribe, faction) == faction):
            _ally_tribe(state, tribe, faction)
    assert get_available(state, faction, rc.ALLY) == remaining


@pytest.mark.parametrize('visibility', [rc.HIDDEN, rc.REVEALED, rc.SCOUTED])
def test_abatis_uses_warbands_in_every_visibility(visibility):
    state = expansion()
    place_piece(state, rc.ATREBATES, rc.BELGAE, rc.WARBAND, piece_state=visibility)

    play(state, 'A64', {'region': rc.ATREBATES})

    assert state['markers'][rc.ATREBATES][rc.MARKER_ABATIS] == rc.BELGAE
    assert count_pieces_by_state(state, rc.ATREBATES, rc.BELGAE, rc.WARBAND, visibility) == 1


@pytest.mark.parametrize('edition', ['original', 'second-edition'])
@pytest.mark.parametrize('tribes', [[], [rc.TRIBE_BELLOVACI] * 2])
def test_remi_cannot_skip_or_duplicate_an_eligible_ally(edition, tribes):
    state = board(edition=edition)
    assert _ally_tribe(state, rc.TRIBE_REMI, rc.ROMANS)
    assert _ally_tribe(state, rc.TRIBE_BELLOVACI, rc.BELGAE)
    play(state, 68, {'replacements': [{'tribe': tribe} for tribe in tribes]}, rejected=True)

    play(state, 68, {'replacements': [{'tribe': rc.TRIBE_BELLOVACI}]})

    assert state['tribes'][rc.TRIBE_BELLOVACI]['allied_faction'] == rc.ROMANS
    assert count_pieces(state, rc.ATREBATES, rc.ROMANS, rc.ALLY) == 2


def test_remi_removes_the_source_when_replacement_is_unavailable():
    state = board()
    assert _ally_tribe(state, rc.TRIBE_BELLOVACI, rc.BELGAE)
    spend_allies(state, rc.ROMANS, 0, exclude=(rc.ATREBATES,))

    play(state, 68, {'replacements': [{'tribe': rc.TRIBE_BELLOVACI}]})

    assert state['tribes'][rc.TRIBE_BELLOVACI]['allied_faction'] is None
    assert count_pieces(state, rc.ATREBATES, rc.ROMANS, rc.ALLY) == 0


def test_remi_accepts_no_replacements_if_only_a_citadel_qualifies_by_distance():
    state = board()
    citadel(state, rc.CARNUTES, rc.TRIBE_CARNUTES, rc.BELGAE)

    play(state, 68, {'replacements': []})

    assert count_pieces(state, rc.CARNUTES, rc.BELGAE, rc.CITADEL) == 1
    assert state['tribes'][rc.TRIBE_CARNUTES]['allied_faction'] == rc.BELGAE


def bibrax(tribe=None):
    return {'faction': rc.ROMANS, 'piece_type': rc.ALLY,
            **({'tribe': tribe} if tribe is not None else {})}


@pytest.mark.parametrize('tribe', [rc.TRIBE_REMI, rc.TRIBE_ATREBATES])
def test_bibrax_removes_only_the_selected_ally(tribe):
    state = expansion()
    tribes = (rc.TRIBE_ATREBATES, rc.TRIBE_REMI)
    for name in tribes:
        assert _ally_tribe(state, name, rc.ROMANS)
    play(state, 'A51', {'removals': [bibrax()]}, shaded=True, rejected=True)
    play(state, 'A51', {'removals': [bibrax(tribe), bibrax(tribe)]}, shaded=True, rejected=True)

    play(state, 'A51', {'removals': [bibrax(tribe)]}, shaded=True)

    other = next(name for name in tribes if name != tribe)
    assert state['tribes'][tribe]['allied_faction'] is None
    assert state['tribes'][other]['allied_faction'] == rc.ROMANS
    assert count_pieces(state, rc.ATREBATES, rc.ROMANS, rc.ALLY) == 1


def test_bibrax_allows_zero_and_keeps_unambiguous_legacy_ally_selection():
    state = expansion()
    assert _ally_tribe(state, rc.TRIBE_REMI, rc.ROMANS)
    play(state, 'A51', {'removals': []}, shaded=True)
    assert state['tribes'][rc.TRIBE_REMI]['allied_faction'] == rc.ROMANS

    play(state, 'A51', {'removals': [bibrax()]}, shaded=True)

    assert state['tribes'][rc.TRIBE_REMI]['allied_faction'] is None


@pytest.mark.parametrize('count', [0, 8])
def test_orgetorix_rejects_a_short_plan_and_preserves_the_pre_event_board(count):
    state = expansion()
    assert _ally_tribe(state, rc.TRIBE_SEQUANI, rc.AEDUI)
    troops = {'region': rc.SEQUANI, 'piece_type': rc.WARBAND, 'count': count}
    play(state, 'A30', {'placements': [troops] if count else []}, shaded=True, rejected=True)

    play(state, 'A30', {'placements': [
        {'region': rc.SEQUANI, 'piece_type': rc.CITADEL},
        dict(troops, count=8),
    ]}, shaded=True)

    assert count_pieces(state, rc.SEQUANI, rc.ARVERNI) == 9
    assert state['tribes'][rc.TRIBE_SEQUANI]['allied_faction'] == rc.ARVERNI


def test_orgetorix_completes_all_possible_placements_with_scarce_supply():
    state = expansion()
    place_piece(state, rc.ARVERNI_REGION, rc.ARVERNI, rc.WARBAND,
                get_available(state, rc.ARVERNI, rc.WARBAND) - 1)
    spend_allies(state, rc.ARVERNI, 1, exclude=(rc.AEDUI_REGION, rc.SEQUANI))
    state['tribes'][rc.TRIBE_AEDUI]['status'] = rc.DISPERSED
    state['markers'][rc.TRIBE_AEDUI] = {rc.MARKER_DISPERSED: True}
    troops = {'region': rc.SEQUANI, 'piece_type': rc.WARBAND, 'count': 6}
    city_ally = {'region': rc.SEQUANI, 'piece_type': rc.ALLY, 'tribe': rc.TRIBE_SEQUANI}
    play(state, 'A30', {'placements': [troops, city_ally]}, shaded=True, rejected=True)

    play(state, 'A30', {'placements': [
        troops, {'region': rc.SEQUANI, 'piece_type': rc.CITADEL},
        dict(city_ally, tribe=rc.TRIBE_HELVETII),
    ]}, shaded=True)

    assert count_pieces(state, rc.SEQUANI, rc.ARVERNI) == 3
    assert state['tribes'][rc.TRIBE_HELVETII]['allied_faction'] == rc.ARVERNI


def test_orgetorix_german_default_preserves_control():
    state = expansion()
    place_piece(state, rc.SEQUANI, rc.GERMANS, rc.WARBAND, 1)
    assert is_controlled_by(state, rc.SEQUANI, rc.GERMANS)
    before = encode(state)
    assert np_available(state, rc.GERMANS, 'A30')
    assert encode(state) == before

    params = derive_params(state, rc.GERMANS, 'A30', npc=True)
    play(state, 'A30', params, shaded=True, actor=rc.GERMANS)

    assert count_pieces(state, rc.AEDUI_REGION, rc.ARVERNI) == 9
    assert is_controlled_by(state, rc.SEQUANI, rc.GERMANS)


def test_galba_requires_both_quotas_before_granting_resources():
    state = expansion()
    state['resources'][rc.BELGAE] = 0
    assert _ally_tribe(state, rc.TRIBE_REMI, rc.ROMANS)
    allies = [{'tribe': rc.TRIBE_REMI}, {'tribe': rc.TRIBE_MENAPII}]
    troops = [{'region': rc.MORINI, 'count': 3}, {'region': rc.NERVII}]
    play(state, 'A56', {'warband_placements': [], 'ally_placements': allies},
         shaded=True, rejected=True)
    play(state, 'A56', {'warband_placements': troops, 'ally_placements': allies[:1]},
         shaded=True, rejected=True)

    play(state, 'A56', {'warband_placements': troops, 'ally_placements': allies}, shaded=True)

    assert state['resources'][rc.BELGAE] == 4
    assert count_pieces(state, rc.MORINI, rc.BELGAE, rc.WARBAND) == 3
    assert count_pieces(state, rc.NERVII, rc.BELGAE, rc.WARBAND) == 1
    assert all(state['tribes'][e['tribe']]['allied_faction'] == rc.BELGAE for e in allies)


def test_galba_accepts_genuine_shortfalls_and_keeps_the_resource_grant():
    state = expansion()
    state['resources'][rc.BELGAE] = 0
    spend_allies(state, rc.BELGAE, 0, exclude=rc.BELGICA_REGIONS)
    place_piece(state, rc.TREVERI, rc.BELGAE, rc.WARBAND,
                get_available(state, rc.BELGAE, rc.WARBAND) - 2)
    assert _ally_tribe(state, rc.TRIBE_REMI, rc.ROMANS)

    play(state, 'A56', {'warband_placements': [{'region': rc.MORINI, 'count': 4}],
                       'ally_placements': []}, shaded=True)

    assert count_pieces(state, rc.MORINI, rc.BELGAE, rc.WARBAND) == 2
    assert state['resources'][rc.BELGAE] == 4
    assert state['tribes'][rc.TRIBE_REMI]['allied_faction'] == rc.ROMANS


def test_kinship_requires_each_source_quota_even_without_replacement_supply():
    state = expansion()
    place_piece(state, rc.ATREBATES, rc.BELGAE, rc.WARBAND,
                get_available(state, rc.BELGAE, rc.WARBAND))
    place_piece(state, rc.MORINI, rc.GERMANS, rc.WARBAND, piece_state=rc.SCOUTED)
    place_piece(state, rc.MORINI, rc.GERMANS, rc.WARBAND, piece_state=rc.REVEALED)
    assert _ally_tribe(state, rc.TRIBE_SUEBI_NORTH, rc.GERMANS)
    troops = [{'region': rc.MORINI, 'piece_state': ps} for ps in (rc.SCOUTED, rc.REVEALED)]
    allies = [{'tribe': rc.TRIBE_SUEBI_NORTH}]
    plan = {'from_faction': rc.GERMANS, 'warband_replacements': troops,
            'ally_replacements': allies}
    play(state, 'A65', dict(plan, warband_replacements=[]), shaded=True, rejected=True)
    play(state, 'A65', dict(plan, ally_replacements=[]), shaded=True, rejected=True)

    play(state, 'A65', plan, shaded=True)

    assert count_pieces(state, rc.MORINI, rc.GERMANS, rc.WARBAND) == 0
    assert count_pieces(state, rc.MORINI, rc.BELGAE, rc.WARBAND) == 0
    assert state['tribes'][rc.TRIBE_SUEBI_NORTH]['allied_faction'] is None


def test_terminal_galba_offers_concrete_mandatory_choices_without_mutating_board(monkeypatch):
    from fs_bot.cli import event_piece_plans, human_plan

    state = expansion()
    state['current_card'] = 'A56'
    before = encode(state)
    selected_tribes = iter((rc.TRIBE_MORINI, rc.TRIBE_REMI))

    def choose(stdin, stdout, prompt, choices):
        entries = [entry for _, entry in choices]
        assert None not in entries
        if 'warband' in prompt:
            return {'region': rc.MORINI, 'count': 4}
        tribe = next(selected_tribes)
        assert {'tribe': tribe} in entries
        return {'tribe': tribe}

    monkeypatch.setattr(event_piece_plans, 'prompt_choice', choose)
    plan = human_plan._collect_event_params(state, rc.BELGAE, 'A56', True,
                                            StringIO(), StringIO())
    assert encode(state) == before

    play(state, 'A56', plan, shaded=True)

    assert count_pieces(state, rc.MORINI, rc.BELGAE, rc.WARBAND) == 4
    assert state['tribes'][rc.TRIBE_MORINI]['allied_faction'] == rc.BELGAE
    assert state['tribes'][rc.TRIBE_REMI]['allied_faction'] == rc.BELGAE
