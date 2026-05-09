#!/usr/bin/env python3
"""
Source of truth for git-emblems icon artwork.

Each emblem combines two signals on one 64x64 canvas:
  * inner dot  -> repo status   (dirty / behind / ahead / clean)
  * outer ring -> ownership tier (primary / secondary / tertiary / external)

Status uses the same four colors the older single-dot emblems used, so the
status meaning is unchanged. The tier ring is new. Run this script to (re)write
the 16 SVGs into this directory. install.sh ships the generated files; the
generator is committed alongside them so colors/sizes stay tweakable in one
place.
"""

import os

STATUS_COLORS = {
    'dirty':  '#e8a23a',
    'behind': '#d04a3a',
    'ahead':  '#3aa856',
    'clean':  '#ffffff',
}

# Ring color per ownership tier. Picked for hue separation from the status dot
# colors so primary-dirty (gold ring + orange dot) and tertiary-behind
# (purple ring + red dot) read as distinct rather than monochrome.
TIER_RINGS = {
    'primary':   {'color': '#f5c419', 'width': 4.0, 'opacity': 0.95},
    'secondary': {'color': '#19c0e0', 'width': 4.0, 'opacity': 0.95},
    'tertiary':  {'color': '#a855f7', 'width': 4.0, 'opacity': 0.95},
    # Faint thin gray ring: visually says "none of yours" without competing
    # with the status dot.
    'external':  {'color': '#9aa0a6', 'width': 2.5, 'opacity': 0.50},
}

SVG_TEMPLATE = '''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" width="64" height="64">
  <circle cx="32" cy="32" r="18" fill="none" stroke="{ring}" stroke-width="{rw}" stroke-opacity="{ro}"/>
  <circle cx="32" cy="32" r="10" fill="{dot}" stroke="#1a1a1a" stroke-width="1.25" stroke-opacity="0.6"/>
</svg>
'''


def main():
    out_dir = os.path.dirname(os.path.abspath(__file__))
    for status, dot in STATUS_COLORS.items():
        for tier, ring in TIER_RINGS.items():
            svg = SVG_TEMPLATE.format(
                ring=ring['color'], rw=ring['width'], ro=ring['opacity'],
                dot=dot,
            )
            name = f'emblem-git-{status}-{tier}.svg'
            with open(os.path.join(out_dir, name), 'w') as fh:
                fh.write(svg)
            print(f'wrote {name}')


if __name__ == '__main__':
    main()
