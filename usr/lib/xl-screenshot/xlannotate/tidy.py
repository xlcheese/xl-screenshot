"""Tidy-up for freehand drawing: is this rough stroke really a line, an
arrow, an ellipse or a rectangle? (Like Preview's Sketch tool.)

recognize(points) looks only at the shape of the path, and is cautious:
if it isn't clearly one of those, it says so and the drawing is kept.
"""

import math

from .shapes import _distance_to_segment, _path_length

MIN_SIZE = 16          # smaller scribbles are left alone (image pixels)
FIT_LIMIT = 0.12       # how far off an ellipse or rectangle may be (see _closed_shape)


def _max_deviation(points, a, b):
    return max(_distance_to_segment(p[0], p[1], *a, *b) for p in points)


def _is_straight(points, a, b):
    chord = math.hypot(b[0] - a[0], b[1] - a[1])
    length = _path_length(points)
    if chord < 1 or length < 1:
        return False
    return chord / length > 0.92 and _max_deviation(points, a, b) < max(4.0, 0.07 * chord)


def _arrow(points):
    """A straight shaft with the head drawn as a hook at the end: the stroke
    goes out to a tip, then turns back a short way towards where it began."""
    start = points[0]
    k = max(range(len(points)), key=lambda i: math.hypot(points[i][0] - start[0],
                                                         points[i][1] - start[1]))
    if k >= len(points) - 2:
        return None                      # no hook after the tip
    tip, end = points[k], points[-1]
    shaft = math.hypot(tip[0] - start[0], tip[1] - start[1])
    if shaft < 30 or not _is_straight(points[:k + 1], start, tip):
        return None
    hook = _path_length(points[k:])
    if not (max(10.0, 0.04 * shaft) <= hook <= 0.6 * shaft):
        return None
    # The hook must point back towards the start (within 75°)
    v1 = (end[0] - tip[0], end[1] - tip[1])
    v2 = (start[0] - tip[0], start[1] - tip[1])
    n1, n2 = math.hypot(*v1), math.hypot(*v2)
    if n1 < 1:
        return None
    cos = (v1[0] * v2[0] + v1[1] * v2[1]) / (n1 * n2)
    if cos < math.cos(math.radians(75)):
        return None
    return start, tip


def _comes_back(points, size):
    """Does the stroke return to where it began? People often overshoot the
    start when closing a circle or box, so look for any point in the second
    half of the stroke that passes near the start, not just the last one."""
    start = points[0]
    return min(math.hypot(p[0] - start[0], p[1] - start[1])
               for p in points[len(points) // 2:]) < 0.25 * size


def _closed_shape(points, box):
    """For a stroke that comes back to where it began: how well does it fit
    an ellipse, and a rectangle, in the same box? Each error is the average
    distance from the outline, as a fraction of the half-size."""
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    cx, cy, rx, ry = x0 + w / 2, y0 + h / 2, w / 2, h / 2
    ellipse_err = sum(abs(math.hypot((x - cx) / rx, (y - cy) / ry) - 1)
                      for x, y in points) / len(points)
    rect_err = sum(min(abs(x - x0), abs(x - x1), abs(y - y0), abs(y - y1))
                   for x, y in points) / len(points) / (min(w, h) / 2)
    if min(ellipse_err, rect_err) > FIT_LIMIT:
        return None
    return "ellipse" if ellipse_err <= rect_err else "rectangle"


def recognize(points):
    """Return one of
        ("line", (x1, y1), (x2, y2))
        ("arrow", (x1, y1), (tip_x, tip_y))
        ("ellipse", (x, y, w, h))
        ("rectangle", (x, y, w, h))
    or None if the stroke isn't clearly any of them."""
    if len(points) < 4:
        return None
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    box = (min(xs), min(ys), max(xs), max(ys))
    w, h = box[2] - box[0], box[3] - box[1]
    size = max(w, h)
    if size < MIN_SIZE:
        return None
    start, end = points[0], points[-1]

    if _is_straight(points, start, end):
        return ("line", start, end)

    arrow = _arrow(points)
    if arrow:
        return ("arrow",) + arrow

    if _comes_back(points, size) and min(w, h) > 0.15 * size:
        kind = _closed_shape(points, box)
        if kind:
            return (kind, (box[0], box[1], w, h))
    return None
