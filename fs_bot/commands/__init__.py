"""Commands module — Rally, Recruit, March, and other command implementations.

Sub-modules:
    rally: Rally (Gallic/Germanic) and Recruit (Roman) commands.
    march: March (all factions) and Harassment.

Reference: §3.2.1, §3.2.2, §3.3.1, §3.3.2, §3.4.1, §3.4.2, §3.4.5,
           §6.2.1, §6.2.2, A3.2.1, A3.2.2, A3.3.1, A3.3.2, A3.4.2, A3.4.5
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
