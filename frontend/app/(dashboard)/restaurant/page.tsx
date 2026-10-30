'use client';

import { useEffect, useRef, useState, type FormEvent, type PointerEvent as ReactPointerEvent } from 'react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import DashboardGreeting from '../../../components/DashboardGreeting';
import PageHeader from '../../../components/PageHeader';
import { api } from '../../../lib/api';
import { formatDateTime, formatMoney } from '../../../lib/format';
import { getMe } from '../../../lib/meCache';
import { moduleEnabledForTenant } from '../../../lib/industryModules';
import { whereWords as deskWhere } from '../../../lib/restaurantDesk';
import './restaurant-desk.css';

type Row = Record<string, any>;

const ORDER_WORDS: Record<string, string> = {
  dine_in: 'Dine in',
  takeaway: 'Takeaway',
  delivery: 'Delivery',
  cash: 'Cash',
  card: 'Card',
  wallet: 'Wallet',
  mobile_money: 'Mobile Money',
  credit: 'Credit',
  open: 'Open',
  sent: 'In the kitchen',
  preparing: 'Preparing',
  ready: 'Ready',
  completed: 'Completed',
  cancelled: 'Cancelled',
  voided: 'Voided',
  refunded: 'Refunded',
  queued: 'Queued',
  kitchen: 'Kitchen',
  bar: 'Bar',
  available: 'Available',
  occupied: 'Occupied',
  held: 'Held',
  reserved: 'Reserved',
  requested: 'Requested',
  seated: 'Seated',
  finished: 'Finished',
  done: 'Done',
  spoilage: 'Spoilage',
  damage: 'Damage',
  waste: 'Waste',
  starter: 'Starter',
  main: 'Main',
  dessert: 'Dessert',
  drink: 'Drink',
  mild: 'Mild',
  medium: 'Medium',
  hot: 'Hot',
  rare: 'Rare',
  well: 'Well',
  bag: 'Bag',
  box: 'Box',
  dining: 'Dining',
  patio: 'Patio',
  private: 'Private',
  vegetarian: 'Vegetarian',
  vegan: 'Vegan',
  halal: 'Halal',
  nuts: 'Nuts',
  gluten: 'Gluten',
  dairy: 'Dairy',
  shellfish: 'Shellfish',
  walk_in: 'Walk-in',
  phone: 'Phone',
  booking: 'Booking',
  hand: 'Hand to guest',
  door: 'Leave at door',
  print: 'Print',
  email: 'Email',
  declined: 'Declined',
};

async function loadDesk(path: string) {
  try {
    return await api(path);
  } catch {
    return { data: null };
  }
}

function tableFloor(tables: Record<string, unknown> | null | undefined) {
  const rows = Object.entries(tables || {}).filter(([, count]) => Number(count) > 0);
  if (!rows.length) return 'No tables yet';
  return rows.map(([status, count]) => `${orderWord(status)} ${count}`).join(' · ');
}

function tenderLabel(row: Row) {
  if (
    row.channel === 'online'
    && row.status !== 'completed'
    && row.status !== 'refunded'
    && row.status !== 'cancelled'
    && row.status !== 'voided'
  ) {
    return 'Pay at the counter';
  }
  return row.payment_method ? orderWord(row.payment_method) : '';
}

/** Each desk says what it is for, in one line. */
const TAB_HEADINGS: Record<string, [string, string]> = {
  tables: ['Tables and floor', 'Drag tables to match your room. Take an order, hold a table, or edit it from its card.'],
  booking: ['Website and booking', 'Your public website, table bookings and walk-ins.'],
  kitchen: ['Kitchen', 'Every dish to cook, oldest first. Start it, then mark it ready.'],
  recipes: ['Recipes', 'What goes into each dish, so stock comes off when it sells.'],
  waste: ['Waste', 'Record spoiled or dropped ingredients so stock stays right.'],
  orders: [
    'Full order editor',
    'Dine-in, takeaway, and delivery. Kitchen tickets follow each item station. Completing an order deducts recipe ingredients.',
  ],
};

function onlineLabel(row: Row) {
  return row.channel === 'online' ? 'Online' : '';
}

function playKitchenChime(ctx: AudioContext) {
  const tone = ctx.createOscillator();
  const level = ctx.createGain();
  tone.frequency.value = 880;
  level.gain.value = 0.05;
  tone.connect(level);
  level.connect(ctx.destination);
  tone.start();
  tone.stop(ctx.currentTime + 0.18);
}

function defaultFloorSpot(index: number) {
  const col = index % 3;
  const row = Math.floor(index / 3);
  return { x: 4 + col * 28, y: 8 + row * 32 };
}

function orderWord(code: unknown) {
  const key = String(code || '');
  return ORDER_WORDS[key] || key.replaceAll('_', ' ');
}

export default function RestaurantPage() {
  const tab = useSearchParams().get('tab') || 'dashboard';
  const [summary, setSummary] = useState<Row | null>(null);
  const [tables, setTables] = useState<Row[]>([]);
  const [stores, setStores] = useState<Row[]>([]);
  const [warehouses, setWarehouses] = useState<Row[]>([]);
  const [orders, setOrders] = useState<Row[]>([]);
  const [kitchen, setKitchen] = useState<Row[]>([]);
  const [products, setProducts] = useState<Row[]>([]);
  const [recipes, setRecipes] = useState<Row[]>([]);
  const [modifierGroups, setModifierGroups] = useState<Row[]>([]);
  const [selectedModifiers, setSelectedModifiers] = useState<string[]>([]);
  const [extraForm, setExtraForm] = useState({ group: '', name: '', price: '0' });
  const [tableForm, setTableForm] = useState({ code: '', name: '', seats: '2', store_id: '', room: '' });
  const [leftoverTableStores, setLeftoverTableStores] = useState<Record<string, string>>({});
  const [addingTable, setAddingTable] = useState(false);
  const [editingTable, setEditingTable] = useState('');
  const [retiringTable, setRetiringTable] = useState('');
  const [leftoverTableRooms, setLeftoverTableRooms] = useState<Record<string, string>>({});
  const [tableEdits, setTableEdits] = useState<Record<string, { code: string; name: string; seats: string }>>({});
  const [leftoverNotes, setLeftoverNotes] = useState<Record<string, string>>({});
  const [leftoverCovers, setLeftoverCovers] = useState<Record<string, string>>({});
  const [leftoverAllergies, setLeftoverAllergies] = useState<Record<string, string>>({});
  const [leftoverAllergens, setLeftoverAllergens] = useState<Record<string, string>>({});
  const [leftoverOccasions, setLeftoverOccasions] = useState<Record<string, string>>({});
  const [leftoverPhones, setLeftoverPhones] = useState<Record<string, string>>({});
  const [leftoverPagers, setLeftoverPagers] = useState<Record<string, string>>({});
  const [leftoverGuestEmails, setLeftoverGuestEmails] = useState<Record<string, string>>({});
  const [leftoverReceipts, setLeftoverReceipts] = useState<Record<string, string>>({});
  const [leftoverReadyBy, setLeftoverReadyBy] = useState<Record<string, string>>({});
  const [leftoverQuotedWaits, setLeftoverQuotedWaits] = useState<Record<string, string>>({});
  const [leftoverFireAt, setLeftoverFireAt] = useState<Record<string, string>>({});
  const [leftoverPackaging, setLeftoverPackaging] = useState<Record<string, string>>({});
  const [leftoverDiets, setLeftoverDiets] = useState<Record<string, string>>({});
  const [leftoverSources, setLeftoverSources] = useState<Record<string, string>>({});
  const [leftoverVehicles, setLeftoverVehicles] = useState<Record<string, string>>({});
  const [leftoverBays, setLeftoverBays] = useState<Record<string, string>>({});
  const [leftoverHandoffs, setLeftoverHandoffs] = useState<Record<string, string>>({});
  const [leftoverCustomerNames, setLeftoverCustomerNames] = useState<Record<string, string>>({});
  const [leftoverPaymentMethods, setLeftoverPaymentMethods] = useState<Record<string, string>>({});
  const [leftoverServiceModes, setLeftoverServiceModes] = useState<Record<string, string>>({});
  const [leftoverServiceTables, setLeftoverServiceTables] = useState<Record<string, string>>({});
  const [leftoverLineQuantities, setLeftoverLineQuantities] = useState<Record<string, string>>({});
  const [leftoverLinePrices, setLeftoverLinePrices] = useState<Record<string, string>>({});
  const [leftoverLineStations, setLeftoverLineStations] = useState<Record<string, string>>({});
  const [leftoverLineCourses, setLeftoverLineCourses] = useState<Record<string, string>>({});
  const [leftoverLineNotes, setLeftoverLineNotes] = useState<Record<string, string>>({});
  const [leftoverLineSeats, setLeftoverLineSeats] = useState<Record<string, string>>({});
  const [leftoverLineSpices, setLeftoverLineSpices] = useState<Record<string, string>>({});
  const [leftoverLineDoneness, setLeftoverLineDoneness] = useState<Record<string, string>>({});
  const [leftoverLineModifiers, setLeftoverLineModifiers] = useState<Record<string, string[]>>({});
  const [leftoverOrderStores, setLeftoverOrderStores] = useState<Record<string, string>>({});
  const [leftoverDeliveryAddresses, setLeftoverDeliveryAddresses] = useState<Record<string, string>>({});
  const [leftoverExtraPrices, setLeftoverExtraPrices] = useState<Record<string, string>>({});
  const [leftoverExtraNames, setLeftoverExtraNames] = useState<Record<string, string>>({});
  const [leftoverExtraGroupNames, setLeftoverExtraGroupNames] = useState<Record<string, string>>({});
  const [leftoverRecipeNames, setLeftoverRecipeNames] = useState<Record<string, string>>({});
  const [leftoverRecipeLineQuantities, setLeftoverRecipeLineQuantities] = useState<Record<string, string>>({});
  const [leftoverRecipeRemoved, setLeftoverRecipeRemoved] = useState<Record<string, string[]>>({});
  const [leftoverRecipeAdded, setLeftoverRecipeAdded] = useState<Record<string, { ingredient_id: string; quantity: string }[]>>({});
  const [leftoverRecipeIngredient, setLeftoverRecipeIngredient] = useState<Record<string, string>>({});
  const [leftoverNewItems, setLeftoverNewItems] = useState<Record<string, string>>({});
  const [leftoverNewQuantities, setLeftoverNewQuantities] = useState<Record<string, string>>({});
  const [leftoverNewModifiers, setLeftoverNewModifiers] = useState<Record<string, string[]>>({});
  const [orderForm, setOrderForm] = useState({
    service_mode: 'dine_in',
    payment_method: 'cash',
    store_id: '',
    table_id: '',
    product_id: '',
    quantity: '1',
    course: 'main',
    item_note: '',
    item_hold: false,
    item_seat: '',
    item_spice: '',
    item_doneness: '',
    covers: '',
    allergy: '',
    allergen: '',
    occasion: '',
    phone: '',
    guest_email: '',
    receipt: '',
    pager: '',
    ready_by: '',
    quoted_wait: '',
    fire_at: '',
    packaging: '',
    diet: '',
    guest_source: '',
    vehicle: '',
    bay: '',
    handoff: '',
    rush: false,
    bill_asked: false,
    guest_arrived: false,
    cutlery: false,
    high_chair: false,
    customer_name: '',
    delivery_address: '',
    delivery_zone: '',
    notes: '',
  });
  const [orderLines, setOrderLines] = useState<{ product_id: string; quantity: string; modifier_ids: string[]; course: string; note: string; hold: boolean; seat: string; spice: string; doneness: string }[]>([]);
  const [recipeForm, setRecipeForm] = useState({ product_id: '', ingredient_id: '', quantity: '1', name: '', cook_time: '', servings: '' });
  const [leftoverCookTimes, setLeftoverCookTimes] = useState<Record<string, string>>({});
  const [leftoverServings, setLeftoverServings] = useState<Record<string, string>>({});
  const [recipeLines, setRecipeLines] = useState<{ ingredient_id: string; quantity: string }[]>([]);
  const [stationForm, setStationForm] = useState({ product_id: '', station: 'kitchen' });
  const [wasteForm, setWasteForm] = useState({ product_id: '', quantity: '1', reason: 'spoilage', notes: '', warehouse_id: '' });
  const [wasteRows, setWasteRows] = useState<Row[]>([]);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [bookingLink, setBookingLink] = useState<Row | null>(null);
  const [bookings, setBookings] = useState<Row[]>([]);
  const [linkForm, setLinkForm] = useState({ hostname: '', link_kind: 'existing' });
  const [walkInForm, setWalkInForm] = useState({
    guest_name: '',
    phone: '',
    party_size: '2',
    booked_for: '',
    notes: '',
    turn: '',
  });
  const [restaurantDesk, setRestaurantDesk] = useState(false);
  const [pageOrigin, setPageOrigin] = useState('');
  const [seatTables, setSeatTables] = useState<Record<string, string>>({});
  const [leftoverBookings, setLeftoverBookings] = useState<Record<string, { guest_name: string; phone: string; party_size: string; booked_for: string; notes: string }>>({});
  const [leftoverTurns, setLeftoverTurns] = useState<Record<string, string>>({});
  const [bookingFilter, setBookingFilter] = useState('upcoming');
  const [addingBooking, setAddingBooking] = useState(false);
  const [editingBooking, setEditingBooking] = useState('');
  const [cancellingBooking, setCancellingBooking] = useState('');
  const [tillSession, setTillSession] = useState<Row | null>(null);
  const [deliveryZones, setDeliveryZones] = useState<string[]>([]);
  const [zoneName, setZoneName] = useState('');
  const [serviceDraft, setServiceDraft] = useState('');
  const [leftoverDeliveryZones, setLeftoverDeliveryZones] = useState<Record<string, string>>({});
  const [onlineOrders, setOnlineOrders] = useState<Row>({ open: false });
  const [floorPlaces, setFloorPlaces] = useState<Row[]>([]);
  const [floorDraft, setFloorDraft] = useState<Record<string, { x: number; y: number }>>({});
  const [kitchenSound, setKitchenSound] = useState<{ on: boolean }>({ on: false });
  const [clock, setClock] = useState<{ open: Row[]; mine_open: boolean }>({ open: [], mine_open: false });
  const [soldOut, setSoldOut] = useState<Row[]>([]);
  const [soldOutId, setSoldOutId] = useState('');
  const floorMapRef = useRef<HTMLDivElement | null>(null);
  const heardTickets = useRef<Set<string> | null>(null);
  const kitchenAudio = useRef<AudioContext | null>(null);

  async function refresh() {
    const [sum, tableRes, orderRes, kitchenRes] = await Promise.all([
      api('/restaurant/summary'),
      api('/restaurant/tables'),
      api('/restaurant/orders'),
      api('/restaurant/kitchen'),
    ]);
    setSummary(sum?.data || null);
    setTables(tableRes?.data || []);
    setOrders(orderRes?.data || []);
    setKitchen(kitchenRes?.data || []);
    const [productRes, linkRes, bookingRes, modifierRes, recipeRes, wasteRes, tillRes, storeRes, warehouseRes, zoneRes, onlineRes, floorRes, soundRes, clockRes, soldOutRes, serviceRes] = await Promise.all([
      loadDesk('/products'),
      loadDesk('/restaurant/booking-link'),
      loadDesk('/restaurant/bookings'),
      loadDesk('/restaurant/modifiers'),
      loadDesk('/restaurant/recipes'),
      loadDesk('/restaurant/waste'),
      loadDesk('/restaurant/till/shift'),
      loadDesk('/stores'),
      loadDesk('/warehouses'),
      loadDesk('/restaurant/delivery-zones'),
      loadDesk('/restaurant/online-orders'),
      loadDesk('/restaurant/floor-places'),
      loadDesk('/restaurant/kitchen-sound'),
      loadDesk('/restaurant/clock'),
      loadDesk('/restaurant/sold-out'),
      loadDesk('/restaurant/service-charge'),
    ]);
    const catalog = productRes?.data;
    setProducts(Array.isArray(catalog) ? catalog : catalog?.items || []);
    setWasteRows(Array.isArray(wasteRes?.data) ? wasteRes.data : []);
    setModifierGroups(Array.isArray(modifierRes?.data) ? modifierRes.data : []);
    setRecipes(Array.isArray(recipeRes?.data) ? recipeRes.data : []);
    setTillSession(tillRes?.data || null);
    const storeCatalog = storeRes?.data;
    setStores(Array.isArray(storeCatalog) ? storeCatalog : storeCatalog?.items || []);
    const warehouseCatalog = warehouseRes?.data;
    setWarehouses(Array.isArray(warehouseCatalog) ? warehouseCatalog : warehouseCatalog?.items || []);
    const link = linkRes?.data || null;
    setBookingLink(link);
    setBookings(Array.isArray(bookingRes?.data) ? bookingRes.data : []);
    setDeliveryZones(Array.isArray(zoneRes?.data) ? zoneRes.data : []);
    setOnlineOrders(onlineRes?.data && typeof onlineRes.data === 'object' ? onlineRes.data : { open: false });
    setFloorPlaces(Array.isArray(floorRes?.data) ? floorRes.data : []);
    setKitchenSound({ on: soundRes?.data?.on === true });
    setClock({
      open: Array.isArray(clockRes?.data?.open) ? clockRes.data.open : [],
      mine_open: clockRes?.data?.mine_open === true,
    });
    setSoldOut(Array.isArray(soldOutRes?.data?.items) ? soldOutRes.data.items : []);
    const servicePercent = Number(serviceRes?.data?.percent || 0);
    setServiceDraft(servicePercent > 0 ? String(servicePercent) : '');
    if (link?.hostname) {
      setLinkForm({ hostname: link.hostname, link_kind: link.link_kind || 'existing' });
    }
  }

  useEffect(() => {
    setPageOrigin(window.location.origin);
    getMe()
      .then((me) => {
        const ok = moduleEnabledForTenant(me.data?.enabled_modules, me.data?.industry, 'restaurant');
        setRestaurantDesk(ok);
        if (!ok) {
          setError('Restaurant is not available for this company.');
          return;
        }
        return refresh();
      })
      .catch((err) => setError(err.message || 'Could not load restaurant'));
  }, []);

  useEffect(() => {
    if (!restaurantDesk) return undefined;
    const timer = window.setInterval(() => {
      void refresh();
    }, 15000);
    return () => window.clearInterval(timer);
  }, [restaurantDesk]);

  useEffect(() => {
    const ids = kitchen.map((row) => String(row.id));
    const previous = heardTickets.current;
    heardTickets.current = new Set(ids);
    if (!kitchenSound.on || previous === null) return;
    if (!ids.some((id) => !previous.has(id))) return;
    const ctx = kitchenAudio.current;
    if (!ctx || ctx.state !== 'running') return;
    playKitchenChime(ctx);
  }, [kitchen, kitchenSound.on]);

  async function createTable(event: FormEvent) {
    event.preventDefault();
    setError('');
    try {
      await api('/restaurant/tables', {
        method: 'POST',
        body: JSON.stringify({
          code: tableForm.code.trim(),
          name: tableForm.name.trim(),
          seats: Number(tableForm.seats) || 2,
          store_id: tableForm.store_id.trim() || null,
          room: tableForm.room.trim() || null,
        }),
      });
      setTableForm({ code: '', name: '', seats: '2', store_id: '', room: '' });
      setMessage('Table saved');
      await refresh();
    } catch (err: any) {
      setError(err.message || 'Could not save table');
    }
  }

  function tableEdit(row: Row) {
    return tableEdits[row.id] || {
      code: String(row.code || ''),
      name: String(row.name || ''),
      seats: String(row.seats || 2),
    };
  }

  function bookingDraft(row: Row, draft?: { guest_name: string; phone: string; party_size: string; booked_for: string; notes: string }) {
    return draft || {
      guest_name: String(row.guest_name ?? ''),
      phone: String(row.phone ?? ''),
      party_size: String(row.party_size ?? '2'),
      booked_for: String(row.booked_for || '').slice(0, 16),
      notes: String(row.notes ?? ''),
    };
  }

  /** One Save for a booking. Only changed fields go up, so an unchanged past time is not re-checked. */
  async function saveWholeBooking(row: Row) {
    setError('');
    const draft = bookingDraft(row, leftoverBookings[row.id]);
    const body: Record<string, unknown> = {};
    if (draft.guest_name.trim() !== String(row.guest_name ?? '')) body.guest_name = draft.guest_name.trim();
    if (draft.phone.trim() !== String(row.phone ?? '')) body.phone = draft.phone.trim();
    if ((Number(draft.party_size) || 1) !== Number(row.party_size)) body.party_size = Number(draft.party_size) || 1;
    if (draft.booked_for && draft.booked_for !== String(row.booked_for || '').slice(0, 16)) body.booked_for = draft.booked_for;
    if (draft.notes.trim() !== String(row.notes ?? '')) body.notes = draft.notes.trim() || null;
    const turnText = (leftoverTurns[row.id] ?? (row.turn == null ? '' : String(row.turn))).trim();
    if ((turnText ? Number(turnText) : null) !== (row.turn ?? null)) body.turn = turnText ? Number(turnText) : null;
    try {
      if (Object.keys(body).length) {
        await api(`/restaurant/bookings/${row.id}`, { method: 'PATCH', body: JSON.stringify(body) });
      }
      setMessage(`Saved leftover booking ${row.booking_number}`);
      setEditingBooking('');
      await refresh();
    } catch (err: any) {
      setError(err.message || 'Could not save the booking');
    }
  }

  /** One Save for everything on a table: code, name, seats, store and room. */
  async function saveWholeTable(row: Row) {
    const edit = tableEdit(row);
    setError('');
    try {
      await api(`/restaurant/tables/${row.id}`, {
        method: 'PATCH',
        body: JSON.stringify({
          code: edit.code.trim(),
          name: edit.name.trim(),
          seats: Number(edit.seats) || 2,
          store_id: (leftoverTableStores[row.id] ?? row.store_id ?? '').trim() || null,
          room: (leftoverTableRooms[row.id] ?? row.room ?? '').trim() || null,
        }),
      });
      setMessage(`Saved ${row.code}`);
      setEditingTable('');
      await refresh();
    } catch (err: any) {
      setError(err.message || 'Could not save the table');
    }
  }


  async function retireTable(row: Row) {
    setError('');
    try {
      await api(`/restaurant/tables/${row.id}/retire`, { method: 'POST', body: JSON.stringify({}) });
      setTableEdits((current) => {
        const next = { ...current };
        delete next[row.id];
        return next;
      });
      setMessage(`Retired ${row.code}`);
      setEditingTable('');
      setRetiringTable('');
      await refresh();
    } catch (err: any) {
      setError(err.message || 'Could not retire the table');
    }
  }

  function addOrderLine() {
    const productId = orderForm.product_id.trim();
    if (!productId) {
      setError('Choose a menu item first');
      return;
    }
    setError('');
    setOrderLines((current) => [
      ...current,
      { product_id: productId, quantity: orderForm.quantity.trim() || '1', modifier_ids: selectedModifiers, course: orderForm.course || 'main', note: orderForm.item_note.trim(), hold: orderForm.item_hold, seat: orderForm.item_seat.trim(), spice: orderForm.item_spice, doneness: orderForm.item_doneness },
    ]);
    setSelectedModifiers([]);
    setOrderForm((current) => ({ ...current, product_id: '', quantity: '1', course: 'main', item_note: '', item_hold: false, item_seat: '', item_spice: '', item_doneness: '' }));
  }

  async function addLeftoverItem(row: Row) {
    const productId = (leftoverNewItems[row.id] || '').trim();
    if (!productId) {
      setError('Choose a menu item first');
      return;
    }
    setError('');
    try {
      await api(`/restaurant/orders/${row.id}`, {
        method: 'PATCH',
        body: JSON.stringify({
          lines: [{
            product_id: productId,
            quantity: (leftoverNewQuantities[row.id] || '').trim() || '1',
            modifier_ids: leftoverNewModifiers[row.id] || [],
          }],
        }),
      });
      setLeftoverNewItems((current) => ({ ...current, [row.id]: '' }));
      setLeftoverNewQuantities((current) => ({ ...current, [row.id]: '1' }));
      setLeftoverNewModifiers((current) => ({ ...current, [row.id]: [] }));
      setMessage(`Saved leftover item on ${row.order_number}`);
      await refresh();
    } catch (err: any) {
      setError(err.message || 'Could not add the leftover item');
    }
  }

  async function removeLeftoverItem(row: Row, item: Row) {
    if (!item.id) {
      setError('Choose a leftover item first');
      return;
    }
    setError('');
    try {
      await api(`/restaurant/orders/${row.id}`, {
        method: 'PATCH',
        body: JSON.stringify({ remove_line_ids: [item.id] }),
      });
      setMessage(`Removed leftover ${item.name} on ${row.order_number}`);
      await refresh();
    } catch (err: any) {
      setError(err.message || 'Could not remove the leftover item');
    }
  }

  function leftoverRecipeLines(row: Row): Row[] {
    const removed = new Set(leftoverRecipeRemoved[row.id] || []);
    const saved = (row.lines || []).filter((line: Row) => line.ingredient_id && !removed.has(String(line.ingredient_id)));
    const savedIds = new Set(saved.map((line: Row) => String(line.ingredient_id)));
    const added = (leftoverRecipeAdded[row.id] || [])
      .filter((line) => line.ingredient_id && !removed.has(line.ingredient_id) && !savedIds.has(line.ingredient_id))
      .map((line) => ({
        ingredient_id: line.ingredient_id,
        quantity: leftoverRecipeLineQuantities[`${row.id}:${line.ingredient_id}`] ?? line.quantity,
        name: products.find((item) => item.id === line.ingredient_id)?.name || 'Ingredient',
      }));
    return [...saved, ...added];
  }

  function addLeftoverRecipeIngredient(row: Row) {
    const ingredientId = (leftoverRecipeIngredient[row.id] || '').trim();
    if (!ingredientId) {
      setError('Choose an ingredient first');
      return;
    }
    if (leftoverRecipeLines(row).some((line) => line.ingredient_id === ingredientId)) {
      setError('That ingredient is already on the recipe');
      return;
    }
    setError('');
    setLeftoverRecipeRemoved((current) => ({
      ...current,
      [row.id]: (current[row.id] || []).filter((id) => id !== ingredientId),
    }));
    setLeftoverRecipeAdded((current) => ({
      ...current,
      [row.id]: [
        ...(current[row.id] || []).filter((line) => line.ingredient_id !== ingredientId),
        { ingredient_id: ingredientId, quantity: '1' },
      ],
    }));
    setLeftoverRecipeIngredient((current) => ({ ...current, [row.id]: '' }));
  }

  function removeLeftoverRecipeLine(row: Row, line: Row) {
    setLeftoverRecipeAdded((current) => ({
      ...current,
      [row.id]: (current[row.id] || []).filter((item) => item.ingredient_id !== line.ingredient_id),
    }));
    setLeftoverRecipeRemoved((current) => ({
      ...current,
      [row.id]: Array.from(new Set([...(current[row.id] || []), String(line.ingredient_id)])),
    }));
  }

  async function saveLeftoverRecipe(row: Row) {
    setError('');
    const visible = leftoverRecipeLines(row);
    if (!visible.length) {
      setError('Recipe needs at least one ingredient');
      return;
    }
    try {
      const leftoverName = leftoverRecipeNames[row.id] ?? row.name;
      const leftoverLines = visible.map((line: Row) => ({
        ingredient_id: line.ingredient_id,
        quantity: leftoverRecipeLineQuantities[`${row.id}:${line.ingredient_id}`] ?? String(line.quantity ?? '0'),
      }));
      await api(`/restaurant/recipes/${row.id}`, {
        method: 'PATCH',
        body: JSON.stringify({
          name: leftoverName,
          lines: leftoverLines,
        }),
      });
      setMessage(`Saved leftover recipe ${leftoverName}`);
      setLeftoverRecipeAdded((current) => ({ ...current, [row.id]: [] }));
      setLeftoverRecipeRemoved((current) => ({ ...current, [row.id]: [] }));
      await refresh();
    } catch (err: any) {
      setError(err.message || 'Could not save the leftover recipe');
    }
  }

  async function saveLeftoverCookTime(row: Row) {
    setError('');
    const text = (leftoverCookTimes[row.id] ?? (row.cook_time ? String(row.cook_time) : '')).trim();
    try {
      await api(`/restaurant/recipes/${row.id}`, {
        method: 'PATCH',
        body: JSON.stringify({ cook_time: text ? Number(text) : null }),
      });
      setMessage(`Saved leftover cook time on ${row.name}`);
      await refresh();
    } catch (err: any) {
      setError(err.message || 'Could not save the cook time');
    }
  }

  async function saveLeftoverServings(row: Row) {
    setError('');
    const text = (leftoverServings[row.id] ?? (row.servings ? String(row.servings) : '')).trim();
    try {
      await api(`/restaurant/recipes/${row.id}`, {
        method: 'PATCH',
        body: JSON.stringify({ servings: text ? Number(text) : null }),
      });
      setMessage(`Saved leftover servings on ${row.name}`);
      await refresh();
    } catch (err: any) {
      setError(err.message || 'Could not save the servings');
    }
  }

  function leftoverExtraIds(item: Row): string[] {
    return leftoverLineModifiers[item.id] ?? (Array.isArray(item.modifier_ids) ? item.modifier_ids : []);
  }

  async function saveLeftoverExtras(row: Row, item: Row) {
    setError('');
    try {
      await api(`/restaurant/orders/${row.id}`, {
        method: 'PATCH',
        body: JSON.stringify({
          line_modifiers: [{ line_id: item.id, modifier_ids: leftoverExtraIds(item) }],
        }),
      });
      setMessage(`Saved leftover extras on ${row.order_number}`);
      await refresh();
    } catch (err: any) {
      setError(err.message || 'Could not save the leftover extras');
    }
  }

  async function saveLeftoverStation(row: Row, item: Row) {
    setError('');
    try {
      await api(`/restaurant/orders/${row.id}`, {
        method: 'PATCH',
        body: JSON.stringify({
          line_stations: [{
            line_id: item.id,
            station: leftoverLineStations[item.id] ?? item.station ?? 'kitchen',
          }],
        }),
      });
      setMessage(`Saved leftover station on ${row.order_number}`);
      await refresh();
    } catch (err: any) {
      setError(err.message || 'Could not save the leftover station');
    }
  }

  async function saveLeftoverCourse(row: Row, item: Row) {
    setError('');
    try {
      await api(`/restaurant/orders/${row.id}`, {
        method: 'PATCH',
        body: JSON.stringify({
          line_courses: [{
            line_id: item.id,
            course: leftoverLineCourses[item.id] ?? item.course ?? 'main',
          }],
        }),
      });
      setMessage(`Saved leftover course on ${row.order_number}`);
      await refresh();
    } catch (err: any) {
      setError(err.message || 'Could not save the leftover course');
    }
  }

  async function saveLeftoverItemNote(row: Row, item: Row) {
    setError('');
    const note = (leftoverLineNotes[item.id] ?? item.note ?? '').trim();
    try {
      await api(`/restaurant/orders/${row.id}`, {
        method: 'PATCH',
        body: JSON.stringify({
          line_notes: [{
            line_id: item.id,
            note: note || null,
          }],
        }),
      });
      setMessage(`Saved leftover item note on ${row.order_number}`);
      await refresh();
    } catch (err: any) {
      setError(err.message || 'Could not save the item note');
    }
  }

  async function saveLeftoverSeat(row: Row, item: Row) {
    setError('');
    const text = (leftoverLineSeats[item.id] ?? (item.seat != null ? String(item.seat) : '')).trim();
    const number = Number(text);
    try {
      await api(`/restaurant/orders/${row.id}`, {
        method: 'PATCH',
        body: JSON.stringify({
          line_seats: [{
            line_id: item.id,
            seat: text && Number.isInteger(number) ? number : text || null,
          }],
        }),
      });
      setMessage(`Saved leftover seat on ${row.order_number}`);
      await refresh();
    } catch (err: any) {
      setError(err.message || 'Could not save the seat');
    }
  }

  async function saveLeftoverSpice(row: Row, item: Row) {
    setError('');
    const spice = (leftoverLineSpices[item.id] ?? item.spice ?? '').trim();
    try {
      await api(`/restaurant/orders/${row.id}`, {
        method: 'PATCH',
        body: JSON.stringify({
          line_spices: [{
            line_id: item.id,
            spice: spice || null,
          }],
        }),
      });
      setMessage(`Saved leftover spice on ${row.order_number}`);
      await refresh();
    } catch (err: any) {
      setError(err.message || 'Could not save the spice');
    }
  }

  async function saveLeftoverDoneness(row: Row, item: Row) {
    setError('');
    const doneness = (leftoverLineDoneness[item.id] ?? item.doneness ?? '').trim();
    try {
      await api(`/restaurant/orders/${row.id}`, {
        method: 'PATCH',
        body: JSON.stringify({
          line_doneness: [{
            line_id: item.id,
            doneness: doneness || null,
          }],
        }),
      });
      setMessage(`Saved leftover doneness on ${row.order_number}`);
      await refresh();
    } catch (err: any) {
      setError(err.message || 'Could not save the doneness');
    }
  }

  async function saveLeftoverHold(row: Row, item: Row, hold: boolean) {
    setError('');
    try {
      await api(`/restaurant/orders/${row.id}`, {
        method: 'PATCH',
        body: JSON.stringify({
          line_holds: [{ line_id: item.id, hold }],
        }),
      });
      setMessage(hold ? `Held ${item.name} on ${row.order_number}` : `Cleared hold on ${row.order_number}`);
      await refresh();
    } catch (err: any) {
      setError(err.message || 'Could not save the hold');
    }
  }

  async function saveLeftoverPrice(row: Row, item: Row) {
    setError('');
    try {
      await api(`/restaurant/orders/${row.id}`, {
        method: 'PATCH',
        body: JSON.stringify({
          line_prices: [{
            line_id: item.id,
            unit_price: leftoverLinePrices[item.id] ?? String(item.unit_price ?? '0'),
          }],
        }),
      });
      setMessage(`Saved leftover price on ${row.order_number}`);
      await refresh();
    } catch (err: any) {
      setError(err.message || 'Could not save the leftover price');
    }
  }

  async function saveLeftoverQuantity(row: Row, item: Row) {
    setError('');
    try {
      await api(`/restaurant/orders/${row.id}`, {
        method: 'PATCH',
        body: JSON.stringify({
          line_quantities: [{
            line_id: item.id,
            quantity: leftoverLineQuantities[item.id] ?? String(item.quantity ?? '1'),
          }],
        }),
      });
      setMessage(`Saved leftover quantity on ${row.order_number}`);
      await refresh();
    } catch (err: any) {
      setError(err.message || 'Could not save the leftover quantity');
    }
  }

  async function saveLeftoverService(row: Row) {
    setError('');
    const mode = leftoverServiceModes[row.id] ?? row.service_mode ?? 'takeaway';
    const body: Record<string, string | null> = { service_mode: mode };
    if (mode === 'dine_in') body.table_id = (leftoverServiceTables[row.id] ?? row.table_id ?? '').trim() || null;
    if (mode === 'delivery') {
      const address = (leftoverDeliveryAddresses[row.id] ?? row.delivery_address ?? '').trim();
      if (address) body.delivery_address = address;
      const zone = (leftoverDeliveryZones[row.id] ?? row.delivery_zone ?? '').trim();
      if (zone) body.delivery_zone = zone;
    }
    try {
      await api(`/restaurant/orders/${row.id}`, {
        method: 'PATCH',
        body: JSON.stringify(body),
      });
      setMessage(`Saved leftover service on ${row.order_number}`);
      await refresh();
    } catch (err: any) {
      setError(err.message || 'Could not save the leftover service');
    }
  }

  async function saveLeftoverStore(row: Row) {
    setError('');
    try {
      await api(`/restaurant/orders/${row.id}`, {
        method: 'PATCH',
        body: JSON.stringify({
          store_id: (leftoverOrderStores[row.id] ?? row.store_id ?? '').trim() || null,
        }),
      });
      setMessage(`Saved leftover store on ${row.order_number}`);
      await refresh();
    } catch (err: any) {
      setError(err.message || 'Could not save the leftover store');
    }
  }

  async function saveLeftoverPayment(row: Row) {
    setError('');
    try {
      await api(`/restaurant/orders/${row.id}`, {
        method: 'PATCH',
        body: JSON.stringify({
          payment_method: leftoverPaymentMethods[row.id] ?? row.payment_method ?? 'cash',
        }),
      });
      setMessage(`Saved leftover payment on ${row.order_number}`);
      await refresh();
    } catch (err: any) {
      setError(err.message || 'Could not save the leftover payment');
    }
  }

  async function saveLeftoverCustomer(row: Row) {
    setError('');
    try {
      await api(`/restaurant/orders/${row.id}`, {
        method: 'PATCH',
        body: JSON.stringify({
          customer_name: (leftoverCustomerNames[row.id] ?? row.customer_name ?? '').trim() || null,
        }),
      });
      setMessage(`Saved leftover customer on ${row.order_number}`);
      await refresh();
    } catch (err: any) {
      setError(err.message || 'Could not save the leftover customer');
    }
  }

  async function saveDeliveryZones(names: string[]) {
    setError('');
    try {
      const saved = await api('/restaurant/delivery-zones', {
        method: 'PUT',
        body: JSON.stringify({ names }),
      });
      setDeliveryZones(Array.isArray(saved?.data) ? saved.data : names);
      setZoneName('');
      setMessage('Delivery zones saved');
    } catch (err: any) {
      setError(err.message || 'Could not save the delivery zones');
    }
  }

  async function saveSoldOut(productIds: string[]) {
    setError('');
    try {
      const saved = await api('/restaurant/sold-out', {
        method: 'PUT',
        body: JSON.stringify({ product_ids: productIds }),
      });
      setSoldOut(Array.isArray(saved?.data?.items) ? saved.data.items : []);
      setSoldOutId('');
      setMessage(productIds.length ? 'Sold out saved' : 'Sold out cleared');
    } catch (err: any) {
      setError(err.message || 'Could not save sold out');
    }
  }

  async function saveOnlineOrders(open: boolean) {
    setError('');
    try {
      const saved = await api('/restaurant/online-orders', {
        method: 'PUT',
        body: JSON.stringify({ open }),
      });
      setOnlineOrders(saved?.data || { open });
      setMessage(open ? 'Online food orders are open' : 'Online food orders are closed');
    } catch (err: any) {
      setError(err.message || 'Could not save online food orders');
    }
  }

  function floorSpot(row: Row, index: number) {
    if (floorDraft[row.id]) return floorDraft[row.id];
    const saved = floorPlaces.find((place) => place.table_id === row.id);
    if (saved) return { x: Number(saved.x) || 0, y: Number(saved.y) || 0 };
    return defaultFloorSpot(index);
  }

  function startFloorDrag(event: ReactPointerEvent<HTMLButtonElement>, row: Row, index: number) {
    const map = floorMapRef.current;
    if (!map) return;
    event.preventDefault();
    const rect = map.getBoundingClientRect();
    const origin = floorSpot(row, index);
    const startX = event.clientX;
    const startY = event.clientY;
    let moved = false;
    let latest = origin;
    const target = event.currentTarget;
    target.setPointerCapture(event.pointerId);
    function move(ev: PointerEvent) {
      const dx = ((ev.clientX - startX) / Math.max(rect.width, 1)) * 100;
      const dy = ((ev.clientY - startY) / Math.max(rect.height, 1)) * 100;
      if (Math.abs(dx) + Math.abs(dy) > 2) moved = true;
      latest = {
        x: Math.max(0, Math.min(76, Math.round(origin.x + dx))),
        y: Math.max(0, Math.min(76, Math.round(origin.y + dy))),
      };
      setFloorDraft((current) => ({ ...current, [row.id]: latest }));
    }
    function up() {
      target.removeEventListener('pointermove', move);
      target.removeEventListener('pointerup', up);
      if (!moved) return;
      const places = tables.map((item, itemIndex) => {
        const place = item.id === row.id ? latest : floorSpot(item, itemIndex);
        return { table_id: item.id, x: place.x, y: place.y };
      });
      void saveFloorPlaces(places);
    }
    target.addEventListener('pointermove', move);
    target.addEventListener('pointerup', up);
  }

  async function saveFloorPlaces(places: Array<{ table_id: string; x: number; y: number }>) {
    setError('');
    try {
      const saved = await api('/restaurant/floor-places', {
        method: 'PUT',
        body: JSON.stringify({ places }),
      });
      setFloorPlaces(Array.isArray(saved?.data) ? saved.data : places);
      setFloorDraft({});
      setMessage('Floor saved');
    } catch (err: any) {
      setError(err.message || 'Could not save the floor');
    }
  }

  async function saveKitchenSound(on: boolean) {
    setError('');
    try {
      if (on) {
        const Ctx = window.AudioContext;
        if (Ctx) {
          const ctx = kitchenAudio.current || new Ctx();
          kitchenAudio.current = ctx;
          await ctx.resume();
        }
      }
      const saved = await api('/restaurant/kitchen-sound', {
        method: 'PUT',
        body: JSON.stringify({ on }),
      });
      setKitchenSound({ on: saved?.data?.on === true });
      setMessage(on ? 'Kitchen sound is on' : 'Kitchen sound is off');
    } catch (err: any) {
      setError(err.message || 'Could not save the kitchen sound');
    }
  }

  async function punchClock(path: 'in' | 'out') {
    setError('');
    try {
      const saved = await api(`/restaurant/clock/${path}`, {
        method: 'POST',
        body: JSON.stringify({}),
      });
      setClock({
        open: Array.isArray(saved?.data?.open) ? saved.data.open : [],
        mine_open: saved?.data?.mine_open === true,
      });
      setMessage(path === 'in' ? 'Clocked in' : 'Clocked out');
    } catch (err: any) {
      setError(err.message || 'Could not save the clock');
    }
  }

  async function saveLeftoverDelivery(row: Row) {
    setError('');
    try {
      await api(`/restaurant/orders/${row.id}`, {
        method: 'PATCH',
        body: JSON.stringify({
          delivery_address: (leftoverDeliveryAddresses[row.id] ?? row.delivery_address ?? '').trim(),
          delivery_zone: (leftoverDeliveryZones[row.id] ?? row.delivery_zone ?? '').trim() || null,
        }),
      });
      setMessage(`Saved leftover delivery address on ${row.order_number}`);
      await refresh();
    } catch (err: any) {
      setError(err.message || 'Could not save the leftover delivery address');
    }
  }

  async function saveLeftoverNotes(row: Row) {
    setError('');
    try {
      await api(`/restaurant/orders/${row.id}`, {
        method: 'PATCH',
        body: JSON.stringify({ notes: (leftoverNotes[row.id] ?? row.notes ?? '').trim() || null }),
      });
      setMessage(`Saved leftover notes on ${row.order_number}`);
      await refresh();
    } catch (err: any) {
      setError(err.message || 'Could not save leftover notes');
    }
  }

  async function saveLeftoverCovers(row: Row) {
    setError('');
    const raw = (leftoverCovers[row.id] ?? (row.covers ? String(row.covers) : '')).trim();
    const covers = raw ? Number(raw) : null;
    if (raw && (!Number.isInteger(covers) || (covers as number) < 1 || (covers as number) > 40)) {
      setError('Covers must be from 1 to 40.');
      return;
    }
    try {
      await api(`/restaurant/orders/${row.id}`, {
        method: 'PATCH',
        body: JSON.stringify({ covers }),
      });
      setMessage(`Saved leftover covers on ${row.order_number}`);
      await refresh();
    } catch (err: any) {
      setError(err.message || 'Could not save the covers');
    }
  }

  async function saveLeftoverAllergy(row: Row) {
    setError('');
    const allergy = (leftoverAllergies[row.id] ?? row.allergy ?? '').trim();
    try {
      await api(`/restaurant/orders/${row.id}`, {
        method: 'PATCH',
        body: JSON.stringify({ allergy: allergy || null }),
      });
      setMessage(`Saved leftover allergy on ${row.order_number}`);
      await refresh();
    } catch (err: any) {
      setError(err.message || 'Could not save the allergy');
    }
  }

  async function saveLeftoverAllergen(row: Row) {
    setError('');
    const allergen = (leftoverAllergens[row.id] ?? row.allergen ?? '').trim();
    try {
      await api(`/restaurant/orders/${row.id}`, {
        method: 'PATCH',
        body: JSON.stringify({ allergen: allergen || null }),
      });
      setMessage(`Saved leftover allergen on ${row.order_number}`);
      await refresh();
    } catch (err: any) {
      setError(err.message || 'Could not save the allergen');
    }
  }

  async function saveLeftoverOccasion(row: Row) {
    setError('');
    const occasion = (leftoverOccasions[row.id] ?? row.occasion ?? '').trim();
    try {
      await api(`/restaurant/orders/${row.id}`, {
        method: 'PATCH',
        body: JSON.stringify({ occasion: occasion || null }),
      });
      setMessage(`Saved leftover occasion on ${row.order_number}`);
      await refresh();
    } catch (err: any) {
      setError(err.message || 'Could not save the occasion');
    }
  }

  async function saveLeftoverPhone(row: Row) {
    setError('');
    const phone = (leftoverPhones[row.id] ?? row.phone ?? '').trim();
    try {
      await api(`/restaurant/orders/${row.id}`, {
        method: 'PATCH',
        body: JSON.stringify({ phone: phone || null }),
      });
      setMessage(`Saved leftover phone on ${row.order_number}`);
      await refresh();
    } catch (err: any) {
      setError(err.message || 'Could not save the phone');
    }
  }

  async function saveLeftoverPager(row: Row) {
    setError('');
    const text = (leftoverPagers[row.id] ?? (row.pager != null ? String(row.pager) : '')).trim();
    const number = Number(text);
    try {
      await api(`/restaurant/orders/${row.id}`, {
        method: 'PATCH',
        body: JSON.stringify({
          pager: text && Number.isInteger(number) ? number : text || null,
        }),
      });
      setMessage(`Saved leftover pager on ${row.order_number}`);
      await refresh();
    } catch (err: any) {
      setError(err.message || 'Could not save the pager');
    }
  }

  async function saveLeftoverReadyBy(row: Row) {
    setError('');
    const readyBy = (leftoverReadyBy[row.id] ?? row.ready_by ?? '').trim();
    try {
      await api(`/restaurant/orders/${row.id}`, {
        method: 'PATCH',
        body: JSON.stringify({ ready_by: readyBy || null }),
      });
      setMessage(`Saved leftover ready by on ${row.order_number}`);
      await refresh();
    } catch (err: any) {
      setError(err.message || 'Could not save the ready time');
    }
  }

  async function saveLeftoverQuotedWait(row: Row) {
    setError('');
    const text = (leftoverQuotedWaits[row.id] ?? (row.quoted_wait == null ? '' : String(row.quoted_wait))).trim();
    const number = text ? Number(text) : null;
    try {
      await api(`/restaurant/orders/${row.id}`, {
        method: 'PATCH',
        body: JSON.stringify({ quoted_wait: text ? (Number.isInteger(number) ? number : text) : null }),
      });
      setMessage(`Saved leftover quoted wait on ${row.order_number}`);
      await refresh();
    } catch (err: any) {
      setError(err.message || 'Could not save the quoted wait');
    }
  }

  async function saveLeftoverFireAt(row: Row) {
    setError('');
    const fireAt = (leftoverFireAt[row.id] ?? row.fire_at ?? '').trim();
    try {
      await api(`/restaurant/orders/${row.id}`, {
        method: 'PATCH',
        body: JSON.stringify({ fire_at: fireAt || null }),
      });
      setMessage(`Saved leftover fire at on ${row.order_number}`);
      await refresh();
    } catch (err: any) {
      setError(err.message || 'Could not save the fire time');
    }
  }

  async function saveLeftoverPackaging(row: Row) {
    setError('');
    const packaging = (leftoverPackaging[row.id] ?? row.packaging ?? '').trim();
    try {
      await api(`/restaurant/orders/${row.id}`, {
        method: 'PATCH',
        body: JSON.stringify({ packaging: packaging || null }),
      });
      setMessage(`Saved leftover packaging on ${row.order_number}`);
      await refresh();
    } catch (err: any) {
      setError(err.message || 'Could not save the packaging');
    }
  }

  async function saveRush(row: Row, rush: boolean) {
    setError('');
    try {
      await api(`/restaurant/orders/${row.id}`, {
        method: 'PATCH',
        body: JSON.stringify({ rush }),
      });
      setMessage(rush ? `Marked ${row.order_number} rush` : `Cleared rush on ${row.order_number}`);
      await refresh();
    } catch (err: any) {
      setError(err.message || 'Could not save the rush');
    }
  }

  async function saveBill(row: Row, billAsked: boolean) {
    setError('');
    try {
      await api(`/restaurant/orders/${row.id}`, {
        method: 'PATCH',
        body: JSON.stringify({ bill_asked: billAsked }),
      });
      setMessage(billAsked ? `Marked bill on ${row.order_number}` : `Cleared bill on ${row.order_number}`);
      await refresh();
    } catch (err: any) {
      setError(err.message || 'Could not save the bill');
    }
  }

  async function saveArrived(row: Row, arrived: boolean) {
    setError('');
    try {
      await api(`/restaurant/orders/${row.id}`, {
        method: 'PATCH',
        body: JSON.stringify({ guest_arrived: arrived }),
      });
      setMessage(arrived ? `Marked arrived on ${row.order_number}` : `Cleared arrived on ${row.order_number}`);
      await refresh();
    } catch (err: any) {
      setError(err.message || 'Could not save the arrival');
    }
  }

  async function saveCutlery(row: Row, cutlery: boolean) {
    setError('');
    try {
      await api(`/restaurant/orders/${row.id}`, {
        method: 'PATCH',
        body: JSON.stringify({ cutlery }),
      });
      setMessage(cutlery ? `Marked cutlery on ${row.order_number}` : `Cleared cutlery on ${row.order_number}`);
      await refresh();
    } catch (err: any) {
      setError(err.message || 'Could not save the cutlery');
    }
  }

  async function saveHighChair(row: Row, highChair: boolean) {
    setError('');
    try {
      await api(`/restaurant/orders/${row.id}`, {
        method: 'PATCH',
        body: JSON.stringify({ high_chair: highChair }),
      });
      setMessage(highChair ? `Marked high chair on ${row.order_number}` : `Cleared high chair on ${row.order_number}`);
      await refresh();
    } catch (err: any) {
      setError(err.message || 'Could not save the high chair');
    }
  }

  async function saveLeftoverDiet(row: Row) {
    setError('');
    const diet = (leftoverDiets[row.id] ?? row.diet ?? '').trim();
    try {
      await api(`/restaurant/orders/${row.id}`, {
        method: 'PATCH',
        body: JSON.stringify({ diet: diet || null }),
      });
      setMessage(`Saved leftover diet on ${row.order_number}`);
      await refresh();
    } catch (err: any) {
      setError(err.message || 'Could not save the diet');
    }
  }

  async function saveLeftoverSource(row: Row) {
    setError('');
    const guestSource = (leftoverSources[row.id] ?? row.guest_source ?? '').trim();
    try {
      await api(`/restaurant/orders/${row.id}`, {
        method: 'PATCH',
        body: JSON.stringify({ guest_source: guestSource || null }),
      });
      setMessage(`Saved leftover source on ${row.order_number}`);
      await refresh();
    } catch (err: any) {
      setError(err.message || 'Could not save the source');
    }
  }

  async function saveLeftoverVehicle(row: Row) {
    setError('');
    const vehicle = (leftoverVehicles[row.id] ?? row.vehicle ?? '').trim();
    try {
      await api(`/restaurant/orders/${row.id}`, {
        method: 'PATCH',
        body: JSON.stringify({ vehicle: vehicle || null }),
      });
      setMessage(`Saved leftover vehicle on ${row.order_number}`);
      await refresh();
    } catch (err: any) {
      setError(err.message || 'Could not save the vehicle');
    }
  }

  async function saveLeftoverBay(row: Row) {
    setError('');
    const text = (leftoverBays[row.id] ?? (row.bay == null ? '' : String(row.bay))).trim();
    const number = text ? Number(text) : null;
    try {
      await api(`/restaurant/orders/${row.id}`, {
        method: 'PATCH',
        body: JSON.stringify({ bay: text ? (Number.isInteger(number) ? number : text) : null }),
      });
      setMessage(`Saved leftover bay on ${row.order_number}`);
      await refresh();
    } catch (err: any) {
      setError(err.message || 'Could not save the bay');
    }
  }

  async function saveLeftoverHandoff(row: Row) {
    setError('');
    const handoff = (leftoverHandoffs[row.id] ?? row.handoff ?? '').trim();
    try {
      await api(`/restaurant/orders/${row.id}`, {
        method: 'PATCH',
        body: JSON.stringify({ handoff: handoff || null }),
      });
      setMessage(`Saved leftover handoff on ${row.order_number}`);
      await refresh();
    } catch (err: any) {
      setError(err.message || 'Could not save the handoff');
    }
  }

  async function saveLeftoverGuestEmail(row: Row) {
    setError('');
    const guestEmail = (leftoverGuestEmails[row.id] ?? row.guest_email ?? '').trim();
    try {
      await api(`/restaurant/orders/${row.id}`, {
        method: 'PATCH',
        body: JSON.stringify({ guest_email: guestEmail || null }),
      });
      setMessage(`Saved leftover email on ${row.order_number}`);
      await refresh();
    } catch (err: any) {
      setError(err.message || 'Could not save the email');
    }
  }

  async function saveLeftoverReceipt(row: Row) {
    setError('');
    const receipt = (leftoverReceipts[row.id] ?? row.receipt ?? '').trim();
    try {
      await api(`/restaurant/orders/${row.id}`, {
        method: 'PATCH',
        body: JSON.stringify({ receipt: receipt || null }),
      });
      setMessage(`Saved leftover receipt on ${row.order_number}`);
      await refresh();
    } catch (err: any) {
      setError(err.message || 'Could not save the receipt');
    }
  }

  function modifierName(id: string) {
    for (const group of modifierGroups) {
      const match = (group.modifiers || []).find((row: Row) => row.id === id);
      if (match) return match.name;
    }
    return 'Extra';
  }

  async function saveExtra(event: FormEvent) {
    event.preventDefault();
    setError('');
    const groupName = extraForm.group.trim();
    const extraName = extraForm.name.trim();
    if (!groupName) {
      setError('Enter an extra group');
      return;
    }
    if (!extraName) {
      setError('Enter an extra name');
      return;
    }
    try {
      const existing = modifierGroups.find((group) => String(group.name || '').toLowerCase() === groupName.toLowerCase());
      const group = existing || (await api('/restaurant/modifier-groups', {
        method: 'POST',
        body: JSON.stringify({ name: groupName }),
      }))?.data;
      await api(`/restaurant/modifier-groups/${group.id}/modifiers`, {
        method: 'POST',
        body: JSON.stringify({ name: extraName, price: extraForm.price.trim() || '0' }),
      });
      setExtraForm({ group: '', name: '', price: '0' });
      setMessage('Extra saved');
      await refresh();
    } catch (err: any) {
      setError(err.message || 'Could not save the extra');
    }
  }

  async function createOrder(event: FormEvent) {
    event.preventDefault();
    setError('');
    const linesToSave = [...orderLines];
    if (orderForm.product_id.trim()) {
      linesToSave.push({
        product_id: orderForm.product_id.trim(),
        quantity: orderForm.quantity.trim() || '1',
        modifier_ids: selectedModifiers,
        course: orderForm.course || 'main',
        note: orderForm.item_note.trim(),
        hold: orderForm.item_hold,
        seat: orderForm.item_seat.trim(),
        spice: orderForm.item_spice,
        doneness: orderForm.item_doneness,
      });
    }
    if (orderForm.service_mode === 'delivery' && !orderForm.delivery_address.trim()) {
      setError('Enter a delivery address');
      return;
    }
    if (orderForm.service_mode === 'delivery' && deliveryZones.length && !orderForm.delivery_zone.trim()) {
      setError('Choose a delivery zone.');
      return;
    }
    if (orderForm.service_mode === 'dine_in' && tables.length && !orderForm.table_id.trim()) {
      setError('Choose a table first.');
      return;
    }
    if (!linesToSave.length) {
      setError('Add at least one menu item');
      return;
    }
    try {
      await api('/restaurant/orders', {
        method: 'POST',
        body: JSON.stringify({
          service_mode: orderForm.service_mode,
          payment_method: orderForm.payment_method,
          store_id: orderForm.store_id.trim() || null,
          table_id: orderForm.service_mode === 'dine_in' && orderForm.table_id.trim() ? orderForm.table_id.trim() : null,
          customer_name: orderForm.customer_name.trim() || null,
          delivery_address: orderForm.service_mode === 'delivery' ? orderForm.delivery_address.trim() : null,
          delivery_zone: orderForm.service_mode === 'delivery' ? orderForm.delivery_zone.trim() || null : null,
          notes: orderForm.notes.trim() || null,
          covers: orderForm.covers.trim() ? Number(orderForm.covers.trim()) : null,
          allergy: orderForm.allergy.trim() || null,
          allergen: orderForm.allergen.trim() || null,
          occasion: orderForm.occasion.trim() || null,
          phone: orderForm.phone.trim() || null,
          guest_email: orderForm.guest_email.trim() || null,
          receipt: orderForm.receipt.trim() || null,
          pager: (() => {
            const text = orderForm.pager.trim();
            if (!text) return null;
            const number = Number(text);
            return Number.isInteger(number) ? number : text;
          })(),
          ready_by: orderForm.ready_by.trim() || null,
          quoted_wait: (() => {
            const text = orderForm.quoted_wait.trim();
            if (!text) return null;
            const number = Number(text);
            return Number.isInteger(number) ? number : text;
          })(),
          fire_at: orderForm.fire_at.trim() || null,
          packaging: orderForm.packaging.trim() || null,
          rush: orderForm.rush ? true : null,
          bill_asked: orderForm.bill_asked ? true : null,
          guest_arrived: orderForm.guest_arrived ? true : null,
          cutlery: orderForm.cutlery ? true : null,
          high_chair: orderForm.high_chair ? true : null,
          diet: orderForm.diet.trim() || null,
          guest_source: orderForm.guest_source.trim() || null,
          vehicle: orderForm.vehicle.trim() || null,
          bay: (() => {
            const text = orderForm.bay.trim();
            if (!text) return null;
            const number = Number(text);
            return Number.isInteger(number) ? number : text;
          })(),
          handoff: orderForm.handoff.trim() || null,
          lines: linesToSave.map((line) => ({
            product_id: line.product_id,
            quantity: line.quantity,
            modifier_ids: line.modifier_ids,
            course: line.course,
            note: (line.note || '').trim() || null,
            hold: line.hold ? true : null,
            seat: (() => {
              const text = (line.seat || '').trim();
              if (!text) return null;
              const number = Number(text);
              return Number.isInteger(number) ? number : text;
            })(),
            spice: (line.spice || '').trim() || null,
            doneness: (line.doneness || '').trim() || null,
          })),
        }),
      });
      setOrderLines([]);
      setSelectedModifiers([]);
      setOrderForm((current) => ({ ...current, product_id: '', quantity: '1', course: 'main', item_note: '', item_hold: false, item_seat: '', item_spice: '', item_doneness: '', covers: '', allergy: '', allergen: '', occasion: '', phone: '', guest_email: '', receipt: '', pager: '', ready_by: '', quoted_wait: '', fire_at: '', packaging: '', diet: '', guest_source: '', vehicle: '', bay: '', handoff: '', rush: false, bill_asked: false, guest_arrived: false, cutlery: false, high_chair: false, customer_name: '', delivery_address: '', delivery_zone: '', notes: '' }));
      setMessage('Order saved');
      await refresh();
    } catch (err: any) {
      setError(err.message || 'Could not save order');
    }
  }

  async function act(orderId: string, action: string) {
    setError('');
    try {
      await api(`/restaurant/orders/${orderId}/${action}`, { method: 'POST' });
      setMessage(`Order ${action}`);
      await refresh();
    } catch (err: any) {
      setError(err.message || `Could not ${action} order`);
    }
  }

  function menuLabel(row: Row) {
    const sold = soldOut.some((item) => item.id === row.id) ? ' · Sold out' : '';
    return `${row.name} · ${orderWord(row.prep_station || 'kitchen')}${sold}`;
  }

  async function saveStation(event: FormEvent) {
    event.preventDefault();
    setError('');
    const productId = stationForm.product_id.trim();
    if (!productId) {
      setError('Choose a menu item first');
      return;
    }
    try {
      await api(`/products/${productId}`, {
        method: 'PATCH',
        body: JSON.stringify({ prep_station: stationForm.station }),
      });
      setMessage(stationForm.station === 'bar' ? 'Menu item goes to the bar' : 'Menu item goes to the kitchen');
      await refresh();
    } catch (err: any) {
      setError(err.message || 'Could not save the station');
    }
  }

  async function saveWaste(event: FormEvent) {
    event.preventDefault();
    setError('');
    if (!wasteForm.product_id.trim()) {
      setError('Choose an ingredient first.');
      return;
    }
    try {
      await api('/restaurant/waste', {
        method: 'POST',
        body: JSON.stringify({
          product_id: wasteForm.product_id.trim(),
          quantity: wasteForm.quantity.trim() || '1',
          reason: wasteForm.reason,
          notes: wasteForm.notes.trim() || null,
          warehouse_id: wasteForm.warehouse_id.trim() || null,
        }),
      });
      setWasteForm({ product_id: '', quantity: '1', reason: 'spoilage', notes: '', warehouse_id: '' });
      setMessage('Waste recorded');
      await refresh();
    } catch (err: any) {
      setError(err.message || 'Could not record waste');
    }
  }

  function addRecipeLine() {
    const ingredientId = recipeForm.ingredient_id.trim();
    if (!ingredientId) {
      setError('Choose an ingredient first');
      return;
    }
    setError('');
    setRecipeLines((current) => [...current, { ingredient_id: ingredientId, quantity: recipeForm.quantity.trim() || '1' }]);
    setRecipeForm((current) => ({ ...current, ingredient_id: '', quantity: '1' }));
  }

  async function createRecipe(event: FormEvent) {
    event.preventDefault();
    setError('');
    const linesToSave = [...recipeLines];
    if (recipeForm.ingredient_id.trim()) {
      linesToSave.push({ ingredient_id: recipeForm.ingredient_id.trim(), quantity: recipeForm.quantity.trim() || '1' });
    }
    if (!linesToSave.length) {
      setError('Add at least one ingredient');
      return;
    }
    try {
      await api('/restaurant/recipes', {
        method: 'POST',
        body: JSON.stringify({
          product_id: recipeForm.product_id,
          name: recipeForm.name.trim() || 'Recipe',
          lines: linesToSave,
          cook_time: recipeForm.cook_time.trim() ? Number(recipeForm.cook_time) : null,
          servings: recipeForm.servings.trim() ? Number(recipeForm.servings) : null,
        }),
      });
      setRecipeLines([]);
      setRecipeForm((current) => ({ ...current, product_id: '', ingredient_id: '', quantity: '1', name: '', cook_time: '', servings: '' }));
      setMessage('Recipe saved');
      await refresh();
    } catch (err: any) {
      setError(err.message || 'Could not save recipe');
    }
  }

  function scanFacts(facts: Array<[string, string | number | null | undefined]>) {
    return facts
      .filter(([, value]) => value !== null && value !== undefined && String(value) !== '')
      .map(([label, value]) => (
        <span className="rest-order-fact" key={label}>
          <span>{label}</span>
          {value}
        </span>
      ));
  }

  function stationQueue(station: string, title: string, empty: string, label: string) {
    const rows = kitchen.filter((row) => (row.station || 'kitchen') === station);
    return (
      <section className="card" aria-label={label}>
        <h2>{title}</h2>
        <ul className="rest-scan-list">
          {rows.map((row) => (
            <li key={row.id} className="rest-order">
              <div className="rest-order-head">
                <strong>{row.order_number || 'Order'}</strong>
                {scanFacts([
                  ['Service', row.service_mode ? orderWord(row.service_mode) : ''],
                  ['From', onlineLabel(row)],
                  ['Guest', row.customer_name],
                  ['Covers', row.covers ? String(row.covers) : ''],
                  ['Allergy', row.allergy || ''],
                  ['Allergen', row.allergen ? orderWord(row.allergen) : ''],
                  ['Occasion', row.occasion || ''],
                  ['Phone', row.phone || ''],
                  ['Email', row.guest_email || ''],
                  ['Receipt', row.receipt ? orderWord(row.receipt) : ''],
                  ['Pager', row.pager ? String(row.pager) : ''],
                  ['Ready by', row.ready_by || ''],
                  ['Quoted wait', row.quoted_wait ? `${row.quoted_wait} min` : ''],
                  ['Fire at', row.fire_at || ''],
                  ['Packaging', row.packaging ? orderWord(row.packaging) : ''],
                  ['Rush', row.rush ? 'Rush' : ''],
                  ['Bill', row.bill_asked ? 'Bill asked' : ''],
                  ['Arrived', row.guest_arrived ? 'Arrived' : ''],
                  ['Cutlery', row.cutlery ? 'Cutlery' : ''],
                  ['High chair', row.high_chair ? 'High chair' : ''],
                  ['Diet', row.diet ? orderWord(row.diet) : ''],
                  ['Source', row.guest_source ? orderWord(row.guest_source) : ''],
                  ['Vehicle', row.vehicle || ''],
                  ['Bay', row.bay ? String(row.bay) : ''],
                  ['Handoff', row.handoff ? orderWord(row.handoff) : ''],
                  ['Server', row.server || ''],
                  ['Opened', row.opened_at ? formatDateTime(row.opened_at) : ''],
                  ['Table', row.table_code],
                  ['Deliver to', row.delivery_address],
                  ['Zone', row.delivery_zone],
                  ['Status', orderWord(row.status)],
                ])}
              </div>
              {row.notes ? <p className="muted">{row.notes}</p> : null}
              <ul className="rest-scan-list">
                {(row.items || []).map((item: Row, index: number) => (
                  <li key={`${row.id}-${index}`} className="rest-order-line">
                    <div className="rest-order-head">
                      {scanFacts([
                        ['Item', item.name],
                        ['Qty', item.quantity],
                        ['Extras', item.modifiers?.length ? item.modifiers.join(', ') : ''],
                        ['Course', orderWord(item.course || 'main')],
                        ['Note', item.note || ''],
                        ['Hold', item.hold ? 'Held' : ''],
                        ['Seat', item.seat ? String(item.seat) : ''],
                        ['Spice', item.spice ? orderWord(item.spice) : ''],
                        ['Doneness', item.doneness ? orderWord(item.doneness) : ''],
                        ['Prep', orderWord(item.prep_status || 'queued')],
                      ])}
                    </div>
                    {item.prep_status === 'ready' ? null : (
                      <div className="rest-order-actions">
                        {item.prep_status === 'preparing' ? null : (
                          <button
                            type="button"
                            aria-label={`Start ${item.name} on ${row.order_number}`}
                            onClick={async () => {
                              setError('');
                              try {
                                await api(`/restaurant/kitchen/lines/${item.id}/start`, {
                                  method: 'POST',
                                  body: JSON.stringify({}),
                                });
                                setMessage(`${item.name} is being prepared`);
                                await refresh();
                              } catch (err: any) {
                                setError(err.message || 'Could not start this item');
                              }
                            }}
                          >
                            Start
                          </button>
                        )}
                        <button
                          type="button"
                          aria-label={`Mark ${item.name} ready on ${row.order_number}`}
                          onClick={async () => {
                            setError('');
                            try {
                              await api(`/restaurant/kitchen/lines/${item.id}/ready`, {
                                method: 'POST',
                                body: JSON.stringify({}),
                              });
                              setMessage(`${item.name} is ready`);
                              await refresh();
                            } catch (err: any) {
                              setError(err.message || 'Could not mark the item ready');
                            }
                          }}
                        >
                          Ready
                        </button>
                      </div>
                    )}
                  </li>
                ))}
              </ul>
            </li>
          ))}
          {!rows.length && <li className="muted">{empty}</li>}
        </ul>
      </section>
    );
  }

  const waitingBookings = bookings.filter((row) => row.status === 'requested');
  const openOrders = orders.filter((row) => ['open', 'sent', 'preparing', 'ready'].includes(String(row.status)));
  const liveTickets = kitchen.filter((row) => ['queued', 'preparing'].includes(String(row.status)));
  const readyTickets = kitchen.filter((row) => row.status === 'ready');
  const heldTables = tables.filter((row) => row.status === 'held');
  const lowIngredients = products.filter((row) => Number(row.reorder_level || 0) > 0 && Number(row.stock_qty || 0) <= Number(row.reorder_level || 0));
  const recipeMenuIds = new Set(recipes.map((row) => row.product_id));
  const recipeIngredientIds = new Set(
    recipes.flatMap((row) => (row.lines || []).map((line: Row) => line.ingredient_id))
  );
  const menuItems = products.filter((row) => {
    if (recipeIngredientIds.has(row.id) && !recipeMenuIds.has(row.id)) return false;
    const station = String(row.prep_station || '');
    return recipeMenuIds.has(row.id) || station === 'kitchen' || station === 'bar';
  });
  const ingredientItems = products.filter((row) => !menuItems.some((item) => item.id === row.id));
  const menuWithoutRecipe = products.filter((row) => {
    if (recipeMenuIds.has(row.id) || recipeIngredientIds.has(row.id)) return false;
    const station = String(row.prep_station || '');
    return station === 'kitchen' || station === 'bar';
  });
  const dashAlerts = [
    waitingBookings.length
      ? {
          href: '/restaurant?tab=booking',
          message:
            waitingBookings.length === 1
              ? '1 booking request is waiting.'
              : `${waitingBookings.length} booking requests are waiting.`,
        }
      : null,
    readyTickets.length
      ? {
          href: '/restaurant?tab=kitchen',
          message:
            readyTickets.length === 1
              ? '1 ticket is ready to serve.'
              : `${readyTickets.length} tickets are ready to serve.`,
        }
      : null,
    heldTables.length
      ? {
          href: '/restaurant?tab=tables',
          message: heldTables.length === 1 ? '1 table is held.' : `${heldTables.length} tables are held.`,
        }
      : null,
    lowIngredients.length
      ? {
          href: '/inventory?tab=lowstock',
          message:
            lowIngredients.length === 1
              ? '1 ingredient is low.'
              : `${lowIngredients.length} ingredients are low.`,
        }
      : null,
    bookingLink?.hostname
      ? null
      : {
          href: '/restaurant?tab=booking',
          message: 'Booking link is not saved.',
        },
    tillSession
      ? null
      : {
          href: '/restaurant/till',
          message: 'No restaurant shift is open.',
        },
    menuWithoutRecipe.length
      ? {
          href: '/restaurant?tab=recipes',
          message:
            menuWithoutRecipe.length === 1
              ? '1 menu item has no recipe.'
              : `${menuWithoutRecipe.length} menu items have no recipe.`,
        }
      : null,
  ].filter(Boolean) as { href: string; message: string }[];

  return (
    <main className="page">
      {restaurantDesk && tab === 'dashboard' ? (
        <DashboardGreeting desk="Restaurant dashboard" />
      ) : restaurantDesk ? (
        <PageHeader
          title={(TAB_HEADINGS[tab] || TAB_HEADINGS.orders)[0]}
          subtitle={(TAB_HEADINGS[tab] || TAB_HEADINGS.orders)[1]}
        />
      ) : null}
      {error && <p role="alert">{error}</p>}
      {message && <p>{message}</p>}
      {restaurantDesk && tab === 'dashboard' && !summary && !error ? (
        <p className="empty">Loading restaurant totals…</p>
      ) : null}
      {restaurantDesk && tab === 'dashboard' && summary && (
        <section className="rdesk rd-dash" aria-label="Restaurant dashboard">
          <div className="rd-actionbar" aria-label="Restaurant quick desks">
            <Link className="rd-action primary" href="/restaurant/till">
              <span className="ico" aria-hidden>＋</span>
              <span>
                <strong>New order</strong>
                <small>Open the restaurant till</small>
              </span>
            </Link>
            <Link className="rd-action" href="/restaurant/orders">
              <span className="ico" aria-hidden>☰</span>
              <span>
                <strong>Orders</strong>
                <small>{openOrders.length} on the floor</small>
              </span>
            </Link>
            <Link className="rd-action" href="/restaurant?tab=kitchen">
              <span className="ico" aria-hidden>♨</span>
              <span>
                <strong>Kitchen</strong>
                <small>{liveTickets.length} cooking · {readyTickets.length} ready</small>
              </span>
            </Link>
            <Link className="rd-action" href="/restaurant?tab=tables">
              <span className="ico" aria-hidden>▦</span>
              <span>
                <strong>Tables and floor</strong>
                <small>{tableFloor(summary.tables)}</small>
              </span>
            </Link>
            <Link className="rd-action" href="/restaurant?tab=booking">
              <span className="ico" aria-hidden>☏</span>
              <span>
                <strong>Website and booking</strong>
                <small>{waitingBookings.length} waiting</small>
              </span>
            </Link>
            <Link className="rd-action" href="/restaurant/bills">
              <span className="ico" aria-hidden>₵</span>
              <span>
                <strong>Bills</strong>
                <small>Today&apos;s takings</small>
              </span>
            </Link>
          </div>
          <p className="rd-sr">Open a restaurant desk.</p>

          <div className="rd-kpis">
            <div className="rd-kpi hero">
              <span>Sales today</span>
              <strong>{formatMoney(summary.sales_today)}</strong>
              <small>
                Table bills {formatMoney(Number(summary.table_sales_today || 0))} · Restaurant till{' '}
                {formatMoney(Number(summary.till_sales_today || 0))}
              </small>
            </div>
            <div className="rd-kpi">
              <span>Open orders</span>
              <strong>{summary.open_orders ?? openOrders.length}</strong>
            </div>
            <div className="rd-kpi">
              <span>Kitchen and bar</span>
              <strong>{liveTickets.length + readyTickets.length}</strong>
              <small>
                Kitchen {summary.kitchen_queue ?? summary.kitchen_backlog ?? 0} · Bar {summary.bar_queue ?? 0}
              </small>
            </div>
            <div className="rd-kpi">
              <span>Tables</span>
              <strong>
                {Object.values(summary.tables || {}).reduce((total: number, count) => total + Number(count || 0), 0)}
              </strong>
              <small>{tableFloor(summary.tables)}</small>
            </div>
            <div className="rd-kpi">
              <span>Booking requests</span>
              <strong>{waitingBookings.length}</strong>
            </div>
          </div>

          {dashAlerts.length ? (
            <ul className="rd-alerts" aria-label="Restaurant operational alerts">
              {dashAlerts.map((row) => (
                <li key={row.message}>
                  <Link href={row.href}>
                    <span className="dot" aria-hidden />
                    {row.message}
                    <span className="go" aria-hidden>→</span>
                  </Link>
                </li>
              ))}
            </ul>
          ) : (
            <p className="rd-allgood">No operational alerts.</p>
          )}

          <div className="rd-split">
            <div className="rd-panel">
              <div className="rd-panel-head">
                <h3>Open orders</h3>
                <Link href="/restaurant/orders">See all →</Link>
              </div>
              <ul className="rd-mini" aria-label="Restaurant open orders">
                {openOrders.slice(0, 6).map((row) => (
                  <li key={row.id}>
                    <Link href="/restaurant/orders">
                      <strong>{deskWhere(row, tables)}</strong>
                      <small>
                        {row.order_number} · {orderWord(row.service_mode)}
                        {onlineLabel(row) === 'Online' ? ' · Online' : ''}
                      </small>
                      <span className={`rd-pill ${row.status === 'ready' ? '' : row.status === 'open' ? 'grey' : 'wait'}`}>
                        {orderWord(row.status)}
                      </span>
                      <b>{formatMoney(row.total_amount)}</b>
                    </Link>
                  </li>
                ))}
                {!openOrders.length && <li className="rd-mini-empty">No open orders.</li>}
              </ul>
            </div>
            <div className="rd-panel">
              <div className="rd-panel-head">
                <h3>Kitchen and bar</h3>
                <Link href="/restaurant?tab=kitchen">Open kitchen →</Link>
              </div>
              <ul className="rd-mini" aria-label="Restaurant live tickets">
                {[...readyTickets, ...liveTickets].slice(0, 6).map((row) => (
                  <li key={row.id}>
                    <Link href="/restaurant?tab=kitchen">
                      <strong>{row.order_number || 'Order'}</strong>
                      <small>{orderWord(row.station || 'kitchen')}</small>
                      <span className={`rd-pill ${row.status === 'ready' ? '' : 'wait'}`}>{orderWord(row.status)}</span>
                      <b>{(row.items || []).length} items</b>
                    </Link>
                  </li>
                ))}
                {!liveTickets.length && !readyTickets.length && (
                  <li className="rd-mini-empty">No tickets in the kitchen or at the bar.</li>
                )}
              </ul>
            </div>
          </div>

          <details className="rd-howto">
            <summary>How these numbers are worked out</summary>
            <p>
              Company dashboard profit uses the ingredient cost. A menu item with no recipe uses its own cost.
              A restaurant till return comes off Sales today. The original receipt stays on the till report.
              A restaurant till return comes off Sales today for the store on the original receipt.
              A restaurant till return comes off company dashboard profit without the tax. Sales today keeps the tax.
              A completed restaurant bill includes its service charge in company dashboard profit.
              A restaurant till discount comes off company dashboard profit. Top dishes stay at the menu amount.
            </p>
          </details>
        </section>
      )}
      {restaurantDesk && tab === 'tables' && (
        <section className="rdesk rd-tables" aria-label="Restaurant tables and floor">
          <div className="rd-head">
            <div className="rd-legend" aria-label="Table status">
              {(['available', 'occupied', 'reserved', 'held'] as const).map((status) => (
                <span key={status} className={`rd-legend-item is-${status}`}>
                  <span className="sw" aria-hidden />
                  {orderWord(status)} <b>{tables.filter((row) => (row.status || 'available') === status).length}</b>
                </span>
              ))}
            </div>
            <div className="rd-head-actions">
              <button
                type="button"
                className="rd-primary"
                aria-label="Add a table"
                onClick={() => {
                  setAddingTable((open) => !open);
                  setEditingTable('');
                }}
              >
                {addingTable ? 'Close' : '+ Add table'}
              </button>
            </div>
          </div>

          {addingTable ? (
            <form className="rd-panel rd-form-grid" onSubmit={async (event) => {
              await createTable(event);
              setAddingTable(false);
            }}>
              <h3>New table</h3>
              <label>
                <span>Code</span>
                <input aria-label="Restaurant table code" placeholder="T9" value={tableForm.code} onChange={(e) => setTableForm({ ...tableForm, code: e.target.value })} required />
              </label>
              <label>
                <span>Name</span>
                <input aria-label="Restaurant table name" placeholder="Window 1" value={tableForm.name} onChange={(e) => setTableForm({ ...tableForm, name: e.target.value })} required />
              </label>
              <label>
                <span>Seats</span>
                <input aria-label="Restaurant table seats" inputMode="numeric" value={tableForm.seats} onChange={(e) => setTableForm({ ...tableForm, seats: e.target.value })} />
              </label>
              <label>
                <span>Store</span>
                <select aria-label="Restaurant table store" value={tableForm.store_id} onChange={(e) => setTableForm({ ...tableForm, store_id: e.target.value })}>
                  <option value="">No store</option>
                  {stores.filter((row) => row.is_active !== false).map((row) => (
                    <option key={row.id} value={row.id}>{row.code} · {row.name}</option>
                  ))}
                </select>
              </label>
              <label>
                <span>Room</span>
                <select aria-label="Restaurant table room" value={tableForm.room} onChange={(e) => setTableForm({ ...tableForm, room: e.target.value })}>
                  <option value="">No room</option>
                  <option value="dining">Dining</option>
                  <option value="patio">Patio</option>
                  <option value="private">Private</option>
                </select>
              </label>
              <div className="rd-form-actions">
                <button type="submit" className="rd-primary" aria-label="Save restaurant table">Save table</button>
              </div>
            </form>
          ) : null}

          <div className="rd-panel">
            <div className="rd-panel-head">
              <h3>Floor</h3>
              <span className="rd-hint">Drag a table to place it on the floor. Double-tap it to edit.</span>
            </div>
            <div className="rest-floor-map rd-floor" aria-label="Restaurant floor map" ref={floorMapRef}>
              {tables.map((row, index) => {
                const spot = floorSpot(row, index);
                const bill = openOrders.find((order) => order.table_id === row.id);
                return (
                  <button
                    key={row.id}
                    type="button"
                    className={`rest-floor-spot rd-spot is-${bill ? 'occupied' : row.status || 'available'}${Number(row.seats || 0) > 4 ? ' big' : ''}${editingTable === row.id ? ' on' : ''}`}
                    style={{ left: `${spot.x}%`, top: `${spot.y}%` }}
                    aria-label={`Place table ${row.code} on the floor`}
                    onPointerDown={(event) => startFloorDrag(event, row, index)}
                    onDoubleClick={() => {
                      setEditingTable(row.id);
                      setAddingTable(false);
                    }}
                  >
                    <strong>{row.code}</strong>
                    <span>{bill ? formatMoney(bill.total_amount) : Number(row.seats || 0) === 1 ? '1 seat' : `${row.seats} seats`}</span>
                  </button>
                );
              })}
            </div>
          </div>

          <ul className="rest-floor rd-table-list" aria-label="Restaurant floor">
            {tables.map((row) => {
              const bill = openOrders.find((order) => order.table_id === row.id);
              const editing = editingTable === row.id;
              return (
                <li key={row.id} className={`rd-table-card is-${bill ? 'occupied' : row.status || 'available'}${editing ? ' editing' : ''}`}>
                  <div className="rd-table-top">
                    <span className="rd-table-code">{row.code}</span>
                    <div className="rd-table-what">
                      <strong>{row.name}</strong>
                      <small>
                        {Number(row.seats || 0) === 1 ? '1 seat' : `${row.seats} seats`} · {row.room ? orderWord(row.room) : 'No room.'}
                      </small>
                    </div>
                    <span className={`rd-pill ${bill || row.status === 'occupied' ? 'wait' : row.status === 'available' ? '' : 'grey'}`}>
                      {bill ? `Open bill ${formatMoney(bill.total_amount)}` : orderWord(row.status)}
                    </span>
                  </div>
                  {editing ? (
                    <>
                      <div className="rest-floor-fields rd-form-grid">
                        <label>
                          <span>Code</span>
                          <input
                            aria-label={`Leftover table code ${row.code}`}
                            value={tableEdit(row).code}
                            onChange={(e) => setTableEdits((current) => ({ ...current, [row.id]: { ...tableEdit(row), code: e.target.value } }))}
                          />
                        </label>
                        <label>
                          <span>Name</span>
                          <input
                            aria-label={`Edit table ${row.code} name`}
                            value={tableEdit(row).name}
                            onChange={(e) => setTableEdits((current) => ({ ...current, [row.id]: { ...tableEdit(row), name: e.target.value } }))}
                          />
                        </label>
                        <label>
                          <span>Seats</span>
                          <input
                            aria-label={`Edit table ${row.code} seats`}
                            inputMode="numeric"
                            value={tableEdit(row).seats}
                            onChange={(e) => setTableEdits((current) => ({ ...current, [row.id]: { ...tableEdit(row), seats: e.target.value } }))}
                          />
                        </label>
                        <label>
                          <span>Store</span>
                          <select
                            aria-label={`Leftover table store ${row.code}`}
                            value={leftoverTableStores[row.id] ?? row.store_id ?? ''}
                            onChange={(e) => setLeftoverTableStores((current) => ({ ...current, [row.id]: e.target.value }))}
                          >
                            <option value="">No store</option>
                            {stores.filter((store) => store.is_active !== false).map((store) => (
                              <option key={store.id} value={store.id}>{store.code} · {store.name}</option>
                            ))}
                          </select>
                        </label>
                        <label>
                          <span>Room</span>
                          <select
                            aria-label={`Leftover table room ${row.code}`}
                            value={leftoverTableRooms[row.id] ?? row.room ?? ''}
                            onChange={(e) => setLeftoverTableRooms((current) => ({ ...current, [row.id]: e.target.value }))}
                          >
                            <option value="">No room</option>
                            <option value="dining">Dining</option>
                            <option value="patio">Patio</option>
                            <option value="private">Private</option>
                          </select>
                        </label>
                      </div>
                      {retiringTable === row.id ? (
                        <div className="rd-confirm" role="alert">
                          Retire {row.code}? It leaves the floor and the till. Past bills stay.
                          <div>
                            <button type="button" onClick={() => setRetiringTable('')}>Keep it</button>
                            <button type="button" className="rd-danger" aria-label={`Retire table ${row.code}`} onClick={() => retireTable(row)}>
                              Yes, retire
                            </button>
                          </div>
                        </div>
                      ) : null}
                      <div className="rest-floor-actions rd-row-actions">
                        <button type="button" className="rd-primary" aria-label={`Save table ${row.code}`} onClick={() => saveWholeTable(row)}>
                          Save
                        </button>
                        <button type="button" onClick={() => setEditingTable('')}>Cancel</button>
                        {row.status === 'available' && !bill ? (
                          <button type="button" className="rd-danger right" aria-label={`Ask to retire table ${row.code}`} onClick={() => setRetiringTable(row.id)}>
                            Retire table
                          </button>
                        ) : null}
                      </div>
                    </>
                  ) : (
                    <div className="rest-floor-actions rd-row-actions">
                      {bill ? (
                        <button
                          type="button"
                          className="rd-primary"
                          aria-label={`Open bill on table ${row.code}`}
                          onClick={() => (window.location.href = `/restaurant/till?order=${encodeURIComponent(bill.id)}`)}
                        >
                          Open bill
                        </button>
                      ) : row.status === 'available' ? (
                        <button
                          type="button"
                          className="rd-go"
                          aria-label={`Seat guests at table ${row.code}`}
                          onClick={() => (window.location.href = '/restaurant/till')}
                        >
                          Take order
                        </button>
                      ) : null}
                      {row.status === 'available' && !bill ? (
                        <button
                          type="button"
                          aria-label={`Hold table ${row.code}`}
                          onClick={async () => {
                            setError('');
                            try {
                              await api(`/restaurant/tables/${row.id}/hold`, { method: 'POST', body: JSON.stringify({}) });
                              setMessage(`Held ${row.code}`);
                              await refresh();
                            } catch (err: any) {
                              setError(err.message || 'Could not hold the table');
                            }
                          }}
                        >
                          Hold
                        </button>
                      ) : row.status === 'held' ? (
                        <button
                          type="button"
                          aria-label={`Release table ${row.code}`}
                          onClick={async () => {
                            setError('');
                            try {
                              await api(`/restaurant/tables/${row.id}/release`, { method: 'POST', body: JSON.stringify({}) });
                              setMessage(`Released ${row.code}`);
                              await refresh();
                            } catch (err: any) {
                              setError(err.message || 'Could not release the table');
                            }
                          }}
                        >
                          Release
                        </button>
                      ) : null}
                      <button
                        type="button"
                        className="right"
                        aria-label={`Edit table ${row.code}`}
                        onClick={() => {
                          setEditingTable(row.id);
                          setAddingTable(false);
                          setRetiringTable('');
                        }}
                      >
                        Edit
                      </button>
                    </div>
                  )}
                </li>
              );
            })}
            {!tables.length && <li className="rd-mini-empty">No tables yet. Add your first table above.</li>}
          </ul>
        </section>
      )}
      {restaurantDesk && tab === 'booking' && (
        <section className="rdesk rd-booking" aria-label="Online booking">
          {(() => {
            // One public website: the menu, food and drink orders (pickup or delivery) and table booking.
            const sitePath = String(
              (bookingLink?.open && bookingLink.path) ||
                onlineOrders.path ||
                (bookingLink?.path ? String(bookingLink.path).replace('/book/', '/order/') : ''),
            );
            const live = Boolean(onlineOrders.open || bookingLink?.open);
            const siteUrl = sitePath ? `${pageOrigin || ''}${sitePath}` : '';
            return (
              <div className="rd-site" aria-label="Your restaurant website">
                <div className="rd-site-main">
                  <span className={`rd-pill ${live ? '' : 'grey'}`}>{live ? 'Live' : 'Not published'}</span>
                  <h3>Your restaurant website</h3>
                  <p>
                    Guests see your menu, order food and drinks for pickup or delivery, follow their order, and book a
                    table. Nothing is charged online: they pay when they collect, on delivery, or at the table.
                  </p>
                  {live && siteUrl ? (
                    <div className="rd-site-link">
                      <input readOnly aria-label="Restaurant website link" value={siteUrl} onFocus={(e) => e.target.select()} />
                      <button
                        type="button"
                        aria-label="Copy website link"
                        onClick={() => {
                          void navigator.clipboard?.writeText(siteUrl).then(() => setMessage('Website link copied'));
                        }}
                      >
                        Copy
                      </button>
                      <a className="rd-btn-link" href={sitePath} target="_blank" rel="noreferrer" aria-label="Open my restaurant website">
                        Open website →
                      </a>
                    </div>
                  ) : (
                    <p className="rd-hint-line">Open orders, or save your domain below, to publish the page.</p>
                  )}
                </div>
                <div className="rd-site-switches">
                  <div className={`rd-switch ${onlineOrders.open ? 'on' : ''}`}>
                    <div>
                      <strong>Food and drink orders</strong>
                      <small>{onlineOrders.open ? 'Guests can order now' : 'Closed'}</small>
                    </div>
                    {onlineOrders.open ? (
                      <button type="button" aria-label="Close online food orders" onClick={() => saveOnlineOrders(false)}>
                        Close orders
                      </button>
                    ) : (
                      <button type="button" className="rd-primary" aria-label="Open online food orders" onClick={() => saveOnlineOrders(true)}>
                        Open orders
                      </button>
                    )}
                  </div>
                  <div className={`rd-switch ${bookingLink?.open ? 'on' : ''}`}>
                    <div>
                      <strong>Table booking</strong>
                      <small>{bookingLink?.open ? `On · ${bookingLink.hostname}` : 'Save your domain below to turn it on'}</small>
                    </div>
                  </div>
                </div>
              </div>
            );
          })()}

          <details className="rd-panel rd-domain" open={!bookingLink?.open}>
            <summary>
              <strong>Your own domain</strong>
              <span>{bookingLink?.hostname ? bookingLink.hostname : 'Not saved yet'}</span>
            </summary>
            <p className="rd-hint-line">
              Record an existing website or a new domain. Guests use the booking link and the request lands here.
              Saving the host does not move DNS or issue a certificate, and the request does not take a payment.
            </p>
            <form
              className="rest-order-form rd-form-grid"
              onSubmit={async (event) => {
                event.preventDefault();
                setError('');
                setMessage('');
                try {
                  const saved = await api('/restaurant/booking-link', {
                    method: 'PUT',
                    body: JSON.stringify({
                      hostname: linkForm.hostname.trim(),
                      link_kind: linkForm.link_kind,
                    }),
                  });
                  setBookingLink(saved?.data || null);
                  setMessage('Booking link saved');
                } catch (err: any) {
                  setError(err.message || 'Could not save the booking link');
                }
              }}
            >
              <label>
                <span>Website or domain</span>
                <input
                  aria-label="Restaurant booking website"
                  value={linkForm.hostname}
                  onChange={(e) => setLinkForm({ ...linkForm, hostname: e.target.value })}
                  placeholder="bistro.example"
                  required
                />
              </label>
              <label>
                <span>Where this host comes from</span>
                <select
                  aria-label="Restaurant booking host kind"
                  value={linkForm.link_kind}
                  onChange={(e) => setLinkForm({ ...linkForm, link_kind: e.target.value })}
                >
                  <option value="existing">Existing website</option>
                  <option value="new">New domain</option>
                </select>
              </label>
              <div className="rd-form-actions">
                <button type="submit" className="rd-primary" aria-label="Save restaurant booking link">Save booking link</button>
              </div>
            </form>
            {bookingLink?.open && bookingLink.path ? (
              <>
                <label className="rd-readonly">
                  <span>Link to put on the website</span>
                  <input
                    readOnly
                    aria-label="Booking link for the website"
                    value={pageOrigin ? `${pageOrigin}${bookingLink.path}` : bookingLink.path}
                  />
                </label>
                <p className="rd-hint-line">
                  Put this link on {bookingLink.hostname}. Guests who open it request a table here. This does not take a payment.
                  {bookingLink.link_kind === 'new'
                    ? ` After ${bookingLink.hostname} points at this ERP, guests can open https://${bookingLink.hostname}/book. Saving the domain does not move DNS.`
                    : ''}
                </p>
              </>
            ) : (
              <p className="rd-hint-line">Save a website or domain before guests can request a table.</p>
            )}
          </details>

          {(() => {
            const now = new Date();
            const startOfDay = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
            const endOfDay = startOfDay + 86400000;
            const when = (row: Row) => new Date(String(row.booked_for || '')).getTime();
            const filters: Array<[string, string, (row: Row) => boolean]> = [
              ['upcoming', 'Coming up', (row) => row.status === 'requested'],
              ['today', 'Today', (row) => when(row) >= startOfDay && when(row) < endOfDay && row.status !== 'cancelled'],
              ['seated', 'Seated now', (row) => row.status === 'seated'],
              ['all', 'All', () => true],
            ];
            const pick = filters.find((f) => f[0] === bookingFilter) || filters[0];
            const shown = bookings
              .filter(pick[2])
              .sort((x, y) => String(x.booked_for || '').localeCompare(String(y.booked_for || '')));
            return (
              <>
                <div className="rd-head">
                  <div>
                    <h2 className="rd-h2">Bookings</h2>
                    <p className="rd-hint-line">
                      Seat names a table when you pick one. Finish frees that table when no open order is using it.
                      Neither one takes a payment.
                    </p>
                  </div>
                  <div className="rd-head-actions">
                    <button
                      type="button"
                      className="rd-primary"
                      aria-label="Add a booking"
                      onClick={() => setAddingBooking((open) => !open)}
                    >
                      {addingBooking ? 'Close' : '+ Add booking'}
                    </button>
                  </div>
                </div>
                <div className="rd-chips" role="tablist" aria-label="Which bookings">
                  {filters.map(([id, label, test]) => (
                    <button
                      key={id}
                      type="button"
                      role="tab"
                      aria-selected={bookingFilter === id}
                      className={bookingFilter === id ? 'on' : ''}
                      onClick={() => setBookingFilter(id)}
                    >
                      {label} <small>{bookings.filter(test).length}</small>
                    </button>
                  ))}
                </div>

                {addingBooking ? (
                  <form
                    className="rest-order-form rd-panel rd-form-grid"
                    onSubmit={async (event) => {
                      event.preventDefault();
                      setError('');
                      setMessage('');
                      try {
                        await api('/restaurant/bookings', {
                          method: 'POST',
                          body: JSON.stringify({
                            guest_name: walkInForm.guest_name.trim(),
                            phone: walkInForm.phone.trim(),
                            party_size: Number(walkInForm.party_size) || 1,
                            booked_for: walkInForm.booked_for.trim(),
                            notes: walkInForm.notes.trim() || null,
                            turn: walkInForm.turn ? Number(walkInForm.turn) : null,
                          }),
                        });
                        setWalkInForm({ guest_name: '', phone: '', party_size: '2', booked_for: '', notes: '', turn: '' });
                        setMessage('Booking requested');
                        setAddingBooking(false);
                        await refresh();
                      } catch (err: any) {
                        setError(err.message || 'Could not save the booking');
                      }
                    }}
                  >
                    <h3>Walk-in or phone request</h3>
                    <p className="rd-hint-line rd-span">Record a guest here. This does not need a booking website and does not take a payment.</p>
                    <label>
                      <span>Guest</span>
                      <input aria-label="Restaurant walk-in guest name" value={walkInForm.guest_name} onChange={(e) => setWalkInForm({ ...walkInForm, guest_name: e.target.value })} required />
                    </label>
                    <label>
                      <span>Phone</span>
                      <input aria-label="Restaurant walk-in guest phone" placeholder="+233241234567" value={walkInForm.phone} onChange={(e) => setWalkInForm({ ...walkInForm, phone: e.target.value })} required />
                    </label>
                    <label>
                      <span>Party</span>
                      <input aria-label="Restaurant walk-in party size" inputMode="numeric" value={walkInForm.party_size} onChange={(e) => setWalkInForm({ ...walkInForm, party_size: e.target.value })} />
                    </label>
                    <label>
                      <span>When</span>
                      <input aria-label="Restaurant walk-in booked for" type="datetime-local" value={walkInForm.booked_for} onChange={(e) => setWalkInForm({ ...walkInForm, booked_for: e.target.value })} required />
                    </label>
                    <label>
                      <span>Turn</span>
                      <select aria-label="Restaurant booking turn" value={walkInForm.turn} onChange={(e) => setWalkInForm({ ...walkInForm, turn: e.target.value })}>
                        <option value="">No turn</option>
                        <option value="60">1 hour</option>
                        <option value="90">90 minutes</option>
                        <option value="120">2 hours</option>
                      </select>
                    </label>
                    <label className="rd-span">
                      <span>Notes</span>
                      <input aria-label="Restaurant walk-in notes" placeholder="Birthday, high chair, window seat…" value={walkInForm.notes} onChange={(e) => setWalkInForm({ ...walkInForm, notes: e.target.value })} />
                    </label>
                    <div className="rd-form-actions">
                      <button type="submit" className="rd-primary" aria-label="Save restaurant walk-in booking">Save walk-in booking</button>
                    </div>
                  </form>
                ) : null}

                <ul className="rest-order-list rd-bookings">
                  {shown.map((row) => {
                    const seatedAt = tables.find((table) => table.id === row.table_id);
                    const openTables = tables.filter(
                      (table) => ['available', 'held'].includes(String(table.status)) && Number(table.seats || 0) >= Number(row.party_size || 0)
                    );
                    const at = new Date(String(row.booked_for || ''));
                    const valid = !Number.isNaN(at.getTime());
                    const [note, preOrder] = String(row.notes || '').split(/(?=Pre-order:)/);
                    const edit = leftoverBookings[row.id];
                    const editing = editingBooking === row.id;
                    return (
                      <li key={row.id} className={`rest-order rd-booking-card is-${row.status}`}>
                        <div className="rd-when">
                          <small>{valid ? at.toLocaleDateString([], { weekday: 'short', day: 'numeric', month: 'short' }) : ''}</small>
                          <strong>{valid ? at.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hourCycle: 'h23' }) : row.booked_for}</strong>
                        </div>
                        <div className="rd-booking-body">
                          <div className="rd-booking-top">
                            <strong>{row.guest_name}</strong>
                            <span className="rd-pill grey">{row.party_size} {Number(row.party_size) === 1 ? 'guest' : 'guests'}</span>
                            <span className={`rd-pill ${row.status === 'requested' ? 'wait' : row.status === 'seated' ? '' : 'grey'}`}>
                              {orderWord(row.status)}
                            </span>
                            {seatedAt ? <span className="rd-pill">Table {seatedAt.code}</span> : null}
                          </div>
                          <small className="rd-booking-meta">
                            {row.booking_number} · <a href={`tel:${row.phone}`}>{row.phone}</a> ·{' '}
                            {row.turn === 60 ? '1 hour' : row.turn === 90 ? '90 minutes' : row.turn === 120 ? '2 hours' : 'No turn.'}
                          </small>
                          {note && note.trim() ? <p className="rd-booking-note">{note.replace(/\.\s*$/, '')}</p> : null}
                          {preOrder ? <p className="rd-booking-pre">{preOrder}</p> : null}

                          {row.status === 'requested' && editing ? (
                            <div className="rest-order-line-fields rd-form-grid">
                              <label>
                                <span>Guest</span>
                                <input
                                  aria-label={`Leftover booking guest ${row.booking_number}`}
                                  value={edit?.guest_name ?? row.guest_name ?? ''}
                                  onChange={(e) => setLeftoverBookings((current) => ({ ...current, [row.id]: { ...bookingDraft(row, current[row.id]), guest_name: e.target.value } }))}
                                />
                              </label>
                              <label>
                                <span>Phone</span>
                                <input
                                  aria-label={`Leftover booking phone ${row.booking_number}`}
                                  value={edit?.phone ?? row.phone ?? ''}
                                  onChange={(e) => setLeftoverBookings((current) => ({ ...current, [row.id]: { ...bookingDraft(row, current[row.id]), phone: e.target.value } }))}
                                />
                              </label>
                              <label>
                                <span>Party</span>
                                <input
                                  aria-label={`Leftover booking party ${row.booking_number}`}
                                  inputMode="numeric"
                                  value={edit?.party_size ?? String(row.party_size ?? '2')}
                                  onChange={(e) => setLeftoverBookings((current) => ({ ...current, [row.id]: { ...bookingDraft(row, current[row.id]), party_size: e.target.value } }))}
                                />
                              </label>
                              <label>
                                <span>When</span>
                                <input
                                  aria-label={`Leftover booking time ${row.booking_number}`}
                                  type="datetime-local"
                                  value={edit?.booked_for ?? String(row.booked_for || '').slice(0, 16)}
                                  onChange={(e) => setLeftoverBookings((current) => ({ ...current, [row.id]: { ...bookingDraft(row, current[row.id]), booked_for: e.target.value } }))}
                                />
                              </label>
                              <label>
                                <span>Turn</span>
                                <select
                                  aria-label={`Leftover booking turn ${row.booking_number}`}
                                  value={leftoverTurns[row.id] ?? (row.turn == null ? '' : String(row.turn))}
                                  onChange={(e) => setLeftoverTurns((current) => ({ ...current, [row.id]: e.target.value }))}
                                >
                                  <option value="">No turn</option>
                                  <option value="60">1 hour</option>
                                  <option value="90">90 minutes</option>
                                  <option value="120">2 hours</option>
                                </select>
                              </label>
                              <label className="rd-span">
                                <span>Notes</span>
                                <input
                                  aria-label={`Leftover booking notes ${row.booking_number}`}
                                  value={edit?.notes ?? row.notes ?? ''}
                                  onChange={(e) => setLeftoverBookings((current) => ({ ...current, [row.id]: { ...bookingDraft(row, current[row.id]), notes: e.target.value } }))}
                                />
                              </label>
                            </div>
                          ) : null}

                          {cancellingBooking === row.id ? (
                            <div className="rd-confirm" role="alert">
                              Cancel {row.guest_name}&apos;s booking? Call them to let them know.
                              <div>
                                <button type="button" onClick={() => setCancellingBooking('')}>Keep it</button>
                                <button
                                  type="button"
                                  className="rd-danger"
                                  aria-label={`Cancel booking ${row.booking_number}`}
                                  onClick={async () => {
                                    setError('');
                                    try {
                                      await api(`/restaurant/bookings/${row.id}/cancel`, { method: 'POST' });
                                      setCancellingBooking('');
                                      await refresh();
                                    } catch (err: any) {
                                      setError(err.message || 'Could not cancel the booking');
                                    }
                                  }}
                                >
                                  Yes, cancel
                                </button>
                              </div>
                            </div>
                          ) : null}

                          {row.status === 'requested' ? (
                            <div className="rest-order-actions rd-row-actions">
                              {editing ? (
                                <>
                                  <button
                                    type="button"
                                    className="rd-primary"
                                    aria-label={`Save leftover booking ${row.booking_number}`}
                                    onClick={() => saveWholeBooking(row)}
                                  >
                                    Save
                                  </button>
                                  <button type="button" onClick={() => setEditingBooking('')}>Close</button>
                                </>
                              ) : (
                                <>
                                  <select
                                    className="rd-seat-pick"
                                    aria-label={`Seat booking ${row.booking_number} at table`}
                                    value={seatTables[row.id] || ''}
                                    onChange={(e) => setSeatTables({ ...seatTables, [row.id]: e.target.value })}
                                  >
                                    <option value="">Pick a table</option>
                                    {openTables.map((table) => (
                                      <option key={table.id} value={table.id}>
                                        {table.code} · {table.seats} seats
                                      </option>
                                    ))}
                                  </select>
                                  <button
                                    type="button"
                                    className="rd-go"
                                    aria-label={`Seat booking ${row.booking_number}`}
                                    onClick={async () => {
                                      setError('');
                                      const tableId = (seatTables[row.id] || '').trim();
                                      try {
                                        await api(`/restaurant/bookings/${row.id}/seat`, {
                                          method: 'POST',
                                          body: JSON.stringify(tableId ? { table_id: tableId } : {}),
                                        });
                                        await refresh();
                                      } catch (err: any) {
                                        setError(err.message || 'Could not seat the booking');
                                      }
                                    }}
                                  >
                                    Seat
                                  </button>
                                  <button type="button" aria-label={`Edit booking ${row.booking_number}`} onClick={() => setEditingBooking(row.id)}>
                                    Edit
                                  </button>
                                  <button type="button" className="rd-danger right" aria-label={`Ask to cancel booking ${row.booking_number}`} onClick={() => setCancellingBooking(row.id)}>
                                    Cancel
                                  </button>
                                </>
                              )}
                            </div>
                          ) : row.status === 'seated' ? (
                            <div className="rest-order-actions rd-row-actions">
                              <button
                                type="button"
                                className="rd-primary"
                                aria-label={`Finish booking ${row.booking_number}`}
                                onClick={async () => {
                                  setError('');
                                  try {
                                    await api(`/restaurant/bookings/${row.id}/finish`, { method: 'POST', body: JSON.stringify({}) });
                                    await refresh();
                                  } catch (err: any) {
                                    setError(err.message || 'Could not finish the booking');
                                  }
                                }}
                              >
                                Finish visit
                              </button>
                              <button type="button" onClick={() => (window.location.href = '/restaurant/till')}>
                                Take order
                              </button>
                            </div>
                          ) : null}
                        </div>
                      </li>
                    );
                  })}
                  {!shown.length && (
                    <li className="rd-mini-empty">{bookings.length ? 'No bookings here.' : 'No booking requests yet.'}</li>
                  )}
                </ul>
              </>
            );
          })()}
        </section>
      )}
      {restaurantDesk && tab === 'orders' && (
        <section className="card">
          <h2>Orders</h2>
          <p className="muted">
            Completing a bill posts the ingredient cost to cost of goods and takes it off inventory. A menu item with no recipe uses its own stock and cost. A refund puts that cost back. A restaurant bill cannot be put on credit. Credit stays on the restaurant till, where a customer can be selected.
          </p>
          <form
            className="rest-order-form"
            onSubmit={async (event) => {
              event.preventDefault();
              setError('');
              const raw = serviceDraft.trim();
              try {
                await api('/restaurant/service-charge', {
                  method: 'PUT',
                  body: JSON.stringify({ percent: raw === '' ? null : Number(raw) }),
                });
                setMessage('Service charge saved');
                await refresh();
              } catch (err: any) {
                setError(err?.message || 'Could not save the service charge');
              }
            }}
          >
            <label>
              <span>Service charge</span>
              <input
                aria-label="Restaurant service charge"
                value={serviceDraft}
                onChange={(e) => setServiceDraft(e.target.value)}
              />
            </label>
            <button type="submit" aria-label="Save restaurant service charge">Save service charge</button>
          </form>
          <form className="rest-order-form" onSubmit={saveExtra}>
            <label>
              <span>Group</span>
              <input aria-label="Restaurant extra group" value={extraForm.group} onChange={(e) => setExtraForm({ ...extraForm, group: e.target.value })} />
            </label>
            <label>
              <span>Name</span>
              <input aria-label="Restaurant extra name" value={extraForm.name} onChange={(e) => setExtraForm({ ...extraForm, name: e.target.value })} />
            </label>
            <label>
              <span>Price</span>
              <input aria-label="Restaurant extra price" value={extraForm.price} onChange={(e) => setExtraForm({ ...extraForm, price: e.target.value })} />
            </label>
            <button type="submit" aria-label="Save restaurant extra">Save extra</button>
          </form>
          {modifierGroups.length ? (
            <ul className="rest-order-list" aria-label="Restaurant extras">
              {modifierGroups.map((group) => (
                <li key={`group-${group.id}`} className="rest-order">
                  <div className="rest-order-head"><strong>{group.name}</strong></div>
                  <div className="rest-order-line-fields">
                  <label>
                    <span>Group</span>
                  <input
                    aria-label={`Leftover extra group name ${group.name}`}
                    value={leftoverExtraGroupNames[group.id] ?? String(group.name ?? '')}
                    onChange={(e) => setLeftoverExtraGroupNames((current) => ({ ...current, [group.id]: e.target.value }))}
                  />
                  </label>
                  </div>
                  <div className="rest-order-actions">
                  <button
                    type="button"
                    aria-label={`Save leftover extra group ${group.name}`}
                    onClick={async () => {
                      setError('');
                      try {
                        await api(`/restaurant/modifier-groups/${group.id}`, {
                          method: 'PATCH',
                          body: JSON.stringify({
                            name: leftoverExtraGroupNames[group.id] ?? group.name,
                          }),
                        });
                        setMessage(`Saved leftover extra group ${leftoverExtraGroupNames[group.id] ?? group.name}`);
                        await refresh();
                      } catch (err: any) {
                        setError(err.message || 'Could not save the leftover extra group');
                      }
                    }}
                  >
                    Save group
                  </button>
                  <button
                    type="button"
                    aria-label={`Retire leftover extra group ${group.name}`}
                    onClick={async () => {
                      setError('');
                      try {
                        await api(`/restaurant/modifier-groups/${group.id}/retire`, { method: 'POST', body: JSON.stringify({}) });
                        setMessage(`Retired leftover extra group ${group.name}`);
                        await refresh();
                      } catch (err: any) {
                        setError(err.message || 'Could not retire the leftover extra group');
                      }
                    }}
                  >
                    Retire group
                  </button>
                  </div>
                </li>
              ))}
              {modifierGroups.flatMap((group) => (group.modifiers || []).map((row: Row) => (
                <li key={row.id} className="rest-order">
                  <div className="rest-order-head">
                    {scanFacts([
                      ['Group', group.name],
                      ['Extra', row.name],
                      ['Price', formatMoney(row.price)],
                    ])}
                  </div>
                  <div className="rest-order-line-fields">
                  <label>
                    <span>Name</span>
                  <input
                    aria-label={`Leftover extra name ${row.name}`}
                    value={leftoverExtraNames[row.id] ?? String(row.name ?? '')}
                    onChange={(e) => setLeftoverExtraNames((current) => ({ ...current, [row.id]: e.target.value }))}
                  />
                  </label>
                  <label>
                    <span>Price</span>
                  <input
                    aria-label={`Leftover extra price ${row.name}`}
                    value={leftoverExtraPrices[row.id] ?? String(row.price ?? '0')}
                    onChange={(e) => setLeftoverExtraPrices((current) => ({ ...current, [row.id]: e.target.value }))}
                  />
                  </label>
                  </div>
                  <div className="rest-order-actions">
                  <button
                    type="button"
                    aria-label={`Save leftover extra ${row.name}`}
                    onClick={async () => {
                      setError('');
                      try {
                        await api(`/restaurant/modifiers/${row.id}`, {
                          method: 'PATCH',
                          body: JSON.stringify({
                            name: leftoverExtraNames[row.id] ?? row.name,
                            price: leftoverExtraPrices[row.id] ?? String(row.price ?? '0'),
                          }),
                        });
                        setMessage(`Saved leftover extra ${row.name}`);
                        await refresh();
                      } catch (err: any) {
                        setError(err.message || 'Could not save the leftover extra');
                      }
                    }}
                  >
                    Save extra
                  </button>
                  <button
                    type="button"
                    aria-label={`Retire extra ${row.name}`}
                    onClick={async () => {
                      setError('');
                      try {
                        await api(`/restaurant/modifiers/${row.id}/retire`, { method: 'POST', body: JSON.stringify({}) });
                        setMessage(`Retired ${row.name}`);
                        await refresh();
                      } catch (err: any) {
                        setError(err.message || 'Could not retire the extra');
                      }
                    }}
                  >
                    Retire
                  </button>
                  </div>
                </li>
              )))}
            </ul>
          ) : (
            <p className="muted">No extras yet.</p>
          )}
          <form
            className="rest-order-form"
            onSubmit={(event) => {
              event.preventDefault();
              const name = zoneName.trim();
              if (!name) {
                setError('Enter a delivery zone');
                return;
              }
              void saveDeliveryZones([...deliveryZones, name]);
            }}
          >
            <label>
              <span>Zone</span>
              <input aria-label="Restaurant delivery zone" value={zoneName} onChange={(e) => setZoneName(e.target.value)} />
            </label>
            <button type="submit" aria-label="Add restaurant delivery zone">Add zone</button>
          </form>
          {deliveryZones.length ? (
            <ul aria-label="Restaurant delivery zones">
              {deliveryZones.map((name) => (
                <li key={name}>
                  {name}
                  <button type="button" aria-label={`Remove delivery zone ${name}`} onClick={() => saveDeliveryZones(deliveryZones.filter((zone) => zone !== name))}>
                    Remove
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <p className="muted">No delivery zones yet.</p>
          )}
          <section aria-label="Restaurant online food orders">
            <h3>Online food orders</h3>
            <p className="muted">Pay at the counter. This does not charge a card.</p>
            {onlineOrders.open ? (
              <>
                <p>Guests order at {onlineOrders.path}.</p>
                {onlineOrders.qr ? (
                  <img alt="Online food order code" src={String(onlineOrders.qr)} width={160} height={160} />
                ) : null}
                <p><Link href={String(onlineOrders.path || '/order')}>Open the guest page</Link></p>
                <button type="button" aria-label="Close online food orders" onClick={() => saveOnlineOrders(false)}>
                  Close online food orders
                </button>
              </>
            ) : (
              <>
                <p className="muted">Online food orders are closed.</p>
                <button type="button" aria-label="Open online food orders" onClick={() => saveOnlineOrders(true)}>
                  Open online food orders
                </button>
              </>
            )}
          </section>
          <section aria-label="Restaurant sold out">
            <h3>Sold out</h3>
            <p className="muted">A sold-out item stays on the menu. New orders cannot add it. This does not change stock.</p>
            {soldOut.length ? (
              <ul aria-label="Restaurant sold out items">
                {soldOut.map((row) => (
                  <li key={row.id}>
                    {row.name}
                    <button
                      type="button"
                      aria-label={`Put ${row.name} back on the menu`}
                      onClick={() => saveSoldOut(soldOut.filter((item) => item.id !== row.id).map((item) => item.id))}
                    >
                      Put back
                    </button>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="muted">Nothing is sold out.</p>
            )}
            <form
              className="rest-order-form"
              onSubmit={(event) => {
                event.preventDefault();
                const productId = soldOutId.trim();
                if (!productId) {
                  setError('Choose a menu item');
                  return;
                }
                void saveSoldOut([...soldOut.map((row) => row.id), productId]);
              }}
            >
              <label>
                <span>Menu item</span>
                <select aria-label="Restaurant sold out item" value={soldOutId} onChange={(e) => setSoldOutId(e.target.value)}>
                  <option value="">Menu item</option>
                  {menuItems.filter((row) => !soldOut.some((item) => item.id === row.id)).map((row) => (
                    <option key={row.id} value={row.id}>{menuLabel(row)}</option>
                  ))}
                </select>
              </label>
              <button type="submit" aria-label="Mark menu item sold out">Mark sold out</button>
            </form>
          </section>
          <form className="rest-order-form" onSubmit={createOrder}>
            <label>
              <span>Service</span>
            <select aria-label="Restaurant service mode" value={orderForm.service_mode} onChange={(e) => setOrderForm({ ...orderForm, service_mode: e.target.value })}>
              <option value="dine_in">Dine in</option>
              <option value="takeaway">Takeaway</option>
              <option value="delivery">Delivery</option>
            </select>
            </label>
            {orderForm.service_mode === 'dine_in' ? (
              <label>
                <span>Table</span>
              <select aria-label="Restaurant order table" value={orderForm.table_id} onChange={(e) => setOrderForm({ ...orderForm, table_id: e.target.value })}>
                <option value="">No table</option>
                {tables.map((table) => (
                  <option key={table.id} value={table.id}>
                    {table.code} · {table.seats} seats · {orderWord(table.status)}
                  </option>
                ))}
              </select>
              </label>
            ) : null}
            {orderForm.service_mode === 'delivery' ? (
              <>
              <label>
                <span>Address</span>
              <input
                aria-label="Restaurant delivery address"
                value={orderForm.delivery_address}
                onChange={(e) => setOrderForm({ ...orderForm, delivery_address: e.target.value })}
              />
              </label>
              {deliveryZones.length ? (
                <label>
                  <span>Zone</span>
                  <select aria-label="Restaurant order delivery zone" value={orderForm.delivery_zone} onChange={(e) => setOrderForm({ ...orderForm, delivery_zone: e.target.value })}>
                    <option value="">Choose a zone</option>
                    {deliveryZones.map((name) => (
                      <option key={name} value={name}>{name}</option>
                    ))}
                  </select>
                </label>
              ) : null}
              </>
            ) : null}
            <label>
              <span>Store</span>
            <select aria-label="Restaurant order store" value={orderForm.store_id} onChange={(e) => setOrderForm({ ...orderForm, store_id: e.target.value })}>
              <option value="">No store</option>
              {stores.filter((row) => row.is_active !== false).map((row) => (
                <option key={row.id} value={row.id}>{row.code} · {row.name}</option>
              ))}
            </select>
            </label>
            <label>
              <span>Tender</span>
            <select aria-label="Restaurant payment method" value={orderForm.payment_method} onChange={(e) => setOrderForm({ ...orderForm, payment_method: e.target.value })}>
              <option value="cash">Cash</option>
              <option value="card">Card</option>
              <option value="wallet">Wallet</option>
              <option value="mobile_money">Mobile Money</option>
            </select>
            </label>
            <label>
              <span>Menu item</span>
            <select aria-label="Restaurant menu item" value={orderForm.product_id} onChange={(e) => setOrderForm({ ...orderForm, product_id: e.target.value })}>
              <option value="">Menu item</option>
              {menuItems.map((row) => (
                <option key={row.id} value={row.id}>{menuLabel(row)}</option>
              ))}
            </select>
            </label>
            <label>
              <span>Quantity</span>
            <input aria-label="Restaurant order quantity" value={orderForm.quantity} onChange={(e) => setOrderForm({ ...orderForm, quantity: e.target.value })} />
            </label>
            <label>
              <span>Course</span>
            <select aria-label="Restaurant order course" value={orderForm.course} onChange={(e) => setOrderForm({ ...orderForm, course: e.target.value })}>
              <option value="starter">Starter</option>
              <option value="main">Main</option>
              <option value="dessert">Dessert</option>
              <option value="drink">Drink</option>
            </select>
            </label>
            <label>
              <span>Item note</span>
            <input aria-label="Restaurant item note" value={orderForm.item_note} onChange={(e) => setOrderForm({ ...orderForm, item_note: e.target.value })} />
            </label>
            <label>
              <input
                type="checkbox"
                aria-label="Restaurant item hold"
                checked={orderForm.item_hold}
                onChange={(e) => setOrderForm({ ...orderForm, item_hold: e.target.checked })}
              />
              <span>Hold</span>
            </label>
            <label>
              <span>Seat</span>
            <input aria-label="Restaurant item seat" value={orderForm.item_seat} onChange={(e) => setOrderForm({ ...orderForm, item_seat: e.target.value })} />
            </label>
            <label>
              <span>Spice</span>
            <select aria-label="Restaurant item spice" value={orderForm.item_spice} onChange={(e) => setOrderForm({ ...orderForm, item_spice: e.target.value })}>
              <option value="">No spice</option>
              <option value="mild">Mild</option>
              <option value="medium">Medium</option>
              <option value="hot">Hot</option>
            </select>
            </label>
            <label>
              <span>Doneness</span>
            <select aria-label="Restaurant item doneness" value={orderForm.item_doneness} onChange={(e) => setOrderForm({ ...orderForm, item_doneness: e.target.value })}>
              <option value="">No doneness</option>
              <option value="rare">Rare</option>
              <option value="medium">Medium</option>
              <option value="well">Well</option>
            </select>
            </label>
            {modifierGroups.flatMap((group) => (group.modifiers || []).map((row: Row) => (
              <label key={row.id}>
                <input
                  type="checkbox"
                  aria-label={`Restaurant extra ${row.name}`}
                  checked={selectedModifiers.includes(row.id)}
                  onChange={(e) => setSelectedModifiers((current) => (
                    e.target.checked ? [...current, row.id] : current.filter((id) => id !== row.id)
                  ))}
                />
                {row.name}
              </label>
            )))}
            <button type="button" aria-label="Add restaurant menu item" onClick={addOrderLine}>Add menu item</button>
            {orderLines.length > 0 ? (
              <ul aria-label="Restaurant order lines">
                {orderLines.map((line, index) => (
                  <li key={`${line.product_id}-${index}`}>
                    {line.quantity} × {products.find((row) => row.id === line.product_id)?.name || 'Menu item'}
                    {` · ${orderWord(line.course || 'main')}`}
                    {line.modifier_ids.length ? ` · ${line.modifier_ids.map(modifierName).join(', ')}` : ''}
                    <button
                      type="button"
                      aria-label={`Remove menu item ${index + 1}`}
                      onClick={() => setOrderLines((current) => current.filter((_, item) => item !== index))}
                    >
                      Remove
                    </button>
                  </li>
                ))}
              </ul>
            ) : null}
            <label>
              <span>Guest</span>
            <input aria-label="Restaurant customer name" value={orderForm.customer_name} onChange={(e) => setOrderForm({ ...orderForm, customer_name: e.target.value })} />
            </label>
            <label>
              <span>Covers</span>
            <input aria-label="Restaurant order covers" value={orderForm.covers} onChange={(e) => setOrderForm({ ...orderForm, covers: e.target.value })} />
            </label>
            <label>
              <span>Allergy</span>
            <input aria-label="Restaurant order allergy" value={orderForm.allergy} onChange={(e) => setOrderForm({ ...orderForm, allergy: e.target.value })} />
            </label>
            <label>
              <span>Allergen</span>
            <select aria-label="Restaurant order allergen" value={orderForm.allergen} onChange={(e) => setOrderForm({ ...orderForm, allergen: e.target.value })}>
              <option value="">No allergen</option>
              <option value="nuts">Nuts</option>
              <option value="gluten">Gluten</option>
              <option value="dairy">Dairy</option>
              <option value="shellfish">Shellfish</option>
            </select>
            </label>
            <label>
              <span>Occasion</span>
            <input aria-label="Restaurant order occasion" value={orderForm.occasion} onChange={(e) => setOrderForm({ ...orderForm, occasion: e.target.value })} />
            </label>
            <label>
              <span>Phone</span>
            <input aria-label="Restaurant order phone" value={orderForm.phone} onChange={(e) => setOrderForm({ ...orderForm, phone: e.target.value })} />
            </label>
            <label>
              <span>Email</span>
            <input aria-label="Restaurant order email" value={orderForm.guest_email} onChange={(e) => setOrderForm({ ...orderForm, guest_email: e.target.value })} />
            </label>
            <label>
              <span>Receipt</span>
            <select aria-label="Restaurant order receipt" value={orderForm.receipt} onChange={(e) => setOrderForm({ ...orderForm, receipt: e.target.value })}>
              <option value="">No receipt</option>
              <option value="print">Print</option>
              <option value="email">Email</option>
              <option value="declined">Declined</option>
            </select>
            </label>
            <label>
              <span>Pager</span>
            <input aria-label="Restaurant order pager" value={orderForm.pager} onChange={(e) => setOrderForm({ ...orderForm, pager: e.target.value })} />
            </label>
            <label>
              <span>Ready by</span>
            <input aria-label="Restaurant order ready by" value={orderForm.ready_by} onChange={(e) => setOrderForm({ ...orderForm, ready_by: e.target.value })} />
            </label>
            <label>
              <span>Quoted wait</span>
            <input aria-label="Restaurant order quoted wait" value={orderForm.quoted_wait} onChange={(e) => setOrderForm({ ...orderForm, quoted_wait: e.target.value })} />
            </label>
            <label>
              <span>Fire at</span>
            <input aria-label="Restaurant order fire at" value={orderForm.fire_at} onChange={(e) => setOrderForm({ ...orderForm, fire_at: e.target.value })} />
            </label>
            <label>
              <span>Packaging</span>
            <select aria-label="Restaurant order packaging" value={orderForm.packaging} onChange={(e) => setOrderForm({ ...orderForm, packaging: e.target.value })}>
              <option value="">No packaging</option>
              <option value="bag">Bag</option>
              <option value="box">Box</option>
            </select>
            </label>
            <label>
              <input
                type="checkbox"
                aria-label="Restaurant order rush"
                checked={orderForm.rush}
                onChange={(e) => setOrderForm({ ...orderForm, rush: e.target.checked })}
              />
              <span>Rush</span>
            </label>
            <label>
              <input
                type="checkbox"
                aria-label="Restaurant order bill"
                checked={orderForm.bill_asked}
                onChange={(e) => setOrderForm({ ...orderForm, bill_asked: e.target.checked })}
              />
              <span>Bill asked</span>
            </label>
            <label>
              <input
                type="checkbox"
                aria-label="Restaurant order arrived"
                checked={orderForm.guest_arrived}
                onChange={(e) => setOrderForm({ ...orderForm, guest_arrived: e.target.checked })}
              />
              <span>Arrived</span>
            </label>
            <label>
              <input
                type="checkbox"
                aria-label="Restaurant order cutlery"
                checked={orderForm.cutlery}
                onChange={(e) => setOrderForm({ ...orderForm, cutlery: e.target.checked })}
              />
              <span>Cutlery</span>
            </label>
            <label>
              <input
                type="checkbox"
                aria-label="Restaurant order high chair"
                checked={orderForm.high_chair}
                onChange={(e) => setOrderForm({ ...orderForm, high_chair: e.target.checked })}
              />
              <span>High chair</span>
            </label>
            <label>
              <span>Diet</span>
            <select aria-label="Restaurant order diet" value={orderForm.diet} onChange={(e) => setOrderForm({ ...orderForm, diet: e.target.value })}>
              <option value="">No diet</option>
              <option value="vegetarian">Vegetarian</option>
              <option value="vegan">Vegan</option>
              <option value="halal">Halal</option>
            </select>
            </label>
            <label>
              <span>Source</span>
            <select aria-label="Restaurant order source" value={orderForm.guest_source} onChange={(e) => setOrderForm({ ...orderForm, guest_source: e.target.value })}>
              <option value="">No source</option>
              <option value="walk_in">Walk-in</option>
              <option value="phone">Phone</option>
              <option value="booking">Booking</option>
            </select>
            </label>
            <label>
              <span>Vehicle</span>
            <input aria-label="Restaurant order vehicle" value={orderForm.vehicle} onChange={(e) => setOrderForm({ ...orderForm, vehicle: e.target.value })} />
            </label>
            <label>
              <span>Bay</span>
            <input aria-label="Restaurant order bay" value={orderForm.bay} onChange={(e) => setOrderForm({ ...orderForm, bay: e.target.value })} />
            </label>
            <label>
              <span>Handoff</span>
            <select aria-label="Restaurant order handoff" value={orderForm.handoff} onChange={(e) => setOrderForm({ ...orderForm, handoff: e.target.value })}>
              <option value="">No handoff</option>
              <option value="hand">Hand to guest</option>
              <option value="door">Leave at door</option>
            </select>
            </label>
            <label>
              <span>Notes</span>
            <input aria-label="Restaurant kitchen notes" value={orderForm.notes} onChange={(e) => setOrderForm({ ...orderForm, notes: e.target.value })} />
            </label>
            <button type="submit" aria-label="Save restaurant order">Save order</button>
          </form>
          <ul className="rest-order-list" aria-label="Restaurant orders">
            {orders.map((row) => (
              <li key={row.id} className="rest-order">
                <div className="rest-order-head">
                  <strong>{row.order_number}</strong>
                  {scanFacts([
                    ['Service', orderWord(row.service_mode)],
                    ['From', onlineLabel(row)],
                    ['Status', orderWord(row.status)],
                    ['Total', formatMoney(row.total_amount)],
                    ['Tax', Number(row.tax_amount) > 0 ? formatMoney(row.tax_amount) : 'No tax.'],
                    ['Service charge', Number(row.service_amount) > 0 ? formatMoney(row.service_amount) : 'No service charge.'],
                    ['Tender', tenderLabel(row)],
                    ['Guest', row.customer_name],
                    ['Covers', row.covers ? String(row.covers) : 'No covers.'],
                    ['Allergy', row.allergy || 'No allergy.'],
                    ['Allergen', row.allergen ? orderWord(row.allergen) : 'No allergen.'],
                    ['Occasion', row.occasion || 'No occasion.'],
                    ['Phone', row.phone || 'No phone.'],
                    ['Email', row.guest_email || 'No email.'],
                    ['Receipt', row.receipt ? orderWord(row.receipt) : 'No receipt.'],
                    ['Pager', row.pager ? String(row.pager) : 'No pager.'],
                    ['Ready by', row.ready_by || 'No ready time.'],
                    ['Quoted wait', row.quoted_wait ? `${row.quoted_wait} min` : 'No quoted wait.'],
                    ['Fire at', row.fire_at || 'No fire time.'],
                    ['Packaging', row.packaging ? orderWord(row.packaging) : 'No packaging.'],
                    ['Rush', row.rush ? 'Rush' : 'Not rushed.'],
                    ['Bill', row.bill_asked ? 'Bill asked.' : 'No bill asked.'],
                    ['Arrived', row.guest_arrived ? 'Guest arrived.' : 'Not arrived.'],
                    ['Cutlery', row.cutlery ? 'Cutlery' : 'No cutlery.'],
                    ['High chair', row.high_chair ? 'High chair' : 'No high chair.'],
                    ['Diet', row.diet ? orderWord(row.diet) : 'No diet.'],
                    ['Source', row.guest_source ? orderWord(row.guest_source) : 'No source.'],
                    ['Vehicle', row.vehicle || 'No vehicle.'],
                    ['Bay', row.bay ? String(row.bay) : 'No bay.'],
                    ['Handoff', row.handoff ? orderWord(row.handoff) : 'No handoff.'],
                    ['Server', row.server || 'No server.'],
                    ['Opened', row.opened_at ? formatDateTime(row.opened_at) : 'No opened time.'],
                    ['Table', row.table_id ? (tables.find((table) => table.id === row.table_id)?.code || 'Table') : ''],
                    ['Deliver to', row.delivery_address],
                  ['Zone', row.delivery_zone],
                    ['Notes', row.notes],
                  ])}
                </div>
                <ul className="rest-order-lines">
                  {(row.items || []).map((item: Row) => (
                    <li key={item.id} className="rest-order-line">
                      <div className="rest-order-head">
                        {scanFacts([
                          ['Item', `${item.quantity} × ${item.name}`],
                          ['Extras', item.modifiers?.length ? item.modifiers.join(', ') : ''],
                          ['Station', orderWord(item.station)],
                          ['Course', orderWord(item.course || 'main')],
                          ['Note', item.note || 'No item note.'],
                          ['Hold', item.hold ? 'Held' : 'Not held.'],
                          ['Seat', item.seat ? String(item.seat) : 'No seat.'],
                          ['Spice', item.spice ? orderWord(item.spice) : 'No spice.'],
                          ['Doneness', item.doneness ? orderWord(item.doneness) : 'No doneness.'],
                          ['Prep', orderWord(item.prep_status)],
                        ])}
                      </div>
                      {(row.status === 'open' || row.status === 'sent') && (
                        <>
                          <div className="rest-order-line-fields">
                          <div className="rest-order-cell">
                          <span>Quantity</span>
                          <input
                            aria-label={`Leftover quantity ${item.name} on ${row.order_number}`}
                            value={leftoverLineQuantities[item.id] ?? String(item.quantity ?? '1')}
                            onChange={(e) => setLeftoverLineQuantities((current) => ({ ...current, [item.id]: e.target.value }))}
                          />
                          <button
                            type="button"
                            aria-label={`Save leftover quantity ${item.name} on ${row.order_number}`}
                            onClick={() => saveLeftoverQuantity(row, item)}
                          >
                            Save quantity
                          </button>
                          </div>
                          <div className="rest-order-cell">
                          <span>Price</span>
                          <input
                            aria-label={`Leftover price ${item.name} on ${row.order_number}`}
                            value={leftoverLinePrices[item.id] ?? String(item.unit_price ?? '0')}
                            onChange={(e) => setLeftoverLinePrices((current) => ({ ...current, [item.id]: e.target.value }))}
                          />
                          <button
                            type="button"
                            aria-label={`Save leftover price ${item.name} on ${row.order_number}`}
                            onClick={() => saveLeftoverPrice(row, item)}
                          >
                            Save price
                          </button>
                          </div>
                          <div className="rest-order-cell">
                          <span>Station</span>
                          <select
                            aria-label={`Leftover station ${item.name} on ${row.order_number}`}
                            value={leftoverLineStations[item.id] ?? item.station ?? 'kitchen'}
                            onChange={(e) => setLeftoverLineStations((current) => ({ ...current, [item.id]: e.target.value }))}
                          >
                            <option value="kitchen">Kitchen</option>
                            <option value="bar">Bar</option>
                          </select>
                          <button
                            type="button"
                            aria-label={`Save leftover station ${item.name} on ${row.order_number}`}
                            onClick={() => saveLeftoverStation(row, item)}
                          >
                            Save station
                          </button>
                          </div>
                          <div className="rest-order-cell">
                          <span>Course</span>
                          <select
                            aria-label={`Leftover course ${item.name} on ${row.order_number}`}
                            value={leftoverLineCourses[item.id] ?? item.course ?? 'main'}
                            onChange={(e) => setLeftoverLineCourses((current) => ({ ...current, [item.id]: e.target.value }))}
                          >
                            <option value="starter">Starter</option>
                            <option value="main">Main</option>
                            <option value="dessert">Dessert</option>
                            <option value="drink">Drink</option>
                          </select>
                          <button
                            type="button"
                            aria-label={`Save leftover course ${item.name} on ${row.order_number}`}
                            onClick={() => saveLeftoverCourse(row, item)}
                          >
                            Save course
                          </button>
                          </div>
                          <div className="rest-order-cell">
                          <span>Item note</span>
                          <input
                            aria-label={`Leftover item note ${item.name} on ${row.order_number}`}
                            value={leftoverLineNotes[item.id] ?? item.note ?? ''}
                            onChange={(e) => setLeftoverLineNotes((current) => ({ ...current, [item.id]: e.target.value }))}
                          />
                          <button
                            type="button"
                            aria-label={`Save leftover item note ${item.name} on ${row.order_number}`}
                            onClick={() => saveLeftoverItemNote(row, item)}
                          >
                            Save item note
                          </button>
                          </div>
                          <div className="rest-order-cell">
                          <span>Seat</span>
                          <input
                            aria-label={`Leftover seat ${item.name} on ${row.order_number}`}
                            value={leftoverLineSeats[item.id] ?? (item.seat != null ? String(item.seat) : '')}
                            onChange={(e) => setLeftoverLineSeats((current) => ({ ...current, [item.id]: e.target.value }))}
                          />
                          <button
                            type="button"
                            aria-label={`Save leftover seat ${item.name} on ${row.order_number}`}
                            onClick={() => saveLeftoverSeat(row, item)}
                          >
                            Save seat
                          </button>
                          </div>
                          <div className="rest-order-cell">
                          <span>Spice</span>
                          <select
                            aria-label={`Leftover spice ${item.name} on ${row.order_number}`}
                            value={leftoverLineSpices[item.id] ?? item.spice ?? ''}
                            onChange={(e) => setLeftoverLineSpices((current) => ({ ...current, [item.id]: e.target.value }))}
                          >
                            <option value="">No spice</option>
                            <option value="mild">Mild</option>
                            <option value="medium">Medium</option>
                            <option value="hot">Hot</option>
                          </select>
                          <button
                            type="button"
                            aria-label={`Save leftover spice ${item.name} on ${row.order_number}`}
                            onClick={() => saveLeftoverSpice(row, item)}
                          >
                            Save spice
                          </button>
                          </div>
                          <div className="rest-order-cell">
                          <span>Doneness</span>
                          <select
                            aria-label={`Leftover doneness ${item.name} on ${row.order_number}`}
                            value={leftoverLineDoneness[item.id] ?? item.doneness ?? ''}
                            onChange={(e) => setLeftoverLineDoneness((current) => ({ ...current, [item.id]: e.target.value }))}
                          >
                            <option value="">No doneness</option>
                            <option value="rare">Rare</option>
                            <option value="medium">Medium</option>
                            <option value="well">Well</option>
                          </select>
                          <button
                            type="button"
                            aria-label={`Save leftover doneness ${item.name} on ${row.order_number}`}
                            onClick={() => saveLeftoverDoneness(row, item)}
                          >
                            Save doneness
                          </button>
                          </div>
                          <div className="rest-order-actions">
                          {item.hold ? (
                            <button type="button" aria-label={`Clear hold on ${item.name} ${row.order_number}`} onClick={() => saveLeftoverHold(row, item, false)}>
                              Clear hold
                            </button>
                          ) : (
                            <button type="button" aria-label={`Hold ${item.name} on ${row.order_number}`} onClick={() => saveLeftoverHold(row, item, true)}>
                              Hold
                            </button>
                          )}
                          </div>
                          </div>
                          <div className="rest-order-actions">
                          {modifierGroups.flatMap((group) => group.modifiers || []).map((extra: Row) => (
                            <label key={extra.id}>
                              <input
                                type="checkbox"
                                aria-label={`Leftover extra ${extra.name} on ${item.name} ${row.order_number}`}
                                checked={leftoverExtraIds(item).includes(extra.id)}
                                onChange={(e) => setLeftoverLineModifiers((current) => {
                                  const selected = current[item.id] ?? (Array.isArray(item.modifier_ids) ? item.modifier_ids : []);
                                  return {
                                    ...current,
                                    [item.id]: e.target.checked
                                      ? [...selected, extra.id]
                                      : selected.filter((id) => id !== extra.id),
                                  };
                                })}
                              />
                              {extra.name}
                            </label>
                          ))}
                          {modifierGroups.some((group) => (group.modifiers || []).length > 0) ? (
                            <button
                              type="button"
                              aria-label={`Save leftover extras ${item.name} on ${row.order_number}`}
                              onClick={() => saveLeftoverExtras(row, item)}
                            >
                              Save extras
                            </button>
                          ) : null}
                          <button
                            type="button"
                            aria-label={`Remove leftover ${item.name} on ${row.order_number}`}
                            onClick={() => removeLeftoverItem(row, item)}
                          >
                            Remove
                          </button>
                          </div>
                        </>
                      )}
                    </li>
                  ))}
                </ul>
                {(row.status === 'open' || row.status === 'sent') && (
                  <>
                    <div className="rest-order-line-fields">
                    <label>
                      <span>Service</span>
                    <select
                      aria-label={`Leftover service mode ${row.order_number}`}
                      value={leftoverServiceModes[row.id] ?? row.service_mode ?? 'takeaway'}
                      onChange={(e) => setLeftoverServiceModes((current) => ({ ...current, [row.id]: e.target.value }))}
                    >
                      <option value="dine_in">Dine in</option>
                      <option value="takeaway">Takeaway</option>
                      <option value="delivery">Delivery</option>
                      </select>
                    </label>
                    {(leftoverServiceModes[row.id] ?? row.service_mode) === 'dine_in' ? (
                      <label>
                        <span>Table</span>
                      <select
                        aria-label={`Leftover service table ${row.order_number}`}
                        value={leftoverServiceTables[row.id] ?? row.table_id ?? ''}
                        onChange={(e) => setLeftoverServiceTables((current) => ({ ...current, [row.id]: e.target.value }))}
                      >
                        <option value="">No table</option>
                        {tables.map((table) => (
                          <option key={table.id} value={table.id}>{table.code} · {table.seats} seats</option>
                        ))}
                      </select>
                      </label>
                    ) : null}
                    <button type="button" aria-label={`Save leftover service on ${row.order_number}`} onClick={() => saveLeftoverService(row)}>
                      Save service
                    </button>
                    <label>
                      <span>Tender</span>
                    <select
                      aria-label={`Leftover payment method ${row.order_number}`}
                      value={leftoverPaymentMethods[row.id] ?? row.payment_method ?? 'cash'}
                      onChange={(e) => setLeftoverPaymentMethods((current) => ({ ...current, [row.id]: e.target.value }))}
                    >
                      <option value="cash">Cash</option>
                      <option value="card">Card</option>
                      <option value="wallet">Wallet</option>
                      <option value="mobile_money">Mobile Money</option>
                    </select>
                    </label>
                    <button type="button" aria-label={`Save leftover payment on ${row.order_number}`} onClick={() => saveLeftoverPayment(row)}>
                      Save payment
                    </button>
                    <label>
                      <span>Store</span>
                    <select
                      aria-label={`Leftover order store ${row.order_number}`}
                      value={leftoverOrderStores[row.id] ?? row.store_id ?? ''}
                      onChange={(e) => setLeftoverOrderStores((current) => ({ ...current, [row.id]: e.target.value }))}
                    >
                      <option value="">No store</option>
                      {stores.filter((store) => store.is_active !== false).map((store) => (
                        <option key={store.id} value={store.id}>{store.code} · {store.name}</option>
                      ))}
                    </select>
                    </label>
                    <button type="button" aria-label={`Save leftover store on ${row.order_number}`} onClick={() => saveLeftoverStore(row)}>
                      Save store
                    </button>
                    <label>
                      <span>Guest</span>
                    <input
                      aria-label={`Leftover customer name ${row.order_number}`}
                      value={leftoverCustomerNames[row.id] ?? row.customer_name ?? ''}
                      onChange={(e) => setLeftoverCustomerNames((current) => ({ ...current, [row.id]: e.target.value }))}
                    />
                    </label>
                    <button type="button" aria-label={`Save leftover customer on ${row.order_number}`} onClick={() => saveLeftoverCustomer(row)}>
                      Save customer
                    </button>
                    <label>
                      <span>Covers</span>
                    <input
                      aria-label={`Leftover covers ${row.order_number}`}
                      value={leftoverCovers[row.id] ?? (row.covers ? String(row.covers) : '')}
                      onChange={(e) => setLeftoverCovers((current) => ({ ...current, [row.id]: e.target.value }))}
                    />
                    </label>
                    <button type="button" aria-label={`Save leftover covers on ${row.order_number}`} onClick={() => saveLeftoverCovers(row)}>
                      Save covers
                    </button>
                    <label>
                      <span>Allergy</span>
                    <input
                      aria-label={`Leftover allergy ${row.order_number}`}
                      value={leftoverAllergies[row.id] ?? row.allergy ?? ''}
                      onChange={(e) => setLeftoverAllergies((current) => ({ ...current, [row.id]: e.target.value }))}
                    />
                    </label>
                    <button type="button" aria-label={`Save leftover allergy on ${row.order_number}`} onClick={() => saveLeftoverAllergy(row)}>
                      Save allergy
                    </button>
                    <label>
                      <span>Allergen</span>
                    <select
                      aria-label={`Leftover allergen ${row.order_number}`}
                      value={leftoverAllergens[row.id] ?? row.allergen ?? ''}
                      onChange={(e) => setLeftoverAllergens((current) => ({ ...current, [row.id]: e.target.value }))}
                    >
                      <option value="">No allergen</option>
                      <option value="nuts">Nuts</option>
                      <option value="gluten">Gluten</option>
                      <option value="dairy">Dairy</option>
                      <option value="shellfish">Shellfish</option>
                    </select>
                    </label>
                    <button type="button" aria-label={`Save leftover allergen on ${row.order_number}`} onClick={() => saveLeftoverAllergen(row)}>
                      Save allergen
                    </button>
                    <label>
                      <span>Occasion</span>
                    <input
                      aria-label={`Leftover occasion ${row.order_number}`}
                      value={leftoverOccasions[row.id] ?? row.occasion ?? ''}
                      onChange={(e) => setLeftoverOccasions((current) => ({ ...current, [row.id]: e.target.value }))}
                    />
                    </label>
                    <button type="button" aria-label={`Save leftover occasion on ${row.order_number}`} onClick={() => saveLeftoverOccasion(row)}>
                      Save occasion
                    </button>
                    <label>
                      <span>Phone</span>
                    <input
                      aria-label={`Leftover phone ${row.order_number}`}
                      value={leftoverPhones[row.id] ?? row.phone ?? ''}
                      onChange={(e) => setLeftoverPhones((current) => ({ ...current, [row.id]: e.target.value }))}
                    />
                    </label>
                    <button type="button" aria-label={`Save leftover phone on ${row.order_number}`} onClick={() => saveLeftoverPhone(row)}>
                      Save phone
                    </button>
                    <label>
                      <span>Email</span>
                    <input
                      aria-label={`Leftover email ${row.order_number}`}
                      value={leftoverGuestEmails[row.id] ?? row.guest_email ?? ''}
                      onChange={(e) => setLeftoverGuestEmails((current) => ({ ...current, [row.id]: e.target.value }))}
                    />
                    </label>
                    <button type="button" aria-label={`Save leftover email on ${row.order_number}`} onClick={() => saveLeftoverGuestEmail(row)}>
                      Save email
                    </button>
                    <label>
                      <span>Receipt</span>
                    <select
                      aria-label={`Leftover receipt ${row.order_number}`}
                      value={leftoverReceipts[row.id] ?? row.receipt ?? ''}
                      onChange={(e) => setLeftoverReceipts((current) => ({ ...current, [row.id]: e.target.value }))}
                    >
                      <option value="">No receipt</option>
                      <option value="print">Print</option>
                      <option value="email">Email</option>
                      <option value="declined">Declined</option>
                    </select>
                    </label>
                    <button type="button" aria-label={`Save leftover receipt on ${row.order_number}`} onClick={() => saveLeftoverReceipt(row)}>
                      Save receipt
                    </button>
                    <label>
                      <span>Pager</span>
                    <input
                      aria-label={`Leftover pager ${row.order_number}`}
                      value={leftoverPagers[row.id] ?? (row.pager != null ? String(row.pager) : '')}
                      onChange={(e) => setLeftoverPagers((current) => ({ ...current, [row.id]: e.target.value }))}
                    />
                    </label>
                    <button type="button" aria-label={`Save leftover pager on ${row.order_number}`} onClick={() => saveLeftoverPager(row)}>
                      Save pager
                    </button>
                    <label>
                      <span>Ready by</span>
                    <input
                      aria-label={`Leftover ready by ${row.order_number}`}
                      value={leftoverReadyBy[row.id] ?? row.ready_by ?? ''}
                      onChange={(e) => setLeftoverReadyBy((current) => ({ ...current, [row.id]: e.target.value }))}
                    />
                    </label>
                    <button type="button" aria-label={`Save leftover ready by on ${row.order_number}`} onClick={() => saveLeftoverReadyBy(row)}>
                      Save ready by
                    </button>
                    <label>
                      <span>Quoted wait</span>
                    <input
                      aria-label={`Leftover quoted wait ${row.order_number}`}
                      value={leftoverQuotedWaits[row.id] ?? (row.quoted_wait == null ? '' : String(row.quoted_wait))}
                      onChange={(e) => setLeftoverQuotedWaits((current) => ({ ...current, [row.id]: e.target.value }))}
                    />
                    </label>
                    <button type="button" aria-label={`Save leftover quoted wait on ${row.order_number}`} onClick={() => saveLeftoverQuotedWait(row)}>
                      Save quoted wait
                    </button>
                    <label>
                      <span>Fire at</span>
                    <input
                      aria-label={`Leftover fire at ${row.order_number}`}
                      value={leftoverFireAt[row.id] ?? row.fire_at ?? ''}
                      onChange={(e) => setLeftoverFireAt((current) => ({ ...current, [row.id]: e.target.value }))}
                    />
                    </label>
                    <button type="button" aria-label={`Save leftover fire at on ${row.order_number}`} onClick={() => saveLeftoverFireAt(row)}>
                      Save fire at
                    </button>
                    <label>
                      <span>Packaging</span>
                    <select
                      aria-label={`Leftover packaging ${row.order_number}`}
                      value={leftoverPackaging[row.id] ?? row.packaging ?? ''}
                      onChange={(e) => setLeftoverPackaging((current) => ({ ...current, [row.id]: e.target.value }))}
                    >
                      <option value="">No packaging</option>
                      <option value="bag">Bag</option>
                      <option value="box">Box</option>
                    </select>
                    </label>
                    <button type="button" aria-label={`Save leftover packaging on ${row.order_number}`} onClick={() => saveLeftoverPackaging(row)}>
                      Save packaging
                    </button>
                    {row.rush ? (
                      <button type="button" aria-label={`Clear rush on ${row.order_number}`} onClick={() => saveRush(row, false)}>
                        Clear rush
                      </button>
                    ) : (
                      <button type="button" aria-label={`Mark ${row.order_number} rush`} onClick={() => saveRush(row, true)}>
                        Mark rush
                      </button>
                    )}
                    {row.bill_asked ? (
                      <button type="button" aria-label={`Clear bill on ${row.order_number}`} onClick={() => saveBill(row, false)}>
                        Clear bill
                      </button>
                    ) : (
                      <button type="button" aria-label={`Mark bill on ${row.order_number}`} onClick={() => saveBill(row, true)}>
                        Mark bill
                      </button>
                    )}
                    {row.guest_arrived ? (
                      <button type="button" aria-label={`Clear arrived on ${row.order_number}`} onClick={() => saveArrived(row, false)}>
                        Clear arrived
                      </button>
                    ) : (
                      <button type="button" aria-label={`Mark arrived on ${row.order_number}`} onClick={() => saveArrived(row, true)}>
                        Mark arrived
                      </button>
                    )}
                    {row.cutlery ? (
                      <button type="button" aria-label={`Clear cutlery on ${row.order_number}`} onClick={() => saveCutlery(row, false)}>
                        Clear cutlery
                      </button>
                    ) : (
                      <button type="button" aria-label={`Mark cutlery on ${row.order_number}`} onClick={() => saveCutlery(row, true)}>
                        Mark cutlery
                      </button>
                    )}
                    {row.high_chair ? (
                      <button type="button" aria-label={`Clear high chair on ${row.order_number}`} onClick={() => saveHighChair(row, false)}>
                        Clear high chair
                      </button>
                    ) : (
                      <button type="button" aria-label={`Mark high chair on ${row.order_number}`} onClick={() => saveHighChair(row, true)}>
                        Mark high chair
                      </button>
                    )}
                    <label>
                      <span>Diet</span>
                    <select
                      aria-label={`Leftover diet ${row.order_number}`}
                      value={leftoverDiets[row.id] ?? row.diet ?? ''}
                      onChange={(e) => setLeftoverDiets((current) => ({ ...current, [row.id]: e.target.value }))}
                    >
                      <option value="">No diet</option>
                      <option value="vegetarian">Vegetarian</option>
                      <option value="vegan">Vegan</option>
                      <option value="halal">Halal</option>
                    </select>
                    </label>
                    <button type="button" aria-label={`Save leftover diet on ${row.order_number}`} onClick={() => saveLeftoverDiet(row)}>
                      Save diet
                    </button>
                    <label>
                      <span>Source</span>
                    <select
                      aria-label={`Leftover source ${row.order_number}`}
                      value={leftoverSources[row.id] ?? row.guest_source ?? ''}
                      onChange={(e) => setLeftoverSources((current) => ({ ...current, [row.id]: e.target.value }))}
                    >
                      <option value="">No source</option>
                      <option value="walk_in">Walk-in</option>
                      <option value="phone">Phone</option>
                      <option value="booking">Booking</option>
                    </select>
                    </label>
                    <button type="button" aria-label={`Save leftover source on ${row.order_number}`} onClick={() => saveLeftoverSource(row)}>
                      Save source
                    </button>
                    <label>
                      <span>Vehicle</span>
                    <input
                      aria-label={`Leftover vehicle ${row.order_number}`}
                      value={leftoverVehicles[row.id] ?? row.vehicle ?? ''}
                      onChange={(e) => setLeftoverVehicles((current) => ({ ...current, [row.id]: e.target.value }))}
                    />
                    </label>
                    <button type="button" aria-label={`Save leftover vehicle on ${row.order_number}`} onClick={() => saveLeftoverVehicle(row)}>
                      Save vehicle
                    </button>
                    <label>
                      <span>Bay</span>
                    <input
                      aria-label={`Leftover bay ${row.order_number}`}
                      value={leftoverBays[row.id] ?? (row.bay == null ? '' : String(row.bay))}
                      onChange={(e) => setLeftoverBays((current) => ({ ...current, [row.id]: e.target.value }))}
                    />
                    </label>
                    <button type="button" aria-label={`Save leftover bay on ${row.order_number}`} onClick={() => saveLeftoverBay(row)}>
                      Save bay
                    </button>
                    <label>
                      <span>Handoff</span>
                    <select
                      aria-label={`Leftover handoff ${row.order_number}`}
                      value={leftoverHandoffs[row.id] ?? row.handoff ?? ''}
                      onChange={(e) => setLeftoverHandoffs((current) => ({ ...current, [row.id]: e.target.value }))}
                    >
                      <option value="">No handoff</option>
                      <option value="hand">Hand to guest</option>
                      <option value="door">Leave at door</option>
                    </select>
                    </label>
                    <button type="button" aria-label={`Save leftover handoff on ${row.order_number}`} onClick={() => saveLeftoverHandoff(row)}>
                      Save handoff
                    </button>
                    <label>
                      <span>Notes</span>
                    <input
                      aria-label={`Leftover notes ${row.order_number}`}
                      value={leftoverNotes[row.id] ?? row.notes ?? ''}
                      onChange={(e) => setLeftoverNotes((current) => ({ ...current, [row.id]: e.target.value }))}
                    />
                    </label>
                    <button type="button" aria-label={`Save leftover notes on ${row.order_number}`} onClick={() => saveLeftoverNotes(row)}>
                      Save notes
                    </button>
                    <label>
                      <span>Menu item</span>
                    <select
                      aria-label={`Leftover menu item ${row.order_number}`}
                      value={leftoverNewItems[row.id] ?? ''}
                      onChange={(e) => setLeftoverNewItems((current) => ({ ...current, [row.id]: e.target.value }))}
                    >
                      <option value="">Menu item</option>
                      {menuItems.map((item) => (
                        <option key={item.id} value={item.id}>{menuLabel(item)}</option>
                      ))}
                    </select>
                    </label>
                    <label>
                      <span>Quantity</span>
                    <input
                      aria-label={`Leftover new quantity ${row.order_number}`}
                      value={leftoverNewQuantities[row.id] ?? '1'}
                      onChange={(e) => setLeftoverNewQuantities((current) => ({ ...current, [row.id]: e.target.value }))}
                    />
                    </label>
                    {modifierGroups.flatMap((group) => group.modifiers || []).map((extra: Row) => (
                      <label key={`${row.id}-${extra.id}`}>
                        <input
                          type="checkbox"
                          aria-label={`Leftover new extra ${extra.name} on ${row.order_number}`}
                          checked={(leftoverNewModifiers[row.id] || []).includes(extra.id)}
                          onChange={(e) => setLeftoverNewModifiers((current) => {
                            const selected = current[row.id] || [];
                            return {
                              ...current,
                              [row.id]: e.target.checked
                                ? [...selected, extra.id]
                                : selected.filter((id) => id !== extra.id),
                            };
                          })}
                        />
                        {extra.name}
                      </label>
                    ))}
                    <button type="button" aria-label={`Add leftover item to ${row.order_number}`} onClick={() => addLeftoverItem(row)}>
                      Add leftover item
                    </button>
                    </div>
                    {(leftoverServiceModes[row.id] ?? row.service_mode) === 'delivery' ? (
                      <>
                        <input
                          aria-label={`Leftover delivery address ${row.order_number}`}
                          value={leftoverDeliveryAddresses[row.id] ?? row.delivery_address ?? ''}
                          onChange={(e) => setLeftoverDeliveryAddresses((current) => ({ ...current, [row.id]: e.target.value }))}
                        />
                        {deliveryZones.length ? (
                          <select
                            aria-label={`Leftover delivery zone ${row.order_number}`}
                            value={leftoverDeliveryZones[row.id] ?? row.delivery_zone ?? ''}
                            onChange={(e) => setLeftoverDeliveryZones((current) => ({ ...current, [row.id]: e.target.value }))}
                          >
                            <option value="">Choose a zone</option>
                            {deliveryZones.map((name) => (
                              <option key={name} value={name}>{name}</option>
                            ))}
                          </select>
                        ) : null}
                        <button type="button" aria-label={`Save leftover delivery address on ${row.order_number}`} onClick={() => saveLeftoverDelivery(row)}>
                          Save address
                        </button>
                      </>
                    ) : null}
                  </>
                )}
                <div className="rest-order-actions">
                {row.status === 'open' && (
                  <button type="button" aria-label={`Send order ${row.order_number} to kitchen`} onClick={() => act(row.id, 'send')}>Send to kitchen</button>
                )}
                {row.status !== 'completed' && row.status !== 'cancelled' && row.status !== 'voided' && row.status !== 'refunded' && (
                  <button type="button" aria-label={`Complete order ${row.order_number}`} onClick={() => act(row.id, 'complete')}>Complete</button>
                )}
                {row.status !== 'completed' && row.status !== 'cancelled' && row.status !== 'voided' && row.status !== 'refunded' && (
                  <button type="button" aria-label={`Cancel order ${row.order_number}`} onClick={() => act(row.id, 'cancel')}>Cancel</button>
                )}
                {row.status !== 'completed' && row.status !== 'cancelled' && row.status !== 'voided' && row.status !== 'refunded' && (
                  <button type="button" aria-label={`Void order ${row.order_number}`} onClick={() => act(row.id, 'void')}>Void</button>
                )}
                {row.status === 'completed' && (
                  <button type="button" aria-label={`Refund order ${row.order_number}`} onClick={() => act(row.id, 'refund')}>Refund</button>
                )}
                </div>
              </li>
            ))}
            {!orders.length && <li className="muted">No orders yet.</li>}
          </ul>
        </section>
      )}
      {restaurantDesk && tab === 'kitchen' && (
        <>
          <section className="card" aria-label="Restaurant kitchen sound">
            <h2>Kitchen sound</h2>
            <p className="muted">A new ticket plays a short chime when the kitchen refreshes.</p>
            {kitchenSound.on ? (
              <>
                <p>Kitchen sound is on.</p>
                <button type="button" aria-label="Turn off kitchen sound" onClick={() => saveKitchenSound(false)}>
                  Turn off kitchen sound
                </button>
              </>
            ) : (
              <>
                <p className="muted">Kitchen sound is off.</p>
                <button type="button" aria-label="Turn on kitchen sound" onClick={() => saveKitchenSound(true)}>
                  Turn on kitchen sound
                </button>
              </>
            )}
          </section>
          <section className="card" aria-label="Restaurant clock">
            <h2>Who is here</h2>
            <p className="muted">Clock in when the shift starts. Clock out when it ends. This does not open the till.</p>
            {clock.mine_open ? (
              <button type="button" aria-label="Clock out" onClick={() => punchClock('out')}>Clock out</button>
            ) : (
              <>
                <p className="muted">Not clocked in.</p>
                <button type="button" aria-label="Clock in" onClick={() => punchClock('in')}>Clock in</button>
              </>
            )}
            <ul className="rest-scan-list" aria-label="Restaurant clock list">
              {clock.open.map((row) => (
                <li key={row.id}>{row.name} · {formatDateTime(row.in_at)}</li>
              ))}
              {!clock.open.length && <li className="muted">No one is clocked in.</li>}
            </ul>
          </section>
          {stationQueue('kitchen', 'Kitchen', 'No tickets in the kitchen.', 'Kitchen queue')}
          {stationQueue('bar', 'Bar', 'No tickets at the bar.', 'Bar queue')}
        </>
      )}
      {restaurantDesk && tab === 'recipes' && (
        <section className="card">
          <h2>Recipes</h2>
          <form className="rest-order-form" onSubmit={saveStation}>
            <label>
              <span>Menu item</span>
            <select aria-label="Restaurant menu station item" value={stationForm.product_id} onChange={(e) => setStationForm({ ...stationForm, product_id: e.target.value })}>
              <option value="">Menu item</option>
              {products.filter((row) => !recipeIngredientIds.has(row.id) || recipeMenuIds.has(row.id)).map((row) => (
                <option key={row.id} value={row.id}>{menuLabel(row)}</option>
              ))}
            </select>
            </label>
            <label>
              <span>Station</span>
            <select aria-label="Restaurant menu station" value={stationForm.station} onChange={(e) => setStationForm({ ...stationForm, station: e.target.value })}>
              <option value="kitchen">Kitchen</option>
              <option value="bar">Bar</option>
            </select>
            </label>
            <button type="submit" aria-label="Save restaurant menu station">Save station</button>
          </form>
          <form className="rest-order-form" onSubmit={createRecipe}>
            <label>
              <span>Name</span>
            <input aria-label="Restaurant recipe name" value={recipeForm.name} onChange={(e) => setRecipeForm({ ...recipeForm, name: e.target.value })} />
            </label>
            <label>
              <span>Menu item</span>
            <select aria-label="Restaurant recipe menu item" value={recipeForm.product_id} onChange={(e) => setRecipeForm({ ...recipeForm, product_id: e.target.value })} required>
              <option value="">Menu item</option>
              {menuItems.map((row) => (
                <option key={row.id} value={row.id}>{menuLabel(row)}</option>
              ))}
            </select>
            </label>
            <label>
              <span>Ingredient</span>
            <select aria-label="Restaurant recipe ingredient" value={recipeForm.ingredient_id} onChange={(e) => setRecipeForm({ ...recipeForm, ingredient_id: e.target.value })}>
              <option value="">Ingredient</option>
              {ingredientItems.map((row) => (
                <option key={row.id} value={row.id}>{row.name}</option>
              ))}
            </select>
            </label>
            <label>
              <span>Quantity</span>
            <input aria-label="Restaurant recipe quantity" value={recipeForm.quantity} onChange={(e) => setRecipeForm({ ...recipeForm, quantity: e.target.value })} />
            </label>
            <label>
              <span>Cook time</span>
            <input aria-label="Restaurant recipe cook time" value={recipeForm.cook_time} onChange={(e) => setRecipeForm({ ...recipeForm, cook_time: e.target.value })} />
            </label>
            <label>
              <span>Servings</span>
            <input aria-label="Restaurant recipe servings" value={recipeForm.servings} onChange={(e) => setRecipeForm({ ...recipeForm, servings: e.target.value })} />
            </label>
            <button type="button" aria-label="Add restaurant ingredient" onClick={addRecipeLine}>Add ingredient</button>
            {recipeLines.length > 0 ? (
              <ul aria-label="Restaurant recipe lines">
                {recipeLines.map((line, index) => (
                  <li key={`${line.ingredient_id}-${index}`}>
                    {line.quantity} × {products.find((row) => row.id === line.ingredient_id)?.name || 'Ingredient'}
                    <button
                      type="button"
                      aria-label={`Remove ingredient ${index + 1}`}
                      onClick={() => setRecipeLines((current) => current.filter((_, item) => item !== index))}
                    >
                      Remove
                    </button>
                  </li>
                ))}
              </ul>
            ) : null}
            <button type="submit" aria-label="Save restaurant recipe">Save recipe</button>
          </form>
          {recipes.length ? (
            <ul className="rest-order-list" aria-label="Restaurant recipes">
              {recipes.map((row) => (
                <li key={row.id} className="rest-order">
                  <div className="rest-order-head">
                    <strong>{row.name}</strong>
                    {scanFacts([
                      ['Menu item', row.menu_item],
                      ['Station', orderWord(row.station)],
                      ['Cook time', row.cook_time ? `${row.cook_time} min` : 'No cook time.'],
                      ['Servings', row.servings ? (Number(row.servings) === 1 ? '1 serving' : `${row.servings} servings`) : 'No servings.'],
                    ])}
                  </div>
                  <div className="rest-order-line-fields">
                  <label>
                    <span>Name</span>
                  <input
                    aria-label={`Leftover recipe name ${row.name}`}
                    value={leftoverRecipeNames[row.id] ?? String(row.name ?? '')}
                    onChange={(e) => setLeftoverRecipeNames((current) => ({ ...current, [row.id]: e.target.value }))}
                  />
                  </label>
                  </div>
                  <div className="rest-order-actions">
                  <button type="button" aria-label={`Save leftover recipe ${row.name}`} onClick={() => saveLeftoverRecipe(row)}>
                    Save recipe
                  </button>
                  <label>
                    <span>Cook time</span>
                    <input
                      aria-label={`Leftover recipe cook time ${row.name}`}
                      value={leftoverCookTimes[row.id] ?? (row.cook_time ? String(row.cook_time) : '')}
                      onChange={(e) => setLeftoverCookTimes((current) => ({ ...current, [row.id]: e.target.value }))}
                    />
                  </label>
                  <button type="button" aria-label={`Save leftover cook time on ${row.name}`} onClick={() => saveLeftoverCookTime(row)}>
                    Save cook time
                  </button>
                  <label>
                    <span>Servings</span>
                    <input
                      aria-label={`Leftover recipe servings ${row.name}`}
                      value={leftoverServings[row.id] ?? (row.servings ? String(row.servings) : '')}
                      onChange={(e) => setLeftoverServings((current) => ({ ...current, [row.id]: e.target.value }))}
                    />
                  </label>
                  <button type="button" aria-label={`Save leftover servings on ${row.name}`} onClick={() => saveLeftoverServings(row)}>
                    Save servings
                  </button>
                  <button
                    type="button"
                    aria-label={`Retire leftover recipe ${row.name}`}
                    onClick={async () => {
                      setError('');
                      try {
                        await api(`/restaurant/recipes/${row.id}/retire`, { method: 'POST', body: JSON.stringify({}) });
                        setMessage(`Retired leftover recipe ${row.name}`);
                        await refresh();
                      } catch (err: any) {
                        setError(err.message || 'Could not retire the leftover recipe');
                      }
                    }}
                  >
                    Retire recipe
                  </button>
                  </div>
                  <ul className="rest-order-lines">
                    {leftoverRecipeLines(row).map((line: Row) => (
                      <li key={`${row.id}-${line.ingredient_id}`} className="rest-order-line">
                        <div className="rest-order-head">
                          {scanFacts([
                            ['Ingredient', line.name],
                            ['Quantity', line.quantity],
                          ])}
                        </div>
                        <div className="rest-order-line-fields">
                        <label>
                          <span>Quantity</span>
                        <input
                          aria-label={`Leftover recipe line quantity ${line.name} on ${row.name}`}
                          value={leftoverRecipeLineQuantities[`${row.id}:${line.ingredient_id}`] ?? String(line.quantity ?? '0')}
                          onChange={(e) => setLeftoverRecipeLineQuantities((current) => ({
                            ...current,
                            [`${row.id}:${line.ingredient_id}`]: e.target.value,
                          }))}
                        />
                        </label>
                        <button
                          type="button"
                          aria-label={`Remove leftover recipe line ${line.name} on ${row.name}`}
                          onClick={() => removeLeftoverRecipeLine(row, line)}
                        >
                          Remove
                        </button>
                        </div>
                      </li>
                    ))}
                  </ul>
                  <div className="rest-order-line-fields">
                  <label>
                    <span>Ingredient</span>
                  <select
                    aria-label={`Leftover recipe ingredient ${row.name}`}
                    value={leftoverRecipeIngredient[row.id] ?? ''}
                    onChange={(e) => setLeftoverRecipeIngredient((current) => ({ ...current, [row.id]: e.target.value }))}
                  >
                    <option value="">Ingredient</option>
                    {ingredientItems
                      .filter((item) => !leftoverRecipeLines(row).some((line) => line.ingredient_id === item.id))
                      .map((item) => (
                        <option key={item.id} value={item.id}>{item.name}</option>
                      ))}
                  </select>
                  </label>
                  <button
                    type="button"
                    aria-label={`Add leftover recipe ingredient ${row.name}`}
                    onClick={() => addLeftoverRecipeIngredient(row)}
                  >
                    Add ingredient
                  </button>
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            <p className="muted">No recipes yet.</p>
          )}
        </section>
      )}
      {restaurantDesk && tab === 'waste' && (
        <section className="card">
          <h2>Waste</h2>
          <p className="muted">
            Waste takes an ingredient off hand. It is not a sale and it does not open a bill. The cost is posted to operating expenses and taken off inventory. An ingredient with no cost still leaves stock and does not post a journal.
          </p>
          <form className="rest-order-form" onSubmit={saveWaste}>
            <label>
              <span>Ingredient</span>
            <select
              aria-label="Restaurant waste ingredient"
              value={wasteForm.product_id}
              onChange={(e) => setWasteForm({ ...wasteForm, product_id: e.target.value })}
            >
              <option value="">Ingredient</option>
              {ingredientItems.map((row) => (
                <option key={row.id} value={row.id}>{row.name}</option>
              ))}
            </select>
            </label>
            <label>
              <span>Quantity</span>
            <input
              aria-label="Restaurant waste quantity"
              value={wasteForm.quantity}
              onChange={(e) => setWasteForm({ ...wasteForm, quantity: e.target.value })}
            />
            </label>
            <label>
              <span>Reason</span>
            <select
              aria-label="Restaurant waste reason"
              value={wasteForm.reason}
              onChange={(e) => setWasteForm({ ...wasteForm, reason: e.target.value })}
            >
              <option value="spoilage">Spoilage</option>
              <option value="damage">Damage</option>
              <option value="waste">Waste</option>
            </select>
            </label>
            <label>
              <span>Notes</span>
            <input
              aria-label="Restaurant waste notes"
              value={wasteForm.notes}
              onChange={(e) => setWasteForm({ ...wasteForm, notes: e.target.value })}
            />
            </label>
            <label>
              <span>Warehouse</span>
            <select
              aria-label="Restaurant waste warehouse"
              value={wasteForm.warehouse_id}
              onChange={(e) => setWasteForm({ ...wasteForm, warehouse_id: e.target.value })}
            >
              <option value="">No warehouse</option>
              {warehouses.filter((row) => row.is_active !== false).map((row) => (
                <option key={row.id} value={row.id}>{row.code} · {row.name}</option>
              ))}
            </select>
            </label>
            <button type="submit" aria-label="Record restaurant waste">Record waste</button>
          </form>
          <ul aria-label="Restaurant waste history">
            {wasteRows.map((row) => (
              <li key={row.id}>
                {row.name} · {row.quantity} · {row.reason}
                {row.notes ? ` · ${row.notes}` : ''}
                {row.journal_entry_id ? ' · On the books' : ''}
              </li>
            ))}
            {!wasteRows.length && <li className="muted">No waste recorded yet.</li>}
          </ul>
        </section>
      )}
    </main>
  );
}
