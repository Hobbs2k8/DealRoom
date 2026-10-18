// Pure scenario logic: cash forecast, feasibility, and the scripted supplier
// negotiation. No React in here so it can move server-side unchanged.
import {
  business,
  cashEvents,
  delayableInvoiceId,
  suppliers,
  type Bundle,
  type CashEvent,
  type Payment,
  type Supplier,
} from './mock';

export type Scenario = { delayDays: number; floor: number; needByDay: number; quantity: number };

export type ForecastPoint = { day: number; balance: number };

export type Forecast = {
  points: ForecastPoint[];
  min: number;
  minDay: number;
  breach: { day: number; balance: number } | null;
};

export const money = (n: number, cents = false) =>
  (n < 0 ? '−$' : '$') +
  Math.abs(n).toLocaleString('en-US', {
    minimumFractionDigits: cents ? 2 : 0,
    maximumFractionDigits: cents ? 2 : 0,
  });

export function scenarioEvents(s: Scenario): CashEvent[] {
  return cashEvents
    .map((e) => (e.id === delayableInvoiceId ? { ...e, day: e.day + s.delayDays } : e))
    .sort((a, b) => a.day - b.day);
}

export function forecast(s: Scenario, payments: Payment[] = []): Forecast {
  const events = scenarioEvents(s);
  const points: ForecastPoint[] = [];
  let balance = business.startCash;
  let min = Infinity;
  let minDay = 0;
  let breach: Forecast['breach'] = null;
  for (let day = 0; day <= business.horizonDays; day++) {
    for (const e of events) if (e.day === day) balance += e.amount;
    for (const p of payments) if (p.day === day) balance -= p.amount;
    points.push({ day, balance });
    if (balance < min) {
      min = balance;
      minDay = day;
    }
    if (!breach && balance < s.floor) breach = { day, balance };
  }
  return { points, min, minDay, breach };
}

export const bundleTotal = (b: Bundle) => b.payments.reduce((t, p) => t + p.amount, 0);

export type MsgKind = 'request' | 'offer' | 'counter' | 'accept' | 'reject' | 'walk';

export type Message = {
  from: 'buyer' | 'supplier';
  kind: MsgKind;
  text: string;
  bundle?: Bundle;
  changed?: ('deliveries' | 'payments' | 'price')[];
};

export type DealOutcome = {
  supplier: Supplier;
  opening: Bundle;
  openingForecast: Forecast;
  final: Bundle | null; // null = no agreement
  finalForecast: Forecast | null;
  renegotiated: boolean;
  transcript: Message[];
  reason: string; // one line for compare view
};

const breachLine = (f: Forecast, floor: number) =>
  f.breach
    ? `Cash drops to ${money(f.breach.balance)} on day ${f.breach.day}, ${money(floor - f.breach.balance)} under your ${money(floor)} floor.`
    : '';

const describe = (b: Bundle) => {
  const d = b.deliveries.map((t) => `${t.qty.toLocaleString()} on day ${t.day}`).join(' + ');
  const p = b.payments.map((x) => `${money(x.amount)} on day ${x.day}`).join(' + ');
  return `$${b.unitPrice.toFixed(2)}/box · deliver ${d} · pay ${p}`;
};

function negotiate(sup: Supplier, s: Scenario, base: Forecast): DealOutcome {
  const opening = sup.opening;
  const openingForecast = forecast(s, opening.payments);
  const t: Message[] = [
    {
      from: 'buyer',
      kind: 'request',
      text: `Requesting a bundle: ${s.quantity.toLocaleString()} kraft bakery boxes, delivered by day ${s.needByDay}. Price, delivery schedule and payment dates all on the table.`,
    },
    { from: 'supplier', kind: 'offer', text: describe(opening), bundle: opening },
  ];
  const out = (final: Bundle | null, reason: string, renegotiated = false): DealOutcome => ({
    supplier: sup,
    opening,
    openingForecast,
    final,
    finalForecast: final ? forecast(s, final.payments) : null,
    renegotiated,
    transcript: t,
    reason,
  });

  // The business breaks the floor with no purchase at all. Nothing to negotiate.
  if (base.breach) {
    t.push({
      from: 'buyer',
      kind: 'walk',
      text: `I can't take any version of this. Without buying anything, your cash already falls to ${money(base.breach.balance)} on day ${base.breach.day}. Standing down.`,
    });
    return out(null, `Books break the floor on day ${base.breach.day} before any purchase.`);
  }

  const feasible = !openingForecast.breach;

  if (sup.persona === 'rigid') {
    if (feasible) {
      t.push({ from: 'buyer', kind: 'accept', text: 'These terms clear the floor. Accepting as offered.' });
      t.push({ from: 'supplier', kind: 'accept', text: `Confirmed. Order locked at ${money(bundleTotal(opening))}.` });
      return out(opening, 'Clears the floor as offered.');
    }
    const later: Bundle = { ...opening, payments: [{ amount: bundleTotal(opening), day: 12 }], paymentTerms: 'Net 10' };
    t.push({
      from: 'buyer',
      kind: 'counter',
      text: `Prepaying day 1 doesn't work. ${breachLine(openingForecast, s.floor)} Same price, same delivery, but payment on day 12 after receivables clear?`,
      bundle: later,
      changed: ['payments'],
    });
    t.push({ from: 'supplier', kind: 'reject', text: 'Prepayment is required on all orders. Terms are not negotiable.' });
    t.push({ from: 'buyer', kind: 'walk', text: 'Understood. Walking away; the cheapest price is no use if it bounces payroll.' });
    return out(null, breachLine(openingForecast, s.floor));
  }

  if (sup.persona === 'net-terms') {
    if (!feasible) {
      t.push({ from: 'buyer', kind: 'walk', text: `Even on net 30 this fails. ${breachLine(openingForecast, s.floor)}` });
      return out(null, breachLine(openingForecast, s.floor));
    }
    const ask: Bundle = { ...opening, unitPrice: 0.86, payments: [{ amount: 860, day: 31 }] };
    t.push({ from: 'buyer', kind: 'counter', text: 'Net 30 works for cash. Can you meet $0.86/box?', bundle: ask, changed: ['price'] });
    t.push({ from: 'supplier', kind: 'reject', text: '$0.90 is our floor on trade terms. Net 30 is the concession.' });
    t.push({ from: 'buyer', kind: 'accept', text: 'Fair. Accepting $0.90, net 30, delivered day 2.' });
    t.push({ from: 'supplier', kind: 'accept', text: `Accepted. ${money(bundleTotal(opening))} due day 31.` });
    return out(opening, `Feasible. Lowest cash ${money(openingForecast.min)} on day ${openingForecast.minDay}.`);
  }

  // flexible-schedule
  if (feasible) {
    const ask: Bundle = {
      ...opening,
      unitPrice: 0.82,
      payments: opening.payments.map((p) => ({ ...p, amount: 410 })),
    };
    t.push({ from: 'buyer', kind: 'counter', text: 'Schedule works for cash. Room on price? $0.82/box.', bundle: ask, changed: ['price'] });
    t.push({ from: 'supplier', kind: 'reject', text: "$0.84 is as low as we go at 1,000 units. Happy to keep the split schedule." });
    t.push({ from: 'buyer', kind: 'accept', text: 'Accepting $0.84 with the split schedule as offered.' });
    t.push({ from: 'supplier', kind: 'accept', text: `Accepted. ${money(bundleTotal(opening))} across two deliveries.` });
    return out(opening, `Feasible. Lowest cash ${money(openingForecast.min)} on day ${openingForecast.minDay}.`);
  }

  // Search for the smallest schedule shift that keeps cash above the floor.
  const [t1, t2] = opening.deliveries;
  const per = opening.unitPrice;
  let best: { bundle: Bundle; shift: number; min: number } | null = null;
  for (let d1 = 1; d1 <= s.needByDay; d1++) {
    for (let d2 = d1; d2 <= s.needByDay; d2++) {
      const b: Bundle = {
        ...opening,
        deliveries: [
          { qty: t1.qty, day: d1 },
          { qty: t2.qty, day: d2 },
        ],
        payments: [
          { amount: Math.round(t1.qty * per), day: d1 },
          { amount: Math.round(t2.qty * per), day: d2 },
        ],
      };
      const f = forecast(s, b.payments);
      if (f.breach) continue;
      const shift = Math.abs(d1 - t1.day) + Math.abs(d2 - t2.day);
      if (!best || shift < best.shift || (shift === best.shift && f.min > best.min)) best = { bundle: b, shift, min: f.min };
    }
  }

  if (!best) {
    t.push({
      from: 'buyer',
      kind: 'walk',
      text: `${breachLine(openingForecast, s.floor)} No split schedule before day ${s.needByDay} fixes it. Standing down.`,
    });
    return out(null, breachLine(openingForecast, s.floor));
  }

  const moved = best.bundle.deliveries
    .map((d, i) => (d.day !== opening.deliveries[i].day ? `tranche ${i + 1} to day ${d.day}` : null))
    .filter(Boolean)
    .join(' and ');
  t.push({
    from: 'buyer',
    kind: 'counter',
    text: `Your original schedule fails: ${breachLine(openingForecast, s.floor)} Same price, same quantities. Move ${moved}?`,
    bundle: best.bundle,
    changed: ['deliveries', 'payments'],
  });
  t.push({
    from: 'supplier',
    kind: 'accept',
    text: `Accepted. ${describe(best.bundle)}.`,
    bundle: best.bundle,
  });
  return out(best.bundle, `Original terms failed; renegotiated to ${moved}.`, true);
}

export type Analysis = {
  base: Forecast;
  outcomes: DealOutcome[];
  ranked: DealOutcome[]; // agreed deals only, best first
  best: DealOutcome | null;
};

export function analyze(s: Scenario): Analysis {
  const base = forecast(s);
  const outcomes = suppliers.map((sup) => negotiate(sup, s, base));
  const ranked = outcomes
    .filter((o) => o.final)
    .sort((a, b) => bundleTotal(a.final!) - bundleTotal(b.final!) || b.finalForecast!.min - a.finalForecast!.min);
  return { base, outcomes, ranked, best: ranked[0] ?? null };
}

export const dealKey = (o: DealOutcome | null) =>
  o && o.final ? `${o.supplier.id}:${o.final.payments.map((p) => `${p.amount}@${p.day}`).join(',')}` : 'none';
