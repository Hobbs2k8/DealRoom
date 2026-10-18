# DealRoom web prototype

Clickable, fully mocked frontend for DealRoom: an AI buyer agent that negotiates purchases around a small business's cash constraint. No backend, no network calls.

```bash
cd web
npm install
npm run dev
```

## Where things live

- `src/mock.ts`: every hardcoded number (cash events, suppliers, opening bundles, ledger history). Swap for API calls later.
- `src/engine.ts`: pure logic. Cash forecast, floor checks, the scripted supplier negotiation, and ranking. No React.
- `src/flow.tsx`: in-memory app state (step, judge delay, floor, approval, execution).
- `src/steps/*`: the eight screens: Intake, Cash, Constraints, Offers, Negotiation, Compare, Approve, Execute.
- `src/components/core/*`: Motion Primitives (copied in, `'use client'` stripped).

## Judge control

The left rail on desktop and the bottom bar on mobile delay the Cafe Luna invoice by 0 to 14 days.

| Delay | Outcome |
| --- | --- |
| 0 to 1 | Bluebonnet $840 on original terms; Apex fails ($2,400 on d5) |
| 2 to 11 | Bluebonnet's original terms fail ($2,780 on d9); buyer moves the first delivery to d10, Bluebonnet accepts, $840 holds |
| 12+ | Payroll on d19 breaks the floor before any purchase: no deal exists |

Changing the delay after approval invalidates the approval; the owner must approve the new terms.
