// All prototype data lives here. Every export maps to something a real API
// will eventually return; swap these for fetches when the backend lands.

export type CashEvent = {
  id: string;
  day: number;
  amount: number; // positive = inflow, negative = outflow
  label: string;
  kind: 'sales' | 'payroll' | 'invoice' | 'rent' | 'purchase';
  counterparty?: string;
};

export type Tranche = { qty: number; day: number };
export type Payment = { amount: number; day: number };

export type Bundle = {
  unitPrice: number;
  deliveries: Tranche[];
  payments: Payment[];
  paymentTerms: string;
};

export type SupplierPersona = 'rigid' | 'flexible-schedule' | 'net-terms';

export type Supplier = {
  id: 'apex' | 'bluebonnet' | 'cardinal';
  name: string;
  agentName: string;
  city: string;
  persona: SupplierPersona;
  personaNote: string;
  accent: string; // storefront brand color
  storefront: { domain: string; tagline: string; sku: string };
  opening: Bundle;
};

export const business = {
  name: 'Hearth & Crumb Bakery',
  owner: 'Maya',
  ledgerSource: 'QuickBooks (synthetic export)',
  startCash: 6000,
  defaultFloor: 3000,
  horizonDays: 35,
};

export const intake = {
  ownerMessage:
    "We need 1,000 cake boxes by the 20th for the holiday preorders. Payroll is tight this month, so don't leave us short.",
  need: {
    item: 'Kraft bakery box, 10 × 10 × 5 in, window lid',
    quantity: 1000,
    needByDay: 20,
    quantityFirm: true,
    priority: 'Keep cash above reserve floor',
  },
  agentAck:
    "Got it. 1,000 boxes on site by day 20. Before I ask anyone for a price, I'm going to read your books so I know what you can actually afford to pay, and when.",
};

export const cashEvents: CashEvent[] = [
  { id: 'e1', day: 3, amount: 800, label: 'Weekend counter sales', kind: 'sales' },
  { id: 'e2', day: 5, amount: -3600, label: 'Payroll', kind: 'payroll' },
  { id: 'e3', day: 8, amount: 2800, label: 'Cafe Luna invoice #1042', kind: 'invoice', counterparty: 'Cafe Luna' },
  { id: 'e4', day: 10, amount: 800, label: 'Weekend counter sales', kind: 'sales' },
  { id: 'e5', day: 12, amount: 1900, label: 'Westside Deli invoice #1047', kind: 'invoice', counterparty: 'Westside Deli' },
  { id: 'e6', day: 15, amount: -1500, label: 'Rent', kind: 'rent' },
  { id: 'e7', day: 17, amount: 800, label: 'Weekend counter sales', kind: 'sales' },
  { id: 'e8', day: 19, amount: -3600, label: 'Payroll', kind: 'payroll' },
  { id: 'e9', day: 24, amount: 800, label: 'Weekend counter sales', kind: 'sales' },
];

// The invoice the judge control delays.
export const delayableInvoiceId = 'e3';

export const suppliers: Supplier[] = [
  {
    id: 'apex',
    name: 'Apex Packaging',
    agentName: 'Apex sales agent',
    city: 'Dallas, TX',
    persona: 'rigid',
    personaNote: 'Lowest price. Prepay only, fixed schedule.',
    accent: '#1d4ed8',
    storefront: { domain: 'shop.apexpack.example', tagline: 'Packaging at scale', sku: 'APX-KB1010-W' },
    opening: {
      unitPrice: 0.8,
      deliveries: [{ qty: 1000, day: 2 }],
      payments: [{ amount: 800, day: 1 }],
      paymentTerms: 'Prepay',
    },
  },
  {
    id: 'bluebonnet',
    name: 'Bluebonnet Box Co',
    agentName: 'Bluebonnet order agent',
    city: 'Austin, TX',
    persona: 'flexible-schedule',
    personaNote: 'Splits shipments, pays-on-delivery. Moves dates on request.',
    accent: '#4f46e5',
    storefront: { domain: 'store.bluebonnetbox.example', tagline: 'Boxes for small makers', sku: 'BB-KRAFT-10W' },
    opening: {
      unitPrice: 0.84,
      deliveries: [
        { qty: 500, day: 9 },
        { qty: 500, day: 14 },
      ],
      payments: [
        { amount: 420, day: 9 },
        { amount: 420, day: 14 },
      ],
      paymentTerms: 'Pay on each delivery',
    },
  },
  {
    id: 'cardinal',
    name: 'Cardinal Supply',
    agentName: 'Cardinal trade desk',
    city: 'Houston, TX',
    persona: 'net-terms',
    personaNote: 'Net 30 on approved accounts. Price is firm.',
    accent: '#b91c1c',
    storefront: { domain: 'buy.cardinalsupply.example', tagline: 'Trade accounts welcome', sku: 'CS-BX-1010K' },
    opening: {
      unitPrice: 0.9,
      deliveries: [{ qty: 1000, day: 2 }],
      payments: [{ amount: 900, day: 31 }],
      paymentTerms: 'Net 30',
    },
  },
];

// Recent posted ledger lines, shown on the execute step before the purchase lands.
export const ledgerHistory = [
  { id: 'l1', date: 'Day −6', account: 'Sales', memo: 'Weekend counter sales', amount: 812 },
  { id: 'l2', date: 'Day −4', account: 'Cost of goods', memo: 'Flour & butter, Hill Country Mill', amount: -640 },
  { id: 'l3', date: 'Day −2', account: 'Accounts receivable', memo: 'Cafe Luna invoice #1042 issued', amount: 2800 },
  { id: 'l4', date: 'Day −1', account: 'Accounts receivable', memo: 'Westside Deli invoice #1047 issued', amount: 1900 },
];

export const orderNumbers: Record<Supplier['id'], string> = {
  apex: 'APX-55120',
  bluebonnet: 'BB-20417',
  cardinal: 'CS-88903',
};
