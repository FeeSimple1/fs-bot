"""Track pieces that already marched into a later origin (§§3.2.2, 3.3.2)."""

from collections import Counter

from fs_bot import rules_consts as rc
from fs_bot.engine.action_windows import clear_cohorts, get_cohorts, set_cohorts


class MarchArrivals:
    def __init__(self, state, faction, origins):
        self.state = state
        self.faction = faction
        self.remaining = Counter(origins)
        self.keys = {}

    def begin_group(self, origin):
        self.remaining[origin] -= 1

    def needs(self, region):
        return self.remaining[region] > 0

    def in_region(self, region):
        excluded = Counter()
        for owner, key in self.keys.items():
            for row in get_cohorts(self.state, key):
                if row['region'] == region and row['count']:
                    excluded[owner, row['piece_type'], row.get('piece_state')] += row['count']
        return excluded

    def record(self, owner, rows):
        key = self.keys.setdefault(owner, f'march.arrivals.{self.faction}.{owner}')
        parked = [dict(row, id='marched_pieces', label='Already marched') for row in rows]
        self._set(owner, [*get_cohorts(self.state, key), *parked])

    def record_group(self, region, group):
        from fs_bot.engine.march_timing import physical_members
        by_owner = {}
        for owner, row in physical_members(self.state, self.faction, region, group):
            by_owner.setdefault(owner, []).append(row)
        for owner, rows in by_owner.items():
            self.record(owner, rows)

    def flip_origin(self, origin):
        """Advance the same visibility changes as the board's origin procedure."""
        targets = {rc.REVEALED: rc.HIDDEN, rc.SCOUTED: rc.REVEALED}
        for owner, key in self.keys.items():
            rows = get_cohorts(self.state, key)
            for row in rows:
                if row['region'] == origin and row.get('piece_state') in targets:
                    row['piece_state'] = targets[row['piece_state']]
            self._set(owner, rows)

    def finish_origin(self, origin):
        if self.needs(origin):
            return
        for owner, key in self.keys.items():
            self._set(owner, [row for row in get_cohorts(self.state, key)
                              if row['region'] != origin])

    def clear(self):
        for key in self.keys.values():
            clear_cohorts(self.state, key)

    def _set(self, owner, rows):
        merged = {}
        for row in rows:
            if row['count']:
                cell = (row['region'], row['piece_type'], row.get('piece_state'),
                        row.get('loan_kind'))
                if cell in merged:
                    merged[cell]['count'] += row['count']
                else:
                    merged[cell] = row
        key = self.keys[owner]
        if merged:
            set_cohorts(self.state, key, owner, list(merged.values()))
        else:
            clear_cohorts(self.state, key)


def acting_counts(state, excluded):
    """Count parked physical arrivals as their types in the acting force."""
    from fs_bot.engine.diviciacus import KEY
    div = state.get(KEY, {})
    counts = Counter()
    for (owner, piece, _), count in (excluded or {}).items():
        if owner == div.get('lender') and piece == div.get('physical_type'):
            piece = div['piece_type']
        counts[piece] += count
    return counts


def enlisted_arrivals(excluded):
    return sum(n for (owner, piece, _), n in (excluded or {}).items()
               if owner == rc.GERMANS and piece == rc.WARBAND)
