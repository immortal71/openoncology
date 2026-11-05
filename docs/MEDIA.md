# Documentation media

The README uses a static product screenshot for orientation and one short animation to demonstrate evidence review. Diagrams explain the workflow; they do not substitute for screenshots of the software.

## Current assets

| Asset | Use | Source |
|:--|:--|:--|
| `assets/readme-banner.svg` | README identity | Original vector artwork using the frontend's DNA mark |
| `assets/evidence-review.jpg` | Main product screenshot | Production build, KRAS G12C demonstration workspace |
| `assets/evidence-review.gif` | Expand a candidate and read its evidence | Captured closed/open UI states, assembled into a seven-second loop |
| `assets/frontend-home.jpg` | Frontend overview | Production build, homepage |
| `assets/case-workflow.svg` | Intended lab-to-oncologist workflow | Original vector diagram |

The screenshots show demonstration data. Scores and evidence labels are illustrative frontend output, not newly calculated benchmark results. The GIF is an edited sequence of actual UI captures, not a continuous recording or a live clinical run. No patient uploads or clinical sessions are included.

## Refresh screenshots

Build the frontend with `NEXT_PUBLIC_ENABLE_DEMO_AUTH=1`, then run the production server. Open `/workspace?demo=true`, select **Drug Results**, and expand a candidate. Keep the demonstration label visible in the overview screenshot. Production mode avoids the development toolbar.

Use a readable browser window, capture the application rather than the desktop, and check the result at the width GitHub will display it. Keep source references and labels legible. Caption the image and describe its purpose in alt text. Capture the homepage only after content has finished loading.

Keep static diagrams as SVGs so text stays sharp. Store final assets here and keep raw recordings, capture frames and temporary palettes outside the tracked repository.

## Make a short GIF from a video

Choose one action. For evidence review, show the candidate list, expand one candidate, hold the evidence long enough to read, and end cleanly. A six-to-eight-second clip is usually enough. Use a static screenshot beside or before the animation so readers do not need to watch it to understand the product.

With FFmpeg available, create a palette and apply it to the same trimmed clip:

```bash
ffmpeg -ss 0 -t 7 -i demo.mp4 -vf "fps=12,scale=930:-1:flags=lanczos,palettegen=stats_mode=diff" palette.png
ffmpeg -ss 0 -t 7 -i demo.mp4 -i palette.png -lavfi "fps=12,scale=930:-1:flags=lanczos[x];[x][1:v]paletteuse=dither=sierra2_4a" -loop 0 evidence-review.gif
```

Compare a smaller-width version with the full-width version. Prefer the smallest file that keeps the text readable. Lower frame rate helps with slow interface changes; it does not fix text that is too small. Avoid animating long page scrolls, loading screens or the entire upload pipeline.

## Review before publishing

Check that the captured version matches the proposed code, demonstration data is clearly identified, and visible labels support the accompanying claims. Review both static images and the animation. Keep the README's scientific scope statement linked to the full evaluation methods.
