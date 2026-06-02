---
title: Keeping a custom theme upgrade-friendly
date: "2024-06-15"
tags: [theming, maintenance]
---
Once you eject a theme, it is yours -- including the parts you did not mean to
own. The copy will not pick up fixes shipped to the built-in theme later. A
little discipline keeps that from hurting.

## Prefer options over edits

Every change you can express as a theme option is a change you did **not** fork.
Options survive upgrades cleanly because they live in your config, not in a
copied template. Edit templates only for things options cannot reach, like a new
header band or a restructured post list.

## Keep the diff small and legible

- Change one thing at a time and keep the template close to the original, so a
  future `diff` against the upstream theme is readable.
- Leave a comment where you depart from the original and why.
- Treat `layout/` as source code: review it, and rebuild after every change to
  confirm nothing broke.

A focused fork you understand beats a pristine theme you cannot bend. See
[[Theme options vs. editing templates]] for where to draw that line.
