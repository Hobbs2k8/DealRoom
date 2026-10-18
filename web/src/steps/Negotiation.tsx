import { AnimatePresence, motion } from 'motion/react';
import { useEffect, useState } from 'react';
import { AnimatedBackground } from '@/components/core/animated-background';
import { TextShimmer } from '@/components/core/text-shimmer';
import { AgentAvatar, Button, Card, Money, Pill, StepHeader, StepNav } from '@/components/ui';
import { bundleTotal, money, type DealOutcome, type Message } from '@/engine';
import { useFlow } from '@/flow';
import { cn } from '@/lib/utils';

const kindLabel: Record<Message['kind'], string> = {
  request: 'Request',
  offer: 'Offer',
  counter: 'Counter',
  accept: 'Accept',
  reject: 'Reject',
  walk: 'Walk away',
};

export function NegotiationStep() {
  const { analysis, next, back } = useFlow();
  const [tab, setTab] = useState<string>('bluebonnet');
  const active = analysis.outcomes.find((o) => o.supplier.id === tab)!;

  return (
    <section>
      <StepHeader
        eyebrow='Step 5 · Negotiation'
        title='Offer, counter, accept'
        sub='The buyer agent negotiates terms, not just price. A deal only exists when the supplier sends Accept.'
      />

      <div className='mb-5 flex flex-wrap gap-1 rounded-2xl border border-line bg-card/60 p-1'>
        <AnimatedBackground
          defaultValue={tab}
          onValueChange={(id) => id && setTab(id)}
          className='rounded-xl bg-card shadow-[0_1px_2px_rgba(26,25,21,0.08),0_0_0_1px_#e5e0d6]'
          transition={{ type: 'spring', bounce: 0.15, duration: 0.35 }}
        >
          {analysis.outcomes.map((o) => (
            <button
              key={o.supplier.id}
              data-id={o.supplier.id}
              type='button'
              className='min-w-0 flex-1 overflow-hidden rounded-xl px-3 py-2.5 text-left'
            >
              <span className='flex items-center gap-2'>
                <span className='size-2 shrink-0 rounded-full' style={{ background: o.supplier.accent }} />
                <span className='text-sm font-medium'>
                  <span className='sm:hidden'>{o.supplier.name.split(' ')[0]}</span>
                  <span className='hidden sm:inline'>{o.supplier.name}</span>
                </span>
              </span>
              <span className='mt-1 block'>
                <OutcomeChip o={o} />
              </span>
            </button>
          ))}
        </AnimatedBackground>
      </div>

      <Transcript outcome={active} />

      <StepNav>
        <Button variant='quiet' onClick={back}>
          ← Back
        </Button>
        <Button onClick={next}>Compare deals →</Button>
      </StepNav>
    </section>
  );
}

function OutcomeChip({ o }: { o: DealOutcome }) {
  if (!o.final) return <Pill tone='bad'>No agreement</Pill>;
  return <Pill tone='ok'>{o.renegotiated ? 'Agreed after counter' : 'Agreed'}</Pill>;
}

function Transcript({ outcome }: { outcome: DealOutcome }) {
  const sig = outcome.supplier.id + outcome.transcript.map((m) => m.kind + m.text).join('|');
  const [shown, setShown] = useState(1);

  useEffect(() => {
    setShown(1);
    const id = setInterval(() => {
      setShown((n) => {
        if (n >= outcome.transcript.length) {
          clearInterval(id);
          return n;
        }
        return n + 1;
      });
    }, 900);
    return () => clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sig]);

  const msgs = outcome.transcript.slice(0, shown);
  const done = shown >= outcome.transcript.length;
  const pending = outcome.transcript[shown];

  return (
    <Card className='p-4 sm:p-6'>
      <div className='space-y-4'>
        <AnimatePresence initial={false}>
          {msgs.map((m, i) => (
            <motion.div
              key={`${sig}-${i}`}
              initial={{ opacity: 0, y: 12, filter: 'blur(4px)' }}
              animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
              transition={{ duration: 0.35 }}
            >
              <Bubble m={m} outcome={outcome} />
            </motion.div>
          ))}
        </AnimatePresence>
        {!done && pending ? (
          <div className={cn('flex', pending.from === 'buyer' ? 'justify-end' : 'justify-start')}>
            <TextShimmer className='text-[13px]' duration={1.2}>
              {pending.from === 'buyer' ? 'Buyer agent is checking the forecast…' : `${outcome.supplier.agentName} is responding…`}
            </TextShimmer>
          </div>
        ) : null}
      </div>

      <AnimatePresence>
        {done ? (
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            className={cn(
              'mt-6 flex flex-wrap items-center gap-x-4 gap-y-1 rounded-xl px-4 py-3 text-sm',
              outcome.final ? 'bg-ok-soft text-ok' : 'bg-bad-soft text-bad'
            )}
          >
            {outcome.final ? (
              <>
                <span className='font-medium'>Agreement: {outcome.supplier.name} accepted</span>
                <span className='text-ink/70'>
                  <Money value={bundleTotal(outcome.final)} /> ·{' '}
                  {outcome.final.payments.map((p) => `${money(p.amount)} d${p.day}`).join(' + ')}
                </span>
              </>
            ) : (
              <span className='font-medium'>No agreement. The supplier never accepted terms that clear your floor.</span>
            )}
          </motion.div>
        ) : null}
      </AnimatePresence>
    </Card>
  );
}

function Bubble({ m, outcome }: { m: Message; outcome: DealOutcome }) {
  const buyer = m.from === 'buyer';
  const tone =
    m.kind === 'accept' ? 'ok' : m.kind === 'reject' || m.kind === 'walk' ? 'bad' : m.kind === 'counter' ? 'floor' : 'neutral';
  return (
    <div className={cn('flex gap-3', buyer && 'flex-row-reverse')}>
      {buyer ? (
        <AgentAvatar />
      ) : (
        <div
          className='grid size-8 shrink-0 place-items-center rounded-full text-[12px] font-semibold text-white'
          style={{ background: outcome.supplier.accent }}
        >
          {outcome.supplier.name[0]}
        </div>
      )}
      <div className={cn('max-w-[min(560px,85%)]', buyer && 'text-right')}>
        <div className={cn('mb-1 flex items-center gap-2 text-xs text-muted', buyer && 'justify-end')}>
          <span>{buyer ? 'Buyer agent' : outcome.supplier.agentName}</span>
          <Pill tone={tone}>{kindLabel[m.kind]}</Pill>
        </div>
        <div
          className={cn(
            'inline-block rounded-2xl px-4 py-3 text-left text-[14px] leading-relaxed',
            buyer ? 'rounded-tr-md bg-ink text-paper' : 'rounded-tl-md border border-line bg-paper'
          )}
        >
          {m.text}
          {m.bundle && m.kind !== 'offer' && m.kind !== 'accept' ? (
            <div className={cn('mt-3 grid gap-1 border-t pt-2.5 font-mono text-[11.5px]', buyer ? 'border-paper/15' : 'border-line')}>
              <TermLine label='price' value={`$${m.bundle.unitPrice.toFixed(2)}/box`} changed={m.changed?.includes('price')} dark={buyer} />
              <TermLine
                label='deliver'
                value={m.bundle.deliveries.map((d) => `${d.qty}@d${d.day}`).join(' + ')}
                changed={m.changed?.includes('deliveries')}
                dark={buyer}
              />
              <TermLine
                label='pay'
                value={m.bundle.payments.map((p) => `$${p.amount}@d${p.day}`).join(' + ')}
                changed={m.changed?.includes('payments')}
                dark={buyer}
              />
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}

function TermLine({ label, value, changed, dark }: { label: string; value: string; changed?: boolean; dark?: boolean }) {
  return (
    <div className='flex gap-3'>
      <span className={cn('w-14', dark ? 'text-paper/50' : 'text-faint')}>{label}</span>
      <span className={cn(changed && 'rounded px-1', changed && (dark ? 'bg-honey text-ink' : 'bg-floor-soft text-floor'))}>{value}</span>
    </div>
  );
}
