#!/usr/bin/env python3
import csv
from pathlib import Path
from collections import defaultdict

path = Path('data/civic_evidence.tsv')
rows = []
with path.open(encoding='utf-8') as fh:
    reader = csv.DictReader(fh, delimiter='\t')
    for row in reader:
        rows.append(dict(row))

# Only sensitivity/response with level A or B
good = [r for r in rows if r['evidence_type'].lower() == 'predictive'
        and r['evidence_status'].lower() == 'accepted'
        and r['therapies']
        and r['significance'].lower() in ('sensitivity/response',)
        and r['evidence_level'] in ('A', 'B')]

print(f'High-confidence sensitivity rows (A/B): {len(good)}')
print()
print('Sample sensitivity/response rows (level A/B):')
for r in good[:20]:
    for k in ['molecular_profile', 'therapies', 'significance', 'evidence_level', 'disease']:
        print(f'  {k}: {r[k]}')
    print()

# Find unique molecular profiles for common oncogenes
oncogenes = ['EGFR', 'ALK', 'KRAS', 'BRAF', 'BRCA', 'ERBB2', 'IDH1', 'IDH2', 'RET', 'NTRK']
print('\nMolecular profiles for key genes (level A/B sensitivity):')
for gene in oncogenes:
    profiles = set()
    for r in good:
        mp = r['molecular_profile']
        if mp.startswith(gene):
            profiles.add(f"{mp} [{r['therapies']}] level={r['evidence_level']} disease={r['disease']}")
    if profiles:
        print(f'\n{gene}:')
        for p in sorted(profiles)[:10]:
            print(f'  {p}')
