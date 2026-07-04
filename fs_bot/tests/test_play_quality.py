"""Smoke tests for the play-quality telemetry instrument."""

from collections import defaultdict

import fs_bot.rules_consts as rc
from fs_bot.tools.play_quality import play_game, _new_scenario_stats


def test_play_quality_telemetry_smoke():
    """One game per family: stats populate, no-effect classification uses
    the SA-salvage rule (a German Settle riding an empty Rally is NOT a
    no-effect turn), and the Gallic War reaches its second half."""
    stats = defaultdict(_new_scenario_stats)
    play_game(rc.SCENARIO_PAX_GALLICA, 1, stats)
    # Seed 7 reaches the second half under the post-errata Arverni Phase
    # timing and the §8.8.1 Roman March-group/Scout-move behaviour.
    res = play_game(rc.SCENARIO_GALLIC_WAR, 7, stats)

    sc = stats[rc.SCENARIO_PAX_GALLICA]
    assert sc["games"] == 1
    assert sum(v for (f, c), v in sc["commands"].items()) > 0
    assert sc["wins"]

    gw = stats[rc.SCENARIO_GALLIC_WAR]
    assert gw["games"] == 1
    assert res["winter_count"] > 3          # the second half happened
    # The Germans' A8.7.4 Settle-on-empty-Rally turns are not counted as
    # no-effect (the classifier checks whether an SA salvaged the turn).
    assert gw["no_effect"].get((rc.GERMANS, "Rally"), 0) == 0
