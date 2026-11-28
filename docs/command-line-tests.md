# Command-line captures: a checklist

Commands to try by hand on a real desktop, with what should happen. Try them
on X11 and on Wayland (Cinnamon); a few only apply to one of the two, and
those are marked **X11** or **Wayland**.

## Set-up

1. Quit xl-Screenshot from the tray, if it's there, and install the test
   `.deb`.
2. Make a folder to work in and go there:

   ```bash
   mkdir -p ~/clitest && cd ~/clitest
   ```

3. Add `; echo "exit $?"` after a command to see its exit status:
   **0** = saved, **1** = nothing captured (canceled or failed),
   **2** = a mistake in the options.

Unless a test says otherwise, a successful command prints the saved file's
full path and nothing else. A file name without a folder (`seam.png`) is saved
in the folder you're in; with no file name at all, captures go to
`~/Pictures/xl-Screenshot`. Check the pictures by opening them (Pix, or
`xl-annotate FILE`).

## 1. Help and screens

| # | Command | Expected |
|---|---|---|
| 1.1 | `xl-screenshot --help` | Every option, grouped: What to capture, Where it goes, Options, The app. No window opens. |
| 1.2 | `xl-screenshot --version` | `xl-Screenshot 0.3.0` (the test build doesn't change the app's own version yet), exit 0 |
| 1.3 | `xl-screenshot --list-screens` | One line per monitor, e.g. `1: 1920x1080+0+0  (primary)`. Sizes in real pixels. The prompt comes straight back, and each screen shows its number large, with its size, for about 3 seconds. |
| 1.4 | The same, clicking a number | The numbers go at once. |
| 1.5 | `xl-screenshot --list-screens \| cat` | The list only: no numbers (a script reading it). |
| 1.6 | `xl-screenshot --list-screens --no-identify` | The list only. |
| 1.7 | `xl-screenshot --identify \| cat` | The list, and the numbers even so. |

## 2. Screens

| # | Command | Expected |
|---|---|---|
| 2.1 | `xl-screenshot --screens` | Saved to `~/Pictures/xl-Screenshot/Screenshot-<date>_<time>.png` (the folder is made if needed). Every monitor, laid out as in Display settings. |
| 2.2 | `xl-screenshot` | The app window opens, as before (not a capture). |
| 2.3 | `xl-screenshot --screen 1 one.png` | `~/clitest/one.png`: just screen 1, its full size from `--list-screens`. |
| 2.4 | `xl-screenshot --screen 2 two.png` | Just screen 2 (with two monitors). |
| 2.5 | `xl-screenshot -M 2 two-scrot.png` | The same, with scrot's spelling. |
| 2.6 | **X11:** `xl-screenshot --screen pointer.png`, with the pointer on screen 2 | Screen 2. Try again with the pointer on screen 1. |
| 2.7 | **Wayland:** `xl-screenshot --screen` | `on Wayland, apps aren't told where the pointer is: give the screen's number…`, exit 2 |

## 3. Areas

| # | Command | Expected |
|---|---|---|
| 3.1 | `xl-screenshot --area 100,100,400,300 area.png` | `area.png`, 400 × 300, from 100 px in and 100 px down on the desktop. |
| 3.2 | `xl-screenshot --area 100,100,400,300 area.png` (again) | Saved as `area_1.png`: the first one isn't replaced. |
| 3.3 | `xl-screenshot -o -a 100,100,400,300 area.png` | `area.png` replaced (`-o`, scrot's `-a`). |
| 3.4 | `xl-screenshot --area 400x300+100+100 geom.png` | The same area as 3.1 (WxH+X+Y, as `--list-screens` prints). |
| 3.5 | Across the seam: `xl-screenshot --area 1800,400,500,500 seam.png` (with a 1920-wide screen 1 on the left; adjust to yours) | 500 × 500: the right edge of screen 1 and the left of screen 2, joined where the seam is. |
| 3.6 | `xl-screenshot --area 1800, 400, 500, 500 x.png` (spaces) | `expected X,Y,W,H with no spaces…`, exit 2 |
| 3.7 | `xl-screenshot --area "1800, 400, 500, 500" quoted.png` | Works: in quotes, spaces are fine. |
| 3.8 | **HiDPI** (if you can set 200%): `xl-screenshot --area 0,0,400,300 hi.png` | 400 × 300 real pixels (a smaller part of the screen than at 100%). |

## 4. Selection and windows

| # | Command | Expected |
|---|---|---|
| 4.1 | `xl-screenshot --selection sel.png` (Accurate chosen in the app) | The Selection overlay; draw, adjust, Capture: `sel.png` is what you drew. |
| 4.2 | Same, Fast chosen in the app | Saved as soon as you let go. |
| 4.3 | `xl-screenshot --selection x.png`, then Esc | `nothing was captured (canceled, or the capture failed)`, exit 1, no file. |
| 4.4 | `xl-screenshot --window win.png` | The window picker; the window clicked is saved, with rounded corners. |
| 4.5 | `xl-screenshot --window --shadow winshadow.png` | The same, with the shadow. |
| 4.6 | `sleep 2; xl-screenshot --focused focused.png`, then click another window within 2 s | That other window (the focused one), not the terminal. |
| 4.7 | **X11:** `xl-screenshot --window-id $(xwininfo -int \| awk '/Window id/{print $4}') byid.png`, then click a window | That window. |
| 4.8 | **Wayland:** `xl-screenshot --window-id 0x1234` | `--window-id works on X11 only…`, exit 2 |

## 5. File names and formats

| # | Command | Expected |
|---|---|---|
| 5.1 | `xl-screenshot -a 0,0,640,480 'shot_%Y-%m-%d_%H%M%S_$wx$h.png'` | e.g. `shot_2026-11-27_201502_640x480.png` (single quotes keep `$w` from the shell). |
| 5.2 | `xl-screenshot -a 0,0,640,480 photo.jpg` | A JPEG (`file photo.jpg` says JPEG). |
| 5.3 | `xl-screenshot -a 0,0,640,480 --format jpg noext` | Saved as `noext.jpg`. |
| 5.4 | `xl-screenshot -a 0,0,640,480 -q 20 low.jpg` | Visibly blockier and much smaller than 5.2. |
| 5.5 | `xl-screenshot -a 0,0,640,480 pic.webp` | A WebP (needs `webp-pixbuf-loader`; without it, `could not save the image: WebP support missing…`, exit 1). |
| 5.6 | `xl-screenshot -a 0,0,640,480 sub/dir/deep.png` | The folders are made; `sub/dir/deep.png` saved. |
| 5.7 | `xl-screenshot -a 0,0,640,480 -F - > piped.png` | Nothing printed; `piped.png` is a good 640 × 480 PNG. |
| 5.8 | `xl-screenshot -a 0,0,640,480 - \| convert - -resize 50% half.png` | `half.png`, 320 × 240 (needs ImageMagick; with ImageMagick 7, `magick` instead of `convert`). |
| 5.9 | `xl-screenshot -a 0,0,640,480 - \| nosuchprogram` | The shell's "command not found", then `the program the image was piped to stopped before reading it…`, exit 1. |

## 6. Clipboard and xl-Annotate

| # | Command | Expected |
|---|---|---|
| 6.1 | `xl-screenshot -a 0,0,300,200 --clipboard` | Nothing printed, no file. Paste into xl-Annotate (Ctrl+V) or LibreOffice: a 300 × 200 picture. |
| 6.2 | Copy some text somewhere, then paste again | The text: the image has been replaced as usual. |
| 6.3 | `xl-screenshot --selection --clipboard`, as a keyboard shortcut (Keyboard settings → Shortcuts → Custom) | Press it, draw, and the area is ready to paste. |
| 6.4 | `xl-screenshot -a 0,0,300,200 --clipboard both.png` | Saved and copied. |
| 6.5 | `xl-screenshot -a 0,0,300,200 --annotate` | Saved to Pictures/xl-Screenshot, and xl-Annotate opens it. |

## 7. Delay and pointer

| # | Command | Expected |
|---|---|---|
| 7.1 | `xl-screenshot -d 3 --screens` | Captured 3 seconds later (open a menu meanwhile: it's in the picture). No file name given, so it goes to Pictures/xl-Screenshot, like 2.1. |
| 7.2 | **X11:** `xl-screenshot -d 5 --screens`, then Esc | Canceled: exit 1, nothing saved. |
| 7.3 | `xl-screenshot -p -a 0,0,800,600 pointer.png`, with the pointer in that area | Your own pointer, as your theme draws it and at its size, in the picture. |
| 7.4 | The same without `-p` | No pointer. |

## 8. Mistakes (each: a message, exit 2, nothing saved)

| # | Command | Message |
|---|---|---|
| 8.1 | `xl-screenshot --screen 9` | `there is no screen 9; this desktop has 2 (see --list-screens)` |
| 8.2 | `xl-screenshot --screen 0` | `screens are numbered from 1 (see --list-screens)` |
| 8.3 | `xl-screenshot --area 1,2,3` | `expected X,Y,W,H, e.g. 100,100,400,300` |
| 8.4 | `xl-screenshot --area 0,0,0,100` | `the width and height must be more than 0` |
| 8.5 | `xl-screenshot --screens --area 0,0,10,10` | `argument --area…: not allowed with argument --screens…` |
| 8.6 | `xl-screenshot -a 0,0,10,10 - --annotate` | `--annotate needs a file, not standard output (-)` |
| 8.7 | `xl-screenshot -a 0,0,10,10 -q 500` | `expected a number from 1 to 100` |
| 8.8 | `xl-screenshot -a 0,0,10,10 -F a.png b.png` | `give the file once: as --file FILE or as FILE` |
| 8.9 | `xl-screenshot --tray --screens` | `--tray can't be used with capture options` |

## 9. Alongside the app

| # | Do this | Expected |
|---|---|---|
| 9.1 | With xl-Screenshot's window open, `xl-screenshot -a 0,0,300,200 x.png` | Saved; the open window doesn't change or pop up. |
| 9.2 | With the tray icon on, the same | The same. |
| 9.3 | `xl-screenshot --selection` (no file) | As before: the app's Selection, into its window. |
| 9.4 | Change Include Pointer and the delay in the app, then `xl-screenshot -a 0,0,300,200 y.png` | No pointer, no delay: the command line only follows its own options (the Accurate/Fast choice is the one exception). |
