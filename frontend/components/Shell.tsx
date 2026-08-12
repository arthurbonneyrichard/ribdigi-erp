'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import { api } from '../lib/api';
import { canReadAnyModule, canReadModule } from '../lib/rbac';
import {
  getSelectedStoreId,
  setSelectedStoreId,
  subscribeStoreContext,
} from '../lib/storeContext';

/** Stage 95 N1/P1 — MVP Navigation IA (discoverability; existing engines). */
type NavLink = {
  kind: 'link';
  label: string;
  href: string;
  modules: string[];
};

type NavSection = { kind: 'section'; label: string };

type NavEntry = NavLink | NavSection;

const primaryNavSpec: NavEntry[] = [
  { kind: 'link', label: 'Dashboard', href: '/dashboard', modules: ['dashboard'] },
  { kind: 'section', label: 'Commerce' },
  { kind: 'link', label: 'Inventory', href: '/inventory', modules: ['inventory'] },
  {
    kind: 'link',
    label: 'Products',
    href: '/inventory?tab=products',
    modules: ['inventory'],
  },
  {
    kind: 'link',
    label: 'Active Products',
    href: '/inventory?tab=products&product_active=true',
    modules: ['inventory'],
  },
  {
    kind: 'link',
    label: 'Inactive Products',
    href: '/inventory?tab=products&product_active=false',
    modules: ['inventory'],
  },
  {
    kind: 'link',
    label: 'Product Search',
    href: '/inventory?tab=products&q=',
    modules: ['inventory'],
  },
  { kind: 'link', label: 'Stock', href: '/inventory?tab=stock', modules: ['inventory'] },
  { kind: 'link', label: 'Low stock', href: '/inventory?tab=lowstock', modules: ['inventory'] },
  {
    kind: 'link',
    label: 'Stock Counts',
    href: '/inventory?tab=counts',
    modules: ['inventory'],
  },
  {
    kind: 'link',
    label: 'Warehouse Transfers',
    href: '/inventory?tab=transfers',
    modules: ['inventory'],
  },
  {
    kind: 'link',
    label: 'Variants',
    href: '/inventory?tab=variants',
    modules: ['inventory'],
  },
  {
    kind: 'link',
    label: 'Active Variants',
    href: '/inventory?tab=variants&variant_active=true',
    modules: ['inventory'],
  },
  {
    kind: 'link',
    label: 'Inactive Variants',
    href: '/inventory?tab=variants&variant_active=false',
    modules: ['inventory'],
  },
  {
    kind: 'link',
    label: 'Batches',
    href: '/inventory?tab=batches',
    modules: ['inventory'],
  },
  {
    kind: 'link',
    label: 'Expiry',
    href: '/inventory?tab=expiry',
    modules: ['inventory'],
  },
  {
    kind: 'link',
    label: 'Stock Adjustments',
    href: '/inventory?tab=ops',
    modules: ['inventory'],
  },
  {
    kind: 'link',
    label: 'Opening Stock',
    href: '/inventory?tab=opening',
    modules: ['inventory'],
  },
  {
    kind: 'link',
    label: 'Movements',
    href: '/inventory?tab=movements',
    modules: ['inventory'],
  },
  {
    kind: 'link',
    label: 'Stock In Movements',
    href: '/inventory?tab=movements&movement_type=stock_in',
    modules: ['inventory'],
  },
  {
    kind: 'link',
    label: 'Stock Out Movements',
    href: '/inventory?tab=movements&movement_type=stock_out',
    modules: ['inventory'],
  },
  {
    kind: 'link',
    label: 'Opening Stock Movements',
    href: '/inventory?tab=movements&movement_type=opening_stock',
    modules: ['inventory'],
  },
  {
    kind: 'link',
    label: 'Adjustment Movements',
    href: '/inventory?tab=movements&movement_type=adjustment',
    modules: ['inventory'],
  },
  {
    kind: 'link',
    label: 'Transfer Out Movements',
    href: '/inventory?tab=movements&movement_type=transfer_out',
    modules: ['inventory'],
  },
  {
    kind: 'link',
    label: 'Transfer In Movements',
    href: '/inventory?tab=movements&movement_type=transfer_in',
    modules: ['inventory'],
  },
  {
    kind: 'link',
    label: 'Catalog Categories',
    href: '/inventory?tab=catalog#categories',
    modules: ['inventory'],
  },
  {
    kind: 'link',
    label: 'Active Categories',
    href: '/inventory?tab=catalog&category_active=true#categories',
    modules: ['inventory'],
  },
  {
    kind: 'link',
    label: 'Inactive Categories',
    href: '/inventory?tab=catalog&category_active=false#categories',
    modules: ['inventory'],
  },
  {
    kind: 'link',
    label: 'Catalog Brands',
    href: '/inventory?tab=catalog#brands',
    modules: ['inventory'],
  },
  {
    kind: 'link',
    label: 'Active Brands',
    href: '/inventory?tab=catalog&brand_active=true#brands',
    modules: ['inventory'],
  },
  {
    kind: 'link',
    label: 'Inactive Brands',
    href: '/inventory?tab=catalog&brand_active=false#brands',
    modules: ['inventory'],
  },
  {
    kind: 'link',
    label: 'Catalog Units',
    href: '/inventory?tab=catalog#units',
    modules: ['inventory'],
  },
  {
    kind: 'link',
    label: 'Active Units',
    href: '/inventory?tab=catalog&unit_active=true#units',
    modules: ['inventory'],
  },
  {
    kind: 'link',
    label: 'Inactive Units',
    href: '/inventory?tab=catalog&unit_active=false#units',
    modules: ['inventory'],
  },
  { kind: 'link', label: 'Sales', href: '/sales', modules: ['sales'] },
  {
    kind: 'link',
    label: 'Quotations',
    href: '/sales?tab=quotations',
    modules: ['sales'],
  },
  {
    kind: 'link',
    label: 'Draft Quotations',
    href: '/sales?tab=quotations&quote_status=draft',
    modules: ['sales'],
  },
  {
    kind: 'link',
    label: 'Accepted Quotations',
    href: '/sales?tab=quotations&quote_status=accepted',
    modules: ['sales'],
  },
  {
    kind: 'link',
    label: 'Sent Quotations',
    href: '/sales?tab=quotations&quote_status=sent',
    modules: ['sales'],
  },
  {
    kind: 'link',
    label: 'Rejected Quotations',
    href: '/sales?tab=quotations&quote_status=rejected',
    modules: ['sales'],
  },
  {
    kind: 'link',
    label: 'Expired Quotations',
    href: '/sales?tab=quotations&quote_status=expired',
    modules: ['sales'],
  },
  {
    kind: 'link',
    label: 'Customer Groups',
    href: '/sales?tab=groups',
    modules: ['sales', 'customers'],
  },
  {
    kind: 'link',
    label: 'Active Customer Groups',
    href: '/sales?tab=groups&active_only=true',
    modules: ['sales', 'customers'],
  },
  {
    kind: 'link',
    label: 'Inactive Customer Groups',
    href: '/sales?tab=groups&group_active=false',
    modules: ['sales', 'customers'],
  },
  {
    kind: 'link',
    label: 'Sales Returns',
    href: '/sales?tab=returns',
    modules: ['sales'],
  },
  {
    kind: 'link',
    label: 'Draft Sales Returns',
    href: '/sales?tab=returns&return_status=draft',
    modules: ['sales'],
  },
  {
    kind: 'link',
    label: 'Posted Sales Returns',
    href: '/sales?tab=returns&return_status=posted',
    modules: ['sales'],
  },
  {
    kind: 'link',
    label: 'Sales Invoices',
    href: '/sales?tab=invoices',
    modules: ['sales'],
  },
  {
    kind: 'link',
    label: 'Draft Invoices',
    href: '/sales?tab=invoices&status=draft',
    modules: ['sales'],
  },
  {
    kind: 'link',
    label: 'Posted Invoices',
    href: '/sales?tab=invoices&status=posted',
    modules: ['sales'],
  },
  {
    kind: 'link',
    label: 'Sent Invoices',
    href: '/sales?tab=invoices&status=sent',
    modules: ['sales'],
  },
  {
    kind: 'link',
    label: 'Overdue Invoices',
    href: '/sales?tab=invoices&status=overdue',
    modules: ['sales'],
  },
  {
    kind: 'link',
    label: 'Paid Invoices',
    href: '/sales?tab=invoices&status=paid',
    modules: ['sales'],
  },
  {
    kind: 'link',
    label: 'Unpaid Invoices',
    href: '/sales?tab=invoices&status=unpaid',
    modules: ['sales'],
  },
  {
    kind: 'link',
    label: 'Partial Invoices',
    href: '/sales?tab=invoices&status=partial',
    modules: ['sales'],
  },
  {
    kind: 'link',
    label: 'Cancelled Invoices',
    href: '/sales?tab=invoices&status=cancelled',
    modules: ['sales'],
  },
  { kind: 'link', label: 'POS', href: '/pos', modules: ['pos'] },
  {
    kind: 'link',
    label: 'POS Sessions',
    href: '/pos#sessions',
    modules: ['pos'],
  },
  {
    kind: 'link',
    label: 'POS Shift',
    href: '/pos#shift',
    modules: ['pos'],
  },
  {
    kind: 'link',
    label: 'POS Cart',
    href: '/pos#cart',
    modules: ['pos'],
  },
  {
    kind: 'link',
    label: 'POS Receipt',
    href: '/pos#receipt',
    modules: ['pos'],
  },
  { kind: 'link', label: 'Purchasing', href: '/purchasing', modules: ['purchasing'] },
  {
    kind: 'link',
    label: 'Purchase Requests',
    href: '/purchasing?tab=requests',
    modules: ['purchasing'],
  },
  {
    kind: 'link',
    label: 'Pending PRs',
    href: '/purchasing?tab=requests&pr_status=pending',
    modules: ['purchasing'],
  },
  {
    kind: 'link',
    label: 'Draft PRs',
    href: '/purchasing?tab=requests&pr_status=draft',
    modules: ['purchasing'],
  },
  {
    kind: 'link',
    label: 'Approved PRs',
    href: '/purchasing?tab=requests&pr_status=approved',
    modules: ['purchasing'],
  },
  {
    kind: 'link',
    label: 'Rejected PRs',
    href: '/purchasing?tab=requests&pr_status=rejected',
    modules: ['purchasing'],
  },
  {
    kind: 'link',
    label: 'Cancelled PRs',
    href: '/purchasing?tab=requests&pr_status=cancelled',
    modules: ['purchasing'],
  },
  {
    kind: 'link',
    label: 'Converted PRs',
    href: '/purchasing?tab=requests&pr_status=converted',
    modules: ['purchasing'],
  },
  {
    kind: 'link',
    label: 'Purchase Orders',
    href: '/purchasing?tab=orders',
    modules: ['purchasing'],
  },
  {
    kind: 'link',
    label: 'Open POs',
    href: '/purchasing?tab=orders&po_status=open',
    modules: ['purchasing'],
  },
  {
    kind: 'link',
    label: 'Draft POs',
    href: '/purchasing?tab=orders&po_status=draft',
    modules: ['purchasing'],
  },
  {
    kind: 'link',
    label: 'Sent POs',
    href: '/purchasing?tab=orders&po_status=sent',
    modules: ['purchasing'],
  },
  {
    kind: 'link',
    label: 'Partially Received POs',
    href: '/purchasing?tab=orders&po_status=partially_received',
    modules: ['purchasing'],
  },
  {
    kind: 'link',
    label: 'Received POs',
    href: '/purchasing?tab=orders&po_status=received',
    modules: ['purchasing'],
  },
  {
    kind: 'link',
    label: 'Cancelled POs',
    href: '/purchasing?tab=orders&po_status=cancelled',
    modules: ['purchasing'],
  },
  {
    kind: 'link',
    label: 'GRN',
    href: '/purchasing?tab=grn',
    modules: ['purchasing'],
  },
  {
    kind: 'link',
    label: 'Draft GRN',
    href: '/purchasing?tab=grn&grn_status=draft',
    modules: ['purchasing'],
  },
  {
    kind: 'link',
    label: 'Posted GRN',
    href: '/purchasing?tab=grn&grn_status=posted',
    modules: ['purchasing'],
  },
  {
    kind: 'link',
    label: 'Purchase Invoices',
    href: '/purchasing?tab=invoices',
    modules: ['purchasing'],
  },
  {
    kind: 'link',
    label: 'Outstanding Purchases',
    href: '/purchasing?tab=invoices&status=outstanding',
    modules: ['purchasing'],
  },
  {
    kind: 'link',
    label: 'Draft Purchases',
    href: '/purchasing?tab=invoices&status=draft',
    modules: ['purchasing'],
  },
  {
    kind: 'link',
    label: 'Overdue Purchases',
    href: '/purchasing?tab=invoices&status=overdue',
    modules: ['purchasing'],
  },
  {
    kind: 'link',
    label: 'Paid Purchases',
    href: '/purchasing?tab=invoices&status=paid',
    modules: ['purchasing'],
  },
  {
    kind: 'link',
    label: 'Unpaid Purchases',
    href: '/purchasing?tab=invoices&status=unpaid',
    modules: ['purchasing'],
  },
  {
    kind: 'link',
    label: 'Partial Purchases',
    href: '/purchasing?tab=invoices&status=partial',
    modules: ['purchasing'],
  },
  {
    kind: 'link',
    label: 'Cancelled Purchases',
    href: '/purchasing?tab=invoices&status=cancelled',
    modules: ['purchasing'],
  },
  {
    kind: 'link',
    label: 'Purchase Returns',
    href: '/purchasing?tab=returns',
    modules: ['purchasing'],
  },
  {
    kind: 'link',
    label: 'Draft Purchase Returns',
    href: '/purchasing?tab=returns&return_status=draft',
    modules: ['purchasing'],
  },
  {
    kind: 'link',
    label: 'Posted Purchase Returns',
    href: '/purchasing?tab=returns&return_status=posted',
    modules: ['purchasing'],
  },
  {
    kind: 'link',
    label: 'Purchase Settings',
    href: '/purchasing?tab=settings#purchase-settings',
    modules: ['purchasing'],
  },
  { kind: 'section', label: 'People' },
  {
    kind: 'link',
    label: 'Customers',
    href: '/sales?tab=customers',
    modules: ['sales', 'customers'],
  },
  {
    kind: 'link',
    label: 'Active Customers',
    href: '/sales?tab=customers&active_only=true',
    modules: ['sales', 'customers'],
  },
  {
    kind: 'link',
    label: 'Inactive Customers',
    href: '/sales?tab=customers&customer_status=inactive',
    modules: ['sales', 'customers'],
  },
  {
    kind: 'link',
    label: 'Suppliers',
    href: '/purchasing?tab=suppliers',
    modules: ['purchasing', 'suppliers'],
  },
  {
    kind: 'link',
    label: 'Active Suppliers',
    href: '/purchasing?tab=suppliers&supplier_status=active',
    modules: ['purchasing', 'suppliers'],
  },
  {
    kind: 'link',
    label: 'Inactive Suppliers',
    href: '/purchasing?tab=suppliers&supplier_status=inactive',
    modules: ['purchasing', 'suppliers'],
  },
  // Stage 96 L1 — Billers alias (Users + salesperson report; not a parallel CRUD engine)
  {
    kind: 'link',
    label: 'Billers',
    href: '/reports?tab=salesperson',
    modules: ['reports', 'users'],
  },
  { kind: 'section', label: 'Finance' },
  { kind: 'link', label: 'Expenses', href: '/expenses', modules: ['expenses'] },
  {
    kind: 'link',
    label: 'Pending Expenses',
    href: '/expenses?status=pending',
    modules: ['expenses'],
  },
  {
    kind: 'link',
    label: 'Approved Expenses',
    href: '/expenses?status=approved',
    modules: ['expenses'],
  },
  {
    kind: 'link',
    label: 'Rejected Expenses',
    href: '/expenses?status=rejected',
    modules: ['expenses'],
  },
  {
    kind: 'link',
    label: 'Expense Approval Matrix',
    href: '/expenses#approval-matrix',
    modules: ['expenses'],
  },
  {
    kind: 'link',
    label: 'Recurring Expenses',
    href: '/expenses#recurring',
    modules: ['expenses'],
  },
  {
    kind: 'link',
    label: 'Active Recurring Expenses',
    href: '/expenses?recurring_active=true#recurring',
    modules: ['expenses'],
  },
  {
    kind: 'link',
    label: 'Paused Recurring Expenses',
    href: '/expenses?recurring_active=false#recurring',
    modules: ['expenses'],
  },
  {
    kind: 'link',
    label: 'Expense Categories & Budgets',
    href: '/expenses#budgets',
    modules: ['expenses'],
  },
  {
    kind: 'link',
    label: 'Active Expense Categories',
    href: '/expenses?expense_category_active=true#budgets',
    modules: ['expenses'],
  },
  {
    kind: 'link',
    label: 'Inactive Expense Categories',
    href: '/expenses?expense_category_active=false#budgets',
    modules: ['expenses'],
  },
  {
    kind: 'link',
    label: 'Income',
    href: '/accounting?tab=ledger#profit-loss',
    modules: ['accounting'],
  },
  {
    kind: 'link',
    label: 'Money Transfer',
    href: '/accounting?tab=ledger#money-transfer',
    modules: ['accounting'],
  },
  {
    kind: 'link',
    label: 'Active Liquid Accounts',
    href: '/accounting?tab=ledger&liquid_active=true#money-transfer',
    modules: ['accounting'],
  },
  {
    kind: 'link',
    label: 'Inactive Liquid Accounts',
    href: '/accounting?tab=ledger&liquid_active=false#money-transfer',
    modules: ['accounting'],
  },
  { kind: 'link', label: 'Accounting', href: '/accounting', modules: ['accounting'] },
  {
    kind: 'link',
    label: 'Chart of Accounts',
    href: '/accounting?tab=ledger#coa',
    modules: ['accounting'],
  },
  {
    kind: 'link',
    label: 'Active Accounts',
    href: '/accounting?tab=ledger&account_active=true#coa',
    modules: ['accounting'],
  },
  {
    kind: 'link',
    label: 'Inactive Accounts',
    href: '/accounting?tab=ledger&account_active=false#coa',
    modules: ['accounting'],
  },
  {
    kind: 'link',
    label: 'Journals',
    href: '/accounting?tab=ledger#journals',
    modules: ['accounting'],
  },
  {
    kind: 'link',
    label: 'Unposted Journals',
    href: '/accounting?tab=ledger&status=unposted#journals',
    modules: ['accounting'],
  },
  {
    kind: 'link',
    label: 'Posted Journals',
    href: '/accounting?tab=ledger&status=posted#journals',
    modules: ['accounting'],
  },
  {
    kind: 'link',
    label: 'Trial Balance',
    href: '/accounting?tab=ledger#trial-balance',
    modules: ['accounting'],
  },
  {
    kind: 'link',
    label: 'Opening Balances',
    href: '/accounting?tab=ledger#opening-balances',
    modules: ['accounting'],
  },
  {
    kind: 'link',
    label: 'Bank Reconciliation',
    href: '/accounting?tab=reconcile#bank-reconciliation',
    modules: ['accounting'],
  },
  {
    kind: 'link',
    label: 'Active Bank Connections',
    href: '/accounting?tab=reconcile&bank_conn_active=true#bank-reconciliation',
    modules: ['accounting'],
  },
  {
    kind: 'link',
    label: 'Inactive Bank Connections',
    href: '/accounting?tab=reconcile&bank_conn_active=false#bank-reconciliation',
    modules: ['accounting'],
  },
  {
    kind: 'link',
    label: 'Cheques',
    href: '/accounting?tab=cheques#cheques',
    modules: ['accounting'],
  },
  {
    kind: 'link',
    label: 'Pending Cheques',
    href: '/accounting?tab=cheques&cheque_status=pending#cheques',
    modules: ['accounting'],
  },
  {
    kind: 'link',
    label: 'Deposited Cheques',
    href: '/accounting?tab=cheques&cheque_status=deposited#cheques',
    modules: ['accounting'],
  },
  {
    kind: 'link',
    label: 'Cleared Cheques',
    href: '/accounting?tab=cheques&cheque_status=cleared#cheques',
    modules: ['accounting'],
  },
  {
    kind: 'link',
    label: 'Bounced Cheques',
    href: '/accounting?tab=cheques&cheque_status=bounced#cheques',
    modules: ['accounting'],
  },
  {
    kind: 'link',
    label: 'Cancelled Cheques',
    href: '/accounting?tab=cheques&cheque_status=cancelled#cheques',
    modules: ['accounting'],
  },
  {
    kind: 'link',
    label: 'Received Cheques',
    href: '/accounting?tab=cheques&cheque_direction=received#cheques',
    modules: ['accounting'],
  },
  {
    kind: 'link',
    label: 'Issued Cheques',
    href: '/accounting?tab=cheques&cheque_direction=issued#cheques',
    modules: ['accounting'],
  },
  { kind: 'link', label: 'Credit', href: '/credit', modules: ['credit'] },
  {
    kind: 'link',
    label: 'Outstanding Receivables',
    href: '/credit?kind=receivable',
    modules: ['credit'],
  },
  {
    kind: 'link',
    label: 'Outstanding Payables',
    href: '/credit?kind=payable',
    modules: ['credit'],
  },
  {
    kind: 'link',
    label: 'Credit Aging',
    href: '/credit#aging',
    modules: ['credit'],
  },
  {
    kind: 'link',
    label: 'Early Pay Terms',
    href: '/credit#early-pay',
    modules: ['credit'],
  },
  {
    kind: 'link',
    label: 'Exchange Rates',
    href: '/credit#exchange-rates',
    modules: ['credit'],
  },
  {
    kind: 'link',
    label: 'Payment Schedule',
    href: '/credit?kind=payable#payment-schedule',
    modules: ['credit'],
  },
  {
    kind: 'link',
    label: 'Credit Party Actions',
    href: '/credit#party-actions',
    modules: ['credit'],
  },
  {
    kind: 'link',
    label: 'Credit By Party',
    href: '/credit#by-party',
    modules: ['credit'],
  },
  {
    kind: 'link',
    label: 'Credit Statement',
    href: '/credit#statement',
    modules: ['credit'],
  },
  { kind: 'link', label: 'Tax', href: '/tax', modules: ['tax'] },
  {
    kind: 'link',
    label: 'Tax Rates',
    href: '/tax#rates',
    modules: ['tax'],
  },
  {
    kind: 'link',
    label: 'Active Tax Rates',
    href: '/tax?tax_active=true#rates',
    modules: ['tax'],
  },
  {
    kind: 'link',
    label: 'Inactive Tax Rates',
    href: '/tax?tax_active=false#rates',
    modules: ['tax'],
  },
  {
    kind: 'link',
    label: 'Tax Calculator',
    href: '/tax#calculator',
    modules: ['tax'],
  },
  {
    kind: 'link',
    label: 'Tax Filing Pack',
    href: '/tax#filing',
    modules: ['tax'],
  },
  { kind: 'section', label: 'Operations' },
  { kind: 'link', label: 'Stores', href: '/stores', modules: ['stores'] },
  {
    kind: 'link',
    label: 'Active Stores',
    href: '/stores?store_active=true',
    modules: ['stores'],
  },
  {
    kind: 'link',
    label: 'Inactive Stores',
    href: '/stores?store_active=false',
    modules: ['stores'],
  },
  { kind: 'link', label: 'Warehouse', href: '/stores#warehouses', modules: ['stores'] },
  {
    kind: 'link',
    label: 'Active Warehouses',
    href: '/stores?warehouse_active=true#warehouses',
    modules: ['stores'],
  },
  {
    kind: 'link',
    label: 'Inactive Warehouses',
    href: '/stores?warehouse_active=false#warehouses',
    modules: ['stores'],
  },
  {
    kind: 'link',
    label: 'FEFO Policy',
    href: '/stores#fefo',
    modules: ['stores'],
  },
  {
    kind: 'link',
    label: 'Reorder Policies',
    href: '/stores#reorder',
    modules: ['stores'],
  },
  {
    kind: 'link',
    label: 'Cash Drawer',
    href: '/stores#cash-drawer',
    modules: ['stores'],
  },
  {
    kind: 'link',
    label: 'Inter-store Transfers',
    href: '/stores#transfers',
    modules: ['stores'],
  },
  {
    kind: 'link',
    label: 'Delivery status',
    href: '/sales?tab=orders',
    modules: ['sales'],
  },
  {
    kind: 'link',
    label: 'Confirmed Orders',
    href: '/sales?tab=orders&order_status=confirmed',
    modules: ['sales'],
  },
  {
    kind: 'link',
    label: 'Draft Orders',
    href: '/sales?tab=orders&order_status=draft',
    modules: ['sales'],
  },
  {
    kind: 'link',
    label: 'Processing Orders',
    href: '/sales?tab=orders&order_status=processing',
    modules: ['sales'],
  },
  {
    kind: 'link',
    label: 'Shipped Orders',
    href: '/sales?tab=orders&order_status=shipped',
    modules: ['sales'],
  },
  {
    kind: 'link',
    label: 'Delivered Orders',
    href: '/sales?tab=orders&order_status=delivered',
    modules: ['sales'],
  },
  {
    kind: 'link',
    label: 'Cancelled Orders',
    href: '/sales?tab=orders&order_status=cancelled',
    modules: ['sales'],
  },
  { kind: 'link', label: 'Reports', href: '/reports', modules: ['reports'] },
  {
    kind: 'link',
    label: 'Reports Summary',
    href: '/reports?tab=summary',
    modules: ['reports'],
  },
  {
    kind: 'link',
    label: 'Sales Report',
    href: '/reports?tab=sales',
    modules: ['reports'],
  },
  {
    kind: 'link',
    label: 'Customers Report',
    href: '/reports?tab=customers',
    modules: ['reports'],
  },
  {
    kind: 'link',
    label: 'Stores Report',
    href: '/reports?tab=stores',
    modules: ['reports'],
  },
  {
    kind: 'link',
    label: 'Transfers Report',
    href: '/reports?tab=transfers',
    modules: ['reports'],
  },
  {
    kind: 'link',
    label: 'Draft Transfers',
    href: '/reports?tab=transfers&status=draft',
    modules: ['reports'],
  },
  {
    kind: 'link',
    label: 'Requested Transfers',
    href: '/reports?tab=transfers&status=requested',
    modules: ['reports'],
  },
  {
    kind: 'link',
    label: 'In-transit Transfers',
    href: '/reports?tab=transfers&status=in_transit',
    modules: ['reports'],
  },
  {
    kind: 'link',
    label: 'Received Transfers',
    href: '/reports?tab=transfers&status=received',
    modules: ['reports'],
  },
  {
    kind: 'link',
    label: 'Cancelled Transfers',
    href: '/reports?tab=transfers&status=cancelled',
    modules: ['reports'],
  },
  {
    kind: 'link',
    label: 'Inter-store Transfer Reports',
    href: '/reports?tab=transfers&scope=inter_store',
    modules: ['reports'],
  },
  {
    kind: 'link',
    label: 'Warehouse Transfer Reports',
    href: '/reports?tab=transfers&scope=warehouse',
    modules: ['reports'],
  },
  {
    kind: 'link',
    label: 'Report Schedules',
    href: '/reports?tab=schedules#schedules',
    modules: ['reports'],
  },
  {
    kind: 'link',
    label: 'Daily Report Schedules',
    href: '/reports?tab=schedules&frequency=daily#schedules',
    modules: ['reports'],
  },
  {
    kind: 'link',
    label: 'Weekly Report Schedules',
    href: '/reports?tab=schedules&frequency=weekly#schedules',
    modules: ['reports'],
  },
  {
    kind: 'link',
    label: 'Enabled Report Schedules',
    href: '/reports?tab=schedules&enabled=true#schedules',
    modules: ['reports'],
  },
  {
    kind: 'link',
    label: 'Disabled Report Schedules',
    href: '/reports?tab=schedules&enabled=false#schedules',
    modules: ['reports'],
  },
  {
    kind: 'link',
    label: 'Profit & Loss',
    href: '/reports?tab=pnl',
    modules: ['reports'],
  },
  {
    kind: 'link',
    label: 'Cash Flow',
    href: '/reports?tab=cashflow',
    modules: ['reports'],
  },
  {
    kind: 'link',
    label: 'Balance Sheet',
    href: '/reports?tab=balancesheet',
    modules: ['reports'],
  },
  {
    kind: 'link',
    label: 'Inventory Report',
    href: '/reports?tab=inventory',
    modules: ['reports'],
  },
  {
    kind: 'link',
    label: 'Purchases Report',
    href: '/reports?tab=purchases',
    modules: ['reports'],
  },
  {
    kind: 'link',
    label: 'Credit Report',
    href: '/reports?tab=credit',
    modules: ['reports'],
  },
  {
    kind: 'link',
    label: 'Tax Report',
    href: '/reports?tab=tax',
    modules: ['reports'],
  },
  {
    kind: 'link',
    label: 'Expenses Report',
    href: '/reports?tab=expenses',
    modules: ['reports'],
  },
  { kind: 'link', label: 'Notifications', href: '/notifications', modules: ['notifications'] },
  {
    kind: 'link',
    label: 'Unread Notifications',
    href: '/notifications?status=unread',
    modules: ['notifications'],
  },
  {
    kind: 'link',
    label: 'Read Notifications',
    href: '/notifications?status=read',
    modules: ['notifications'],
  },
  {
    kind: 'link',
    label: 'Notification History',
    href: '/notifications?status=all',
    modules: ['notifications'],
  },
  {
    kind: 'link',
    label: 'Stock Alerts',
    href: '/notifications?group=stock',
    modules: ['notifications'],
  },
  {
    kind: 'link',
    label: 'Order Alerts',
    href: '/notifications?group=orders',
    modules: ['notifications'],
  },
  {
    kind: 'link',
    label: 'Payment Alerts',
    href: '/notifications?group=payments',
    modules: ['notifications'],
  },
  {
    kind: 'link',
    label: 'System Alerts',
    href: '/notifications?group=system',
    modules: ['notifications'],
  },
  { kind: 'link', label: 'AI Assistant', href: '/ai', modules: ['ai'] },
  {
    kind: 'link',
    label: 'AI Chat',
    href: '/ai#chat',
    modules: ['ai'],
  },
  {
    kind: 'link',
    label: 'AI Forecast',
    href: '/ai#forecast',
    modules: ['ai'],
  },
  {
    kind: 'link',
    label: 'AI Dead Stock',
    href: '/ai#dead-stock',
    modules: ['ai'],
  },
  {
    kind: 'link',
    label: 'AI Insights',
    href: '/ai#insights',
    modules: ['ai'],
  },
  {
    kind: 'link',
    label: 'AI Security',
    href: '/ai#security',
    modules: ['ai'],
  },
  {
    kind: 'link',
    label: 'AI Sales Analysis',
    href: '/ai#sales-analysis',
    modules: ['ai'],
  },
  {
    kind: 'link',
    label: 'AI Expense Analysis',
    href: '/ai#expense-analysis',
    modules: ['ai'],
  },
  {
    kind: 'link',
    label: 'AI Purchases Analysis',
    href: '/ai#purchases-analysis',
    modules: ['ai'],
  },
  {
    kind: 'link',
    label: 'AI Cross-Domain',
    href: '/ai#cross-domain',
    modules: ['ai'],
  },
  {
    kind: 'link',
    label: 'AI Document',
    href: '/ai#document',
    modules: ['ai'],
  },
  {
    kind: 'link',
    label: 'AI Customer',
    href: '/ai#customer',
    modules: ['ai'],
  },
  {
    kind: 'link',
    label: 'AI Report Generator',
    href: '/ai#report-generator',
    modules: ['ai'],
  },
  {
    kind: 'link',
    label: 'AI Low Stock',
    href: '/ai#low-stock',
    modules: ['ai'],
  },
  { kind: 'link', label: 'Settings', href: '/company', modules: ['company'] },
  {
    kind: 'link',
    label: 'Company Profile',
    href: '/company#profile',
    modules: ['company'],
  },
  {
    kind: 'link',
    label: 'Company Logo',
    href: '/company#logo',
    modules: ['company'],
  },
  {
    kind: 'link',
    label: 'Locale Formats',
    href: '/company#locale',
    modules: ['company'],
  },
  {
    kind: 'link',
    label: 'Company Tax',
    href: '/company#tax',
    modules: ['company', 'tax'],
  },
  {
    kind: 'link',
    label: 'Fiscal Period',
    href: '/company#fiscal-period',
    modules: ['company'],
  },
  {
    kind: 'link',
    label: 'Email Settings',
    href: '/company#email',
    modules: ['company'],
  },
  {
    kind: 'link',
    label: 'SMS Settings',
    href: '/company#sms',
    modules: ['company'],
  },
  {
    kind: 'link',
    label: 'Document templates',
    href: '/company#document-templates',
    modules: ['company'],
  },
  {
    kind: 'link',
    label: 'Branches',
    href: '/company#branches',
    modules: ['company'],
  },
  {
    kind: 'link',
    label: 'Active Branches',
    href: '/company?branch_active=true#branches',
    modules: ['company'],
  },
  {
    kind: 'link',
    label: 'Inactive Branches',
    href: '/company?branch_active=false#branches',
    modules: ['company'],
  },
  {
    kind: 'link',
    label: 'Departments',
    href: '/company#departments',
    modules: ['company'],
  },
  {
    kind: 'link',
    label: 'Active Departments',
    href: '/company?dept_active=true#departments',
    modules: ['company'],
  },
  {
    kind: 'link',
    label: 'Inactive Departments',
    href: '/company?dept_active=false#departments',
    modules: ['company'],
  },
  {
    kind: 'link',
    label: 'Document numbering',
    href: '/company#document-numbering',
    modules: ['company'],
  },
  {
    kind: 'link',
    label: 'Media storage',
    href: '/company#media',
    modules: ['company'],
  },
  {
    kind: 'link',
    label: 'Notification settings',
    href: '/notifications#preferences',
    modules: ['notifications'],
  },
];

const userMgmtLinks: NavLink[] = [
  { kind: 'link', label: 'Users', href: '/users', modules: ['users'] },
  {
    kind: 'link',
    label: 'Active Users',
    href: '/users?is_active=true',
    modules: ['users'],
  },
  {
    kind: 'link',
    label: 'Inactive Users',
    href: '/users?is_active=false',
    modules: ['users'],
  },
  {
    kind: 'link',
    label: 'Cashier Users',
    href: '/users?role=cashier',
    modules: ['users'],
  },
  {
    kind: 'link',
    label: 'Company Admin Users',
    href: '/users?role=company_admin',
    modules: ['users'],
  },
  {
    kind: 'link',
    label: 'Store Manager Users',
    href: '/users?role=store_manager',
    modules: ['users'],
  },
  {
    kind: 'link',
    label: 'Accountant Users',
    href: '/users?role=accountant',
    modules: ['users'],
  },
  {
    kind: 'link',
    label: 'Inventory Officer Users',
    href: '/users?role=inventory_officer',
    modules: ['users'],
  },
  {
    kind: 'link',
    label: 'Sales Officer Users',
    href: '/users?role=sales_officer',
    modules: ['users'],
  },
  { kind: 'link', label: 'Roles', href: '/admin/roles', modules: ['users'] },
  {
    kind: 'link',
    label: 'Create Role',
    href: '/admin/roles#create',
    modules: ['users'],
  },
  {
    kind: 'link',
    label: 'Custom Roles',
    href: '/admin/roles#custom',
    modules: ['users'],
  },
  {
    kind: 'link',
    label: 'Active Custom Roles',
    href: '/admin/roles?role_active=true#custom',
    modules: ['users'],
  },
  {
    kind: 'link',
    label: 'Inactive Custom Roles',
    href: '/admin/roles?role_active=false#custom',
    modules: ['users'],
  },
  {
    kind: 'link',
    label: 'System Roles',
    href: '/admin/roles#system',
    modules: ['users'],
  },
  { kind: 'link', label: 'Permissions', href: '/admin/permissions', modules: ['users'] },
  {
    kind: 'link',
    label: 'Custom Permissions',
    href: '/admin/permissions#custom',
    modules: ['users'],
  },
  {
    kind: 'link',
    label: 'System Permissions',
    href: '/admin/permissions#system',
    modules: ['users'],
  },
  {
    kind: 'link',
    label: 'Cashier Permissions',
    href: '/admin/permissions?role=cashier',
    modules: ['users'],
  },
  {
    kind: 'link',
    label: 'Company Admin Permissions',
    href: '/admin/permissions?role=company_admin',
    modules: ['users'],
  },
  {
    kind: 'link',
    label: 'Store Manager Permissions',
    href: '/admin/permissions?role=store_manager',
    modules: ['users'],
  },
  {
    kind: 'link',
    label: 'Accountant Permissions',
    href: '/admin/permissions?role=accountant',
    modules: ['users'],
  },
  {
    kind: 'link',
    label: 'Inventory Officer Permissions',
    href: '/admin/permissions?role=inventory_officer',
    modules: ['users'],
  },
  {
    kind: 'link',
    label: 'Sales Officer Permissions',
    href: '/admin/permissions?role=sales_officer',
    modules: ['users'],
  },
  {
    kind: 'link',
    label: 'Super Admin Permissions',
    href: '/admin/permissions?role=super_admin',
    modules: ['users'],
  },
  { kind: 'link', label: 'Audit', href: '/audit', modules: ['audit'] },
  {
    kind: 'link',
    label: 'Auth Audit',
    href: '/audit?module=auth',
    modules: ['audit'],
  },
  {
    kind: 'link',
    label: 'Sales Audit',
    href: '/audit?module=sales',
    modules: ['audit'],
  },
  {
    kind: 'link',
    label: 'Purchasing Audit',
    href: '/audit?module=purchasing',
    modules: ['audit'],
  },
  {
    kind: 'link',
    label: 'Inventory Audit',
    href: '/audit?module=inventory',
    modules: ['audit'],
  },
  {
    kind: 'link',
    label: 'Accounting Audit',
    href: '/audit?module=accounting',
    modules: ['audit'],
  },
  {
    kind: 'link',
    label: 'Expenses Audit',
    href: '/audit?module=expenses',
    modules: ['audit'],
  },
  {
    kind: 'link',
    label: 'Credit Audit',
    href: '/audit?module=credit',
    modules: ['audit'],
  },
  {
    kind: 'link',
    label: 'POS Audit',
    href: '/audit?module=pos',
    modules: ['audit'],
  },
  {
    kind: 'link',
    label: 'Tax Audit',
    href: '/audit?module=tax',
    modules: ['audit'],
  },
  {
    kind: 'link',
    label: 'Users Audit',
    href: '/audit?module=users',
    modules: ['audit'],
  },
  {
    kind: 'link',
    label: 'Company Audit',
    href: '/audit?module=company',
    modules: ['audit'],
  },
  {
    kind: 'link',
    label: 'Stores Audit',
    href: '/audit?module=stores',
    modules: ['audit'],
  },
  {
    kind: 'link',
    label: 'Security Audit',
    href: '/audit?module=security',
    modules: ['audit'],
  },
  {
    kind: 'link',
    label: 'Notifications Audit',
    href: '/audit?module=notifications',
    modules: ['audit'],
  },
  {
    kind: 'link',
    label: 'Backup Audit',
    href: '/audit?module=backup',
    modules: ['audit'],
  },
  {
    kind: 'link',
    label: 'AI Audit',
    href: '/audit?module=ai',
    modules: ['audit'],
  },
  {
    kind: 'link',
    label: 'Reports Audit',
    href: '/audit?module=reports',
    modules: ['audit'],
  },
  {
    kind: 'link',
    label: 'Dashboard Audit',
    href: '/audit?module=dashboard',
    modules: ['audit'],
  },
  { kind: 'link', label: 'Activity', href: '/activity', modules: ['audit'] },
  { kind: 'link', label: 'Backup', href: '/backup#schedule', modules: ['backup'] },
  {
    kind: 'link',
    label: 'Backup & Restore',
    href: '/backup#restore',
    modules: ['backup'],
  },
  {
    kind: 'link',
    label: 'Backup History',
    href: '/backup#history',
    modules: ['backup'],
  },
  { kind: 'link', label: 'Security', href: '/security', modules: ['security'] },
  {
    kind: 'link',
    label: 'Passkeys',
    href: '/security#passkeys',
    modules: ['security'],
  },
  {
    kind: 'link',
    label: 'TOTP',
    href: '/security#totp',
    modules: ['security'],
  },
  {
    kind: 'link',
    label: 'Webhooks',
    href: '/security#webhooks',
    modules: ['security'],
  },
  {
    kind: 'link',
    label: 'Active Webhooks',
    href: '/security?webhook_active=true#webhooks',
    modules: ['security'],
  },
  {
    kind: 'link',
    label: 'Paused Webhooks',
    href: '/security?webhook_active=false#webhooks',
    modules: ['security'],
  },
  {
    kind: 'link',
    label: 'API keys',
    href: '/security#api-keys',
    modules: ['security'],
  },
  {
    kind: 'link',
    label: 'Active sessions',
    href: '/security#sessions',
    modules: ['security'],
  },
];

type StoreOption = { id: string; code: string; name: string; is_active?: boolean };

type OnboardingStep = {
  id: string;
  title: string;
  description?: string;
  href: string;
  completed: boolean;
  auto_completed?: boolean;
  skipped?: boolean;
};

type OnboardingChecklist = {
  steps: OnboardingStep[];
  completed_count: number;
  total_count: number;
  progress_pct: number;
  dismissed: boolean;
  dismissible: boolean;
  visible: boolean;
};

export default function Shell({ children }: { children: React.ReactNode }) {
  const [unread, setUnread] = useState(0);
  const [permissions, setPermissions] = useState<Record<string, string[]> | null>(null);
  const [role, setRole] = useState('');
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [principal, setPrincipal] = useState('');
  const [idleMinutes, setIdleMinutes] = useState(30);
  const [stores, setStores] = useState<StoreOption[]>([]);
  const [storeId, setStoreId] = useState('');
  const [onboarding, setOnboarding] = useState<OnboardingChecklist | null>(null);
  const [onboardingBusy, setOnboardingBusy] = useState(false);
  const [navOpen, setNavOpen] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);
  const [searchQ, setSearchQ] = useState('');
  const [searchBusy, setSearchBusy] = useState(false);
  const [searchResults, setSearchResults] = useState<
    { kind: string; id?: string; label: string; meta?: string; href: string }[]
  >([]);
  const [searchOpen, setSearchOpen] = useState(false);
  const canManageOnboarding = role === 'company_admin' || role === 'super_admin';

  useEffect(() => {
    setStoreId(getSelectedStoreId());
    return subscribeStoreContext((id) => setStoreId(id));
  }, []);

  useEffect(() => {
    let active = true;
    async function load() {
      try {
        const meRes = await api('/me');
        if (!active) return;
        // ADR-137 — platform staff use Ribdigi House console, not tenant ERP nav
        // (allow /security for MFA enrollment).
        if (meRes.data?.principal === 'platform') {
          setPrincipal('platform');
          const path = typeof window !== 'undefined' ? window.location.pathname : '';
          if (path !== '/security' && !path.startsWith('/security/')) {
            window.location.replace(meRes.data?.redirect_path || '/platform/dashboard');
            return;
          }
          setPermissions(meRes.data?.permissions || {});
          setRole(meRes.data?.role || '');
          setFullName(meRes.data?.full_name || '');
          setEmail(meRes.data?.email || '');
          setIdleMinutes(Number(meRes.data?.inactivity_timeout_minutes) || 30);
          setUnread(0);
          return;
        }
        setPrincipal(meRes.data?.principal || 'tenant');
        const countRes = await api('/notifications/unread-count').catch(() => ({
          data: { count: 0 },
        }));
        if (!active) return;
        setUnread(countRes.data?.count || 0);
        setPermissions(meRes.data?.permissions || {});
        setRole(meRes.data?.role || '');
        setFullName(meRes.data?.full_name || '');
        setEmail(meRes.data?.email || '');
        setIdleMinutes(Number(meRes.data?.inactivity_timeout_minutes) || 30);
      } catch {
        if (active) {
          setUnread(0);
          setPermissions({});
          setRole('');
          setFullName('');
          setEmail('');
          setPrincipal('');
        }
      }
    }
    load();
    const id = setInterval(load, 30000);
    return () => {
      active = false;
      clearInterval(id);
    };
  }, []);

  useEffect(() => {
    let active = true;
    async function loadOnboarding() {
      try {
        const res = await api('/onboarding/checklist');
        if (!active) return;
        setOnboarding(res.data || null);
      } catch {
        if (active) setOnboarding(null);
      }
    }
    loadOnboarding();
    const id = setInterval(loadOnboarding, 60000);
    return () => {
      active = false;
      clearInterval(id);
    };
  }, []);

  async function mutateOnboarding(path: string) {
    if (onboardingBusy) return;
    setOnboardingBusy(true);
    try {
      const res = await api(path, { method: 'POST', body: '{}' });
      setOnboarding(res.data || null);
    } catch {
      // Keep existing banner state; next poll will refresh.
    } finally {
      setOnboardingBusy(false);
    }
  }

  useEffect(() => {
    if (!canReadModule(permissions, 'stores')) {
      setStores([]);
      return;
    }
    let active = true;
    api('/stores')
      .then((res) => {
        if (!active) return;
        const rows = (res.data || []).filter((s: StoreOption) => s.is_active !== false);
        setStores(rows);
        const selected = getSelectedStoreId();
        if (selected && !rows.some((s: StoreOption) => s.id === selected)) {
          setSelectedStoreId('');
        }
      })
      .catch(() => {
        if (active) setStores([]);
      });
    return () => {
      active = false;
    };
  }, [permissions]);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    const token = localStorage.getItem('token');
    if (!token) return;
    const timeoutMs = Math.max(5, idleMinutes) * 60 * 1000;
    let timer: ReturnType<typeof setTimeout> | null = null;
    let loggingOut = false;

    async function performIdleLogout() {
      if (loggingOut) return;
      loggingOut = true;
      try {
        await api('/auth/idle-logout', { method: 'POST', body: '{}' });
      } catch {
        // Still clear local credentials if the server call fails (expired token, etc.)
      }
      localStorage.removeItem('token');
      localStorage.removeItem('refresh_token');
      window.location.href = '/';
    }

    const reset = () => {
      if (timer) clearTimeout(timer);
      timer = setTimeout(() => {
        void performIdleLogout();
      }, timeoutMs);
    };
    const events = ['mousemove', 'mousedown', 'keydown', 'touchstart', 'scroll'] as const;
    events.forEach((ev) => window.addEventListener(ev, reset, { passive: true }));
    reset();
    return () => {
      if (timer) clearTimeout(timer);
      events.forEach((ev) => window.removeEventListener(ev, reset));
    };
  }, [idleMinutes]);

  async function logout() {
    try {
      await api('/auth/logout', { method: 'POST', body: '{}' });
    } catch {
      // clear local session anyway
    }
    localStorage.removeItem('token');
    localStorage.removeItem('refresh_token');
    window.location.href = '/';
  }

  async function runSearch(e?: React.FormEvent) {
    if (e) e.preventDefault();
    const q = searchQ.trim();
    if (!q) {
      setSearchResults([]);
      setSearchOpen(false);
      return;
    }
    setSearchBusy(true);
    try {
      const r = await api(`/search?q=${encodeURIComponent(q)}`);
      setSearchResults(r.data?.results || []);
      setSearchOpen(true);
    } catch {
      setSearchResults([]);
      setSearchOpen(true);
    } finally {
      setSearchBusy(false);
    }
  }

  const linkVisible = (link: NavLink) =>
    principal === 'platform'
      ? link.href === '/security' || link.href.startsWith('/security')
      : canReadAnyModule(permissions, link.modules);

  const visiblePrimary: NavEntry[] = [];
  if (principal !== 'platform') {
    for (const entry of primaryNavSpec) {
      if (entry.kind === 'section') {
        visiblePrimary.push(entry);
        continue;
      }
      if (linkVisible(entry)) visiblePrimary.push(entry);
    }
    // Drop empty section headers (no following visible link before next section/end).
    const pruned: NavEntry[] = [];
    for (let i = 0; i < visiblePrimary.length; i++) {
      const entry = visiblePrimary[i];
      if (entry.kind === 'section') {
        const hasLink = visiblePrimary
          .slice(i + 1)
          .find((e) => e.kind === 'section' || e.kind === 'link');
        if (hasLink && hasLink.kind === 'link') pruned.push(entry);
      } else {
        pruned.push(entry);
      }
    }
    visiblePrimary.length = 0;
    visiblePrimary.push(...pruned);
  }

  const visibleUserMgmt =
    principal === 'platform'
      ? userMgmtLinks.filter((l) => l.href === '/security')
      : userMgmtLinks.filter(linkVisible);

  const showStoreSwitcher =
    principal !== 'platform' && canReadModule(permissions, 'stores') && stores.length > 0;

  return (
    <div className={`shell${navOpen ? ' nav-open' : ''}`}>
      <aside className="side" id="tenant-side-nav">
        <div className="brand">{principal === 'platform' ? 'Ribdigi House' : 'RIBDIGI ERP'}</div>
        <nav className="nav" aria-label="Main">
          {principal === 'platform' && (
            <Link href="/platform/dashboard" onClick={() => setNavOpen(false)}>
              Platform console
            </Link>
          )}
          {visiblePrimary.map((entry, idx) =>
            entry.kind === 'section' ? (
              <div
                key={`section-${entry.label}-${idx}`}
                className="nav-section"
                aria-hidden={false}
              >
                {entry.label}
              </div>
            ) : (
              <Link
                key={entry.href + entry.label}
                href={entry.href}
                onClick={() => setNavOpen(false)}
              >
                {entry.label}
                {entry.href === '/notifications' && unread > 0 ? ` (${unread})` : ''}
              </Link>
            ),
          )}
          {visibleUserMgmt.length > 0 && (
            <>
              <div className="nav-section">User Management</div>
              {visibleUserMgmt.map((l) => (
                <Link key={l.href} href={l.href} onClick={() => setNavOpen(false)}>
                  {l.label}
                </Link>
              ))}
            </>
          )}
        </nav>
      </aside>
      <main className="main">
        <div className="topbar">
          <button
            type="button"
            className="nav-toggle"
            aria-expanded={navOpen}
            aria-controls="tenant-side-nav"
            onClick={() => setNavOpen((v) => !v)}
          >
            Menu
          </button>
          {principal !== 'platform' && (
            <form className="global-search" onSubmit={runSearch} role="search">
              <input
                value={searchQ}
                onChange={(e) => setSearchQ(e.target.value)}
                onFocus={() => {
                  if (searchResults.length) setSearchOpen(true);
                }}
                placeholder="Search products or customers"
                aria-label="Global search"
              />
              <button type="submit" disabled={searchBusy}>
                {searchBusy ? '…' : 'Search'}
              </button>
              {searchOpen && (
                <div className="global-search-results" role="listbox">
                  {searchResults.length === 0 ? (
                    <p className="muted" style={{ margin: 0, padding: 8 }}>
                      No matches
                    </p>
                  ) : (
                    searchResults.map((hit) => (
                      <Link
                        key={`${hit.kind}-${hit.id || hit.label}`}
                        href={hit.href}
                        role="option"
                        onClick={() => {
                          setSearchOpen(false);
                          setSearchQ('');
                        }}
                      >
                        <strong>{hit.label}</strong>
                        <span className="muted">
                          {' '}
                          · {hit.kind}
                          {hit.meta ? ` · ${hit.meta}` : ''}
                        </span>
                      </Link>
                    ))
                  )}
                </div>
              )}
            </form>
          )}
          {showStoreSwitcher && (
            <label className="store-switcher">
              <span className="muted">Store</span>
              <select
                value={storeId}
                onChange={(e) => setSelectedStoreId(e.target.value)}
                aria-label="Global store context"
              >
                <option value="">All stores</option>
                {stores.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.code} — {s.name}
                  </option>
                ))}
              </select>
            </label>
          )}
          <div className="topbar-spacer" />
          {canReadModule(permissions, 'notifications') && (
            <Link href="/notifications" className="bell">
              Alerts{unread > 0 ? ` · ${unread}` : ''}
            </Link>
          )}
          <div className="profile-menu">
            <button
              type="button"
              className="profile-trigger"
              aria-expanded={profileOpen}
              onClick={() => setProfileOpen((v) => !v)}
            >
              {fullName || email || 'Account'}
            </button>
            {profileOpen && (
              <div className="profile-dropdown" role="menu">
                <p className="muted" style={{ margin: '0 0 8px', fontSize: 12 }}>
                  {email || '—'}
                  {role ? ` · ${role}` : ''}
                </p>
                <Link
                  href="/security"
                  role="menuitem"
                  onClick={() => setProfileOpen(false)}
                >
                  Security / 2FA
                </Link>
                <button type="button" role="menuitem" onClick={() => void logout()}>
                  Log out
                </button>
              </div>
            )}
          </div>
        </div>
        {navOpen && (
          <button
            type="button"
            className="nav-backdrop"
            aria-label="Close menu"
            onClick={() => setNavOpen(false)}
          />
        )}
        {onboarding?.visible ? (
          <section className="onboarding-banner" aria-label="Getting started checklist">
            <div className="onboarding-banner-head">
              <div>
                <strong>Getting started</strong>
                <span className="muted">
                  {' '}
                  · {onboarding.completed_count}/{onboarding.total_count} complete (
                  {onboarding.progress_pct}%)
                </span>
              </div>
              {canManageOnboarding ? (
                <div className="onboarding-actions">
                  {onboarding.dismissible ? (
                    <button
                      type="button"
                      className="onboarding-btn"
                      disabled={onboardingBusy}
                      onClick={() => mutateOnboarding('/onboarding/checklist/dismiss')}
                    >
                      Dismiss
                    </button>
                  ) : (
                    <span className="muted">Dismiss after 80%</span>
                  )}
                </div>
              ) : null}
            </div>
            <div
              className="onboarding-progress"
              role="progressbar"
              aria-valuenow={onboarding.progress_pct}
              aria-valuemin={0}
              aria-valuemax={100}
            >
              <div
                className="onboarding-progress-bar"
                style={{ width: `${onboarding.progress_pct}%` }}
              />
            </div>
            <ul className="onboarding-steps">
              {onboarding.steps.map((step) => (
                <li key={step.id} className={step.completed ? 'done' : ''}>
                  <span className="onboarding-mark" aria-hidden>
                    {step.completed ? '✓' : '○'}
                  </span>
                  <Link href={step.href}>{step.title}</Link>
                  {canManageOnboarding && !step.auto_completed && !step.skipped ? (
                    <button
                      type="button"
                      className="onboarding-btn linkish"
                      disabled={onboardingBusy}
                      onClick={() =>
                        mutateOnboarding(`/onboarding/checklist/steps/${step.id}/skip`)
                      }
                    >
                      Skip
                    </button>
                  ) : null}
                  {canManageOnboarding && step.skipped ? (
                    <button
                      type="button"
                      className="onboarding-btn linkish"
                      disabled={onboardingBusy}
                      onClick={() =>
                        mutateOnboarding(`/onboarding/checklist/steps/${step.id}/unskip`)
                      }
                    >
                      Undo skip
                    </button>
                  ) : null}
                </li>
              ))}
            </ul>
          </section>
        ) : null}
        {children}
      </main>
    </div>
  );
}
