"""Confirm Supply Lines before committing an NP Recruit and its preceding SA.

Pure forecasts may consider a player's agreement. Actual declarations precede
effects (§3.2.1); a refusal reruns the flowchart before Build or Recruit, while
accepted agreements bind through the Command/Event (§1.5.2).
"""
from contextlib import contextmanager
from copy import deepcopy
import hashlib
import json

from fs_bot import rules_consts as rc

ANSWERS = '_recruit_supply_answers'
QUERIES = '_recruit_supply_queries'
CONFIRMATIONS = '_recruit_supply_confirmations'
REQUESTS = 'supply_line_requests'
CANDIDATE = 'supply_line_recruit_candidate'


def _key(request):
    return (request['requesting_faction'], request['faction'], request['region'])


def _signature(action):
    from fs_bot.state.serialize import encode
    return hashlib.sha256(json.dumps(encode(action), sort_keys=True).encode()).hexdigest()


@contextmanager
def forecast_supply(state):
    """Record hypothetical Supply requests without invoking a live callback."""
    missing = object()
    previous = state.get(QUERIES, missing)
    requests = []
    state[QUERIES] = requests
    try:
        yield requests
    finally:
        if previous is missing:
            state.pop(QUERIES, None)
        else:
            state[QUERIES] = previous


def forecast_answer(state, requester, controller, region):
    """Return a plan's known reply, or its explicitly hypothetical yes."""
    key = requester, controller, region
    request = {'requesting_faction': requester, 'faction': controller,
               'region': region}
    queries = state.get(QUERIES)
    if queries is not None and request not in queries:
        queries.append(request)
    answers = state.get(ANSWERS, {})
    from fs_bot.commands.rally import np_aedui_supply_key
    action_key = np_aedui_supply_key(state, requester, controller)
    if action_key is not None and action_key in answers:
        return answers[action_key]
    if key in answers:
        return answers[key]
    return True if queries is not None else None


def clear_supply_confirmation(state):
    state.pop(CONFIRMATIONS, None)


def confirm_supply_plan(state, action, answers):
    """Resolve concrete Supply dependencies; return whether to replan.

``answers`` is local to the caller's planning loop. A refusal or a real
consent die roll requires a new pure pass; speculative planning RNG must
never overwrite the live die. Only engine-created confirmations are used
by execution, never an answer claimed inside a player action.
    """
    from fs_bot.engine.agent import consult_agent, AGREEMENT
    from fs_bot.engine.supply_retry import resolve_np_supply
    from fs_bot.commands.rally import np_aedui_supply_key
    details = action.get('details') or {}
    requests = details.get(REQUESTS, [])
    before_rng = state['rng'].getstate()
    refused = False
    for request in requests:
        key = _key(request)
        if key in answers:
            continue
        requester, controller, region = key
        before_request_rng = state['rng'].getstate()
        action_key = np_aedui_supply_key(state, requester, controller)
        accepted = state.get('_supply_line_agreements', {})
        if action_key is not None and action_key in answers:
            answer = answers[action_key]
        elif action_key is not None and action_key in accepted:
            answer = accepted[action_key]
        elif key in accepted:
            answer = True
        elif controller in state.get('non_player_factions', ()):
            answer = resolve_np_supply(state, controller, requester)
        else:
            response = consult_agent(state, controller, {
                'kind': AGREEMENT, 'request_type': 'supply_line',
                'requesting_faction': requester,
                'context': {'region': region,
                            'proposed_action': deepcopy(details.get(CANDIDATE, action))},
            })
            if response is not None and type(response) is not bool:
                raise ValueError('Supply Line agreement requires true or false')
            answer = True if response is None else response
        answers[key] = bool(answer)
        if (action_key is not None
                and (answer or state['rng'].getstate() != before_request_rng
                     or action_key in answers or action_key in accepted)):
            answers[action_key] = bool(answer)
            if '_supply_line_agreements' in state:
                state['_supply_line_agreements'][action_key] = bool(answer)
        if answer and '_supply_line_agreements' in state:
            # A surrounding Event is already executing: its new promises
            # bind even if another refusal discards this sub-action. An
            # ordinary pre-Command forecast has no outer agreement scope.
            state['_supply_line_agreements'][key] = True
        refused |= not answer
    replan = refused or state['rng'].getstate() != before_rng
    executable = (action.get('command') not in (None, 'Pass')
                  or action.get('sa') not in (None, 'No SA'))
    if not executable or not requests or CANDIDATE in details:
        # A canceled ordinary Recruit may fall through to Seize. A promise
        # made for that Recruit cannot authorize the different Command;
        # its live SA negotiates again. Existing outer Event agreements
        # remain in their own §1.5.2 scope.
        clear_supply_confirmation(state)
    elif not replan and answers:
        state[CONFIRMATIONS] = {'signature': _signature(action),
                                'answers': deepcopy(answers)}
    return replan


@contextmanager
def install_confirmed_supply(state, action):
    """Use one confirmed plan's replies throughout its actual execution."""
    if state.get(QUERIES) is not None or state.get('_diviciacus_preview'):
        yield
        return
    saved = state.get(CONFIRMATIONS)
    if not saved or saved['signature'] != _signature(action):
        yield
        return
    from fs_bot.commands.rally import supply_agreement_scope
    state.pop(CONFIRMATIONS, None)
    missing = object()
    previous = state.get(ANSWERS, missing)
    state[ANSWERS] = dict(saved['answers'])
    try:
        with supply_agreement_scope(state):
            accepted = state['_supply_line_agreements']
            accepted.update({key: True for key, yes in saved['answers'].items() if yes})
            # Unlike a human refusal, the PR-07 automated Aedui refusal is
            # fixed for the action, including its accompanying Special Ability.
            from fs_bot.commands.rally import np_aedui_supply_key
            key = np_aedui_supply_key(state, rc.ROMANS, rc.AEDUI)
            if key is not None and key in saved['answers']:
                accepted[key] = saved['answers'][key]
            yield
    finally:
        if previous is missing:
            state.pop(ANSWERS, None)
        else:
            state[ANSWERS] = previous


def plan_with_recruit_supply(state, planner):
    """Plan, obtain concrete consent, and replan before any physical effects."""
    if state.get('_diviciacus_preview') or state.get(QUERIES) is not None:
        return planner(state)
    from fs_bot.engine.diviciacus_planning import confirm_plan, clear_confirmation
    initial_rng = state['rng'].getstate()
    initial_accepted = deepcopy(state.get('_supply_line_agreements'))
    answers = dict(state.get(ANSWERS, {}))
    denied_diviciacus = set(state.get('_diviciacus_refused', {}).get(rc.ROMANS, []))
    clear_supply_confirmation(state)
    try:
        while True:
            planning = deepcopy({k: v for k, v in state.items() if k != 'decision_agent'})
            planning['_diviciacus_preview'] = True
            planning[ANSWERS] = dict(answers)
            planning['_diviciacus_refused'] = {rc.ROMANS: sorted(denied_diviciacus)}
            action = planner(planning)
            if confirm_supply_plan(state, action, answers):
                clear_confirmation(state, rc.ROMANS)
                continue
            before_consent_rng = state['rng'].getstate()
            refused = set(confirm_plan(state, rc.ROMANS, action)) - denied_diviciacus
            if refused or state['rng'].getstate() != before_consent_rng:
                denied_diviciacus.update(refused)
                clear_supply_confirmation(state)
                continue
            state['rng'].setstate(planning['rng'].getstate())
            return action
    except BaseException:
        state['rng'].setstate(initial_rng)
        if initial_accepted is not None:
            accepted = state.setdefault('_supply_line_agreements', {})
            accepted.clear()
            accepted.update(initial_accepted)
        clear_supply_confirmation(state)
        clear_confirmation(state, rc.ROMANS)
        raise
