# DealRoom evaluation

28000 negotiations, 100 companies. Savings = % below the current price, counting failed deals as 0%.

## All suppliers

| buyer | negotiations | avg saved | deal rate | avg rounds | ms per move | floor-guess error | $ per negotiation |
|---|---|---|---|---|---|---|---|
| split | 14000 | 6.7% | 93% | 3.5 | 0.0 | n/a | $0.0000 |
| search | 14000 | 8.4% | 88% | 4.1 | 0.8 | 2.5% | $0.0000 |

## Built-in supplier types

| buyer | negotiations | avg saved | deal rate | avg rounds | ms per move | floor-guess error | $ per negotiation |
|---|---|---|---|---|---|---|---|
| split | 8000 | 7.2% | 97% | 3.4 | 0.0 | n/a | $0.0000 |
| search | 8000 | 9.6% | 94% | 4.2 | 0.8 | 2.5% | $0.0000 |

## Held-out supplier types (never seen while building)

| buyer | negotiations | avg saved | deal rate | avg rounds | ms per move | floor-guess error | $ per negotiation |
|---|---|---|---|---|---|---|---|
| split | 6000 | 6.0% | 88% | 3.7 | 0.0 | n/a | $0.0000 |
| search | 6000 | 6.8% | 81% | 4.0 | 0.8 | 2.4% | $0.0000 |

## By supplier type (avg saved / deal rate)

| supplier | set | search | split |
|---|---|---|---|
| stubborn | built | 7.6% / 100% | 5.5% / 100% |
| desperate | built | 12.1% / 100% | 9.4% / 100% |
| bluffer | built | 10.0% / 100% | 6.9% / 100% |
| walker | built | 8.6% / 76% | 7.0% / 89% |
| noisy | held-out | 10.0% / 100% | 7.0% / 100% |
| hardball | held-out | 4.2% / 100% | 2.9% / 90% |
| deadline | held-out | 6.2% / 43% | 8.2% / 75% |
