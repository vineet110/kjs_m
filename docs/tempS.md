# Session notes (Nishita)

One subheading per task. Moved into the shared docs after the PR merges (see `docs/prompt.md` section 7).


## Product cards grow 20% on hover (feat/card-hover, 5 Nov)

- Product cards (`ProductCard`, `HomeProductCard`) have a `hover-grow` class: under the cursor they grow 20% and come in front of their neighbours.
- Direction: a card at the left edge of its grid grows to the right, one at the right edge grows to the left, the middle ones grow evenly. `HoverGrowSides.tsx` (one `mouseover` listener in the public layout) measures this when the cursor enters, so it works on 2, 3 or 4 columns.
- Styles in `globals.css`, outside the Tailwind layers so they win over the cards' own hover lift. The grid cell is put on top with `:has()`, because the cards' `Reveal` wrappers would otherwise paint later cards over the grown one.
- Only with a mouse at tablet/desktop widths (`hover: hover` and 768px+). Phones: no effect. Reduced motion: no animation.
