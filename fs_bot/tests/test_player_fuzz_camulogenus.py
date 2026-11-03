"""Mixed-seat fuzzing must exercise the new choices without borrowing live RNG."""
import random

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import place_piece
from fs_bot.cards.camulogenus import make_request, validate_response
from fs_bot.cards.roman_event_grants import accept_request
from fs_bot.state.serialize import encode
from fs_bot.state.state_schema import build_initial_state
from fs_bot.tools.player_fuzz import make_random_reactive


def test_fuzzed_camulogenus_plans_are_legal_deterministic_and_leave_board_unchanged():
    state = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=70)
    for region in (rc.MORINI, rc.CARNUTES, rc.MANDUBII):
        place_piece(state, region, rc.ROMANS, rc.LEGION, 3, from_legions_track=True)
        place_piece(state, region, rc.ROMANS, rc.AUXILIA, 3)
    place_piece(state, rc.MORINI, rc.ROMANS, rc.LEADER, leader_name=rc.CAESAR)
    request = make_request(state)
    before = encode(state)
    multiple_origins = False
    destinations = set()
    decisions = set()
    for seed in range(20):
        first = make_random_reactive([rc.ROMANS], random.Random(seed))
        second = make_random_reactive([rc.ROMANS], random.Random(seed))
        accept = first(state, rc.ROMANS, accept_request(70))
        assert accept == second(state, rc.ROMANS, accept_request(70))
        decisions.add(tuple(accept))
        response = first(state, rc.ROMANS, request)
        assert response == second(state, rc.ROMANS, request)
        assert validate_response(state, request, response) is None
        assert sum(entry['legions'] for entry in response['marches']) <= 4
        destinations.add(response['destination'])
        multiple_origins |= len({entry['origin'] for entry in response['marches']}) > 1
    assert multiple_origins
    assert len(destinations) == 3 and decisions == {('accept',), ('decline',)}
    assert encode(state) == before


def test_fuzzer_does_not_answer_for_another_players_roman_benefit():
    reactive = make_random_reactive([rc.BELGAE], random.Random(70))
    assert reactive({}, rc.ROMANS, accept_request(70)) is None
