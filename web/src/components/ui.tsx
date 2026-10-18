import type { ReactNode } from 'react';
import { AnimatedNumber } from '@/components/core/animated-number';
import { TextEffect } from '@/components/core/text-effect';
import { TextShimmer } from '@/components/core/text-shimmer';
import { cn } from '@/lib/utils';
import { business, type Bundle } from '@/mock';

const spring = { stiffness: 120, damping: 20, mass: 0.6 };

export function Money({ value, cents, className }: { value: number; cents?: boolean; className?: string }) {
  return (
    <span className={cn('tabular-nums whitespace-nowrap', className)}>
      {value < 0 ? '−$' : '$'}
      <AnimatedNumber value={Math.abs(value)} springOptions={spring} />
      {cents ? '.00' : null}
    </span>
  );
}

export function Num({ value, className }: { value: number; className?: string }) {
  return <AnimatedNumber value={value} springOptions={spring} className={className} />;
}

export function StepHeader({ eyebrow, title, sub }: { eyebrow: string; title: string; sub?: ReactNode }) {
  return (
    <header className='mb-8'>
      <p className='mb-2 font-mono text-[11px] tracking-[0.18em] text-faint uppercase'>{eyebrow}</p>
      <h1 className='font-display text-3xl leading-tight font-medium tracking-tight text-ink sm:text-[2.5rem]'>
        {title}
      </h1>
      {sub ? <p className='mt-3 max-w-2xl text-[15px] leading-relaxed text-muted'>{sub}</p> : null}
    </header>
  );
}

export function AgentAvatar({ className }: { className?: string }) {
  return (
    <div
      className={cn(
        'relative grid size-8 shrink-0 place-items-center rounded-full bg-ink text-[13px] font-semibold text-paper',
        className
      )}
    >
      D
      <span className='absolute -right-0.5 -bottom-0.5 size-2.5 rounded-full border-2 border-paper bg-honey' />
    </div>
  );
}

export function Agent({ text, thinking, className }: { text?: string; thinking?: string; className?: string }) {
  return (
    <div className={cn('flex gap-3', className)}>
      <AgentAvatar />
      <div className='min-w-0 flex-1 pt-1'>
        <p className='mb-1 text-xs font-medium text-muted'>Buyer agent</p>
        {thinking ? (
          <TextShimmer className='text-[15px]' duration={1.4}>
            {thinking}
          </TextShimmer>
        ) : text ? (
          <TextEffect
            key={text}
            per='word'
            preset='fade-in-blur'
            speedReveal={3}
            speedSegment={1.5}
            className='text-[15px] leading-relaxed text-ink'
          >
            {text}
          </TextEffect>
        ) : null}
      </div>
    </div>
  );
}

export function Button({
  children,
  onClick,
  variant = 'primary',
  disabled,
  className,
}: {
  children: ReactNode;
  onClick?: () => void;
  variant?: 'primary' | 'ghost' | 'quiet';
  disabled?: boolean;
  className?: string;
}) {
  return (
    <button
      type='button'
      onClick={onClick}
      disabled={disabled}
      className={cn(
        'inline-flex h-10 items-center justify-center gap-2 rounded-full px-5 text-sm font-medium transition-all active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-40',
        variant === 'primary' && 'bg-ink text-paper hover:bg-ink/85',
        variant === 'ghost' && 'border border-line bg-card text-ink hover:border-ink/30',
        variant === 'quiet' && 'px-3 text-muted hover:text-ink',
        className
      )}
    >
      {children}
    </button>
  );
}

export function Card({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div className={cn('rounded-2xl border border-line bg-card shadow-[0_1px_0_rgba(26,25,21,0.04)]', className)}>
      {children}
    </div>
  );
}

export function Pill({ tone = 'neutral', children }: { tone?: 'neutral' | 'ok' | 'bad' | 'floor'; children: ReactNode }) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-[11px] font-medium whitespace-nowrap',
        tone === 'neutral' && 'bg-ink/5 text-muted',
        tone === 'ok' && 'bg-ok-soft text-ok',
        tone === 'bad' && 'bg-bad-soft text-bad',
        tone === 'floor' && 'bg-floor-soft text-floor'
      )}
    >
      {children}
    </span>
  );
}

export function StepNav({ children }: { children: ReactNode }) {
  return <div className='mt-10 flex flex-wrap items-center justify-end gap-2 border-t border-line pt-6'>{children}</div>;
}

// Day-by-day strip that shows when boxes arrive and when money leaves.
export function TermsStrip({ bundle, needBy, highlight }: { bundle: Bundle; needBy: number; highlight?: boolean }) {
  const H = business.horizonDays;
  const pct = (d: number) => `${(d / H) * 100}%`;
  return (
    <div className='relative mt-6 mb-6 h-10'>
      <div className='absolute top-1/2 right-0 left-0 h-px bg-line' />
      <div className='absolute top-1/2 h-px bg-ink/20' style={{ left: 0, width: pct(needBy) }} />
      <div className='absolute top-0 bottom-0 border-l border-dashed border-ink/30' style={{ left: pct(needBy) }}>
        <span className='absolute -top-3.5 -translate-x-1/2 font-mono text-[9px] whitespace-nowrap text-faint'>need by d{needBy}</span>
      </div>
      {bundle.deliveries.map((d, i) => (
        <div
          key={`d${i}`}
          className='absolute top-0 -translate-x-1/2 transition-all duration-500'
          style={{ left: pct(d.day) }}
          title={`${d.qty} boxes on day ${d.day}`}
        >
          <div className={cn('size-0 border-x-[6px] border-b-[9px] border-x-transparent', highlight ? 'border-b-ok' : 'border-b-ink')} />
        </div>
      ))}
      {bundle.payments.map((p, i) => (
        <div
          key={`p${i}`}
          className='absolute bottom-0 -translate-x-1/2 transition-all duration-500'
          style={{ left: pct(p.day) }}
          title={`$${p.amount} on day ${p.day}`}
        >
          <div className='size-2.5 rounded-full bg-honey ring-2 ring-card' />
          <span className='absolute top-3 left-1/2 -translate-x-1/2 font-mono text-[9px] whitespace-nowrap text-muted'>
            d{p.day}
          </span>
        </div>
      ))}
    </div>
  );
}

export function TermsLegend() {
  return (
    <div className='flex items-center gap-4 text-[11px] text-muted'>
      <span className='inline-flex items-center gap-1.5'>
        <span className='size-0 border-x-[5px] border-b-[8px] border-x-transparent border-b-ink' /> delivery
      </span>
      <span className='inline-flex items-center gap-1.5'>
        <span className='size-2 rounded-full bg-honey' /> payment
      </span>
    </div>
  );
}
