"""Inspect blind holdout cases."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from api.services.benchmark import ADDITIONAL_VALIDATION_CASES

print('Total ADDITIONAL_VALIDATION_CASES:', len(ADDITIONAL_VALIDATION_CASES))
singles = [c for c in ADDITIONAL_VALIDATION_CASES if len(c.get('known_drugs') or []) <= 1]
multis  = [c for c in ADDITIONAL_VALIDATION_CASES if len(c.get('known_drugs') or []) > 1]
print('Single-drug (<=1 known):', len(singles))
print('Multi-drug  (>1 known): ', len(multis))

print('\n=== MULTI-DRUG ===')
for c in multis:
    print(f"  {c['case_id']:50} {c.get('known_drugs')}")

print('\n=== SINGLE-DRUG/NEGATIVE ===')
for c in singles:
    print(f"  {c['case_id']:50} {c.get('known_drugs')}")
