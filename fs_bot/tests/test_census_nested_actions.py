"""Execution diagnostics must include Event grants and split Commands."""
from collections import Counter

from fs_bot import rules_consts as rc
from fs_bot.tools.error_census import census_result


def _census(ex):
    result = {'card_results': [{'card': 57, 'turn_result': {'actions_taken': {
        rc.AEDUI: {'bot_action': {'command': 'Event', 'sa': 'No SA'},
                   'execution': ex}}}}]}
    counts, examples, occurrences = Counter(), {}, []
    census_result(result, counts, examples, rc.SCENARIO_PAX_GALLICA, 4, occurrences)
    return counts, occurrences


def test_event_grant_nested_command_errors_keep_beneficiary_and_raw_error():
    error = {'region': rc.NERVII, 'error': 'Not enough Resources'}
    ex = {'executed': True, 'free_actions': [
        {'free_action': 'free_command', 'faction': rc.BELGAE, 'result': {
            'executed': False, 'command': rc.CMD_MARCH, 'errors': [error]}}]}
    counts, occurrences = _census(ex)
    assert sum(counts.values()) == 1
    assert occurrences[0]['faction'] == rc.BELGAE
    assert occurrences[0]['command'] == rc.CMD_MARCH
    assert occurrences[0]['severity'] == 'illegal'
    assert occurrences[0]['raw'] == error


def test_nested_special_ability_error_is_not_hidden_by_successful_event():
    ex = {'executed': True, 'free_actions': [
        {'free_action': 'march', 'faction': rc.ROMANS, 'result': {
            'executed': True, 'command': rc.CMD_MARCH}, 'sa_execution': {
                'executed': True, 'sa': rc.SA_BUILD, 'results': [
                    {'error': 'Cannot place a second Fort'}]}}]}
    _, occurrences = _census(ex)
    assert len(occurrences) == 1
    assert occurrences[0]['faction'] == rc.ROMANS
    assert occurrences[0]['command'] == f'{rc.CMD_MARCH}+{rc.SA_BUILD}'
    assert occurrences[0]['kind'] == 'sa-error'
    assert occurrences[0]['severity'] == 'illegal'


def test_arbitrary_result_depth_and_direct_refusal_remain_visible():
    ex = {'executed': True, 'free_actions': [
        {'free_action': 'battle', 'results': [
            {'result': {'executed': False, 'reason': 'target outside granted Region'}}]}]}
    _, occurrences = _census(ex)
    assert len(occurrences) == 1
    assert occurrences[0]['command'] == rc.CMD_BATTLE
    assert occurrences[0]['severity'] == 'other-refused'


def test_explicit_optional_declines_are_legal_but_do_not_mask_errors():
    ex = {'executed': True, 'free_actions': [
        {'result': {'executed': False, 'reason': 'free Command declined'}},
        {'result': {'executed': False, 'reason': 'no March selected'}},
        {'sa_execution': {'executed': False, 'reason': 'no Special Ability selected'}},
        {'result': {'executed': False, 'declined_no_effect': True,
                    'reason': 'no legal effect', 'errors': ['invalid piece count']}}]}
    _, occurrences = _census(ex)
    assert [r['severity'] for r in occurrences].count('illegal') == 1
    assert [r['severity'] for r in occurrences].count('legal-decline') == 4
    assert not any(r['severity'] in ('other-refused', 'wasteful-sa') for r in occurrences)


def test_split_command_aggregate_does_not_count_child_errors_twice():
    first_error = {'region': rc.NERVII, 'error': 'invalid piece count'}
    second_error = {'region': rc.TREVERI, 'error': 'invalid piece count'}
    ex = {'executed': True, 'command': rc.CMD_MARCH,
          'errors': [first_error, second_error, 'additional parent failure'],
          'command_parts': [
              {'executed': True, 'errors': [dict(first_error)]},
              {'executed': False, 'errors': [dict(second_error)]}]}
    _, occurrences = _census(ex)
    assert len(occurrences) == 3
    assert all(row['severity'] == 'illegal' for row in occurrences)
    assert sum(row['message'] == 'invalid piece count' for row in occurrences) == 2


def test_alias_or_cycle_does_not_repeat_diagnostics_or_recurse_forever():
    child = {'executed': True, 'errors': ['one failure']}
    ex = {'executed': True, 'result': child, 'results': [child]}
    child['parent'] = ex
    counts, occurrences = _census(ex)
    assert sum(counts.values()) == len(occurrences) == 1


def test_non_declined_failed_sa_still_reports_wasteful_and_illegal():
    ex = {'executed': True, 'free_actions': [{'free_action': 'free_sa',
        'sa': rc.SA_BUILD, 'result': {'executed': False, 'errors': ['illegal Build']}}]}
    _, occurrences = _census(ex)
    assert sorted(r['severity'] for r in occurrences) == ['illegal', 'wasteful-sa']
    assert all(r['command'] == f'Event+{rc.SA_BUILD}' for r in occurrences)


def test_winter_campaign_and_game_run_phase_diagnostics_are_audited():
    phases = {
        'winter_campaign': {'owner': rc.BELGAE, 'actions': [{
            'result': {'executed': True, 'command': rc.CMD_MARCH,
                       'errors': ['illegal winter March']}}]},
        'germans': {'battle': {'battles': [{
            'result': {'error': 'illegal German Battle'}}]}}}
    winter = {'winter_result': {'phases': phases}}
    result = {'card_results': [{'card': 'Winter', 'winter_result': winter}]}
    counts, examples, occurrences = Counter(), {}, []
    census_result(result, counts, examples, rc.SCENARIO_PAX_GALLICA, 4, occurrences)
    assert len(occurrences) == 2
    assert {(r['faction'], r['command']) for r in occurrences} == {
        (rc.BELGAE, rc.CMD_MARCH), (rc.GERMANS, rc.CMD_BATTLE)}
    assert all(r['severity'] == 'illegal' for r in occurrences)


def test_no_target_or_skipped_winter_phases_are_not_illegal():
    phases = {
        'germans': {'skipped': 'first Winter special rule'},
        'arverni': {'battle': {'battles': [], 'regions': []}},
        'winter_campaign': {'owner': rc.BELGAE, 'actions': [],
                            'result': {'executed': False}}}
    winter = {'winter_result': {'phases': phases}}
    result = {'card_results': [{'card': 'Winter', 'winter_result': winter}]}
    counts, examples = Counter(), {}
    census_result(result, counts, examples, rc.SCENARIO_PAX_GALLICA, 4)
    assert counts == {}
