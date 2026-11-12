'use client';

/**
 * The lock around a till screen (retail POS and restaurant till).
 *
 * Quiet for 60 seconds, the till locks. A cashier unlocks with a personal passcode and
 * from then on the server treats them as the person at the till. If the page starts
 * locked it does not mount at all, so a refresh shows nothing behind the lock. A lock
 * mid-sale keeps the page mounted underneath, so the same cashier returns to exactly
 * where they left off.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { api, formatApiError } from '../lib/api';
import { loadCompanyLogo } from '../lib/companyLogo';
import { invalidateMeCache } from '../lib/meCache';
import { getOrCreateDeviceId, hydrateDeviceId } from '../lib/posOffline';
import {
  POS_LOCK_NOW_EVENT,
  POS_LOCKED_EVENT,
  POS_OPERATOR_HEADER,
  checkOfflinePasscode,
  clearLeftLocked,
  clearTillOnlyPending,
  getOperatorToken,
  holdOperatorToken,
  offlineVerifierFor,
  parkForOwner,
  readTillSale,
  rememberWelcome,
  resumeHeldToken,
  saveCurrentSale,
  saveOfflineVerifier,
  setOperatorToken,
  setTillLockedFlag,
  setTillOnlyLocal,
  takeParked,
  tillOnlyPendingServer,
  takeWelcome,
  wasLeftLocked,
  type TillOperator,
  type TillSnapshot,
  type TillSurface,
} from '../lib/posLock';
import './pos-lock.css';

const FALLBACK_LOGO = '/brand/logo-sidebar.png';
const ACTIVITY_EVENTS = ['pointerdown', 'pointermove', 'keydown', 'touchstart', 'wheel', 'scroll'] as const;
const PING_EVERY_MS = 20_000;

type LockState = {
  enforced: boolean;
  locked: boolean;
  login_user_id: string;
  idle_seconds: number;
  passcode_length: number;
  operator: TillOperator | null;
  last_operator: TillOperator | null;
  company: { id: string; name: string; has_logo: boolean; logo_version: string | null };
};

type Phase = 'checking' | 'locked-first' | 'open';

function tenantOf(): string {
  try {
    return localStorage.getItem('tenant') || '';
  } catch {
    return '';
  }
}

function plainError(err: unknown, fallback: string): string {
  return err instanceof Error && err.message ? err.message : fallback;
}

/** A lock nobody can open would stop the shop: the company needs passcodes, and offline a saved one. */
function canLock(state: LockState | null, offline: boolean): boolean {
  if (offline) return Boolean(offlineVerifierFor(tenantOf()));
  return Boolean(state?.enforced);
}

function isNoAnswer(err: unknown): boolean {
  return (err as { status?: number })?.status === undefined;
}

function LockScreen({
  surface,
  state,
  onUnlocked,
}: {
  surface: TillSurface;
  state: LockState | null;
  onUnlocked: (operator: TillOperator, result: { switched: boolean; offline?: boolean }) => void;
}) {
  const length = state?.passcode_length || 6;
  const [code, setCode] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [logo, setLogo] = useState<string | null>(null);
  const [online, setOnline] = useState(() => typeof navigator === 'undefined' || navigator.onLine !== false);
  const busyRef = useRef(false);

  useEffect(() => {
    const up = () => setOnline(true);
    const down = () => setOnline(false);
    window.addEventListener('online', up);
    window.addEventListener('offline', down);
    return () => {
      window.removeEventListener('online', up);
      window.removeEventListener('offline', down);
    };
  }, []);

  useEffect(() => {
    let live = true;
    const version = state?.company?.logo_version;
    const tenant = state?.company?.id;
    if (state?.company?.has_logo && version && tenant) {
      void loadCompanyLogo(tenant, version).then((url) => {
        if (live) setLogo(url);
      });
    }
    return () => {
      live = false;
    };
  }, [state?.company?.has_logo, state?.company?.id, state?.company?.logo_version]);

  const submitCode = useCallback(
    async (value: string) => {
      if (busyRef.current || value.length !== length) return;
      busyRef.current = true;
      setBusy(true);
      setError('');
      const tenant = tenantOf();
      try {
        const res = await api('/pos/lock/unlock', {
          method: 'POST',
          body: JSON.stringify({ surface, device_id: getOrCreateDeviceId(), passcode: value }),
        });
        const data = res.data;
        setOperatorToken(data.operator_token);
        await saveOfflineVerifier(tenant, data.operator, value);
        onUnlocked(data.operator, { switched: Boolean(data.switched) });
      } catch (err) {
        setCode('');
        if (isNoAnswer(err)) {
          const check = await checkOfflinePasscode(tenant, value);
          if (check.ok && check.operator) {
            resumeHeldToken();
            onUnlocked(check.operator, { switched: false, offline: true });
          } else if (check.waitMs) {
            setError(`Too many wrong passcodes. Try again in ${Math.ceil(check.waitMs / 60000)} minutes.`);
          } else if (offlineVerifierFor(tenant)) {
            setError('That passcode is not right. While offline, only the last cashier on this till can unlock.');
          } else {
            setError('This till is offline and cannot check that passcode. Reconnect to unlock.');
          }
        } else {
          setError(plainError(err, 'That passcode is not right.'));
        }
      } finally {
        busyRef.current = false;
        setBusy(false);
      }
    },
    [length, onUnlocked, surface]
  );

  const press = useCallback(
    (key: string) => {
      setError('');
      setCode((prev) => {
        if (key === 'clear') return '';
        if (key === 'back') return prev.slice(0, -1);
        if (prev.length >= length) return prev;
        const next = prev + key;
        if (next.length === length) void submitCode(next);
        return next;
      });
    },
    [length, submitCode]
  );

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (/^\d$/.test(event.key)) press(event.key);
      else if (event.key === 'Backspace') press('back');
      else if (event.key === 'Escape') press('clear');
      else return;
      event.preventDefault();
      event.stopPropagation();
    };
    window.addEventListener('keydown', onKey, true);
    return () => window.removeEventListener('keydown', onKey, true);
  }, [press]);

  // Keyboard focus must not reach the menu or Log out behind the lock.
  useEffect(() => {
    const keepInside = (event: FocusEvent) => {
      const target = event.target as HTMLElement | null;
      if (target?.closest?.('.plock')) return;
      document.querySelector<HTMLElement>('.plock-keys button')?.focus();
    };
    document.addEventListener('focusin', keepInside);
    return () => document.removeEventListener('focusin', keepInside);
  }, []);

  const name = state?.company?.name || 'Ribdigi ERP';
  const last = state?.last_operator?.name;

  return (
    <div className="plock plock-split" role="dialog" aria-modal="true" aria-label="POS Locked">
      <section className="plock-brand">
        <div className={`plock-logo${logo ? ' has-company-logo' : ''}`}>
          <img src={logo || FALLBACK_LOGO} alt={logo ? `${name} logo` : 'Ribdigi ERP'} />
        </div>
        <p className="plock-company">{name}</p>
      </section>

      <section className="plock-pad">
        <h1 className="plock-title">
          <svg viewBox="0 0 24 24" aria-hidden>
            <path
              fill="currentColor"
              d="M12 2a5 5 0 0 0-5 5v3H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-8a2 2 0 0 0-2-2h-1V7a5 5 0 0 0-5-5Zm-3 8V7a3 3 0 1 1 6 0v3H9Z"
            />
          </svg>
          POS Locked
        </h1>
        <p className="plock-hint">{last ? `Enter your passcode. Last used by ${last}.` : 'Enter your passcode.'}</p>
        {!online ? <p className="plock-offline">Offline. Only the last cashier on this till can unlock.</p> : null}

        <div className="plock-dots" role="status" aria-label={`${code.length} of ${length} digits entered`}>
          {Array.from({ length }).map((_, i) => (
            <span key={i} className={i < code.length ? 'is-filled' : ''} />
          ))}
        </div>
        <div className="plock-keys">
          {['1', '2', '3', '4', '5', '6', '7', '8', '9'].map((key) => (
            <button key={key} type="button" disabled={busy} onClick={() => press(key)}>
              {key}
            </button>
          ))}
          <button type="button" className="plock-key-soft" disabled={busy} onClick={() => press('clear')}>
            Clear
          </button>
          <button type="button" disabled={busy} onClick={() => press('0')}>
            0
          </button>
          <button
            type="button"
            className="plock-key-soft"
            aria-label="Delete last digit"
            disabled={busy}
            onClick={() => press('back')}
          >
            ⌫
          </button>
        </div>
        <button
          type="button"
          className="plock-unlock"
          disabled={busy || code.length !== length}
          onClick={() => void submitCode(code)}
        >
          {busy ? 'Checking…' : 'Unlock'}
        </button>

        <p className="plock-error" role="alert">
          {error}
        </p>
      </section>
    </div>
  );
}

export default function PosLockGate({ surface, children }: { surface: TillSurface; children: React.ReactNode }) {
  const [phase, setPhase] = useState<Phase>('checking');
  const [locked, setLocked] = useState(false);
  const [state, setState] = useState<LockState | null>(null);
  const [welcome, setWelcome] = useState('');
  const [failed, setFailed] = useState('');
  const wrapRef = useRef<HTMLDivElement | null>(null);
  const lastActive = useRef(Date.now());
  const lastPing = useRef(Date.now());
  const operatorRef = useRef<string>('');
  const stateRef = useRef<LockState | null>(null);
  stateRef.current = state;

  const refreshState = useCallback(async () => {
    const device = await hydrateDeviceId();
    const res = await api(`/pos/lock/state?surface=${surface}&device_id=${encodeURIComponent(device)}`);
    setState(res.data);
    return res.data as LockState;
  }, [surface]);

  useEffect(() => {
    let live = true;
    (async () => {
      try {
        const data = await refreshState();
        if (!live) return;
        operatorRef.current = data.operator?.id || '';
        if (data.locked) {
          holdOperatorToken();
          setLocked(true);
          setPhase('locked-first');
        } else {
          clearLeftLocked();
          setPhase('open');
        }
      } catch (err) {
        if (!live) return;
        // No answer: an offline till that was left locked stays locked if it can be unlocked here.
        const stuck = wasLeftLocked() && Boolean(offlineVerifierFor(tenantOf()));
        if (isNoAnswer(err) && stuck) {
          setTillLockedFlag(true);
          setLocked(true);
          setPhase('locked-first');
        } else {
          if (!isNoAnswer(err)) setFailed(`Could not check the till lock. ${formatApiError({}, (err as { status?: number }).status || 0)}`);
          setPhase('open');
        }
      }
    })();
    const name = takeWelcome();
    if (name) setWelcome(name);
    return () => {
      live = false;
      setTillLockedFlag(false);
    };
  }, [refreshState]);

  useEffect(() => {
    if (!failed) return;
    const id = window.setTimeout(() => setFailed(''), 5000);
    return () => window.clearTimeout(id);
  }, [failed]);

  useEffect(() => {
    if (!welcome) return;
    const id = window.setTimeout(() => setWelcome(''), 3500);
    return () => window.clearTimeout(id);
  }, [welcome]);

  const lockNow = useCallback(
    (reason: 'idle' | 'manual') => {
      const token = getOperatorToken();
      holdOperatorToken();
      setLocked(true);
      void api('/pos/lock/lock', {
        method: 'POST',
        headers: token ? { [POS_OPERATOR_HEADER]: token } : {},
        body: JSON.stringify({ surface, device_id: getOrCreateDeviceId(), reason }),
      }).catch(() => undefined);
      void refreshState().catch(() => undefined);
    },
    [refreshState, surface]
  );

  // Inactivity timer and the activity ping the server's own idle check relies on.
  useEffect(() => {
    if (phase !== 'open' || locked) return;
    lastActive.current = Date.now();
    const seen = () => {
      lastActive.current = Date.now();
    };
    const opts: AddEventListenerOptions = { capture: true, passive: true };
    ACTIVITY_EVENTS.forEach((name) => window.addEventListener(name, seen, opts));
    const check = () => {
      const now = Date.now();
      const idleMs = (stateRef.current?.idle_seconds || 60) * 1000;
      const offline = typeof navigator !== 'undefined' && navigator.onLine === false;
      if (now - lastActive.current >= idleMs) {
        if (canLock(stateRef.current, offline)) lockNow('idle');
        return;
      }
      if (!offline && getOperatorToken() && lastActive.current > lastPing.current && now - lastPing.current >= PING_EVERY_MS) {
        lastPing.current = now;
        void api('/pos/lock/ping', {
          method: 'POST',
          body: JSON.stringify({ surface, device_id: getOrCreateDeviceId() }),
        }).catch(() => undefined);
      }
    };
    const id = window.setInterval(check, 1000);
    document.addEventListener('visibilitychange', check);
    return () => {
      ACTIVITY_EVENTS.forEach((name) => window.removeEventListener(name, seen, opts));
      window.clearInterval(id);
      document.removeEventListener('visibilitychange', check);
    };
  }, [phase, locked, lockNow, surface]);

  useEffect(() => {
    const serverLocked = () => {
      setLocked(true);
      void refreshState().catch(() => undefined);
    };
    const asked = () => {
      const offline = typeof navigator !== 'undefined' && navigator.onLine === false;
      if (canLock(stateRef.current, offline)) lockNow('manual');
      else setFailed('Set a till passcode for your staff first. Until then this till cannot be locked.');
    };
    window.addEventListener(POS_LOCKED_EVENT, serverLocked);
    window.addEventListener(POS_LOCK_NOW_EVENT, asked);
    return () => {
      window.removeEventListener(POS_LOCKED_EVENT, serverLocked);
      window.removeEventListener(POS_LOCK_NOW_EVENT, asked);
    };
  }, [lockNow, refreshState]);

  useEffect(() => {
    const el = wrapRef.current;
    if (!el) return;
    if (locked) el.setAttribute('inert', '');
    else el.removeAttribute('inert');
  }, [locked, phase]);

  const onUnlocked = useCallback(
    (operator: TillOperator, result: { switched: boolean; offline?: boolean }) => {
      // A passcode opens the till and Sales only. The rest waits for a full sign-in with a password.
      setTillOnlyLocal(true, { pendingServer: Boolean(result.offline) });
      // What is on screen so far belongs to the last cashier, or on a first unlock to the login.
      const shownFor = phase === 'open' ? operatorRef.current : stateRef.current?.login_user_id;
      if (shownFor !== operator.id && !result.offline) {
        // A different person: reload so shift, permissions and cart start from their identity.
        // The cart was saved as it changed, and the handover question is asked after this.
        rememberWelcome(operator.name);
        invalidateMeCache();
        window.location.reload();
        return;
      }
      operatorRef.current = operator.id;
      invalidateMeCache();
      lastActive.current = Date.now();
      lastPing.current = Date.now();
      setTillLockedFlag(false);
      setLocked(false);
      setPhase('open');
      setWelcome(operator.name);
    },
    [phase]
  );

  // An offline unlock could not hold the session to the till on the server; do it on reconnect.
  useEffect(() => {
    const tell = () => {
      if (!tillOnlyPendingServer() || (typeof navigator !== 'undefined' && navigator.onLine === false)) return;
      void api('/pos/lock/restrict', { method: 'POST' })
        .then(() => clearTillOnlyPending())
        .catch(() => undefined);
    };
    tell();
    window.addEventListener('online', tell);
    return () => window.removeEventListener('online', tell);
  }, []);

  if (phase === 'checking') {
    return <div className="plock plock-checking" aria-busy="true" />;
  }
  return (
    <>
      {phase === 'open' ? (
        <div ref={wrapRef} className="plock-page">
          {children}
        </div>
      ) : null}
      {locked ? <LockScreen surface={surface} state={state} onUnlocked={onUnlocked} /> : null}
      {welcome ? (
        <div className="plock-welcome" role="status">
          Signed in as <strong>{welcome}</strong>
        </div>
      ) : null}
      {failed ? (
        <div className="plock-welcome plock-welcome-bad" role="alert">
          {failed}
        </div>
      ) : null}
    </>
  );
}

/** The small Lock button on a till's top bar: step away, or hand the till to someone else. */
export function PosLockButton({ className }: { className?: string }) {
  return (
    <button
      type="button"
      className={className}
      aria-label="Lock this till"
      onClick={() => window.dispatchEvent(new Event(POS_LOCK_NOW_EVENT))}
    >
      Lock
    </button>
  );
}

type Owner = { id: string; name: string; tenantId: string } | null;

/**
 * Keep the sale on this till safe across a lock, refresh or crash, and settle whose it is.
 *
 * A sale left by another cashier is never quietly given to the new one. They choose, and
 * the server records the choice. Until they do, the question covers the till.
 */
export function useTillSale<T>({
  surface,
  owner,
  itemCount,
  total,
  data,
  restore,
  startedBy,
}: {
  surface: TillSurface;
  owner: Owner;
  itemCount: number;
  total: number;
  data: T;
  restore: (data: T, startedBy: string | null) => void;
  startedBy?: string | null;
}) {
  const [settled, setSettled] = useState(false);
  const [question, setQuestion] = useState<TillSnapshot | null>(null);
  const restoreRef = useRef(restore);
  restoreRef.current = restore;

  useEffect(() => {
    if (!owner || settled || question) return;
    const till = readTillSale(surface, owner.tenantId);
    const left = till.current;
    if (left && left.owner_id !== owner.id && left.item_count > 0) {
      setQuestion(left);
      return;
    }
    const mine = left && left.owner_id === owner.id ? left : takeParked(surface, owner.tenantId, owner.id);
    if (mine) restoreRef.current(mine.data as T, mine.started_by || null);
    setSettled(true);
  }, [owner, question, settled, surface]);

  useEffect(() => {
    if (!owner || !settled) return;
    saveCurrentSale(
      surface,
      owner.tenantId,
      itemCount > 0
        ? {
            owner_id: owner.id,
            owner_name: owner.name,
            at: Date.now(),
            item_count: itemCount,
            total,
            data,
            started_by: startedBy || null,
          }
        : null
    );
  }, [data, itemCount, owner, settled, startedBy, surface, total]);

  const decide = useCallback(
    (decision: 'take_over' | 'keep_for_owner') => {
      if (!owner || !question) return;
      void api('/pos/lock/handover', {
        method: 'POST',
        body: JSON.stringify({
          surface,
          device_id: getOrCreateDeviceId(),
          from_user_id: question.owner_id,
          decision,
          item_count: question.item_count,
          total: question.total,
        }),
      }).catch(() => undefined);
      if (decision === 'take_over') {
        restoreRef.current(question.data as T, question.started_by || question.owner_id);
      } else {
        parkForOwner(surface, owner.tenantId, question);
        const mine = takeParked(surface, owner.tenantId, owner.id);
        if (mine) restoreRef.current(mine.data as T, mine.started_by || null);
      }
      setQuestion(null);
      setSettled(true);
    },
    [owner, question, surface]
  );

  const handover = useMemo(() => {
    if (!question) return null;
    const count = question.item_count;
    return (
      <div className="plock plock-handover" role="dialog" aria-modal="true" aria-label="Sale started by another cashier">
        <div className="plock-card">
          <h1 className="plock-title">Whose sale is this?</h1>
          <p className="plock-hint">
            <strong>{question.owner_name}</strong> left a sale on this till with {count} {count === 1 ? 'item' : 'items'}.
          </p>
          <div className="plock-choice">
            <button type="button" className="plock-unlock" onClick={() => decide('take_over')}>
              Take over this sale
              <small>It will be recorded under your name, and as started by {question.owner_name}.</small>
            </button>
            <button type="button" className="plock-unlock plock-unlock-soft" onClick={() => decide('keep_for_owner')}>
              Keep it for {question.owner_name}
              <small>You start a new sale. It comes back when they unlock this till.</small>
            </button>
          </div>
        </div>
      </div>
    );
  }, [decide, question]);

  return { handover };
}

