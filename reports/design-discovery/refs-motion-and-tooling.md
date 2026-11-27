# Refs · Motion and product-demo tooling

Captured 2026-11-27. Scope: how a ranked therapy opens its evidence (Sotorasib, KRAS G12C, NSCLC sample case): click candidate → evidence summary (OncoKB level, sources) → gaps (missing data in amber). The founder's proposal is a portrait report sheet in the hero with a short loop recorded from the real demo app.

**How the observations were made.** Each site was loaded in a real browser. JS probes listed every `<video>` (src, `autoplay`, `loop`, `preload`, `poster`, duration, intrinsic size), checked play state against the viewport while scrolling, counted canvases and Lottie/Rive assets, and pulled all `@media (prefers-reduced-motion)` rules from the CSSOM. SSR HTML was fetched with curl as a cross-check, and poster/thumbnail frames were downloaded and inspected. Labels used below:

- **OBSERVED**: measured by me in this session.
- **INFERENCE**: my reading of what was observed. Not a fact.
- **UNVERIFIED**: claimed somewhere or plausible, but I didn't confirm it.

Caveat: most probes ran in a background browser tab, where browsers may throttle autoplay. "Paused in view" counts can therefore be low, but the structural facts (attributes, durations, sizes, CSS rules) are unaffected.

---

## Part A · Reference cards

### 1. Mercury: tabbed product loops plus a scroll-scrubbed hero

**Source:** https://mercury.com/: hero, then the section "Everything you do with money. All in one place." (tabs: Business banking & more / Cards & expense management / Payments & invoicing / Accounting).

**What the motion does (OBSERVED)**
- **Product loops.** Four MP4 clips (`/videos/hero/flow_1..4.mp4`): 8.0 s, 11.3 s, 9.4 s and 8.6 s, at 0.66–1.13 MB each. Posters are 1920×720 JPGs. None of the `<video>` elements carries `autoplay` or `loop`; playback is driven by script. In a foreground tab, flow_1 started when the section entered view and paused once scrolled 700 px past it. The section has a visible **Play** button, four tab buttons and "Go to item N" controls.
- **Cursor.** The poster frame shows a plain OS arrow cursor over one isolated "Accounts" card. The rest of the UI is dimmed and faded out. It reads as a composited render rather than a raw screen capture (INFERENCE).
- **Hero.** `hero-scrub-{sm,md,lg}.mp4` (6.4 s, lg 4.8 MB, sm 2.4 MB). It is muted with no autoplay and no loop. `currentTime` tracked scroll: 0 s at the top, 5.14 s at 285 px, 6.37 s at 700 px. It is a cinematic scene, not product UI.
- **Reduced motion.** The hero `<video>` has `motion-reduce:hidden`, and a `<picture>` start frame sits underneath it as the fallback. There are separate start frames for sm/md/lg/xl plus an **810×1440 portrait** frame served at `(orientation: portrait) and (max-aspect-ratio: 9/16)`. The page also has 15 `motion-reduce:transition-none` and 9 `motion-reduce:aria-hidden` utilities.

**Why it may work for OpenOncology (INFERENCE).** The flow clips do exactly our job: one panel, one cursor, one action, 8–11 s. Dimming everything except the active card maps onto "the evidence panel is what matters now". The Play button and pause-off-screen behaviour are the accessibility baseline we need.

**Where it could fail.** The composited, dimmed look is post-production. A raw Playwright capture won't look like this without an overlay or zoom step. The scroll-scrubbed hero is atmosphere, and copying it would be decoration without a job.

**Principle to adapt.** One clip per claim, 8–12 s, with the surrounding UI dimmed so the eye follows the cursor to the single panel that answers the question.

---

### 2. Dia (The Browser Company): real screen recordings, enlarged cursor, 4:5 crops

**Source:** https://www.diabrowser.com/: hero ("More than a browser. A better workday.") and the feature rows (e.g. "PROFILES").

**What the motion does (OBSERVED)**
- **Delivery.** Real screen recordings, delivered through Mux (HLS `stream.mux.com/*.m3u8` into an MSE `blob:` source). Attributes: `autoPlay muted playsInline loop preload="metadata"`, with a Mux `thumbnail.webp` as the poster.
- **Hero.** 22.0 s loop at 1516×1080.
- **Feature clips.** 4.8 s, 5.7 s and 6.4 s loops. Two are **860×1080, which is 4:5 portrait** (a crop of the browser's left sidebar plus part of the page); one is 1720×1080.
- **Cursor.** The hero frame at 3 s shows a recording in Windows window chrome with an **oversized yellow branded cursor** and a hand-drawn "Prep me…" sticker callout.
- **CMS.** The page data has per-block fields `type: video | image | lottie` and a separate `windowsAsset`, so Windows visitors get a Windows recording (OBSERVED in page JSON).
- **Off-screen behaviour.** The hero was paused in 10 of 10 off-screen samples. One feature clip kept playing off-screen in 5 samples. Behaviour is inconsistent.
- **Reduced motion.** Rules cover only marquees, `.app-tour` and a "what's new" bar. I found no evidence that the videos stop under reduced motion (UNVERIFIED either way).

**Why it may work for OpenOncology (INFERENCE).** This is the closest match to the founder's idea: short real recordings, cropped portrait. The 860×1080 crops show you can frame one column of an app (list plus detail) rather than shrinking a whole desktop window. An enlarged, brand-coloured cursor stays legible at hero scale.

**Where it could fail.** A playful sticker and cursor would undercut clinical credibility. HLS through Mux is a paid service and overkill for one clip. The autoplay loops ignore reduced motion, which we must not copy.

**Principle to adapt.** Crop the recording to the one column that tells the story, and make the cursor large enough to read at hero size, in a brand colour but not playful.

---

### 3. Cal.com: sticky, scroll-driven DOM walkthrough

**Source:** https://cal.com/workflows: the five-step section "Trigger → Timing → Text message → Email → After the call". Same pattern on `/routing`, `/assistant`, `/smart-routing` and `/app` (`story-step` present in SSR).

**What the motion does (OBSERVED)**
- **Structure.** No video. A sticky DOM product panel ("When new event is booked · Active on Discovery call · Wait until 24 hours before event…") sits beside five text steps in a 2,918 px section.
- **State changes on scroll.** Each step gets `data-active="true"`. The panel's camera element translates from `-43px` to `-169px` to `-312.5px` to `-465px`, and the workflow nodes move from `data-status="pending"` to `"active"` to `"done"`.
- **Reduced motion.** `.story-step`/`.story-frame` transitions drop to 80 ms with `translate: none`, and `.wf-callout` animation drops to 1 ms. **The states still change, but they snap instead of gliding.**
- **Cursor system.** The shared CSS bundle also defines `.flow-cursor`, `.flow-press`, `.flow-type`, `.wf-camera` and `.wf-callout`, which looks like a DOM cursor-walkthrough system. I couldn't locate the page that renders `.flow-cursor` (UNVERIFIED where it's used).
- **Homepage.** The h1 embeds a DOM booking chip ("Intro call · 30m · 4:00 PM · ✓ Booked"). Reduced-motion rules set `.appear`/`.feature-fly-in` to `opacity:1; animation:none`, so the end state shows.

**Why it may work for OpenOncology (INFERENCE).** "pending → active → done" is structurally the same as "candidate → evidence → gaps". A sticky report sheet with three captions scrolling past would let the reader control pace, which suits evidence reading better than a timed loop. Real DOM text stays sharp, selectable and translatable.

**Where it could fail.** It needs the panel rebuilt or driven as DOM states, which is more engineering than a clip and can drift from the real app. Scroll-jacking-adjacent patterns annoy readers if the section is too tall. At 320–390 px the sticky panel takes the whole viewport (Cal.com puts it first on mobile with `max-lg:sticky max-lg:top-0`).

**Principle to adapt.** Let scroll position, not a timer, decide which evidence state the sheet shows, and under reduced motion snap between the same states instead of removing them.

---

### 4. Linear: the hero product shot is the app, rendered as DOM

**Source:** https://linear.app/: hero ("The product development system for teams and agents"). Also https://linear.app/agents ("Watch example").

**What the motion does (OBSERVED)**
- **Homepage.** **No `<video>` and no canvas.** The hero product shot is a DOM replica of the app: sidebar (Inbox, My issues, Reviews, Projects…) and issue "DRV-8852 Faster app launch" with real-looking body text. That is 224 SVGs and 39 images, and the text is selectable.
- **Motion.** All CSS/SVG (85 running animations, e.g. `grid-dot-*-upDown` at 2.8 s, infinite).
- **Reduced motion.** 40 `prefers-reduced-motion` rules, almost all written as **`@media (prefers-reduced-motion: no-preference) { …animation… }`**. Motion is opt-in, so reduced motion is the default state.
- **/agents.** Video is **click-to-play** inside a dialog: `cursor-video.mp4` at 1280×720 with `preload: auto`, a `thumb.png` poster and a YouTube link.

**Why it may work for OpenOncology (INFERENCE).** `oo-art-direction` already asks for "product proof from real components". Linear shows the top of that ladder: the hero is the product, crisp at every DPR, and indexable. Writing motion inside `no-preference` is the safest default for a clinical audience.

**Where it could fail.** Linear's hero is mostly static. It proves the UI exists, not how a result opens. Without a cursor or state change it doesn't do our "how does evidence open" job alone.

**Principle to adapt.** Write every motion rule inside `prefers-reduced-motion: no-preference`, so the still, fully legible report sheet is the default and motion is an enhancement.

---

### 5. Attio: a record filled with real content, no video

**Source:** https://attio.com/: hero ("Welcome to agentic revenue.") and "Self-building" (record view "Sarah Johnson · Compose email · Highlights · Summary").

**What the motion does (OBSERVED)**
- **Media.** No `<video>`. One canvas (480×764) in the "Universal Context™" section, and no Lottie or Rive assets loaded.
- **Hero.** A DOM meeting UI ("Product Demo w/ GreenLeaf · 10:00 · 28:14 · Meeting Transcript · Speakers").
- **Self-building.** A DOM person record with highlights and a summary. Its `.enrichment-scroll` container is a horizontal overflow scroller, and I found no scroll-linked transform at my viewport (1024 px).
- **Reduced motion.** 6 rules, including `.enrichment-scroll { transition: none }` and shortened navigation animations.

**Why it may work for OpenOncology (INFERENCE).** Attio sells a record (a person and what is known about them) much as we sell a candidate and the evidence behind it. A record that shows filled fields next to explicitly empty ones is the visual we need for gaps.

**Where it could fail.** I didn't observe the motion that fills the record (it may need a wider viewport or foreground tab: UNVERIFIED). Taken as a still, it is a reference for layout, not motion.

**Principle to adapt.** Show the evidence record with real field labels, so missing values (VAF, depth) read as a fact about the case, not as a loading state.

---

### 6. Resend: counter-reference, motion with no product job

**Source:** https://resend.com/: the 3D cube and section icons ("broadcast", "react", "control").

**What the motion does (OBSERVED).** Four `<video>` elements, each `muted playsInline loop disablePictureInPicture` with a `poster` fallback JPG. The section icons use `preload="none"`, and the hero cube is 225–255 px `autoPlay` with an `/static/cube.mp4` source under `max-width: 1023px`.

**Why it is here (INFERENCE).** The plumbing is right: poster fallback, `preload="none"` below the fold, no picture-in-picture. The motion itself is decorative 3D that doesn't show the product.

**Where it could fail for us.** Anything that animates for mood (a spinning molecule, a DNA helix, a glowing genome) would be the same mistake, and helices are already on the rejected list.

**Principle to adapt.** Copy the delivery hygiene (poster, `preload="none"` off-hero, no PiP) and never the decorative subject.

---

### Patterns across the six

| | Mercury | Dia | Cal.com | Linear | Attio | Resend |
|---|---|---|---|---|---|---|
| Medium | MP4 (render) | HLS real recording | DOM | DOM | DOM | MP4 decor |
| Trigger | in-view + tabs; hero scroll-scrub | autoplay loop | scroll (sticky) | static / CSS loops; click-to-play video on /agents | static | autoplay / lazy |
| Loop length | 8–11 s | 4.8–6.4 s (feature), 22 s (hero) | n/a (scroll) | n/a | n/a | short |
| Cursor | plain OS arrow | enlarged yellow | DOM cursor classes exist (unlocated) | none on homepage | none seen | none |
| Pause control | visible Play button | none seen | n/a | n/a | n/a | none |
| Off-screen | pauses | mostly pauses | n/a | n/a | n/a | not tested |
| Reduced motion | video hidden → still frame | not handled for video | snap states (80 ms) | motion opt-in (`no-preference`) | transitions off | not checked |

**Takeaway (INFERENCE).** The best-in-class sites split two ways. **Real or rendered video** for "watch someone do it" (Mercury, Dia) is short, single-purpose and pauses. **DOM states** for "here is the product" (Linear, Cal.com, Attio) are sharp and accessible by construction. None of them uses GIF.

---

## Part B · Tooling to produce the clip from the real app

The real app already runs deterministically in demo mode (`NEXT_PUBLIC_ENABLE_DEMO_AUTH=1`, production build on :3100, sample case from `web/lib/demo-data.ts`). The Playwright installed in `web/` is **@playwright/test 1.63.0** (`playwright` ^1.61.1). GSAP ^3.15.1 and framer-motion ^11.2.10 are installed. **ffmpeg and gifski are not installed** on this machine.

### Options compared

| Option | License | Maintenance | Windows | Output quality | Effort |
|---|---|---|---|---|---|
| **Playwright `page.screencast` + ffmpeg** | Apache-2.0 (Playwright); ffmpeg LGPL/GPL depending on build | Active. Screencast API since **1.59**; `showActions({cursor:"pointer"})` since **1.61**; VP9 encoding, `fps` option, eased cursor path and CSS `style` for the cursor/highlight since **1.64** (release notes) | Yes (already runs our E2E) | Good for UI. Built-in output is WebM (VP9 from 1.64). Default frame size is the viewport scaled to fit 800×800, so `size` must be set explicitly. Whether frames are captured at `deviceScaleFactor` 2 is UNVERIFIED; the `onFrame` JPEG stream with `quality` 0–100 is the fallback for full control | Low. Reuses the E2E boot; a script of about 40 lines |
| Playwright `recordVideo` (older API) | Apache-2.0 | Maintained | Yes | Same encoder; `video.show.actions` adds action titles and outlines | Lowest, less control |
| **Remotion** (React → MP4) | Source-available, not OSI. Free for "an individual", "a for-profit organization with up to 3 employees", non-profits, and evaluation. Otherwise a Company License: Creators **$25/seat/month**, Automators **$0.01/render, $100/month minimum**, Enterprise from **$500/month**. The LICENSE notes Remotion 5.0 "will slightly change" the terms | Very active | Yes | Excellent (frame-exact, any resolution, crisp) | High. You rebuild the UI as Remotion compositions, so it is **not the real app**, and that defeats the founder's "real demo app" requirement |
| **Live DOM + GSAP** (no video) | GSAP "standard no-charge license" (Webflow): commercial use allowed; prohibited only in visual no-code animation builders competing with Webflow. Not OSI | Active | n/a | Perfect sharpness at any DPR, real text, themable | Medium–high. You drive real components through scripted states; `gsap.matchMedia()` with `reduceMotion: "(prefers-reduced-motion: reduce)"` reverts and re-runs when the preference toggles |
| **GIF via gifski** | gifski: "AGPL 3 or later", commercial licence offered (supso.org). The AGPL covers the tool, not the GIFs it outputs (INFERENCE, not legal advice) | Maintained; Windows `.msi` 1.14.4 | Yes | Best-looking GIF encoder, but still a 256-colour palette per frame, large files, no native pause | Low. ffmpeg pipes `yuv4mpegpipe` into gifski |
| **OpenScreen** (Screen Studio-style) | MIT | **Archived, "no longer maintained"**, pointing to `getopenscreen/openscreen`; the author says "not production grade" | Yes (winget/.exe) | Auto-zoom following the cursor, cursor size, smoothing, click effects; MP4/GIF export in several aspect ratios (4:5 not named) | Manual recording, so it doesn't reproduce in CI |
| **Recordly** (OpenScreen fork) | README badge says AGPL-3.0 (UNVERIFIED against the LICENSE file) | Active per press (1.3.x betas) | Yes, native capture | Screen Studio-like cursor animation and zoom (reviews; UNVERIFIED by me) | Manual |
| **Cap** | AGPLv3 (some crates MIT) | Active, 25.7k stars | Yes | Studio mode with zooms, backgrounds, trims; auto-zoom and cursor size not documented in the README | Manual |
| **ghost-cursor** | MIT | 1.6k stars, no releases listed | n/a (library) | Bézier, Fitts's-law mouse paths. Puppeteer API; `path()` is browser-agnostic, so it could feed Playwright `mouse.move` steps. `installMouseHelper` is debug-only | Low–medium. Mostly superseded by Playwright 1.64's eased action cursor |

### Format facts that decide the encode (verified on caniuse, 2026-11-27)

- **WebM.** Full support in Safari macOS 16+ and Safari iOS 17.4+; partial on earlier versions. Chrome, Firefox and Edge are fully supported.
- **AV1.** Chrome 70+, Firefox 67+ and Edge 121+ support it. Safari 17+ has only **partial** support. My understanding is that Safari decodes AV1 only on devices with hardware decoders (prior knowledge, UNVERIFIED here). An MP4/H.264 fallback is therefore mandatory.
- **GIF.** No pause, no `poster`, no `preload`, 256 colours per frame. UI recordings with antialiased text band and dither, and files typically run several times the MP4 size (INFERENCE from encoder design, not measured here). Reduced motion can be honoured with `<picture><source media="(prefers-reduced-motion: reduce)" srcset="still.png"><img src="loop.gif"></picture>`, but the WCAG 2.2.2 pause requirement (auto-moving content over 5 s) still needs JS.

### Recommendation: one pipeline

**Record the real demo app with Playwright `page.screencast`, then encode with ffmpeg to AV1-or-VP9 WebM plus H.264 MP4, with a final-state poster. Serve it in a `<video>` that pauses off-screen, has a visible pause button, and becomes a still under reduced motion.**

Why this one:
1. **It is the real app.** It records `/lab/results` from the same demo-mode production build the E2E suite already boots. Nothing is re-drawn, which matters for a clinical-evidence product. Remotion and hand-built GSAP scenes both re-create the UI and can drift from what the app actually shows.
2. **It is reproducible.** The clip regenerates whenever the UI changes, from one command, on Windows/Git Bash, with no paid service. Manual recorders (OpenScreen, Recordly, Cap) look nicer but can't be re-run in CI.
3. **The cursor is solved in-tool.** `screencast.showActions({ cursor: "pointer", style: { point, highlight, title } })` draws an eased cursor between real clicks. It needs **Playwright ≥ 1.64** (we have 1.63), so bump `@playwright/test` and `playwright` together.
4. **Video beats GIF** on sharpness, size, pause control and posters. A DOM version (the Cal.com scroll pattern) stays as the stronger option for a later scroll section below the hero (see the note at the end).

**Recording spec**
- **Boot.** Reuse `web/playwright.config.ts` `webServer` (demo mode, :3100) through a separate Playwright project or a standalone script under `web/`.
- **Not in `scripts/**`.** Root `scripts/**` is a protected path under the repo guard hook.
- **Viewport.** 540×675 CSS px (4:5) with `deviceScaleFactor: 2`, and `screencast.start({ path, size: { width: 1080, height: 1350 }, fps: 30 })`. If the output turns out soft (DPR capture UNVERIFIED), switch to `onFrame` at `quality: 95`, or to a viewport of 1080×1350 with the page zoomed to 200% via CSS, then pipe frames to ffmpeg.
- **Determinism.** Fixed fonts loaded, `page.emulateMedia({ reducedMotion: "no-preference" })`, and explicit `waitFor` on each panel before the next click.

**Storyboard (12 s, seamless loop)**

| Time | Shot |
|---|---|
| 0.0–1.5 s | Candidates list at rest. Sotorasib 0.98 and Adagrasib 0.97 both visible, with the near-tie note. **Don't crop #2 out**, because the required near-tie state must survive. "Sample case, not a patient" visible in frame. |
| 1.5–2.5 s | Cursor travels to Sotorasib; click. |
| 2.5–6.0 s | Evidence summary opens: OncoKB Level 1, sources OncoKB · OpenTargets · ClinVar. Dwell long enough to read one line. |
| 6.0–7.0 s | Cursor to "Gaps 10"; click. |
| 7.0–10.5 s | Amber missing fields (VAF, read depth) and "oncologist sign-off pending". |
| 10.5–12.0 s | Hold, then a 300 ms crossfade back to frame 0. Done in ffmpeg, or by recording a return click. |

**Encode (ffmpeg, Windows: `winget install Gyan.FFmpeg`)**
- **AV1 WebM.** `-c:v libsvtav1 -crf 38 -preset 6 -an`, or VP9 `-c:v libvpx-vp9 -b:v 0 -crf 36 -row-mt 1 -an`.
- **MP4 fallback.** `-c:v libx264 -crf 24 -preset slow -pix_fmt yuv420p -movflags +faststart -an`.
- **Strip audio** (`-an`).
- **Constant frame rate 30.** UI recordings could drop to 24 if the size budget is tight.

**Delivery**

| | Value |
|---|---|
| Aspect | **4:5** portrait report sheet. The 860×1080 Dia crops confirm the frame works for one app column; 3:4 if the sheet needs more width for HGVS strings. |
| Master / served | 1080×1350 master. Serve 1080×1350 to ≥1024 px viewports (sheet about 440–540 CSS px wide at 2×) and 720×900 to phones via `<source media>`. |
| Size budget | **≤ 1.2 MB WebM, ≤ 2.0 MB MP4** for 12 s. Benchmark: Mercury's 8–11 s flow clips are 0.66–1.13 MB at 1920×720. Phone variant ≤ 600 KB. |
| Poster | The **final state** (evidence open, gaps in amber), exported from the same run with `page.screenshot` at DPR 2. AVIF ≤ 80 KB, JPG fallback ≤ 150 KB. It doubles as the reduced-motion still and the no-JS state, and it is the frame that carries the claim. |
| Markup | `<video muted playsinline loop preload="metadata" poster=… disablepictureinpicture aria-describedby=…>` with WebM then MP4 `<source>`s. No `autoplay` attribute: start from an IntersectionObserver only when the visitor has no motion preference, and pause when out of view (Mercury). |
| Pause control | A visible pause/play button (Mercury's "Play"). Required by WCAG 2.2.2 for auto-playing content over 5 s. |
| Reduced motion | Never autoplay. Show the poster still with the three-step caption ("Click a candidate → see its evidence → see what's missing"). The play button remains so the visitor can opt in. Write motion CSS inside `prefers-reduced-motion: no-preference` (Linear). |
| Text alternative | Put the three steps as real text in a `<figcaption>` or visually hidden ordered list next to the video. The clip is illustrative, the text is the content. |

**Note: what DOM is better for (INFERENCE).** The Cal.com sticky pattern (sheet pinned, three captions scroll past, states snap under reduced motion) is the better medium **below the hero**, where readers want to set the pace. It would reuse the real workspace components and GSAP `matchMedia`, and the video would then serve as the hero teaser.

---

## Sources

- Mercury homepage: https://mercury.com/ (video assets `/videos/hero/flow_1..4.mp4`, `hero-scrub-*.mp4`, start frames under `/_next/static/media/hero_start_frame_*`)
- Dia: https://www.diabrowser.com/ (Mux thumbnails `image.mux.com/…/thumbnail`)
- Cal.com Workflows: https://cal.com/workflows; also /routing, /assistant, /smart-routing, /app
- Linear: https://linear.app/ and https://linear.app/agents
- Attio: https://attio.com/
- Resend: https://resend.com/
- Also checked, not carded: https://www.raycast.com/ (DOM keyboard and launcher, no video), https://stripe.com/ (DOM plus 2 WebGL canvases, no video), https://clerk.com/ (live DOM auth components, no video, no reduced-motion CSS found), https://arc.net/ (no video in SSR)
- Playwright videos: https://playwright.dev/docs/videos
- Playwright release notes (1.59 screencast, 1.61 cursor, 1.64 VP9/fps/style): https://playwright.dev/docs/release-notes
- Playwright Screencast API: https://playwright.dev/docs/api/class-screencast
- Remotion license: https://raw.githubusercontent.com/remotion-dev/remotion/HEAD/LICENSE.md and pricing https://www.remotion.dev/docs/license/pricing
- gifski: https://github.com/ImageOptim/gifski
- GSAP licensing: https://gsap.com/licensing/
- `gsap.matchMedia()`: https://gsap.com/docs/v3/GSAP/gsap.matchMedia()
- OpenScreen: https://github.com/siddharthvaddem/openscreen
- Recordly README: https://raw.githubusercontent.com/webadderallorg/Recordly/main/README.md
- Cap: https://github.com/CapSoftware/Cap
- ghost-cursor: https://github.com/Xetera/ghost-cursor
- caniuse AV1: https://caniuse.com/av1
- caniuse WebM: https://caniuse.com/webm
