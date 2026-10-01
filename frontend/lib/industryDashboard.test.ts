import assert from 'node:assert/strict';
import test from 'node:test';
import {
  filterIndustryDashboardFeatures,
  industryDashboardFeatures,
  industryDashboardSectionLabel,
  industryHomePath,
} from './industryDashboard';

test('hotel home is /hotel; everyone else stays on /dashboard', () => {
  assert.equal(industryHomePath('hotel'), '/hotel');
  assert.equal(industryHomePath('hospitality'), '/hotel');
  assert.equal(industryHomePath('pharmacy'), '/dashboard');
  assert.equal(industryHomePath('mart'), '/dashboard');
  assert.equal(industryHomePath('restaurant'), '/dashboard');
  assert.equal(industryHomePath('retail'), '/dashboard');
});

test('pharmacy extras are lots/batches/POS plus Rx catalog and prescriptions; mart has none', () => {
  const pharmacy = industryDashboardFeatures('pharmacy');
  assert.deepEqual(
    pharmacy.map((f) => f.id),
    ['expiry_lots', 'batches', 'pos', 'rx_products', 'prescriptions'],
  );
  assert.equal(
    pharmacy.some((f) => f.href.startsWith('/hotel')),
    false,
  );
  assert.equal(pharmacy.some((f) => f.href === '/prescriptions'), true);
  assert.deepEqual(industryDashboardFeatures('mart'), []);
  assert.deepEqual(industryDashboardFeatures('retail'), []);
  assert.equal(industryDashboardSectionLabel('pharmacy'), 'Pharmacy management');
  assert.equal(industryDashboardSectionLabel('mart'), null);
});

test('restaurant cards are POS/printers without hotel PMS', () => {
  const rows = industryDashboardFeatures('restaurant');
  assert.deepEqual(
    rows.map((f) => f.href),
    ['/pos', '/printers'],
  );
  assert.equal(
    rows.some((f) => f.href.startsWith('/hotel')),
    false,
  );
});

test('filter drops pharmacy-only and hotel tiles for mart', () => {
  const leaked = [
    ...industryDashboardFeatures('pharmacy'),
    ...industryDashboardFeatures('hotel'),
  ];
  assert.deepEqual(filterIndustryDashboardFeatures(leaked, 'mart'), []);
  assert.equal(filterIndustryDashboardFeatures(leaked, 'pharmacy').some((f) => f.id === 'batches'), true);
});
