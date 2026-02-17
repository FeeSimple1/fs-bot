"""Commands module — Rally, Recruit, and other command implementations.

Sub-modules:
    rally: Rally (Gallic/Germanic) and Recruit (Roman) commands.

Reference: §3.2.1, §3.3.1, §3.4.1, §6.2.1, A3.2.1, A3.3.1, A3.4.1
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
