import { useEffect, useState } from 'react';
import { AnimatedGroup } from '@/components/core/animated-group';
import { Agent, Button, Card, Money, Pill, StepHeader, StepNav, TermsLegend, TermsStrip } from '@/components/ui';
import { bundleTotal, money } from '@/engine';
import { useFlow } from '@/flow';

let requestedOnce = false;

export function OffersStep() {
  const { analysis, scenario, next, back } = useFlow();
  const [loading, setLoading] = useState(!requestedOnce);

  useEffect(() => {
    if (!loading) return;
    const t = setTimeout(() => {
      requestedOnce = true;
      setLoading(false);
    }, 1600);
    return () => clearTimeout(t);
  }, [loading]);

  const apex = analysis.outcomes.find((o) => o.supplier.id === 'apex')!;
  const failing = analysis.outcomes.filter((o) => o.openingForecast.breach);
  const say = analysis.base.breach
    ? "Three bundles in. None of them matter yet: your books break the floor on their own. I'll show you why in negotiation."
    : `Three bundles in. ${apex.supplier.name} is cheapest at ${money(bundleTotal(apex.opening))}, but it wants the money on day ${apex.opening.payments[0].day}, before payroll. ${
        failing.length === 1
          ? 'That one breaks your floor as offered. The other two clear it.'
          : `${failing.length} of 3 break your floor as offered. Time to negotiate.`
      }`;

  return (
    <section>
      <StepHeader
        eyebrow='Step 4 · Offers'
        title='Three supplier agents answered'
        sub='Each one returned a structured bundle: unit price, delivery schedule, and when the money leaves your account.'
      />

      {loading ? (
        <Agent thinking='Requesting bundles from Apex, Bluebonnet and Cardinal…' />
      ) : (
        <>
          <div className='mb-3 flex justify-end'>
            <TermsLegend />
          </div>
          <AnimatedGroup preset='blur-slide' className='grid gap-4 lg:grid-cols-3'>
            {analysis.outcomes.map((o) => {
              const b = o.opening;
              const f = o.openingForecast;
              return (
                <Card key={o.supplier.id} className='flex h-full flex-col p-5'>
                  <div className='mb-4 flex items-start justify-between gap-2'>
                    <div>
                      <p className='font-display text-xl tracking-tight'>{o.supplier.name}</p>
                      <p className='text-xs text-faint'>
                        {o.supplier.agentName} · {o.supplier.city}
                      </p>
                    </div>
                    <span className='size-2.5 shrink-0 rounded-full' style={{ background: o.supplier.accent }} />
                  </div>
                  <div className='mb-1 flex items-baseline gap-2'>
                    <span className='font-display text-3xl tracking-tight'>${b.unitPrice.toFixed(2)}</span>
                    <span className='text-sm text-muted'>/ box</span>
                    <span className='ml-auto text-sm text-muted'>
                      total <Money value={bundleTotal(b)} className='font-medium text-ink' />
                    </span>
                  </div>
                  <TermsStrip bundle={b} needBy={scenario.needByDay} />
                  <dl className='space-y-1.5 text-[13px]'>
                    <Row k='Delivery' v={b.deliveries.map((d) => `${d.qty.toLocaleString()} on d${d.day}`).join(' + ')} />
                    <Row k='Payment' v={b.payments.map((p) => `${money(p.amount)} on d${p.day}`).join(' + ')} />
                    <Row k='Terms' v={b.paymentTerms} />
                  </dl>
                  <p className='mt-4 text-[12.5px] leading-snug text-muted'>{o.supplier.personaNote}</p>
                  <div className='mt-auto pt-4'>
                    {f.breach ? (
                      <Pill tone='bad'>
                        As offered: {money(f.breach.balance)} on day {f.breach.day}
                      </Pill>
                    ) : (
                      <Pill tone='ok'>As offered: clears floor, low {money(f.min)}</Pill>
                    )}
                  </div>
                </Card>
              );
            })}
          </AnimatedGroup>
          <div className='mt-8'>
            <Agent text={say} />
          </div>
        </>
      )}

      <StepNav>
        <Button variant='quiet' onClick={back}>
          ← Back
        </Button>
        <Button onClick={next} disabled={loading}>
          Negotiate →
        </Button>
      </StepNav>
    </section>
  );
}

function Row({ k, v }: { k: string; v: string }) {
  return (
    <div className='flex gap-3'>
      <dt className='w-16 shrink-0 text-faint'>{k}</dt>
      <dd className='min-w-0'>{v}</dd>
    </div>
  );
}
