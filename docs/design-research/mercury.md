# Mercury (mercury.com): scroll-scrubbed hero

Observed on 2026-11-08 and 2026-11-09 on the live public page with browser DevTools: layout, computed styles, and video element state. No source code or assets were copied. Reviewed by an independent devil's-advocate pass; over-claims were removed.

## Measured

- **Scroll track:** the hero sits in a scroll track 250vh tall (1215px at a 486px viewport). Inside it, a `position: sticky` stage 100vh tall holds one muted `<video>`, which leaves 150vh of track beyond the stage.
- **Video:** 6.4 s long.
- **Playback follows scrolling:** in a visible tab on 2026-11-08, `currentTime` read about 1.3 s and then about 4.7 s as the page was scrolled down. The scroll positions for those two readings weren't recorded.
- **Three encodes by viewport width,** chosen by `<source media>`:
  - `hero-scrub-sm` by default;
  - `hero-scrub-md` from 40rem;
  - `hero-scrub-lg` from 64rem.

## Not established

- **Update mechanism:**
  - **What was seen:** in a hidden tab, `currentTime` stayed at 0 at every scroll position.
  - **Why that isn't conclusive:** hidden tabs also throttle scroll handlers and can pause media seeking, so this fits `requestAnimationFrame`, scroll handlers and paused seeking alike.
  - **How to settle it:** a Performance recording in a visible tab, noting whether "Animation Frame Fired" or "Scroll" comes before each seek.
- **Scroll distance per second of video, and whether the mapping is linear.**
  - **Needs:** about 10 `(scrollY, currentTime)` pairs taken evenly across the track, in a visible tab.
- **Smoothing:**
  - **Needs:** jump with `scrollTo`, then sample `currentTime` every animation frame for 500ms. Values that ease in over several frames would mean lerping.
- **Release:** what the last frame and the next section do at the end of the 250vh track.
- **Reduced motion:** behaviour with `prefers-reduced-motion: reduce` (DevTools > Rendering).
- **Frame cost:** dropped frames across the track at a 4x CPU throttle.
- **Phones:** only the `<source>` markup was read. Behaviour at 390px with touch emulation was not observed.
- **Keyframe interval** of the encodes.

## What OpenOncology takes

- **Runway:** 100vh sticky plus 150vh of progress, matching our 250vh hero cap. This is a layout pattern, not code.
- **Progress:** computed once per frame from the track's position. Our hero (concept A in `/lab/hero`) maps it to three discrete states, not to a video.
- **Product first:** the product is visible at frame 0, and scrolling adds depth.
- **Phones and reduced motion:** both get the static first frame. We don't ship a cut-down scrub.
- **Encoding for the later product film:** a keyframe on every frame for smooth seeking (plan v3, section 6). This is general video-encoding practice, not something measured on Mercury.
