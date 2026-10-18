# DealRoom evaluation

124 negotiations, 1 companies. Savings = % below the current price, counting failed deals as 0%.

## All suppliers

| buyer | negotiations | avg saved | deal rate | avg rounds | ms per move | floor-guess error | $ per negotiation |
|---|---|---|---|---|---|---|---|
| split | 42 | 7.0% | 93% | 3.4 | 0.0 | n/a | $0.0000 |
| asi | 40 | 3.3% | 98% | 1.6 | 601.7 | n/a | $0.0000 |
| search | 42 | 9.2% | 88% | 3.8 | 1.8 | 2.9% | $0.0000 |

## Built-in supplier types

| buyer | negotiations | avg saved | deal rate | avg rounds | ms per move | floor-guess error | $ per negotiation |
|---|---|---|---|---|---|---|---|
| split | 24 | 7.3% | 92% | 3.2 | 0.0 | n/a | $0.0000 |
| asi | 24 | 3.3% | 96% | 1.6 | 605.0 | n/a | $0.0000 |
| search | 24 | 10.2% | 92% | 3.8 | 1.8 | 3.1% | $0.0000 |

## Held-out supplier types (never seen while building)

| buyer | negotiations | avg saved | deal rate | avg rounds | ms per move | floor-guess error | $ per negotiation |
|---|---|---|---|---|---|---|---|
| split | 18 | 6.7% | 94% | 3.6 | 0.0 | n/a | $0.0000 |
| asi | 16 | 3.3% | 100% | 1.7 | 563.7 | n/a | $0.0000 |
| search | 18 | 7.9% | 83% | 3.8 | 2.0 | 2.6% | $0.0000 |

## By supplier type (avg saved / deal rate)

| supplier | set | asi | search | split |
|---|---|---|---|---|
| stubborn | built | 2.8% / 100% | 8.5% / 100% | 6.0% / 100% |
| desperate | built | 4.0% / 100% | 13.4% / 100% | 10.2% / 100% |
| bluffer | built | 3.5% / 100% | 10.9% / 100% | 7.5% / 100% |
| walker | built | 2.9% / 83% | 8.2% / 67% | 5.4% / 67% |
| noisy | held-out | 3.5% / 100% | 9.7% / 100% | 6.8% / 100% |
| hardball | held-out | 2.6% / 100% | 5.6% / 100% | 3.8% / 100% |
| deadline | held-out | 4.0% / 100% | 8.3% / 50% | 9.5% / 83% |
