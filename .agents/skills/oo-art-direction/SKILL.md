---
name: oo-art-direction
description: OpenOncology art direction and visual QA. Use for any marketing-site, landing-page, hero, artwork or demo-presentation design work in this repo, before writing code and before calling a design finished.
---

# OpenOncology art direction

The benchmark is Mercury-level craft. No skill guarantees that; this one stops average work being called finished.

## Sources of truth

- Plan: `C:/Users/TES/Documents/Codex/2026-11-15/br/outputs/openoncology-design-plan/DESIGN-PLAN.md`
- Board: `.../openoncology-design-plan/DESIGN-BOARD.html`
- Reference captures: `.../openoncology-design-plan/references/*.jpg` (Mercury, Linear, Benchling, Tempus, Retool, Modal, Stripe, Metabase)

The plan is guidance, not law. Challenge it with a reason; don't ignore it silently.

## Approved decisions (preserve; do not reinvent each turn)

- Direction A, "Evidence Atlas": paper `#F7F5F0`, surface `#FFFFFF`, ink `#221E2B`, ink-2 `#615B69`, violet `#584493` (selection and thread only), wash `#ECE7F4`, rule `#DCD7DF`, night `#211D2A`, thread eosin `#C2417A`.
- Type: Inter (local `app/fonts/Inter-Variable.woff2`, `lib/atlas-font.ts`) for display and UI, tight tracking on display; IBM Plex Mono for metadata. Serif only if a reason is written down.
- Signature artwork: the evidence ribbon (`components/atlas/evidence-ribbon.tsx`): a silk bundle of threads with one eosin thread pulled out through Variant, Candidate, Source. It is labelled "Illustrative evidence pathway · demo case".
- Product proof uses the app's real components and demo data in one coherent frame. No screenshots shrunk into laptops, no floating dashboard collages, no fake controls.
- Buttons: ink primary, 6px radius; text links underlined. Pills only where functional.

## Rejected (do not bring back)

- Stock white-coat photography as filler; violet-washed photo stages.
- H&E tissue texture as the hero (implies digital pathology).
- Floating cards scattered over an image; icon-in-rounded-square feature lists; repeated three-card grids; giant violet blooms; particle wallpaper; generic DNA helices.
- Fabricated customers, logos, testimonials, metrics or validation numbers.

## Required loop

1. Open and look at the relevant reference captures (Read the images). Name what each contributes.
2. Before coding, write the spec: composition (grid columns), type sizes, colour use, artwork, product-image treatment.
3. Build within the approved decisions above.
4. Render at 1440×900, 1280×720 and 390×844 (headless Playwright script in the session scratchpad). Check console errors and horizontal overflow.
5. Compare the screenshots against the references and list concrete shortcomings (spacing, hierarchy, crop, contrast, rhythm, anything generic).
6. Run an independent devil's-advocate review (subagent) on the screenshots and code.
7. Fix the shortcomings, re-render, and only then present, with the remaining weaknesses stated.

## Content accuracy

Clinical claims and demo values come from `web/lib/demo-data.ts` and the real helpers (`lib/evidence.ts`, `lib/evidence-levels.ts`, `lib/therapy-groups.ts`). Research prototype, not a medical device, oncologist review required. A score is not a probability of response.
