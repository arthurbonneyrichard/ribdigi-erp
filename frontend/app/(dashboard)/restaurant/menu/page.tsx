'use client';

/**
 * Digital menu: what guests see on the TV board and through the QR code.
 * Prices and names here are the same ones the till uses.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { api, apiFetch } from '../../../../lib/api';
import { getMe } from '../../../../lib/meCache';
import { problem, type Row } from '../../../../lib/restaurantDesk';
import { GuestMenuView, menuPrice, type GuestItem, type GuestMenu } from '../../../../components/digital-menu/DigitalMenu';
import OnlineAlertsPanel from '../../../../components/OnlineAlertsPanel';
import '../restaurant-desk.css';
import './menu-admin.css';

function canEditMenu(me: Row | null): boolean {
  const perms = me?.permissions;
  if (!perms) return false;
  if (Array.isArray(perms['*'])) return true;
  return (perms.inventory || []).some((a: string) => a === 'write' || a === '*');
}

/** Staff can see photos before the menu is public, so these load with the staff session. */
function useStaffImage(path: string | null, version?: string | null): string {
  const [url, setUrl] = useState('');
  useEffect(() => {
    if (!path) {
      setUrl('');
      return;
    }
    let live = true;
    let made = '';
    apiFetch(path)
      .then(async (res) => {
        if (!res.ok) return;
        made = URL.createObjectURL(await res.blob());
        if (live) setUrl(made);
      })
      .catch(() => undefined);
    return () => {
      live = false;
      if (made) URL.revokeObjectURL(made);
    };
  }, [path, version]);
  return url;
}

function StaffPhoto({ itemId, version }: { itemId: string; version?: string | null }) {
  const url = useStaffImage(`/restaurant/menu/items/${itemId}/photo`, version);
  return url ? <img src={url} alt="" loading="lazy" decoding="async" /> : null;
}

function Choice({
  label,
  value,
  options,
  onPick,
  disabled,
}: {
  label: string;
  value: string;
  options: [string, string][];
  onPick: (value: string) => void;
  disabled?: boolean;
}) {
  return (
    <div className="dmenu-choice" role="group" aria-label={label || 'Choose'}>
      {label ? <span className="l">{label}</span> : null}
      <div className="opts">
        {options.map(([key, text]) => (
          <button key={key} type="button" className={value === key ? 'on' : ''} aria-pressed={value === key} disabled={disabled} onClick={() => onPick(key)}>
            {text}
          </button>
        ))}
      </div>
    </div>
  );
}

const DESIGN_PRESETS: { name: string; design: Record<string, string> }[] = [
  { name: 'Fresh green', design: { primary: '#0B6B3A', accent: '#4AB012', background: '#FFFFFF', font: 'sans', corners: 'round' } },
  { name: 'Midnight gold', design: { primary: '#111827', accent: '#F59E0B', background: '#0F172A', font: 'sans', corners: 'soft' } },
  { name: 'Sunset', design: { primary: '#9A3412', accent: '#F97316', background: '#FFF7ED', font: 'serif', corners: 'soft' } },
  { name: 'Ocean', design: { primary: '#0C4A6E', accent: '#0EA5E9', background: '#F0F9FF', font: 'sans', corners: 'round' } },
  { name: 'Berry', design: { primary: '#831843', accent: '#EC4899', background: '#FDF2F8', font: 'rounded', corners: 'soft' } },
  { name: 'Black and gold', design: { primary: '#1C1917', accent: '#CA8A04', background: '#FAFAF9', font: 'serif', corners: 'sharp' } },
  { name: 'Forest and cream', design: { primary: '#14532D', accent: '#B45309', background: '#FEFCE8', font: 'elegant', corners: 'soft' } },
  { name: 'Charcoal and red', design: { primary: '#27272A', accent: '#DC2626', background: '#FAFAFA', font: 'modern', corners: 'sharp' } },
  { name: 'Teal fresh', design: { primary: '#115E59', accent: '#14B8A6', background: '#F0FDFA', font: 'modern', corners: 'round' } },
  { name: 'Lavender', design: { primary: '#4C1D95', accent: '#9333EA', background: '#FAF5FF', font: 'rounded', corners: 'round' } },
  { name: 'Coral', design: { primary: '#9F1239', accent: '#FB7185', background: '#FFF1F2', font: 'sans', corners: 'round' } },
  { name: 'Olive', design: { primary: '#3F6212', accent: '#CA8A04', background: '#F7FEE7', font: 'elegant', corners: 'soft' } },
  { name: 'Night red', design: { primary: '#450A0A', accent: '#F97316', background: '#1C1917', font: 'serif', corners: 'soft' } },
  { name: 'Monochrome', design: { primary: '#18181B', accent: '#71717A', background: '#FFFFFF', font: 'modern', corners: 'sharp' } },
];

async function downloadFile(path: string, filename: string) {
  const res = await apiFetch(path);
  if (!res.ok) throw new Error('Could not prepare that file.');
  const url = URL.createObjectURL(await res.blob());
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

function ItemEditor({
  item,
  categories,
  currency,
  onSave,
  onPhoto,
  onCancel,
}: {
  item: Row;
  categories: Row[];
  currency: string;
  onSave: (body: Row) => void;
  onPhoto: (file: File) => void;
  onCancel: () => void;
}) {
  const [name, setName] = useState(item.name || '');
  const [price, setPrice] = useState(String(item.price ?? ''));
  const [description, setDescription] = useState(item.description || '');
  const [promo, setPromo] = useState(item.promo_label || '');
  const [categoryId, setCategoryId] = useState(item.category_id);
  return (
    <form
      className="dmenu-edit"
      onSubmit={(e) => {
        e.preventDefault();
        onSave({
          name: name.trim(),
          price: Number(price),
          description: description.trim() || null,
          promo_label: promo.trim() || null,
          category_id: categoryId,
        });
      }}
    >
      <label>
        Name
        <input value={name} onChange={(e) => setName(e.target.value)} required maxLength={200} aria-label="Dish name" />
      </label>
      <label>
        Price ({currency})
        <input value={price} onChange={(e) => setPrice(e.target.value)} inputMode="decimal" required aria-label="Dish price" />
      </label>
      <label>
        Category
        <select value={categoryId} onChange={(e) => setCategoryId(e.target.value)} aria-label="Dish category">
          {categories.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </select>
      </label>
      <label>
        Promotion label
        <input
          value={promo}
          onChange={(e) => setPromo(e.target.value)}
          maxLength={60}
          placeholder="Chef's pick"
          aria-label="Dish promotion label"
        />
      </label>
      <label className="dmenu-wide">
        Description
        <textarea value={description} onChange={(e) => setDescription(e.target.value)} maxLength={500} rows={2} aria-label="Dish description" />
      </label>
      <label className="dmenu-wide">
        Photo
        <input
          type="file"
          accept="image/png,image/jpeg,image/webp"
          aria-label="Dish photo"
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) onPhoto(file);
          }}
        />
      </label>
      <div className="dmenu-wide dmenu-row-actions">
        <button type="submit" className="btn-ok">
          Save
        </button>
        <button type="button" onClick={onCancel}>
          Cancel
        </button>
      </div>
    </form>
  );
}

export default function RestaurantDigitalMenuPage() {
  const [data, setData] = useState<Row | null>(null);
  const [me, setMe] = useState<Row | null>(null);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);
  const [editing, setEditing] = useState('');
  const [newCategory, setNewCategory] = useState('');
  const [qr, setQr] = useState('');
  const [preview, setPreview] = useState<GuestMenu | null>(null);
  const [adding, setAdding] = useState<Row>({ category_id: '', name: '', price: '', station: 'kitchen' });
  const qrRef = useRef('');

  const load = useCallback(async () => {
    const res = await api('/restaurant/menu');
    setData(res.data);
    return res.data as Row;
  }, []);

  const loadQr = useCallback(async () => {
    const res = await apiFetch('/restaurant/menu/qr.png');
    if (!res.ok) return;
    const url = URL.createObjectURL(await res.blob());
    if (qrRef.current) URL.revokeObjectURL(qrRef.current);
    qrRef.current = url;
    setQr(url);
  }, []);

  useEffect(() => {
    load().then(loadQr).catch((err) => setError(problem(err)));
    void getMe().then((res) => setMe(res?.data || null)).catch(() => undefined);
    return () => {
      if (qrRef.current) URL.revokeObjectURL(qrRef.current);
    };
  }, [load, loadQr]);

  const [previewMode, setPreviewMode] = useState<'phone' | 'desktop'>('phone');
  const [previewTick, setPreviewTick] = useState(0);

  const [dropping, setDropping] = useState(false);

  function uploadSiteImage(file?: File | null) {
    if (!file) return;
    if (!/^image\/(png|jpe?g|webp)$/i.test(file.type)) {
      setError('Choose a JPG, PNG or WebP photo.');
      return;
    }
    void run(async () => {
      const form = new FormData();
      form.append('file', file);
      await api('/restaurant/menu/site-image', { method: 'POST', body: form });
    }, 'Display image saved.');
  }

  async function run(action: () => Promise<unknown>, done?: string) {
    setBusy(true);
    setError('');
    setNotice('');
    try {
      await action();
      await load();
      setPreviewTick((t) => t + 1);
      if (preview) setPreview((await api('/restaurant/menu/preview')).data);
      if (done) setNotice(done);
    } catch (err) {
      setError(problem(err));
    } finally {
      setBusy(false);
    }
  }

  const send = (path: string, method: string, body?: unknown) =>
    api(path, { method, body: body === undefined ? undefined : JSON.stringify(body) });

  const logoPreview = useStaffImage(preview && data?.has_logo ? '/tenants/me/logo' : null, preview?.restaurant?.logo_version);
  const siteImagePreview = useStaffImage(data?.settings?.has_site_image ? '/restaurant/menu/site-image' : null, data?.settings?.has_site_image ? `y${previewTick}` : 'n');
  const bannerPreview = useStaffImage(preview?.banner?.version ? '/restaurant/menu/banner' : null, preview?.banner?.version);

  if (!data) {
    return (
      <div className="rdesk">
        <p className="muted">{error || 'Loading the menu…'}</p>
      </div>
    );
  }

  const settings: Row = data.settings;
  const categories: Row[] = data.categories || [];
  const unlisted: Row[] = data.unlisted || [];
  const currency: string = data.currency;
  const editable = canEditMenu(me);
  const slug = String(data.company_name || 'restaurant').toLowerCase().replace(/[^a-z0-9]+/g, '-');

  const design: Row = settings.site_design || { font: 'serif', corners: 'round', layout: 'square', pattern: 'none' };

  function saveDesign(patch: Row, done = 'Website design saved.') {
    void run(() => send('/restaurant/menu/site-design', 'PATCH', patch), done);
  }

  function saveSettings(patch: Row, done = 'Saved.') {
    void run(() => send('/restaurant/menu/settings', 'PATCH', patch), done);
  }

  function move(list: Row[], index: number, delta: number): string[] {
    const ids = list.map((row) => row.id);
    const [picked] = ids.splice(index, 1);
    ids.splice(index + delta, 0, picked);
    return ids;
  }

  function regenerate() {
    const ok = window.confirm('Make a new QR code? Every printed code and saved link stops working straight away.');
    if (!ok) return;
    void run(async () => {
      await send('/restaurant/menu/regenerate-link', 'POST');
      await loadQr();
    }, 'New QR code ready. Print it again for your tables.');
  }

  async function togglePreview() {
    if (preview) {
      setPreview(null);
      return;
    }
    try {
      setPreview((await api('/restaurant/menu/preview')).data);
    } catch (err) {
      setError(problem(err));
    }
  }

  async function copyLink() {
    try {
      await navigator.clipboard.writeText(settings.public_url);
      setNotice('Link copied.');
    } catch {
      setError('Could not copy. Select the link and copy it by hand.');
    }
  }

  return (
    <div className="rdesk dmenu">
      <header className="rd-head">
        <div>
          <h1>Digital menu</h1>
          <p>Your menu for the TV screen and the QR code on your tables. Changes show on every screen within a minute.</p>
        </div>
        <div className="rd-head-actions">
          <button type="button" onClick={() => void togglePreview()}>
            {preview ? 'Close preview' : 'Preview'}
          </button>
        </div>
      </header>

      {error ? <p className="dmenu-error" role="alert">{error}</p> : null}
      {notice ? <p className="dmenu-ok" role="status">{notice}</p> : null}

      {preview ? (
        <section className="dmenu-phone" aria-label="Menu preview">
          <GuestMenuView
            menu={preview}
            logoSrc={logoPreview}
            bannerSrc={bannerPreview}
            photo={(item: GuestItem) => (item.image_version ? <StaffPhoto itemId={item.id} version={item.image_version} /> : null)}
          />
        </section>
      ) : null}

      <div className="dmenu-top">
        <section className="rd-panel dmenu-share">
          <div className="rd-panel-head">
            <h2>Share your menu</h2>
            <span className={`dmenu-state${settings.is_published ? ' on' : ''}`}>
              {settings.is_published ? 'Live for guests' : 'Not published'}
            </span>
          </div>
          <div className="dmenu-qr">
            {qr ? <img src={qr} alt="QR code for your menu" /> : <div className="dmenu-qr-empty" />}
            <div>
              {editable ? (
                <button
                  type="button"
                  className={settings.is_published ? 'btn-danger' : 'btn-ok'}
                  disabled={busy}
                  onClick={() =>
                    saveSettings(
                      { is_published: !settings.is_published },
                      settings.is_published ? 'Menu unpublished. Guests can no longer open it.' : 'Your menu is live.'
                    )
                  }
                >
                  {settings.is_published ? 'Unpublish menu' : 'Publish menu'}
                </button>
              ) : null}
              <p className="dmenu-link">
                <a href={settings.public_url} target="_blank" rel="noreferrer">
                  {settings.public_url}
                </a>
              </p>
              <div className="dmenu-row-actions">
                <button type="button" onClick={() => void copyLink()}>
                  Copy link
                </button>
                <button
                  type="button"
                  onClick={() =>
                    void downloadFile('/restaurant/menu/qr.png?size=large', `menu-qr-${slug}.png`).catch((err) => setError(problem(err)))
                  }
                >
                  Download PNG
                </button>
                <button
                  type="button"
                  onClick={() =>
                    void downloadFile('/restaurant/menu/qr.pdf', `menu-qr-card-${slug}.pdf`).catch((err) => setError(problem(err)))
                  }
                >
                  Printable card (PDF)
                </button>
                <a className="dmenu-btn" href={settings.board_url} target="_blank" rel="noreferrer">
                  Open TV board
                </a>
                {editable ? (
                  <button type="button" className="btn-danger" disabled={busy} onClick={regenerate}>
                    New QR code
                  </button>
                ) : null}
              </div>
            </div>
          </div>
        </section>

        <section className="rd-panel">
          <div className="rd-panel-head">
            <h2>Look and feel</h2>
          </div>
          <div className="dmenu-look">
            <label>
              Tagline
              <input
                key={settings.tagline || ''}
                defaultValue={settings.tagline || ''}
                maxLength={160}
                disabled={!editable}
                aria-label="Menu tagline"
                placeholder="Fresh from our kitchen"
                onBlur={(e) => {
                  const next = e.target.value.trim() || null;
                  if (next !== (settings.tagline || null)) saveSettings({ tagline: next });
                }}
              />
            </label>
            <label>
              Accent colour
              <input
                type="color"
                value={settings.accent_color}
                disabled={!editable}
                aria-label="Menu accent colour"
                onChange={(e) => saveSettings({ accent_color: e.target.value })}
              />
            </label>
            {([
              ['primary_color', 'Header and card colour', '#006B2E', 'Menu header colour'],
              ['background_color', 'Page background colour', '#F5FAF0', 'Menu background colour'],
              ['board_background_color', 'TV board background colour', '#001A0E', 'TV board background colour'],
            ] as const).map(([key, label, fallback, aria]) => (
              <label key={key}>
                {label}
                <span className="dmenu-colour">
                  <input
                    type="color"
                    value={settings[key] || fallback}
                    disabled={!editable}
                    aria-label={aria}
                    onChange={(e) => saveSettings({ [key]: e.target.value })}
                  />
                  {settings[key] ? (
                    <button type="button" disabled={!editable} aria-label={`Reset ${label.toLowerCase()}`} onClick={() => saveSettings({ [key]: null }, 'Colour reset.')}>
                      Reset
                    </button>
                  ) : (
                    <small>Default</small>
                  )}
                </span>
              </label>
            ))}
            <label>
              Background pattern
              <select
                value={settings.background_pattern || 'food'}
                disabled={!editable}
                aria-label="Menu background pattern"
                onChange={(e) => saveSettings({ background_pattern: e.target.value })}
              >
                <option value="food">Food icons</option>
                <option value="dots">Soft dots</option>
                <option value="none">Plain</option>
              </select>
            </label>
            <label>
              Board style
              <select
                value={settings.board_style}
                disabled={!editable}
                aria-label="Board style"
                onChange={(e) => saveSettings({ board_style: e.target.value })}
              >
                <option value="forest">Dark green</option>
                <option value="mist">Light</option>
              </select>
            </label>
            <label>
              Seconds per board page
              <input
                type="number"
                min={5}
                max={60}
                key={settings.board_rotate_seconds}
                defaultValue={settings.board_rotate_seconds}
                disabled={!editable}
                aria-label="Seconds per board page"
                onBlur={(e) => {
                  const next = Math.min(60, Math.max(5, Number(e.target.value) || 12));
                  if (next !== settings.board_rotate_seconds) saveSettings({ board_rotate_seconds: next });
                }}
              />
            </label>
            <label>
              Banner image
              <input
                type="file"
                accept="image/png,image/jpeg,image/webp"
                disabled={!editable}
                aria-label="Menu banner image"
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  e.target.value = '';
                  if (!file) return;
                  void run(async () => {
                    const form = new FormData();
                    form.append('file', file);
                    await api('/restaurant/menu/banner', { method: 'POST', body: form });
                  }, 'Banner saved.');
                }}
              />
            </label>
            {settings.has_banner ? (
              <>
                <label>
                  Banner position
                  <select
                    value={settings.banner_position || 'top'}
                    disabled={!editable}
                    aria-label="Banner position"
                    onChange={(e) => saveSettings({ banner_position: e.target.value })}
                  >
                    <option value="top">Top of the menu</option>
                    <option value="footer">Bottom of the menu</option>
                  </select>
                </label>
                <button
                  type="button"
                  className="btn-danger"
                  disabled={!editable}
                  aria-label="Remove menu banner"
                  onClick={() => void run(() => send('/restaurant/menu/banner', 'DELETE'), 'Banner removed.')}
                >
                  Remove banner
                </button>
              </>
            ) : null}
            <p className="dmenu-hint">
              {data.has_logo
                ? 'Your company logo shows at the top of the menu.'
                : 'Add your logo under Company to show it at the top of the menu.'}
            </p>
            <label className="dmenu-check">
              <input
                type="checkbox"
                checked={settings.show_unavailable}
                disabled={!editable}
                aria-label="Show unavailable dishes"
                onChange={(e) => saveSettings({ show_unavailable: e.target.checked })}
              />
              Show sold-out dishes, marked unavailable
            </label>
          </div>
        </section>
      </div>

      <OnlineAlertsPanel editable={editable} />

      <section className="rd-panel dmenu-design" aria-label="Website design">
        <div className="rd-panel-head">
          <h2>Website design</h2>
          <small>How your online ordering and booking pages look to customers. Every change saves at once and shows in the preview.</small>
        </div>
        <div className="dmenu-design-grid">
          <div className="dmenu-design-controls">
            <fieldset className="dmenu-step">
              <legend><span>1</span> Pick a look</legend>
              <div className="dmenu-presets" role="group" aria-label="Design starters">
                {DESIGN_PRESETS.map((preset) => {
                  const on = ['primary', 'accent', 'background'].every((k) => (design[k] || '').toUpperCase() === preset.design[k].toUpperCase());
                  return (
                    <button
                      key={preset.name}
                      type="button"
                      className={`dmenu-preset${on ? ' on' : ''}`}
                      disabled={!editable}
                      aria-pressed={on}
                      aria-label={`Use the ${preset.name} look`}
                      onClick={() => saveDesign(preset.design, `${preset.name} look applied. Change anything below.`)}
                    >
                      <span className="sws">
                        <span className="sw" style={{ background: preset.design.primary }} />
                        <span className="sw" style={{ background: preset.design.accent }} />
                        <span className="sw" style={{ background: preset.design.background }} />
                      </span>
                      {preset.name}
                    </button>
                  );
                })}
              </div>
            </fieldset>

            <fieldset className="dmenu-step">
              <legend><span>2</span> Your colours</legend>
              <div className="dmenu-colours">
                {([
                  ['primary', 'Main colour', 'Header, buttons, booking area', '#003D1F'],
                  ['accent', 'Highlight colour', 'Badges and selected dishes', '#4AB012'],
                  ['background', 'Page background', 'Behind everything', '#FFFFFF'],
                ] as const).map(([key, label, help, fallback]) => (
                  <div key={key} className="dmenu-colour-row">
                    <input
                      type="color"
                      value={design[key] || fallback}
                      disabled={!editable}
                      aria-label={`Website ${label}`}
                      onChange={(e) => saveDesign({ [key]: e.target.value })}
                    />
                    <span className="t">
                      <strong>{label}</strong>
                      <small>{help}</small>
                    </span>
                    <code>{(design[key] || 'Default').toUpperCase()}</code>
                    {design[key] ? (
                      <button type="button" className="rd-link" disabled={!editable} aria-label={`Reset website ${label}`} onClick={() => saveDesign({ [key]: null }, 'Colour reset.')}>
                        Reset
                      </button>
                    ) : null}
                  </div>
                ))}
              </div>
            </fieldset>

            <fieldset className="dmenu-step">
              <legend><span>3</span> Display image</legend>
              <div className="dmenu-hero-image">
                <label
                  className={`dmenu-drop${siteImagePreview ? ' has' : ''}${dropping ? ' over' : ''}`}
                  onDragOver={(e) => {
                    e.preventDefault();
                    if (editable) setDropping(true);
                  }}
                  onDragLeave={() => setDropping(false)}
                  onDrop={(e) => {
                    e.preventDefault();
                    setDropping(false);
                    if (editable) uploadSiteImage(e.dataTransfer.files?.[0]);
                  }}
                >
                  {siteImagePreview ? <img src={siteImagePreview} alt="Your display image" /> : null}
                  <span className="dmenu-drop-text">
                    <b>{busy ? 'Saving…' : siteImagePreview ? 'Change image' : 'Add your image'}</b>
                    <small>{siteImagePreview ? 'Click or drop a new photo' : 'Click here or drop a photo'}</small>
                  </span>
                  <input
                    type="file"
                    accept="image/png,image/jpeg,image/webp"
                    disabled={!editable || busy}
                    aria-label="Website display image"
                    onChange={(e) => {
                      uploadSiteImage(e.target.files?.[0]);
                      e.target.value = '';
                    }}
                  />
                </label>
                <div className="dmenu-hero-side">
                  <p className="dmenu-hint">
                    The big picture at the top of your site. Choose the one you like best and change it any time. A wide photo of your food or your place works best (JPG, PNG or WebP). We make it smaller for you so the site stays fast.
                  </p>
                  {settings.has_site_image ? (
                    <button type="button" className="dmenu-remove" disabled={!editable || busy} aria-label="Remove website display image" onClick={() => void run(() => send('/restaurant/menu/site-image', 'DELETE'), 'Display image removed.')}>
                      Remove image
                    </button>
                  ) : null}
                </div>
              </div>
              <div className="dmenu-styles" role="group" aria-label="Image style">
                {([
                  ['full', 'Full width', 'Behind the title'],
                  ['split', 'Beside title', 'Next to the text'],
                  ['plain', 'No image', 'Just colour'],
                ] as const).map(([key, title, sub]) => (
                  <button key={key} type="button" className={`dmenu-style${(design.hero || 'full') === key ? ' on' : ''}`} aria-pressed={(design.hero || 'full') === key} disabled={!editable} onClick={() => saveDesign({ hero: key })}>
                    <span className={`pic ${key}`} aria-hidden>
                      <i />
                      <i />
                    </span>
                    <b>{title}</b>
                    <small>{sub}</small>
                  </button>
                ))}
              </div>
            </fieldset>

            <fieldset className="dmenu-step">
              <legend><span>4</span> Style</legend>
              <Choice label="Font" value={design.font} disabled={!editable} options={[['serif', 'Classic'], ['elegant', 'Elegant'], ['sans', 'Clean'], ['modern', 'Modern'], ['rounded', 'Friendly']]} onPick={(v) => saveDesign({ font: v })} />
              <Choice label="Corners" value={design.corners} disabled={!editable} options={[['round', 'Round'], ['soft', 'Soft'], ['sharp', 'Sharp']]} onPick={(v) => saveDesign({ corners: v })} />
              <Choice label="Menu layout" value={design.layout} disabled={!editable} options={[['square', 'Square cards'], ['list', 'List']]} onPick={(v) => saveDesign({ layout: v })} />
              <Choice label="Dish cards" value={design.cards || 'shadow'} disabled={!editable} options={[['shadow', 'Shadow'], ['outline', 'Outline'], ['flat', 'Flat']]} onPick={(v) => saveDesign({ cards: v })} />
              <Choice label="Top bar" value={design.header || 'glass'} disabled={!editable} options={[['glass', 'Frosted'], ['solid', 'Main colour'], ['plain', 'Plain']]} onPick={(v) => saveDesign({ header: v })} />
              <Choice label="Title position" value={design.align || 'left'} disabled={!editable} options={[['left', 'Left'], ['center', 'Centred']]} onPick={(v) => saveDesign({ align: v })} />
              <Choice label="Info chips" value={design.show_facts === false ? 'off' : 'on'} disabled={!editable} options={[['on', 'Show'], ['off', 'Hide']]} onPick={(v) => saveDesign({ show_facts: v === 'on' })} />
              <Choice label="Background" value={design.pattern} disabled={!editable} options={[['none', 'Plain'], ['food', 'Food icons']]} onPick={(v) => saveDesign({ pattern: v })} />
            </fieldset>

            <fieldset className="dmenu-step">
              <legend><span>5</span> Your words</legend>
              <label className="dmenu-field">
                Headline
                <input
                  key={`h-${design.headline || ''}`}
                  defaultValue={design.headline || ''}
                  maxLength={80}
                  disabled={!editable}
                  placeholder="Your restaurant name"
                  aria-label="Website headline"
                  onBlur={(e) => {
                    const next = e.target.value.trim() || null;
                    if (next !== (design.headline || null)) saveDesign({ headline: next });
                  }}
                />
              </label>
              <label className="dmenu-field">
                Welcome text
                <input
                  key={`i-${design.intro || ''}`}
                  defaultValue={design.intro || ''}
                  maxLength={240}
                  disabled={!editable}
                  placeholder="A line about your food"
                  aria-label="Website welcome text"
                  onBlur={(e) => {
                    const next = e.target.value.trim() || null;
                    if (next !== (design.intro || null)) saveDesign({ intro: next });
                  }}
                />
              </label>
            </fieldset>
          </div>

          <aside className="dmenu-design-preview" aria-label="Website preview">
            <div className="dmenu-preview-bar">
              <Choice label="" value={previewMode} options={[['phone', 'Phone'], ['desktop', 'Computer']]} onPick={(v) => setPreviewMode(v as 'phone' | 'desktop')} />
              {data.site_slug ? (
                <a href={`/order/${data.site_slug}`} target="_blank" rel="noreferrer" className="dmenu-btn">
                  Open site
                </a>
              ) : null}
            </div>
            <div className={`dmenu-device ${previewMode}`}>
              {data.site_slug ? (
                <iframe key={previewTick} title="Your website" src={`/order/${data.site_slug}?preview=${previewTick}`} loading="lazy" />
              ) : null}
            </div>
            <p className="dmenu-hint">If the preview says the page is not open, switch on online orders or the booking link first.</p>
          </aside>
        </div>
      </section>

      {categories.map((category, categoryIndex) => (
        <section key={category.id} className="rd-panel dmenu-category">
          <div className="rd-panel-head">
            <h2>
              {category.name}
              {category.is_published ? null : <small> · hidden from guests</small>}
            </h2>
            {editable ? (
              <div className="dmenu-row-actions">
                <button
                  type="button"
                  aria-label={`Move ${category.name} up`}
                  disabled={busy || categoryIndex === 0}
                  onClick={() => void run(() => send('/restaurant/menu/categories/order', 'PUT', { ids: move(categories, categoryIndex, -1) }))}
                >
                  ↑
                </button>
                <button
                  type="button"
                  aria-label={`Move ${category.name} down`}
                  disabled={busy || categoryIndex === categories.length - 1}
                  onClick={() => void run(() => send('/restaurant/menu/categories/order', 'PUT', { ids: move(categories, categoryIndex, 1) }))}
                >
                  ↓
                </button>
                <button
                  type="button"
                  disabled={busy}
                  onClick={() =>
                    void run(() => send(`/restaurant/menu/categories/${category.id}`, 'PATCH', { is_published: !category.is_published }))
                  }
                >
                  {category.is_published ? 'Hide' : 'Show'}
                </button>
                {category.items.length === 0 ? (
                  <button
                    type="button"
                    className="btn-danger"
                    disabled={busy}
                    onClick={() => void run(() => send(`/restaurant/menu/categories/${category.id}`, 'DELETE'), 'Category removed.')}
                  >
                    Remove
                  </button>
                ) : null}
              </div>
            ) : null}
          </div>

          {category.items.length === 0 ? <p className="muted">No dishes here yet.</p> : null}
          {category.items.map((item: Row, itemIndex: number) => (
            <div key={item.id} className={`dmenu-item${item.is_published ? '' : ' is-draft'}`}>
              <div className="dmenu-line">
                <div className="dmenu-thumb">{item.has_image ? <StaffPhoto itemId={item.id} /> : null}</div>
                <div className="dmenu-name">
                  <strong>{item.name}</strong>
                  <small>
                    {menuPrice(item.price, currency)}
                    {item.promo_label ? ` · ${item.promo_label}` : ''}
                    {item.available ? '' : ' · sold out'}
                    {item.dish_active ? '' : ' · dish switched off'}
                  </small>
                </div>
                {editable ? (
                  <div className="dmenu-row-actions">
                    <button
                      type="button"
                      aria-label={`Move ${item.name} up`}
                      disabled={busy || itemIndex === 0}
                      onClick={() =>
                        void run(() => send(`/restaurant/menu/categories/${category.id}/items/order`, 'PUT', { ids: move(category.items, itemIndex, -1) }))
                      }
                    >
                      ↑
                    </button>
                    <button
                      type="button"
                      aria-label={`Move ${item.name} down`}
                      disabled={busy || itemIndex === category.items.length - 1}
                      onClick={() =>
                        void run(() => send(`/restaurant/menu/categories/${category.id}/items/order`, 'PUT', { ids: move(category.items, itemIndex, 1) }))
                      }
                    >
                      ↓
                    </button>
                    <button
                      type="button"
                      aria-pressed={item.is_published}
                      disabled={busy}
                      onClick={() => void run(() => send(`/restaurant/menu/items/${item.id}`, 'PATCH', { is_published: !item.is_published }))}
                    >
                      {item.is_published ? 'Unpublish' : 'Publish'}
                    </button>
                    <button
                      type="button"
                      aria-pressed={!item.available}
                      disabled={busy}
                      onClick={() => void run(() => send(`/restaurant/menu/items/${item.id}`, 'PATCH', { available: !item.available }))}
                    >
                      {item.available ? 'Mark sold out' : 'Mark available'}
                    </button>
                    <button
                      type="button"
                      aria-pressed={item.is_featured}
                      disabled={busy}
                      onClick={() => void run(() => send(`/restaurant/menu/items/${item.id}`, 'PATCH', { is_featured: !item.is_featured }))}
                    >
                      {item.is_featured ? 'Unfeature' : 'Feature'}
                    </button>
                    <button type="button" className="btn-ok" onClick={() => setEditing(editing === item.id ? '' : item.id)}>
                      Edit
                    </button>
                    <button
                      type="button"
                      className="btn-danger"
                      disabled={busy}
                      onClick={() => void run(() => send(`/restaurant/menu/items/${item.id}`, 'DELETE'), `${item.name} taken off the menu. It stays on the till.`)}
                    >
                      Remove
                    </button>
                  </div>
                ) : null}
              </div>
              {editing === item.id ? (
                <ItemEditor
                  item={item}
                  categories={categories}
                  currency={currency}
                  onCancel={() => setEditing('')}
                  onSave={(body) =>
                    void run(async () => {
                      await send(`/restaurant/menu/items/${item.id}`, 'PATCH', body);
                      setEditing('');
                    }, 'Dish saved. The till uses the same price.')
                  }
                  onPhoto={(file) =>
                    void run(async () => {
                      const form = new FormData();
                      form.append('file', file);
                      await api(`/restaurant/menu/items/${item.id}/photo`, { method: 'POST', body: form });
                    }, 'Photo saved.')
                  }
                />
              ) : null}
            </div>
          ))}
        </section>
      ))}

      {editable ? (
        <section className="rd-panel">
          <div className="rd-panel-head">
            <h2>Add to the menu</h2>
          </div>
          <form
            className="dmenu-add"
            onSubmit={(e) => {
              e.preventDefault();
              const name = newCategory.trim();
              if (!name) return;
              void run(async () => {
                await send('/restaurant/menu/categories', 'POST', { name });
                setNewCategory('');
              }, 'Category added.');
            }}
          >
            <label>
              New category
              <input value={newCategory} onChange={(e) => setNewCategory(e.target.value)} maxLength={120} aria-label="New category name" />
            </label>
            <button type="submit" className="btn-ok" disabled={busy || !newCategory.trim()}>
              Add category
            </button>
          </form>

          {categories.length > 0 ? (
            <form
              className="dmenu-add"
              onSubmit={(e) => {
                e.preventDefault();
                void run(async () => {
                  await send('/restaurant/menu/items', 'POST', {
                    category_id: adding.category_id || categories[0].id,
                    name: String(adding.name).trim(),
                    price: Number(adding.price),
                    station: adding.station,
                  });
                  setAdding({ category_id: adding.category_id, name: '', price: '', station: adding.station });
                }, 'Dish added. It is on the till too.');
              }}
            >
              <label>
                New dish
                <input
                  value={adding.name}
                  onChange={(e) => setAdding({ ...adding, name: e.target.value })}
                  maxLength={200}
                  aria-label="New dish name"
                />
              </label>
              <label>
                Price ({currency})
                <input
                  value={adding.price}
                  inputMode="decimal"
                  onChange={(e) => setAdding({ ...adding, price: e.target.value })}
                  aria-label="New dish price"
                />
              </label>
              <label>
                Category
                <select
                  value={adding.category_id || categories[0].id}
                  onChange={(e) => setAdding({ ...adding, category_id: e.target.value })}
                  aria-label="New dish category"
                >
                  {categories.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Made in
                <select
                  value={adding.station}
                  onChange={(e) => setAdding({ ...adding, station: e.target.value })}
                  aria-label="New dish station"
                >
                  <option value="kitchen">Kitchen</option>
                  <option value="bar">Bar</option>
                </select>
              </label>
              <button type="submit" className="btn-ok" disabled={busy || !String(adding.name).trim() || adding.price === ''}>
                Add dish
              </button>
            </form>
          ) : null}

          {unlisted.length > 0 && categories.length > 0 ? (
            <div className="dmenu-unlisted">
              <h3>On the till, not on this menu</h3>
              {unlisted.map((dish) => (
                <div key={dish.id} className="dmenu-line">
                  <div className="dmenu-name">
                    <strong>{dish.name}</strong>
                    <small>{menuPrice(dish.price, currency)}</small>
                  </div>
                  <button
                    type="button"
                    className="btn-ok"
                    disabled={busy}
                    onClick={() =>
                      void run(() =>
                        send('/restaurant/menu/items', 'POST', {
                          category_id: adding.category_id || categories[0].id,
                          product_id: dish.id,
                        })
                      )
                    }
                  >
                    Add
                  </button>
                </div>
              ))}
            </div>
          ) : null}
        </section>
      ) : null}
    </div>
  );
}
