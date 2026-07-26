"""Value filtering helpers for MQ2200MH sensors."""


def despiked_value(buffer, group_size):
    """Pick a de-spiked value from a list of recent readings.

    ``buffer`` is a list of (sequence, value) tuples in insertion order, where
    ``sequence`` is a monotonically increasing counter used to decide which
    value is "newest". ``value`` is the raw reading.

    Approach:
      1. Find the tightest contiguous window of ``group_size`` values in sorted
         order. This is the "reference cluster" of readings that agree with
         each other. A lone spike is far from every neighbour, so it can never
         be part of the tightest window.
      2. Widen that cluster's span by its largest internal gap to form an
         accepted band. This keeps values that continue the same gentle slope
         (slow drift, e.g. SOC or a rising energy counter) while still
         excluding a far-away spike.
      3. From all values inside the band, return the newest (highest sequence).

    Examples (group_size=3):
      [20, 21, 22, 5000, 23] -> 23   (5000 rejected, newest survivor is 23)
      [10, 20, 30, 40, 50]   -> 50   (no spike, steady climb, newest is 50)
      [22, 5000, 23, 24, 5000] -> 24 (two spikes rejected)

    If fewer than ``group_size`` values are available, returns None (caller
    should fall back to the last known / restored value).
    """
    if len(buffer) < group_size:
        return None

    ordered = sorted(buffer, key=lambda item: item[1])
    values = [v for _, v in ordered]

    # 1. Tightest contiguous window of group_size values. On ties (equal
    #    spread) prefer the window containing the newest readings, so that
    #    during slow drift the accepted band tracks the current level rather
    #    than lagging at the oldest end.
    best_i = 0
    best_key = None  # (spread, -newest_seq_in_window): smaller is better
    for i in range(len(ordered) - group_size + 1):
        window = ordered[i:i + group_size]
        spread = window[-1][1] - window[0][1]
        newest_seq = max(seq for seq, _ in window)
        key = (spread, -newest_seq)
        if best_key is None or key < best_key:
            best_key = key
            best_i = i

    cluster = values[best_i:best_i + group_size]

    # 2. Accepted band: cluster span widened by its largest internal gap.
    inner_gaps = [cluster[j + 1] - cluster[j] for j in range(len(cluster) - 1)]
    tolerance = max(inner_gaps) if inner_gaps else 0
    lo = cluster[0] - tolerance
    hi = cluster[-1] + tolerance

    # 3. Newest survivor within the accepted band.
    survivors = [(seq, val) for seq, val in buffer if lo <= val <= hi]
    if not survivors:
        return None
    return max(survivors, key=lambda item: item[0])[1]
