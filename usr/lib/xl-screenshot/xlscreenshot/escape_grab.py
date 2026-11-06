"""Catching the Escape key while our windows are hidden."""

from gi.repository import GLib

try:
    from Xlib import X, XK
    import Xlib.display
    import Xlib.error
    HAS_XLIB = True
except ImportError:
    HAS_XLIB = False


class EscapeKeyGrab:
    """Catch the Escape key while our windows are hidden (during a delay,
    or while the user picks a window).

    Uses a passive X key grab on the root window, so only Escape is taken
    from other apps, and only until release() is called.
    """

    # Grab Escape whatever the state of Caps Lock (Lock) and Num Lock (Mod2)
    MODIFIER_COMBOS = (0, X.LockMask, X.Mod2Mask, X.LockMask | X.Mod2Mask) if HAS_XLIB else ()

    def __init__(self, on_escape):
        self.on_escape = on_escape
        self.display = None
        self.watch_id = None
        if not HAS_XLIB:
            print("Esc to cancel needs python3-xlib (sudo apt install python3-xlib)")
            return
        try:
            self.display = Xlib.display.Display()
            self.root = self.display.screen().root
            self.keycode = self.display.keysym_to_keycode(XK.string_to_keysym("Escape"))
            catcher = Xlib.error.CatchError(Xlib.error.BadAccess)
            for mods in self.MODIFIER_COMBOS:
                self.root.grab_key(self.keycode, mods, True,
                                   X.GrabModeAsync, X.GrabModeAsync, onerror=catcher)
            self.display.sync()
            if catcher.get_error():
                print("Could not grab Escape: another program is using it.")
            self.watch_id = GLib.io_add_watch(
                self.display.fileno(), GLib.PRIORITY_DEFAULT,
                GLib.IOCondition.IN, self._on_x_events
            )
        except Exception as e:
            print(f"Could not grab Escape: {e}")
            self.release()

    def _on_x_events(self, fd, condition):
        if not self.display:
            return False
        pressed = False
        while self.display.pending_events():
            event = self.display.next_event()
            if event.type == X.KeyPress and event.detail == self.keycode:
                pressed = True
        if pressed:
            self.release()
            self.on_escape()
            return False
        return True

    def release(self):
        if self.watch_id is not None:
            GLib.source_remove(self.watch_id)
            self.watch_id = None
        if self.display is not None:
            try:
                for mods in self.MODIFIER_COMBOS:
                    self.root.ungrab_key(self.keycode, mods)
                self.display.sync()
                self.display.close()
            except Exception:
                pass
            self.display = None
