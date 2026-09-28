import pathlib
p = pathlib.Path(r"frontend/app/(dashboard)/expenses/page.tsx")
t = p.read_text(encoding="utf-8")
i = t.find("async function refresh")
print("line", t[:i].count("\n") + 1)
print(t[i : i + 800])
