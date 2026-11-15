# Design decisions

The redesign's decision log. Once phase 0 closes, a decision changes only if a judging round fails on that exact point. New ideas go in `later.md`.

## 2026-11-08: Fonts are free and self-hosted

- **Decision:** no paid fonts. Every family is open-licensed (SIL OFL) and self-hosted as woff2 files in `web/app/fonts`, following the reasoning in `web/app/layout.tsx`. Fetching from Google Fonts at build time made CI fail for reasons unrelated to the change under test.
- **Consequence:** type-test candidates are limited to OFL families we can bundle. IBM Plex Sans, Manrope and JetBrains Mono are already present. Any new family adds its woff2 files and its license to `app/fonts/OFL.md`.
- **Identity:** a custom-drawn SVG wordmark, not a custom typeface. Drawing a full typeface would take months of specialist work; a hand-tuned wordmark gives a unique signature at no cost.

## 2026-11-08: Replace the double-helix logo

- **Decision:** retire the DNA double helix in `web/components/ui/logo-animated.tsx`. It's the most overused symbol in biotech branding, and it says "biology" rather than what OpenOncology does: rank drugs against a mutation profile.
## 2026-11-08: Logo direction is A, Track

- **Decision:** the mark is a sequence track with one raised block, the variant the ranking starts from. In the wordmark, the l in "Oncology" becomes that raised block, in the accent color, so the mark and the name are one idea.
- **Rejected:**
  - B, Rank (three falling bars). It read as a "text align" or menu icon.
  - C, Locus (a ring with a highlighted arc). It read as a loading spinner or donut chart.
- **Recommended:**
  - The A2 Bold mark everywhere, since it's the only variant that holds at 16px.
  - The W1 wordmark (sentence case, accent l) as the primary logo.
  - Both pending the owner's confirmation on `/lab/brand`.
- **After confirmation:** outline the wordmark to SVG paths and kern it by hand, then replace `components/ui/logo-animated.tsx` and the favicon.

## 2026-11-08: Logo locked

- **Decision:** the A2 Bold mark plus the W1 wordmark, owner-confirmed.
- **Where it lives:**
  - in the nav, via `components/ui/logo-animated.tsx`;
  - as the favicon, via `app/icon.svg`.
- **Still to do:** outlining the wordmark to SVG paths and kerning it by hand.

## 2026-11-09: Palette A, H&E on paper

- **Decision:** hematoxylin violet for actions and eosin pink for visualization highlights, on warm paper. Tokens are in `web/app/globals.css` (`--oo-*`) and exposed in Tailwind as `oo-*`.
- **Eosin rules:**
  - Eosin appears only inside visualizations (variant tracks, chart marks).
  - Never as text on a light background.
  - Never next to status pills.
- **Contrast:**
  - Eosin was darkened from `#E58FB3` to `#D9669A`, because the lighter value failed the 3:1 graphic-contrast minimum on white (2.36:1); it now measures 3.32:1. `#FBE8F0` stays as the soft halo.
  - All checked text pairs measure 4.5:1 or better (see `/lab/palette`).
- **Analyzing moved from blue to amber,** because blue sat too close to the brand violet. The status set is now:
  - queued: stone;
  - analyzing: amber;
  - complete: green;
  - failed: red, with an alert icon.
- **Rejected:**
  - B, ink plus one violet: no conflicts, but too plain.
  - C, green and cream: the brand green was nearly identical to the Complete status green, so primary buttons read as success badges.

## 2026-11-09: Typefaces

- **Display:** Source Serif 4, Display optical size, Semibold. Marketing headlines only, never inside the app.
- **UI:** IBM Plex Sans 400/500/600, already bundled. Headings get tightened tracking.
- **Mono:** IBM Plex Mono, replacing JetBrains Mono behind `--font-mono`. Used for sequences, IDs and scores.
- **Retired:**
  - JetBrains Mono, removed;
  - Manrope and Inter, removed as their pages get restyled. Inter is loaded only by `/workspace`'s layout.
- **Installed:**
  - `IBMPlexMono-Variable-Latin1.woff2` (32 KB) and `SourceSerif4Display-Semibold.woff2` (84 KB), the publishers' own unmodified files. Both families reserve their font names, so neither is subset here; see `web/app/fonts/OFL.md`.
  - The display font loads only where `lib/display-font.ts` is imported, which keeps it off app pages.
- **Rejected:**
  - Inter, the benchmark's default (Modal and Cradle use it), so it gives parity, not distinction.
  - Geist, which reads as a developer tool.
  - Plex Serif display, stiff at 48px and above.
  - Instrument Serif, Fraunces and Newsreader, this cycle's trend fonts.
- **Bug fixed:**
  - **Cause:** `font-[var(--font-plex)]` compiled to `font-weight: var(--font-plex)`, not a font family. Tailwind reads an arbitrary `font-[var(...)]` as a weight.
  - **Effect:** the whole site rendered in the system font, and IBM Plex Sans never loaded.
  - **Fix:** Plex Sans is now Tailwind's `sans` family and the body uses `font-sans`.
  - **Still open:** four `font-[var(--font-manrope)]` usages have the same bug. They now inherit Plex Sans, which matches retiring Manrope. Delete those classes when the pages are restyled.
- **Payload rules:** only the weights in use, Latin subset, and preload only the display weight. Target: about 60–100 KB added.
- **Risk:** serif plus violet can read as an academic journal. The serif stays confined to marketing headlines.

## 2026-11-09: Hero is A, "Product first, then unpacked"

- **Decision:** the finished, labelled Results card is visible at first paint, so it's the LCP element. A sticky stage gives up to 150vh of scroll, for a 250vh track in total, across three discrete states:
  - load: the card tilted back 12° at 92% scale;
  - from 30%: the card flat, and the variant annotated;
  - from 65%: each drug row opens to show its approval status, mechanism and its own named evidence sources.
- **Labels never animate.** The CTA, demo label, research pill and oncologist-review note are visible from frame 0. Phones and reduced-motion visitors get the flat first frame, with no scroll scene.
- **Why:** an independent review of round 1 showed concept 1 made visitors scroll 250vh to reach the product, and that its evidence choreography was semantically wrong, because sources belong to drugs, not to the variant. Mercury-style product-first fixes both.
- **Rejected:**
  - concept B, genome to report: the product appears too late, and it's the highest 60fps risk. Its base-level frame may come back in a "how it works" section;
  - the original concepts 1 and 3, merged into A.
- **Headline:** "From a tumor VCF to a ranked drug list, with its evidence sources named." "Evidence-linked" was dropped because sources are names, not links. Final wording still needs the owner's claims sign-off.
- **DiffDock** stays out of displayed sources until OO-30 is decided.
- **Phase 0 closed.**

## 2026-11-09: Anti-slop ban list (checked in every devil's-advocate review)

These are AI-generated defaults we don't ship. Each line is checked against every page and component. Sources are in `docs/design-research/tooling.md`.

### Never ship

- Purple, indigo or rainbow gradients, as backgrounds or text fills. The hematoxylin violet is a solid color, used only for actions and active states.
- Glassmorphism panels, blurred color blobs, glowing borders, animated beams, or particle backgrounds behind text.
- A centered gradient hero followed by three identical icon-plus-title feature cards.
- Stock or generic imagery that could belong to any SaaS. Every visual shows OpenOncology data or is a labelled schematic.
- Formulaic headlines ("Unlock…", "Supercharge…", "The future of…", "AI-powered…") and invented metrics or testimonials.
- Inter or a system font as the identity. Ours is Plex Sans with Source Serif 4 Display.
- Emoji as icons, and icon-only buttons without labels.
- Motion for its own sake: staggered fly-ins on load, parallax on text, bouncing springs, and any animation on disclaimers or clinical text.
- Color as the only signal (status needs a label; failed needs an icon).

### Always

- Real demo data, labelled as demo.
- Tabular numbers in data.
- Visible keyboard focus.
- A static first frame for reduced motion.

## 2026-11-09: Libraries

- **Motion:** framer-motion, already in the repo, is the only animation engine. GSAP, now free, is reconsidered only if a section needs a long timeline.
- **Rejected:** Magic UI, Aceternity UI and React Bits, whose signature effects are on the ban list.
- **Behaviour:** Radix, with the look in `components/oo`.

## 2026-11-09: Component set revised after review

An independent review scored the first component set 5.5/10 as a base for the Results page. Changes made:

- **Violet only for actions.**
  - Tier pills: FDA approved is a bordered neutral pill with a check; repurposed is a soft neutral pill.
  - Score bars are neutral ink.
  - The empty-state icon is neutral.
- **Status:**
  - Linear-style shape glyphs (dashed ring, half-filled, check, alert) with neutral label text, replacing tinted pills.
  - A screen-reader prefix "Status:".
  - "Awaiting oncologist review" is its own neutral state, driven by `oncologist_reviewed`. It never uses amber, so it can't read as Analyzing.
- **Findings:** a single list of expandable rows (`FindingList`). Each row is one button, with `aria-expanded`, that opens in place using framer-motion. A second render tree for mobile was removed. Radix Collapsible would have been a new dependency, so it wasn't used.
- **Shared helpers:** `lib/evidence.ts` holds the DiffDock filter and source labels; `lib/approval.ts` holds the approval-status parser. Both are tested, so the hero and Results page can't drift apart.
- **Focus and motion:**
  - Focus uses `outline`, not a box-shadow ring, so it survives Windows High Contrast.
  - `MotionConfig reducedMotion="user"` wraps the app.
  - The Tailwind easing tokens `ease-oo-out` and `ease-oo-in-out` match `lib/motion.ts`.
- **Craft:**
  - buttons `rounded-md font-medium`, with subtle depth shadows;
  - app buttons are 36px tall;
  - cards 10px radius;
  - table headers in 12px sentence case, not tracked uppercase;
  - 44px rows.
- **Nav:** the global nav is solid. The translucent blurred bar was glassmorphism, which the ban list forbids. This supersedes the blurred-nav takeaway in the earlier Linear research notes.
- **Not yet done:**
  - the paper-colored nav, which waits until pages move off the dark theme;
  - dropping the stat-card row from Results, done when Results is built.

## 2026-11-09: Motion libraries and rules

### Libraries, one per job

| Job | Library | Notes |
|---|---|---|
| Component and data motion | Motion (framer-motion) | |
| Landing scroll scenes | GSAP with ScrollTrigger, via `@gsap/react` | Installed 3.15.1 |
| Smooth scroll under the scroll hero | Lenis | 1.3.27 (MIT). Only if scrubbing feels steppy |
| Live-changing numbers | NumberFlow | Adopt when needed |
| List reordering | framer's `layout` prop, or AutoAnimate | Adopt when needed |

- **Load scope:** each library loads only on routes that use it. GSAP never ships with app pages.
- **GSAP license:** GSAP is free, including commercially, but under GSAP's "Standard No Charge" license (gsap.com/standard-license), not an open-source license. It restricts uses such as building a competing visual animation tool. Acceptable here; recorded because the repo is open source.
- **Rejected:**
  - Lottie, which needs an After Effects pipeline;
  - React Spring, which overlaps Motion;
  - Magic UI and Aceternity, on the ban list;
  - hand-written CSS keyframes for data motion.

### Rules (from the motion review, which scored the first pass 5.5/10)

- **Only chart shapes animate.** Drug names, variant labels and domain bands never fade; clinical text never animates.
- **One narrow exception, disclosure in place.** A container that holds clinical text may grow open in height, as the Results rows and the landing hero card do. The text inside is at full opacity, never moves, and isn't revealed letter by letter or faded. The landing hero shows everything by default (no-JS, phones, short laptops, reduced motion); only the desktop scroll scene starts collapsed, and its first state change doesn't animate.
- **Landing hero, round 3:** a 160vh track (down from 200vh) with a scrubbed 1px progress rail on the step list (GSAP ScrollTrigger `scrub`), and steps as buttons that scroll to their stage. The step list is hidden outside the scroll scene, where the card already shows every state. The protein strip left the hero; its facts (domain, classification, OncoKB level) sit in the card header, and the full view stays in the result section.
- **Landing hero, round 4 (owner chose "add an opening moment" on 2026-11-15, revised after review):** a new first step, "Variant supplied", with the input line as the card's top row (tinted while active), above "Ranked candidates for" and the cancer type. When step 2 begins, the score bars fill once to their true values in about 0.6s (GSAP, `scaleX` only), and they empty again if you scroll back. An earlier scrubbed fill was dropped, because a reader could stop on bars that disagreed with the printed scores. The track is 170vh. The demo and oncologist-review note sits above the card, so disclosures never push it. Outside the scene every bar shows its true value from first paint, and print and reduced motion are covered by the `data-reveal="scale-x"` override. The scene still needs a viewport at least 860px tall, so 768–800px laptops get the static card.
- **Derived signals aren't sources.** `ClinicalPhase` is a scoring input, not a named evidence source, so it's shown as a note beside the source badges ("Score also weighs the drug's clinical phase"), not as a badge.
- **One trigger per section** (`useInView`, `amount: 0.3`), with short stagger (0.04–0.06s) inside it. No page-level staggered fly-ins.
- **Transforms only:** `x`, `scaleX` and `scaleY`, never `left` or `width`.
- **Timings:** slide 0.45s; pin 0.3s; head pop +0.18s over 0.2s, from 0.6 scale, without overshoot. Everything settles in about 0.6s.
- **Score bars in the table are static,** since they repeat the ladder's values.
- **True values without animation:** under reduced motion, print or no-JS, every shape shows its true value from the first paint (CSS overrides plus a noscript fallback). Verified in headless Chromium: dots, lines and pins match 0.983, 0.973 and 0.71 in all three modes, with no console errors.
- **Hover:**
  - mouse-only (pointer type check, and Tailwind `hoverOnlyWhenSupported`);
  - focus is tracked separately;
  - rows subscribe through a tiny external store, so only the affected rows re-render.
- **Expand:** height over 0.22s, content fades in after a 0.08s delay.

## Open

- Display typeface
- Hero concept
- Final headline wording
