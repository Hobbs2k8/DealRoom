# DealRoom evaluation

420 negotiations, 1 companies. Savings = % below the current price, counting failed deals as 0%.

## All suppliers

| buyer | negotiations | avg saved | deal rate | avg rounds | ms per move | floor-guess error | $ per negotiation |
|---|---|---|---|---|---|---|---|
| split | 210 | 6.8% | 94% | 3.5 | 0.0 | n/a | $0.0000 |
| search | 210 | 9.1% | 92% | 4.0 | 1.8 | 2.6% | $0.0000 |

## Built-in supplier types

| buyer | negotiations | avg saved | deal rate | avg rounds | ms per move | floor-guess error | $ per negotiation |
|---|---|---|---|---|---|---|---|
| split | 120 | 7.2% | 96% | 3.4 | 0.0 | n/a | $0.0000 |
| search | 120 | 10.2% | 96% | 4.1 | 1.8 | 2.5% | $0.0000 |

## Held-out supplier types (never seen while building)

| buyer | negotiations | avg saved | deal rate | avg rounds | ms per move | floor-guess error | $ per negotiation |
|---|---|---|---|---|---|---|---|
| split | 90 | 6.2% | 92% | 3.7 | 0.0 | n/a | $0.0000 |
| search | 90 | 7.7% | 87% | 3.9 | 1.8 | 2.7% | $0.0000 |

## By supplier type (avg saved / deal rate)

| supplier | set | search | split |
|---|---|---|---|
| stubborn | built | 7.8% / 100% | 5.4% / 100% |
| desperate | built | 12.4% / 100% | 9.3% / 100% |
| bluffer | built | 10.8% / 100% | 7.3% / 100% |
| walker | built | 9.7% / 83% | 6.8% / 83% |
| noisy | held-out | 9.9% / 100% | 6.9% / 100% |
| hardball | held-out | 4.2% / 100% | 2.5% / 93% |
| deadline | held-out | 8.9% / 60% | 9.2% / 83% |
