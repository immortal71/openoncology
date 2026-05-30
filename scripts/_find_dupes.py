"""Find duplicate tuple keys in _LEVEL_TABLE that silently clobber earlier entries."""
import re
import collections

with open("api/services/oncokb_evidence.py", encoding="utf-8") as f:
    lines = f.readlines()

pattern = re.compile(r'^\s+\("([A-Z0-9\-]+)",\s*"([^"]+)"\)\s*:\s*\{')
seen: dict = collections.defaultdict(list)
for i, line in enumerate(lines, 1):
    m = pattern.match(line)
    if m:
        key = (m.group(1), m.group(2))
        seen[key].append(i)

dupes = {k: v for k, v in seen.items() if len(v) > 1}
print(f"Total duplicate keys: {len(dupes)}")
for key, linenos in sorted(dupes.items()):
    print(f"  {key}  lines: {linenos}")
