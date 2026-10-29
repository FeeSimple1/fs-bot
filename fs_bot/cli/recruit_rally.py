"""Human placement plans, preserving quantities and the chosen Rally order."""

from copy import deepcopy

from fs_bot.board.pieces import PieceError, get_available
from fs_bot.cli.menus import prompt_choice
from fs_bot.commands.common import CommandError
from fs_bot.commands.rally import (
    _find_subdued_tribe_for_ally, recruit_count_limits, recruit_in_region,
    rally_count_limits, rally_in_region, validate_recruit_region,
    validate_rally_option, validate_rally_region,
)
from fs_bot.rules_consts import (
    ARIOVISTUS_SCENARIOS, AUXILIA, BASE_SCENARIOS, BELGAE, GERMANS, WARBAND,
)


def _copy(state):
    # Planning never asks another human for consent or consumes live RNG.
    sim = deepcopy({k: v for k, v in state.items() if k != "decision_agent"})
    sim["_diviciacus_preview"] = True
    return sim


def _apply(state, faction, entry, *, rally, prior=()):
    from fs_bot.engine.diviciacus import placement_owner_scope
    sim = _copy(state)
    kwargs = {k: entry[k] for k in ("tribe", "count", "warband_mix") if k in entry}
    with placement_owner_scope(sim, faction, entry["region"], entry.get("placement_owners")):
        if rally:
            validate_rally_option(sim, entry["region"], faction, entry["action"], set(prior))
            result = rally_in_region(
                sim, entry["region"], faction, entry["action"],
                free=bool(prior), include_home_bonus=True,
                include_bonuses=not prior, **kwargs)
        else:
            result = recruit_in_region(sim, entry["region"], entry["action"], **kwargs)
    return sim, result


def _legal(state, faction, entry, *, rally, prior=()):
    try:
        _apply(state, faction, entry, rally=rally, prior=prior)
    except (CommandError, PieceError):
        return False
    return True


def _mixes(state, region, prior, entry=None):
    """Use the mechanic to validate exact physical-owner allocations."""
    from fs_bot.commands.sa_enlist import BORROW_KEY
    context = state.get(BORROW_KEY)
    if not context or region not in context["regions"]:
        return None
    if entry is not None and entry["action"] != "place_warbands":
        # A legal Ally option need not have a base for ordinary Warbands.
        # Only its compulsory additions need a physical-owner allocation.
        from fs_bot.commands.rally import _rally_bonus
        maximum = _rally_bonus(state, region, BELGAE, include_home_bonus=True,
                               include_bonuses=not prior)
        if not maximum:
            return []
    else:
        limits = rally_count_limits(state, region, BELGAE, include_home_bonus=True,
                                   include_bonuses=not prior)
        maximum = limits["cap"]
    german_max = min(maximum, get_available(state, GERMANS, WARBAND))
    if state["scenario"] in ARIOVISTUS_SCENARIOS:
        german_max = min(german_max, max(0, 4 - context["affected"]))
    own_max = min(maximum, get_available(state, BELGAE, WARBAND))
    entry = entry or {"region": region, "action": "place_warbands"}
    return [mix for german in range(german_max, -1, -1)
            for own in range(min(own_max, maximum - german), -1, -1)
            if _legal(state, BELGAE, dict(
                entry, warband_mix=(mix := {BELGAE: own, GERMANS: german})),
                rally=True, prior=prior)]


def _options(state, faction, region, *, rally, prior=()):
    """Derive options on the evolving board with the actual mechanics."""
    from fs_bot.cli.human_plan import _citadel_upgrade_tribes
    options = []
    action = "place_warbands" if rally else "place_auxilia"
    try:
        limits = (rally_count_limits(state, region, faction,
                                    include_home_bonus=True, include_bonuses=not prior)
                  if rally else recruit_count_limits(state, region))
        mixes = _mixes(state, region, prior) if rally and faction == BELGAE else None
        if mixes is not None:
            quantities = mixes
        else:
            quantities = [n for n in range(limits["max"], limits["min"] - 1, -1)
                          if _legal(state, faction, {
                              "region": region, "action": action, "count": n},
                              rally=rally, prior=prior)]
        if quantities:
            options.append(("Warbands" if rally else "Auxilia", action, quantities, mixes is not None))
    except (CommandError, PieceError):
        pass
    for label, action, tribes in (
        ("an Ally at a Subdued Tribe", "place_ally",
         _find_subdued_tribe_for_ally(state, region, faction)),
        ("a Citadel (replace your Ally at a City)", "place_citadel",
         _citadel_upgrade_tribes(state, region, faction) if rally else []),
    ):
        legal = [tribe for tribe in tribes if _legal(
            state, faction, {"region": region, "action": action, "tribe": tribe},
            rally=rally, prior=prior)]
        if legal:
            options.append((label, action, legal, False))
    return options


def _choose_mix(values, stdin, stdout):
    german = prompt_choice(stdin, stdout, "  Place how many German Warbands?",
                           [(str(n), n) for n in sorted(
                               {mix[GERMANS] for mix in values}, reverse=True)])
    own = prompt_choice(stdin, stdout, "  Place how many Belgic Warbands?",
                        [(str(mix[BELGAE]), mix[BELGAE]) for mix in values
                         if mix[GERMANS] == german])
    return {BELGAE: own, GERMANS: german}


def _entry(region, option, stdin, stdout):
    _, action, values, mixed = option
    entry = {"region": region, "action": action}
    if action in ("place_ally", "place_citadel"):
        entry["tribe"] = prompt_choice(
            stdin, stdout, f"  At which Tribe in {region}?", [(t, t) for t in values])
    elif mixed:
        entry["warband_mix"] = _choose_mix(values, stdin, stdout)
    else:
        piece = "Warbands" if action == "place_warbands" else AUXILIA
        entry["count"] = prompt_choice(
            stdin, stdout, f"  How many {piece} to place now (including required bonuses)?",
            [(str(n), n) for n in values])
    return entry


def collect(state, faction, stdin, stdout, single, *, rally, excluded=()):
    from fs_bot.cli.human_plan import _pick_regions, _playable_regions
    sim = _copy(state)
    validator = (lambda r: validate_rally_region(sim, r, faction)[0]) if rally else (
        lambda r: validate_recruit_region(sim, r)[0])
    regions = [r for r in _playable_regions(sim, faction)
               if r not in excluded and validator(r)]
    if not regions:
        return None
    command = "Rally" if rally else "Recruit"
    picked = _pick_regions(
        stdin, stdout, f"{command} in which Region(s), in resolution order?", regions,
        single=single, max_regions=state.get("_cli_command_max_regions"))
    entries = []
    for region in picked:
        prior = set()
        while True:
            options = _options(sim, faction, region, rally=rally, prior=prior)
            if not options:
                if not prior:
                    stdout.write(f"  No legal placement remains in {region}; skip this Region.\n")
                break
            choices = [(option[0], option) for option in options]
            choices.append(("Finish this Region" if prior else "Skip this Region", None))
            option = prompt_choice(stdin, stdout, f"  In {region}, place:", choices)
            if option is None:
                break
            entry = _entry(region, option, stdin, stdout)
            if rally and faction == BELGAE and entry["action"] != "place_warbands":
                mixes = _mixes(sim, region, prior, entry)
                if mixes and any(sum(mix.values()) for mix in mixes):
                    entry["warband_mix"] = _choose_mix(mixes, stdin, stdout)
            # Select physical owners before reserving the preview pools, so
            # cooperation does not hide a later native-only placement.
            from fs_bot.engine.diviciacus import placement_owner_request
            from fs_bot.cli.diviciacus import collect_pieces
            _, preview = _apply(sim, faction, entry, rally=rally, prior=prior)
            piece = WARBAND if rally else AUXILIA
            count = preview.get("pieces_placed", {}).get(piece, 0)
            request = (placement_owner_request(sim, region, faction, piece, count)
                       if count else None)
            if request is not None:
                entry["placement_owners"] = collect_pieces(
                    sim, faction, request, stdin, stdout)["counts"]
            sim, result = _apply(sim, faction, entry, rally=rally, prior=prior)
            entries.append(entry)
            prior.add(entry["action"])
            if entry["action"] in ("place_ally", "place_citadel"):
                for piece in (WARBAND, AUXILIA):
                    bonus = result.get("pieces_placed", {}).get(piece, 0)
                    if bonus:
                        stdout.write(f"  This placement also adds {bonus} {piece}.\n")
            if not rally:
                break
    if not entries:
        return None
    return {"rally_plan": {"steps": entries}} if rally else {"recruit_plan": entries}


def collect_enlist_rally(state, region, stdin, stdout):
    """The free German Command uses German limits, including its Home minimum."""
    from fs_bot.commands.enlist_free import execute_free_enlist
    base = state["scenario"] in BASE_SCENARIOS

    def legal(plan):
        try:
            return execute_free_enlist(_copy(state), plan)
        except (CommandError, PieceError):
            return None

    common = {"type": "german_rally", "region": region}
    plans = [dict(common, place="warbands")]
    plans += [dict(common, place="ally", tribe=tribe)
              for tribe in _find_subdued_tribe_for_ally(state, region, GERMANS)]
    available = []
    for plan in plans:
        if plan["place"] == "warbands" or base:
            # The exact mechanic also enforces Enlist's expansion four-piece
            # allowance and rejects an invalid follow-on after placing an Ally.
            counts = [n for n in range(get_available(state, GERMANS, WARBAND), -1, -1)
                      if legal(dict(plan, count=n)) is not None]
            if counts:
                available.append((plan, counts))
        elif legal(plan) is not None:
            available.append((plan, None))
    if not available:
        stdout.write(f"  No legal German Rally remains in {region}.\n")
        return None
    places = [place for place in ("warbands", "ally")
              if any(plan["place"] == place for plan, _ in available)]
    place = prompt_choice(stdin, stdout, "  German Rally placement?",
                          [("Warbands" if p == "warbands" else "an Ally", p) for p in places])
    choices = [(plan, counts) for plan, counts in available if plan["place"] == place]
    if place == "ally":
        tribe = prompt_choice(stdin, stdout, "  Ally which Tribe?",
                              [(plan["tribe"], plan["tribe"]) for plan, _ in choices])
        choices = [(plan, counts) for plan, counts in choices if plan["tribe"] == tribe]
    plan, counts = choices[0]
    if counts is not None:
        prompt = ("  Place how many German Warbands after the Ally?" if place == "ally"
                  else "  Place how many German Warbands (including required bonuses)?")
        plan["count"] = prompt_choice(stdin, stdout, prompt, [(str(n), n) for n in counts])
    return plan
