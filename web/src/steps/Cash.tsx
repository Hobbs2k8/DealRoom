import { motion } from 'motion/react';
import type { ReactNode } from 'react';
import { ForecastChart } from '@/components/ForecastChart';
import { Agent, Button, Card, Money, StepHeader, StepNav } from '@/components/ui';
import { money, scenarioEvents } from '@/engine';
import { useFlow } from '@/flow';
import { cn } from '@/lib/utils';
import { business, delayableInvoiceId } from '@/mock';

export function CashStep() {
  const { analysis, scenario, next, back, delay } = useFlow();
  const { base } = analysis;
  const events = scenarioEvents(scenario);
  const headroom = base.min - scenario.floor;
  const nextInflow = events.find((e) => e.amount > 0 && e.day > base.minDay);

  const say = base.breach
    ? `Stop before we shop. Cafe Luna now pays on day ${events.find((e) => e.id === delayableInvoiceId)!.day}, so payroll on day ${base.breach.day} takes you to ${money(base.breach.balance)}. That's under your ${money(scenario.floor)} floor before you buy a single box.`
    : `Your tightest moment is day ${base.minDay}: ${money(base.min)} right after payroll, only ${money(headroom)} above your floor. Anything you pay before ${nextInflow ? `day ${nextInflow.day}` : 'the next inflow'} has to fit inside that ${money(headroom)}. That's the constraint I'll negotiate around.`;

  let running = business.startCash;
  const rows = events.map((e) => {
    running += e.amount;
    return { ...e, running };
  });

  return (
    <section>
      <StepHeader
        eyebrow='Step 2 · Cash picture'
        title='Your next 35 days, from the ledger'
        sub={`Pulled from ${business.ledgerSource}: opening balance, payroll, rent, and the invoices customers owe you.`}
      />

      <div className='mb-6 grid grid-cols-2 gap-3 md:grid-cols-4'>
        <Stat label='Cash today' value={<Money value={business.startCash} />} />
        <Stat
          label={`Lowest point · day ${base.minDay}`}
          value={<Money value={base.min} />}
          tone={base.breach ? 'bad' : undefined}
        />
        <Stat label='Reserve floor' value={<Money value={scenario.floor} />} tone='floor' />
        <Stat label='Headroom' value={<Money value={headroom} />} tone={headroom < 0 ? 'bad' : headroom < 500 ? 'floor' : 'ok'} />
      </div>

      <div className='grid gap-6 xl:grid-cols-[minmax(0,1fr)_380px]'>
        <Card className='p-4 sm:p-5'>
          <div className='mb-2 flex items-center justify-between'>
            <span className='text-sm font-medium'>Projected balance</span>
            <span className='font-mono text-[11px] text-faint'>no purchase yet</span>
          </div>
          <ForecastChart base={base} floor={scenario.floor} tone={base.breach ? 'bad' : 'ink'} height={300} />
        </Card>

        <Card className='overflow-hidden'>
          <div className='border-b border-line px-4 py-3 text-sm font-medium'>Scheduled in the books</div>
          <ul className='divide-y divide-line text-[13px]'>
            {rows.map((e) => {
              const isLuna = e.id === delayableInvoiceId;
              const hot = base.breach?.day === e.day || (!base.breach && base.minDay === e.day);
              return (
                <motion.li
                  layout
                  key={e.id}
                  transition={{ type: 'spring', bounce: 0.2, duration: 0.5 }}
                  className={cn('flex items-center gap-3 px-4 py-2.5', isLuna && delay > 0 && 'bg-floor-soft/60')}
                >
                  <span className='w-9 font-mono text-[11px] text-faint'>d{e.day}</span>
                  <span className='min-w-0 flex-1 truncate'>
                    {e.label}
                    {isLuna && delay > 0 ? <span className='ml-1 text-[11px] text-floor'>+{delay}d late</span> : null}
                  </span>
                  <span className={cn('tabular-nums', e.amount > 0 ? 'text-ok' : 'text-ink')}>
                    {e.amount > 0 ? '+' : '−'}${Math.abs(e.amount).toLocaleString()}
                  </span>
                  <span className={cn('w-14 text-right font-mono text-[11px] tabular-nums', hot ? 'text-bad' : 'text-faint')}>
                    {(e.running / 1000).toFixed(1)}k
                  </span>
                </motion.li>
              );
            })}
          </ul>
        </Card>
      </div>

      <div className='mt-8'>
        <Agent text={say} />
      </div>

      <StepNav>
        <Button variant='quiet' onClick={back}>
          ← Back
        </Button>
        <Button onClick={next}>Set my constraints →</Button>
      </StepNav>
    </section>
  );
}

function Stat({ label, value, tone }: { label: string; value: ReactNode; tone?: 'ok' | 'bad' | 'floor' }) {
  return (
    <Card className='px-4 py-3.5'>
      <p className='mb-1 text-[11px] text-muted'>{label}</p>
      <p
        className={cn(
          'font-display text-2xl tracking-tight',
          tone === 'bad' && 'text-bad',
          tone === 'ok' && 'text-ok',
          tone === 'floor' && 'text-floor'
        )}
      >
        {value}
      </p>
    </Card>
  );
}
