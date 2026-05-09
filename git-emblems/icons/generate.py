#!/usr/bin/env python3
"""
Source of truth for git-emblems icon artwork.

Each emblem layers two signals on one 64x64 canvas:
  * outer disk -> repo status   (dirty / behind / ahead / clean)
  * inner dot  -> ownership tier (primary / secondary / tertiary)

The tier dot is small and black-outlined so the surrounding status color
reads as a ring around it. The 'external' tier has no inner dot at all —
the plain status disk signals "no ownership to declare", matching the
pre-ownership look.

Run this script to (re)write the 16 SVGs into this directory. install.sh
ships the generated files; the generator is committed alongside them so
colors/sizes stay tweakable in one place.
"""

import os

STATUS_COLORS = {
    'dirty':  '#e8a23a',
    'behind': '#d04a3a',
    'ahead':  '#3aa856',
    'clean':  '#ffffff',
}

# Inner-dot color per ownership tier. Black outline does the heavy lifting
# for separation, so colors are picked for hue distinctness more than for
# contrast against the status color underneath.
TIER_DOT_COLORS = {
    'primary':   '#f5c419',  # gold
    'secondary': '#19c0e0',  # cyan
    'tertiary':  '#a855f7',  # purple
    # 'external' is rendered without an inner dot.
}

# Outline shared by status disk and tier dot — almost-black, slightly
# softened so it doesn't read as harsh at small render sizes.
STROKE = '#1a1a1a'

SVG_WITH_TIER = '''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" width="64" height="64">
  <circle cx="32" cy="32" r="10" fill="{dot}" stroke="{stroke}" stroke-width="1.25" stroke-opacity="0.6"/>
  <circle cx="32" cy="32" r="5"  fill="{tier}" stroke="{stroke}" stroke-width="1.2"  stroke-opacity="0.85"/>
</svg>
'''

SVG_EXTERNAL = '''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" width="64" height="64">
  <circle cx="32" cy="32" r="10" fill="{dot}" stroke="{stroke}" stroke-width="1.25" stroke-opacity="0.6"/>
</svg>
'''


def main():
    out_dir = os.path.dirname(os.path.abspath(__file__))
    tiers = list(TIER_DOT_COLORS.keys()) + ['external']
    for status, dot in STATUS_COLORS.items():
        for tier in tiers:
            if tier == 'external':
                svg = SVG_EXTERNAL.format(dot=dot, stroke=STROKE)
            else:
                svg = SVG_WITH_TIER.format(
                    dot=dot, tier=TIER_DOT_COLORS[tier], stroke=STROKE,
                )
            name = f'emblem-git-{status}-{tier}.svg'
            with open(os.path.join(out_dir, name), 'w') as fh:
                fh.write(svg)
            print(f'wrote {name}')


if __name__ == '__main__':
    main()
