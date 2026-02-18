"""Common definitions shared across command modules.

Provides the base CommandError exception and shared helper functions
used by rally, march, raid, and seize modules.
"""

from fs_bot.rules_consts import MARKER_DEVASTATED, MARKER_INTIMIDATED


class CommandError(Exception):
    """Raised when a command violates game rules."""
    pass


def _is_devastated(state, region):
    """Check if a region has the Devastated marker."""
    markers = state.get("markers", {}).get(region, {})
    return MARKER_DEVASTATED in markers


def _is_intimidated(state, region):
    """Check if a region has the Intimidated marker (Ariovistus only)."""
    markers = state.get("markers", {}).get(region, {})
    return MARKER_INTIMIDATED in markers
