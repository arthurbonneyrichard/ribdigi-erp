from pathlib import Path
p = Path(r"C:\Users\arthu\ribdigi-erp-production\frontend\app\globals.css")
text = p.read_text(encoding="utf-8")
for key in ["list-page-head", "list-pager", "list-btn-primary", "list-sort", "list-toast"]:
    i = text.find("." + key if not key.startswith(".") else key)
    # search without assuming
    idx = text.find(key)
    print(key, idx)
    if idx >= 0:
        print(text[max(0, idx-80): idx+400])
        print("---")
