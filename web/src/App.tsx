import { AnimatePresence, motion } from 'motion/react';
import { useEffect, useRef, useState } from 'react';
import { AnimatedBackground } from '@/components/core/animated-background';
import { TransitionPanel } from '@/components/core/transition-panel';
import { Money } from '@/components/ui';
import { bundleTotal, dealKey } from '@/engine';
import { FlowProvider, STEPS, useFlow } from '@/flow';
import { cn } from '@/lib/utils';
import { business, cashEvents, delayableInvoiceId } from '@/mock';
import { IntakeStep } from '@/steps/Intake';
import { CashStep } from '@/steps/Cash';
import { ConstraintsStep } from '@/steps/Constraints';
import { OffersStep } from '@/steps/Offers';
import { NegotiationStep } from '@/steps/Negotiation';
import { CompareStep } from '@/steps/Compare';
import { ApproveStep } from '@/steps/Approve';
import { ExecuteStep } from '@/steps/Execute';

export default function App() {
  return (
    <FlowProvider>
      <Shell />
    </FlowProvider>
  );
}

function Shell() {
  const { step } = useFlow();
  return (
    <div className='min-h-screen'>
      <TopBar />
      <div className='mx-auto grid max-w-[1320px] gap-8 px-4 pb-40 sm:px-6 lg:grid-cols-[248px_minmax(0,1fr)] lg:pb-16'>
        <aside className='hidden lg:block'>
          <div className='sticky top-[84px] space-y-6'>
            <Stepper />
            <JudgeControl />
          </div>
        </aside>
        <main className='min-w-0 pt-2 lg:pt-6'>
          <MobileStepper />
          <TransitionPanel
            activeIndex={step}
            transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
            variants={{
              enter: { opacity: 0, y: 14, filter: 'blur(4px)' },
              center: { opacity: 1, y: 0, filter: 'blur(0px)' },
              exit: { opacity: 0, y: -10, filter: 'blur(4px)' },
            }}
          >
            {[
              <IntakeStep key='intake' />,
              <CashStep key='cash' />,
              <ConstraintsStep key='constraints' />,
              <OffersStep key='offers' />,
              <NegotiationStep key='negotiation' />,
              <CompareStep key='compare' />,
              <ApproveStep key='approve' />,
              <ExecuteStep key='execute' />,
            ]}
          </TransitionPanel>
        </main>
      </div>
      <div className='fixed inset-x-0 bottom-0 z-30 border-t border-line bg-paper/95 px-4 py-3 backdrop-blur lg:hidden'>
        <JudgeControl compact />
      </div>
    </div>
  );
}

function TopBar() {
  const { reset } = useFlow();
  return (
    <div className='sticky top-0 z-40 border-b border-line bg-paper/85 backdrop-blur'>
      <div className='mx-auto flex h-16 max-w-[1320px] items-center gap-3 px-4 sm:px-6'>
        <button type='button' onClick={reset} className='flex items-center gap-2.5' title='Start over'>
          <img src='/favicon.svg' alt='' className='size-7' />
          <span className='font-display text-xl font-medium tracking-tight'>DealRoom</span>
        </button>
        <span className='hidden h-5 w-px bg-line sm:block' />
        <span className='hidden truncate text-sm text-muted sm:block'>{business.name}</span>
        <div className='ml-auto flex items-center gap-3'>
          <span className='rounded-full border border-dashed border-floor/60 bg-floor-soft px-3 py-1 font-mono text-[10.5px] tracking-wide text-floor uppercase'>
            <span className='sm:hidden'>Synthetic data</span>
            <span className='hidden sm:inline'>Synthetic data · simulated suppliers</span>
          </span>
        </div>
      </div>
    </div>
  );
}

function StepStatus({ i }: { i: number }) {
  const { step, reached } = useFlow();
  const done = i < reached || (i < step);
  return (
    <span
      className={cn(
        'grid size-6 shrink-0 place-items-center rounded-full border font-mono text-[11px] transition-colors',
        i === step ? 'border-ink bg-ink text-paper' : done ? 'border-ok/40 bg-ok-soft text-ok' : 'border-line text-faint'
      )}
    >
      {done && i !== step ? '✓' : i + 1}
    </span>
  );
}

function Stepper() {
  const { step, setStep } = useFlow();
  return (
    <nav>
      <p className='mb-3 px-3 font-mono text-[10.5px] tracking-[0.18em] text-faint uppercase'>Purchase · 1,000 boxes</p>
      <div className='flex flex-col'>
        <AnimatedBackground
          defaultValue={String(step)}
          onValueChange={(id) => id !== null && setStep(Number(id))}
          className='rounded-xl bg-card shadow-[0_1px_2px_rgba(26,25,21,0.06),0_0_0_1px_#e5e0d6]'
          transition={{ type: 'spring', bounce: 0.15, duration: 0.4 }}
        >
          {STEPS.map((s, i) => (
            <button key={s.id} data-id={String(i)} type='button' className='w-full rounded-xl px-3 py-2.5 text-left'>
              <span className='flex items-center gap-3'>
                <StepStatus i={i} />
                <span className='min-w-0'>
                  <span className={cn('block text-sm', i === step ? 'font-medium text-ink' : 'text-ink/80')}>{s.title}</span>
                  <span className='block text-[11.5px] text-faint'>{s.hint}</span>
                </span>
              </span>
            </button>
          ))}
        </AnimatedBackground>
      </div>
    </nav>
  );
}

function MobileStepper() {
  const { step, setStep } = useFlow();
  return (
    <div className='-mx-4 mb-6 flex gap-1.5 overflow-x-auto px-4 pb-1 lg:hidden'>
      {STEPS.map((s, i) => (
        <button
          key={s.id}
          type='button'
          onClick={() => setStep(i)}
          className={cn(
            'shrink-0 rounded-full border px-3 py-1.5 text-xs whitespace-nowrap',
            i === step ? 'border-ink bg-ink text-paper' : 'border-line bg-card text-muted'
          )}
        >
          {i + 1}. {s.title}
        </button>
      ))}
    </div>
  );
}

function JudgeControl({ compact }: { compact?: boolean }) {
  const { delay, setDelay, analysis } = useFlow();
  const luna = cashEvents.find((e) => e.id === delayableInvoiceId)!;
  const best = analysis.best;
  const key = dealKey(best);
  const prevKey = useRef(key);
  const [flash, setFlash] = useState(false);

  useEffect(() => {
    if (prevKey.current !== key) {
      prevKey.current = key;
      setFlash(true);
      const t = setTimeout(() => setFlash(false), 1400);
      return () => clearTimeout(t);
    }
  }, [key]);

  const outcome = (
    <AnimatePresence mode='popLayout' initial={false}>
      <motion.div
        key={key}
        initial={{ opacity: 0, y: 8, filter: 'blur(4px)' }}
        animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
        exit={{ opacity: 0, y: -8, filter: 'blur(4px)' }}
        transition={{ duration: 0.3 }}
        className='min-w-0'
      >
        {best?.final ? (
          <div className='flex items-baseline justify-between gap-2'>
            <span className='min-w-0 text-sm'>
              <span className='block truncate'>{best.supplier.name}</span>
              {best.renegotiated ? <span className='block text-[11px] text-floor'>renegotiated</span> : null}
            </span>
            <Money value={bundleTotal(best.final)} className='font-display text-lg' />
          </div>
        ) : (
          <div className='text-sm font-medium text-bad'>No deal exists</div>
        )}
      </motion.div>
    </AnimatePresence>
  );

  if (compact) {
    return (
      <div className='flex items-center gap-4'>
        <div className='w-[46%] shrink-0'>
          <div className='flex items-baseline justify-between text-[11px] text-muted'>
            <span>Delay Cafe Luna</span>
            <span className='font-mono text-ink'>+{delay}d</span>
          </div>
          <input
            type='range'
            min={0}
            max={14}
            value={delay}
            onChange={(e) => setDelay(Number(e.target.value))}
            className='mt-2 w-full'
            aria-label='Delay the Cafe Luna invoice by N days'
          />
        </div>
        <div className={cn('min-w-0 flex-1 rounded-lg px-2 py-1 transition-colors', flash && 'bg-honey/25')}>{outcome}</div>
      </div>
    );
  }

  return (
    <div
      className={cn(
        'rounded-2xl border border-dashed border-ink/25 bg-card/60 p-4 transition-shadow duration-500',
        flash && 'shadow-[0_0_0_4px_rgba(224,164,88,0.35)]'
      )}
    >
      <div className='mb-3 flex items-center justify-between'>
        <span className='font-mono text-[10.5px] tracking-[0.18em] text-faint uppercase'>Judge control</span>
        {delay > 0 ? (
          <button type='button' onClick={() => setDelay(0)} className='text-[11px] text-muted hover:text-ink'>
            reset
          </button>
        ) : null}
      </div>
      <label className='block text-sm leading-snug'>
        Delay the Cafe Luna invoice by{' '}
        <span className='inline-block min-w-[2ch] rounded bg-ink px-1.5 text-center font-mono text-paper'>{delay}</span> days
      </label>
      <input
        type='range'
        min={0}
        max={14}
        value={delay}
        onChange={(e) => setDelay(Number(e.target.value))}
        className='mt-4 w-full'
        aria-label='Delay the Cafe Luna invoice by N days'
      />
      <div className='mt-1.5 flex justify-between font-mono text-[10px] text-faint'>
        <span>on time</span>
        <span>pays day {luna.day + delay}</span>
      </div>
      <div className='mt-4 border-t border-line pt-3'>
        <p className='mb-1 text-[11px] text-muted'>Best deal right now</p>
        {outcome}
      </div>
    </div>
  );
}
