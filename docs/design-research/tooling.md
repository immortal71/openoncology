# Tooling and anti-slop research (2026-11-09)

What to use for motion and components, and how to avoid the generic AI-generated look. The sources are 2026 web articles; several are vendor-adjacent, so version numbers and star counts were not relied on.

## Motion

- **Motion** (formerly framer-motion, imported from `motion/react` in newer versions) is the React-first, MIT-licensed choice for component animation: state changes, enter and exit, layout, and gestures. The repo already ships `framer-motion` 11.
- **GSAP** is now free, including its previously paid plugins such as ScrollTrigger and SplitText. Its `useGSAP()` hook from `@gsap/react` works alongside Motion in Next.js client components.
- **Decision:** Motion only, for now.
  - The hero (`decisions.md`, hero A) uses three discrete scroll states, which Motion's `useScroll` handles.
  - A second animation engine adds weight for no gain.
  - Reconsider GSAP only for a section that needs a long, timeline-driven sequence.
  - Plan v3's reason for skipping GSAP (its license) is outdated and no longer applies.
- **Lenis** smooth scrolling is often paired with ScrollTrigger. It stays optional (plan v3, section 9) and is added only if scenes feel steppy.

## Component and effect libraries

- **shadcn/ui-style structure plus Radix behaviour** is the common base. The repo already has Radix, and our own look lives in `components/oo`.
- **Not adopted:** Magic UI, Aceternity UI and React Bits. They are popular copy-and-paste effect collections, but their signature effects are animated beams, glowing borders, and gradient or blurred-blob backgrounds, which the anti-slop guides below list as AI tells.
  - One comparison notes React Bits ships `prefers-reduced-motion` handling that the others lack by default. If a single effect primitive is ever needed, check it there first, and only after it passes the ban list.

## Anti-slop guidance, and how we apply it

| Guidance (2026 sources) | Where we stand |
|---|---|
| Set the direction (type, color, spacing, motion) in writing before coding, for example in a DESIGN.md | `docs/design/decisions.md` holds the locked direction |
| Use real references | Measured references in `docs/design-research/` |
| Use visuals tied to the actual product, not imagery that fits any SaaS | The hero shows real demo output (variant track, ranked drugs) |
| Audit against a ban list of AI defaults | Added to `decisions.md` and used in every devil's-advocate review |
| No skill avoids slop on its own | Treat skills as helpers; the decisions are brand-specific |

## Sources

- [Motion vs GSAP (OpenReplay)](https://blog.openreplay.com/motion-vs-gsap/)
- [Motion vs GSAP in React (Syncfusion)](https://www.syncfusion.com/blogs/post/motion-vs-gsap-react)
- [Best React animation libraries 2026 (PkgPulse)](https://www.pkgpulse.com/guides/best-react-animation-libraries-2026)
- [Why AI design looks generic (Superdesign)](https://www.superdesign.dev/blog/why-ai-design-looks-generic)
- [Fix a generic AI landing page (Superdesign)](https://superdesign.dev/blog/fix-generic-ai-landing-page)
- [AI slop web design guide (925 Studios)](https://www.925studios.co/blog/ai-slop-web-design-guide)
- [AI design slop: overused UI patterns (Noqta)](https://noqta.tn/en/blog/ai-design-slop-overused-ui-patterns-fix-2026)
- [Anti AI slop ban list (GitHub wiki)](https://github.com/Laith0003/ux-skill/wiki/Anti-AI-slop-ban-list)
- [React Bits vs Aceternity vs Magic UI (PkgPulse)](https://www.pkgpulse.com/guides/react-bits-vs-aceternity-magic-ui-2026)
- [Animated UI component libraries (WrapPixel)](https://www.wrappixel.com/animated-ui-component-libraries/)
