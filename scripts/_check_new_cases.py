"""Check top-3 drugs for potential new benchmark cases."""
import sys
import asyncio
sys.path.insert(0, '.')

import warnings
warnings.filterwarnings('ignore')

from api.ai.ranking import rank_candidates
from api.services.oncokb_evidence import get_all_drugs_for_variant_live


async def check(g, v, ct):
    drugs = get_all_drugs_for_variant_live(g, v, ct)
    if not drugs:
        print(f'NO_DRUGS: {g} {v} {ct}')
        return
    ranked = await rank_candidates(g, v, ct, drugs, vaf=0.4, tumour_purity=0.8)
    top3 = [r.drug for r in ranked[:3]]
    l1 = [k for k, lv in drugs.items() if lv == 'LEVEL_1']
    print(f'{g} {v} {ct}:')
    print(f'  L1={l1}')
    print(f'  top3={top3}')


async def main():
    cases = [
        ('ROS1', 'FUSION', 'Non-Small Cell Lung Cancer'),
        ('IDH1', 'R132C', 'Cholangiocarcinoma'),
        ('IDH1', 'R132H', 'Acute Myeloid Leukemia'),
        ('IDH2', 'R140Q', 'Acute Myeloid Leukemia'),
        ('IDH2', 'R172K', 'Acute Myeloid Leukemia'),
        ('FGFR3', 'FUSION', 'Bladder Cancer'),
        ('FGFR2', 'FUSION', 'Cholangiocarcinoma'),
        ('BRAF', 'V600E', 'Thyroid Cancer'),
        ('BRAF', 'V600E', 'Colorectal Cancer'),
        ('BRCA1', 'MUTATION', 'Ovarian Cancer'),
        ('BRCA2', 'MUTATION', 'Breast Cancer'),
        ('ATM', 'MUTATION', 'Prostate Cancer'),
        ('PALB2', 'MUTATION', 'Pancreatic Cancer'),
    ]
    for args in cases:
        await check(*args)

asyncio.run(main())
