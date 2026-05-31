# pyssg brand

The pyssg mark is the letter **p** drawn as a small **knowledge graph**: a stem,
a circular bowl, and a satellite node linked by a thin edge. It signals what
pyssg is growing into - a generator for AI, learning, productivity and
knowledge bases, with linked notes in the spirit of Obsidian and Notion
(backlinks, neural-style nodes, connected thinking).

## Files

| File | Use |
|------|-----|
| `logo-icon.svg` | App icon / favicon. Gradient rounded tile with a white mark. Primary mark. |
| `logo-mark.svg` | Gradient mark on a transparent background. Use on solid light/dark surfaces. |
| `logo-mono.svg` | Single-color mark (`currentColor`). Stamps, print, one-color contexts. |
| `logo-wordmark.svg` | Horizontal lockup: mark + `pyssg`. Headers, READMEs, social. |
| `preview.html` | Contact sheet of every variant at multiple sizes on light/dark. |

## Color

The gradient runs indigo to violet:

- `#6366F1` indigo (start)
- `#6D45D8` (mid)
- `#8B3DE0` violet (end)

It matches the docs theme accent so the site, icon and wordmark stay consistent.
For one-color use, `logo-mono.svg` follows the surrounding text color when
inlined.

## Clear space and sizing

- Keep clear space around the mark equal to the height of one node.
- The tile (`logo-icon.svg`) stays legible down to 16px (favicon).
- Below ~24px prefer the tile over the transparent mark - the gradient tile
  holds contrast better at small sizes.

## Don'ts

- Do not recolor the gradient outside the palette above.
- Do not stretch, rotate or add shadows to the mark.
- Do not place the transparent mark on a busy or low-contrast background; use the
  tile instead.

## Wordmark font

The lockup sets `pyssg` in Inter / system-sans, weight 800. For print or to drop
the font dependency, outline the text to paths in your vector editor.
