# Brand

## The mark

A drive platter with a keyhole cut through it. The keyhole's slot runs out through the platter's edge, so the lock is open and the data is reachable. That is the whole product in one silhouette.

Because the notch joins the keyhole to the outside, the shape is a single closed outline with no holes. It renders identically in every SVG engine, cuts cleanly as a stencil, and embosses.

## Construction

Built on a 64-unit grid. Disc centre (32, 32), radius 27, leaving 5 units of clear margin on every side. Keyhole circle centre (32, 26), radius 7.5: it sits 6 units above the disc centre so the slot's weight below it balances the whole. Slot half-width 4.5 at the keyhole, widening to 6 at the edge so the notch stays open when the mark is rendered at 16 px.

The path is generated, not drawn: see `MARK_PATH` in `app/wdpassport/ui/icons.py`.

## Why this shape

- One idea, two primitives. It survives being drawn from memory.
- Reads at favicon size (`assets/brand/icon-16.png`) and in one colour.
- Says "security" through the keyhole and "open" through the notch, without a padlock cliche or a hard-drive illustration.
- Not derived from any WD mark. Nothing in it references the manufacturer.

## Colour

| Name | Hex | Use |
| --- | --- | --- |
| Navy | `#0f1e33` | Tile gradient end, sidebar, dark text |
| Signal blue | `#1f5fbf` | Mark on light backgrounds, primary buttons, gradient start |
| Sky | `#4f8fe6` | Mark on dark backgrounds |
| White | `#ffffff` | Mark on the tile |

The tile (`logo-tile.svg`) is the app icon: the mark in white at 80% on a navy-to-blue gradient with 14-unit corners. The flat marks (`logo-mark.svg`, `logo-mark-white.svg`, `logo-mark-mono.svg`) are for everything else.

## Type

Outfit Bold for "Linux Unlocker", Outfit Regular for "WD My Passport", tracked slightly. The lockup SVGs carry the letters as outlines, so they need no fonts installed. Outfit is under the SIL Open Font License.

## Rules

- Clear space around the mark: at least the keyhole's diameter (15 units of 64).
- Minimum size: 16 px for the tile, 20 px for the flat mark, 120 px wide for the lockup.
- Do not rotate the mark, close the notch, add a shackle, or set it in another colour than the four above.
- The lockup reads "Linux Unlocker" first because that is the product. "WD My Passport" is the compatibility line, never the brand.

## Files

`assets/brand/`: `logo-mark.svg`, `logo-mark-white.svg`, `logo-mark-mono.svg`, `logo-tile.svg`, `logo-lockup.svg`, `logo-lockup-dark.svg`, `icon-16.png` to `icon-512.png`, `lockup.png`, `lockup-dark.png`. `assets/wd-hdd-unlocker.svg` is the tile and is what the .deb installs as the desktop icon.
