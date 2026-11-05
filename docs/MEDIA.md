# Repository media

The README uses a presentation mockup to explain evidence review. Its workbench composition draws on [Hoppscotch](https://github.com/hoppscotch/hoppscotch). The styled components come from [HeroUI 2.8.10](https://v2.heroui.com/docs/components/listbox): selectable Listbox rows, circular Avatar rank markers, Chip status pills, Tabs, Accordion, Breadcrumbs and Button. Cursor motion is adapted from [RemotionUI](https://github.com/riaz37/remotion-ui). The palette uses Radix Slate neutrals, white surfaces, graphite text and a Blue accent. Amber marks the off-label status. Only the selected drug receives a filled background; the other candidates remain open list rows.

## Current showcase

| Asset | Purpose |
| --- | --- |
| `assets/showcase-demo.gif` | Ten-second loop: inspect source annotations, select Adagrasib, return to the opening view |
| `assets/showcase-demo.mp4` | Higher-quality version with playback controls in a video viewer |
| `assets/showcase-poster.png` | Static view of the same presentation |

The content comes from the current demonstration fixtures in `web/lib/demo-data.ts`. The layout differs from the running app and is labelled as a presentation mockup. The list explicitly labels Rank 1 (Sotorasib), Rank 2 (Adagrasib) and Rank 3 (Osimertinib), matching the existing demonstration order. Numeric demo scores are displayed separately. Rank 3 retains its different-indication warning; its position does not make it a validated match. Scores and source labels are illustrative demo output. The animation does not run a genomic pipeline, retrieve live evidence or demonstrate clinical validity.

Earlier screenshots and diagrams remain for existing links. The showcase caption identifies which visuals are presentation mockups.

## Production notes

The showcase is a 1280 x 740 Remotion composition at 30 frames per second. The GIF uses every second frame, giving 15 frames per second. Settled intervals remain still, the cursor lands at the active controls, and the final transition returns to the opening view. No blur, vignette or colour tint is applied.

The [editable source package](assets/showcase-source.zip) includes the composition, styles, loop-reset still, pinned direct dependencies and upstream MIT notices. Raw captures and editing files stay outside the tracked repository. Preserve library notices when moving or publishing copied source.

The separately captured current frontend is a content reference, not the source of the mockup's layout. A recording and a presentation mockup should always be captioned differently.

## Refresh and review

1. Check names, mechanisms and source labels against the current demo fixtures. Do not invent clinical claims to fill the design.
2. Keep the presentation label visible. Use a recording caption only for footage of the running frontend.
3. Inspect candidate selection, evidence, source annotations and the loop boundary. A poster alone does not verify motion.
4. Compare GIF text quality and file size at GitHub's rendered width.
5. Check light and dark backgrounds, provide a static alternative, and keep papers and methods accessible as ordinary Markdown links.

GitHub displays GIFs in README images. The MP4 and poster links provide alternatives for playback controls or no motion. The local review page includes controls and a static-view option; GitHub playback still needs verification after publication.
