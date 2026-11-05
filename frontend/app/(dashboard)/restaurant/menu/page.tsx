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
import '../restaurant-desk.css';
import './menu-admin.css';

function canEditMenu(me: Row | null): boolean {
  const perms = me?.permissions;
  if (!perms) return false;
  if (Array.isArray(perms['*'])) return true;
  return (perms.inventory || []).some((a: string) => a === 'write' || a === '*');
}

/** Staff can see photos before the menu is public, so these load with the staff session. */
function StaffPhoto({ itemId, version }: { itemId: string; version?: string | null }) {
  const [url, setUrl] = useState('');
  useEffect(() => {
    let live = true;
    let made = '';
    apiFetch(`/restaurant/menu/items/${itemId}/photo`)
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
  }, [itemId, version]);
  return url ? <img src={url} alt="" /> : null;
}

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

  async function run(action: () => Promise<unknown>, done?: string) {
    setBusy(true);
    setError('');
    setNotice('');
    try {
      await action();
      await load();
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
