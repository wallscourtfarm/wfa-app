"""Where spelling partners sit on Bee day (Thursday).

The teacher lays one double-sided card on every other seat; the two partners on a card sit side by
side. Given the room (every seat as (row, col), from the Seating Plan import in Class Manager), each
child's usual seat and the partner pairs, plan() picks two side-by-side seats for every pair (one
seat for a child with no partner) so that as many children as possible stay in their own seat and
the rest move as little as possible. Cards come back in the teacher's snake hand-out order: row 1
left to right, row 2 right to left, and so on.

Seats are side by side when they are in the same row and next-door columns (an aisle column with no
seat in it breaks the run). If the room has no side-by-side pair left, a pair is put one behind the
other, and only as a last resort further apart. Pure functions, no I/O; deterministic.
"""
import math
import random

MOVE = 10        # cost of a child leaving their own seat (plus the distance walked)
NO_HOME = 12     # a child the seating plan did not place
BEHIND = 40      # partners one in front of the other instead of side by side
APART = 100      # partners further apart than that (plus 5 per seat of distance)


def _dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def snake_index(seats):
    """{(row, col): position} in hand-out order."""
    rows = sorted({s[0] for s in seats})
    out, n = {}, 0
    for i, r in enumerate(rows):
        for s in sorted((s for s in seats if s[0] == r), key=lambda s: s[1], reverse=bool(i % 2)):
            out[s] = n
            n += 1
    return out


def _gap(s, t):
    if s[0] == t[0] and abs(s[1] - t[1]) == 1:
        return 0
    if s[1] == t[1] and abs(s[0] - t[0]) == 1:
        return BEHIND
    return APART + 5 * _dist(s, t)


def plan(seats, home, pairs, singles, restarts=40, seed=0):
    """seats: iterable of (row, col); home: {pupil_id: (row, col)}; pairs: [(a, b)]; singles: [a].
    Returns {'cards': [{'seats': {pupil_id: (row, col)}, 'front': id, 'back': id|None}], 'stayed': n,
    'side_by_side': n} with cards in hand-out order, or None if there are fewer seats than children."""
    seats = sorted({tuple(s) for s in seats})
    home = {k: tuple(v) for k, v in (home or {}).items()}
    groups = [tuple(p) for p in pairs] + [(a,) for a in singles]
    if sum(len(g) for g in groups) > len(seats):
        return None

    def move(x, s):
        h = home.get(x)
        if h is None:
            return NO_HOME
        return 0 if h == s else MOVE + _dist(h, s)

    # Every way of seating each group, with its cost: (cost, (seat for g[0], seat for g[1]?))
    side = [(s, t) for s in seats for t in seats if s != t and _gap(s, t) == 0]

    def options(g, free):
        if len(g) == 1:
            return [(move(g[0], s), (s,)) for s in free]
        cand = [(s, t) for s, t in side if s in free and t in free]
        if not cand:
            cand = [(s, t) for s in free for t in free if s != t]
        return [(_gap(s, t) + move(g[0], s) + move(g[1], t), (s, t)) for s, t in cand]

    def cost(g, spot):
        return (_gap(*spot) if len(g) == 2 else 0) + sum(move(x, s) for x, s in zip(g, spot))

    def total(assign):
        return sum(cost(groups[i], spot) for i, spot in assign.items())

    def place_greedy(order, assign, used):
        for i in order:
            opts = options(groups[i], [s for s in seats if s not in used])
            c, spot = min(opts)
            assign[i] = spot
            used.update(spot)

    def improve(assign):
        better = True
        while better:
            better = False
            used = {s for spot in assign.values() for s in spot}
            # 1. move a group to free seats
            for i in range(len(groups)):
                free = [s for s in seats if s not in used or s in assign[i]]
                c, spot = min(options(groups[i], free))
                if c < cost(groups[i], assign[i]) - 1e-9:
                    used.difference_update(assign[i])
                    assign[i] = spot
                    used.update(spot)
                    better = True
            # 2. swap the seats of two groups of the same size (pairs try both ways round)
            for i in range(len(groups)):
                for j in range(i + 1, len(groups)):
                    if len(groups[i]) != len(groups[j]):
                        continue
                    a, b = assign[i], assign[j]
                    now = cost(groups[i], a) + cost(groups[j], b)
                    c, na, nb = min((cost(groups[i], x) + cost(groups[j], y), x, y)
                                    for x in (b, b[::-1]) for y in (a, a[::-1]))
                    if c < now - 1e-9:
                        assign[i], assign[j] = na, nb
                        better = True
            # 3. put a pair on two seats others are using, and re-seat those others
            for i in range(len(groups)):
                if len(groups[i]) != 2:
                    continue
                before = total(assign)
                for spot in side:
                    hit = [j for j, sp in assign.items() if j != i and (spot[0] in sp or spot[1] in sp)]
                    if not hit or len(hit) > 2:
                        continue
                    trial = dict(assign)
                    trial[i] = spot
                    for j in hit:
                        del trial[j]
                    place_greedy(hit, trial, {x for sp in trial.values() for x in sp})
                    if total(trial) < before - 1e-9:
                        assign.clear()
                        assign.update(trial)
                        before = total(assign)
                        better = True
        return assign

    rng = random.Random(seed)
    best, best_cost = None, None
    for k in range(max(1, restarts)):
        order = list(range(len(groups)))
        if k:
            rng.shuffle(order)
        else:   # first try: pairs who already sit together, then everyone else
            order.sort(key=lambda i: (len(groups[i]) == 1,
                                      not (len(groups[i]) == 2 and all(x in home for x in groups[i])
                                           and _gap(home[groups[i][0]], home[groups[i][1]]) == 0)))
        assign = {}
        place_greedy(order, assign, set())
        improve(assign)
        c = total(assign)
        if best is None or c < best_cost - 1e-9:
            best, best_cost = dict(assign), c

    snake = snake_index(seats)
    cards = []
    for i, spot in best.items():
        g = groups[i]
        where = dict(zip(g, spot))
        front = min(g, key=lambda x: snake[where[x]])
        back = next((x for x in g if x != front), None)
        cards.append({'seats': where, 'front': front, 'back': back, '_at': snake[where[front]]})
    cards.sort(key=lambda c: c['_at'])
    for c in cards:
        del c['_at']
    stayed = sum(1 for c in cards for x, s in c['seats'].items() if home.get(x) == s)
    side_by_side = sum(1 for c in cards if c['back'] and _gap(*c['seats'].values()) == 0)
    return {'cards': cards, 'stayed': stayed, 'side_by_side': side_by_side}
