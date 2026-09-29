from pathlib import Path
p = Path(r"C:\Users\arthu\ribdigi-erp-production\frontend\app\(dashboard)\reports\page.tsx")
for i,l in enumerate(p.read_text(encoding="utf-8").splitlines(),1):
    if "loading" in l.lower() and ("Load" in l or "loading" in l):
        if i < 650 or "Loading" in l:
            print(f"{i}:{l.rstrip()[:140]}")
