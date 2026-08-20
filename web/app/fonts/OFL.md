# Bundled fonts

These files are served from the repository instead of fetched from Google at
build time. `next/font/google` downloads from `fonts.gstatic.com` while
compiling, and when the build machine cannot reach it the build dies with

    An error occurred in `next/font`.
    TypeError: Cannot read properties of null (reading '1')

which failed CI on pull requests that changed nothing about the frontend. The
job was intermittent, so neither a red nor a green run meant much.

| File | Family | Licence |
|---|---|---|
| `Manrope-Variable.woff2` | Manrope, variable 200-800 | SIL Open Font License 1.1 |
| `IBMPlexSans-400/500/600.woff2` | IBM Plex Sans | SIL Open Font License 1.1 |
| `JetBrainsMono-Variable.woff2` | JetBrains Mono, variable 100-800 | SIL Open Font License 1.1 |
| `Inter-Variable.woff2` | Inter, variable 100-900 | SIL Open Font License 1.1 |

All four are licensed under the SIL Open Font License 1.1, which permits
redistribution as part of a larger work. Latin subset only, matching the
`subsets: ["latin"]` the previous `next/font/google` configuration requested.

To refresh, download the latin `woff2` for each family from the Google Fonts
CSS API and replace the file in place; the declarations in `app/layout.tsx`
name the weights each file must cover.
