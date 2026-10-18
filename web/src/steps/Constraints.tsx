import { Agent, Button, Card, Money, StepHeader, StepNav } from '@/components/ui';
import { money } from '@/engine';
import { useFlow } from '@/flow';
import { cn } from '@/lib/utils';
import { intake } from '@/mock';

export function ConstraintsStep() {
  const { floor, setFloor, quantityFirm, setQuantityFirm, analysis, constraintsLocked, lockConstraints, next, back } = useFlow();
  const headroom = analysis.base.min - floor;
  const bump = (d: number) => setFloor(Math.max(1000, Math.min(5000, floor + d)));

  return (
    <section>
      <StepHeader
        eyebrow='Step 3 · Confirm constraints'
        title='Two things only you can decide'
        sub="The agent won't guess at these. Whatever you set here is a hard rule for every offer it considers."
      />

      <div className='grid gap-4 md:grid-cols-2'>
        <Card className='p-6'>
          <p className='mb-1 text-[11px] tracking-wide text-faint uppercase'>Quantity</p>
          <p className='font-display text-4xl tracking-tight'>{intake.need.quantity.toLocaleString()} boxes</p>
          <p className='mt-1 text-sm text-muted'>by day {intake.need.needByDay}</p>
          <label className='mt-6 flex cursor-pointer items-start gap-3'>
            <button
              type='button'
              role='switch'
              aria-checked={quantityFirm}
              onClick={() => setQuantityFirm(!quantityFirm)}
              className={cn(
                'relative mt-0.5 h-6 w-10 shrink-0 rounded-full transition-colors',
                quantityFirm ? 'bg-ink' : 'bg-line'
              )}
            >
              <span
                className={cn(
                  'absolute top-1 left-1 size-4 rounded-full bg-paper transition-transform',
                  quantityFirm && 'translate-x-4'
                )}
              />
            </button>
            <span className='text-sm leading-snug'>
              <span className='font-medium'>Quantity is firm.</span>
              <span className='block text-muted'>
                Don't settle for fewer boxes to save cash. Splitting deliveries is fine; shrinking the order isn't.
              </span>
            </span>
          </label>
        </Card>

        <Card className='p-6'>
          <p className='mb-1 text-[11px] tracking-wide text-faint uppercase'>Reserve floor</p>
          <div className='flex items-center gap-3'>
            <button
              type='button'
              onClick={() => bump(-100)}
              className='grid size-9 place-items-center rounded-full border border-line text-lg hover:border-ink/30'
            >
              −
            </button>
            <p className='font-display text-4xl tracking-tight text-floor'>
              <Money value={floor} />
            </p>
            <button
              type='button'
              onClick={() => bump(100)}
              className='grid size-9 place-items-center rounded-full border border-line text-lg hover:border-ink/30'
            >
              +
            </button>
          </div>
          <input
            type='range'
            min={1000}
            max={5000}
            step={100}
            value={floor}
            onChange={(e) => setFloor(Number(e.target.value))}
            className='mt-5 w-full'
            aria-label='Reserve floor'
          />
          <p className='mt-4 text-sm text-muted'>
            Cash must never dip below this on any day.{' '}
            {headroom >= 0 ? (
              <>
                At the tightest point you'll have <Money value={headroom} className='font-medium text-ink' /> to spare.
              </>
            ) : (
              <span className='text-bad'>Your books already break this floor by {money(-headroom)}.</span>
            )}
          </p>
        </Card>
      </div>

      <div className='mt-8'>
        <Agent
          text={
            constraintsLocked
              ? `Locked: ${intake.need.quantity.toLocaleString()} boxes${quantityFirm ? ', firm' : ''}, cash never below ${money(floor)}. Sending the request to three supplier agents now.`
              : 'Confirm these and I\'ll ask suppliers for full bundles: price, delivery dates and payment dates. All three matter to your cash.'
          }
        />
      </div>

      <StepNav>
        <Button variant='quiet' onClick={back}>
          ← Back
        </Button>
        {constraintsLocked ? (
          <Button onClick={next}>See offers →</Button>
        ) : (
          <Button onClick={lockConstraints}>
            Lock constraints
          </Button>
        )}
      </StepNav>
    </section>
  );
}
