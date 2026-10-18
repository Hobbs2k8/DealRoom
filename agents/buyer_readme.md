# DealRoom Buyer Agent

![tag:negotiation](https://img.shields.io/badge/negotiation-3D8BD3)
![tag:procurement](https://img.shields.io/badge/procurement-3D8BD3)
![tag:quickbooks](https://img.shields.io/badge/quickbooks-3D8BD3)
![tag:small-business](https://img.shields.io/badge/small--business-3D8BD3)

A purchasing department for a small business that doesn't have one.

DealRoom reads the business's QuickBooks accounts payable (bills, payments, payroll runs, bank balance) and finds a supplier bill worth renegotiating: prices that crept up over the year, a long record of reliable payment, or bills due right next to payroll. It asks the owner whether to negotiate, haggles with the supplier's agent over price and payment timing (pay now vs. net 45), and asks the owner to approve the final deal. **Nothing is agreed without the owner's approval.**

## Talk to it

- `scan`: find the best negotiation opportunity and explain why
- `negotiate`: start negotiating with the supplier agent
- `passive`, `balanced`, `aggressive`: how hard to push
- `status`: current round, supplier ask, and the agent's guess of the supplier's floor
- `approve` / `decline`: accept or reject the deal the supplier agreed to

## Example

> **You:** scan
> **DealRoom:** Best opportunity: Ironclad Larkspur Outfitters, 255 croissant trays at $9.86. Price is up 12.7% this year; you've spent $437k with them and pay reliably.
> **You:** negotiate
> **DealRoom:** Ironclad accepted $8.81 (was $9.86), paid now. That saves $267.75. Reply 'approve' or 'decline'.

Demo data: synthetic QuickBooks books for Hearthloaf Bakeries (LA Hacks 2026 dataset).
