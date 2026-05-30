#!/usr/bin/env python3
import csv
from pathlib import Path

path = Path('data/civic_evidence.tsv')
rows = []
with path.open(encoding='utf-8') as fh:
    reader = csv.DictReader(fh, delimiter='\t')
    for row in reader:
        rows.append(dict(row))

pred = [r for r in rows if r['evidence_type'].lower() == 'predictive'
        and r['evidence_status'].lower() == 'accepted'
        and r['therapies']]

print(f'Predictive accepted with therapies: {len(pred)}')
print()
print('Sample predictive rows:')
for r in pred[:5]:
    for k in ['molecular_profile', 'therapies', 'significance', 'evidence_level', 'disease']:
        print(f'  {k}: {r[k]}')
    print()

sigs = {r['significance'] for r in pred}
print('Unique significance values:', sorted(sigs))
