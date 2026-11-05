'use client';
// Product cards (.hover-grow, styles in globals.css) grow 20% under the cursor. This decides which way:
// a card at the left edge of its grid grows to the right, one at the right edge grows to the left,
// the ones in between grow evenly. Measured when the cursor enters, so it is right on 2, 3 or 4
// columns and after a resize. One listener for the whole site, nothing per card. Renders nothing.
import { useEffect } from 'react';

const EDGE_PX = 4; // "at the edge" tolerance for rounding

export default function HoverGrowSides() {
  useEffect(() => {
    const onOver = (e: MouseEvent) => {
      const card = (e.target as Element | null)?.closest?.<HTMLElement>('.hover-grow');
      const grid = card?.closest('.grid');
      if (!card || !grid) return;
      const c = card.getBoundingClientRect();
      const g = grid.getBoundingClientRect();
      card.dataset.side = c.left - g.left < EDGE_PX ? 'left' : g.right - c.right < EDGE_PX ? 'right' : 'center';
    };
    document.addEventListener('mouseover', onOver);
    return () => document.removeEventListener('mouseover', onOver);
  }, []);
  return null;
}
