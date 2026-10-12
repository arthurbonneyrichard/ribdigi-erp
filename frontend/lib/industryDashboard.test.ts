import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';
import {
  dashboardLayout,
  filterIndustryDashboardFeatures,
  industryDashboardFeatures,
  industryDashboardSectionLabel,
  industryHomePath,
  showsRetailOperations,
  softwareOwnerDashboardPath,
} from './industryDashboard';

test('hotel home is /hotel and restaurant home is /restaurant', () => {
  assert.equal(industryHomePath('hotel'), '/hotel');
  assert.equal(industryHomePath('hospitality'), '/hotel');
  assert.equal(industryHomePath('pharmacy'), '/dashboard');
  assert.equal(industryHomePath('mart'), '/dashboard');
  assert.equal(industryHomePath('restaurant'), '/restaurant');
  assert.equal(industryHomePath('retail'), '/dashboard');
});

test('removed industries are not customer desks', () => {
  for (const code of ['pharmacy', 'wholesale', 'retail_wholesale', 'fmcg', 'hospital', 'mart']) {
    assert.deepEqual(industryDashboardFeatures(code), []);
    assert.equal(industryDashboardSectionLabel(code), null);
    assert.equal(dashboardLayout(code), 'unconfigured');
    assert.equal(showsRetailOperations(code), false);
    assert.equal(industryHomePath(code), '/dashboard');
  }
  assert.deepEqual(industryDashboardFeatures('retail').map((f) => f.id), []);
  assert.equal(industryDashboardSectionLabel('retail'), null);
  assert.equal(showsRetailOperations('retail'), true);
});

test('restaurant cards are floor and kitchen without hotel PMS', () => {
  const rows = industryDashboardFeatures('restaurant');
  assert.deepEqual(
    rows.map((f) => f.href),
    ['/restaurant', '/restaurant?tab=orders', '/restaurant?tab=kitchen', '/printers'],
  );
  assert.equal(
    rows.some((f) => f.href.startsWith('/hotel')),
    false,
  );
});

test('software owner dashboard is the platform console, not an operating desk', () => {
  assert.equal(industryHomePath('software'), '/platform');
  assert.equal(dashboardLayout('software'), 'platform');
  assert.equal(showsRetailOperations('software'), false);
  assert.equal(showsRetailOperations('platform'), false);
  assert.deepEqual(industryDashboardFeatures('software'), []);
  const operating = [
    ...industryDashboardFeatures('retail'),
    ...industryDashboardFeatures('hotel'),
    ...industryDashboardFeatures('restaurant'),
  ];
  assert.equal(operating.some((row) => row.id === 'prescriptions' || row.href.startsWith('/hotel')), true);
  assert.deepEqual(filterIndustryDashboardFeatures(operating, 'software'), []);
  for (const role of [
    'platform_owner',
    'platform_admin',
    'platform_support',
    'platform_finance',
    'super_admin',
  ]) {
    assert.equal(softwareOwnerDashboardPath(role, 'software'), '/platform');
    assert.equal(softwareOwnerDashboardPath(role, null), '/platform');
  }
  assert.equal(softwareOwnerDashboardPath('', 'software'), null);
  assert.equal(softwareOwnerDashboardPath('company_admin', 'pharmacy'), null);
  assert.equal(softwareOwnerDashboardPath('company_admin', 'retail'), null);
  assert.equal(softwareOwnerDashboardPath('cashier', 'restaurant'), null);
  assert.equal(industryHomePath('retail'), '/dashboard');
  assert.equal(industryHomePath('pharmacy'), '/dashboard');
  assert.equal(industryHomePath('hotel'), '/hotel');
  assert.equal(industryHomePath('restaurant'), '/restaurant');
  assert.equal(dashboardLayout('pharmacy'), 'unconfigured');
  assert.equal(dashboardLayout('retail'), 'retail');
  assert.equal(showsRetailOperations('retail'), true);

  const page = readFileSync(
    join(dirname(fileURLToPath(import.meta.url)), '../app/(dashboard)/dashboard/page.tsx'),
    'utf8',
  );
  const platformGate = page.indexOf('Opening platform console');
  const pharmacyDesk = page.indexOf("liveIndustry === 'pharmacy'");
  const retailGrid = page.indexOf('{stats.map');
  const wholesaleDesk = page.indexOf('<WholesaleDeskCards');
  assert.ok(platformGate > 0);
  assert.ok(pharmacyDesk > platformGate);
  assert.ok(retailGrid > platformGate);
  assert.ok(wholesaleDesk > platformGate);
  assert.match(page, /softwareOwnerDashboardPath/);
  assert.match(page, /if \(ownerHome \|\| platformLayout\)/);

  const platform = readFileSync(
    join(dirname(fileURLToPath(import.meta.url)), '../app/(dashboard)/platform/page.tsx'),
    'utf8',
  );
  assert.match(platform, /Open support tickets/);
  assert.match(platform, /No open support tickets/);
  assert.match(platform, /No companies yet/);
  assert.match(platform, /\/platform\/reports\/summary/);
  assert.doesNotMatch(platform, /Total Sales|Pharmacy desk|Front desk|Kitchen|IndustryDashboardViews/);
});

test('filter drops hotel tiles for industries that are not a hotel desk', () => {
  const leaked = industryDashboardFeatures('hotel');
  assert.ok(leaked.some((f) => f.href.startsWith('/hotel')));
  assert.deepEqual(filterIndustryDashboardFeatures(leaked, 'mart'), []);
  assert.deepEqual(filterIndustryDashboardFeatures(leaked, 'pharmacy'), []);
  assert.deepEqual(filterIndustryDashboardFeatures(leaked, 'retail'), []);
});
