"""Lay out a Strands board for the scavenger hunt.

Every letter is used exactly once, each word is a path of touching letters
(including diagonals), the spangram (first word) reaches from one edge to the
opposite edge, and no two paths cross diagonally.

The board is 8 rows tall; the number of columns comes from the letter count,
so the total letters must be a multiple of 8 (48 = 6 wide, 56 = 7 wide).

Usage:
  python3 tools/strands_gen.py SPANGRAM WORD WORD ... [--seed N]

Example:
  python3 tools/strands_gen.py SWEETHEART GUMMYBEARS LAFFYTAFFY ICECREAM FUDGE MILKCHOCOLATE --seed 11

It prints the board, then rows/words lines to paste into a place's game: { type: "strands", ... }.
It can take a minute or two. A different --seed gives a different board."""
import random, sys, json, time

ROWS, COLS = 8, 6   # COLS is set from the letter count in main()
N = ROWS * COLS

def nbrs(i):
    r, c = divmod(i, COLS)
    for dr in (-1, 0, 1):
        for dc in (-1, 0, 1):
            if dr or dc:
                rr, cc = r + dr, c + dc
                if 0 <= rr < ROWS and 0 <= cc < COLS:
                    yield rr * COLS + cc

def diag_key(a, b):
    """For a diagonal step, the crossing diagonal in the same 2x2 square."""
    ra, ca = divmod(a, COLS); rb, cb = divmod(b, COLS)
    if ra == rb or ca == cb: return None, None
    r0, c0 = min(ra, rb), min(ca, cb)
    sq = (r0, c0)
    kind = "\\" if (ra - rb) == (ca - cb) else "/"
    return sq, kind

def subset_sums(lengths):
    s = {0}
    for L in lengths: s |= {x + L for x in s}
    return s

def components(empty):
    seen, comps = set(), []
    for s in empty:
        if s in seen: continue
        stack, size = [s], 0; seen.add(s)
        while stack:
            x = stack.pop(); size += 1
            for y in nbrs(x):
                if y in empty and y not in seen: seen.add(y); stack.append(y)
        comps.append(size)
    return comps

def solve(spangram, words, rng, deadline):
    grid = [None] * N
    diags = {}  # (r0,c0) -> kind used

    def can_step(a, b):
        sq, kind = diag_key(a, b)
        return sq is None or diags.get(sq) in (None, kind)

    def place(path, word):
        for i, ch in zip(path, word): grid[i] = ch
        added = []
        for a, b in zip(path, path[1:]):
            sq, kind = diag_key(a, b)
            if sq is not None and sq not in diags: diags[sq] = kind; added.append(sq)
        return added

    def unplace(path, added):
        for i in path: grid[i] = None
        for sq in added: del diags[sq]

    def ok_regions(remaining):
        empty = {i for i in range(N) if grid[i] is None}
        sums = subset_sums(remaining)
        mn = min(remaining) if remaining else 0
        for size in components(empty):
            if size < mn or size not in sums: return False
        return True

    def walks(start, length, extra_ok=lambda p: True):
        """Random-order self-avoiding walks over empty cells."""
        path = [start]
        def rec():
            if time.time() > deadline: return
            if len(path) == length:
                if extra_ok(path): yield list(path)
                return
            nb = [y for y in nbrs(path[-1]) if grid[y] is None and y not in path and can_step(path[-1], y)]
            rng.shuffle(nb)
            for y in nb:
                path.append(y)
                yield from rec()
                path.pop()
        yield from rec()

    # 1) spangram: top->bottom or left->right
    vertical = rng.random() < 0.5
    if vertical:
        starts = list(range(COLS)); touches_end = lambda p: any(i // COLS == ROWS - 1 for i in p)
    else:
        starts = [r * COLS for r in range(ROWS)]; touches_end = lambda p: any(i % COLS == COLS - 1 for i in p)
    rng.shuffle(starts)
    for st in starts:
        tries = 0
        for p in walks(st, len(spangram), touches_end):
            tries += 1
            if tries > 400: break
            if rng.random() < 0.5: p = p[::-1]
            added = place(p, spangram)
            rest = [w for w in words]
            if ok_regions([len(w) for w in rest]):
                res = fill(rest, place, unplace, ok_regions, walks, grid, rng, deadline)
                if res is not None:
                    return grid, [(spangram, p, True)] + res
            unplace(p, added)
            if time.time() > deadline: return None
    return None

def fill(words, place, unplace, ok_regions, walks, grid, rng, deadline):
    if not words: return []
    first = next(i for i in range(N) if grid[i] is None)
    order = list(words); rng.shuffle(order)
    for w in order:
        rest = list(words); rest.remove(w)
        count = 0
        for p in walks(first, len(w)):
            count += 1
            if count > 3000 or time.time() > deadline: break
            for path in ((p, p[::-1]) if rng.random() < .5 else (p[::-1], p)):
                if path[0] != first and path[-1] != first: continue
                added = place(path, w)
                if ok_regions([len(x) for x in rest]):
                    res = fill(rest, place, unplace, ok_regions, walks, grid, rng, deadline)
                    if res is not None: return [(w, path, False)] + res
                unplace(path, added)
    return None

def straightness(found):
    """Penalise long straight runs so the board looks scrambled."""
    pen = 0
    for _, p, _ in found:
        for a, b, c in zip(p, p[1:], p[2:]):
            if b - a == c - b: pen += 1
    return pen

def main():
    global COLS, N
    args = sys.argv[1:]
    seed = None
    if "--seed" in args:
        k = args.index("--seed"); seed = int(args[k + 1]); del args[k:k + 2]
    if len(args) < 2: sys.exit(__doc__)
    span, words = args[0].upper(), [w.upper() for w in args[1:]]
    total = len(span) + sum(map(len, words))
    if total % ROWS:
        lo, hi = total - total % ROWS, total - total % ROWS + ROWS
        sys.exit(f"{total} letters. It needs a multiple of 8: take away {total - lo} or add {hi - total}.")
    COLS, N = total // ROWS, total
    print(f"{total} letters -> {ROWS} rows x {COLS} columns. Working on it...", file=sys.stderr)
    best = None
    base = seed if seed is not None else random.randrange(10**6)
    for t in range(20):
        rng = random.Random(base + t)
        r = solve(span, words, rng, time.time() + 3)
        if r:
            sc = straightness(r[1])
            if best is None or sc < best[0]: best = (sc, r)
    if not best: sys.exit("no layout found")
    grid, found = best[1]
    rows = ["".join(grid[r * COLS:(r + 1) * COLS]) for r in range(ROWS)]
    for row in rows: print(" ".join(row))
    print("\nPaste into the place's game: { type: \"strands\", theme: \"...\", hints: 3, ... }\n")
    print("            rows: [" + ",\n                   ".join(json.dumps(r) for r in rows) + "],")
    print("            words: [")
    lines = []
    for w, p, s in found:
        lines.append("              { word: %-16s path: [%s]%s }" % (json.dumps(w) + ",", ",".join(map(str, p)), ", spangram: true" if s else ""))
    print(",\n".join(lines))
    print("            ]")

main()
