'use client';

import { useEffect, useState } from 'react';
import Shell from '../../components/Shell';
import AttachmentPreview from '../../components/AttachmentPreview';
import { api } from '../../lib/api';

const apiBase = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

type Tab = 'ledger' | 'cash' | 'reconcile' | 'cheques';

export default function Page() {
  const [tab, setTab] = useState<Tab>('ledger');
  const [accounts, setAccounts] = useState<any[]>([]);
  const [accountManageFilter, setAccountManageFilter] = useState<'all' | 'active' | 'inactive'>('all');
  const [liquid, setLiquid] = useState<any[]>([]);
  const [journals, setJournals] = useState<any[]>([]);
  const [journalManageFilter, setJournalManageFilter] = useState<'all' | 'posted' | 'unposted'>(
    'all'
  );
  const [transfers, setTransfers] = useState<any[]>([]);
  const [trial, setTrial] = useState<any>(null);
  const [pnl, setPnl] = useState<any>(null);
  const [statements, setStatements] = useState<any[]>([]);
  const [statementManageFilter, setStatementManageFilter] = useState<
    'all' | 'draft' | 'in_progress' | 'reconciled'
  >('all');
  const [selected, setSelected] = useState<any>(null);
  const [cheques, setCheques] = useState<any[]>([]);
  const [chequeDirection, setChequeDirection] = useState('');
  const [chequeStatus, setChequeStatus] = useState('');
  const [chequeActionReason, setChequeActionReason] = useState('');
  const [unpostReason, setUnpostReason] = useState('');
  const [error, setError] = useState('');
  const [attachPreview, setAttachPreview] = useState<{ apiPath: string; title: string } | null>(null);
  type ManualLine = { account_code: string; debit: string; credit: string; description: string };
  const emptyManualLine = (): ManualLine => ({
    account_code: '',
    debit: '',
    credit: '',
    description: '',
  });
  const [manualLines, setManualLines] = useState<ManualLine[]>([emptyManualLine(), emptyManualLine()]);
  const [description, setDescription] = useState('Manual adjusting entry');
  const [journalRef, setJournalRef] = useState('');
  const [entryDate, setEntryDate] = useState('');
  const [message, setMessage] = useState('');
  const [reconAccountId, setReconAccountId] = useState('');
  const [opening, setOpening] = useState('0');
  const [closing, setClosing] = useState('0');
  const [lineAmount, setLineAmount] = useState('100');
  const [lineDesc, setLineDesc] = useState('Deposit');
  const [lineExternalRef, setLineExternalRef] = useState('');
  const [stmtNotes, setStmtNotes] = useState('');
  const [stmtDate, setStmtDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [lineTxnDate, setLineTxnDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [pickBank, setPickBank] = useState<string[]>([]);
  const [pickBook, setPickBook] = useState<string[]>([]);
  const [clearGroupNotes, setClearGroupNotes] = useState('');
  const [importFile, setImportFile] = useState<File | null>(null);
  const [connections, setConnections] = useState<any[]>([]);
  const [connectionManageFilter, setConnectionManageFilter] = useState<'all' | 'active' | 'inactive'>('all');
  const [connName, setConnName] = useState('Operating account feed');
  const [connProvider, setConnProvider] = useState('mock');
  const [connFeedUrl, setConnFeedUrl] = useState('');
  const [connExtId, setConnExtId] = useState('demo-acct-1');
  const [xferKind, setXferKind] = useState('transfer');
  const [xferKindManageFilter, setXferKindManageFilter] = useState<
    'all' | 'transfer' | 'deposit' | 'withdrawal'
  >('all');
  const [xferFrom, setXferFrom] = useState('');
  const [xferTo, setXferTo] = useState('');
  const [xferAmount, setXferAmount] = useState('100');
  const [xferRef, setXferRef] = useState('');
  const [xferNotes, setXferNotes] = useState('');
  const [newAcctCode, setNewAcctCode] = useState('');
  const [newAcctName, setNewAcctName] = useState('');
  const [newAcctKind, setNewAcctKind] = useState('cash');
  const [newBankName, setNewBankName] = useState('');
  const [jePrefix, setJePrefix] = useState('JE');
  const [jeNext, setJeNext] = useState('1');
  const [jePreview, setJePreview] = useState('');
  const [xferPrefix, setXferPrefix] = useState('XFER');
  const [xferNext, setXferNext] = useState('1');
  const [xferPreview, setXferPreview] = useState('');
  const [newAcctNumber, setNewAcctNumber] = useState('');
  const [newBankBranch, setNewBankBranch] = useState('');
  const [coaOpenCode, setCoaOpenCode] = useState('1000');
  const [coaOpenAmount, setCoaOpenAmount] = useState('0');
  const [coaOpenLines, setCoaOpenLines] = useState<{ code: string; amount: string }[]>([]);
  const [coaOpenRef, setCoaOpenRef] = useState('');
  const [coaOpenNotes, setCoaOpenNotes] = useState('');
  const [coaOpenStatus, setCoaOpenStatus] = useState<any>(null);
  const [editAcctId, setEditAcctId] = useState('');
  const [editAcctName, setEditAcctName] = useState('');
  const [pnlFrom, setPnlFrom] = useState('');
  const [pnlTo, setPnlTo] = useState('');
  const [pnlStoreId, setPnlStoreId] = useState('');
  const [pnlBranchId, setPnlBranchId] = useState('');
  const [stores, setStores] = useState<any[]>([]);
  const [branches, setBranches] = useState<any[]>([]);
  const [period, setPeriod] = useState<any>(null);
  const [closeThrough, setCloseThrough] = useState('');
  const [periodReason, setPeriodReason] = useState('');
  const [tbAsOf, setTbAsOf] = useState('');

  function pnlQuery() {
    const params = new URLSearchParams();
    if (pnlFrom) params.set('from_date', pnlFrom);
    if (pnlTo) params.set('to_date', pnlTo);
    if (pnlStoreId) params.set('store_id', pnlStoreId);
    if (pnlBranchId) params.set('branch_id', pnlBranchId);
    const s = params.toString();
    return s ? `?${s}` : '';
  }

  async function loadPnl() {
    const p = await api(`/accounting/profit-loss${pnlQuery()}`);
    setPnl(p.data);
  }

  async function loadTrial() {
    const qs = tbAsOf ? `?as_of=${encodeURIComponent(tbAsOf)}` : '';
    const t = await api(`/accounting/trial-balance${qs}`);
    setTrial(t.data);
  }

  async function loadCheques(direction = chequeDirection, status = chequeStatus) {
    const params = new URLSearchParams();
    if (direction) params.set('direction', direction);
    if (status) params.set('status', status);
    const q = params.toString();
    const chq = await api(`/accounting/cheques${q ? `?${q}` : ''}`);
    setCheques(chq.data || []);
  }

  async function refresh() {
    const [a, j, t, p, liq, stmts, conns, xfers, openSt, st, br, per, settings] = await Promise.all([
      api('/accounting/accounts'),
      api('/accounting/journal-entries'),
      api('/accounting/trial-balance'),
      api(`/accounting/profit-loss${pnlQuery()}`),
      api('/accounting/liquid-accounts'),
      api('/accounting/bank-statements'),
      api('/accounting/bank-connections').catch(() => ({ data: [] })),
      api('/accounting/transfers').catch(() => ({ data: [] })),
      api('/accounting/opening-balances').catch(() => ({ data: null })),
      api('/stores').catch(() => ({ data: [] })),
      api('/branches').catch(() => ({ data: [] })),
      api('/accounting/period').catch(() => ({ data: null })),
      api('/accounting/settings').catch(() => ({ data: null })),
    ]);
    setAccounts(a.data || []);
    setJournals(j.data || []);
    setTrial(t.data);
    setPnl(p.data);
    setLiquid(liq.data || []);
    setStatements(stmts.data || []);
    await loadCheques();
    setConnections(conns.data || []);
    setTransfers(xfers.data || []);
    setCoaOpenStatus(openSt.data || null);
    setStores(st.data || []);
    setBranches(br.data || []);
    setPeriod(per.data || null);
    const jeNum = settings.data?.journal_numbering;
    if (jeNum) {
      setJePrefix(jeNum.prefix || 'JE');
      setJeNext(String(jeNum.next_number ?? 1));
      setJePreview(jeNum.preview || '');
    }
    const xferNum = settings.data?.cash_transfer_numbering;
    if (xferNum) {
      setXferPrefix(xferNum.prefix || 'XFER');
      setXferNext(String(xferNum.next_number ?? 1));
      setXferPreview(xferNum.preview || '');
    }
    if (!closeThrough && per.data?.books_closed_through) {
      setCloseThrough(per.data.books_closed_through);
    }
    if (!reconAccountId && liq.data?.length) setReconAccountId(liq.data[0].id);
    if (!xferFrom && liq.data?.length) setXferFrom(liq.data[0].id);
    if (!xferTo && liq.data?.length > 1) setXferTo(liq.data[1].id);
    else if (!xferTo && liq.data?.length) setXferTo(liq.data[0].id);
  }

  async function saveAccountingNumbering() {
    setError('');
    setMessage('');
    try {
      const r = await api('/accounting/settings', {
        method: 'PATCH',
        body: JSON.stringify({
          journal_numbering: {
            prefix: jePrefix.trim(),
            next_number: Math.max(1, Number(jeNext) || 1),
          },
          cash_transfer_numbering: {
            prefix: xferPrefix.trim(),
            next_number: Math.max(1, Number(xferNext) || 1),
          },
        }),
      });
      const jeNum = r.data?.journal_numbering;
      if (jeNum) {
        setJePrefix(jeNum.prefix || 'JE');
        setJeNext(String(jeNum.next_number ?? 1));
        setJePreview(jeNum.preview || '');
      }
      const xferNum = r.data?.cash_transfer_numbering;
      if (xferNum) {
        setXferPrefix(xferNum.prefix || 'XFER');
        setXferNext(String(xferNum.next_number ?? 1));
        setXferPreview(xferNum.preview || '');
      }
      setMessage(
        `Numbering saved — JE ${jeNum?.preview || ''} · XFER ${xferNum?.preview || ''}`.trim(),
      );
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function closeBooks() {
    setError('');
    setMessage('');
    try {
      if (!closeThrough) throw new Error('Choose a close-through date');
      const reason = periodReason.trim();
      if (!reason) {
        setError('Enter a close reason before closing the books');
        return;
      }
      await api('/accounting/period/close', {
        method: 'POST',
        body: JSON.stringify({ through_date: closeThrough, reason }),
      });
      setMessage(`Books closed through ${closeThrough}`);
      setPeriodReason('');
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function reopenBooks() {
    setError('');
    setMessage('');
    try {
      const reason = periodReason.trim();
      if (!reason) {
        setError('Enter a reopen reason before reopening the books');
        return;
      }
      await api('/accounting/period/reopen', {
        method: 'POST',
        body: JSON.stringify({ through_date: null, reason }),
      });
      setMessage('Books reopened (closed date cleared)');
      setPeriodReason('');
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  useEffect(() => {
    refresh().catch((err) => setError(err.message));
  }, []);

  async function postManual() {
    setError('');
    setMessage('');
    try {
      const lines = manualLines.map((l) => ({
        account_code: l.account_code.trim(),
        debit: Math.max(0, Number(l.debit) || 0),
        credit: Math.max(0, Number(l.credit) || 0),
        description: l.description.trim() || null,
      }));
      if (lines.length < 2) {
        throw new Error('Journal entry requires at least two lines');
      }
      for (const line of lines) {
        if (!line.account_code) throw new Error('Each line needs an account code');
        if (line.debit <= 0 && line.credit <= 0) {
          throw new Error('Each line needs a debit or credit amount');
        }
        if (line.debit > 0 && line.credit > 0) {
          throw new Error('A line cannot have both debit and credit');
        }
      }
      const debitTotal = lines.reduce((s, l) => s + l.debit, 0);
      const creditTotal = lines.reduce((s, l) => s + l.credit, 0);
      if (Math.abs(debitTotal - creditTotal) > 0.01) {
        throw new Error(
          `Entry is unbalanced (debit ${debitTotal.toFixed(2)} ≠ credit ${creditTotal.toFixed(2)})`,
        );
      }
      await api('/accounting/journal-entries', {
        method: 'POST',
        body: JSON.stringify({
          description: description.trim(),
          reference: journalRef.trim() || null,
          entry_date: entryDate.trim() || null,
          lines,
        }),
      });
      setMessage('Journal posted');
      setManualLines([emptyManualLine(), emptyManualLine()]);
      setEntryDate('');
      setJournalRef('');
      setDescription('Manual adjusting entry');
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function unpostJournal(id: string) {
    setError('');
    setMessage('');
    const reason = unpostReason.trim();
    if (!reason) {
      setError('Enter an unpost reason before unposting a journal');
      return;
    }
    try {
      await api(`/accounting/journal-entries/${id}/unpost`, {
        method: 'POST',
        body: JSON.stringify({ reason }),
      });
      setMessage('Journal unposted');
      setUnpostReason('');
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function uploadJournalAttachment(id: string, file: File) {
    setError('');
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
      if (!res.ok) throw new Error(body.detail?.message || body.detail || body.message || 'Upload failed');
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
    try {
      await api(`/accounting/journal-entries/${id}/attachment`, { method: 'DELETE' });
      setMessage('Attachment removed');
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function createLiquidAccount() {
    setError('');
    setMessage('');
    try {
      const body: Record<string, unknown> = {
        code: newAcctCode.trim(),
        name: newAcctName.trim(),
        liquid_kind: newAcctKind,
      };
      if (newAcctKind === 'bank') {
        // Blank bank_name → schema 422 (BankNameValue); omit only when empty so
        // service required-name 400 still covers intentional omit.
        const trimmedBank = newBankName.trim();
        if (trimmedBank) body.bank_name = trimmedBank;
        body.account_number = newAcctNumber.trim() || null;
        body.bank_branch = newBankBranch.trim() || null;
      }
      const r = await api('/accounting/accounts', { method: 'POST', body: JSON.stringify(body) });
      setMessage(`Account ${r.data.code} created`);
      setNewAcctCode('');
      setNewAcctName('');
      setNewBankName('');
      setNewAcctNumber('');
      setNewBankBranch('');
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  function addCoaOpenLine() {
    if (!coaOpenCode || !coaOpenAmount || Number(coaOpenAmount) <= 0) return;
    setCoaOpenLines((prev) => [...prev, { code: coaOpenCode, amount: coaOpenAmount }]);
    setCoaOpenAmount('0');
  }

  async function postCoaOpening() {
    setError('');
    setMessage('');
    if (!coaOpenLines.length) {
      setError('Add at least one opening balance line');
      return;
    }
    try {
      const r = await api('/accounting/opening-balances', {
        method: 'POST',
        body: JSON.stringify({
          reference: coaOpenRef.trim() || null,
          notes: coaOpenNotes.trim() || null,
          lines: coaOpenLines.map((l) => ({
            account_code: l.code,
            amount: Number(l.amount),
          })),
        }),
      });
      const plug =
        r.data.equity_plug_amount && Math.abs(r.data.equity_plug_amount) > 0.009
          ? ` · equity plug ${r.data.equity_plug_amount}`
          : '';
      setMessage(
        `Opening balances posted (${r.data.journal_number})${plug}. Dr ${r.data.total_debit} / Cr ${r.data.total_credit}`,
      );
      setCoaOpenLines([]);
      setCoaOpenNotes('');
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function saveAccountName() {
    setError('');
    setMessage('');
    if (!editAcctId || !editAcctName.trim()) return;
    try {
      const r = await api(`/accounting/accounts/${editAcctId}`, {
        method: 'PATCH',
        body: JSON.stringify({ name: editAcctName.trim() }),
      });
      setMessage(`Updated ${r.data.code}`);
      setEditAcctId('');
      setEditAcctName('');
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function setAccountActive(id: string, isActive: boolean) {
    setError('');
    setMessage('');
    try {
      await api(`/accounting/accounts/${id}`, {
        method: 'PATCH',
        body: JSON.stringify({ is_active: isActive }),
      });
      setMessage(isActive ? 'Account activated' : 'Account deactivated');
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function postTransfer() {
    setError('');
    setMessage('');
    try {
      const body: Record<string, unknown> = {
        kind: xferKind,
        amount: Number(xferAmount),
        reference: xferRef.trim() || null,
        notes: xferNotes.trim() || null,
      };
      if (xferKind === 'transfer' || xferKind === 'withdrawal') body.from_account_id = xferFrom;
      if (xferKind === 'transfer' || xferKind === 'deposit') body.to_account_id = xferTo;
      const r = await api('/accounting/transfers', { method: 'POST', body: JSON.stringify(body) });
      setMessage(`${r.data.kind} posted for ${r.data.amount}`);
      setXferNotes('');
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
      const desc = lineDesc.trim() || null;
      const r = await api('/accounting/bank-statements', {
        method: 'POST',
        body: JSON.stringify({
          account_id: reconAccountId,
          statement_date: stmtDate || undefined,
          opening_balance: Number(opening),
          closing_balance: Number(closing),
          notes: stmtNotes.trim() || null,
          lines: [
            {
              txn_date: lineTxnDate || undefined,
              amount: amt,
              description: desc,
              external_ref: lineExternalRef.trim() || null,
            },
          ],
        }),
      });
      setMessage('Statement created');
      setSelected(r.data);
      setStmtNotes('');
      setLineExternalRef('');
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
      if (stmtDate) qs.set('statement_date', stmtDate);
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
    const displayName = connName.trim();
    setError('');
    setMessage('');
    try {
      await api('/accounting/bank-connections', {
        method: 'POST',
        body: JSON.stringify({
          account_id: reconAccountId,
          provider: connProvider,
          display_name: displayName || null,
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

  async function setConnectionActive(id: string, isActive: boolean) {
    setError('');
    setMessage('');
    try {
      await api(`/accounting/bank-connections/${id}`, {
        method: 'PATCH',
        body: JSON.stringify({ is_active: isActive }),
      });
      setMessage(isActive ? 'Bank connection activated' : 'Bank connection deactivated');
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

  async function autoClear(minConfidence: 'high' | 'medium' | 'low' = 'high') {
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
    if (action === 'bounce' || action === 'cancel') {
      const reason = chequeActionReason.trim();
      if (!reason) {
        setError(`Enter a reason before ${action === 'bounce' ? 'bouncing' : 'cancelling'} a cheque`);
        return;
      }
    }
    try {
      const reason = chequeActionReason.trim();
      const opts: RequestInit = { method: 'POST' };
      if (action === 'bounce' || action === 'cancel') {
        opts.body = JSON.stringify({ reason });
      }
      await api(`/accounting/cheques/${id}/${action}`, opts);
      if (action === 'bounce' || action === 'cancel') {
        setChequeActionReason('');
      }
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
          notes: clearGroupNotes.trim() || null,
        }),
      });
      setSelected(r.data);
      setPickBank([]);
      setPickBook([]);
      setClearGroupNotes('');
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

  const managedConnections = connections.filter((c) => {
    if (connectionManageFilter === 'all') return true;
    const active = c.is_active !== false;
    return connectionManageFilter === 'inactive' ? !active : active;
  });
  const managedStatements = statements.filter((s) => {
    if (statementManageFilter === 'all') return true;
    return (s.status || 'draft') === statementManageFilter;
  });
  const managedJournals = journals.filter((j) => {
    if (journalManageFilter === 'all') return true;
    return (j.status || 'posted') === journalManageFilter;
  });
  const managedTransfers = transfers.filter((t) => {
    if (xferKindManageFilter === 'all') return true;
    return (t.kind || 'transfer') === xferKindManageFilter;
  });

  const manualDebitTotal = manualLines.reduce((s, l) => s + (Number(l.debit) || 0), 0);
  const manualCreditTotal = manualLines.reduce((s, l) => s + (Number(l.credit) || 0), 0);
  const manualBalanced = Math.abs(manualDebitTotal - manualCreditTotal) <= 0.01;
  const managedAccounts = accounts.filter((a) => {
    if (accountManageFilter === 'all') return true;
    const active = a.is_active !== false;
    return accountManageFilter === 'inactive' ? !active : active;
  });
  const activeAccounts = accounts.filter((a) => a.is_active !== false);

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
        <button onClick={() => setTab('cash')} disabled={tab === 'cash'}>
          Cash &amp; Bank
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
          <div className="card" style={{ marginBottom: 16, display: 'grid', gap: 8 }}>
            <strong>Document numbering</strong>
            <p className="muted" style={{ margin: 0 }}>
              Journals and cash/bank transfers use PREFIX-YYYY-NNNN (defaults JE / XFER). Blank
              transfer reference auto-allocates the next XFER number.
            </p>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
              <span className="muted">Journal</span>
              <input
                value={jePrefix}
                onChange={(e) => setJePrefix(e.target.value.toUpperCase())}
                placeholder="Prefix"
                style={{ width: 100 }}
                aria-label="Journal number prefix"
                title="Journal document prefix (letters, digits, _ or -)"
              />
              <input
                value={jeNext}
                onChange={(e) => setJeNext(e.target.value)}
                placeholder="Next #"
                style={{ width: 90 }}
                aria-label="Journal next number"
              />
              <span className="muted">{jePreview || '—'}</span>
            </div>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
              <span className="muted">Transfer/XFER</span>
              <input
                value={xferPrefix}
                onChange={(e) => setXferPrefix(e.target.value.toUpperCase())}
                placeholder="Prefix"
                style={{ width: 100 }}
                aria-label="Cash transfer number prefix"
                title="Cash transfer document prefix (letters, digits, _ or -)"
              />
              <input
                value={xferNext}
                onChange={(e) => setXferNext(e.target.value)}
                placeholder="Next #"
                style={{ width: 90 }}
                aria-label="Cash transfer next number"
              />
              <span className="muted">{xferPreview || '—'}</span>
              <button type="button" onClick={saveAccountingNumbering} aria-label="Save accounting numbering">
                Save numbering
              </button>
            </div>
          </div>

          <div className="card" style={{ marginBottom: 16, display: 'grid', gap: 8 }}>
            <h3>Period close (BR-10.2)</h3>
            <p className="muted" style={{ margin: 0 }}>
              Closing books through a date blocks posting and unposting journals on or before that
              date. Fiscal year start: {period?.fiscal_year_start || '01-01'}
              {period?.current_fiscal_start
                ? ` · current period ${period.current_fiscal_start} → ${period.current_fiscal_end_exclusive}`
                : ''}
            </p>
            <p style={{ margin: 0 }}>
              Closed through:{' '}
              <strong>{period?.books_closed_through || 'not closed'}</strong>
            </p>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
              <input
                value={closeThrough}
                onChange={(e) => setCloseThrough(e.target.value)}
                placeholder="Through date YYYY-MM-DD"
                aria-label="Period close through date"
                title="Period close through date (YYYY-MM-DD)"
              />
              <input
                value={periodReason}
                onChange={(e) => setPeriodReason(e.target.value)}
                placeholder="Required close / reopen reason"
                style={{ minWidth: 280 }}
                title="Required close/reopen reason (1–500 chars; letters/digits required)"
                aria-label="Period close or reopen reason"
              />
              <button type="button" className="btn-danger" onClick={closeBooks} aria-label="Close books">
                Close books
              </button>
              {period?.books_closed_through && (
                <button type="button" className="btn-ok" onClick={reopenBooks} aria-label="Reopen books">
                  Reopen (clear)
                </button>
              )}
            </div>
            <p className="muted" style={{ margin: 0 }}>
              Reason is required for close and reopen (audit <code>period_closed</code> /{' '}
              <code>period_reopened</code> <code>details.reason</code>).
            </p>
          </div>

          <div className="card" style={{ marginBottom: 16 }}>
            <h3>Manual journal</h3>
            <p className="muted" style={{ marginTop: 0 }}>
              Multi-line adjusting entries (BR-10.2). At least two lines; Σ debit must equal Σ credit
              (±0.01). Each line is debit <em>or</em> credit.
            </p>
            <div style={{ display: 'grid', gap: 8 }}>
              <input
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Description"
                aria-label="Journal description"
                title="Journal description (2–500 chars; letters/digits required)"
              />
              <input
                value={journalRef}
                onChange={(e) => setJournalRef(e.target.value)}
                placeholder="Reference (optional)"
                aria-label="Journal reference"
                title="Optional reference (1–100 chars; letters/digits required)"
              />
              <input
                value={entryDate}
                onChange={(e) => setEntryDate(e.target.value)}
                placeholder="Entry date YYYY-MM-DD (optional)"
                aria-label="Journal entry date"
                title="Journal entry date (optional YYYY-MM-DD; blank → now)"
              />
              <table className="table" aria-label="Manual journal lines">
                <thead>
                  <tr>
                    <th>Account code</th>
                    <th>Debit</th>
                    <th>Credit</th>
                    <th>Line desc</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {manualLines.map((line, idx) => (
                    <tr key={idx}>
                      <td>
                        <input
                          list="manual-journal-accounts"
                          value={line.account_code}
                          onChange={(e) =>
                            setManualLines((prev) =>
                              prev.map((row, i) =>
                                i === idx ? { ...row, account_code: e.target.value } : row,
                              ),
                            )
                          }
                          placeholder="e.g. 6000"
                          aria-label={`Journal line ${idx + 1} account code`}
                        />
                      </td>
                      <td>
                        <input
                          value={line.debit}
                          onChange={(e) =>
                            setManualLines((prev) =>
                              prev.map((row, i) =>
                                i === idx ? { ...row, debit: e.target.value, credit: '' } : row,
                              ),
                            )
                          }
                          placeholder="0"
                          style={{ width: 100 }}
                          aria-label={`Journal line ${idx + 1} debit`}
                        />
                      </td>
                      <td>
                        <input
                          value={line.credit}
                          onChange={(e) =>
                            setManualLines((prev) =>
                              prev.map((row, i) =>
                                i === idx ? { ...row, credit: e.target.value, debit: '' } : row,
                              ),
                            )
                          }
                          placeholder="0"
                          style={{ width: 100 }}
                          aria-label={`Journal line ${idx + 1} credit`}
                        />
                      </td>
                      <td>
                        <input
                          value={line.description}
                          onChange={(e) =>
                            setManualLines((prev) =>
                              prev.map((row, i) =>
                                i === idx ? { ...row, description: e.target.value } : row,
                              ),
                            )
                          }
                          placeholder="Optional"
                          style={{ width: 140 }}
                          aria-label={`Journal line ${idx + 1} description`}
                          title="Optional line description (1–500 chars; letters/digits required)"
                        />
                      </td>
                      <td>
                        <button
                          type="button"
                          disabled={manualLines.length <= 2}
                          onClick={() =>
                            setManualLines((prev) => prev.filter((_, i) => i !== idx))
                          }
                          title={
                            manualLines.length <= 2
                              ? 'Journal requires at least two lines'
                              : 'Remove line'
                          }
                        >
                          Remove
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <datalist id="manual-journal-accounts">
                {activeAccounts.map((a) => (
                  <option key={a.id} value={a.code}>
                    {a.name}
                  </option>
                ))}
              </datalist>
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
                <button
                  type="button"
                  onClick={() => setManualLines((prev) => [...prev, emptyManualLine()])}
                >
                  Add line
                </button>
                <span className="muted" style={{ fontSize: 13 }}>
                  Debit {manualDebitTotal.toFixed(2)} · Credit {manualCreditTotal.toFixed(2)}
                  {manualBalanced ? ' · balanced' : ' · unbalanced'}
                </span>
              </div>
              <button
                type="button"
                className="btn-ok"
                onClick={postManual}
                disabled={!manualBalanced}
                aria-label="Post balanced entry"
              >
                Post balanced entry
              </button>
            </div>
          </div>

          <div className="card" style={{ marginBottom: 16, display: 'grid', gap: 8 }}>
            <h3>COA opening balances (BR-10.1)</h3>
            <p className="muted" style={{ margin: 0 }}>
              Post go-live / fiscal-year openings. Asset &amp; expense amounts debit; liability,
              equity &amp; income credit. Unbalanced residual plugs to Owner&apos;s Equity (3000).
            </p>
            {coaOpenStatus?.posted ? (
              <p style={{ color: '#047857', margin: 0 }}>
                Already posted: {coaOpenStatus.journal_number}
                {coaOpenStatus.reference ? ` (${coaOpenStatus.reference})` : ''}
              </p>
            ) : (
              <>
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
                  <select value={coaOpenCode} onChange={(e) => setCoaOpenCode(e.target.value)}>
                    {activeAccounts.map((a) => (
                      <option key={a.id} value={a.code}>
                        {a.code} — {a.name} ({a.account_type})
                      </option>
                    ))}
                  </select>
                  <input
                    value={coaOpenAmount}
                    onChange={(e) => setCoaOpenAmount(e.target.value)}
                    placeholder="Amount"
                    style={{ width: 120 }}
                  />
                  <button type="button" onClick={addCoaOpenLine}>
                    Add line
                  </button>
                </div>
                <input
                  value={coaOpenRef}
                  onChange={(e) => setCoaOpenRef(e.target.value)}
                  placeholder="Reference (e.g. FY2026-OPEN)"
                  aria-label="Opening balance reference"
                  title="Optional reference (1–100 chars; blank → auto COA-OPEN-YYYYMMDD)"
                />
                <input
                  value={coaOpenNotes}
                  onChange={(e) => setCoaOpenNotes(e.target.value)}
                  placeholder="Notes (optional)"
                  aria-label="Opening balance notes"
                  title="Optional notes (1–500 chars; letters/digits required)"
                />
                {coaOpenLines.length > 0 && (
                  <ul style={{ margin: 0, paddingLeft: 18 }}>
                    {coaOpenLines.map((l, i) => (
                      <li key={`${l.code}-${i}`}>
                        {l.code}: {l.amount}{' '}
                        <button
                          type="button"
                          onClick={() =>
                            setCoaOpenLines((prev) => prev.filter((_, idx) => idx !== i))
                          }
                        >
                          Remove
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
                <button
                  type="button"
                  className="btn-ok"
                  onClick={postCoaOpening}
                  disabled={!coaOpenLines.length}
                  aria-label="Post opening balances"
                >
                  Post opening balances
                </button>
              </>
            )}
          </div>

          <div className="card" style={{ marginBottom: 16, display: 'grid', gap: 8 }}>
            <h3>Edit account name</h3>
            <select
              value={editAcctId}
              onChange={(e) => {
                setEditAcctId(e.target.value);
                const a = accounts.find((x) => x.id === e.target.value);
                setEditAcctName(a?.name || '');
              }}
            >
              <option value="">Select account</option>
              {accounts.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.code} — {a.name}
                </option>
              ))}
            </select>
            <input
              value={editAcctName}
              onChange={(e) => setEditAcctName(e.target.value)}
              placeholder="Display name"
              disabled={!editAcctId}
              aria-label="Edit account name"
              title="Account display name (1–150 chars; letters/digits required)"
            />
            <button
              type="button"
              onClick={saveAccountName}
              disabled={!editAcctId}
              aria-label="Save account name"
            >
              Save name
            </button>
          </div>

          <h3>Chart of accounts</h3>
          <select
            value={accountManageFilter}
            onChange={(e) =>
              setAccountManageFilter(e.target.value as 'all' | 'active' | 'inactive')
            }
            title="Filter manage chart of accounts by status"
            aria-label="Account status filter"
            style={{ marginBottom: 8 }}
          >
            <option value="all">All statuses</option>
            <option value="active">Active only</option>
            <option value="inactive">Inactive only</option>
          </select>
          <table className="table">
            <thead>
              <tr>
                <th>Code</th>
                <th>Name</th>
                <th>Type</th>
                <th>Liquid</th>
                <th>Opening</th>
                <th>Balance</th>
                <th>Active</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {managedAccounts.length === 0 && (
                <tr>
                  <td colSpan={8} className="muted">
                    No accounts for this filter
                  </td>
                </tr>
              )}
              {managedAccounts.map((r) => (
                <tr key={r.id}>
                  <td>{r.code}</td>
                  <td>
                    {r.name}
                    {r.is_system ? ' · system' : ''}
                    {r.is_active === false ? (
                      <span className="muted" style={{ marginLeft: 6, fontSize: 12 }}>
                        [inactive]
                      </span>
                    ) : null}
                  </td>
                  <td>{r.account_type}</td>
                  <td>{r.is_cash_account ? 'cash' : r.is_bank_account ? 'bank' : '—'}</td>
                  <td>{r.opening_balance ?? 0}</td>
                  <td>{r.balance}</td>
                  <td>{r.is_active === false ? 'no' : 'yes'}</td>
                  <td>
                    {r.is_active === false ? (
                      <button type="button" className="btn-ok" onClick={() => setAccountActive(r.id, true)}>
                        Activate
                      </button>
                    ) : (
                      <button
                        type="button"
                        className="btn-danger"
                        onClick={() => setAccountActive(r.id, false)}
                      >
                        Deactivate
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          <div className="grid" style={{ marginTop: 16 }}>
            <div className="card">
              <h3>Trial balance</h3>
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 8 }}>
                <input
                  type="date"
                  value={tbAsOf}
                  onChange={(e) => setTbAsOf(e.target.value)}
                  title="As of (empty = live balances)"
                  aria-label="Trial balance as of date"
                />
                <button
                  type="button"
                  onClick={() => loadTrial().catch((err) => setError(err.message))}
                >
                  Apply
                </button>
              </div>
              <p className="muted">
                {trial?.mode === 'journals' ? `As of ${trial?.as_of} (journals)` : 'Live balances'}
                {' · '}
                Balanced: {String(trial?.balanced)} | Dr {trial?.total_debit} / Cr{' '}
                {trial?.total_credit}
              </p>
              {!!trial?.rows?.length && (
                <table className="table" style={{ marginTop: 8 }}>
                  <thead>
                    <tr>
                      <th>Code</th>
                      <th>Name</th>
                      <th>Debit</th>
                      <th>Credit</th>
                    </tr>
                  </thead>
                  <tbody>
                    {trial.rows.slice(0, 40).map((r: any) => (
                      <tr key={r.account_id || r.code}>
                        <td>{r.code}</td>
                        <td>{r.name}</td>
                        <td>{r.debit}</td>
                        <td>{r.credit}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
            <div className="card">
              <h3>Profit &amp; Loss</h3>
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 8 }}>
                <input
                  type="date"
                  value={pnlFrom}
                  onChange={(e) => setPnlFrom(e.target.value)}
                  title="From date (YYYY-MM-DD)"
                  aria-label="P&L from date"
                />
                <input
                  type="date"
                  value={pnlTo}
                  onChange={(e) => setPnlTo(e.target.value)}
                  title="To date (YYYY-MM-DD)"
                  aria-label="P&L to date"
                />
                <select value={pnlBranchId} onChange={(e) => setPnlBranchId(e.target.value)}>
                  <option value="">All branches</option>
                  {branches.map((b) => (
                    <option key={b.id} value={b.id}>
                      {b.code} — {b.name}
                    </option>
                  ))}
                </select>
                <select value={pnlStoreId} onChange={(e) => setPnlStoreId(e.target.value)}>
                  <option value="">All stores</option>
                  {stores
                    .filter((s) => !pnlBranchId || s.branch_id === pnlBranchId)
                    .map((s) => (
                      <option key={s.id} value={s.id}>
                        {s.code} — {s.name}
                      </option>
                    ))}
                </select>
                <button
                  type="button"
                  onClick={() =>
                    loadPnl().catch((err: any) => setError(err.message || String(err)))
                  }
                >
                  Apply
                </button>
              </div>
              <p className="muted" style={{ marginTop: 0 }}>
                {pnl?.mode === 'journals'
                  ? 'Period / location from posted journals'
                  : 'Lifetime account balances'}
              </p>
              <p>Revenue: {pnl?.revenue ?? pnl?.income}</p>
              <p>COGS: {pnl?.cogs ?? 0}</p>
              <p>Gross profit: {pnl?.gross_profit ?? (pnl?.income ?? 0) - (pnl?.cogs ?? 0)}</p>
              <p>Operating expenses: {pnl?.operating_expenses ?? pnl?.expense}</p>
              <div className="kpi">{pnl?.net_profit}</div>
              <p className="muted" style={{ margin: 0 }}>
                Net profit
              </p>
            </div>
          </div>

          <h3 style={{ marginTop: 16 }}>Recent journals</h3>
          <p className="muted">
            Manual journals can be unposted within the current fiscal period when books are open for
            that date. Attach supporting
            documents on any entry (BR-10.2).
          </p>
          <select
            value={journalManageFilter}
            onChange={(e) =>
              setJournalManageFilter(e.target.value as 'all' | 'posted' | 'unposted')
            }
            title="Filter journal list by status"
            aria-label="Journal status filter"
            style={{ marginBottom: 12 }}
          >
            <option value="all">All statuses</option>
            <option value="posted">Posted only</option>
            <option value="unposted">Unposted only</option>
          </select>
          <label style={{ display: 'block', marginBottom: 8 }}>
            Unpost reason{' '}
            <input
              value={unpostReason}
              onChange={(e) => setUnpostReason(e.target.value)}
              placeholder="Required before Unpost"
              title="Required unpost reason (1–500 chars; letters/digits required)"
              aria-label="Journal unpost reason"
              style={{ minWidth: 280 }}
            />
          </label>
          <p className="muted" style={{ marginTop: 0 }}>
            Appended to the journal description and audit (`POST .../unpost` {'{ reason }'}).
          </p>
          <table className="table">
            <thead>
              <tr>
                <th>Entry</th>
                <th>Description</th>
                <th>Source</th>
                <th>Status</th>
                <th>Debit</th>
                <th>Credit</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {managedJournals.length === 0 ? (
                <tr>
                  <td colSpan={7} className="muted">
                    {journals.length === 0
                      ? 'No journals yet'
                      : 'No journals for this filter'}
                  </td>
                </tr>
              ) : (
                managedJournals.map((j) => (
                <tr key={j.id}>
                  <td>{j.entry_number}</td>
                  <td>{j.description}</td>
                  <td>{j.source_type || 'manual'}</td>
                  <td>{j.status}</td>
                  <td>{j.total_debit}</td>
                  <td>{j.total_credit}</td>
                  <td>
                    <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center' }}>
                      {j.can_unpost && j.status === 'posted' && (
                        <button
                          type="button"
                          className="btn-danger"
                          onClick={() => unpostJournal(j.id)}
                          aria-label={`Unpost journal ${j.id}`}
                        >
                          Unpost
                        </button>
                      )}
                      <label style={{ cursor: 'pointer' }}>
                        <span className="muted" style={{ textDecoration: 'underline' }}>
                          Attach
                        </span>
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
                      {j.has_attachment && (
                        <>
                          <button
                            type="button"
                            onClick={() =>
                              setAttachPreview({
                                apiPath: `/accounting/journal-entries/${j.id}/attachment`,
                                title: `Journal attachment — ${j.entry_number || j.id.slice(0, 8)}`,
                              })
                            }
                          >
                            Preview
                          </button>
                          <button type="button" onClick={() => downloadJournalAttachment(j.id)}>
                            Download
                          </button>
                          <button type="button" onClick={() => removeJournalAttachment(j.id)}>
                            Remove file
                          </button>
                        </>
                      )}
                    </div>
                  </td>
                </tr>
                ))
              )}
            </tbody>
          </table>
        </>
      )}

      {tab === 'cash' && (
        <>
          <div className="card" style={{ marginBottom: 16, display: 'grid', gap: 8 }}>
            <h3>Create cash / bank account</h3>
            <p className="muted" style={{ margin: 0 }}>
              Add petty cash tills or bank accounts (BR-10.3). Bank accounts need a bank name.
            </p>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              <input
                value={newAcctCode}
                onChange={(e) => setNewAcctCode(e.target.value)}
                placeholder="Code (e.g. 1001)"
                style={{ width: 120 }}
                aria-label="Account code"
                title="Account code (1–30 chars: letters, digits, _ or -)"
              />
              <input
                value={newAcctName}
                onChange={(e) => setNewAcctName(e.target.value)}
                placeholder="Name (e.g. Petty Cash)"
                aria-label="Account name"
                title="Account display name (1–150 chars; letters/digits required)"
              />
              <select value={newAcctKind} onChange={(e) => setNewAcctKind(e.target.value)}>
                <option value="cash">Cash</option>
                <option value="bank">Bank</option>
              </select>
              {newAcctKind === 'bank' && (
                <>
                  <input
                    value={newBankName}
                    onChange={(e) => setNewBankName(e.target.value)}
                    placeholder="Bank name"
                    aria-label="Bank name"
                  />
                  <input
                    value={newAcctNumber}
                    onChange={(e) => setNewAcctNumber(e.target.value)}
                    placeholder="Account number"
                    aria-label="Bank account number"
                  />
                  <input
                    value={newBankBranch}
                    onChange={(e) => setNewBankBranch(e.target.value)}
                    placeholder="Branch"
                    aria-label="Bank branch"
                  />
                </>
              )}
              <button type="button" onClick={createLiquidAccount} aria-label="Create liquid account">
                Create account
              </button>
            </div>
          </div>

          <div className="card" style={{ marginBottom: 16, display: 'grid', gap: 8 }}>
            <h3>Transfer / deposit / withdrawal</h3>
            <p className="muted" style={{ margin: 0 }}>
              Transfer moves funds between liquid accounts. Deposit credits Owner&apos;s Equity (3000);
              withdrawal debits equity.
            </p>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
              <select value={xferKind} onChange={(e) => setXferKind(e.target.value)}>
                <option value="transfer">Transfer</option>
                <option value="deposit">Deposit</option>
                <option value="withdrawal">Withdrawal</option>
              </select>
              {(xferKind === 'transfer' || xferKind === 'withdrawal') && (
                <select value={xferFrom} onChange={(e) => setXferFrom(e.target.value)}>
                  <option value="">From</option>
                  {liquid.map((a) => (
                    <option key={a.id} value={a.id}>
                      {a.code} — {a.name} ({a.balance})
                    </option>
                  ))}
                </select>
              )}
              {(xferKind === 'transfer' || xferKind === 'deposit') && (
                <select value={xferTo} onChange={(e) => setXferTo(e.target.value)}>
                  <option value="">To</option>
                  {liquid.map((a) => (
                    <option key={a.id} value={a.id}>
                      {a.code} — {a.name} ({a.balance})
                    </option>
                  ))}
                </select>
              )}
              <input
                value={xferAmount}
                onChange={(e) => setXferAmount(e.target.value)}
                placeholder="Amount"
                style={{ width: 100 }}
              />
              <input
                value={xferRef}
                onChange={(e) => setXferRef(e.target.value)}
                placeholder="Reference"
                aria-label="Cash transfer reference"
              />
              <input
                value={xferNotes}
                onChange={(e) => setXferNotes(e.target.value)}
                placeholder="Notes"
                aria-label="Cash transfer notes"
                title="Optional notes (1–500 chars; letters/digits required)"
              />
              <button type="button" className="btn-ok" onClick={postTransfer} aria-label="Post cash transfer">
                Post
              </button>
            </div>
          </div>

          <h3>Liquid accounts</h3>
          <table className="table">
            <thead>
              <tr>
                <th>Code</th>
                <th>Name</th>
                <th>Kind</th>
                <th>Bank</th>
                <th>Balance</th>
              </tr>
            </thead>
            <tbody>
              {liquid.map((a) => (
                <tr key={a.id}>
                  <td>{a.code}</td>
                  <td>{a.name}</td>
                  <td>{a.is_cash_account ? 'cash' : a.is_bank_account ? 'bank' : '—'}</td>
                  <td>
                    {a.bank_name || '—'}
                    {a.bank_branch ? ` / ${a.bank_branch}` : ''}
                    {a.account_number ? ` (#${a.account_number})` : ''}
                  </td>
                  <td>{a.balance}</td>
                </tr>
              ))}
            </tbody>
          </table>

          <h3 style={{ marginTop: 16 }}>Recent movements</h3>
          <select
            value={xferKindManageFilter}
            onChange={(e) =>
              setXferKindManageFilter(
                e.target.value as 'all' | 'transfer' | 'deposit' | 'withdrawal',
              )
            }
            title="Filter cash movements by kind"
            aria-label="Cash transfer kind filter"
            style={{ marginBottom: 12 }}
          >
            <option value="all">All kinds</option>
            <option value="transfer">Transfer only</option>
            <option value="deposit">Deposit only</option>
            <option value="withdrawal">Withdrawal only</option>
          </select>
          <table className="table">
            <thead>
              <tr>
                <th>Kind</th>
                <th>From</th>
                <th>To</th>
                <th>Amount</th>
                <th>Reference</th>
              </tr>
            </thead>
            <tbody>
              {managedTransfers.length === 0 ? (
                <tr>
                  <td colSpan={5} className="muted">
                    No transfers for this filter
                  </td>
                </tr>
              ) : (
                managedTransfers.map((t) => (
                  <tr key={t.id}>
                    <td>{t.kind}</td>
                    <td>{t.from_account ? `${t.from_account.code} ${t.from_account.name}` : '—'}</td>
                    <td>{t.to_account ? `${t.to_account.code} ${t.to_account.name}` : '—'}</td>
                    <td>{t.amount}</td>
                    <td>{t.reference || '—'}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </>
      )}

      {tab === 'reconcile' && (
        <>
          <div className="card" style={{ marginBottom: 16, display: 'grid', gap: 8 }}>
            <h3>New statement</h3>
            <select
              value={reconAccountId}
              onChange={(e) => setReconAccountId(e.target.value)}
              aria-label="Reconcile liquid account"
            >
              {liquid.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.code} — {a.name} ({a.balance})
                </option>
              ))}
            </select>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              <input
                type="date"
                value={stmtDate}
                onChange={(e) => setStmtDate(e.target.value)}
                title="Statement date (YYYY-MM-DD)"
                aria-label="Statement date"
              />
              <input
                type="date"
                value={lineTxnDate}
                onChange={(e) => setLineTxnDate(e.target.value)}
                title="Statement line txn date (YYYY-MM-DD)"
                aria-label="Statement line txn date"
              />
              <input
                value={opening}
                onChange={(e) => setOpening(e.target.value)}
                placeholder="Opening"
                aria-label="Statement opening balance"
              />
              <input
                value={closing}
                onChange={(e) => setClosing(e.target.value)}
                placeholder="Closing"
                aria-label="Statement closing balance"
              />
              <input
                value={lineAmount}
                onChange={(e) => setLineAmount(e.target.value)}
                placeholder="Line amount (+in/−out)"
                aria-label="Statement line amount"
              />
              <input
                value={lineDesc}
                onChange={(e) => setLineDesc(e.target.value)}
                placeholder="Line desc"
                aria-label="Statement line description"
                title="Optional line description (1–500 chars; letters/digits required)"
              />
              <input
                value={lineExternalRef}
                onChange={(e) => setLineExternalRef(e.target.value)}
                placeholder="Line external ref (optional)"
                aria-label="Statement line external ref"
                title="Optional external ref (1–120 chars; letters/digits required)"
              />
            </div>
            <input
              value={stmtNotes}
              onChange={(e) => setStmtNotes(e.target.value)}
              placeholder="Statement notes (optional)"
              aria-label="Statement notes"
              title="Optional statement notes (1–500 chars; letters/digits required)"
            />
            <button
              onClick={createStatement}
              disabled={!reconAccountId}
              aria-label="Create bank statement"
            >
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

          <div className="card" style={{ marginBottom: 16, display: 'grid', gap: 8 }}>
            <h3>Bank API connections</h3>
            <p className="muted">
              Link a liquid GL account to a live feed (`mock` for demos/tests, `http_json` for any
              aggregator that returns JSON transactions). Sync creates a reconcilable statement;
              duplicates are skipped by external ref. Soft-deactivate pauses Sync / Celery auto-sync
              without deleting the connection (use Remove to delete).
            </p>
            <input aria-label="Bank connection display name" value={connName} onChange={(e) => setConnName(e.target.value)} placeholder="Connection name" />
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
                title="Absolute https feed URL (http only for localhost)"
                aria-label="Bank feed URL"
              />
            )}
            <button
              type="button"
              aria-label="Connect bank account"
              onClick={createConnection}
              disabled={!reconAccountId}
            >
              Connect selected liquid account
            </button>
            <select
              value={connectionManageFilter}
              onChange={(e) =>
                setConnectionManageFilter(e.target.value as 'all' | 'active' | 'inactive')
              }
              title="Filter manage bank connection list by status"
              aria-label="Bank connection status filter"
              style={{ marginTop: 8 }}
            >
              <option value="all">All statuses</option>
              <option value="active">Active only</option>
              <option value="inactive">Inactive only</option>
            </select>
            <ul>
              {managedConnections.map((c) => (
                <li key={c.id} style={{ marginBottom: 8 }}>
                  {c.display_name}
                  {c.is_active === false ? (
                    <span className="muted" style={{ marginLeft: 6, fontSize: 12 }}>
                      [inactive]
                    </span>
                  ) : null}{' '}
                  · {c.provider}
                  {c.is_active === false ? ' · inactive' : ' · active'}
                  {c.last_sync_status ? ` · last ${c.last_sync_status}` : ''}{' '}
                  <button
                    type="button"
                    onClick={() => syncConnection(c.id)}
                    disabled={c.is_active === false}
                    title={c.is_active === false ? 'Activate connection before syncing' : undefined}
                  >
                    Sync now
                  </button>{' '}
                  {c.is_active === false ? (
                    <button type="button" className="btn-ok" onClick={() => setConnectionActive(c.id, true)}>
                      Activate
                    </button>
                  ) : (
                    <button
                      type="button"
                      className="btn-danger"
                      onClick={() => setConnectionActive(c.id, false)}
                    >
                      Deactivate
                    </button>
                  )}{' '}
                  <button type="button" onClick={() => removeConnection(c.id)}>
                    Remove
                  </button>
                </li>
              ))}
              {!managedConnections.length && (
                <li className="muted">
                  {connections.length ? 'No connections for this filter' : 'No API connections yet'}
                </li>
              )}
            </ul>
          </div>

          <h3>Statements</h3>
          <select
            value={statementManageFilter}
            onChange={(e) =>
              setStatementManageFilter(
                e.target.value as 'all' | 'draft' | 'in_progress' | 'reconciled'
              )
            }
            title="Filter bank statement list by status"
            aria-label="Bank statement status filter"
            style={{ marginBottom: 12 }}
          >
            <option value="all">All statuses</option>
            <option value="draft">Draft only</option>
            <option value="in_progress">In progress only</option>
            <option value="reconciled">Reconciled only</option>
          </select>
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
              {managedStatements.map((s) => (
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
              {!managedStatements.length && (
                <tr>
                  <td colSpan={6} className="muted">
                    No statements for this filter
                  </td>
                </tr>
              )}
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
                style={{ marginBottom: 12, marginRight: 8 }}
              >
                Auto-clear medium+
              </button>
              <button
                onClick={() => autoClear('low')}
                disabled={selected.status === 'reconciled'}
                style={{ marginBottom: 12 }}
              >
                Auto-clear low+
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
                <input
                  value={clearGroupNotes}
                  onChange={(e) => setClearGroupNotes(e.target.value)}
                  placeholder="Clear-group notes (optional)"
                  aria-label="Clear-group notes"
                  title="Optional clear-group notes (1–500 chars; letters/digits required)"
                  style={{ display: 'block', width: '100%', marginBottom: 8 }}
                />
                <button
                  onClick={clearGroup}
                  disabled={!pickBank.length || !pickBook.length}
                  aria-label="Clear selected as group"
                >
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
                                  aria-label="Match bank line to journal line"
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
          <p className="muted">
            Received cheques post to 1020 then deposit/clear to Bank. Issued cheques post to 2015 until
            cleared against Bank.
          </p>
          <div className="card" style={{ marginBottom: 12, display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'center' }}>
            <label style={{ display: 'inline-flex', gap: 6, alignItems: 'center' }}>
              Direction
              <select
                aria-label="Cheque direction filter"
                value={chequeDirection}
                onChange={(e) => {
                  const v = e.target.value;
                  setChequeDirection(v);
                  void loadCheques(v, chequeStatus);
                }}
              >
                <option value="">All</option>
                <option value="received">received</option>
                <option value="issued">issued</option>
              </select>
            </label>
            <label style={{ display: 'inline-flex', gap: 6, alignItems: 'center' }}>
              Status
              <select
                aria-label="Cheque status filter"
                value={chequeStatus}
                onChange={(e) => {
                  const v = e.target.value;
                  setChequeStatus(v);
                  void loadCheques(chequeDirection, v);
                }}
              >
                <option value="">All</option>
                <option value="pending">pending</option>
                <option value="deposited">deposited</option>
                <option value="cleared">cleared</option>
                <option value="bounced">bounced</option>
                <option value="cancelled">cancelled</option>
              </select>
            </label>
          </div>
          <div className="card" style={{ marginBottom: 12 }}>
            <label>
              Bounce / Cancel reason{' '}
              <input
                value={chequeActionReason}
                onChange={(e) => setChequeActionReason(e.target.value)}
                placeholder="Required before Bounce or Cancel"
                title="Required bounce/cancel reason (1–500 chars; letters/digits required)"
                aria-label="Cheque bounce cancel reason"
                style={{ minWidth: 280 }}
              />
            </label>
            <p className="muted" style={{ marginTop: 6 }}>
              Appended to cheque notes and journal description (`POST .../bounce|cancel` {'{ reason }'}).
            </p>
          </div>
          <table className="table">
            <thead>
              <tr>
                <th>Number</th>
                <th>Dir</th>
                <th>Status</th>
                <th>Amount</th>
                <th>Bank</th>
                <th>Notes</th>
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
                  <td className="muted" style={{ maxWidth: 240, whiteSpace: 'pre-wrap' }}>
                    {c.notes || '—'}
                  </td>
                  <td style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                    {c.direction === 'received' && c.status === 'pending' && (
                      <button className="btn-ok" onClick={() => chequeAction(c.id, 'deposit')}>Deposit</button>
                    )}
                    {(c.status === 'pending' || c.status === 'deposited') && (
                      <button className="btn-ok" onClick={() => chequeAction(c.id, 'clear')}>Clear</button>
                    )}
                    {c.status !== 'bounced' && c.status !== 'cancelled' && (
                      <button
                        className="btn-danger"
                        onClick={() => chequeAction(c.id, 'bounce')}
                        aria-label={`Bounce cheque ${c.id}`}
                      >
                        Bounce
                      </button>
                    )}
                    {c.direction === 'issued' && c.status === 'pending' && (
                      <button
                        className="btn-danger"
                        onClick={() => chequeAction(c.id, 'cancel')}
                        aria-label={`Cancel cheque ${c.id}`}
                      >
                        Cancel
                      </button>
                    )}
                  </td>
                </tr>
              ))}
              {!cheques.length && (
                <tr>
                  <td colSpan={7} className="muted">
                    No cheques — record a customer/supplier payment with method cheque
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </>
      )}
      {attachPreview && (
        <AttachmentPreview
          open
          apiPath={attachPreview.apiPath}
          title={attachPreview.title}
          onClose={() => setAttachPreview(null)}
          onError={(msg) => setError(msg)}
        />
      )}
    </Shell>
  );
}
