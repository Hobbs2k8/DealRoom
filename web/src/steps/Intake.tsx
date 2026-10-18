import { useEffect, useState } from 'react';
import { AnimatedGroup } from '@/components/core/animated-group';
import { Agent, Button, Card, StepHeader, StepNav } from '@/components/ui';
import { useFlow } from '@/flow';
import { business, intake } from '@/mock';

export function IntakeStep() {
  const { intakeSent, sendIntake, next } = useFlow();
  const [text, setText] = useState(intake.ownerMessage);
  const [parsing, setParsing] = useState(false);

  useEffect(() => {
    if (!parsing) return;
    const t = setTimeout(() => {
      setParsing(false);
      sendIntake();
    }, 1400);
    return () => clearTimeout(t);
  }, [parsing, sendIntake]);

  const n = intake.need;
  const fields = [
    ['Item', n.item],
    ['Quantity', `${n.quantity.toLocaleString()} boxes`],
    ['Needed by', `Day ${n.needByDay}`],
    ['Priority', n.priority],
  ];

  return (
    <section>
      <StepHeader
        eyebrow='Step 1 · Intake'
        title={`What do you need, ${business.owner}?`}
        sub='Say it the way you would to a person. The buyer agent turns it into something suppliers can quote on.'
      />

      <div className='space-y-6'>
        <div className='flex justify-end'>
          <div className='w-full max-w-xl'>
            <p className='mb-1.5 text-right text-xs font-medium text-muted'>{business.owner} · owner</p>
            <div className='rounded-2xl rounded-tr-md bg-ink p-1 text-paper'>
              <textarea
                value={text}
                onChange={(e) => setText(e.target.value)}
                disabled={intakeSent || parsing}
                rows={3}
                className='block w-full resize-none bg-transparent px-4 py-3 text-[15px] leading-relaxed outline-none placeholder:text-paper/40 disabled:opacity-90'
              />
              {!intakeSent && (
                <div className='flex justify-end p-2 pt-0'>
                  <button
                    type='button'
                    onClick={() => setParsing(true)}
                    disabled={parsing || !text.trim()}
                    className='rounded-full bg-paper px-4 py-1.5 text-sm font-medium text-ink disabled:opacity-50'
                  >
                    Send to buyer agent
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>

        {parsing && <Agent thinking='Reading your request and pulling out the parts a supplier needs…' />}

        {intakeSent && (
          <>
            <Agent text={intake.agentAck} />
            <Card className='ml-11 overflow-hidden'>
              <div className='flex items-center justify-between border-b border-line px-5 py-3'>
                <span className='text-sm font-medium'>Structured need</span>
                <span className='font-mono text-[11px] text-faint'>need_0193 · draft</span>
              </div>
              <AnimatedGroup preset='blur-slide' className='grid gap-px bg-line sm:grid-cols-2'>
                {fields.map(([k, v]) => (
                  <div key={k} className='bg-card px-5 py-4'>
                    <p className='mb-1 text-[11px] tracking-wide text-faint uppercase'>{k}</p>
                    <p className='text-[15px]'>{v}</p>
                  </div>
                ))}
              </AnimatedGroup>
            </Card>
          </>
        )}
      </div>

      <StepNav>
        <Button onClick={next} disabled={!intakeSent}>
          Read my books →
        </Button>
      </StepNav>
    </section>
  );
}
