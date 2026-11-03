"""Builds frontend/src/lib/countries-data.ts: every country / region with its English name and phone code.

    cd backend && .venv/Scripts/python ../scripts/make_countries.py

No new package: the phone codes come from `phonenumbers` (already a backend requirement), the English
names from Node's built-in Intl.DisplayNames. Run it again when phonenumbers is upgraded.
"""
import json
import subprocess
from pathlib import Path

import phonenumbers

OUT = Path(__file__).resolve().parents[1] / "frontend" / "src" / "lib" / "countries-data.ts"

codes = {region: phonenumbers.country_code_for_region(region) for region in sorted(phonenumbers.SUPPORTED_REGIONS)}
names = json.loads(subprocess.run(
    ["node", "-e", "const d = new Intl.DisplayNames(['en'], { type: 'region' });"
                   "process.stdout.write(JSON.stringify(Object.fromEntries(JSON.parse(process.argv[1]).map((c) => [c, d.of(c)]))))",
     json.dumps(list(codes))],
    check=True, capture_output=True, text=True).stdout)

# The main country of a shared code (+1 is the United States, +44 the United Kingdom, +7 Russia)
main = {d: phonenumbers.region_code_for_country_code(d) for d in set(codes.values())}
rows = sorted(({"code": c, "name": names[c], "dial": str(d), "main": main[d] == c} for c, d in codes.items()),
              key=lambda r: r["name"])
lines = [f"  ['{r['code']}', {json.dumps(r['name'], ensure_ascii=False)}, '{r['dial']}', {str(r['main']).lower()}],"
         for r in rows]
OUT.write_text(
    "// Made by scripts/make_countries.py (do not edit by hand):\n"
    "// [ISO code, English name, phone code, main country of that code (+1 = United States)].\n"
    "export const COUNTRY_ROWS: [code: string, name: string, dial: string, main: boolean][] = [\n"
    + "\n".join(lines) + "\n];\n",
    encoding="utf-8", newline="\n")
print(f"{len(rows)} countries -> {OUT}")
