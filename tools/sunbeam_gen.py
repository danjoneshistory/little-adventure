"""Make a grid for the `sunbeam` game with exactly one solution.

Usage: python3 tools/sunbeam_gen.py WORD SEED   (try a few seeds; it keeps the grid with the most stones)
In the printed grid, / is an "f" stone and \\ is a "b" stone in index.html rows; > marks the start row.

Grid R x C. The beam enters from the left edge at row R0 heading east.
Cells: '.' water, '#' rock (stops beam), 'm' rotatable stone ('/' or '\\').
Letter pads sit on water cells; the beam passes through and lights them.
Win: beam exits at the dock AND the letters it lit (first visits, in order) spell WORD.
"""
import random, itertools, sys

R, C = 7, 6
WORD = sys.argv[1] if len(sys.argv) > 1 else "ADVENTURE"
DECOYS = "LS"
DIRS = {"E": (0, 1), "W": (0, -1), "N": (-1, 0), "S": (1, 0)}
SLASH = {"E": "N", "N": "E", "W": "S", "S": "W"}
BACK = {"E": "S", "S": "E", "W": "N", "N": "W"}


def trace(stones, rocks, config, r0):
    r, c, d = r0, 0, "E"
    cells = []
    for _ in range(400):
        if not (0 <= r < R and 0 <= c < C):
            return cells, (r, c)  # exited: position just outside
        if (r, c) in rocks:
            return cells, None
        cells.append((r, c))
        if (r, c) in stones:
            d = (SLASH if config[stones.index((r, c))] == 0 else BACK)[d]
        dr, dc = DIRS[d]
        r, c = r + dr, c + dc
    return cells, None


def lit(cells, pads):
    seen, out = set(), []
    for cell in cells:
        if cell in pads and cell not in seen:
            seen.add(cell); out.append(pads[cell])
    return "".join(out)


TURN = {("E","N"):0,("N","E"):0,("W","S"):0,("S","W"):0,("E","S"):1,("S","E"):1,("W","N"):1,("N","W"):1}
LEFTRIGHT = {"E":"NS","W":"NS","N":"EW","S":"EW"}

def walk(rng):
    r0 = rng.randrange(1, R-1)
    r, c, d = r0, 0, "E"
    seen, stones, config, cells = set(), [], [], []
    while 0 <= r < R and 0 <= c < C:
        if (r, c) in seen: return None
        seen.add((r, c)); cells.append((r, c))
        if rng.random() < 0.42 and len(cells) > 1 or (len(cells) == 1 and rng.random() < .3):
            nd = rng.choice(LEFTRIGHT[d])
            stones.append((r, c)); config.append(TURN[(d, nd)]); d = nd
        dr, dc = DIRS[d]; r, c = r + dr, c + dc
    if not (c == C or r == R): return None
    return r0, stones, config, cells, (r, c)

def attempt(rng):
    w = walk(rng)
    if not w: return None
    r0, stones, config, cells, ex = w
    if not (7 <= len(stones) <= 11): return None
    water = [x for x in cells if x not in stones]
    if len(water) < len(WORD): return None
    idx = sorted(rng.sample(range(len(water)), len(WORD)))
    pads = {water[i]: WORD[k] for k, i in enumerate(idx)}
    off = [(a, b) for a in range(R) for b in range(C) if (a, b) not in cells]
    if len(off) < 5: return None
    picks = rng.sample(off, 5)
    rocks = set(picks[:3])
    for ch, cell in zip(DECOYS, picks[3:]): pads[cell] = ch
    wins = hits = 0
    for cfg in itertools.product((0, 1), repeat=len(stones)):
        cs, e2 = trace(stones, rocks, cfg, r0)
        if e2 == ex:
            hits += 1
            if lit(cs, pads) == WORD:
                wins += 1
                if wins > 1: return None
    if wins != 1 or hits < 4: return None
    return dict(r0=r0, stones=stones, rocks=rocks, config=config, pads=pads, exit=ex, pathlen=len(cells), dock_hits=hits)

rng = random.Random(int(sys.argv[2]))
best = None
for t in range(200000):
    a = attempt(rng)
    if a and (best is None or (len(a["stones"]), a["pathlen"]) > (len(best["stones"]), best["pathlen"])):
        best = a
print(best)
g = [["." for _ in range(C)] for _ in range(R)]
for (r, c) in best["rocks"]: g[r][c] = "#"
for (r, c), ch in best["pads"].items(): g[r][c] = ch
for k, (r, c) in enumerate(best["stones"]): g[r][c] = "/" if best["config"][k] == 0 else "\\"
for r, row in enumerate(g): print(("> " if r == best["r0"] else "  ") + " ".join(row))
