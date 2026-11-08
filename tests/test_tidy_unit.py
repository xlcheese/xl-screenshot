import helpers  # noqa: F401  (paths, a temporary home folder, English)
import sys, math, random
import gi; gi.require_version("Gtk", "3.0"); gi.require_version("Gdk", "3.0"); gi.require_version("GdkPixbuf", "2.0")
gi.require_version("Pango", "1.0"); gi.require_version("PangoCairo", "1.0")
from xlannotate.tidy import recognize
from xlannotate.shapes import smooth_points

def wobble(pts, amp, seed):
    rnd = random.Random(seed)
    # low-frequency hand wobble + small jitter, sampled like mouse motion
    phase = rnd.uniform(0, 6.28)
    out = []
    for i, (x, y) in enumerate(pts):
        drift = amp * math.sin(i / 9.0 + phase)
        out.append((x + drift * 0.6 + rnd.uniform(-amp, amp) * 0.4, y + drift + rnd.uniform(-amp, amp) * 0.4))
    return smooth_points(out)
def line(x1, y1, x2, y2, n=60): return [(x1 + (x2 - x1) * t / n, y1 + (y2 - y1) * t / n) for t in range(n + 1)]
def ellipse(cx, cy, rx, ry, n=90, start=0.3, overshoot=0.15, gap=0.0):
    return [(cx + rx * math.cos(start + a), cy + ry * math.sin(start + a))
            for a in [2 * math.pi * (1 + overshoot - gap) * i / n for i in range(n + 1)]]
def rect(x, y, w, h, n=25, overshoot=0.08):
    corners = [(x, y), (x + w, y), (x + w, y + h), (x, y + h), (x, y)]
    pts = []
    for a, b in zip(corners, corners[1:]): pts += line(*a, *b, n)[:-1]
    pts += line(x, y, x + w * overshoot, y, 5)
    return pts
def arrow(x1, y1, x2, y2, hook=25, side=1):
    shaft = line(x1, y1, x2, y2, 60)
    ang = math.atan2(y2 - y1, x2 - x1) + math.pi - side * math.radians(30)
    return shaft + line(x2, y2, x2 + hook * math.cos(ang), y2 + hook * math.sin(ang), 10)[1:]

cases = []
for seed in range(12):
    amp = 1.5 + (seed % 4)
    cases += [
        ("line", wobble(line(20, 50, 300, 90), amp, seed)),
        ("line", wobble(line(50, 20, 60, 260), amp, seed + 100)),
        ("arrow", wobble(arrow(30, 300, 280, 120, hook=22 + seed, side=1 if seed % 2 else -1), amp * 0.7, seed + 200)),
        ("ellipse", wobble(ellipse(200, 200, 120, 70, overshoot=0.05 + 0.02 * (seed % 5)), amp, seed + 300)),
        ("ellipse", wobble(ellipse(200, 200, 60, 60, gap=0.06), amp, seed + 400)),
        ("rectangle", wobble(rect(50, 50, 220, 120), amp, seed + 500)),
        ("rectangle", wobble(rect(80, 40, 90, 150, overshoot=0.02), amp, seed + 600)),
        (None, wobble([(20 + i * 4, 100 + 40 * math.sin(i / 3)) for i in range(70)], amp, seed + 700)),   # wavy line
        (None, wobble(line(20, 200, 120, 260, 30) + line(120, 260, 300, 40, 50)[1:], amp, seed + 800)),   # check mark
        (None, wobble(ellipse(200, 200, 100, 60, overshoot=-0.35), amp, seed + 900)),                     # open arc (a "C")
        (None, wobble([(100 + 60 * math.cos(a) * a / 12, 100 + 60 * math.sin(a) * a / 12) for a in [i * 0.15 for i in range(90)]], amp, seed + 1000)),  # spiral
        (None, wobble(line(20, 20, 26, 28, 8), 0.5, seed + 1100)),                                           # tiny
    ]
ok = 0
bad = {}
for want, pts in cases:
    got = recognize(pts)
    got_kind = got[0] if got else None
    if got_kind == want:
        ok += 1
    else:
        bad.setdefault((want, got_kind), 0); bad[(want, got_kind)] += 1
print(f"recognised correctly: {ok}/{len(cases)}")
for (want, got), n in sorted(bad.items(), key=str):
    print(f"  wanted {want!s:10} got {got!s:10} x{n}")

import xlannotate.tidy as T
print("\n--- missed shapes:")
for want, pts in cases:
    got = recognize(pts)
    if want and (not got or got[0] != want):
        xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
        box = (min(xs), min(ys), max(xs), max(ys)); w, h = box[2]-box[0], box[3]-box[1]; size = max(w, h)
        gap = math.hypot(pts[-1][0]-pts[0][0], pts[-1][1]-pts[0][1])
        x0, y0, x1, y1 = box; cx, cy, rx, ry = x0+w/2, y0+h/2, w/2, h/2
        e = sum(abs(math.hypot((x-cx)/rx, (y-cy)/ry)-1) for x, y in pts)/len(pts)
        r = sum(min(abs(x-x0), abs(x-x1), abs(y-y0), abs(y-y1)) for x, y in pts)/len(pts)/(min(w, h)/2)
        if want == "arrow":
            s = pts[0]; k = max(range(len(pts)), key=lambda i: math.hypot(pts[i][0]-s[0], pts[i][1]-s[1]))
            print(f"  arrow: k={k}/{len(pts)-1} straight={T._is_straight(pts[:k+1], s, pts[k])} hook={T._path_length(pts[k:]):.0f}")
        else:
            print(f"  {want}: gap/size={gap/size:.2f} ellipse_err={e:.3f} rect_err={r:.3f}")

print(("PASS " if ok == len(cases) else "FAIL ") + f"rough lines, arrows, ellipses and boxes are recognised ({ok}/{len(cases)})")
print("FAILURES:", "none" if ok == len(cases) else len(cases) - ok)
