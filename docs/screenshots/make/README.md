# Making the README screenshots

`make-screenshots` draws the eight pictures on the project's front page, in
Linux Mint's Mint-Y and Mint-Y-Dark themes, and writes them to
`docs/screenshots/`. Re-run it after changing how either app looks.

```bash
sudo apt install xvfb openbox xdotool fonts-ubuntu python3-numpy
docs/screenshots/make/make-screenshots
```

It runs the real apps on an invisible screen (at 2x, so the pictures are
sharp), so nothing appears on your desktop. Each window gets the rounded
corners and soft shadow that Cinnamon draws.

- `scenery.py` draws the mountain lake picture (original artwork, made in code)
- `scene_annotate.py`: xl-Annotate marking up the picture
- `scene_screens.py`: xl-Screenshot with a capture, and the Selection overlay
- `scene_empty.py`: xl-Screenshot before a capture
- `common.py`: the theme, fonts, window shadows and other shared set-up

Mint-Y comes with Linux Mint. Elsewhere, set `MINT_THEMES_DIR` to a folder
holding `themes/Mint-Y`, `themes/Mint-Y-Dark` and `icons/Mint-Y`
(from github.com/linuxmint/mint-themes and mint-y-icons).
