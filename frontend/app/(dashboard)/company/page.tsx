'use client';

import { useEffect, useState } from 'react';
import PageHeader from '../../../components/PageHeader';
import { api, apiFetch, apiOptional } from '../../../lib/api';
import { getMe, invalidateMeCache } from '../../../lib/meCache';
import { formatDateTime, formatNumber, formatWhen, plainLabel, rememberFormatPrefs } from '../../../lib/format';
import { canDownloadStaffGuide, industryLabel } from '../../../lib/industries';
import { TAX_COUNTRIES } from '../../../lib/taxCountries';

const FISCAL_MMDD = /^(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])$/;

function fiscalStartError(raw: string): string {
  const value = raw.trim();
  if (!FISCAL_MMDD.test(value)) {
    return 'Enter the fiscal year start as MM-DD, for example 01-01.';
  }
  const month = Number(value.slice(0, 2));
  const day = Number(value.slice(3, 5));
  const year = month === 2 && day === 29 ? 2024 : 2023;
  const parsed = new Date(Date.UTC(year, month - 1, day));
  if (parsed.getUTCMonth() !== month - 1 || parsed.getUTCDate() !== day) {
    return 'Enter a real calendar day as MM-DD, for example 01-01.';
  }
  return '';
}

function mergeFields(current: any, data: any, keys: string[]) {
  const next = { ...(current || {}) };
  for (const key of keys) {
    if (data && Object.prototype.hasOwnProperty.call(data, key)) next[key] = data[key];
  }
  return next;
}

export default function Page() {
  const [tenant, setTenant] = useState<any>(null);
  const [emailStatus, setEmailStatus] = useState<any>(null);
  const [smsStatus, setSmsStatus] = useState<any>(null);
  const [profilePhone, setProfilePhone] = useState('');
  const [profileFullName, setProfileFullName] = useState('');
  const [logoPreview, setLogoPreview] = useState<string | null>(null);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [printHeader, setPrintHeader] = useState('');
  const [printFooter, setPrintFooter] = useState('');
  const [invTemplate, setInvTemplate] = useState('a4');
  const [receiptPaper, setReceiptPaper] = useState('80mm');
  const [emailHost, setEmailHost] = useState('');
  const [emailPort, setEmailPort] = useState('587');
  const [emailUser, setEmailUser] = useState('');
  const [emailPassword, setEmailPassword] = useState('');
  const [emailFromEmail, setEmailFromEmail] = useState('');
  const [emailFromName, setEmailFromName] = useState('');
  const [emailUseTls, setEmailUseTls] = useState(true);
  const [emailUseSsl, setEmailUseSsl] = useState(false);
  const [smsAccountSid, setSmsAccountSid] = useState('');
  const [smsAuthToken, setSmsAuthToken] = useState('');
  const [smsFromNumber, setSmsFromNumber] = useState('');
  const [loadBusy, setLoadBusy] = useState(true);
  const [canGuide, setCanGuide] = useState(false);
  const [guideBusy, setGuideBusy] = useState(false);
  const [guideError, setGuideError] = useState('');
  const [profileBusy, setProfileBusy] = useState(false);
  const [printBusy, setPrintBusy] = useState(false);
  const [emailBusy, setEmailBusy] = useState(false);
  const [smsBusy, setSmsBusy] = useState(false);
  const [meBusy, setMeBusy] = useState(false);
  const [myProfileBusy, setMyProfileBusy] = useState(false);
  const [profileFlash, setProfileFlash] = useState<{ ok?: string; err?: string }>({});
  const [printFlash, setPrintFlash] = useState<{ ok?: string; err?: string }>({});
  const [emailFlash, setEmailFlash] = useState<{ ok?: string; err?: string }>({});
  const [smsFlash, setSmsFlash] = useState<{ ok?: string; err?: string }>({});
  const [meFlash, setMeFlash] = useState<{ ok?: string; err?: string }>({});
  const [industryValid, setIndustryValid] = useState(true);

  const [logoBusy, setLogoBusy] = useState(false);
  const [meRole, setMeRole] = useState('');
  const [offlineHours, setOfflineHours] = useState('168');
  const [storeLimitDraft, setStoreLimitDraft] = useState('');
  const [timeoutDraft, setTimeoutDraft] = useState('30');
  const [taxFlash, setTaxFlash] = useState<{ ok?: string; err?: string }>({});
  const [fiscalFlash, setFiscalFlash] = useState<{ ok?: string; err?: string }>({});
  const [timeoutFlash, setTimeoutFlash] = useState<{ ok?: string; err?: string }>({});
  const [logoFlash, setLogoFlash] = useState<{ ok?: string; err?: string }>({});
  const [storeFlash, setStoreFlash] = useState<{ ok?: string; err?: string }>({});
  const [taxBusy, setTaxBusy] = useState(false);
  const [fiscalBusy, setFiscalBusy] = useState(false);
  const [timeoutBusy, setTimeoutBusy] = useState(false);
  const [storeBusy, setStoreBusy] = useState(false);

  const LOGO_MAX_BYTES = 2_000_000;
  const LOGO_TYPES = new Set(['image/png', 'image/jpeg', 'image/jpg', 'image/webp', 'image/gif']);

  async function loadLogoPreview(hasLogo: boolean) {
    if (!hasLogo) {
      setLogoPreview(null);
      return;
    }
    try {
      const res = await apiFetch('/tenants/me/logo');
      if (!res.ok) {
        setLogoPreview(null);
        return;
      }
      const blob = await res.blob();
      setLogoPreview((prev) => {
        if (prev) URL.revokeObjectURL(prev);
        return URL.createObjectURL(blob);
      });
    } catch {
      setLogoPreview(null);
    }
  }

  async function refresh() {
    setLoadBusy(true);
    const [r, e, s, me, print] = await Promise.all([
      apiOptional('/tenants/me'),
      apiOptional('/settings/email'),
      apiOptional('/settings/sms'),
      getMe().then((body) => ({ ...body, error: null as string | null })).catch((err: any) => ({
        data: null,
        error: err?.message || 'Could not load your profile',
      })),
      apiOptional('/settings/print'),
    ]);
    const loadError = [r, e, s, me].map((x) => x.error).filter(Boolean).join(' ');
    if (r.data) {
      setTenant(r.data);
      setOfflineHours(String(r.data.offline_auth_hours ?? 168));
      setStoreLimitDraft(
        r.data.store_limit == null || r.data.store_limit === '' ? '' : String(r.data.store_limit),
      );
      setTimeoutDraft(String(r.data.inactivity_timeout_minutes ?? 30));
    }
    setEmailStatus(e.data);
    if (e.data) {
      setEmailHost(e.data.host || '');
      setEmailPort(String(e.data.port ?? 587));
      setEmailUser(e.data.username || '');
      setEmailPassword('');
      setEmailFromEmail(e.data.from_email || '');
      setEmailFromName(e.data.from_name || '');
      setEmailUseTls(e.data.use_tls !== false);
      setEmailUseSsl(!!e.data.use_ssl);
    }
    setSmsStatus(s.data);
    if (s.data) {
      setSmsAccountSid(s.data.account_sid || '');
      setSmsAuthToken('');
      setSmsFromNumber(s.data.from_number || '');
    }
    setProfilePhone(me.data?.phone || '');
    setProfileFullName(me.data?.full_name || '');
    setCanGuide(canDownloadStaffGuide(me.data?.role, me.data?.permissions));
    setMeRole(me.data?.role || '');
    if (me.data) {
      setIndustryValid(me.data.industry_valid !== false);
    }
    if (print.data) {
      setPrintHeader(print.data.header_text || '');
      setPrintFooter(print.data.footer_text || '');
      setInvTemplate(print.data.default_invoice_template || 'a4');
      setReceiptPaper(print.data.default_receipt_paper || '80mm');
    }
    setError(loadError);
    setLoadBusy(false);
    if (r.data) {
      await loadLogoPreview(!!r.data.has_logo);
    }
  }

  async function reloadEmailSettings() {
    const e = await apiOptional('/settings/email');
    setEmailStatus(e.data);
    if (e.data) {
      setEmailHost(e.data.host || '');
      setEmailPort(String(e.data.port ?? 587));
      setEmailUser(e.data.username || '');
      setEmailPassword('');
      setEmailFromEmail(e.data.from_email || '');
      setEmailFromName(e.data.from_name || '');
      setEmailUseTls(e.data.use_tls !== false);
      setEmailUseSsl(!!e.data.use_ssl);
      setEmailFlash({});
    } else {
      setEmailFlash({ err: e.error || 'Email settings could not be loaded.' });
    }
  }

  async function reloadSmsSettings() {
    const s = await apiOptional('/settings/sms');
    setSmsStatus(s.data);
    if (s.data) {
      setSmsAccountSid(s.data.account_sid || '');
      setSmsAuthToken('');
      setSmsFromNumber(s.data.from_number || '');
      setSmsFlash({});
    } else {
      setSmsFlash({ err: s.error || 'SMS settings could not be loaded.' });
    }
  }

  useEffect(() => {
    refresh().catch((err) => {
      setError(err.message);
      setLoadBusy(false);
    });
  }, []);

  async function downloadStaffGuide() {
    setGuideError('');
    setGuideBusy(true);
    try {
      const response = await apiFetch('/staff-guide');
      const type = (response.headers.get('content-type') || '').toLowerCase();
      if (!response.ok || !type.includes('pdf')) {
        let detail = 'Could not download the guide.';
        try {
          const body = await response.json();
          const raw = body?.detail;
          if (typeof raw === 'string') detail = raw;
          else if (raw?.message) detail = String(raw.message);
        } catch {
          if (response.status === 401) detail = 'Sign in required';
          if (response.status === 403) detail = 'Missing permission: staff_guide:download';
        }
        setGuideError(detail);
        return;
      }
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = 'RIBDIGI-ERP-Customer-User-Guide.pdf';
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    } catch {
      setGuideError('Could not download the guide.');
    } finally {
      setGuideBusy(false);
    }
  }

  async function save() {
    setProfileFlash({});
    const tradingName = String(tenant.company_name || '').trim();
    if (!tradingName) {
      setProfileFlash({ err: 'Enter a trading name. It is required.' });
      return;
    }
    setProfileBusy(true);
    try {
      const r = await api('/tenants/me', {
        method: 'PATCH',
        body: JSON.stringify({
          company_name: String(tenant.company_name || '').trim(),
          currency: tenant.currency,
          // Omit blank phone so Save does not 422 (E164PhoneValue); leave prior value.
          ...(String(tenant.phone || '').trim()
            ? { phone: String(tenant.phone).trim() }
            : {}),
          // Omit blank email so Save does not 422 (EmailStr); leave prior value.
          ...(String(tenant.email || '').trim()
            ? { email: String(tenant.email).trim() }
            : {}),
          // Omit blank website so Save does not 422 (WebhookUrlValue); leave prior value.
          ...(String(tenant.website || '').trim()
            ? { website: String(tenant.website).trim() }
            : {}),
          // Omit blank HQ address so Save does not 422 (AddressValue); leave prior.
          ...(String(tenant.address || '').trim()
            ? { address: String(tenant.address).trim() }
            : {}),
          // Omit blank legal name so Save does not 422 (LegalNameValue); leave prior.
          ...(String(tenant.legal_name || '').trim()
            ? { legal_name: String(tenant.legal_name).trim() }
            : {}),
          // Omit blank registration so Save does not 422 (RegistrationNumberValue); leave prior.
          ...(String(tenant.registration_number || '').trim()
            ? { registration_number: String(tenant.registration_number).trim() }
            : {}),
          // Omit blank contact so Save does not 422 (ContactPersonValue); leave prior.
          ...(String(tenant.contact_person || '').trim()
            ? { contact_person: String(tenant.contact_person).trim() }
            : {}),
          timezone: tenant.timezone,
          date_format: tenant.date_format,
          decimal_separator: tenant.decimal_separator,
          thousand_separator: tenant.thousand_separator,
          time_format: tenant.time_format,
        }),
      });
      setTenant((current: any) =>
        mergeFields(current, r.data, [
          'company_name',
          'legal_name',
          'phone',
          'email',
          'address',
          'website',
          'contact_person',
          'registration_number',
          'currency',
          'timezone',
          'date_format',
          'decimal_separator',
          'thousand_separator',
          'time_format',
        ]),
      );
      rememberFormatPrefs({
        date_format: r.data?.date_format,
        decimal_separator: r.data?.decimal_separator,
        thousand_separator: r.data?.thousand_separator,
        time_format: r.data?.time_format,
      });
      invalidateMeCache();
      setProfileFlash({ ok: 'Profile saved. Dates and numbers across the app follow this company.' });
    } catch (err: any) {
      setProfileFlash({ err: err.message || 'Could not save the company profile' });
    } finally {
      setProfileBusy(false);
    }
  }

  async function saveTax() {
    setTaxFlash({});
    setTaxBusy(true);
    try {
      const r = await api('/tenants/me', {
        method: 'PATCH',
        body: JSON.stringify({
          tax_jurisdiction: tenant.tax_jurisdiction,
          tax_filing_period: tenant.tax_filing_period,
          // Omit blank TIN so Save does not 422 (TaxRegistrationNumberValue); leave prior.
          ...(String(tenant.tax_registration_number || '').trim()
            ? { tax_registration_number: String(tenant.tax_registration_number).trim() }
            : {}),
        }),
      });
      setTenant((current: any) =>
        mergeFields(current, r.data, [
          'tax_jurisdiction',
          'tax_registration_number',
          'tax_filing_period',
        ]),
      );
      setTaxFlash({ ok: 'Tax settings saved' });
    } catch (err: any) {
      setTaxFlash({ err: err.message || 'Could not save tax settings' });
    } finally {
      setTaxBusy(false);
    }
  }

  async function saveFiscal() {
    setFiscalFlash({});
    const problem = fiscalStartError(String(tenant.fiscal_year_start || ''));
    if (problem) {
      setFiscalFlash({ err: problem });
      return;
    }
    setFiscalBusy(true);
    try {
      const r = await api('/tenants/me', {
        method: 'PATCH',
        body: JSON.stringify({
          fiscal_year_start: String(tenant.fiscal_year_start || '').trim(),
        }),
      });
      setTenant((current: any) =>
        mergeFields(current, r.data, ['fiscal_year_start', 'fiscal_year_label']),
      );
      setFiscalFlash({ ok: 'Fiscal year saved' });
    } catch (err: any) {
      setFiscalFlash({ err: err.message || 'Could not save the fiscal year' });
    } finally {
      setFiscalBusy(false);
    }
  }

  async function saveTimeout() {
    setTimeoutFlash({});
    const raw = timeoutDraft.trim();
    if (!/^\d+$/.test(raw)) {
      setTimeoutFlash({ err: 'Inactivity timeout must be a whole number of minutes from 5 to 480.' });
      return;
    }
    const minutes = Number(raw);
    if (minutes < 5 || minutes > 480) {
      setTimeoutFlash({ err: 'Inactivity timeout must be a whole number of minutes from 5 to 480.' });
      return;
    }
    setTimeoutBusy(true);
    try {
      const r = await api('/tenants/me', {
        method: 'PATCH',
        body: JSON.stringify({ inactivity_timeout_minutes: minutes }),
      });
      setTenant((current: any) => mergeFields(current, r.data, ['inactivity_timeout_minutes']));
      setTimeoutDraft(String(r.data?.inactivity_timeout_minutes ?? minutes));
      setTimeoutFlash({ ok: 'Inactivity timeout saved' });
    } catch (err: any) {
      setTimeoutFlash({ err: err.message || 'Could not save the inactivity timeout' });
    } finally {
      setTimeoutBusy(false);
    }
  }

  async function saveEmail() {
    setEmailFlash({});
    const body: Record<string, unknown> = {
      use_tls: emailUseTls,
      use_ssl: emailUseSsl,
    };
    const portRaw = emailPort.trim();
    if (portRaw) {
      if (!/^\d+$/.test(portRaw) || Number(portRaw) < 1 || Number(portRaw) > 65535) {
        setEmailFlash({ err: 'SMTP port must be a whole number from 1 to 65535.' });
        return;
      }
      body.port = Number(portRaw);
    }
    // Omit blank host so Save does not 422 (SmtpHostValue); leave prior value.
    const trimmedHost = emailHost.trim();
    if (trimmedHost) body.host = trimmedHost;
    // Omit blank username so Save does not 422 (SmtpUsernameValue); leave prior.
    const trimmedUser = emailUser.trim();
    if (trimmedUser) body.username = trimmedUser;
    const trimmedFrom = emailFromEmail.trim();
    if (trimmedFrom) body.from_email = trimmedFrom;
    // Omit blank from_name so Save does not 422 (SmtpFromNameValue); leave prior.
    const trimmedFromName = emailFromName.trim();
    if (trimmedFromName) body.from_name = trimmedFromName;
    // Omit blank password so Save does not 422 (SmtpPasswordValue); leave prior.
    const trimmedPassword = emailPassword.trim();
    if (trimmedPassword) body.password = trimmedPassword;
    setEmailBusy(true);
    try {
      const r = await api('/settings/email', {
        method: 'PATCH',
        body: JSON.stringify(body),
      });
      setEmailStatus(r.data);
      if (r.data) {
        setEmailHost(r.data.host || '');
        setEmailPort(String(r.data.port ?? emailPort));
        setEmailUser(r.data.username || '');
        setEmailFromEmail(r.data.from_email || '');
        setEmailFromName(r.data.from_name || '');
        setEmailUseTls(r.data.use_tls !== false);
        setEmailUseSsl(!!r.data.use_ssl);
      }
      setEmailPassword('');
      setEmailFlash({ ok: 'Email settings saved' });
    } catch (err: any) {
      setEmailFlash({ err: err.message || 'Could not save email settings' });
    } finally {
      setEmailBusy(false);
    }
  }

  async function saveSms() {
    setSmsFlash({});
    const body: Record<string, unknown> = {};
    // Omit blank SID so Save does not 422 (TwilioAccountSidValue); leave prior.
    const trimmedSid = smsAccountSid.trim();
    if (trimmedSid) body.account_sid = trimmedSid;
    const trimmedFrom = smsFromNumber.trim();
    if (trimmedFrom) body.from_number = trimmedFrom;
    // Omit blank token so Save does not 422 (TwilioAuthTokenValue); leave prior.
    const trimmedToken = smsAuthToken.trim();
    if (trimmedToken) body.auth_token = trimmedToken;
    setSmsBusy(true);
    try {
      const r = await api('/settings/sms', {
        method: 'PATCH',
        body: JSON.stringify(body),
      });
      setSmsStatus(r.data);
      if (r.data) {
        setSmsAccountSid(r.data.account_sid || '');
        setSmsFromNumber(r.data.from_number || '');
      }
      setSmsAuthToken('');
      setSmsFlash({ ok: 'SMS settings saved' });
    } catch (err: any) {
      setSmsFlash({ err: err.message || 'Could not save SMS settings' });
    } finally {
      setSmsBusy(false);
    }
  }

  async function saveMyProfile() {
    setSmsFlash({});
    try {
      const body: Record<string, unknown> = {};
      // Omit blank name so Save does not 422 (UserFullNameValue); leave prior.
      const trimmedName = profileFullName.trim();
      if (trimmedName) body.full_name = trimmedName;
      // Omit blank phone so Save does not 422 (E164PhoneValue); leave prior.
      const trimmedPhone = profilePhone.trim();
      if (trimmedPhone) body.phone = trimmedPhone;
      setMyProfileBusy(true);
      await api('/me', {
        method: 'PATCH',
        body: JSON.stringify(body),
      });
      invalidateMeCache();
      setSmsFlash({ ok: 'Your profile was saved for the SMS test' });
    } catch (err: any) {
      setSmsFlash({ err: err.message || 'Could not save your profile' });
    } finally {
      setMyProfileBusy(false);
    }
  }

  async function savePrint() {
    setPrintFlash({});
    setPrintBusy(true);
    try {
      const r = await api('/settings/print', {
        method: 'PATCH',
        body: JSON.stringify({
          // null clears; blank would 422 (PrintHeader/FooterTextValue)
          header_text: printHeader.trim() || null,
          footer_text: printFooter.trim() || null,
          default_invoice_template: invTemplate,
          default_receipt_paper: receiptPaper,
        }),
      });
      setPrintHeader(r.data?.header_text || '');
      setPrintFooter(r.data?.footer_text || '');
      setInvTemplate(r.data?.default_invoice_template || 'a4');
      setReceiptPaper(r.data?.default_receipt_paper || '80mm');
      setPrintFlash({ ok: 'Print branding saved' });
    } catch (err: any) {
      setPrintFlash({ err: err.message || 'Could not save print branding' });
    } finally {
      setPrintBusy(false);
    }
  }

  function storeEntitlementCap(row: any): number | null {
    const raw =
      row?.store_usage?.subscription_store_entitlement ??
      row?.subscription?.subscription_store_entitlement ??
      row?.max_stores;
    if (raw == null || raw === '') return null;
    const cap = Number(raw);
    return Number.isFinite(cap) ? cap : null;
  }

  async function saveAdministration() {
    setMeFlash({});
    const hoursRaw = offlineHours.trim();
    if (!/^\d+$/.test(hoursRaw)) {
      setMeFlash({ err: 'Offline authorization hours must be a whole number from 1 to 168.' });
      return;
    }
    const hours = Number(hoursRaw);
    if (hours < 1 || hours > 168) {
      setMeFlash({ err: 'Offline authorization hours must be a whole number from 1 to 168.' });
      return;
    }
    setMeBusy(true);
    try {
      const profile = await api('/tenants/me', {
        method: 'PATCH',
        body: JSON.stringify({ offline_auth_hours: hours }),
      });
      setTenant((current: any) => mergeFields(current, profile.data, ['offline_auth_hours']));
      setOfflineHours(String(profile.data?.offline_auth_hours ?? hours));
      setMeFlash({ ok: 'Offline authorization hours saved' });
    } catch (err: any) {
      setMeFlash({ err: err.message || 'Could not save company administration' });
    } finally {
      setMeBusy(false);
    }
  }

  async function saveStoreAllocation() {
    setStoreFlash({});
    const limitRaw = storeLimitDraft.trim();
    let storeLimit: number | null = null;
    if (limitRaw) {
      if (!/^\d+$/.test(limitRaw)) {
        setStoreFlash({
          err: 'Store allocation must be a whole number, or blank to use the full entitlement.',
        });
        return;
      }
      storeLimit = Number(limitRaw);
    }
    const cap = storeEntitlementCap(tenant);
    if (storeLimit != null && cap != null && storeLimit > cap) {
      setStoreFlash({ err: `Store allocation cannot exceed the subscription entitlement (${cap}).` });
      return;
    }
    setStoreBusy(true);
    try {
      const allocation = await api('/tenants/me/store-limit', {
        method: 'PATCH',
        body: JSON.stringify({ store_limit: storeLimit }),
      });
      setTenant((current: any) => ({
        ...(current || {}),
        ...(allocation.data || {}),
        store_usage: allocation.data?.store_usage ?? current?.store_usage,
      }));
      const savedLimit = allocation.data?.store_limit;
      setStoreLimitDraft(savedLimit == null ? '' : String(savedLimit));
      setStoreFlash({
        ok: storeLimit == null
          ? 'Store allocation cleared. New stores can use the full subscription entitlement.'
          : 'Store allocation saved',
      });
    } catch (err: any) {
      setStoreFlash({ err: err.message || 'Could not save store allocation' });
    } finally {
      setStoreBusy(false);
    }
  }

  async function activate() {
    setError('');
    try {
      const r = await api('/tenants/me/activate', { method: 'POST', body: '{}' });
      setTenant(r.data);
      setMessage(r.message || 'Activated');
    } catch (err: any) {
      setError(err.message);
    }
  }

  if (!tenant) {
    return (
      <>
        <PageHeader title="Company" subtitle="Company profile could not be loaded." />
        {error && <p style={{ color: '#b91c1c' }}>{error}</p>}
        {loadBusy ? (
          <p className="muted">Loading…</p>
        ) : (
          <>
            <p className="muted">Company profile could not be loaded.</p>
            <p>
              <button
                type="button"
                className="primary"
                onClick={() => refresh().catch((err) => setError(err.message))}
                aria-label="Retry loading company profile"
              >
                Retry
              </button>
            </p>
          </>
        )}
      </>
    );
  }

  return (
    <div className="company-page">
      <PageHeader
        title="Company"
        subtitle="Your business details, branding, and settings for email, tax and printing."
      />
      {!industryValid && (
        <p className="login-error" role="alert">
          This company&apos;s business type is not recognized. A platform owner must set it to Retail, Hotel,
          or Restaurant. This page cannot change the business type.
        </p>
      )}
      <p className="muted">
        Status: {plainLabel(tenant.status)} · Company code for sign-in: {tenant.slug}
        {tenant.days_remaining != null && tenant.status === 'trial'
          ? ` · Trial days left: ${tenant.days_remaining}`
          : ''}
        {tenant.days_remaining != null && tenant.status === 'grace'
          ? ` · Grace days left: ${tenant.days_remaining}`
          : ''}
      </p>
      {tenant.status === 'trial' && (
        <div className="card" style={{ borderLeft: '4px solid #ca8a04' }}>
          <p>
            Trial ends {tenant.trial_ends_at ? formatDateTime(tenant.trial_ends_at, tenant) : 'soon'}
            {tenant.days_remaining != null ? ` (${tenant.days_remaining} day(s) left)` : ''}.
          </p>
          <button className="btn-ok" aria-label="Activate company" onClick={activate}>Activate now</button>
        </div>
      )}
      {tenant.read_only || tenant.status === 'grace' ? (
        <div className="card" style={{ borderLeft: '4px solid #b91c1c' }}>
          <p>
            <b>Read-only grace period.</b> Writes are blocked until you activate.
            {tenant.grace_ends_at
              ? ` Grace ends ${formatWhen(tenant.grace_ends_at, tenant)}.`
              : ''}
          </p>
          <button className="btn-ok" aria-label="Activate company" onClick={activate}>Activate to restore access</button>
        </div>
      ) : null}
      {error && <p style={{ color: '#b91c1c' }}>{error}</p>}
      {message && <p style={{ color: 'var(--brand, #4AB012)' }}>{message}</p>}

      <section className="card" aria-labelledby="company-profile-title">
        <h2 id="company-profile-title">Company profile</h2>
        <p className="muted">
          Your business name, contact details, currency, timezone, and how dates and numbers
          appear on invoices and receipts.
        </p>
        <div className="company-page-grid">
          <div className="company-page-field">
            <label htmlFor="company-trading-name">Company trading name</label>
            <input
              id="company-trading-name"
              value={tenant.company_name || ''}
              onChange={(e) => setTenant({ ...tenant, company_name: e.target.value })}
              placeholder="Company name (trading)"
              aria-label="Company trading name"
            />
          </div>
          <div className="company-page-field">
            <label htmlFor="company-legal-name">Company legal name</label>
            <input
              id="company-legal-name"
              value={tenant.legal_name || ''}
              onChange={(e) => setTenant({ ...tenant, legal_name: e.target.value })}
              placeholder="Legal name"
              aria-label="Company legal name"
            />
          </div>
          <div className="company-page-field">
            <label htmlFor="company-phone">Company phone</label>
            <input
              id="company-phone"
              value={tenant.phone || ''}
              onChange={(e) => setTenant({ ...tenant, phone: e.target.value })}
              placeholder="Phone, e.g. +233 24 123 4567"
              aria-label="Company phone"
            />
          </div>
          <div className="company-page-field">
            <label htmlFor="company-email">Company email</label>
            <input
              id="company-email"
              value={tenant.email || ''}
              onChange={(e) => setTenant({ ...tenant, email: e.target.value })}
              placeholder="Email"
              aria-label="Company email"
            />
          </div>
          <div className="company-page-field company-page-span">
            <label htmlFor="company-address">Company headquarters address</label>
            <textarea
              id="company-address"
              value={tenant.address || ''}
              onChange={(e) => setTenant({ ...tenant, address: e.target.value })}
              placeholder="Headquarters address"
              aria-label="Company headquarters address"
            />
          </div>
          <div className="company-page-field">
            <label htmlFor="company-currency">Company currency</label>
            <select
              id="company-currency"
              value={tenant.currency || 'GHS'}
              onChange={(e) => setTenant({ ...tenant, currency: e.target.value })}
              aria-label="Company currency"
            >
              {Array.from(
                new Set(
                  [tenant.currency || 'GHS', 'GHS', 'USD', 'EUR', 'GBP', 'NGN', 'XOF', 'CAD'].filter(Boolean),
                ),
              ).map((c) => (
                <option key={c} value={c}>
                  Currency: {c}
                </option>
              ))}
            </select>
          </div>
          <div className="company-page-field">
            <label htmlFor="company-timezone">Company timezone</label>
            <select
              id="company-timezone"
              value={tenant.timezone || 'Africa/Accra'}
              onChange={(e) => setTenant({ ...tenant, timezone: e.target.value })}
              aria-label="Company timezone"
            >
              {Array.from(
                new Set(
                  [
                    tenant.timezone || 'Africa/Accra',
                    'Africa/Accra',
                    'Africa/Lagos',
                    'Africa/Abidjan',
                    'Africa/Nairobi',
                    'Africa/Johannesburg',
                    'UTC',
                    'Europe/London',
                    'America/New_York',
                    'Asia/Dubai',
                  ].filter(Boolean),
                ),
              ).map((z) => (
                <option key={z} value={z}>
                  Timezone: {z}
                </option>
              ))}
            </select>
          </div>
          <h3 className="company-page-span">Date and number format</h3>
          <p className="muted company-page-span" style={{ margin: 0 }}>
            How dates, numbers and times appear.
          </p>
          <div className="company-page-field">
            <label htmlFor="company-date-format">Company date format</label>
            <select
              id="company-date-format"
              value={tenant.date_format || 'DD/MM/YYYY'}
              onChange={(e) => setTenant({ ...tenant, date_format: e.target.value })}
              aria-label="Company date format"
            >
              <option value="DD/MM/YYYY">DD/MM/YYYY</option>
              <option value="MM/DD/YYYY">MM/DD/YYYY</option>
              <option value="YYYY-MM-DD">YYYY-MM-DD</option>
            </select>
          </div>
          <div className="company-page-field">
            <label htmlFor="company-time-format">Company time format</label>
            <select
              id="company-time-format"
              value={tenant.time_format || '24h'}
              onChange={(e) => setTenant({ ...tenant, time_format: e.target.value })}
              aria-label="Company time format"
            >
              <option value="24h">24-hour</option>
              <option value="12h">12-hour</option>
            </select>
          </div>
          <div className="company-page-field">
            <label htmlFor="company-decimal-separator">Company decimal separator</label>
            <select
              id="company-decimal-separator"
              value={tenant.decimal_separator || '.'}
              onChange={(e) => setTenant({ ...tenant, decimal_separator: e.target.value })}
              aria-label="Company decimal separator"
            >
              <option value=".">Dot (1,234.56)</option>
              <option value=",">Comma (1.234,56)</option>
            </select>
          </div>
          <div className="company-page-field">
            <label htmlFor="company-thousand-separator">Company thousand separator</label>
            <select
              id="company-thousand-separator"
              value={
                tenant.thousand_separator === undefined || tenant.thousand_separator === null
                  ? ','
                  : tenant.thousand_separator === ''
                    ? 'none'
                    : tenant.thousand_separator
              }
              onChange={(e) =>
                setTenant({
                  ...tenant,
                  thousand_separator: e.target.value === 'none' ? '' : e.target.value,
                })
              }
              aria-label="Company thousand separator"
            >
              <option value=",">Comma</option>
              <option value=".">Dot</option>
              <option value=" ">Space</option>
              <option value="none">None</option>
            </select>
          </div>
          <p className="muted company-page-span" style={{ margin: 0 }}>
            Preview: {formatNumber(1234.56, tenant)} · {formatDateTime(new Date(), tenant)}
          </p>
          <div className="company-page-field">
            <label htmlFor="company-website">Company website</label>
            <input
              id="company-website"
              value={tenant.website || ''}
              onChange={(e) => setTenant({ ...tenant, website: e.target.value })}
              placeholder="Website (https://…)"
              aria-label="Company website"
            />
            <p className="muted" style={{ margin: '6px 0 0' }}>
              This is the public company URL. Link it for the built-in storefront on{' '}
              <a href="/ecommerce">Online store</a>.
            </p>
          </div>
          <div className="company-page-field">
            <label htmlFor="company-contact-person">Company contact person</label>
            <input
              id="company-contact-person"
              value={tenant.contact_person || ''}
              onChange={(e) => setTenant({ ...tenant, contact_person: e.target.value })}
              placeholder="Primary contact person"
              aria-label="Company contact person"
            />
          </div>
          <div className="company-page-field">
            <label htmlFor="company-registration-number">Company registration number</label>
            <input
              id="company-registration-number"
              value={tenant.registration_number || ''}
              onChange={(e) => setTenant({ ...tenant, registration_number: e.target.value })}
              placeholder="Company registration number"
              aria-label="Company registration number"
            />
          </div>
          <p aria-label="Company industry" className="muted company-page-field" style={{ margin: 0 }}>
            Business type: {industryLabel(tenant.industry)}
          </p>
          <div className="company-page-span company-page-actions">
            <button type="button" className="btn-ok" onClick={save} disabled={!!tenant.read_only || profileBusy} aria-label="Save company profile">
              {profileBusy ? 'Saving…' : 'Save profile'}
            </button>
            {(tenant.status === 'trial' || tenant.status === 'grace') && (
              <button type="button" className="btn-ok" aria-label="Activate company" onClick={activate}>Activate</button>
            )}
          </div>
          {profileFlash.ok ? (
            <p className="form-flash ok company-page-span" role="status">
              {profileFlash.ok}
            </p>
          ) : null}
          {profileFlash.err ? (
            <p className="form-flash err company-page-span" role="alert">
              {profileFlash.err}
            </p>
          ) : null}
        </div>
      </section>

      <div className="company-page-pair">
          <div className="card">
            <h2>Email</h2>
            {!emailStatus ? (
              <>
                <p className="muted">Email settings could not be loaded. Retry, then enter the SMTP host and from address.</p>
                <button type="button" onClick={() => reloadEmailSettings()}>Retry loading email settings</button>
                {emailFlash.err ? (
                  <p className="form-flash err" role="alert">{emailFlash.err}</p>
                ) : null}
              </>
            ) : (
            <>
              <p className="muted">
                Emails to customers and suppliers, such as invoices and purchase orders.{' '}
                {emailStatus.configured && emailStatus.enabled
                  ? emailStatus.tenant_override
                    ? 'Sending from your own mail server.'
                    : 'Sending through the Ribdigi mail service.'
                  : 'Email sending is not set up yet.'}
              </p>
              {!emailStatus.configured ? (
                <p className="muted">To send from your own mail server, enter its host and the address emails come from, then save. Leave the password blank to keep the saved one.</p>
              ) : null}
              <div className="company-page-grid">
                <div className="company-page-field">
                  <label htmlFor="company-smtp-host">Company SMTP host</label>
                  <input
                    id="company-smtp-host"
                    value={emailHost}
                    onChange={(e) => setEmailHost(e.target.value)}
                    placeholder="smtp.example.com"
                    aria-label="Company SMTP host"
                  />
                </div>
                <div className="company-page-field">
                  <label htmlFor="company-smtp-port">Company SMTP port</label>
                  <input
                    id="company-smtp-port"
                    value={emailPort}
                    onChange={(e) => setEmailPort(e.target.value)}
                    aria-label="Company SMTP port"
                  />
                </div>
                <div className="company-page-field">
                  <label htmlFor="company-smtp-username">Company SMTP username</label>
                  <input
                    id="company-smtp-username"
                    value={emailUser}
                    onChange={(e) => setEmailUser(e.target.value)}
                    aria-label="Company SMTP username"
                  />
                </div>
                <div className="company-page-field">
                  <label htmlFor="company-smtp-password">
                    Company SMTP password{emailStatus.has_password ? ' (saved — leave blank to keep)' : ''}
                  </label>
                  <input
                    id="company-smtp-password"
                    type="password"
                    value={emailPassword}
                    onChange={(e) => setEmailPassword(e.target.value)}
                    placeholder={emailStatus.has_password ? '••••••••' : ''}
                    autoComplete="new-password"
                    aria-label="Company SMTP password"
                    title="SMTP password"
                  />
                </div>
                <div className="company-page-field">
                  <label htmlFor="company-from-email">Company from email</label>
                  <input
                    id="company-from-email"
                    type="email"
                    value={emailFromEmail}
                    onChange={(e) => setEmailFromEmail(e.target.value)}
                    placeholder="noreply@example.com"
                    aria-label="Company from email"
                  />
                </div>
                <div className="company-page-field">
                  <label htmlFor="company-from-name">Company from name</label>
                  <input
                    id="company-from-name"
                    value={emailFromName}
                    onChange={(e) => setEmailFromName(e.target.value)}
                    aria-label="Company from name"
                  />
                </div>
                <div className="company-page-checks company-page-span">
                  <label className="company-page-check">
                    <input
                      type="checkbox"
                      aria-label="Company SMTP use TLS"
                      checked={emailUseTls}
                      onChange={(e) => {
                        setEmailUseTls(e.target.checked);
                        if (e.target.checked) setEmailUseSsl(false);
                      }}
                    />
                    Use STARTTLS
                  </label>
                  <label className="company-page-check">
                    <input
                      type="checkbox"
                      checked={emailUseSsl}
                      onChange={(e) => {
                        setEmailUseSsl(e.target.checked);
                        if (e.target.checked) setEmailUseTls(false);
                      }}
                      aria-label="Company SMTP use SSL"
                    />
                    Use SSL
                  </label>
                </div>
                <div className="company-page-actions company-page-span">
                  <button
                    type="button"
                    className="btn-ok"
                    onClick={saveEmail}
                    disabled={emailBusy || !!tenant.read_only}
                    aria-label="Save email settings"
                  >
                    {emailBusy ? 'Saving…' : 'Save email settings'}
                  </button>
                  <button
                    type="button"
                    onClick={async () => {
                      setEmailFlash({});
                      try {
                        const r = await api('/settings/email/test', { method: 'POST', body: '{}' });
                        setEmailFlash({ ok: r.message || `Test email via ${r.data?.mode}` });
                      } catch (err: any) {
                        setEmailFlash({ err: err.message || 'Could not send the test email' });
                      }
                    }}
                    aria-label="Send test email to me"
                  >
                    Send test email to me
                  </button>
                </div>
                {emailFlash.ok ? (
                  <p className="form-flash ok company-page-span" role="status">{emailFlash.ok}</p>
                ) : null}
                {emailFlash.err ? (
                  <p className="form-flash err company-page-span" role="alert">{emailFlash.err}</p>
                ) : null}
              </div>
            </>
            )}
            </div>

          <div className="card">
            <h2>SMS</h2>
            {!smsStatus ? (
              <>
                <p className="muted">SMS settings could not be loaded. Retry, then enter the account SID and from number.</p>
                <button type="button" onClick={() => reloadSmsSettings()}>Retry loading SMS settings</button>
                {smsFlash.err ? (
                  <p className="form-flash err" role="alert">{smsFlash.err}</p>
                ) : null}
              </>
            ) : (
            <>
              <p className="muted">
                Text messages to customers, such as receipts and payment reminders.{' '}
                {smsStatus.configured && smsStatus.enabled
                  ? smsStatus.tenant_override
                    ? 'Sending from your own SMS account.'
                    : 'Sending through the Ribdigi SMS service.'
                  : 'SMS sending is not set up yet.'}
              </p>
              {!smsStatus.configured ? (
                <p className="muted">To send from your own Twilio account, enter its account SID and sending number, then save. Leave the token blank to keep the saved one.</p>
              ) : null}
              <div className="company-page-grid">
                <div className="company-page-field">
                  <label htmlFor="company-sms-sid">Company SMS account SID</label>
                  <input
                    id="company-sms-sid"
                    value={smsAccountSid}
                    onChange={(e) => setSmsAccountSid(e.target.value)}
                    placeholder="ACxxxxxxxx"
                    aria-label="Company SMS account SID"
                  />
                </div>
                <div className="company-page-field">
                  <label htmlFor="company-sms-from">Company SMS from number</label>
                  <input
                    id="company-sms-from"
                    value={smsFromNumber}
                    onChange={(e) => setSmsFromNumber(e.target.value)}
                    placeholder="e.g. +233 24 123 4567"
                    aria-label="Company SMS from number"
                  />
                </div>
                <div className="company-page-field company-page-span">
                  <label htmlFor="company-sms-token">
                    Company SMS auth token{smsStatus.has_auth_token ? ' (saved — leave blank to keep)' : ''}
                  </label>
                  <input
                    id="company-sms-token"
                    type="password"
                    value={smsAuthToken}
                    onChange={(e) => setSmsAuthToken(e.target.value)}
                    placeholder={smsStatus.has_auth_token ? '••••••••' : ''}
                    autoComplete="new-password"
                    aria-label="Company SMS auth token"
                    title="Twilio auth token"
                  />
                </div>
                <div className="company-page-field">
                  <label htmlFor="company-profile-name">Profile full name</label>
                  <input
                    id="company-profile-name"
                    value={profileFullName}
                    onChange={(e) => setProfileFullName(e.target.value)}
                    placeholder="Full name"
                    aria-label="Profile full name"
                    title="Profile full name"
                  />
                </div>
                <div className="company-page-field">
                  <label htmlFor="company-profile-phone">Profile phone for SMS test</label>
                  <input
                    id="company-profile-phone"
                    value={profilePhone}
                    onChange={(e) => setProfilePhone(e.target.value)}
                    placeholder="Your mobile, e.g. +233 24 123 4567"
                    aria-label="Profile phone for SMS test"
                  />
                </div>
                <div className="company-page-actions company-page-span">
                  <button
                    type="button"
                    className="btn-ok"
                    onClick={saveSms}
                    disabled={smsBusy || !!tenant.read_only}
                    aria-label="Save SMS settings"
                  >
                    {smsBusy ? 'Saving…' : 'Save SMS settings'}
                  </button>
                  <button
                    type="button"
                    className="btn-ok"
                    onClick={saveMyProfile}
                    disabled={myProfileBusy}
                    aria-label="Save my profile"
                  >
                    {myProfileBusy ? 'Saving…' : 'Save my profile'}
                  </button>
                  <button
                    type="button"
                    onClick={async () => {
                      setSmsFlash({});
                      try {
                        const r = await api('/settings/sms/test', { method: 'POST', body: '{}' });
                        setSmsFlash({ ok: r.message || `Test SMS via ${r.data?.mode}` });
                      } catch (err: any) {
                        setSmsFlash({ err: err.message || 'Could not send the test SMS' });
                      }
                    }}
                    aria-label="Send test SMS to me"
                  >
                    Send test SMS to me
                  </button>
                </div>
                {smsFlash.ok ? (
                  <p className="form-flash ok company-page-span" role="status">{smsFlash.ok}</p>
                ) : null}
                {smsFlash.err ? (
                  <p className="form-flash err company-page-span" role="alert">{smsFlash.err}</p>
                ) : null}
              </div>
            </>
            )}
            </div>
        </div>

      <div className="company-page-pair">
        <section className="card" aria-labelledby="company-logo-title">
          <h2 id="company-logo-title">Logo</h2>
          <p className="muted">Shown in the sidebar and on printed documents when a logo is saved. PNG, JPEG, WebP, or GIF, up to 2 MB.</p>
          {!tenant.has_logo ? (
            <p className="muted">No logo is saved yet. Choose a PNG, JPEG, WebP, or GIF up to 2 MB.</p>
          ) : null}
          <div className="company-page-field">
            <label htmlFor="company-logo-file">Company logo</label>
            {tenant.has_logo && logoPreview && (
              <div className="company-logo-preview">
                <img src={logoPreview} alt="Company logo" />
              </div>
            )}
            <input
              id="company-logo-file"
              type="file"
              accept="image/png,image/jpeg,image/webp,image/gif"
              disabled={!!tenant.read_only || logoBusy}
              aria-label="Company logo file"
              onChange={async (e) => {
                const file = e.target.files?.[0];
                if (!file) return;
                setLogoFlash({});
                if (!LOGO_TYPES.has(file.type)) {
                  setLogoFlash({ err: 'That file type is not allowed. Use PNG, JPEG, WebP, or GIF.' });
                  e.target.value = '';
                  return;
                }
                if (file.size <= 0) {
                  setLogoFlash({ err: 'The file is empty. Choose another image.' });
                  e.target.value = '';
                  return;
                }
                if (file.size > LOGO_MAX_BYTES) {
                  setLogoFlash({ err: 'That file is too large. Maximum size is 2 MB.' });
                  e.target.value = '';
                  return;
                }
                setLogoBusy(true);
                try {
                  const form = new FormData();
                  form.append('file', file);
                  const r = await api('/tenants/me/logo', { method: 'POST', body: form });
                  setTenant((current: any) => mergeFields(current, r.data, ['has_logo']));
                  setLogoFlash({ ok: r.message || 'Logo uploaded' });
                  invalidateMeCache();
                  window.dispatchEvent(new Event('ribdigi-tenant-logo'));
                  await loadLogoPreview(true);
                } catch (err: any) {
                  setLogoFlash({ err: typeof err.message === 'string' ? err.message : 'Could not upload the logo.' });
                } finally {
                  setLogoBusy(false);
                  e.target.value = '';
                }
              }}
            />
          </div>
          {tenant.has_logo && (
            <div className="company-page-actions" style={{ marginTop: 12 }}>
              <button
                type="button"
                className="btn-danger"
                disabled={!!tenant.read_only}
                aria-label="Remove company logo"
                onClick={async () => {
                  setLogoFlash({});
                  try {
                    const r = await api('/tenants/me/logo', { method: 'DELETE' });
                    setTenant((current: any) => mergeFields(current, r.data, ['has_logo']));
                    setLogoPreview(null);
                    setLogoFlash({ ok: 'Logo removed' });
                    invalidateMeCache();
                    window.dispatchEvent(new Event('ribdigi-tenant-logo'));
                  } catch (err: any) {
                    setLogoFlash({ err: err.message || 'Could not remove the logo' });
                  }
                }}
              >
                Remove logo
              </button>
            </div>
          )}
          {logoFlash.ok ? (
            <p className="form-flash ok" role="status">{logoFlash.ok}</p>
          ) : null}
          {logoFlash.err ? (
            <p className="form-flash err" role="alert">{logoFlash.err}</p>
          ) : null}
        </section>

        <section className="card" aria-labelledby="company-print-title">
          <h2 id="company-print-title">Print branding</h2>
          <p className="muted">
            Header and footer on invoices, receipts, and outbound emails. The company logo is embedded on PDFs
            and branded HTML emails.
          </p>
          <div className="company-page-grid">
            <div className="company-page-field company-page-span">
              <label htmlFor="company-print-header">Print branding header text</label>
              <input
                id="company-print-header"
                value={printHeader}
                onChange={(e) => setPrintHeader(e.target.value)}
                placeholder="Tagline under company name"
                title="Optional header; blank clears"
                aria-label="Print branding header text"
              />
            </div>
            <div className="company-page-field company-page-span">
              <label htmlFor="company-print-footer">Print branding footer text</label>
              <input
                id="company-print-footer"
                value={printFooter}
                onChange={(e) => setPrintFooter(e.target.value)}
                placeholder="Thank you line"
                title="Optional footer; blank clears"
                aria-label="Print branding footer text"
              />
            </div>
            <div className="company-page-field">
              <label htmlFor="company-invoice-template">Default invoice template</label>
              <select
                id="company-invoice-template"
                value={invTemplate}
                onChange={(e) => setInvTemplate(e.target.value)}
                aria-label="Default invoice template"
              >
                <option value="a4">A4</option>
                <option value="thermal">Thermal</option>
              </select>
            </div>
            <div className="company-page-field">
              <label htmlFor="company-receipt-paper">Default receipt paper</label>
              <select
                id="company-receipt-paper"
                value={receiptPaper}
                onChange={(e) => setReceiptPaper(e.target.value)}
                aria-label="Default receipt paper"
              >
                <option value="80mm">80mm</option>
                <option value="58mm">58mm</option>
              </select>
            </div>
            <div className="company-page-actions company-page-span">
              <button
                type="button"
                className="btn-ok"
                aria-label="Save print branding"
                onClick={savePrint}
                disabled={printBusy || !!tenant.read_only}
              >
                {printBusy ? 'Saving…' : 'Save print branding'}
              </button>
            </div>
            {printFlash.ok ? (
              <p className="form-flash ok company-page-span" role="status">{printFlash.ok}</p>
            ) : null}
            {printFlash.err ? (
              <p className="form-flash err company-page-span" role="alert">{printFlash.err}</p>
            ) : null}
          </div>
        </section>
      </div>

      <div className="company-page-pair">
        <section className="card" aria-labelledby="company-tax-title">
          <h2 id="company-tax-title">Tax</h2>
          <p className="muted">Choose the country for this company&apos;s tax records, then save. The government filing template is still Ghana only.</p>
          <div className="company-page-grid">
            <div className="company-page-field company-page-span">
              <label htmlFor="company-tax-jurisdiction">Tax jurisdiction</label>
              <select
                id="company-tax-jurisdiction"
                value={tenant.tax_jurisdiction || 'GH'}
                onChange={(e) => setTenant({ ...tenant, tax_jurisdiction: e.target.value })}
                aria-label="Tax jurisdiction"
              >
                {(TAX_COUNTRIES.some((c) => c.code === (tenant.tax_jurisdiction || 'GH'))
                  ? TAX_COUNTRIES
                  : [
                      {
                        code: tenant.tax_jurisdiction || 'GH',
                        name: tenant.tax_jurisdiction || 'Ghana',
                      },
                      ...TAX_COUNTRIES,
                    ]
                ).map((c) => (
                  <option key={c.code} value={c.code}>
                    Tax jurisdiction: {c.code} — {c.name}
                  </option>
                ))}
              </select>
            </div>
            <div className="company-page-field">
              <label htmlFor="company-tin">TIN / VAT registration number</label>
              <input
                id="company-tin"
                value={tenant.tax_registration_number || ''}
                onChange={(e) => setTenant({ ...tenant, tax_registration_number: e.target.value })}
                placeholder="TIN / VAT registration number (tax ID)"
                aria-label="TIN / VAT registration number"
              />
            </div>
            <div className="company-page-field">
              <label htmlFor="company-filing-period">Tax filing period</label>
              <select
                id="company-filing-period"
                value={tenant.tax_filing_period || 'monthly'}
                onChange={(e) => setTenant({ ...tenant, tax_filing_period: e.target.value })}
                aria-label="Tax filing period"
              >
                <option value="monthly">Filing period: monthly</option>
                <option value="quarterly">Filing period: quarterly</option>
              </select>
            </div>
            <div className="company-page-actions company-page-span">
              <button type="button" className="btn-ok" onClick={saveTax} disabled={!!tenant.read_only || taxBusy}>
                {taxBusy ? 'Saving…' : 'Save tax settings'}
              </button>
            </div>
            {taxFlash.ok ? (
              <p className="form-flash ok company-page-span" role="status">{taxFlash.ok}</p>
            ) : null}
            {taxFlash.err ? (
              <p className="form-flash err company-page-span" role="alert">{taxFlash.err}</p>
            ) : null}
          </div>
        </section>

        <section className="card" aria-labelledby="company-fiscal-title">
          <h2 id="company-fiscal-title">Fiscal year</h2>
          <p className="muted">Enter the financial year start as MM-DD, for example 01-01, then save.</p>
          <div className="company-page-grid">
            <div className="company-page-field">
              <label className="muted" htmlFor="company-fiscal-year-start">
                Fiscal year starts (MM-DD)
              </label>
              <input
                id="company-fiscal-year-start"
                value={tenant.fiscal_year_start ?? ''}
                onChange={(e) => setTenant({ ...tenant, fiscal_year_start: e.target.value })}
                placeholder="Fiscal year start MM-DD"
                pattern="(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])"
                maxLength={5}
                aria-label="Fiscal year start"
                title="MM-DD (e.g. 01-01)"
              />
            </div>
            <p className="muted company-page-field" style={{ margin: 0 }} aria-label="Fiscal year label">
              Current period: {tenant.fiscal_year_label || 'FY'}
            </p>
            <div className="company-page-actions company-page-span">
              <button type="button" className="btn-ok" onClick={saveFiscal} disabled={!!tenant.read_only || fiscalBusy}>
                {fiscalBusy ? 'Saving…' : 'Save fiscal year'}
              </button>
            </div>
            {fiscalFlash.ok ? (
              <p className="form-flash ok company-page-span" role="status">{fiscalFlash.ok}</p>
            ) : null}
            {fiscalFlash.err ? (
              <p className="form-flash err company-page-span" role="alert">{fiscalFlash.err}</p>
            ) : null}
          </div>
        </section>
      </div>

      <div className="company-page-pair">
          <div className="card">
            <h2>Staff user guide</h2>
            {canGuide ? (
              <>
                <p className="muted" style={{ margin: 0 }}>
                  Download the authorized PDF for this company. Requires staff_guide:download.
                </p>
                <button
                  type="button"
                  className="btn-ok"
                  onClick={downloadStaffGuide}
                  disabled={guideBusy}
                  aria-label="Download staff user guide PDF"
                >
                  {guideBusy ? 'Preparing staff guide…' : 'Download staff user guide (PDF)'}
                </button>
                {guideError ? (
                  <p className="form-flash err" role="alert">
                    {guideError}
                  </p>
                ) : null}
              </>
            ) : (
              <p className="muted" style={{ margin: 0 }}>
                Ask a company administrator for staff guide download permission.
              </p>
            )}
          </div>
        <div className="card">
          <h2>Users</h2>
          <p className="muted" style={{ margin: 0 }}>
            Add and manage staff in Settings → Users.
          </p>
          <a href="/users#create-user" aria-label="Add User">
            Add User
          </a>
        </div>
      </div>

      {(meRole === 'company_admin' || meRole === 'super_admin') && tenant && (
        <>
        <section className="card" aria-labelledby="company-store-title">
          <h2 id="company-store-title">Store allocation</h2>
          <p className="muted">
            Enter how many active stores this company may use, or leave it blank to use the full subscription entitlement, then save.
          </p>
          <div className="company-page-grid">
            <div className="company-page-field">
              <label htmlFor="company-store-allocation">Store allocation</label>
              <input
                id="company-store-allocation"
                type="number"
                min={0}
                value={storeLimitDraft}
                onChange={(e) => setStoreLimitDraft(e.target.value)}
                placeholder="Full entitlement"
                aria-label="Company store allocation"
                title="Active-store cap within the subscription. Blank uses the full entitlement."
              />
              <p className="muted" style={{ margin: 0 }}>
                {(() => {
                  const usage = tenant.store_usage || {};
                  const active = usage.stores_active;
                  const effective = usage.effective_store_limit ?? tenant.subscription?.effective_store_limit;
                  const unlimited =
                    usage.unlimited ?? tenant.subscription?.unlimited_stores ?? storeEntitlementCap(tenant) == null;
                  if (active == null && effective == null && !unlimited) {
                    return 'Store usage loads with the company profile.';
                  }
                  if (unlimited && active != null) return `${active} active stores (unlimited entitlement)`;
                  if (active != null && effective != null) return `${active} of ${effective} stores used`;
                  return unlimited ? 'Store entitlement is unlimited' : 'Store usage loads with the company profile.';
                })()}
              </p>
              <p className="muted" style={{ margin: 0 }}>
                Blank store allocation uses the full subscription entitlement
                {storeEntitlementCap(tenant) != null ? ` (${storeEntitlementCap(tenant)})` : ' (unlimited)'}.
              </p>
            </div>
            <div className="company-page-actions company-page-span">
              <button
                type="button"
                className="btn-ok"
                onClick={saveStoreAllocation}
                disabled={!!tenant.read_only || storeBusy}
              >
                {storeBusy ? 'Saving…' : 'Save store allocation'}
              </button>
            </div>
            {storeFlash.ok ? (
              <p className="form-flash ok company-page-span" role="status">{storeFlash.ok}</p>
            ) : null}
            {storeFlash.err ? (
              <p className="form-flash err company-page-span" role="alert">{storeFlash.err}</p>
            ) : null}
          </div>
        </section>
        <section className="card" aria-labelledby="company-admin-title">
          <h2 id="company-admin-title">Company administration</h2>
          <p className="muted">
            These tools stay inside this company. The sidebar is built from the saved industry,
            enabled modules, and your permissions. A hidden menu item is not permission to open the page.
          </p>
          <p className="muted" style={{ marginTop: 0 }}>
            Business type: {industryLabel(tenant.industry)}
            {tenant.package_code ? ` · Package: ${plainLabel(tenant.package_code)}` : ''}
          </p>
          <p className="muted" style={{ marginTop: 0 }}>
            Enabled modules:{' '}
            {Array.isArray(tenant.enabled_modules) && tenant.enabled_modules.length
              ? tenant.enabled_modules.map((code: string) => plainLabel(code)).join(', ')
              : 'None'}
          </p>
          <div className="company-page-scroll">
            <nav aria-label="Company administration links" className="company-page-links">
              <a href="/users">Users and roles</a>
              <a href="/stores">Stores and locations</a>
              <a href="/notifications">Notifications</a>
              <a href="/audit">Activity log</a>
              <a href="/company/billing">Subscription billing</a>
              <a href="/printers">Printers</a>
              <a href="/backup">Download a backup</a>
            </nav>
          </div>
          <p className="muted">
            Printers covers receipts and barcode output for this company&apos;s saved industry.
            Barcode labels are also printed from Inventory. The cash drawer is on Multi-Store when
            that module is enabled.
          </p>
          <div className="company-page-grid">
            <div className="company-page-field">
              <label htmlFor="company-offline-hours">Company offline authorization hours</label>
              <input
                id="company-offline-hours"
                type="number"
                min={1}
                max={168}
                value={offlineHours}
                onChange={(e) => setOfflineHours(e.target.value)}
                aria-label="Company offline authorization hours"
                title="Hours a signed-in device may sell offline (1–168)"
              />
              <p className="muted" style={{ margin: 0 }}>
                How long a signed-in till may keep selling without internet. Offline sales upload when the till is back online with the Point of Sale page open.
              </p>
            </div>
            <div className="company-page-actions company-page-span">
              <button
                type="button"
                className="btn-ok"
                onClick={saveAdministration}
                disabled={!!tenant.read_only || meBusy}
                aria-label="Save company administration"
              >
                {meBusy ? 'Saving…' : 'Save company administration'}
              </button>
            </div>
          </div>
          {meFlash.ok ? (
            <p className="form-flash ok" role="status">
              {meFlash.ok}
            </p>
          ) : null}
          {meFlash.err ? (
            <p className="form-flash err" role="alert">
              {meFlash.err}
            </p>
          ) : null}
        </section>
        </>
      )}

      <section className="card" aria-labelledby="company-timeout-title">
        <h2 id="company-timeout-title">Inactivity timeout</h2>
        <p className="muted">
          Enter a whole number of minutes from 5 to 480, then save. The default is 30. This signs people out after they stop using the app.
        </p>
        <div className="company-page-grid">
          <div className="company-page-field">
            <label htmlFor="company-inactivity-timeout">Company inactivity timeout minutes</label>
            <input
              id="company-inactivity-timeout"
              type="number"
              min={5}
              max={480}
              value={timeoutDraft}
              onChange={(e) => setTimeoutDraft(e.target.value)}
              aria-label="Company inactivity timeout minutes"
            />
          </div>
          <div className="company-page-actions company-page-span">
            <button type="button" className="btn-ok" onClick={saveTimeout} disabled={!!tenant.read_only || timeoutBusy}>
              {timeoutBusy ? 'Saving…' : 'Save inactivity timeout'}
            </button>
          </div>
          {timeoutFlash.ok ? (
            <p className="form-flash ok company-page-span" role="status">{timeoutFlash.ok}</p>
          ) : null}
          {timeoutFlash.err ? (
            <p className="form-flash err company-page-span" role="alert">{timeoutFlash.err}</p>
          ) : null}
        </div>
      </section>

      <section className="card company-page-danger" aria-labelledby="company-suspension-title">
        <h2 id="company-suspension-title">Suspension</h2>
        <p className="muted" style={{ marginBottom: 0 }}>
          Current status: {plainLabel(tenant.status)}.
        </p>
      </section>
    </div>
  );
}
