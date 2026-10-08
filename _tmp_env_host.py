from pathlib import Path

root = Path(r"C:\Users\arthu\ribdigi-erp-production")
for name in (".env", "backend/.env", "frontend/.env", "frontend/.env.local"):
    path = root / name
    print(name, path.exists())
    if not path.exists():
        continue
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith(("DATABASE_URL=", "REDIS_URL=", "NEXT_PUBLIC_API")):
            key, val = line.split("=", 1)
            val = val.strip().strip('"').strip("'")
            host = val.split("@", 1)[-1].split("/", 1)[0]
            print(key, host[:100])
