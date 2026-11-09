# Ambience Healthcare (ambiencehealthcare.com): serif headline, load

Observed on 2026-11-08 and 2026-11-09 on the live public page with browser DevTools. No source code or assets were copied. Reviewed by an independent devil's-advocate pass; over-claims were removed.

## Measured

- **Headline:** a serif ("Rhetorik Serif"), 55.25px, weight 400, line-height 1.0, letter-spacing about −0.03em.
- **Body text:** Geist.
- **Background:** warm cream `#F6F4EF`.
- **On 2026-11-08 (foreground):** the page showed blank for about 2 s before appearing.
- **On 2026-11-09 (possibly a background tab):** after load, the headline was at full opacity with no transform from 0 to 2.5 s, and no CSS or Web Animations were running.

## Not established

- **Whether there's a designed entrance.** We saw no entrance effect, but that's unconfirmed.
- **Whether the 2 s blank was font blocking or a slow load.**
  - **Needs:** a foreground Performance recording with screenshots from navigation start, cache disabled, plus the network waterfall and the `font-display` of its `@font-face` rules.
- **Spacing scale:** the page has no `<section>` elements, so it couldn't be read section by section.

## What OpenOncology takes

- **Serif headline tracking:** set tight. We use −0.02em on Source Serif 4 Display, our own value.
- **Load motion stays minimal:** one headline reveal, no staggered fly-ins. This applies to load motion only; the scroll-driven hero is a separate decision.
- **Never show a blank screen:** the hero's static state renders on the server and in the first paint, and motion only adds to it. Our font files use `display: swap` (`app/layout.tsx`, `lib/display-font.ts`), so text is never hidden while fonts load.
