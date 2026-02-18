"""Commands module — Rally, Recruit, March, Raid, Seize, Special Activities.

Sub-modules:
    common: Shared CommandError exception and helper functions.
    rally: Rally (Gallic/Germanic) and Recruit (Roman) commands.
    march: March (all factions) and Harassment.
    raid: Raid (Gallic/Germanic) command.
    seize: Seize (Roman) command.
    sa_ambush: Ambush SA — §4.3.3, §4.4.3, §4.5.3, §3.4.4, A4.3.3, A4.6.3
    sa_scout: Scout SA — §4.2.2
    sa_build: Build SA — §4.2.1
    sa_besiege: Besiege SA — §4.2.3
    sa_entreat: Entreat SA — §4.3.1
    sa_devastate: Devastate SA — §4.3.2
    sa_trade: Trade SA — §4.4.1
    sa_suborn: Suborn SA — §4.4.2
    sa_enlist: Enlist SA — §4.5.1
    sa_rampage: Rampage SA — §4.5.2
    sa_settle: Settle SA — A4.6.1
    sa_intimidate: Intimidate SA — A4.6.2

Reference: §3.2.1, §3.2.2, §3.2.3, §3.3.1, §3.3.2, §3.3.3,
           §3.4.1, §3.4.2, §3.4.3, §3.4.5,
           §6.2.1, §6.2.2, §6.2.3,
           A3.2.1, A3.2.2, A3.2.3, A3.3.1, A3.3.2, A3.3.3,
           A3.4.1, A3.4.2, A3.4.3, A3.4.5,
           §4.0-§4.5, A4.0-A4.6
"""

from fs_bot.commands.common import (  # noqa: F401
    CommandError,
)

from fs_bot.commands.rally import (  # noqa: F401
    recruit_in_region,
    rally_in_region,
    has_supply_line,
    recruit_cost,
    rally_cost,
    validate_recruit_region,
    validate_rally_region,
    germans_phase_rally,
)

from fs_bot.commands.march import (  # noqa: F401
    execute_march,
    march_from_origin,
    march_group,
    march_cost,
    resolve_harassment,
    germans_phase_march,
    drop_off_pieces,
    MarchError,
)

from fs_bot.commands.raid import (  # noqa: F401
    raid_in_region,
    validate_raid_region,
    validate_raid_steal_target,
    get_valid_steal_targets,
    germans_phase_raid_region,
    get_germans_phase_raid_targets,
)

from fs_bot.commands.seize import (  # noqa: F401
    seize_in_region,
    validate_seize_region,
    count_dispersed_on_map,
    get_dispersible_tribes,
    calculate_forage,
    calculate_harassment,
    get_harassment_factions,
    execute_harassment_loss,
    remove_hard_target,
    seize_rally_roll,
)

# ── Special Activities ──

from fs_bot.commands.sa_ambush import (  # noqa: F401
    validate_ambush_region,
)

from fs_bot.commands.sa_scout import (  # noqa: F401
    scout_move,
    scout_reveal,
)

from fs_bot.commands.sa_build import (  # noqa: F401
    validate_build_region,
    build_fort,
    build_subdue,
    build_place_ally,
)

from fs_bot.commands.sa_besiege import (  # noqa: F401
    validate_besiege_region,
    get_besiege_targets,
)

from fs_bot.commands.sa_entreat import (  # noqa: F401
    validate_entreat_region,
    entreat_replace_piece,
    entreat_replace_ally,
)

from fs_bot.commands.sa_devastate import (  # noqa: F401
    validate_devastate_region,
    devastate_region,
)

from fs_bot.commands.sa_trade import (  # noqa: F401
    trade,
)

from fs_bot.commands.sa_suborn import (  # noqa: F401
    validate_suborn_region,
    suborn,
)

from fs_bot.commands.sa_enlist import (  # noqa: F401
    validate_enlist_region,
    get_enlistable_german_pieces,
    validate_enlist_ariovistus_limit,
)

from fs_bot.commands.sa_rampage import (  # noqa: F401
    validate_rampage_region,
    validate_rampage_target,
    rampage,
)

from fs_bot.commands.sa_settle import (  # noqa: F401
    validate_settle_region,
    settle,
)

from fs_bot.commands.sa_intimidate import (  # noqa: F401
    validate_intimidate_region,
    intimidate,
)
