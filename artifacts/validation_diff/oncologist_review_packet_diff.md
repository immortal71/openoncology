# Oncologist Review Packet Diff (Before vs After)

- Before run: 2026-05-02T03:46:22.407112+00:00
- After run: 2026-05-08T14:02:28.786851+00:00
- Cases total: 50
- Difficult cases reviewed: 16
- Difficult cases with top-3 changes: 16
- Auto-pass flips: 2

## Metrics Delta

- Standard P@3: 0.5625 -> 0.5083 (delta -0.0542)
- Normalized P@3: None -> 0.8167 (delta +0.8167)
- Hit@3: 1.0 -> 0.9 (delta -0.1000)
- MRR: None -> 0.8833 (delta +0.8833)
- NDCG@3: None -> 0.8827 (delta +0.8827)
- False positives: 0 -> 0 (delta +0)

## Difficult Case Top-3 Changes

- BLIND-002 | KIT EXON9MUT | Gastrointestinal Stromal Tumor | L3_L4
  - Before: (none)
  - After: Imatinib, Sunitinib, Regorafenib
- BLIND-003 | TMB TMB_High | Glioblastoma Multiforme | L3_L4
  - Before: Belzutifan
  - After: Pembrolizumab
- BLIND-004 | ARID1A Loss_of_Function | Ovarian Clear Cell Carcinoma | L3_L4
  - Before: (none)
  - After: Olaparib, Tazemetostat
- BLIND-006 | SMARCA4 Loss_of_Function | Non-Small Cell Lung Cancer | L3_L4
  - Before: Venetoclax
  - After: Tazemetostat
- BLIND-007 | KRAS G12V | Non-Small Cell Lung Cancer | L3_L4
  - Before: Enasidenib
  - After: (none)
- BLIND-008 | NPM1 W288FS | Acute Myeloid Leukemia | L3_L4
  - Before: Larotrectinib, Entrectinib
  - After: Azacitidine, Venetoclax
- BLIND-010 | TSC1 MUTATION | Renal Angiomyolipoma | L3_L4
  - Before: (none)
  - After: Everolimus, Temsirolimus
- BLIND-013 | MET AMPLIFICATION | Gastric Cancer | L3_L4
  - Before: Pemigatinib, Futibatinib, Infigratinib
  - After: Capmatinib, Tepotinib, Crizotinib
- BLIND-015 | TP53 R248H | Osteosarcoma | VUS_NEG
  - Before: Crizotinib, Lorlatinib
  - After: (none)
- BLIND-017 | NRAS Q61L | Colorectal Cancer | L3_L4
  - Before: Vemurafenib, Dabrafenib, Trametinib
  - After: Binimetinib
- BLIND-018 | SMARCB1 Loss_of_Function | Epithelioid Sarcoma | L3_L4
  - Before: Avapritinib, Imatinib
  - After: (none)
- BLIND-019 | PTEN truncation | Endometrial Cancer | L3_L4
  - Before: (none)
  - After: Everolimus, Temsirolimus
- BLIND-020 | FGFR2 AMPLIFICATION | Gastric Cancer | L3_L4
  - Before: Erdafitinib, Pemigatinib
  - After: Futibatinib, Pemigatinib, Erdafitinib
- BLIND-021 | EGFR AMPLIFICATION | Non-Small Cell Lung Cancer | L3_L4
  - Before: Everolimus, Temsirolimus
  - After: Cetuximab, Panitumumab, Erlotinib
- BLIND-022 | MTOR E1799K | Renal Cell Carcinoma | L3_L4
  - Before: (none)
  - After: Everolimus
- BLIND-023 | TSC2 truncation | Clear Cell Renal Cell Carcinoma | VUS_NEG
  - Before: Mrtx1133
  - After: (none)

## Auto-Pass Outcome Flips

- BLIND-007 | KRAS_G12V_NSCLC_EMERGING_01 | auto_pass True -> False
- BLIND-018 | LIT_SMARCB1_LOF_EPS_01 | auto_pass True -> False
