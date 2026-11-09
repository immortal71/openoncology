# Linear (linear.app): headline, nav, ambient motion

Observed on 2026-11-09 on the live public page with browser DevTools: computed styles, plus the Web Animations timing data the page was already running. The tab may have been in the background. No source code was copied. Reviewed by an independent devil's-advocate pass; over-claims were removed.

## Measured

- **Headline:**
  - Inter Variable, 38px, weight 510;
  - letter-spacing about −0.022em;
  - line-height 1.1.
- **Nav (header):**
  - a blurred backdrop over a transparent background, with a faint light hairline at the bottom;
  - border color and background have short ease-out transitions declared;
  - no change was seen between scrollY 0 and 400, but that's a single pair of samples, possibly still inside the hero.
- **Ambient motion:** about 40 CSS animations running after load, all slow background loops: a 30 s linear drift, and 2.8 s pulses on dots in a decorative grid.

## Not measured

- **Headline reveal timing:** none was running at measurement time. Either it had finished or there isn't one.
- **Card cursor light** (pointer-following highlight).
- **Nav state across the whole page.**
  - **Needs:** `getComputedStyle` at scrollY 0, 100, 400, 1000, 2000 and past the hero, in a visible tab, plus a MutationObserver on the header's class.
- **Reduced-motion behaviour, and frame cost.**

## What OpenOncology takes

These are our own values, informed by the observations above, not copies of Linear's CSS.

- **Headline tracking:** tight, about −0.02em on large sans headings. Plex Sans ships as static 400/500/600 here, so headings use 600.
- **Nav:**
  - a solid background with an `oo-line` hairline;
  - no blur, because a translucent blurred bar is glassmorphism and on our ban list (`decisions.md`, 2026-11-09);
  - our micro duration of 150ms on our ease-out token for state changes (plan v3, section 9).
- **Ambient motion, our rules rather than anything taken from Linear:**
  - loops are slow, 2.4 s or longer;
  - at most one ambient element per view;
  - never near clinical text.
