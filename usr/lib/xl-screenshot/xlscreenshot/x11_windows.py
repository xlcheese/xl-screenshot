"""The windows on an X11 desktop, for our window picker (when Cinnamon's own
screenshot service isn't there, e.g. Linux Mint 22).

X11 lets any program see where every window is, so we can do what Cinnamon's
picker does: tint the desktop and lift the window under the pointer.
"""

from Xlib import X, Xatom, display as xdisplay, error as xerror


def _atoms(dpy, window, name):
    prop = window.get_full_property(dpy.intern_atom(name), Xatom.ATOM)
    return set(prop.value) if prop else set()


def _cardinals(dpy, window, name):
    prop = window.get_full_property(dpy.intern_atom(name), Xatom.CARDINAL)
    return list(prop.value) if prop and len(prop.value) == 4 else None


def list_windows():
    """The normal windows on screen, top first: dicts with
    id      the X window id
    rect    (x, y, w, h) in desktop pixels, as captured: titlebar and borders
            included, and any invisible shadow area of GTK windows left out
    maximized  True for maximized and full-screen windows (square corners, no
            shadow on screen)
    csd     the window draws its own title bar (GTK): rounded by the GTK theme
    framed  Cinnamon draws its title bar: rounded by the window-border theme
    """
    try:
        dpy = xdisplay.Display()
    except Exception:
        return []
    try:
        root = dpy.screen().root
        stacking = root.get_full_property(dpy.intern_atom("_NET_CLIENT_LIST_STACKING"), Xatom.WINDOW)
        if stacking is None:
            stacking = root.get_full_property(dpy.intern_atom("_NET_CLIENT_LIST"), Xatom.WINDOW)
        ids = list(stacking.value) if stacking else []
        skip_types = {dpy.intern_atom(n) for n in ("_NET_WM_WINDOW_TYPE_DESKTOP", "_NET_WM_WINDOW_TYPE_DOCK")}
        hidden = dpy.intern_atom("_NET_WM_STATE_HIDDEN")
        max_v = dpy.intern_atom("_NET_WM_STATE_MAXIMIZED_VERT")
        max_h = dpy.intern_atom("_NET_WM_STATE_MAXIMIZED_HORZ")
        fullscreen = dpy.intern_atom("_NET_WM_STATE_FULLSCREEN")
        windows = []
        for wid in reversed(ids):          # the stacking list is bottom first
            win = dpy.create_resource_object("window", wid)
            try:
                if win.get_attributes().map_state != X.IsViewable:
                    continue
                if _atoms(dpy, win, "_NET_WM_WINDOW_TYPE") & skip_types:
                    continue
                state = _atoms(dpy, win, "_NET_WM_STATE")
                if hidden in state:
                    continue
                geo = win.get_geometry()
                pos = root.translate_coords(win, 0, 0)
                x, y, w, h = pos.x, pos.y, geo.width, geo.height
                gtk = _cardinals(dpy, win, "_GTK_FRAME_EXTENTS")
                if gtk:                    # GTK's invisible shadow area: not part of the window
                    left, right, top, bottom = gtk
                    x, y, w, h = x + left, y + top, w - left - right, h - top - bottom
                frame = _cardinals(dpy, win, "_NET_FRAME_EXTENTS")
                if frame:                  # the window manager's titlebar and borders
                    left, right, top, bottom = frame
                    x, y, w, h = x - left, y - top, w + left + right, h + top + bottom
                if w < 4 or h < 4:
                    continue
                windows.append({"id": wid, "rect": (x, y, w, h),
                                "maximized": (max_v in state and max_h in state) or fullscreen in state,
                                # who draws the title bar: GTK (csd) or the window manager (framed)
                                "csd": bool(gtk), "framed": bool(frame and any(frame))})
            except xerror.XError:
                continue                   # closed while we looked
        return windows
    finally:
        dpy.close()


def window_at(windows, x, y):
    """The top window containing desktop point (x, y), or None."""
    for win in windows:
        wx, wy, ww, wh = win["rect"]
        if wx <= x < wx + ww and wy <= y < wy + wh:
            return win
    return None


def active_window_id():
    """The X window id of the window that has the focus, or None."""
    try:
        dpy = xdisplay.Display()
    except Exception:
        return None
    try:
        prop = dpy.screen().root.get_full_property(dpy.intern_atom("_NET_ACTIVE_WINDOW"), Xatom.WINDOW)
        wid = prop.value[0] if prop and len(prop.value) else 0
        return wid or None
    except xerror.XError:
        return None
    finally:
        dpy.close()
