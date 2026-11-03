"""The mixed-seat harness must exercise restored Event Battle choices."""
import random

from fs_bot import rules_consts as rc
from fs_bot.tools.player_fuzz import make_random_reactive


def _request():
    return {
        'kind': 'free_action', 'request_type': 'fixed_event_battle',
        'card_id': 25, 'allow_decline': False,
        'defenders_by_region': {
            rc.PICTONES: [rc.AEDUI, rc.BELGAE],
            rc.ARVERNI_REGION: [rc.GERMANS],
        },
    }


def test_fuzzer_selects_all_offered_event_battles_instead_of_defaulting():
    rng = random.Random('fixed-event-battle-choices')
    reactive = make_random_reactive({rc.ROMANS}, rng)
    expected = {(rc.PICTONES, rc.AEDUI), (rc.PICTONES, rc.BELGAE),
                (rc.ARVERNI_REGION, rc.GERMANS)}
    observed = set()
    for _ in range(100):
        response = reactive({}, rc.ROMANS, _request())
        assert set(response) == {'region', 'defender'}
        pair = (response['region'], response['defender'])
        assert pair in expected
        observed.add(pair)
    assert observed == expected


def test_fuzzer_event_battle_choices_replay_and_ignore_mapping_order():
    first = make_random_reactive({rc.ROMANS}, random.Random('same'))
    second = make_random_reactive({rc.ROMANS}, random.Random('same'))
    request = _request()
    reordered = dict(request, defenders_by_region={
        region: list(reversed(defenders))
        for region, defenders in reversed(list(request['defenders_by_region'].items()))
    })
    assert [first({}, rc.ROMANS, request) for _ in range(30)] == [
        second({}, rc.ROMANS, reordered) for _ in range(30)]


def test_fuzzer_does_not_answer_for_a_nonhuman_seat_or_consume_rng():
    rng = random.Random('other-seat')
    reactive = make_random_reactive({rc.ROMANS}, rng)
    before = rng.getstate()
    assert reactive({}, rc.AEDUI, _request()) is None
    assert rng.getstate() == before
