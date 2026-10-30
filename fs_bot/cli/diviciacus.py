"""Human choices for consenting Roman/Aedui cooperation (38, A1.4)."""

from contextlib import nullcontext

from fs_bot.cli.menus import prompt_choice, prompt_yes_no
from fs_bot.rules_consts import ROMANS, AEDUI, AUXILIA, WARBAND


def choose_regions(state, faction, phase, stdin, stdout, *, excluded=()):
    """Select requested cooperation without consuming the other human's reply."""
    from fs_bot.engine.diviciacus import eligible_regions
    regions = sorted(set(eligible_regions(state, faction, phase=phase))
                     - set(excluded))
    allowed = state.get("_cli_allowed_regions")
    if allowed is not None:
        regions = [region for region in regions if region in allowed]
    if not regions:
        return None
    label = "Special Activity" if phase == "special_ability" else "Command"
    if not prompt_yes_no(stdin, stdout,
                         f"Request Diviciacus cooperation for this {label}?",
                         default=False):
        return []
    from fs_bot.cli.human_plan import _pick_regions
    selected = _pick_regions(
        stdin, stdout, "Use cooperating forces in which Regions?",
        regions, at_least_one=True)
    stdout.write("Planning assumes the other Faction agrees. Their actual "
                 "decision is made when this action resolves.\n")
    return selected


def planning_scope(state, faction, regions, phase):
    if not regions:
        return nullcontext()
    from fs_bot.engine.diviciacus import force_scope
    return force_scope(state, faction, regions, phase=phase)


def collect_pieces(state, faction, request, stdin, stdout):
    """Offer every allocation between physical owners for the requested count."""
    available = request["available"]
    count = request["count"]
    phase = request["phase"]
    verb = {"placement": "Place", "formation": "Move", "dropoff": "Leave",
            "loss": "Remove"}.get(
        phase, "Choose")
    stdout.write(f"\n{faction}: {verb.lower()} {count} {request['piece_type']} "
                 f"in {request['region']}; choose their physical owners.\n")
    roman_max = min(count, available.get(ROMANS, 0))
    roman_min = max(0, count - available.get(AEDUI, 0))
    number = prompt_choice(
        stdin, stdout, f"{verb} which pieces?",
        [(f"{n} {ROMANS} {AUXILIA} and {count - n} {AEDUI} {WARBAND}", n)
         for n in range(roman_min, roman_max + 1)])
    return {"counts": {ROMANS: number, AEDUI: count - number}}


def collect_force_cohort(state, faction, request, stdin, stdout):
    """Keep an Event's selected physical counters distinct during borrowing."""
    count, available = request['count'], request['available']
    selected_label = request.get('selected_label', 'selected Event group')
    other_label = request.get('other_label', 'other counters')
    low = max(0, count - available.get('other', 0))
    high = min(count, available.get('selected', 0))
    number = prompt_choice(stdin, stdout,
        f"{faction}: {request['operation']} {count} {request['piece_type']} "
        f"in {request['region']}; which physical counters?",
        [(f'{n} {selected_label}; {count - n} {other_label}', n)
         for n in range(low, high + 1)]
        + [('Use the standard physical order', None)])
    return ({'use_default': True} if number is None
            else {'counts': {'selected': number, 'other': count - number}})
