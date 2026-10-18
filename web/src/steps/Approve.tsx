import { AnimatePresence, motion } from 'motion/react';
import { useEffect, useState } from 'react';
import { ForecastChart } from '@/components/ForecastChart';
import { Agent, Button, Card, Money, StepHeader, StepNav } from '@/components/ui';
import { bundleTotal, dealKey, money } from '@/engine';
import { useFlow } from '@/flow';
import { cn } from '@/lib/utils';
import { business, intake } from '@/mock';

export function ApproveStep() {
  const { analysis, scenario, approval, approvalValid, approve, next, back, setStep } = useFlow();
  const best = analysis.best;
  const [checked, setChecked] = useState(false);
  const key = dealKey(best);
  useEffect(() => setChecked(false), [key]);

  if (!best?.final) {
    return (
      <section>
        <StepHeader eyebrow='Step 7 · Approve' title='Nothing to approve' />
        <Agent text="There's no deal that keeps you above your floor right now, so I won't put one in front of you. Check the compare step for what would change that." />
        <StepNav>
          <Button variant='quiet' onClick={back}>
            ← Back
          </Button>
          <Button variant='ghost' onClick={() => setStep(5)}>
            Go to compare
          </Button>
        </StepNav>
      </section>
    );
  }

  const b = best.final;
  const total = bundleTotal(b);
  const f = best.finalForecast!;
  const stale = !!approval && !approvalValid;

  const lines = b.deliveries
    .map((d, i) => ({ day: d.day, qty: d.qty, pay: b.payments[i] && b.payments[i].day === d.day ? b.payments[i].amount : null }))
    .concat(
      b.payments
        .filter((p) => !b.deliveries.some((d) => d.day === p.day))
        .map((p) => ({ day: p.day, qty: 0, pay: p.amount }))
    )
    .sort((x, y) => x.day - y.day);

  return (
    <section>
      <StepHeader
        eyebrow='Step 7 · Approve'
        title={`Approve ${money(total, true)} to ${best.supplier.name}?`}
        sub='The agent can only spend what you approve here: this amount, these dates. Any change sends it back to you.'
      />

      <AnimatePresence>
        {stale && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className='mb-4 overflow-hidden'
          >
            <div className='rounded-xl border border-floor/40 bg-floor-soft px-4 py-3 text-sm text-floor'>
              The deal changed after you approved {money(approval!.amount)} to {approval!.supplier}. That approval no longer
              applies. Review the new terms below.
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      <div className='grid gap-6 lg:grid-cols-[minmax(0,420px)_minmax(0,1fr)]'>
        <Card className='relative overflow-hidden'>
          <div className='border-b border-dashed border-line px-6 pt-6 pb-5'>
            <p className='text-[11px] tracking-wide text-faint uppercase'>Purchase authorization</p>
            <p className='mt-2 font-display text-5xl tracking-tight'>
              <Money value={total} cents />
            </p>
            <p className='mt-1 text-sm text-muted'>
              {intake.need.quantity.toLocaleString()} × {intake.need.item.split(',')[0].toLowerCase()} @ ${b.unitPrice.toFixed(2)}
            </p>
          </div>
          <div className='px-6 py-4'>
            <p className='mb-2 text-[11px] tracking-wide text-faint uppercase'>Schedule</p>
            <ul className='space-y-2 text-sm'>
              {lines.map((l, i) => (
                <motion.li layout key={`${l.day}-${i}`} className='flex items-center gap-3'>
                  <span className='w-12 font-mono text-[12px] text-faint'>Day {l.day}</span>
                  <span className='flex-1'>{l.qty ? `${l.qty.toLocaleString()} boxes delivered` : 'Invoice due'}</span>
                  {l.pay ? <Money value={l.pay} cents className='font-medium' /> : <span className='text-faint'>—</span>}
                </motion.li>
              ))}
            </ul>
          </div>
          <div className='border-t border-dashed border-line px-6 py-4 text-[13px] text-muted'>
            <div className='flex justify-between'>
              <span>Payee</span>
              <span className='text-ink'>{best.supplier.name}</span>
            </div>
            <div className='mt-1 flex justify-between'>
              <span>Terms</span>
              <span className='text-ink'>{b.paymentTerms}</span>
            </div>
            <div className='mt-1 flex justify-between'>
              <span>Lowest cash after</span>
              <span className='text-ok'>
                <Money value={f.min} /> · d{f.minDay}
              </span>
            </div>
          </div>
          <AnimatePresence>
            {approvalValid && (
              <motion.div
                initial={{ opacity: 0, scale: 1.6, rotate: -18 }}
                animate={{ opacity: 1, scale: 1, rotate: -10 }}
                exit={{ opacity: 0 }}
                transition={{ type: 'spring', bounce: 0.4, duration: 0.5 }}
                className='pointer-events-none absolute top-8 right-6 rounded-lg border-2 border-ok px-3 py-1 font-mono text-sm font-medium tracking-widest text-ok uppercase'
              >
                Approved
              </motion.div>
            )}
          </AnimatePresence>
        </Card>

        <div className='min-w-0 space-y-6'>
          <Card className='p-4 sm:p-5'>
            <p className='mb-2 text-sm font-medium'>Your cash with this deal</p>
            <ForecastChart base={analysis.base} deal={f} floor={scenario.floor} tone='ok' height={220} />
          </Card>

          {!approvalValid ? (
            <Card className='p-5'>
              <label className='flex cursor-pointer items-start gap-3 text-sm leading-relaxed'>
                <input
                  type='checkbox'
                  checked={checked}
                  onChange={(e) => setChecked(e.target.checked)}
                  className='mt-1 size-4 accent-[#1a1915]'
                />
                <span>
                  I, {business.owner}, approve paying <strong>{money(total, true)}</strong> to {best.supplier.name}:{' '}
                  {b.payments.map((p) => `${money(p.amount, true)} on day ${p.day}`).join(' and ')}. The agent may not change
                  the amount, payee or dates without asking me again.
                </span>
              </label>
              <div className='mt-4 flex justify-end'>
                <Button onClick={approve} disabled={!checked} className={cn(!checked && 'opacity-40')}>
                  Approve {money(total, true)}
                </Button>
              </div>
            </Card>
          ) : (
            <Agent text={`Approved. I'll check out with ${best.supplier.name} at exactly ${money(total, true)} on the agreed dates and post it to your ledger.`} />
          )}
        </div>
      </div>

      <StepNav>
        <Button variant='quiet' onClick={back}>
          ← Back
        </Button>
        <Button onClick={next} disabled={!approvalValid}>
          Execute purchase →
        </Button>
      </StepNav>
    </section>
  );
}
