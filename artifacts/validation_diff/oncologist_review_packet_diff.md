# Oncologist Review Packet Diff (Before vs After)

- Before run: 2026-05-02T03:46:22.407112+00:00
- After run: 2026-05-03T13:35:18.424510+00:00
- Cases total: 24
- Difficult cases reviewed: 13
- Difficult cases with top-3 changes: 12
- Auto-pass flips: 0

## Metrics Delta

- Standard P@3: 0.5625 -> 0.5789 (delta +0.0164)
- Normalized P@3: None -> 0.9825 (delta +0.9825)
- Hit@3: 1.0 -> 1.0 (delta +0.0000)
- MRR: None -> 0.9211 (delta +0.9211)
- NDCG@3: None -> 0.9355 (delta +0.9355)
- False positives: 0 -> 0 (delta +0)

## Difficult Case Top-3 Changes

- BLIND-001 | KIT EXON17MUT | GIST | L3_L4
  - Before: Olaparib, Niraparib, Rucaparib
  - After: Avapritinib, Ripretinib
- BLIND-002 | IDH2 R140Q | Relapsed Refractory AML | L3_L4
  - Before: (none)
  - After: Enasidenib, Azacitidine
- BLIND-003 | FAT1 truncation | Non-Small Cell Lung Cancer | VUS_NEG
  - Before: Belzutifan
  - After: (none)
- BLIND-004 | TSC2 MUTATION | Lymphangioleiomyomatosis | L3_L4
  - Before: (none)
  - After: Everolimus, Temsirolimus
- BLIND-006 | MYC Amplification | Diffuse Large B-Cell Lymphoma | VUS_NEG
  - Before: Venetoclax
  - After: (none)
- BLIND-007 | SMARCA4 Loss_of_Function | Non-Small Cell Lung Cancer | L3_L4
  - Before: Enasidenib
  - After: Tazemetostat
- BLIND-009 | TSC2 truncation | Clear Cell Renal Cell Carcinoma | VUS_NEG
  - Before: Trastuzumab, Trastuzumab Deruxtecan, Pertuzumab
  - After: (none)
- BLIND-016 | PIK3CA E542K | Endometrial Cancer | L3_L4
  - Before: Selpercatinib, Pralsetinib, Vandetanib
  - After: Alpelisib
- BLIND-017 | SMARCA4 Loss_of_Function | Ovarian Cancer | L3_L4
  - Before: Vemurafenib, Dabrafenib, Trametinib
  - After: Tazemetostat
- BLIND-020 | CD79B Y196C | Diffuse Large B-Cell Lymphoma | L3_L4
  - Before: Erdafitinib, Pemigatinib
  - After: Ibrutinib, Zanubrutinib, Acalabrutinib
- BLIND-023 | TET2 frameshift | Acute Myeloid Leukemia | VUS_NEG
  - Before: Mrtx1133
  - After: (none)
- BLIND-024 | NPM1 W288FS | Acute Myeloid Leukemia | L3_L4
  - Before: (none)
  - After: Azacitidine, Venetoclax

## Auto-Pass Outcome Flips

- No auto-pass outcome flips.
