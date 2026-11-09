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
| `IBMPlexMono-Variable-Latin1.woff2` | IBM Plex Mono, variable 100-700 | SIL Open Font License 1.1 |
| `Inter-Variable.woff2` | Inter, variable 100-900 (used by `/workspace`) | SIL Open Font License 1.1 |
| `SourceSerif4Display-Semibold.woff2` | Source Serif 4 Display, Semibold | SIL Open Font License 1.1 |

All are licensed under the SIL Open Font License 1.1, which permits
redistribution as part of a larger work. Manrope, IBM Plex Sans and Inter are
Latin subsets, matching the `subsets: ["latin"]` the previous
`next/font/google` configuration requested.

The two newer files are the publishers' own files, unmodified:

- `IBMPlexMono-Variable-Latin1.woff2` is `IBM Plex Mono Var-Roman-Latin1.woff2`
  from IBM's `@ibm/plex-mono-variable@1.0.0` release
  (github.com/IBM/plex). Copyright © 2017 IBM Corp. with Reserved Font Name
  "Plex".
- `SourceSerif4Display-Semibold.woff2` is
  `TTF/SourceSerif4Display-Semibold.ttf.woff2` from Adobe's `4.005R` release
  (github.com/adobe-fonts/source-serif). Copyright 2014 - 2023 Adobe, with
  Reserved Font Name 'Source'.

Both families declare a Reserved Font Name, so these files are not subset or
otherwise modified here; a modified copy would have to be renamed.

To refresh the Google-sourced files, download the latin `woff2` for each
family from the Google Fonts CSS API and replace the file in place. For the
two newer files, take the same file from a newer release of the publisher's
repository. The declarations in `app/layout.tsx` and `lib/display-font.ts`
name the weights each file must cover.
