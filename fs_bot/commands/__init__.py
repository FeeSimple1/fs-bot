"""Commands module — Rally, Recruit, March, Raid, Seize implementations.

Sub-modules:
    common: Shared CommandError exception and helper functions.
    rally: Rally (Gallic/Germanic) and Recruit (Roman) commands.
    march: March (all factions) and Harassment.
    raid: Raid (Gallic/Germanic) command.
    seize: Seize (Roman) command.

Reference: §3.2.1, §3.2.2, §3.2.3, §3.3.1, §3.3.2, §3.3.3,
           §3.4.1, §3.4.2, §3.4.3, §3.4.5,
           §6.2.1, §6.2.2, §6.2.3,
           A3.2.1, A3.2.2, A3.2.3, A3.3.1, A3.3.2, A3.3.3,
           A3.4.1, A3.4.2, A3.4.3, A3.4.5
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
