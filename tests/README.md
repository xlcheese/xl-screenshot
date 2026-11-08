# Tests

About 425 checks in 24 suites, covering both apps: captures and the Selection
overlay (including on HiDPI screens), the tray icon, Esc to cancel, window
picking, every xl-Annotate tool and style option, freehand tidying, undo,
crop, zoom, saving, the translations, and starting the programs from the
command line.

They open real windows on a virtual screen (Xvfb), so they don't disturb your
desktop, and each uses a new empty home folder, so your settings are never
touched.

## Running them

```bash
sudo apt install xvfb openbox dbus xdotool x11-utils python3-xlib gettext
make check
```

or, for just some of them (any part of a suite's name):

```bash
tests/run-tests tidy annotate
```

A full run takes about three and a half minutes. Each suite prints one line:

```
  ok    test_annotate           63 checks
  ok    test_tools              57 checks
  ...
24 suites passed, 0 failed, 425 checks in all.
```

When something fails, the failing checks are listed under the suite's name.
To see a suite's full output, run it on its own:

```bash
xvfb-run -a -s "-screen 0 1280x800x24" python3 tests/test_tools.py
```

Some suites also save pictures of the windows they checked. Set
`XL_TEST_PICTURES=/some/folder` to keep them for a look.

## On GitHub

Every push runs the whole set on Ubuntu 24.04 (the base of Linux Mint 22):
see the Actions tab. The result shows as the badge at the top of the README.

## Writing a new test

Start the file with `import helpers` (it sets up the paths, a temporary home
folder and English text), print `PASS <what>` or `FAIL <what>` for each
check, and finish with `FAILURES: none` when all is well. `run-tests` picks up
any `test_*.py` or `test_*.sh` file in this folder.
