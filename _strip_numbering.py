from pathlib import Path

root = Path(r"frontend/app/(dashboard)")


def cut(t: str, start_s: str, end_s: str) -> str:
    start = t.index(start_s)
    end = t.index(end_s, start + len(start_s))
    return t[:start] + t[end:]


p = root / "purchasing/page.tsx"
t = p.read_text(encoding="utf-8")
t = cut(t, "  const [poPrefix, setPoPrefix] = useState('PO');\n", "  async function refresh() {")
t = t.replace("      api('/purchasing/settings').catch(() => ({ data: null })),\n", "")
t = t.replace(
    "    const [poRes, prRes, settingsRes, numRes, supRes, prodRes, unitRes, whRes, grnRes, invRes, retRes] =",
    "    const [poRes, prRes, settingsRes, supRes, prodRes, unitRes, whRes, grnRes, invRes, retRes] =",
)
t = cut(t, "    const poNum = numRes.data?.purchase_order_numbering;\n", "  }\n\n  useEffect(() => {")
t = cut(t, "  async function savePurchasingNumbering() {", "  function updatePrLevel(")
t = cut(
    t,
    "          <div className=\"card\" style={{ marginBottom: 16 }}>\n            <h3>Document numbering</h3>",
    "          <div className=\"card\" style={{ marginBottom: 16 }}>\n            <h3>PR approval matrix</h3>",
)
p.write_text(t, encoding="utf-8")
print("purchasing ok")

p = root / "inventory/page.tsx"
t = p.read_text(encoding="utf-8")
t = cut(t, "  const [trPrefix, setTrPrefix] = useState('TR');\n", "  async function refresh() {")
t = t.replace("      apiOptional('/inventory/settings'),\n", "")
t = t.replace(
    "    const [p, e, c, b, u, w, sc, os, rates, settings] = await Promise.all([",
    "    const [p, e, c, b, u, w, sc, os, rates] = await Promise.all([",
)
t = cut(t, "    const trNum = settings.data?.stock_transfer_numbering;\n", "    if (!countWarehouseId && w.data?.length)")
t = cut(t, "  async function saveInventoryNumbering() {", "  async function refreshSelected(id: string) {")
t = cut(
    t,
    "      {(tab === 'opening' || tab === 'counts' || tab === 'transfers') && (\n      <div className=\"card\" style={{ marginBottom: 16, display: 'grid', gap: 8 }}>\n        <strong>Document numbering</strong>",
    "      {tab !== 'products' &&",
)
p.write_text(t, encoding="utf-8")
print("inventory leftover", "Document numbering" in t, "saveInventoryNumbering" in t)

p = root / "expenses/page.tsx"
t = p.read_text(encoding="utf-8")
t = cut(t, "  const [expPrefix, setExpPrefix] = useState('EXP');\n", "  const [recurring, setRecurring]")
t = cut(t, "    const num = settings.data?.expense_numbering;\n", "    if (!recCategoryId && (cats.data || []).length) {")
t = cut(t, "  async function saveExpenseNumbering() {", "  function updateLevel(")
t = cut(
    t,
    "      <div className=\"card\" style={{ display: 'grid', gap: 8 }}>\n        <strong>Document numbering</strong>",
    "      <div className=\"card\" style={{ marginBottom: 16 }}>\n        <h3>Approval matrix</h3>",
)
p.write_text(t, encoding="utf-8")
print("expenses leftover", "saveExpenseNumbering" in t, "Document numbering" in t)

p = root / "accounting/page.tsx"
t = p.read_text(encoding="utf-8")
t = cut(t, "  const [jePrefix, setJePrefix] = useState('JE');\n", "  const [newAcctNumber, setNewAcctNumber]")
t = t.replace("      api('/accounting/settings').catch(() => ({ data: null })),\n", "")
t = t.replace(
    "    const [a, j, t, p, liq, stmts, conns, xfers, openSt, st, br, per, settings] = await Promise.all([",
    "    const [a, j, t, p, liq, stmts, conns, xfers, openSt, st, br, per] = await Promise.all([",
)
t = cut(t, "    const jeNum = settings.data?.journal_numbering;\n", "    if (!closeThrough && per.data?.books_closed_through) {")
t = cut(t, "  async function saveAccountingNumbering() {", "  async function closeBooks() {")
t = cut(
    t,
    "          <div className=\"card\" style={{ marginBottom: 16, display: 'grid', gap: 8 }}>\n            <strong>Document numbering</strong>",
    "          <div className=\"card\" style={{ marginBottom: 16, display: 'grid', gap: 8 }}>",
)
p.write_text(t, encoding="utf-8")
print("accounting leftover", "saveAccountingNumbering" in t, "Document numbering" in t)
print("sales leftover", "saveInvoiceNumbering" in (root / "sales/page.tsx").read_text(encoding="utf-8"))
