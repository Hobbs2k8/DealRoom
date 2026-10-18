import { AnimatePresence, motion } from 'motion/react';
import { BorderTrail } from '@/components/core/border-trail';
import { ForecastChart } from '@/components/ForecastChart';
import { Agent, Button, Card, Money, Pill, StepHeader, StepNav } from '@/components/ui';
import { bundleTotal, money, type DealOutcome } from '@/engine';
import { useFlow } from '@/flow';
import { cn } from '@/lib/utils';
import { cashEvents, delayableInvoiceId } from '@/mock';

export function CompareStep() {
  const { analysis, scenario, next, back } = useFlow();
  const { ranked, best, base } = analysis;
  const failed = analysis.outcomes.filter((o) => !o.final);
  const luna = cashEvents.find((e) => e.id === delayableInvoiceId)!;

  const say = best
    ? `${best.supplier.name} at ${money(bundleTotal(best.final!))} is the cheapest deal that never touches your floor${
        best.renegotiated ? ', but only after I moved the delivery dates' : ''
      }. ${ranked.length > 1 ? `${ranked[1].supplier.name} is the backup at ${money(bundleTotal(ranked[1].final!))}.` : ''}`
    : `No deal exists. Cafe Luna paying on day ${luna.day + scenario.delayDays} means payroll on day ${base.breach?.day} breaks your floor whatever I buy. Lower the floor to ${money(Math.floor(base.min / 100) * 100)} or get Cafe Luna to pay by day ${(base.breach?.day ?? 19) - 1}.`;

  return (
    <section>
      <StepHeader
        eyebrow='Step 6 · Compare'
        title='Every deal that survives your floor'
        sub='Ranked by total cost. Each one shows your cash under that deal, against what happens if you buy nothing.'
      />

      <div className='space-y-4'>
        <AnimatePresence mode='popLayout'>
          {ranked.map((o, i) => (
            <motion.div
              key={o.supplier.id}
              layout
              initial={{ opacity: 0, scale: 0.98 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.98 }}
              transition={{ type: 'spring', bounce: 0.15, duration: 0.5 }}
            >
              <DealCard o={o} rank={i + 1} best={i === 0} />
            </motion.div>
          ))}
          {!best && (
            <motion.div key='none' layout initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
              <Card className='border-bad/30 bg-bad-soft/40 p-6 sm:p-8'>
                <p className='font-display text-3xl tracking-tight text-bad'>No deal exists</p>
                <p className='mt-2 max-w-xl text-sm text-ink/80'>
                  Your cash breaks the {money(scenario.floor)} floor on day {base.breach?.day} even without buying anything. The
                  agent won't recommend a purchase it can't make safe.
                </p>
                <div className='mt-5 rounded-xl bg-card p-3'>
                  <ForecastChart base={base} floor={scenario.floor} tone='bad' height={180} />
                </div>
              </Card>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {failed.length > 0 && (
        <>
          <h2 className='mt-10 mb-3 font-mono text-[11px] tracking-[0.18em] text-faint uppercase'>Didn't make it</h2>
          <div className='grid gap-3 md:grid-cols-3'>
            {failed.map((o) => (
              <motion.div key={o.supplier.id} layout>
                <Card className='h-full p-4'>
                  <div className='mb-1 flex items-center justify-between gap-2'>
                    <span className='font-medium'>{o.supplier.name}</span>
                    <span className='text-sm text-muted line-through'>{money(bundleTotal(o.opening))}</span>
                  </div>
                  <p className='text-[13px] leading-snug text-bad'>{o.reason}</p>
                  <div className='mt-3 -mx-1'>
                    <ForecastChart base={base} deal={o.openingForecast} floor={scenario.floor} tone='bad' height={70} compact />
                  </div>
                </Card>
              </motion.div>
            ))}
          </div>
        </>
      )}

      <div className='mt-8'>
        <Agent text={say} />
      </div>

      <StepNav>
        <Button variant='quiet' onClick={back}>
          ← Back
        </Button>
        <Button onClick={next} disabled={!best}>
          Review & approve →
        </Button>
      </StepNav>
    </section>
  );
}

function DealCard({ o, rank, best }: { o: DealOutcome; rank: number; best: boolean }) {
  const { analysis, scenario } = useFlow();
  const b = o.final!;
  const f = o.finalForecast!;
  return (
    <Card className={cn('relative overflow-hidden p-5 sm:p-6', best && 'border-ink/20')}>
      {best && <BorderTrail className='bg-gradient-to-l from-honey via-honey to-transparent' size={160} transition={{ repeat: Infinity, duration: 6, ease: 'linear' }} />}
      <div className='grid gap-6 md:grid-cols-[minmax(0,260px)_minmax(0,1fr)]'>
        <div>
          <div className='mb-3 flex flex-wrap items-center gap-2'>
            <span className='font-mono text-[11px] text-faint'>#{rank}</span>
            {best && <Pill tone='ok'>Recommended</Pill>}
            {o.renegotiated && <Pill tone='floor'>Renegotiated</Pill>}
          </div>
          <p className='font-display text-2xl tracking-tight'>{o.supplier.name}</p>
          <p className='mt-1 font-display text-4xl tracking-tight'>
            <Money value={bundleTotal(b)} />
          </p>
          <dl className='mt-4 space-y-1.5 text-[13px]'>
            <div className='flex gap-3'>
              <dt className='w-20 text-faint'>Delivery</dt>
              <dd>{b.deliveries.map((d) => `${d.qty.toLocaleString()} d${d.day}`).join(' + ')}</dd>
            </div>
            <div className='flex gap-3'>
              <dt className='w-20 text-faint'>Payment</dt>
              <dd>{b.payments.map((p) => `${money(p.amount)} d${p.day}`).join(' + ')}</dd>
            </div>
            <div className='flex gap-3'>
              <dt className='w-20 text-faint'>Lowest cash</dt>
              <dd>
                <Money value={f.min} /> on d{f.minDay}
              </dd>
            </div>
          </dl>
          {o.renegotiated && o.openingForecast.breach ? (
            <p className='mt-3 text-[12px] leading-snug text-muted'>
              As first offered: <span className='text-bad'>{money(o.openingForecast.breach.balance)}</span> on day{' '}
              {o.openingForecast.breach.day}.
            </p>
          ) : null}
        </div>
        <div className='min-w-0'>
          <ForecastChart base={analysis.base} deal={f} floor={scenario.floor} tone={best ? 'ok' : 'ink'} height={200} />
        </div>
      </div>
    </Card>
  );
}
