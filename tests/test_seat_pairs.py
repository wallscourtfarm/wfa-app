"""Run with plain python:  python3 tests/test_seat_pairs.py
Proves seat_pairs.plan(): never seats two children in one seat, matches a brute-force best answer on
small rooms, puts partners side by side when the room allows, keeps children in their own seat where
it can, and returns cards in snake hand-out order. Fake data only."""
import os, sys, itertools, random
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import seat_pairs as sp


def cost(res, home):
    c = 0
    for card in res['cards']:
        ss = list(card['seats'].values())
        if len(ss) == 2:
            c += sp._gap(*ss)
        for x, s in card['seats'].items():
            c += 0 if home.get(x) == s else sp.MOVE + sp._dist(home[x], s)
    return c


def brute(seats, home, pairs, singles):
    kids = [x for p in pairs for x in p] + list(singles)
    best = None
    for perm in itertools.permutations(seats, len(kids)):
        w = dict(zip(kids, perm))
        c = sum(sp._gap(w[a], w[b]) for a, b in pairs)
        c += sum(0 if home[x] == w[x] else sp.MOVE + sp._dist(home[x], w[x]) for x in kids)
        best = c if best is None or c < best else best
    return best


rng = random.Random(7)
small = [(1, 0), (1, 1), (1, 2), (1, 3), (2, 0), (2, 1), (2, 3)]
for t in range(20):
    kids = list(range(rng.choice([5, 6, 7])))
    home = dict(zip(kids, rng.sample(small, len(kids))))
    rng.shuffle(kids)
    pairs = [(kids[i], kids[i + 1]) for i in range(0, len(kids) - 1, 2)]
    singles = kids[len(pairs) * 2:]
    r = sp.plan(small, home, pairs, singles)
    assert abs(cost(r, home) - brute(small, home, pairs, singles)) < 1e-6, t
print('matches brute force on small rooms OK')

# Partners already side by side both stay put
r = sp.plan([(0, 0), (0, 1), (0, 2), (0, 3)], {'a': (0, 0), 'b': (0, 1), 'c': (0, 2), 'd': (0, 3)},
            [('a', 'b'), ('c', 'd')], [])
assert r['stayed'] == 4 and r['side_by_side'] == 2
# Swapped partners: one of each pair stays, partner moves beside them
r = sp.plan([(0, 0), (0, 1), (0, 2), (0, 3)], {'a': (0, 0), 'b': (0, 1), 'c': (0, 2), 'd': (0, 3)},
            [('a', 'c'), ('b', 'd')], [])
assert r['stayed'] == 2 and r['side_by_side'] == 2, r
# an aisle (missing column) is not "side by side"
assert sp._gap((0, 3), (0, 5)) > 0 and sp._gap((0, 3), (0, 4)) == 0
# too many children
assert sp.plan([(0, 0)], {}, [('a', 'b')], []) is None
print('small cases OK')

# A full class: 30 seats with aisles, 14 pairs + 1 on their own
cols = {1: [0, 1, 2, 3, 5, 6, 7, 8], 2: [0, 1, 2, 3, 5, 6, 7, 8], 3: [0, 1, 2, 3, 5, 6, 7], 4: [0, 1, 2, 5, 6, 7, 8]}
seats = [(r, c) for r, cs in cols.items() for c in cs]
kids = list(range(29))
home = dict(zip(kids, rng.sample(seats, 29)))
rng.shuffle(kids)
pairs = [(kids[i], kids[i + 1]) for i in range(0, 28, 2)]
r = sp.plan(seats, home, pairs, [kids[28]])
taken = [s for c in r['cards'] for s in c['seats'].values()]
assert len(taken) == 29 and len(set(taken)) == 29, 'two children in one seat'
assert r['side_by_side'] >= 13 and r['stayed'] >= 13, r['stayed']
snake = sp.snake_index(seats)
at = [snake[c['seats'][c['front']]] for c in r['cards']]
assert at == sorted(at), 'cards not in hand-out order'
assert all(snake[c['seats'][c['front']]] < snake[c['seats'][c['back']]] for c in r['cards'] if c['back'])
assert sp.plan(seats, home, pairs, [kids[28]]) == r, 'not repeatable'
print(f"full class OK: {r['stayed']}/29 stay, {r['side_by_side']}/14 side by side")
print('ALL OK')
