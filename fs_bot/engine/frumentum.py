"""A53: Aedui fund distinct paid Roman actions in any selected order.

Card A53 and A8.6.6 govern the amount and actions. User-adopted provisional
ruling PR-03 treats the allocation as a transfer: Romans retain unused funds.
See docs/provisional-rulings.md; an authoritative clarification may supersede
this ruling. Ordinary negotiated transfers remain separate from this grant.
"""
from contextlib import contextmanager
from copy import deepcopy

from fs_bot.rules_consts import AEDUI, ROMANS, MAX_RESOURCES
from fs_bot.engine.agent import consult_agent
from fs_bot.commands.rally import preserve_supply_agreements


ACTION_SA = "Special Ability"
ACTIONS = ("Recruit", "March", ACTION_SA)


@contextmanager
def spending_scope(state, allowance):
    """Keep Roman personal funds reserved and suspend inherited free costs."""
    missing = object()
    saved = {key: state.get(key, missing) for key in
             ("_free_action_factions", "_planning_free_command", "_planning_event_command")}
    treasury = state["resources"].get(ROMANS, 0)
    budget = state.get("_frumentum_budget")
    prior_paying = budget.get("paying", False) if budget else False
    if budget is not None:
        budget["paying"] = True
    state["resources"][ROMANS] = allowance
    state["_free_action_factions"] = set(state.get("_free_action_factions", ())) - {ROMANS}
    state.pop("_planning_free_command", None)
    state["_planning_event_command"] = True
    try:
        yield
    finally:
        state["resources"][ROMANS] = treasury
        if budget is not None:
            budget["paying"] = prior_paying
        for key, value in saved.items():
            if value is missing:
                state.pop(key, None)
            else:
                state[key] = value


def _copy(state):
    return deepcopy({k: v for k, v in state.items() if k != "decision_agent"})


def _action_kind(plan):
    return plan.get("command") or ACTION_SA


def _execute(state, plan, allowance, *, request=None):
    from fs_bot.engine.execute import _execute_recruit, _execute_march, _execute_sa
    from fs_bot.engine.recruit_planning import install_confirmed_supply
    with install_confirmed_supply(state, plan), spending_scope(state, allowance):
        original = plan
        if request is not None and (plan.get('command') == 'Recruit'
                                    or plan.get('sa') == 'Build'):
            from fs_bot.engine.supply_reconsideration import reconsider
            sa_only = plan.get('command') is None
            plan = reconsider(state, ROMANS, plan, with_sa=sa_only, sa_only=sa_only,
                              allowed_commands=[cmd for cmd in ('Recruit', 'March')
                                                if cmd in request['remaining_actions']],
                              frumentum=request)
        command = plan.get("command")
        if 'skip' in plan:
            result = {'executed': False, 'declined_no_effect': True}
        elif command == "Recruit":
            result = _execute_recruit(state, ROMANS, plan)
        elif command == "March":
            result = _execute_march(state, ROMANS, plan)
        else:
            result = _execute_sa(state, ROMANS, plan) or {"executed": False}
        if plan != original:
            result['supply_replacement'] = deepcopy(plan)
        spent = allowance - state["resources"][ROMANS]
    return result, spent


def validate_response(state, request, response):
    """Validate typed Aedui allocations and paid Roman choices on a copy."""
    if response in ({"decline": True}, {"use_default": True}):
        return
    if not isinstance(response, dict):
        raise ValueError("Frumentum requires an amount or action object.")
    if request["kind"] == "frumentum_amount":
        if (set(response) != {"amount"} or type(response["amount"]) is not int
                or not 0 <= response["amount"] <= state["resources"].get(AEDUI, 0)):
            raise ValueError("Choose a whole-number amount from the Aedui's available Resources.")
        return
    remaining = request.get("remaining_actions", list(ACTIONS))
    if set(response) == {"skip"}:
        if response["skip"] not in remaining:
            raise ValueError("That Frumentum action is not available to skip.")
        return
    if any(key in response for key in ("skip", "decline", "use_default", "amount")):
        raise ValueError("Choose exactly one Frumentum action or control response.")
    command, sa = response.get("command"), response.get("sa", "No SA")
    if _action_kind(response) not in remaining:
        raise ValueError("Choose an unused Frumentum action: Recruit, March, or one SA.")
    if command not in (None, "Recruit", "March"):
        raise ValueError("Frumentum grants only Recruit and March Commands.")
    if command and sa not in (None, "No SA"):
        raise ValueError("Select the Special Ability as its own action in the desired order.")
    if command is None and sa not in ("Build", "Scout"):
        raise ValueError("Choose Build or Scout; Besiege requires a Battle that A53 does not grant.")
    details = response.get("details")
    if not isinstance(details, dict):
        raise ValueError("Supply the complete paid action plan in details.")
    if any(key in details for key in ("transfers", "command_parts", "free")):
        raise ValueError("Frumentum funds only its three distinct paid actions.")
    required = {"Recruit": "recruit_plan", "Build": "build_plan", "Scout": "scout_plan"}.get(command or sa)
    if required is not None and required not in details:
        raise ValueError(f"An explicit {required} is required.")
    from fs_bot.engine.free_actions import _result_error
    from fs_bot.commands.common import CommandError
    from fs_bot.board.pieces import PieceError
    try:
        trial = _copy(state)
        trial['_diviciacus_preview'] = True
        result, spent = _execute(trial, deepcopy(response), request["remaining_resources"])
    except (CommandError, PieceError, ValueError, TypeError, KeyError, IndexError, AttributeError) as exc:
        raise ValueError(f"Invalid paid Frumentum plan: {exc}") from exc
    error = _result_error(result)
    if error:
        raise ValueError(f"Invalid paid Frumentum plan: {error}")
    if not result.get("executed"):
        raise ValueError("Frumentum plan has no legal effect within the remaining allocation.")
    if not 0 <= spent <= request["remaining_resources"]:
        raise ValueError("Frumentum cannot spend beyond the Aedui allocation.")


def _default_amount(state):
    from fs_bot.bots.aedui_bot import node_a_agreements
    answer = node_a_agreements(state, ROMANS, "frumentum_transfer")
    return answer.get("amount", 0) if isinstance(answer, dict) else 0


def _sa_plan(state, sa):
    from fs_bot.bots.roman_bot import node_r_build, node_r_scout
    if sa == "Build":
        details = {"build_plan": node_r_build(state)}
    elif sa == "Scout":
        details = {"scout_plan": node_r_scout(state)}
    else:
        return None
    return {"command": None, "regions": [], "sa": sa,
            "sa_regions": [], "details": details}


def _default_action(state, request):
    from fs_bot.engine.recruit_planning import plan_with_recruit_supply
    return plan_with_recruit_supply(
        state, lambda planning: _default_action_once(planning, request))


def _default_action_once(state, request):
    """Follow the Roman chart within the remaining paid grant (A8.2.3)."""
    from fs_bot.bots.bot_dispatch import dispatch_bot_turn
    from fs_bot.bots.roman_bot import node_r_march, node_r_recruit
    from fs_bot.engine.execute import _sa_runs_before_command
    planning = _copy(state)
    planning["rng"] = state["rng"]  # only real bot-choice tie breaks advance RNG
    planning["can_play_event"] = False
    planning["is_second_eligible"] = False
    planning["non_player_factions"] = set(state.get("non_player_factions", ())) | {ROMANS}
    planning["_diviciacus_preview"] = True
    remaining = request["remaining_actions"]
    planning["_command_with_sa"] = ACTION_SA in remaining
    with spending_scope(planning, request["remaining_resources"]):
        candidates = []

        def append_action(action):
            command_name, sa = action.get("command"), action.get("sa")
            if command_name not in remaining:
                return
            sa_plan = _sa_plan(planning, sa) if ACTION_SA in remaining else None
            before = _sa_runs_before_command(command_name, sa)
            if before and sa_plan:
                candidates.append(sa_plan)
            command = deepcopy(action)
            command.update(sa="No SA", sa_regions=[])
            candidates.append(command)
            if not before and sa_plan:
                candidates.append(sa_plan)

        append_action(dispatch_bot_turn(planning, ROMANS))
        # If the chart chose an unavailable Command, retain its node order.
        for node in (node_r_march, node_r_recruit):
            append_action(node(planning))
        if ACTION_SA in remaining:
            candidates.extend(_sa_plan(planning, sa) for sa in ("Build", "Scout"))
    for candidate in candidates:
        if candidate is None:
            continue
        try:
            validate_response(state, request, candidate)
        except ValueError:
            continue
        # A53 resolves its SA and Commands as separate choices. Confirm only
        # the selected action's routes, not a later Recruit from the combined
        # flowchart forecast or an already-used Special Ability.
        from fs_bot.engine.recruit_planning import forecast_supply
        trial = _copy(state)
        with forecast_supply(trial) as requests:
            _execute(trial, deepcopy(candidate), request["remaining_resources"])
        candidate.setdefault("details", {})["supply_line_requests"] = requests
        return candidate
    return {"decline": True}


@preserve_supply_agreements
def resolve_frumentum(state):
    """Select funding, then resolve each distinct Roman action in chosen order."""
    from fs_bot.cards.card_effects import _event_step
    _event_step(state, "A53.funding")
    request = {"kind": "frumentum_amount", "card_id": "A53",
               "available_resources": state["resources"].get(AEDUI, 0)}
    while True:
        response = (None if AEDUI in state.get("non_player_factions", ())
                    else consult_agent(state, AEDUI, request))
        if response is None or response == {"use_default": True}:
            amount = _default_amount(state)
            break
        try:
            validate_response(state, request, response)
        except ValueError as exc:
            request["errors"] = [str(exc)]
            continue
        amount = 0 if response == {"decline": True} else response["amount"]
        break
    state["resources"][AEDUI] -= amount
    remaining, allowance, results, errors = list(ACTIONS), amount, [], []
    treasury = state["resources"].get(ROMANS, 0)
    context = {"allocated": amount, "remaining": allowance, "reserved_treasury": treasury}
    state["_frumentum_budget"] = context
    try:
        while remaining:
            from fs_bot.cards.card_effects import _event_step
            _event_step(state, "A53.action")
            request = {"kind": "frumentum_action", "card_id": "A53",
                       "remaining_actions": list(remaining),
                       "remaining_resources": allowance, "allocated_resources": amount,
                       "reserved_roman_resources": treasury}
            if errors:
                request["errors"] = errors
            response = (None if ROMANS in state.get("non_player_factions", ())
                        else consult_agent(state, ROMANS, request))
            if response is None or response == {"use_default": True}:
                response = _default_action(state, request)
            try:
                validate_response(state, request, response)
            except ValueError as exc:
                errors = [str(exc)]
                continue
            if response == {"decline": True}:
                break
            if "skip" in response:
                remaining.remove(response["skip"])
                errors = []
                continue
            result, spent = _execute(state, response, allowance, request=request)
            response = result.get('supply_replacement', response)
            kind = response.get('skip') or _action_kind(response)
            remaining.remove(kind)
            allowance -= spent
            context["remaining"] = allowance
            results.append({"action": kind, "plan": response,
                            "spent": spent, "result": result})
            errors = []
    finally:
        # Provisional PR-03: the allocation is transferred, with no automatic
        # refund. Keep the historical unused_policy result label for saved
        # logs/controllers; authoritative clarification may change the ruling.
        state["resources"][ROMANS] = min(MAX_RESOURCES, treasury + allowance)
        state.pop("_frumentum_budget", None)
    return [{"flag": "card_A53", "event_action": "frumentum", "allocated": amount,
             "spent": amount - allowance, "unused": allowance,
             "unused_policy": "legacy_roman_retention", "actions": results,
             "result": {"executed": bool(amount or results)}}]
