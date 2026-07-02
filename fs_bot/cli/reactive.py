"""CLI reactive-decision agent — prompts a human for the choices forced on
them during ANOTHER action's resolution (engine/agent.py request kinds):

  RETREAT    — the defender's Retreat choice (§3.2.4/§8.4.3)
  LOSS_ORDER — which pieces absorb Battle Losses, in what order (§3.2.4)
  AGREEMENT  — inter-Faction agreements (§1.5.2): Supply Line, Retreat into
               your Control, Quarters, Harassment, Trade

Installed as state["decision_agent"] for games with any human seat. Returns
None (defer to the engine's defaults) for bot factions, on EOF (piped or
scripted input that ends early), and for unknown request kinds.
"""

from fs_bot.engine.agent import RETREAT, LOSS_ORDER, AGREEMENT
from fs_bot.cli.menus import prompt_choice, prompt_yes_no


def _fmt_piece(piece):
    ptype, pstate = piece
    return f"{ptype} ({pstate})" if pstate else str(ptype)


def make_cli_reactive(human_factions, stdin, stdout):
    """Build a decision agent that prompts the given human factions."""
    humans = set(human_factions)

    def agent(state, faction, request):
        if faction not in humans:
            return None
        kind = request.get("kind")
        try:
            if kind == RETREAT:
                legal = list(request.get("legal_regions") or [])
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
                return prompt_yes_no(
                    stdin, stdout,
                    f"\n{faction}: {rf} asks your agreement — {rt}{where}. "
                    f"Agree?", default=True)
        except EOFError:
            return None
        return None

    return agent
