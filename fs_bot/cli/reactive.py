"""CLI reactive-decision agent -- prompts a human for the choices forced on
them during ANOTHER action's resolution (engine/agent.py request kinds):

  RETREAT    -- the defender's Retreat choice (Sec.3.2.4/Sec.8.4.3)
  LOSS_ORDER -- which pieces absorb Battle Losses, in what order (Sec.3.2.4)
  HARASSMENT_LOSS -- choose casualties or a hard-piece roll (Sec.3.2.2–3)
  AGREEMENT  -- inter-Faction agreements (Sec.1.5.2): Supply Line, Retreat into
               your Control, Quarters, Harassment, Trade

Installed as state["decision_agent"] for games with any human seat. Returns
None (defer to the engine's defaults) for bot factions and unknown request
kinds. Input exhaustion interrupts the action so it can be saved and resumed.
"""

from fs_bot.engine.agent import RETREAT, LOSS_ORDER, AGREEMENT, HARASSMENT_LOSS
from fs_bot.cli.menus import prompt_choice, prompt_yes_no
from fs_bot.rules_consts import WARBAND


def _fmt_piece(piece):
    ptype, pstate = piece[:2]
    label = f"{ptype} ({pstate})" if pstate else str(ptype)
    if len(piece) >= 3 and piece[2] is not None:
        label = f"{piece[2]} {label}"
    if len(piece) == 4 and piece[3] == 'elite':
        label += ' (as Legion)'
    return label


def make_cli_reactive(human_factions, stdin, stdout):
    """Build a decision agent that prompts the given human factions."""
    humans = set(human_factions)

    def agent(state, faction, request):
        if faction not in humans:
            return None
        kind = request.get("kind")
        try:
            if kind == "voluntary_removal":
                from fs_bot.cli.voluntary_removal import collect_removals
                return collect_removals(state, faction, request, stdin, stdout)
            if kind == 'force_cohort':
                from fs_bot.cli.diviciacus import collect_force_cohort
                return collect_force_cohort(state, faction, request, stdin, stdout)
            if kind == 'battle_elite':
                from fs_bot.battle.elite import collect_selection
                return collect_selection(state, faction, request, stdin, stdout)
            if kind == 'quarters_provincia':
                from fs_bot.cli.quarters import collect_provincia
                return collect_provincia(state, faction, request, stdin, stdout)
            if kind == 'quarters_payment':
                from fs_bot.cli.quarters import collect_payment
                return collect_payment(state, faction, request, stdin, stdout)
            if kind == "supply_refusal":
                from fs_bot.cli.supply import collect_supply_refusal
                return collect_supply_refusal(state, faction, request, stdin, stdout)
            if kind == "trade_region":
                from fs_bot.cli.trade import collect_trade_region
                return collect_trade_region(state, faction, request, stdin, stdout)
            if kind == "spring_leader":
                from fs_bot.cli.spring import collect_leader
                return collect_leader(state, faction, request, stdin, stdout)
            if kind in ("council_selection", "council_choice"):
                from fs_bot.cli.council import collect_selection, collect_choice
                collect = collect_selection if kind == "council_selection" else collect_choice
                return collect(state, faction, request, stdin, stdout)
            if kind == "diviciacus_pieces":
                from fs_bot.cli.diviciacus import collect_pieces
                return collect_pieces(state, faction, request, stdin, stdout)
            if kind == "march_cohort":
                from fs_bot.cli.march_choices import collect_march_cohort
                return collect_march_cohort(state, faction, request, stdin, stdout)
            if kind in ("winter_uprising_timing", "winter_uprising_placement"):
                from fs_bot.cli.winter_uprising import collect_timing, collect_placement
                collector = collect_timing if kind == "winter_uprising_timing" else collect_placement
                return collector(state, faction, request, stdin, stdout)
            if kind == "ambacti_removal":
                from fs_bot.cli.ambacti import collect_removal
                return collect_removal(state, faction, request, stdin, stdout)
            if kind == "raid_intimidate":
                from fs_bot.cli.raid_intimidate import collect_raid_intimidate
                return collect_raid_intimidate(state, faction, request, stdin, stdout)
            if kind in ("frumentum_amount", "frumentum_action"):
                from fs_bot.cli.frumentum import collect_frumentum
                return collect_frumentum(state, faction, request, stdin, stdout)
            if kind == "kinship":
                from fs_bot.cli.kinship import collect_kinship
                return collect_kinship(state, faction, request, stdin, stdout)
            if kind == "free_action":
                from fs_bot.cli.free_actions import collect_free_action
                return collect_free_action(state, faction, request, stdin, stdout)
            if kind == "winter_campaign":
                from fs_bot.cli.winter_campaign import collect_winter_campaign
                return collect_winter_campaign(state, faction, request, stdin, stdout)
            if kind == "quarters_plan":
                from fs_bot.cli.quarters import collect_quarters_plan
                return collect_quarters_plan(state, faction, request, stdin, stdout)
            if kind == HARASSMENT_LOSS:
                phase = request["phase"]
                stdout.write(
                    f"\n{faction}: {request.get('harasser')} Harassment in "
                    f"{request['region']}, Loss {request['loss_index']} of "
                    f"{request['num_losses']}.\n")
                if phase == "remove":
                    stdout.write(f"Die roll {request['roll']}: remove a hard piece.\n")
                elif phase == "ally":
                    stdout.write("Choose the Roman Allied Tribe to remove.\n")
                elif phase == "piece_state":
                    stdout.write(f"Choose which {request['piece_type']} to remove.\n")
                elif phase == 'physical_owner':
                    stdout.write('Choose the physical owner of the moving-group casualty.\n')
                else:
                    stdout.write("Remove a soft piece, or roll: on 1–3 remove a "
                                 "hard piece; on 4–6 lose nothing.\n")
                options = [("Use bot default", None)]
                for option in request["options"]:
                    label = ("Roll for a hard piece" if option == "roll"
                             else f"Remove {option}")
                    if phase == "piece_state":
                        label = f"Remove {option} {request['piece_type']}"
                    elif phase == 'physical_owner':
                        label = (f"Remove a {request.get('piece_state', '')} {option} "
                                 f"{request['piece_type']} from the moving group")
                    options.append((label, option))
                choice = prompt_choice(stdin, stdout, "Harassment Loss?", options)
                return {"use_default": True} if choice is None else {"choice": choice}
            if kind == RETREAT:
                legal = list(request.get("legal_regions") or [])
                ctx = request.get("context") or {}
                if ctx.get("rampage"):
                    stdout.write(
                        f"\n{faction}: {request.get('attacker')} Rampages "
                        f"in {request.get('region')} -- "
                        f"{ctx.get('num_pieces')} of your piece(s) must "
                        f"Retreat or be removed (Sec.4.5.2).\n")
                    opts = [("Remove them", "stay")]
                    opts += [(f"Retreat them to {r}", r) for r in legal]
                    pick = prompt_choice(stdin, stdout,
                                         "Remove or Retreat?", opts)
                    if pick == "stay":
                        return {"retreat": False, "region": None}
                    return {"retreat": True, "region": pick}
                stdout.write(
                    f"\n{faction}: {request.get('attacker')} Battles you in "
                    f"{request.get('region')}"
                    f"{' (Ambush!)' if request.get('is_ambush') else ''}.\n")
                opts = [("No Retreat (take Losses in place)", "stay")]
                opts += [(f"Retreat to {r}", r) for r in legal]
                pick = prompt_choice(stdin, stdout, "Retreat?", opts)
                if pick == "stay":
                    return {"retreat": False, "region": None}
                return {"retreat": True, "region": pick}

            if kind == LOSS_ORDER:
                pieces = list(request.get("pieces") or [])
                if not pieces:
                    return None
                stdout.write(
                    f"\n{faction}: order pieces to absorb "
                    f"{request.get('num_losses')} Loss(es) in "
                    f"{request.get('region')} (hard pieces still roll).\n")
                chosen, remaining = [], list(pieces)
                while remaining:
                    opts = [(_fmt_piece(p), i)
                            for i, p in enumerate(remaining)]
                    if chosen:
                        opts.append(("(default order for the rest)", None))
                    pick = prompt_choice(
                        stdin, stdout,
                        f"Next piece to absorb a Loss "
                        f"({len(chosen)} ordered):", opts)
                    if pick is None:
                        break
                    chosen.append(remaining.pop(pick))
                return chosen or None

            if kind == AGREEMENT:
                rt = request.get("request_type") or "agreement"
                rf = request.get("requesting_faction")
                ctx = request.get("context") or {}
                where = f" in {ctx['region']}" if ctx.get("region") else ""
                if rt == "diviciacus_defense":
                    return prompt_yes_no(
                        stdin, stdout,
                        f"\n{faction}: request Diviciacus cooperation to defend "
                        f"against {ctx.get('attacker')}{where}? Cooperating "
                        "forces can affect Ambush and absorb Battle losses.",
                        default=False)
                if rt == "diviciacus_command":
                    regions = ", ".join(ctx.get("regions") or [])
                    targets = ", ".join(dict.fromkeys(
                        enemy for enemies in (ctx.get("targets") or {}).values()
                        for enemy in enemies))
                    return prompt_yes_no(
                        stdin, stdout,
                        f"\n{faction}: request Diviciacus cooperation for "
                        f"card {ctx.get('card_id')}'s {ctx.get('command')} "
                        f"against {targets} in {regions}? Cooperating forces "
                        "fight and can absorb losses as your pieces. The "
                        "other Faction must also agree.", default=False)
                if rt == "diviciacus":
                    regions = ", ".join(ctx.get("regions") or [])
                    phase = ctx.get("phase", "command").replace("_", " ")
                    return prompt_yes_no(
                        stdin, stdout,
                        f"\n{faction}: agree to Diviciacus cooperation with {rf} "
                        f"for this {phase} in {regions}? Roman Auxilia and "
                        "Aedui Warbands can act as the other type, move and "
                        "take losses while keeping their physical owners.",
                        default=False)
                if rt == "admagetobriga_warbands":
                    return prompt_yes_no(
                        stdin, stdout,
                        f"\n{faction}: lend your Warbands and Auxilia{where} "
                        f"to {rf} for Battle against {ctx.get('defender')}? "
                        "They fight as that faction's pieces, can take its "
                        "Counterattack losses, and surviving Hidden pieces "
                        "will Reveal. Agree?", default=False)
                if rt == "harassment":
                    # An opt-in, not a favour: your Hidden Warbands may
                    # Harass the moving/foraging group (Sec.3.2.2).
                    return prompt_yes_no(
                        stdin, stdout,
                        f"\n{faction}: your {ctx.get('hidden_warbands')} "
                        f"Hidden {ctx.get('harassing_piece', WARBAND)} may Harass {rf}'s "
                        f"{'Vercingetorix ' if ctx.get('vercingetorix') else ''}"
                        f"group{where} (1 Loss per 3). Harass?",
                        default=False)
                if rt == "retreat_into_control":
                    # Sec.3.2.4: a Defender may Retreat into an adjacent
                    # Region only if its controller agrees.
                    frm = ctx.get("from_region")
                    frm_txt = f" defeated in {frm}" if frm else ""
                    return prompt_yes_no(
                        stdin, stdout,
                        f"\n{faction}: {rf} pieces{frm_txt} want to "
                        f"RETREAT into {ctx.get('region')}, which you "
                        f"Control (Sec.3.2.4). Agreeing lets their "
                        f"survivors enter your Region; refusing may "
                        f"leave them nowhere to run. Agree?",
                        default=False)
                if rt == "supply_line":
                    # Sec.3.2.1: chains need each controller's agreement.
                    return prompt_yes_no(
                        stdin, stdout,
                        f"\n{faction}: {rf} asks to trace a SUPPLY LINE "
                        f"through {ctx.get('region')}, which you Control "
                        f"(Sec.3.2.1). Agreeing gives them cheaper "
                        f"Recruit/Quarters through your Region this "
                        f"action. Agree?", default=True)
                if rt == "trade_roman_agreement":
                    # Sec.4.4.1: Roman agreement doubles Aedui Trade
                    # yields (the Aedui often share the proceeds).
                    return prompt_yes_no(
                        stdin, stdout,
                        f"\n{faction}: the Aedui ask your blessing for "
                        f"TRADE (Sec.4.4.1). Agreeing doubles their "
                        f"yield from Allies/Citadels on Supply Lines; "
                        f"refusing halves it (a way to starve an Aedui "
                        f"about to win). Agree?", default=True)
                return prompt_yes_no(
                    stdin, stdout,
                    f"\n{faction}: {rf} asks your agreement -- {rt}{where}. "
                    f"Agree?", default=True)
        except EOFError:
            raise
        return None

    agent.supports_action_windows = True
    return agent
