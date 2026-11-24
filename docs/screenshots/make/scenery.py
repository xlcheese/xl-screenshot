"""A mountain lake at sunrise, drawn with cairo (original artwork, no photos)."""
import math, random
import cairo

def _ridge(w, base, rough, seed, levels=9):
    rnd = random.Random(seed)
    n = 2 ** levels
    pts = [0.0] * (n + 1)
    pts[0], pts[n] = rnd.uniform(-1, 1), rnd.uniform(-1, 1)
    step, amp = n, 1.0
    while step > 1:
        half = step // 2
        for i in range(half, n, step):
            pts[i] = (pts[i - half] + pts[i + half]) / 2 + rnd.uniform(-amp, amp)
        step, amp = half, amp * rough
    return [(i * w / n, base - p) for i, p in enumerate(pts)]

def _layer(cr, w, h, pts, top, bottom):
    cr.move_to(0, h)
    for x, y in pts:
        cr.line_to(x, y)
    cr.line_to(w, h); cr.close_path()
    ys = [y for _, y in pts]
    g = cairo.LinearGradient(0, min(ys), 0, h)
    g.add_color_stop_rgb(0, *top); g.add_color_stop_rgb(1, *bottom)
    cr.set_source(g); cr.fill()

def _pine(cr, x, y, hgt, color):
    cr.set_source_rgb(*color)
    tiers = 5
    for i in range(tiers):
        t = i / tiers
        ty = y - hgt * (0.15 + 0.85 * t)
        wid = hgt * 0.32 * (1 - t * 0.8)
        cr.move_to(x - wid, ty + hgt * 0.28); cr.line_to(x, ty - hgt * 0.12); cr.line_to(x + wid, ty + hgt * 0.28)
        cr.close_path(); cr.fill()
    cr.rectangle(x - hgt * 0.025, y - hgt * 0.16, hgt * 0.05, hgt * 0.16); cr.fill()

def draw(w, h, with_cabin=True):
    """Returns (surface, points of interest)."""
    s = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
    cr = cairo.Context(s)
    horizon = h * 0.62
    # sky: deep blue to warm gold
    g = cairo.LinearGradient(0, 0, 0, horizon)
    g.add_color_stop_rgb(0.0, 0.16, 0.25, 0.48)
    g.add_color_stop_rgb(0.45, 0.62, 0.52, 0.66)
    g.add_color_stop_rgb(0.8, 0.98, 0.70, 0.52)
    g.add_color_stop_rgb(1.0, 1.0, 0.86, 0.62)
    cr.set_source(g); cr.rectangle(0, 0, w, horizon + 2); cr.fill()
    sun = (w * 0.68, horizon - h * 0.355)
    glow = cairo.RadialGradient(*sun, 0, *sun, h * 0.55)
    glow.add_color_stop_rgba(0, 1, 0.98, 0.88, 1.0); glow.add_color_stop_rgba(0.07, 1, 0.92, 0.7, 0.8)
    glow.add_color_stop_rgba(0.4, 1, 0.75, 0.5, 0.32); glow.add_color_stop_rgba(1, 1, 0.7, 0.5, 0)
    cr.set_source(glow); cr.rectangle(0, 0, w, horizon); cr.fill()
    cr.set_source_rgba(1, 0.98, 0.9, 1); cr.arc(*sun, h * 0.035, 0, 2 * math.pi); cr.fill()
    # soft clouds
    rnd = random.Random(7)
    for _ in range(7):
        cx, cy = rnd.uniform(0, w), rnd.uniform(h * 0.05, h * 0.22)
        for k in range(4):
            rx = rnd.uniform(w * 0.03, w * 0.07)
            cg = cairo.RadialGradient(cx + k * rx * 0.6, cy, 0, cx + k * rx * 0.6, cy, rx)
            cg.add_color_stop_rgba(0, 1, 0.86, 0.82, 0.10); cg.add_color_stop_rgba(1, 1, 0.88, 0.85, 0)
            cr.set_source(cg); cr.save(); cr.translate(0, cy); cr.scale(1, 0.22); cr.translate(0, -cy)
            cr.arc(cx + k * rx * 0.6, cy, rx, 0, 2 * math.pi); cr.fill(); cr.restore()
    # mountain ranges, far (hazy) to near (dark)
    ranges = [
        (horizon - h * 0.30, 0.55, 3, h * 0.16, (0.60, 0.56, 0.72), (0.86, 0.72, 0.70)),
        (horizon - h * 0.20, 0.52, 11, h * 0.14, (0.42, 0.42, 0.62), (0.70, 0.60, 0.66)),
        (horizon - h * 0.10, 0.50, 5, h * 0.10, (0.26, 0.32, 0.48), (0.46, 0.46, 0.56)),
        (horizon - h * 0.02, 0.48, 21, h * 0.05, (0.14, 0.24, 0.30), (0.20, 0.30, 0.36)),
    ]
    summit = None
    for i, (base, rough, seed, amp, top, bottom) in enumerate(ranges):
        pts = [(x, base + (y - base) * amp) for x, y in _ridge(w, base, rough, seed)]
        if i == 1:
            # a clear peak for the note to point at
            peak_x = w * 0.3
            pts = [(x, y - h * 0.13 * math.exp(-((x - peak_x) / (w * 0.09)) ** 2)) for x, y in pts]
            summit = min(((x, y) for x, y in pts if abs(x - peak_x) < w * 0.05), key=lambda p: p[1])
            ridge2 = pts
        # snow caps on the tallest range
        _layer(cr, w, horizon, pts, top, bottom)
        if i == 1:
            cr.save()
            cr.move_to(0, horizon)
            for x, y in pts:
                cr.line_to(x, y)
            cr.line_to(w, horizon); cr.close_path(); cr.clip()
            sg = cairo.LinearGradient(0, summit[1], 0, summit[1] + h * 0.09)
            sg.add_color_stop_rgba(0, 1, 0.93, 0.88, 0.85); sg.add_color_stop_rgba(1, 1, 0.93, 0.88, 0)
            cr.set_source(sg); cr.rectangle(0, 0, w, horizon); cr.fill(); cr.restore()
        # mist between ranges
        mg = cairo.LinearGradient(0, base - h * 0.02, 0, horizon)
        mg.add_color_stop_rgba(0, 1, 0.85, 0.75, 0); mg.add_color_stop_rgba(1, 1, 0.85, 0.75, 0.18 - i * 0.03)
        cr.set_source(mg); cr.rectangle(0, base - h * 0.05, w, horizon - base + h * 0.05); cr.fill()
    scene = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, int(horizon) + 1)
    sc = cairo.Context(scene); sc.set_source_surface(s, 0, 0); sc.paint()
    # the lake: the scene reflected, darkened, with ripples
    cr.save(); cr.rectangle(0, horizon, w, h - horizon); cr.clip()
    cr.translate(0, 2 * horizon); cr.scale(1, -1)
    cr.set_source_surface(scene, 0, 0); cr.paint_with_alpha(0.75)
    cr.restore()
    lg = cairo.LinearGradient(0, horizon, 0, h)
    lg.add_color_stop_rgba(0, 0.10, 0.18, 0.30, 0.25); lg.add_color_stop_rgba(1, 0.04, 0.08, 0.16, 0.85)
    cr.set_source(lg); cr.rectangle(0, horizon, w, h - horizon); cr.fill()
    rnd = random.Random(3)
    for _ in range(260):
        y = horizon + (rnd.random() ** 1.6) * (h - horizon)
        x = rnd.uniform(0, w); ln = rnd.uniform(10, 60) * (1 + (y - horizon) / (h - horizon) * 2)
        near_sun = math.exp(-((x - sun[0]) / (w * 0.08)) ** 2)
        cr.set_source_rgba(1, 0.85 + 0.1 * near_sun, 0.7, 0.10 + 0.35 * near_sun)
        cr.set_line_width(1.2 + (y - horizon) / (h - horizon) * 2.5)
        cr.move_to(x - ln / 2, y); cr.line_to(x + ln / 2, y); cr.stroke()
    # near shore, left, with pines and the cabin
    shore = [(0, h * 0.71), (w * 0.09, h * 0.70), (w * 0.19, h * 0.715), (w * 0.26, h * 0.75),
             (w * 0.31, h * 0.83), (w * 0.335, h), (0, h)]
    cr.move_to(*shore[0])
    for p in shore[1:]:
        cr.line_to(*p)
    cr.close_path(); cr.set_source_rgb(0.07, 0.13, 0.12); cr.fill()
    cabin = (w * 0.165, h * 0.712)
    if with_cabin:
        cx, cy = cabin; cw, ch = w * 0.04, h * 0.035
        cr.set_source_rgb(0.30, 0.19, 0.13); cr.rectangle(cx - cw / 2, cy - ch, cw, ch); cr.fill()
        cr.set_source_rgb(0.16, 0.10, 0.08)
        cr.move_to(cx - cw * 0.62, cy - ch); cr.line_to(cx, cy - ch * 1.9); cr.line_to(cx + cw * 0.62, cy - ch); cr.close_path(); cr.fill()
        cr.rectangle(cx + cw * 0.18, cy - ch * 1.75, cw * 0.12, ch * 0.5); cr.fill()
        lw = cairo.RadialGradient(cx - cw * 0.15, cy - ch * 0.55, 0, cx - cw * 0.15, cy - ch * 0.55, cw * 0.6)
        lw.add_color_stop_rgba(0, 1, 0.8, 0.4, 0.5); lw.add_color_stop_rgba(1, 1, 0.8, 0.4, 0)
        cr.set_source(lw); cr.arc(cx - cw * 0.15, cy - ch * 0.55, cw * 0.6, 0, 2 * math.pi); cr.fill()
        cr.set_source_rgb(1, 0.82, 0.45); cr.rectangle(cx - cw * 0.28, cy - ch * 0.7, cw * 0.22, ch * 0.3); cr.fill()
        cr.rectangle(cx + cw * 0.08, cy - ch * 0.7, cw * 0.22, ch * 0.3); cr.fill()
        cr.set_source_rgb(0.12, 0.08, 0.06); cr.rectangle(cx - cw * 0.02, cy - ch * 0.55, cw * 0.06, ch * 0.55); cr.fill()
        # smoke
        cr.set_line_width(h * 0.004); cr.set_source_rgba(0.9, 0.85, 0.85, 0.35)
        sx0, sy0 = cx + cw * 0.24, cy - ch * 1.8
        cr.move_to(sx0, sy0); cr.curve_to(sx0 - 10, sy0 - 30, sx0 + 25, sy0 - 50, sx0 + 5, sy0 - 90); cr.stroke()
    rnd = random.Random(11)
    for x, y, hg in [(w * 0.015, h * 0.715, h * 0.15), (w * 0.045, h * 0.71, h * 0.11), (w * 0.08, h * 0.705, h * 0.17),
                     (w * 0.11, h * 0.705, h * 0.10), (w * 0.215, h * 0.73, h * 0.12), (w * 0.245, h * 0.75, h * 0.18),
                     (w * 0.275, h * 0.78, h * 0.14), (w * 0.30, h * 0.83, h * 0.21)]:
        _pine(cr, x, y + hg * 0.02, hg, (0.05, 0.11, 0.10))
    # far shore pines, right
    for i in range(40):
        x = w * 0.62 + i * w * 0.0095 + rnd.uniform(-3, 3)
        _pine(cr, x, horizon + 2, rnd.uniform(h * 0.025, h * 0.05), (0.11, 0.18, 0.20))
    cr.set_source_rgb(0.11, 0.18, 0.20); cr.rectangle(w * 0.61, horizon - 1, w * 0.39, 4); cr.fill()
    # birds
    cr.set_source_rgba(0.15, 0.13, 0.2, 0.8); cr.set_line_width(h * 0.0025)
    for bx, by, bs in [(0.50, 0.17, 1.0), (0.53, 0.155, 0.8), (0.555, 0.18, 0.7)]:
        x, y, s_ = bx * w, by * h, bs * w * 0.012
        cr.move_to(x - s_, y - s_ * 0.3); cr.curve_to(x - s_ * 0.5, y - s_ * 0.6, x - s_ * 0.2, y - s_ * 0.3, x, y)
        cr.curve_to(x + s_ * 0.2, y - s_ * 0.3, x + s_ * 0.5, y - s_ * 0.6, x + s_, y - s_ * 0.3); cr.stroke()
    return s, {"summit": summit, "cabin": cabin, "sun": sun, "horizon": horizon, "ridge": ridge2}

if __name__ == "__main__":
    s, poi = draw(1840, 1100)
    s.write_to_png("scenery.png"); print(poi["summit"], poi["cabin"])
