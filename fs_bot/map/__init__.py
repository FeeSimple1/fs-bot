"""Map module — Region, tribe, and adjacency data for Falling Sky."""

from fs_bot.map.map_data import (
    get_region_data,
    get_tribe_data,
    get_adjacent,
    get_adjacent_with_type,
    is_adjacent,
    get_adjacency_type,
    get_region_for_tribe,
    get_tribes_in_region,
    get_playable_regions,
    get_control_value,
    get_tribe_city,
    get_tribe_restriction,
    is_city_tribe,
    get_region_group,
    ALL_REGION_DATA,
)

__all__ = [
    "get_region_data",
    "get_tribe_data",
    "get_adjacent",
    "get_adjacent_with_type",
    "is_adjacent",
    "get_adjacency_type",
    "get_region_for_tribe",
    "get_tribes_in_region",
    "get_playable_regions",
    "get_control_value",
    "get_tribe_city",
    "get_tribe_restriction",
    "is_city_tribe",
    "get_region_group",
    "ALL_REGION_DATA",
]
