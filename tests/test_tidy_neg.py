import helpers  # paths, a temporary home folder, English
import sys, math
# borrow the stroke-drawing helpers (line, wobble, recognize...) from the top of test_tidy_unit.py
import os
exec(open(os.path.join(helpers.TESTS, "test_tidy_unit.py")).read().split("cases = []")[0])
def poly(pts, n=25):
    out = []
    for a, b in zip(pts, pts[1:]): out += line(*a, *b, n)[:-1]
    return out + [pts[-1]]
negs = {
    "triangle": lambda: poly([(150, 40), (260, 230), (40, 230), (150, 40), (170, 75)]),
    "star": lambda: poly([(150 + 110 * math.cos(math.radians(-90 + 144 * i)), 150 + 110 * math.sin(math.radians(-90 + 144 * i))) for i in range(6)]),
    "squiggle underline": lambda: [(20 + i * 3, 200 + 6 * math.sin(i / 1.3)) for i in range(100)],
    "figure 8": lambda: [(150 + 80 * math.sin(a), 150 + 110 * math.sin(a) * math.cos(a)) for a in [i * 0.07 for i in range(92)]],
    "S curve": lambda: [(150 + 70 * math.sin(a), 40 + a * 40) for a in [i * 0.08 for i in range(80)]],
    "scribble": lambda: [(150 + 80 * math.cos(a * 3.1) * math.sin(a), 150 + 60 * math.sin(a * 2.3)) for a in [i * 0.05 for i in range(120)]],
    "zigzag": lambda: poly([(20 + 40 * i, 100 + (40 if i % 2 else 0)) for i in range(8)]),
}
wrong = 0; total = 0
for name, f in negs.items():
    results = []
    for seed in range(8):
        got = recognize(wobble(f(), 1.5 + seed % 3, seed))
        results.append(got[0] if got else None)
        total += 1
    bad = [r for r in results if r is not None]
    wrong += len(bad)
    print(f"  {name:20} → {'left alone' if not bad else 'tidied as ' + ', '.join(sorted(set(bad))) + f' ({len(bad)}/8)'}")
print(f"left alone correctly: {total - wrong}/{total}")
print(("PASS " if wrong == 0 else "FAIL ") + "rough shapes that should stay freehand are left alone")
print("FAILURES:", "none" if wrong == 0 else wrong)
