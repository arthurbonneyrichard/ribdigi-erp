'use client';

import { useEffect, useMemo, useState } from 'react';
import { authHeaders } from '../lib/api';
import {
  getCompanyId,
  getWorkspaceKind,
  subscribeWorkspace,
  type WorkspaceKind,
} from '../lib/workspaceContext';
import { getSelectedStoreId, subscribeStoreContext } from '../lib/storeContext';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

export type BrandCompany = {
  id: string;
  name: string;
  has_logo?: boolean;
  business_type_label?: string | null;
  industry?: string | null;
};

export type StoreOption = { id: string; name: string; code?: string };

function initialsFor(name: string): string {
  const parts = (name || '')
    .trim()
    .split(/\s+/)
    .filter(Boolean);
  if (!parts.length) return 'CO';
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[1][0]).toUpperCase();
}

type Props = {
  principal: string;
  tenantName: string;
  tenantHasLogo?: boolean;
  companies: BrandCompany[];
  stores?: StoreOption[];
  collapsed?: boolean;
};

export default function WorkspaceBrand({
  principal,
  tenantName,
  tenantHasLogo = false,
  companies,
  stores = [],
  collapsed = false,
}: Props) {
  const [workspaceKind, setWorkspaceKind] = useState<WorkspaceKind>('company');
  const [companyId, setCompanyId] = useState('');
  const [storeId, setStoreId] = useState('');
  const [logoUrl, setLogoUrl] = useState<string | null>(null);
  const [logoFailed, setLogoFailed] = useState(false);
  const [brandTick, setBrandTick] = useState(0);

  useEffect(() => {
    setWorkspaceKind(getWorkspaceKind());
    setCompanyId(getCompanyId() || '');
    setStoreId(getSelectedStoreId() || '');
    const unsubWs = subscribeWorkspace(() => {
      setWorkspaceKind(getWorkspaceKind());
      setCompanyId(getCompanyId() || '');
    });
    const onBrand = () => {
      setWorkspaceKind(getWorkspaceKind());
      setCompanyId(getCompanyId() || '');
      setBrandTick((n) => n + 1);
    };
    window.addEventListener('ribdigi-branding-changed', onBrand);
    return () => {
      unsubWs();
      window.removeEventListener('ribdigi-branding-changed', onBrand);
    };
  }, []);

  useEffect(() => {
    return subscribeStoreContext(() => setStoreId(getSelectedStoreId() || ''));
  }, []);

  const activeCompany = useMemo(() => {
    if (!companyId) return null;
    return companies.find((c) => c.id === companyId) || null;
  }, [companies, companyId]);

  const storeLabel = useMemo(() => {
    if (!storeId) return '';
    const s = stores.find((x) => x.id === storeId);
    if (!s) return '';
    return s.name || s.code || '';
  }, [stores, storeId]);

  const brand = useMemo(() => {
    if (principal === 'platform') {
      return {
        title: 'Ribdigi ERP',
        subtitle: 'Platform Administration',
        initials: 'RE',
        hasLogo: false,
        logoPath: null as string | null,
        alt: 'Ribdigi ERP logo',
      };
    }
    if (workspaceKind === 'tenant') {
      const name = tenantName || 'Tenant Workspace';
      return {
        title: name,
        subtitle: 'Tenant Workspace',
        initials: initialsFor(name),
        hasLogo: Boolean(tenantHasLogo),
        logoPath: tenantHasLogo ? '/tenants/me/logo' : null,
        alt: `${name} logo`,
      };
    }
    const name = activeCompany?.name || 'Company';
    const typeLabel =
      activeCompany?.business_type_label ||
      (activeCompany?.industry
        ? activeCompany.industry.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
        : '');
    return {
      title: name,
      subtitle: typeLabel || '',
      tertiary: storeLabel || '',
      initials: initialsFor(name),
      hasLogo: Boolean(activeCompany?.has_logo),
      logoPath:
        activeCompany?.id && activeCompany?.has_logo
          ? `/companies/${activeCompany.id}/logo`
          : null,
      alt: `${name} logo`,
    };
  }, [
    principal,
    workspaceKind,
    tenantName,
    tenantHasLogo,
    activeCompany,
    storeLabel,
  ]);

  useEffect(() => {
    let active = true;
    let objectUrl: string | null = null;
    setLogoFailed(false);
    setLogoUrl(null);
    if (!brand.logoPath) {
      return () => undefined;
    }
    (async () => {
      try {
        const res = await fetch(`${API_BASE}${brand.logoPath}`, {
          headers: authHeaders(),
          cache: 'no-store',
        });
        if (!res.ok) throw new Error('logo missing');
        const blob = await res.blob();
        objectUrl = URL.createObjectURL(blob);
        if (active) setLogoUrl(objectUrl);
      } catch {
        if (active) {
          setLogoUrl(null);
          setLogoFailed(true);
        }
      }
    })();
    return () => {
      active = false;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [brand.logoPath, workspaceKind, companyId, principal, brandTick, tenantHasLogo]);

  const showImage = Boolean(logoUrl) && !logoFailed;
  const titleAttr = [brand.title, brand.subtitle, brand.tertiary].filter(Boolean).join(' — ');

  return (
    <div
      className={`workspace-brand${collapsed ? ' is-collapsed' : ''}`}
      title={titleAttr}
      aria-label={titleAttr}
    >
      <div className="workspace-brand-mark" aria-hidden={showImage ? undefined : true}>
        {showImage ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={logoUrl!}
            alt={brand.alt}
            className="workspace-brand-logo"
            onError={() => {
              setLogoFailed(true);
              setLogoUrl(null);
            }}
          />
        ) : (
          <span className="workspace-brand-initials" aria-hidden="true">
            {brand.initials}
          </span>
        )}
      </div>
      {!collapsed && (
        <div className="workspace-brand-text">
          <div className="workspace-brand-title">{brand.title}</div>
          {brand.subtitle ? (
            <div className="workspace-brand-sub">{brand.subtitle}</div>
          ) : null}
          {brand.tertiary ? (
            <div className="workspace-brand-tertiary">{brand.tertiary}</div>
          ) : null}
        </div>
      )}
      {/* Screen-reader name when collapsed / initials-only */}
      <span className="sr-only">{brand.title}</span>
    </div>
  );
}
