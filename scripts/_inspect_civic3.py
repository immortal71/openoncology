#!/usr/bin/env python3
"""Show all high-confidence (A/B) sensitivity entries from CIViC"""
import csv
from pathlib import Path
from collections import defaultdict

path = Path('data/civic_evidence.tsv')
rows = []
with path.open(encoding='utf-8') as fh:
    reader = csv.DictReader(fh, delimiter='\t')
    for row in reader:
        rows.append(dict(row))

good = [r for r in rows if r['evidence_type'].lower() == 'predictive'
        and r['evidence_status'].lower() == 'accepted'
        and r['therapies']
        and r['significance'].lower() in ('sensitivity/response',)
        and r['evidence_level'] in ('A', 'B')]

# Show ALL unique molecular_profile -> therapies -> disease combos for level A
print("=== LEVEL A (Highest evidence) SENSITIVITY entries ===")
level_a = [r for r in good if r['evidence_level'] == 'A']
for r in sorted(level_a, key=lambda x: x['molecular_profile']):
    print(f"  {r['molecular_profile']} | {r['therapies']} | {r['disease']}")

print(f"\nTotal Level A: {len(level_a)}")

# Additional genes not covered
print("\n=== Missing/underrepresented genes ===")
genes_in_civic = defaultdict(list)
for r in good:
    mp = r['molecular_profile']
    gene = mp.split()[0].split('::')[0]
    genes_in_civic[gene].append(r)

known_genes = {
    'EGFR', 'ALK', 'ROS1', 'KRAS', 'BRAF', 'NRAS', 'RET', 'MET', 'ERBB2',
    'PIK3CA', 'BRCA1', 'BRCA2', 'IDH1', 'IDH2', 'FLT3', 'KIT', 'PDGFRA',
    'ABL1', 'JAK2', 'MPL', 'CALR', 'TP53', 'APC', 'VHL', 'PTEN',
    'FGFR1', 'FGFR2', 'FGFR3', 'NTRK1', 'NTRK2', 'NTRK3', 'NF1',
    'CDKN2A', 'CDK4', 'CDK6', 'CCND1', 'ESR1', 'AR', 'PALB2',
    'RAD51', 'ATM', 'CDK12', 'ARID1A', 'SMARCA4',
    'TSC1', 'TSC2', 'MTOR', 'STK11', 'MAP2K1', 'MAP2K2',
    'EZH2', 'DNMT3A', 'TET2', 'ASXL1', 'NPM1', 'RUNX1',
    'MLH1', 'MSH2', 'MSH6', 'PMS2', 'HRAS', 'NF2', 'SMO', 'PTCH1',
    'RB1', 'AKT1', 'AKT2', 'BCR', 'POLE', 'ERBB3', 'ERBB4',
}

for gene in sorted(genes_in_civic.keys()):
    entries = genes_in_civic[gene]
    level_a_count = sum(1 for r in entries if r['evidence_level'] == 'A')
    if gene not in known_genes or level_a_count > 0:
        print(f"  {gene}: {len(entries)} B entries, {level_a_count} A entries")
