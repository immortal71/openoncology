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

## Open

- Display typeface
- Hero concept
- Final headline wording
