"""Commands module — Rally, Recruit, Raid, Seize, and other command implementations.

Sub-modules:
    rally: Rally (Gallic/Germanic) and Recruit (Roman) commands.
    raid: Raid (Gallic/Germanic) command.
    seize: Seize (Roman) command.

Reference: §3.2.1, §3.2.3, §3.3.1, §3.3.3, §3.4.1, §3.4.3,
           §6.2.1, §6.2.3, A3.2.1, A3.2.3, A3.3.1, A3.3.3, A3.4.3
"""

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
