import sys, asyncio, os
# Support running from any working directory
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ROOT, 'api'))
sys.path.insert(0, _ROOT)   # allows  'from api.xxx import'  patterns
from services.benchmark import run_hard_clinical_benchmark
r = asyncio.run(run_hard_clinical_benchmark())
# r is HardClinicalBenchmarkReport dataclass
p3 = r.mean_standard_precision_at_3
h3 = getattr(r, 'hit_rate_at_3', None)
print(f'P@3  = {p3:.4f}  ({p3*100:.1f}%)')
if h3 is not None:
    print(f'H@3  = {h3:.4f}  ({h3*100:.1f}%)')
print(r.summary())
