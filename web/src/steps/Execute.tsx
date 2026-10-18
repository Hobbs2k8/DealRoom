import { AnimatePresence, motion } from 'motion/react';
import { useEffect, useState } from 'react';
import { TextShimmer } from '@/components/core/text-shimmer';
import { ForecastChart } from '@/components/ForecastChart';
import { Agent, Button, Card, Money, StepHeader, StepNav } from '@/components/ui';
import { bundleTotal, dealKey, money } from '@/engine';
import { useFlow } from '@/flow';
import { cn } from '@/lib/utils';
import { intake, ledgerHistory, orderNumbers } from '@/mock';

export function ExecuteStep() {
  const { analysis, approvalValid, execution, execute, back, setStep, reset, scenario } = useFlow();
  const [stage, setStage] = useState(execution ? 99 : -1);

  const deal = execution?.outcome ?? analysis.best;
  const stages = deal?.final
    ? [
        `Opening ${deal.supplier.storefront.domain}`,
        `Adding ${intake.need.quantity.toLocaleString()} × ${deal.supplier.storefront.sku} to cart`,
        'Applying negotiated delivery & payment schedule',
        `Confirming ${money(bundleTotal(deal.final), true)}, exactly as approved`,
        `Order ${orderNumbers[deal.supplier.id]} placed`,
      ]
    : [];

  useEffect(() => {
    if (stage < 0 || stage >= stages.length) return;
    const t = setTimeout(() => {
      if (stage === stages.length - 1) {
        execute();
        setStage(99);
      } else setStage(stage + 1);
    }, 1000);
    return () => clearTimeout(t);
  }, [stage, stages.length, execute]);

  if (!execution && (!approvalValid || !deal?.final)) {
    return (
      <section>
        <StepHeader eyebrow='Step 8 · Execute' title='Waiting on your approval' />
        <Agent text="I don't check out without a current approval from you. If the deal changed since you approved, I need you to look again." />
        <StepNav>
          <Button variant='quiet' onClick={back}>
            ← Back
          </Button>
          <Button onClick={() => setStep(6)}>Go to approval</Button>
        </StepNav>
      </section>
    );
  }

  const b = deal!.final!;
  const s = deal!.supplier;
  const done = stage === 99;
  const running = stage >= 0 && !done;
  const drifted = !!execution && execution.key !== dealKey(analysis.best);

  const newRows = done
    ? [
        {
          id: 'po',
          date: 'Day 0',
          account: 'Purchase order',
          memo: `${s.name} · ${orderNumbers[s.id]} · ${intake.need.quantity.toLocaleString()} boxes`,
          amount: 0,
          note: `${money(bundleTotal(b))} committed`,
        },
        ...b.payments.map((p, i) => ({
          id: `ap${i}`,
          date: `Day ${p.day}`,
          account: 'Accounts payable',
          memo: `${s.name} · ${b.deliveries[i] && b.deliveries[i].day === p.day ? `${b.deliveries[i].qty} boxes on delivery` : b.paymentTerms}`,
          amount: -p.amount,
          note: 'scheduled',
        })),
      ]
    : [];

  return (
    <section>
      <StepHeader
        eyebrow='Step 8 · Execute'
        title={done ? 'Bought, booked, and still above the floor' : `Checking out with ${s.name}`}
        sub='The agent completes checkout on the supplier storefront, then posts the purchase and its payment schedule to your ledger.'
      />

      {drifted && (
        <div className='mb-4 rounded-xl border border-line bg-card px-4 py-3 text-sm text-muted'>
          This order was placed with Cafe Luna {execution!.delayDays} days late. The judge control has moved since; the booked
          purchase below doesn't change.
        </div>
      )}

      <div className='grid gap-6 xl:grid-cols-2'>
        {/* Storefront */}
        <Card className='overflow-hidden'>
          <div className='flex items-center gap-2 border-b border-line bg-paper px-3 py-2'>
            <span className='flex gap-1'>
              <span className='size-2.5 rounded-full bg-line' />
              <span className='size-2.5 rounded-full bg-line' />
              <span className='size-2.5 rounded-full bg-line' />
            </span>
            <span className='ml-2 flex-1 truncate rounded-md bg-card px-3 py-1 font-mono text-[11px] text-muted'>
              https://{s.storefront.domain}/checkout
            </span>
          </div>
          <div className='px-5 py-4 text-white' style={{ background: s.accent }}>
            <p className='text-lg font-semibold tracking-tight'>{s.name}</p>
            <p className='text-xs opacity-80'>{s.storefront.tagline}</p>
          </div>
          <div className='space-y-4 p-5 text-sm'>
            <div className='flex items-center gap-4'>
              <div className='grid size-14 shrink-0 place-items-center rounded-lg bg-[#d9c7a7] text-[10px] font-medium text-[#6b5432]'>
                KRAFT
              </div>
              <div className='min-w-0 flex-1'>
                <p className='font-medium'>{intake.need.item}</p>
                <p className='font-mono text-[11px] text-faint'>{s.storefront.sku}</p>
              </div>
              <div className='text-right'>
                <p className='tabular-nums'>
                  {stage >= 1 ? intake.need.quantity.toLocaleString() : 0} × ${b.unitPrice.toFixed(2)}
                </p>
              </div>
            </div>
            <div
              className={cn(
                'rounded-lg border border-dashed p-3 transition-colors duration-500',
                stage >= 2 ? 'border-ok/50 bg-ok-soft/50' : 'border-line'
              )}
            >
              <p className='mb-1.5 text-[11px] tracking-wide text-faint uppercase'>Agent-negotiated terms</p>
              {b.deliveries.map((d, i) => (
                <p key={i} className='flex justify-between text-[13px]'>
                  <span>
                    Ship {d.qty.toLocaleString()} · day {d.day}
                  </span>
                  <span className='text-muted'>
                    {b.payments[i] ? `pay ${money(b.payments[i].amount)} · day ${b.payments[i].day}` : ''}
                  </span>
                </p>
              ))}
              {b.payments.length > b.deliveries.length || b.payments[0].day !== b.deliveries[0].day ? (
                <p className='mt-1 text-[12px] text-muted'>{b.paymentTerms}</p>
              ) : null}
            </div>
            <div className='flex items-center justify-between border-t border-line pt-4'>
              <span className='text-muted'>Order total</span>
              <span className='text-lg font-semibold tabular-nums'>
                <Money value={stage >= 1 ? bundleTotal(b) : 0} cents />
              </span>
            </div>
            <button
              type='button'
              disabled
              className='h-11 w-full rounded-lg text-sm font-semibold text-white transition-opacity'
              style={{ background: s.accent, opacity: stage >= 3 ? 1 : 0.5 }}
            >
              {done ? `✓ Order ${orderNumbers[s.id]} confirmed` : stage >= 3 ? 'Placing order…' : 'Place order'}
            </button>
          </div>
        </Card>

        {/* Agent log + ledger */}
        <div className='min-w-0 space-y-6'>
          <Card className='p-5'>
            <p className='mb-3 text-sm font-medium'>Agent checkout log</p>
            {stage === -1 ? (
              <div className='flex flex-col items-start gap-3'>
                <p className='text-sm text-muted'>
                  Approved: {money(bundleTotal(b), true)} to {s.name}. Ready when you are.
                </p>
                <Button onClick={() => setStage(0)}>Run checkout</Button>
              </div>
            ) : (
              <ol className='space-y-2 text-[13px]'>
                {stages.map((t, i) => {
                  const st = done || i < stage ? 'done' : i === stage ? 'now' : 'todo';
                  return (
                    <li key={t} className='flex items-center gap-3'>
                      <span
                        className={cn(
                          'grid size-5 shrink-0 place-items-center rounded-full text-[10px]',
                          st === 'done' && 'bg-ok text-white',
                          st === 'now' && 'border border-ink',
                          st === 'todo' && 'border border-line'
                        )}
                      >
                        {st === 'done' ? '✓' : ''}
                      </span>
                      {st === 'now' ? (
                        <TextShimmer className='text-[13px]' duration={1.2}>
                          {t}
                        </TextShimmer>
                      ) : (
                        <span className={cn(st === 'todo' && 'text-faint')}>{t}</span>
                      )}
                    </li>
                  );
                })}
              </ol>
            )}
          </Card>

          <Card className='overflow-hidden'>
            <div className='flex items-center justify-between border-b border-line px-5 py-3'>
              <span className='text-sm font-medium'>General ledger</span>
              <span className='font-mono text-[11px] text-faint'>{running ? 'syncing…' : done ? 'synced' : 'last 4 entries'}</span>
            </div>
            <ul className='divide-y divide-line text-[13px]'>
              {ledgerHistory.map((r) => (
                <li key={r.id} className='flex items-center gap-3 px-5 py-2.5 text-muted'>
                  <span className='w-14 shrink-0 font-mono text-[11px] text-faint'>{r.date}</span>
                  <span className='min-w-0 flex-1 truncate'>{r.memo}</span>
                  <span className='tabular-nums'>{r.amount > 0 ? '+' : '−'}${Math.abs(r.amount).toLocaleString()}</span>
                </li>
              ))}
              <AnimatePresence>
                {newRows.map((r, i) => (
                  <motion.li
                    key={r.id}
                    initial={{ opacity: 0, x: -12, backgroundColor: 'rgba(224,164,88,0.35)' }}
                    animate={{ opacity: 1, x: 0, backgroundColor: 'rgba(224,164,88,0.08)' }}
                    transition={{ delay: 0.25 * i, duration: 0.6 }}
                    className='flex items-center gap-3 px-5 py-2.5'
                  >
                    <span className='w-14 shrink-0 font-mono text-[11px] text-faint'>{r.date}</span>
                    <span className='min-w-0 flex-1'>
                      <span className='block truncate'>{r.memo}</span>
                      <span className='block text-[11px] text-faint'>
                        {r.account} · {r.note}
                      </span>
                    </span>
                    <span className='tabular-nums'>{r.amount ? `−$${Math.abs(r.amount).toLocaleString()}` : '—'}</span>
                  </motion.li>
                ))}
              </AnimatePresence>
            </ul>
          </Card>
        </div>
      </div>

      <AnimatePresence>
        {done && (
          <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.6 }} className='mt-6'>
            <Card className='p-4 sm:p-5'>
              <div className='mb-2 flex flex-wrap items-baseline justify-between gap-2'>
                <span className='text-sm font-medium'>Forecast with the purchase booked</span>
                <span className='text-sm text-muted'>
                  lowest <Money value={deal!.finalForecast!.min} className='text-ok' /> on d{deal!.finalForecast!.minDay}, floor{' '}
                  {money(scenario.floor)}
                </span>
              </div>
              <ForecastChart base={analysis.base} deal={deal!.finalForecast} floor={scenario.floor} tone='ok' height={200} />
            </Card>
            <div className='mt-6'>
              <Agent
                text={`Done. ${intake.need.quantity.toLocaleString()} boxes arrive by day ${Math.max(...b.deliveries.map((d) => d.day))}, ${money(bundleTotal(b))} leaves on the dates you approved, and your cash never drops below ${money(deal!.finalForecast!.min)}.`}
              />
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      <StepNav>
        <Button variant='quiet' onClick={back}>
          ← Back
        </Button>
        {done && (
          <Button variant='ghost' onClick={reset}>
            Start a new purchase
          </Button>
        )}
      </StepNav>
    </section>
  );
}
