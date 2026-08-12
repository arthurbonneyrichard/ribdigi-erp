'use client';

import { useEffect, useState } from 'react';
import Shell from '../../components/Shell';
import { api } from '../../lib/api';
import { useTabQuery } from '../../lib/tabQuery';

const apiBase = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

type Tab = 'ledger' | 'reconcile' | 'cheques';
const ACCOUNTING_TABS: Tab[] = ['ledger', 'reconcile', 'cheques'];

export default function Page() {
  const [tab, setTab] = useTabQuery(ACCOUNTING_TABS, 'ledger');
  const [accounts, setAccounts] = useState<any[]>([]);
  // Stage 123 F1 — account_active → GET /accounting/accounts?is_active=
  const [accountActiveFilter, setAccountActiveFilter] = useState(() => {
    if (typeof window === 'undefined') return '';
    const v = (new URLSearchParams(window.location.search).get('account_active') || '')
      .trim()
      .toLowerCase();
    return v === 'true' || v === 'false' ? v : '';
  });
  // Stage 125 L1 — liquid_active → GET /accounting/liquid-accounts?is_active=
  const [liquidActiveFilter, setLiquidActiveFilter] = useState(() => {
    if (typeof window === 'undefined') return '';
    const v = (new URLSearchParams(window.location.search).get('liquid_active') || '')
      .trim()
      .toLowerCase();
    return v === 'true' || v === 'false' ? v : '';
  });
  // Stage 126 C1 — bank_conn_active → GET /accounting/bank-connections?is_active=
  const [bankConnActiveFilter, setBankConnActiveFilter] = useState(() => {
    if (typeof window === 'undefined') return '';
    const v = (new URLSearchParams(window.location.search).get('bank_conn_active') || '')
      .trim()
      .toLowerCase();
    return v === 'true' || v === 'false' ? v : '';
  });
  const [liquid, setLiquid] = useState<any[]>([]);
  const [journals, setJournals] = useState<any[]>([]);
  const [journalStatusFilter, setJournalStatusFilter] = useState('all');
  const [chequeDirectionFilter, setChequeDirectionFilter] = useState('');
  const [chequeStatusFilter, setChequeStatusFilter] = useState('');
  const [trial, setTrial] = useState<any>(null);
  const [pnl, setPnl] = useState<any>(null);
  const [statements, setStatements] = useState<any[]>([]);
  const [selected, setSelected] = useState<any>(null);
  const [cheques, setCheques] = useState<any[]>([]);
  const [error, setError] = useState('');
  const [debitCode, setDebitCode] = useState('6000');
  const [creditCode, setCreditCode] = useState('1000');
  const [amount, setAmount] = useState('100');
  const [description, setDescription] = useState('Manual adjusting entry');
  const [message, setMessage] = useState('');
  const [reconAccountId, setReconAccountId] = useState('');
  const [opening, setOpening] = useState('0');
  const [closing, setClosing] = useState('0');
  const [lineAmount, setLineAmount] = useState('100');
  const [lineDesc, setLineDesc] = useState('Deposit');
  const [pickBank, setPickBank] = useState<string[]>([]);
  const [pickBook, setPickBook] = useState<string[]>([]);
  const [importFile, setImportFile] = useState<File | null>(null);
  const [connections, setConnections] = useState<any[]>([]);
  const [connName, setConnName] = useState('Operating account feed');
  const [connProvider, setConnProvider] = useState('mock');
  const [connFeedUrl, setConnFeedUrl] = useState('');
  const [connExtId, setConnExtId] = useState('demo-acct-1');
  const [liqKind, setLiqKind] = useState<'cash' | 'bank'>('cash');
  const [liqCode, setLiqCode] = useState('1005');
  const [liqName, setLiqName] = useState('Petty Cash');
  const [liqBankName, setLiqBankName] = useState('');
  const [liqAccountNumber, setLiqAccountNumber] = useState('');
  const [liqBankBranch, setLiqBankBranch] = useState('');
  const [xferFrom, setXferFrom] = useState('');
  const [xferTo, setXferTo] = useState('');
  const [xferAmount, setXferAmount] = useState('50');
  const [xferDesc, setXferDesc] = useState('');
  const [coaCode, setCoaCode] = useState('1050');
  const [coaName, setCoaName] = useState('Petty Cash Drawer');
  const [coaType, setCoaType] = useState('asset');
  const [coaParentId, setCoaParentId] = useState('');
  const [obAccountId, setObAccountId] = useState('');
  const [obAmount, setObAmount] = useState('100');
  const [pnlFrom, setPnlFrom] = useState('');
  const [pnlTo, setPnlTo] = useState('');
  const [pnlStoreId, setPnlStoreId] = useState('');
  const [stores, setStores] = useState<any[]>([]);
  const [journalStoreId, setJournalStoreId] = useState('');
  const [manualStoreId, setManualStoreId] = useState('');
  const [tbAsOf, setTbAsOf] = useState('');
  const [accountTx, setAccountTx] = useState<any | null>(null);
  const [txFrom, setTxFrom] = useState('');
  const [txTo, setTxTo] = useState('');

  function accountDepth(row: any, byId: Record<string, any>): number {
    let depth = 0;
    let cursor = row.parent_id ? byId[row.parent_id] : null;
    const seen = new Set<string>();
    while (cursor && !seen.has(cursor.id)) {
      seen.add(cursor.id);
      depth += 1;
      cursor = cursor.parent_id ? byId[cursor.parent_id] : null;
    }
    return depth;
  }

  function writeAccountingQuery(patch: Record<string, string | null>) {
    if (typeof window === 'undefined') return;
    const url = new URL(window.location.href);
    for (const [key, value] of Object.entries(patch)) {
      if (!value) url.searchParams.delete(key);
      else url.searchParams.set(key, value);
    }
    const qs = url.searchParams.toString();
    window.history.replaceState({}, '', `${url.pathname}${qs ? `?${qs}` : ''}${url.hash}`);
  }

  async function refresh(opts?: {
    journalStatus?: string;
    journalStoreId?: string;
    chequeDirection?: string;
    chequeStatus?: string;
    accountActive?: string;
    liquidActive?: string;
    bankConnActive?: string;
  }) {
    const jStatus = opts?.journalStatus !== undefined ? opts.journalStatus : journalStatusFilter;
    const jStore = opts?.journalStoreId !== undefined ? opts.journalStoreId : journalStoreId;
    const cDir = opts?.chequeDirection !== undefined ? opts.chequeDirection : chequeDirectionFilter;
    const cStatus = opts?.chequeStatus !== undefined ? opts.chequeStatus : chequeStatusFilter;
    const accountActive =
      opts?.accountActive !== undefined ? opts.accountActive : accountActiveFilter;
    const accountQs =
      accountActive === 'true'
        ? '?is_active=true&active_only=false'
        : accountActive === 'false'
          ? '?is_active=false&active_only=false'
          : accountActive === 'all'
            ? '?active_only=false'
            : '';
    const liquidActive =
      opts?.liquidActive !== undefined ? opts.liquidActive : liquidActiveFilter;
    const liquidQs =
      liquidActive === 'true'
        ? '?is_active=true'
        : liquidActive === 'false'
          ? '?is_active=false'
          : liquidActive === 'all'
            ? '?active_only=false'
            : '';
    const bankConnActive =
      opts?.bankConnActive !== undefined ? opts.bankConnActive : bankConnActiveFilter;
    const bankConnQs =
      bankConnActive === 'true'
        ? '?is_active=true'
        : bankConnActive === 'false'
          ? '?is_active=false'
          : bankConnActive === 'all'
            ? '?active_only=false'
            : '';
    const pnlQs = new URLSearchParams();
    if (pnlFrom) pnlQs.set('from_date', pnlFrom);
    if (pnlTo) pnlQs.set('to_date', pnlTo);
    if (pnlStoreId) pnlQs.set('store_id', pnlStoreId);
    const pnlPath = pnlQs.toString()
      ? `/accounting/profit-loss?${pnlQs}`
      : '/accounting/profit-loss';
    const journalParams = new URLSearchParams();
    if (jStore) journalParams.set('store_id', jStore);
    if (jStatus && jStatus !== 'all') {
      journalParams.set('status', jStatus);
    } else if (jStatus === 'all') {
      journalParams.set('status', 'all');
    }
    const journalQs = journalParams.toString()
      ? `/accounting/journal-entries?${journalParams}`
      : '/accounting/journal-entries';
    const chequeParams = new URLSearchParams();
    if (cDir) chequeParams.set('direction', cDir);
    if (cStatus) chequeParams.set('status', cStatus);
    const chequeQs = chequeParams.toString()
      ? `/accounting/cheques?${chequeParams}`
      : '/accounting/cheques';
    const tbPath = tbAsOf
      ? `/accounting/trial-balance?as_of_date=${encodeURIComponent(tbAsOf)}`
      : '/accounting/trial-balance';
    const [a, j, t, p, liq, stmts, chq, conns, storeRows] = await Promise.all([
      api(`/accounting/accounts${accountQs}`),
      api(journalQs),
      api(tbPath),
      api(pnlPath),
      api(`/accounting/liquid-accounts${liquidQs}`),
      api('/accounting/bank-statements'),
      api(chequeQs),
      api(`/accounting/bank-connections${bankConnQs}`).catch(() => ({ data: [] })),
      api('/stores').catch(() => ({ data: [] })),
    ]);
    setAccounts(a.data || []);
    setJournals(j.data || []);
    setTrial(t.data);
    setPnl(p.data);
    setLiquid(liq.data || []);
    setStatements(stmts.data || []);
    setCheques(chq.data || []);
    setConnections(conns.data || []);
    setStores(storeRows.data || []);
    const activeLiquid = (liq.data || []).filter((r: any) => r.is_active !== false);
    if (!reconAccountId && activeLiquid.length) setReconAccountId(activeLiquid[0].id);
    if (!xferFrom && activeLiquid.length) setXferFrom(activeLiquid[0].id);
    if (!xferTo && activeLiquid.length > 1) setXferTo(activeLiquid[1].id);
    if (!obAccountId && a.data?.length) {
      const cash = a.data.find((r: any) => r.code === '1000') || a.data[0];
      setObAccountId(cash.id);
    }
  }

  // Stage 104 A1 / Stage 113 C1 — honor journal status/store_id + cheque_direction/cheque_status URL filters (incl. bounced/cancelled)
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    let jStatus = 'all';
    const st = params.get('status')?.trim() || '';
    if (['all', 'posted', 'unposted'].includes(st)) {
      jStatus = st;
      setJournalStatusFilter(st);
    }
    const store = params.get('store_id')?.trim() || '';
    if (store) setJournalStoreId(store);
    let cDir = '';
    const cd = params.get('cheque_direction')?.trim() || '';
    if (['received', 'issued'].includes(cd)) {
      cDir = cd;
      setChequeDirectionFilter(cd);
    }
    let cStatus = '';
    const cs = params.get('cheque_status')?.trim() || '';
    if (['pending', 'deposited', 'cleared', 'bounced', 'cancelled'].includes(cs)) {
      cStatus = cs;
      setChequeStatusFilter(cs);
    }
    let liqActive = liquidActiveFilter;
    const la = params.get('liquid_active')?.trim().toLowerCase() || '';
    if (la === 'true' || la === 'false') {
      liqActive = la;
      setLiquidActiveFilter(la);
    }
    let bankActive = bankConnActiveFilter;
    const ba = params.get('bank_conn_active')?.trim().toLowerCase() || '';
    if (ba === 'true' || ba === 'false') {
      bankActive = ba;
      setBankConnActiveFilter(ba);
    }
    refresh({
      journalStatus: jStatus,
      journalStoreId: store,
      chequeDirection: cDir,
      chequeStatus: cStatus,
      liquidActive: liqActive,
      bankConnActive: bankActive,
    }).catch((err) => setError(err.message));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Stage 100 G1 / Stage 109 O1 / Stage 111 C1 — ledger hashes + #bank-reconciliation + #cheques
  useEffect(() => {
    if (typeof window === 'undefined') return;
    const hash = (window.location.hash || '').replace(/^#/, '');
    if (!hash) return;
    const ledgerAnchors = [
      'coa',
      'journals',
      'trial-balance',
      'money-transfer',
      'opening-balances',
      'profit-loss',
    ];
    if (hash === 'bank-reconciliation' && tab !== 'reconcile') {
      setTab('reconcile');
      return;
    }
    if (hash === 'cheques' && tab !== 'cheques') {
      setTab('cheques');
      return;
    }
    if (ledgerAnchors.includes(hash) && tab !== 'ledger') {
      setTab('ledger');
      return;
    }
    const t = window.setTimeout(() => {
      const el = document.getElementById(hash);
      if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 80);
    return () => window.clearTimeout(t);
  }, [tab, setTab]);

  async function postManual() {
    setError('');
    setMessage('');
    try {
      const value = Number(amount);
      await api('/accounting/journal-entries', {
        method: 'POST',
        body: JSON.stringify({
          description,
          store_id: manualStoreId || null,
          lines: [
            { account_code: debitCode, debit: value, credit: 0 },
            { account_code: creditCode, debit: 0, credit: value },
          ],
        }),
      });
      setMessage('Journal posted');
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function unpostJournal(id: string) {
    setError('');
    setMessage('');
    try {
      await api(`/accounting/journal-entries/${id}/unpost`, { method: 'POST' });
      setMessage('Journal unposted');
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function uploadJournalAttachment(id: string, file: File) {
    setError('');
    setMessage('');
    try {
      const token = localStorage.getItem('token');
      const tenant = localStorage.getItem('tenant');
      const form = new FormData();
      form.append('file', file);
      const res = await fetch(`${apiBase}/accounting/journal-entries/${id}/attachment`, {
        method: 'POST',
        headers: {
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
          ...(tenant ? { 'X-Tenant-ID': tenant } : {}),
        },
        body: form,
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(body.detail?.message || body.detail || body.message || 'Upload failed');
      }
      setMessage('Supporting document uploaded');
      await refresh();
    } catch (err: any) {
      setError(typeof err.message === 'string' ? err.message : 'Upload failed');
    }
  }

  async function downloadJournalAttachment(id: string) {
    setError('');
    try {
      const token = localStorage.getItem('token');
      const tenant = localStorage.getItem('tenant');
      const res = await fetch(`${apiBase}/accounting/journal-entries/${id}/attachment`, {
        headers: {
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
          ...(tenant ? { 'X-Tenant-ID': tenant } : {}),
        },
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || body.message || 'Download failed');
      }
      const blob = await res.blob();
      const cd = res.headers.get('Content-Disposition') || '';
      const match = cd.match(/filename="?([^"]+)"?/);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = match?.[1] || 'journal-attachment';
      a.click();
      URL.revokeObjectURL(url);
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function removeJournalAttachment(id: string) {
    setError('');
    setMessage('');
    try {
      await api(`/accounting/journal-entries/${id}/attachment`, { method: 'DELETE' });
      setMessage('Supporting document removed');
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function createLiquidAccount() {
    setError('');
    setMessage('');
    try {
      await api('/accounting/liquid-accounts', {
        method: 'POST',
        body: JSON.stringify({
          kind: liqKind,
          code: liqCode,
          name: liqName,
          bank_name: liqKind === 'bank' ? liqBankName || undefined : undefined,
          account_number: liqKind === 'bank' ? liqAccountNumber || undefined : undefined,
          bank_branch: liqKind === 'bank' ? liqBankBranch || undefined : undefined,
        }),
      });
      setMessage(`${liqKind === 'cash' ? 'Cash' : 'Bank'} account created`);
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function setLiquidActive(accountId: string, next: boolean) {
    setError('');
    setMessage('');
    try {
      await api(`/accounting/liquid-accounts/${accountId}`, {
        method: 'PATCH',
        body: JSON.stringify({ is_active: next }),
      });
      setMessage(next ? 'Liquid account reactivated' : 'Liquid account deactivated');
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function postLiquidTransfer() {
    setError('');
    setMessage('');
    try {
      const r = await api('/accounting/liquid-transfers', {
        method: 'POST',
        body: JSON.stringify({
          from_account_id: xferFrom,
          to_account_id: xferTo,
          amount: Number(xferAmount),
          description: xferDesc || undefined,
        }),
      });
      setMessage(`Posted ${r.data?.source_type || 'liquid transfer'}`);
      setXferDesc('');
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function createCoaAccount() {
    setError('');
    setMessage('');
    try {
      await api('/accounting/accounts', {
        method: 'POST',
        body: JSON.stringify({
          code: coaCode,
          name: coaName,
          account_type: coaType,
          parent_id: coaParentId || undefined,
        }),
      });
      setMessage('Account created');
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function loadAccountTransactions(accountId: string) {
    if (!accountId) return;
    setError('');
    try {
      const qs = new URLSearchParams();
      if (txFrom) qs.set('from_date', txFrom);
      if (txTo) qs.set('to_date', txTo);
      const suffix = qs.toString() ? `?${qs}` : '';
      const r = await api(`/accounting/accounts/${accountId}/transactions${suffix}`);
      setAccountTx(r.data);
      setObAccountId(accountId);
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function postOpeningBalance() {
    setError('');
    setMessage('');
    try {
      await api(`/accounting/accounts/${obAccountId}/opening-balance`, {
        method: 'POST',
        body: JSON.stringify({ amount: Number(obAmount) }),
      });
      setMessage('Opening balance posted');
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function createStatement() {
    setError('');
    setMessage('');
    try {
      const amt = Number(lineAmount);
      const r = await api('/accounting/bank-statements', {
        method: 'POST',
        body: JSON.stringify({
          account_id: reconAccountId,
          statement_date: new Date().toISOString().slice(0, 10),
          opening_balance: Number(opening),
          closing_balance: Number(closing),
          lines: [
            {
              txn_date: new Date().toISOString().slice(0, 10),
              amount: amt,
              description: lineDesc,
            },
          ],
        }),
      });
      setMessage('Statement created');
      setSelected(r.data);
      await refresh();
      const detail = await api(`/accounting/bank-statements/${r.data.id}`);
      setSelected(detail.data);
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function importFeed() {
    if (!reconAccountId || !importFile) return;
    setError('');
    setMessage('');
    try {
      const token = localStorage.getItem('token');
      const tenant = localStorage.getItem('tenant');
      const apiBase = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';
      const form = new FormData();
      form.append('file', importFile);
      const qs = new URLSearchParams({
        account_id: reconAccountId,
        opening_balance: String(Number(opening) || 0),
      });
      if (closing !== '' && closing != null) qs.set('closing_balance', String(Number(closing)));
      const res = await fetch(`${apiBase}/accounting/bank-statements/import?${qs}`, {
        method: 'POST',
        headers: {
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
          ...(tenant ? { 'X-Tenant-ID': tenant } : {}),
        },
        body: form,
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(body.detail?.message || body.detail || body.message || 'Import failed');
      }
      setMessage(
        `Imported ${body.data?.import?.format?.toUpperCase() || 'feed'} (${body.data?.import?.line_count || 0} lines)`,
      );
      setImportFile(null);
      setSelected(body.data);
      await refresh();
      if (body.data?.id) {
        const detail = await api(`/accounting/bank-statements/${body.data.id}`);
        setSelected(detail.data);
      }
    } catch (err: any) {
      setError(typeof err.message === 'string' ? err.message : 'Import failed');
    }
  }

  async function createConnection() {
    if (!reconAccountId) return;
    setError('');
    setMessage('');
    try {
      await api('/accounting/bank-connections', {
        method: 'POST',
        body: JSON.stringify({
          account_id: reconAccountId,
          provider: connProvider,
          display_name: connName,
          external_account_id: connExtId || null,
          feed_url: connProvider === 'http_json' ? connFeedUrl : null,
          auto_sync: true,
          auto_match_after_sync: true,
        }),
      });
      setMessage('Bank connection created');
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function syncConnection(id: string) {
    setError('');
    setMessage('');
    try {
      const r = await api(`/accounting/bank-connections/${id}/sync`, { method: 'POST', body: '{}' });
      const imported = r.data?.imported ?? 0;
      setMessage(
        imported
          ? `Synced ${imported} new lines`
          : r.data?.message || 'Sync complete (no new lines)',
      );
      await refresh();
      if (r.data?.statement_id) {
        const detail = await api(`/accounting/bank-statements/${r.data.statement_id}`);
        setSelected(detail.data);
      }
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function removeConnection(id: string) {
    setError('');
    try {
      await api(`/accounting/bank-connections/${id}`, { method: 'DELETE' });
      setMessage('Bank connection removed');
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function setBankConnActive(id: string, next: boolean) {
    setError('');
    setMessage('');
    try {
      await api(`/accounting/bank-connections/${id}`, {
        method: 'PATCH',
        body: JSON.stringify({ is_active: next }),
      });
      setMessage(next ? 'Bank connection reactivated' : 'Bank connection deactivated');
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function openStatement(id: string) {
    setError('');
    try {
      const r = await api(`/accounting/bank-statements/${id}`);
      setSelected(r.data);
      setPickBank([]);
      setPickBook([]);
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function matchLine(lineId: string, journalLineId: string) {
    if (!selected?.id) return;
    setError('');
    try {
      await api(`/accounting/bank-statements/${selected.id}/lines/${lineId}/match`, {
        method: 'POST',
        body: JSON.stringify({ journal_line_id: journalLineId }),
      });
      setMessage('Matched');
      await openStatement(selected.id);
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function ignoreLine(lineId: string) {
    if (!selected?.id) return;
    try {
      await api(`/accounting/bank-statements/${selected.id}/lines/${lineId}/ignore`, {
        method: 'POST',
      });
      await openStatement(selected.id);
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function completeStatement() {
    if (!selected?.id) return;
    setError('');
    try {
      const r = await api(`/accounting/bank-statements/${selected.id}/complete`, { method: 'POST' });
      setMessage('Statement reconciled');
      setSelected(r.data);
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function autoClear(minConfidence: 'high' | 'medium' = 'high') {
    if (!selected?.id) return;
    setError('');
    try {
      const r = await api(`/accounting/bank-statements/${selected.id}/auto-clear`, {
        method: 'POST',
        body: JSON.stringify({ min_confidence: minConfidence, date_window_days: 7 }),
      });
      setSelected(r.data);
      setMessage(`Auto-cleared ${r.data?.auto_clear?.applied_count ?? 0} line(s) (${minConfidence}+)`);
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function chequeAction(id: string, action: 'deposit' | 'clear' | 'bounce' | 'cancel') {
    setError('');
    setMessage('');
    try {
      await api(`/accounting/cheques/${id}/${action}`, { method: 'POST' });
      setMessage(`Cheque ${action} ok`);
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  function applySuggestion(s: any) {
    matchLine(s.statement_line_id, s.journal_line_id);
  }

  function togglePick(list: string[], id: string, setter: (v: string[]) => void) {
    setter(list.includes(id) ? list.filter((x) => x !== id) : [...list, id]);
  }

  async function clearGroup() {
    if (!selected?.id || !pickBank.length || !pickBook.length) return;
    setError('');
    try {
      const r = await api(`/accounting/bank-statements/${selected.id}/clear-group`, {
        method: 'POST',
        body: JSON.stringify({
          statement_line_ids: pickBank,
          journal_line_ids: pickBook,
        }),
      });
      setSelected(r.data);
      setPickBank([]);
      setPickBook([]);
      setMessage(
        r.data?.clear_result?.mode === 'group'
          ? `Cleared group (${r.data.clear_result.group.bank_total})`
          : 'Matched 1:1',
      );
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function dissolveGroup(groupId: string) {
    if (!selected?.id) return;
    setError('');
    try {
      const r = await api(
        `/accounting/bank-statements/${selected.id}/clear-groups/${groupId}/dissolve`,
        { method: 'POST' },
      );
      setSelected(r.data);
      setMessage('Clearing group dissolved');
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  return (
    <Shell>
      <h1>Accounting</h1>
      <p className="muted">Chart of accounts, journals, trial balance, P&amp;L, bank reconciliation, and cheques</p>
      {error && <p style={{ color: '#b91c1c' }}>{error}</p>}
      {message && <p style={{ color: '#047857' }}>{message}</p>}

      <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
        <button onClick={() => setTab('ledger')} disabled={tab === 'ledger'}>
          Ledger
        </button>
        <button onClick={() => setTab('reconcile')} disabled={tab === 'reconcile'}>
          Reconcile
        </button>
        <button onClick={() => setTab('cheques')} disabled={tab === 'cheques'}>
          Cheques
        </button>
      </div>

      {tab === 'ledger' && (
        <>
          <div className="card" style={{ marginBottom: 16 }} id="money-transfer">
            <h3>Cash &amp; bank accounts</h3>
            <p className="muted" style={{ marginBottom: 8 }}>
              Money Transfer — create petty cash / bank accounts; deposit (cash→bank), withdrawal
              (bank→cash), or transfer between liquid accounts. Filter via{' '}
              <code>liquid_active</code> → <code>GET /accounting/liquid-accounts?is_active=</code>{' '}
              (Stage 125 L1).
            </p>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 12 }}>
              <select
                value={liquidActiveFilter || 'default'}
                onChange={(e) => {
                  const v = e.target.value === 'default' ? '' : e.target.value;
                  setLiquidActiveFilter(v);
                  const url = new URL(window.location.href);
                  if (v === 'true' || v === 'false') url.searchParams.set('liquid_active', v);
                  else url.searchParams.delete('liquid_active');
                  window.history.replaceState({}, '', url.toString());
                  refresh({ liquidActive: v }).catch((err) => setError(err.message));
                }}
              >
                <option value="default">Active filter (default / all)</option>
                <option value="true">Active only</option>
                <option value="false">Inactive only</option>
                <option value="all">All (active_only=false)</option>
              </select>
              <button
                type="button"
                onClick={async () => {
                  const token = localStorage.getItem('access_token') || '';
                  const qs = new URLSearchParams();
                  if (liquidActiveFilter === 'true' || liquidActiveFilter === 'false') {
                    qs.set('is_active', liquidActiveFilter);
                  } else if (liquidActiveFilter === 'all') {
                    qs.set('active_only', 'false');
                  }
                  const q = qs.toString();
                  const res = await fetch(
                    `${apiBase}/accounting/liquid-accounts/export${q ? `?${q}` : ''}`,
                    { headers: { Authorization: `Bearer ${token}` } },
                  );
                  if (!res.ok) {
                    setError(await res.text());
                    return;
                  }
                  const blob = await res.blob();
                  const a = document.createElement('a');
                  a.href = URL.createObjectURL(blob);
                  a.download = 'liquid_accounts_export.csv';
                  a.click();
                  URL.revokeObjectURL(a.href);
                  setMessage('Liquid accounts CSV downloaded');
                }}
              >
                Export liquid accounts CSV
              </button>
            </div>
            <div style={{ display: 'grid', gap: 8, maxWidth: 520, marginBottom: 16 }}>
              <select
                value={liqKind}
                onChange={(e) => setLiqKind(e.target.value as 'cash' | 'bank')}
              >
                <option value="cash">Cash</option>
                <option value="bank">Bank</option>
              </select>
              <input value={liqCode} onChange={(e) => setLiqCode(e.target.value)} placeholder="Code" />
              <input value={liqName} onChange={(e) => setLiqName(e.target.value)} placeholder="Name" />
              {liqKind === 'bank' && (
                <>
                  <input
                    value={liqBankName}
                    onChange={(e) => setLiqBankName(e.target.value)}
                    placeholder="Bank name"
                  />
                  <input
                    value={liqAccountNumber}
                    onChange={(e) => setLiqAccountNumber(e.target.value)}
                    placeholder="Account number"
                  />
                  <input
                    value={liqBankBranch}
                    onChange={(e) => setLiqBankBranch(e.target.value)}
                    placeholder="Branch"
                  />
                </>
              )}
              <button type="button" onClick={createLiquidAccount}>
                Create {liqKind} account
              </button>
            </div>
            <table className="table" style={{ marginBottom: 16 }}>
              <thead>
                <tr>
                  <th>Code</th>
                  <th>Name</th>
                  <th>Kind</th>
                  <th>Bank</th>
                  <th>Balance</th>
                  <th>Active</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {liquid.map((a) => (
                  <tr key={a.id}>
                    <td>{a.code}</td>
                    <td>{a.name}</td>
                    <td>{a.is_cash_account ? 'cash' : 'bank'}</td>
                    <td>
                      {a.is_bank_account
                        ? [a.bank_name, a.account_number, a.bank_branch].filter(Boolean).join(' · ') ||
                          '—'
                        : '—'}
                    </td>
                    <td>{a.balance}</td>
                    <td>{a.is_active === false ? 'no' : 'yes'}</td>
                    <td>
                      {a.is_active === false ? (
                        <button type="button" onClick={() => setLiquidActive(a.id, true)}>
                          Reactivate
                        </button>
                      ) : (
                        <button type="button" onClick={() => setLiquidActive(a.id, false)}>
                          Deactivate
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <h4>Deposit / withdrawal / transfer</h4>
            <div style={{ display: 'grid', gap: 8, maxWidth: 520 }}>
              <select value={xferFrom} onChange={(e) => setXferFrom(e.target.value)}>
                {liquid
                  .filter((a) => a.is_active !== false)
                  .map((a) => (
                    <option key={a.id} value={a.id}>
                      From {a.code} {a.name} ({a.balance})
                    </option>
                  ))}
              </select>
              <select value={xferTo} onChange={(e) => setXferTo(e.target.value)}>
                {liquid
                  .filter((a) => a.is_active !== false)
                  .map((a) => (
                    <option key={a.id} value={a.id}>
                      To {a.code} {a.name} ({a.balance})
                    </option>
                  ))}
              </select>
              <input
                value={xferAmount}
                onChange={(e) => setXferAmount(e.target.value)}
                placeholder="Amount"
              />
              <input
                value={xferDesc}
                onChange={(e) => setXferDesc(e.target.value)}
                placeholder="Description (optional)"
              />
              <button type="button" onClick={postLiquidTransfer}>
                Post move
              </button>
            </div>
          </div>

          <div className="card" style={{ marginBottom: 16 }}>
            <h3>Manual journal</h3>
            <div style={{ display: 'grid', gap: 8, maxWidth: 480 }}>
              <input
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Description"
              />
              <select
                value={manualStoreId}
                onChange={(e) => setManualStoreId(e.target.value)}
                aria-label="Journal store"
              >
                <option value="">No store</option>
                {stores.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.code} — {s.name}
                  </option>
                ))}
              </select>
              <input
                value={debitCode}
                onChange={(e) => setDebitCode(e.target.value)}
                placeholder="Debit account code"
              />
              <input
                value={creditCode}
                onChange={(e) => setCreditCode(e.target.value)}
                placeholder="Credit account code"
              />
              <input value={amount} onChange={(e) => setAmount(e.target.value)} placeholder="Amount" />
              <button onClick={postManual}>Post balanced entry</button>
            </div>
          </div>

          <div className="card" style={{ marginBottom: 16 }} id="coa">
            <h3>Chart of accounts</h3>
            <p className="muted" style={{ marginBottom: 8 }}>
              Add non-system accounts with optional parent (same type). Opening balances post a
              balanced journal against Opening Balances Equity (3900). Filter via{' '}
              <code>account_active</code> → <code>GET /accounting/accounts?is_active=</code> (Stage
              123 F1).
            </p>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 12, alignItems: 'center' }}>
              <label className="muted">
                Active status{' '}
                <select
                  value={accountActiveFilter}
                  onChange={(e) => {
                    const v = e.target.value;
                    setAccountActiveFilter(v);
                    const url = new URL(window.location.href);
                    if (v === 'true' || v === 'false') url.searchParams.set('account_active', v);
                    else url.searchParams.delete('account_active');
                    const qs = url.searchParams.toString();
                    window.history.replaceState(
                      {},
                      '',
                      `${url.pathname}${qs ? `?${qs}` : ''}${url.hash}`
                    );
                    refresh({ accountActive: v }).catch((err) => setError(err.message));
                  }}
                  aria-label="Account active filter"
                >
                  <option value="">Active only (default)</option>
                  <option value="true">Active only</option>
                  <option value="false">Inactive only</option>
                  <option value="all">All</option>
                </select>
              </label>
              <button
                type="button"
                onClick={async () => {
                  // Stage 123 X1 — accounts CSV export
                  setError('');
                  try {
                    const token = localStorage.getItem('token');
                    const tenant = localStorage.getItem('tenant');
                    const qs =
                      accountActiveFilter === 'true'
                        ? '?is_active=true'
                        : accountActiveFilter === 'false'
                          ? '?is_active=false'
                          : accountActiveFilter === 'all'
                            ? '?active_only=false'
                            : '';
                    const res = await fetch(`${apiBase}/accounting/accounts/export${qs}`, {
                      headers: {
                        ...(token ? { Authorization: `Bearer ${token}` } : {}),
                        ...(tenant ? { 'X-Tenant-ID': tenant } : {}),
                      },
                    });
                    if (!res.ok) throw new Error('Accounts export failed');
                    const blob = await res.blob();
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = 'accounts_export.csv';
                    a.click();
                    URL.revokeObjectURL(url);
                  } catch (err: any) {
                    setError(err.message || 'Accounts export failed');
                  }
                }}
              >
                Export accounts CSV
              </button>
            </div>
            <div style={{ display: 'grid', gap: 8, maxWidth: 520, marginBottom: 16 }}>
              <input value={coaCode} onChange={(e) => setCoaCode(e.target.value)} placeholder="Code" />
              <input value={coaName} onChange={(e) => setCoaName(e.target.value)} placeholder="Name" />
              <select value={coaType} onChange={(e) => setCoaType(e.target.value)}>
                <option value="asset">Asset</option>
                <option value="liability">Liability</option>
                <option value="equity">Equity</option>
                <option value="income">Income</option>
                <option value="expense">Expense</option>
              </select>
              <select value={coaParentId} onChange={(e) => setCoaParentId(e.target.value)}>
                <option value="">No parent</option>
                {accounts
                  .filter((a) => a.account_type === coaType)
                  .map((a) => (
                    <option key={a.id} value={a.id}>
                      {a.code} — {a.name}
                    </option>
                  ))}
              </select>
              <button type="button" onClick={createCoaAccount}>
                Create account
              </button>
            </div>
            <div
              style={{ display: 'grid', gap: 8, maxWidth: 520, marginBottom: 16 }}
              id="opening-balances"
            >
              <h4 style={{ margin: 0 }}>Opening balance</h4>
              <select value={obAccountId} onChange={(e) => setObAccountId(e.target.value)}>
                {accounts.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.code} — {a.name}
                  </option>
                ))}
              </select>
              <input
                value={obAmount}
                onChange={(e) => setObAmount(e.target.value)}
                placeholder="Amount (natural side)"
              />
              <button type="button" onClick={postOpeningBalance}>
                Post opening balance
              </button>
            </div>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 8, alignItems: 'center' }}>
              <span className="muted">Ledger date filter</span>
              <input type="date" value={txFrom} onChange={(e) => setTxFrom(e.target.value)} />
              <input type="date" value={txTo} onChange={(e) => setTxTo(e.target.value)} />
              {obAccountId && (
                <button type="button" onClick={() => loadAccountTransactions(obAccountId)}>
                  Refresh ledger
                </button>
              )}
            </div>
            <table className="table">
              <thead>
                <tr>
                  <th>Code</th>
                  <th>Name</th>
                  <th>Type</th>
                  <th>System</th>
                  <th>Liquid</th>
                  <th>Balance</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {(() => {
                  const byId = Object.fromEntries(accounts.map((a) => [a.id, a]));
                  return accounts.map((r) => {
                    const depth = accountDepth(r, byId);
                    return (
                      <tr key={r.id}>
                        <td style={{ paddingLeft: 8 + depth * 16 }}>{r.code}</td>
                        <td>{r.name}</td>
                        <td>{r.account_type}</td>
                        <td>{r.is_system ? 'yes' : '—'}</td>
                        <td>{r.is_cash_account ? 'cash' : r.is_bank_account ? 'bank' : '—'}</td>
                        <td>{r.balance}</td>
                        <td>
                          <button type="button" onClick={() => loadAccountTransactions(r.id)}>
                            Ledger
                          </button>
                        </td>
                      </tr>
                    );
                  });
                })()}
              </tbody>
            </table>
            {accountTx && (
              <div style={{ marginTop: 16 }}>
                <h4 style={{ margin: '0 0 8px' }}>
                  Account ledger — {accountTx.account?.code} {accountTx.account?.name}{' '}
                  <span className="muted">
                    (open {accountTx.opening_balance} → close {accountTx.closing_balance} ·{' '}
                    {accountTx.transaction_count} lines)
                  </span>
                </h4>
                <table className="table">
                  <thead>
                    <tr>
                      <th>Date</th>
                      <th>Entry</th>
                      <th>Reference</th>
                      <th>Description</th>
                      <th>Debit</th>
                      <th>Credit</th>
                      <th>Balance</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(accountTx.transactions || []).map((t: any) => (
                      <tr key={t.line_id}>
                        <td>
                          {t.entry_date
                            ? String(t.entry_date).replace('T', ' ').slice(0, 10)
                            : '—'}
                        </td>
                        <td>
                          <code>{t.entry_number}</code>
                        </td>
                        <td>{t.reference || '—'}</td>
                        <td>{t.description || '—'}</td>
                        <td>{t.debit}</td>
                        <td>{t.credit}</td>
                        <td>{t.balance}</td>
                      </tr>
                    ))}
                    {!accountTx.transactions?.length && (
                      <tr>
                        <td colSpan={7} className="muted">
                          No posted lines in this range
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          <div className="grid" style={{ marginTop: 16 }}>
            <div className="card" id="trial-balance">
              <h3>Trial balance</h3>
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 8 }}>
                <input
                  type="date"
                  value={tbAsOf}
                  onChange={(e) => setTbAsOf(e.target.value)}
                  aria-label="Trial balance as of"
                />
                <button type="button" onClick={() => refresh().catch((err) => setError(err.message))}>
                  Apply
                </button>
              </div>
              <p className="muted">
                As of {trial?.as_of || '—'} · Balanced: {String(trial?.balanced)} | Dr{' '}
                {trial?.total_debit} / Cr {trial?.total_credit}
              </p>
            </div>
            <div className="card" id="profit-loss">
              <h3>Profit &amp; Loss / Income</h3>
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 8 }}>
                <input type="date" value={pnlFrom} onChange={(e) => setPnlFrom(e.target.value)} />
                <input type="date" value={pnlTo} onChange={(e) => setPnlTo(e.target.value)} />
                <select
                  value={pnlStoreId}
                  onChange={(e) => setPnlStoreId(e.target.value)}
                  aria-label="P&L store filter"
                >
                  <option value="">All stores</option>
                  {stores.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.code} — {s.name}
                    </option>
                  ))}
                </select>
                <button type="button" onClick={() => refresh().catch((err) => setError(err.message))}>
                  Apply
                </button>
              </div>
              <p>Revenue: {pnl?.revenue ?? pnl?.income}</p>
              <p>COGS: {pnl?.cogs ?? 0}</p>
              <p>Gross: {pnl?.gross_profit ?? 0}</p>
              <p>OpEx: {pnl?.operating_expenses ?? 0}</p>
              <p>Income: {pnl?.income} · Expense: {pnl?.expense}</p>
              <div className="kpi">{pnl?.net_profit}</div>
            </div>
          </div>

          <div id="journals">
          <h3 style={{ marginTop: 16 }}>Recent journals</h3>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 8, alignItems: 'center' }}>
            <select
              value={journalStoreId}
              onChange={(e) => setJournalStoreId(e.target.value)}
              aria-label="Journal store filter"
            >
              <option value="">All stores</option>
              {stores.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.code} — {s.name}
                </option>
              ))}
            </select>
            <select
              value={journalStatusFilter}
              onChange={(e) => setJournalStatusFilter(e.target.value)}
              aria-label="Journal status filter"
            >
              <option value="all">All statuses</option>
              <option value="posted">Posted</option>
              <option value="unposted">Unposted</option>
            </select>
            <button
              type="button"
              onClick={() => {
                writeAccountingQuery({
                  status: journalStatusFilter === 'all' ? null : journalStatusFilter,
                  store_id: journalStoreId || null,
                });
                refresh().catch((err) => setError(err.message));
              }}
            >
              Apply filter
            </button>
          </div>
          <table className="table">
            <thead>
              <tr>
                <th>Entry</th>
                <th>Description</th>
                <th>Store</th>
                <th>Source</th>
                <th>Status</th>
                <th>Debit</th>
                <th>Credit</th>
                <th>Document</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {journals.map((j) => (
                <tr key={j.id}>
                  <td>{j.entry_number}</td>
                  <td>{j.description}</td>
                  <td>
                    {j.store_id
                      ? stores.find((s) => s.id === j.store_id)?.code || j.store_id
                      : '—'}
                  </td>
                  <td>{j.source_type || 'manual'}</td>
                  <td>{j.status || 'posted'}</td>
                  <td>{j.total_debit}</td>
                  <td>{j.total_credit}</td>
                  <td>
                    {j.has_attachment ? (
                      <span style={{ display: 'inline-flex', gap: 6, flexWrap: 'wrap' }}>
                        <button type="button" onClick={() => downloadJournalAttachment(j.id)}>
                          Download
                        </button>
                        <button type="button" onClick={() => removeJournalAttachment(j.id)}>
                          Remove
                        </button>
                      </span>
                    ) : (
                      <label style={{ cursor: 'pointer' }}>
                        <span className="muted">Upload</span>
                        <input
                          type="file"
                          style={{ display: 'none' }}
                          onChange={(e) => {
                            const f = e.target.files?.[0];
                            if (f) uploadJournalAttachment(j.id, f);
                            e.target.value = '';
                          }}
                        />
                      </label>
                    )}
                  </td>
                  <td>
                    {(j.status || 'posted') === 'posted' ? (
                      <button type="button" onClick={() => unpostJournal(j.id)}>
                        Unpost
                      </button>
                    ) : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          </div>
        </>
      )}

      {tab === 'reconcile' && (
        <>
          <div
            className="card"
            style={{ marginBottom: 16, display: 'grid', gap: 8, maxWidth: 640 }}
            id="bank-reconciliation"
          >
            <h3>New statement</h3>
            <select value={reconAccountId} onChange={(e) => setReconAccountId(e.target.value)}>
              {liquid
                .filter((a) => a.is_active !== false)
                .map((a) => (
                <option key={a.id} value={a.id}>
                  {a.code} — {a.name} ({a.balance})
                </option>
              ))}
            </select>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              <input value={opening} onChange={(e) => setOpening(e.target.value)} placeholder="Opening" />
              <input value={closing} onChange={(e) => setClosing(e.target.value)} placeholder="Closing" />
              <input
                value={lineAmount}
                onChange={(e) => setLineAmount(e.target.value)}
                placeholder="Line amount (+in/−out)"
              />
              <input value={lineDesc} onChange={(e) => setLineDesc(e.target.value)} placeholder="Line desc" />
            </div>
            <button onClick={createStatement} disabled={!reconAccountId}>
              Create statement with one line
            </button>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
              <input
                type="file"
                accept=".csv,.ofx,.qfx,.txt"
                onChange={(e) => setImportFile(e.target.files?.[0] || null)}
              />
              <button onClick={importFeed} disabled={!reconAccountId || !importFile}>
                Import CSV / OFX
              </button>
            </div>
            <p className="muted">
              Tip: post a cash/bank journal first, import a CSV/OFX feed (or create a line), then
              auto-clear or match manually. CSV needs date + amount (or debit/credit) columns.
            </p>
          </div>

          <div className="card" style={{ marginBottom: 16, display: 'grid', gap: 8, maxWidth: 640 }}>
            <h3>Bank API connections</h3>
            <p className="muted">
              Link a liquid GL account to a live feed (`mock` for demos/tests, `http_json` for any
              aggregator that returns JSON transactions). Sync creates a reconcilable statement;
              duplicates are skipped by external ref. Filter via <code>bank_conn_active</code> →{' '}
              <code>GET /accounting/bank-connections?is_active=</code> (Stage 126 C1).
            </p>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              <select
                value={bankConnActiveFilter || 'default'}
                onChange={(e) => {
                  const v = e.target.value === 'default' ? '' : e.target.value;
                  setBankConnActiveFilter(v);
                  const url = new URL(window.location.href);
                  if (v === 'true' || v === 'false') url.searchParams.set('bank_conn_active', v);
                  else url.searchParams.delete('bank_conn_active');
                  window.history.replaceState({}, '', url.toString());
                  refresh({ bankConnActive: v }).catch((err) => setError(err.message));
                }}
              >
                <option value="default">Active filter (default / all)</option>
                <option value="true">Active only</option>
                <option value="false">Inactive only</option>
                <option value="all">All (active_only=false)</option>
              </select>
              <button
                type="button"
                onClick={async () => {
                  const token = localStorage.getItem('token') || '';
                  const qs = new URLSearchParams();
                  if (bankConnActiveFilter === 'true' || bankConnActiveFilter === 'false') {
                    qs.set('is_active', bankConnActiveFilter);
                  } else if (bankConnActiveFilter === 'all') {
                    qs.set('active_only', 'false');
                  }
                  const q = qs.toString();
                  const res = await fetch(
                    `${apiBase}/accounting/bank-connections/export${q ? `?${q}` : ''}`,
                    { headers: { Authorization: `Bearer ${token}` } },
                  );
                  if (!res.ok) {
                    setError(await res.text());
                    return;
                  }
                  const blob = await res.blob();
                  const a = document.createElement('a');
                  a.href = URL.createObjectURL(blob);
                  a.download = 'bank_connections_export.csv';
                  a.click();
                  URL.revokeObjectURL(a.href);
                  setMessage('Bank connections CSV downloaded');
                }}
              >
                Export bank connections CSV
              </button>
            </div>
            <input value={connName} onChange={(e) => setConnName(e.target.value)} placeholder="Connection name" />
            <select value={connProvider} onChange={(e) => setConnProvider(e.target.value)}>
              <option value="mock">mock (built-in sample feed)</option>
              <option value="http_json">http_json (GET JSON feed URL)</option>
            </select>
            <input
              value={connExtId}
              onChange={(e) => setConnExtId(e.target.value)}
              placeholder="External account id"
            />
            {connProvider === 'http_json' && (
              <input
                value={connFeedUrl}
                onChange={(e) => setConnFeedUrl(e.target.value)}
                placeholder="https://…/transactions"
              />
            )}
            <button onClick={createConnection} disabled={!reconAccountId}>
              Connect selected liquid account
            </button>
            <ul>
              {connections.map((c) => (
                <li key={c.id} style={{ marginBottom: 8 }}>
                  {c.display_name} · {c.provider}
                  {c.is_active === false ? ' · inactive' : ''}
                  {c.last_sync_status ? ` · last ${c.last_sync_status}` : ''}{' '}
                  <button type="button" onClick={() => syncConnection(c.id)}>
                    Sync now
                  </button>{' '}
                  {c.is_active === false ? (
                    <button type="button" onClick={() => setBankConnActive(c.id, true)}>
                      Reactivate
                    </button>
                  ) : (
                    <button type="button" onClick={() => setBankConnActive(c.id, false)}>
                      Deactivate
                    </button>
                  )}{' '}
                  <button type="button" onClick={() => removeConnection(c.id)}>
                    Remove
                  </button>
                </li>
              ))}
              {!connections.length && <li className="muted">No API connections yet</li>}
            </ul>
          </div>

          <h3>Statements</h3>
          <table className="table">
            <thead>
              <tr>
                <th>Date</th>
                <th>Status</th>
                <th>Opening</th>
                <th>Closing</th>
                <th>Unmatched</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {statements.map((s) => (
                <tr key={s.id}>
                  <td>{String(s.statement_date).slice(0, 10)}</td>
                  <td>{s.status}</td>
                  <td>{s.opening_balance}</td>
                  <td>{s.closing_balance}</td>
                  <td>{s.unmatched_count}</td>
                  <td>
                    <button onClick={() => openStatement(s.id)}>Open</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {selected && (
            <div style={{ marginTop: 16 }}>
              <h3>
                Statement {String(selected.statement_date).slice(0, 10)} — {selected.status}
              </h3>
              <button
                onClick={completeStatement}
                disabled={selected.status === 'reconciled'}
                style={{ marginBottom: 12, marginRight: 8 }}
              >
                Mark reconciled
              </button>
              <button
                onClick={() => autoClear('high')}
                disabled={selected.status === 'reconciled'}
                style={{ marginBottom: 12, marginRight: 8 }}
              >
                Auto-clear high confidence
              </button>
              <button
                onClick={() => autoClear('medium')}
                disabled={selected.status === 'reconciled'}
                style={{ marginBottom: 12 }}
              >
                Auto-clear medium+
              </button>

              {(selected.suggestions || []).length > 0 && (
                <div className="card" style={{ marginBottom: 12 }}>
                  <h4>Suggestions</h4>
                  <ul>
                    {(selected.suggestions || []).map((s: any) => (
                      <li key={`${s.statement_line_id}-${s.journal_line_id}`}>
                        [{s.confidence}] {s.entry_number}: bank {s.bank_amount} ↔ book{' '}
                        {s.journal_signed_amount}
                        {s.ref_match ? ' (ref)' : ''} Δ{s.date_delta_days}d{' '}
                        <button onClick={() => applySuggestion(s)}>Apply</button>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {(selected.clearing_groups || []).length > 0 && (
                <div className="card" style={{ marginBottom: 12 }}>
                  <h4>Clearing groups</h4>
                  <ul>
                    {(selected.clearing_groups || []).map((g: any) => (
                      <li key={g.id}>
                        {g.statement_line_ids?.length || 0} bank ↔ {g.journal_line_ids?.length || 0}{' '}
                        book = {g.bank_total}{' '}
                        <button onClick={() => dissolveGroup(g.id)}>Dissolve</button>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              <div className="card" style={{ marginBottom: 12 }}>
                <h4>Multi-line clear</h4>
                <p className="muted">
                  Select unmatched bank + book lines whose totals match, then clear as a group.
                </p>
                <p>
                  Bank picked: {pickBank.length} · Book picked: {pickBook.length}
                </p>
                <button onClick={clearGroup} disabled={!pickBank.length || !pickBook.length}>
                  Clear selected as group
                </button>
              </div>

              <div className="grid">
                <div>
                  <h4>Bank lines</h4>
                  <table className="table">
                    <thead>
                      <tr>
                        <th />
                        <th>Date</th>
                        <th>Amount</th>
                        <th>Desc</th>
                        <th>Status</th>
                        <th />
                      </tr>
                    </thead>
                    <tbody>
                      {(selected.lines || []).map((ln: any) => (
                        <tr key={ln.id}>
                          <td>
                            {ln.status === 'unmatched' && (
                              <input
                                type="checkbox"
                                checked={pickBank.includes(ln.id)}
                                onChange={() => togglePick(pickBank, ln.id, setPickBank)}
                              />
                            )}
                          </td>
                          <td>{String(ln.txn_date).slice(0, 10)}</td>
                          <td>{ln.amount}</td>
                          <td>
                            {ln.description || '—'}
                            {ln.clearing_group_id ? ` [grp]` : ''}
                          </td>
                          <td>{ln.status}</td>
                          <td>
                            {ln.status === 'unmatched' && (
                              <button onClick={() => ignoreLine(ln.id)}>Ignore</button>
                            )}
                            {ln.status === 'matched' && (
                              <button
                                onClick={async () => {
                                  await api(
                                    `/accounting/bank-statements/${selected.id}/lines/${ln.id}/unmatch`,
                                    { method: 'POST' },
                                  );
                                  await openStatement(selected.id);
                                }}
                              >
                                Unmatch
                              </button>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <div>
                  <h4>Unmatched book lines</h4>
                  <table className="table">
                    <thead>
                      <tr>
                        <th />
                        <th>Entry</th>
                        <th>Signed</th>
                        <th>Desc</th>
                        <th />
                      </tr>
                    </thead>
                    <tbody>
                      {(selected.unmatched_book_lines || []).map((jl: any) => (
                        <tr key={jl.journal_line_id}>
                          <td>
                            <input
                              type="checkbox"
                              checked={pickBook.includes(jl.journal_line_id)}
                              onChange={() =>
                                togglePick(pickBook, jl.journal_line_id, setPickBook)
                              }
                            />
                          </td>
                          <td>{jl.entry_number}</td>
                          <td>{jl.signed_amount}</td>
                          <td>{jl.description || '—'}</td>
                          <td>
                            {(selected.lines || [])
                              .filter((ln: any) => ln.status === 'unmatched')
                              .slice(0, 1)
                              .map((ln: any) => (
                                <button
                                  key={ln.id}
                                  onClick={() => matchLine(ln.id, jl.journal_line_id)}
                                >
                                  Match first open
                                </button>
                              ))}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}
        </>
      )}

      {tab === 'cheques' && (
        <>
          <p className="muted" id="cheques">
            Received cheques post to 1020 then deposit/clear to Bank. Issued cheques post to 2015 until
            cleared against Bank.
          </p>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 8, alignItems: 'center' }}>
            <select
              value={chequeDirectionFilter}
              onChange={(e) => setChequeDirectionFilter(e.target.value)}
              aria-label="Cheque direction filter"
            >
              <option value="">All directions</option>
              <option value="received">Received</option>
              <option value="issued">Issued</option>
            </select>
            <select
              value={chequeStatusFilter}
              onChange={(e) => setChequeStatusFilter(e.target.value)}
              aria-label="Cheque status filter"
            >
              <option value="">All statuses</option>
              <option value="pending">Pending</option>
              <option value="deposited">Deposited</option>
              <option value="cleared">Cleared</option>
              <option value="bounced">Bounced</option>
              <option value="cancelled">Cancelled</option>
            </select>
            <button
              type="button"
              onClick={() => {
                writeAccountingQuery({
                  cheque_direction: chequeDirectionFilter || null,
                  cheque_status: chequeStatusFilter || null,
                });
                refresh().catch((err) => setError(err.message));
              }}
            >
              Apply filter
            </button>
            <button
              type="button"
              onClick={async () => {
                const token = localStorage.getItem('token') || '';
                const params = new URLSearchParams();
                if (chequeDirectionFilter) params.set('direction', chequeDirectionFilter);
                if (chequeStatusFilter) params.set('status', chequeStatusFilter);
                const qs = params.toString() ? `?${params}` : '';
                const res = await fetch(`${apiBase}/accounting/cheques/export${qs}`, {
                  headers: { Authorization: `Bearer ${token}` },
                });
                if (!res.ok) {
                  setError(await res.text());
                  return;
                }
                const blob = await res.blob();
                const a = document.createElement('a');
                a.href = URL.createObjectURL(blob);
                a.download = 'cheques_export.csv';
                a.click();
                URL.revokeObjectURL(a.href);
                setMessage('Cheques CSV downloaded (Stage 130 C1)');
              }}
            >
              Export cheques CSV
            </button>
          </div>
          <table className="table">
            <thead>
              <tr>
                <th>Number</th>
                <th>Dir</th>
                <th>Status</th>
                <th>Amount</th>
                <th>Bank</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {cheques.map((c) => (
                <tr key={c.id}>
                  <td>{c.cheque_number}</td>
                  <td>{c.direction}</td>
                  <td>{c.status}</td>
                  <td>{c.amount}</td>
                  <td>{c.bank_name || '—'}</td>
                  <td style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                    {c.direction === 'received' && c.status === 'pending' && (
                      <button onClick={() => chequeAction(c.id, 'deposit')}>Deposit</button>
                    )}
                    {(c.status === 'pending' || c.status === 'deposited') && (
                      <button onClick={() => chequeAction(c.id, 'clear')}>Clear</button>
                    )}
                    {c.status !== 'bounced' && c.status !== 'cancelled' && (
                      <button onClick={() => chequeAction(c.id, 'bounce')}>Bounce</button>
                    )}
                    {c.direction === 'issued' && c.status === 'pending' && (
                      <button onClick={() => chequeAction(c.id, 'cancel')}>Cancel</button>
                    )}
                  </td>
                </tr>
              ))}
              {!cheques.length && (
                <tr>
                  <td colSpan={6} className="muted">
                    No cheques — record a customer/supplier payment with method cheque
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </>
      )}
    </Shell>
  );
}
