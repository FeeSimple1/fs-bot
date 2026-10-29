"""Human Leader placement during Spring and scenario transitions."""

from fs_bot.board.pieces import count_pieces
from fs_bot.cli.menus import prompt_choice
from fs_bot.rules_consts import LEADER


def collect_leader(state, faction, request, stdin, stdout):
    """Expose every offered destination, including empty legal Home Regions."""
    leader = request["leader"]
    if request.get("source") == "spring_box":
        stdout.write(
            f"\n{faction}: {leader} may enter from the Spring box. "
            "Choose any offered Region, or leave him in the box for later.\n")
    else:
        stdout.write(f"\n{faction}: place {leader}. Placement is required.\n")
    choices = []
    for region in request["legal_regions"]:
        count = count_pieces(state, region, faction)
        label = "own pieces"
        if request.get("reason") == "interlude_ambiorix":
            count -= count_pieces(state, region, faction, LEADER)
            label = "other own pieces"
        choices.append((f"{region} ({count} {label})", region))
    if request.get("can_defer"):
        choices.append(("Leave in the Spring box for now", "defer"))
    choices.append(("Use bot placement priorities", "default"))
    selected = prompt_choice(stdin, stdout, "Leader destination?", choices)
    if selected == "default":
        return {"use_default": True}
    if selected == "defer":
        return {"defer": True}
    return {"region": selected}
