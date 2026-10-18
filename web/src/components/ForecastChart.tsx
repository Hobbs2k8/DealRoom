import {
  Area,
  ComposedChart,
  Line,
  ReferenceArea,
  ReferenceDot,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { money, type Forecast } from '@/engine';

type Props = {
  base: Forecast;
  deal?: Forecast | null;
  floor: number;
  height?: number;
  compact?: boolean;
  tone?: 'ok' | 'bad' | 'ink';
};

const toneColor = { ok: '#1f7a4d', bad: '#c2410c', ink: '#1a1915' };

export function ForecastChart({ base, deal, floor, height = 280, compact, tone = 'ink' }: Props) {
  const data = base.points.map((p, i) => ({ day: p.day, base: p.balance, deal: deal?.points[i].balance }));
  const primary = deal ?? base;
  const color = toneColor[tone];
  const yMax = 10000;
  const yMin = Math.min(0, Math.floor((primary.min - 500) / 1000) * 1000);
  const gid = `g-${tone}-${compact ? 'c' : 'f'}`;

  return (
    <ResponsiveContainer width='100%' height={height}>
      <ComposedChart data={data} margin={compact ? { top: 6, right: 6, bottom: 0, left: 6 } : { top: 12, right: 12, bottom: 4, left: 4 }}>
        <defs>
          <linearGradient id={gid} x1='0' y1='0' x2='0' y2='1'>
            <stop offset='0%' stopColor={color} stopOpacity={0.16} />
            <stop offset='100%' stopColor={color} stopOpacity={0} />
          </linearGradient>
        </defs>
        <ReferenceArea y1={yMin} y2={floor} fill='#c2410c' fillOpacity={0.05} ifOverflow='hidden' />
        <XAxis
          dataKey='day'
          hide={compact}
          tickLine={false}
          axisLine={{ stroke: '#e5e0d6' }}
          ticks={[0, 5, 10, 15, 20, 25, 30, 35]}
          tick={{ fontSize: 11, fill: '#a29d94', fontFamily: 'JetBrains Mono' }}
          tickFormatter={(d) => `d${d}`}
        />
        <YAxis
          hide={compact}
          domain={[yMin, yMax]}
          tickLine={false}
          axisLine={false}
          width={48}
          tick={{ fontSize: 11, fill: '#a29d94', fontFamily: 'JetBrains Mono' }}
          tickFormatter={(v) => `$${v / 1000}k`}
        />
        {!compact && (
          <Tooltip
            cursor={{ stroke: '#1a1915', strokeOpacity: 0.15 }}
            contentStyle={{
              background: '#fffdf9',
              border: '1px solid #e5e0d6',
              borderRadius: 12,
              fontSize: 12,
              boxShadow: '0 8px 24px rgba(26,25,21,0.08)',
            }}
            labelFormatter={(d) => `Day ${d}`}
            formatter={(v, name) => [money(Number(v)), name === 'base' ? (deal ? 'Without deal' : 'Cash') : 'With deal']}
          />
        )}
        <ReferenceLine
          y={floor}
          stroke='#b7791f'
          strokeDasharray='5 4'
          label={
            compact
              ? undefined
              : { value: `floor ${money(floor)}`, position: 'insideBottomRight', fill: '#b7791f', fontSize: 11, fontFamily: 'JetBrains Mono' }
          }
        />
        {deal ? (
          <>
            <Line type='stepAfter' dataKey='base' stroke='#a29d94' strokeWidth={1.25} strokeDasharray='3 3' dot={false} animationDuration={600} />
            <Area type='stepAfter' dataKey='deal' stroke={color} strokeWidth={2} fill={`url(#${gid})`} dot={false} animationDuration={600} />
          </>
        ) : (
          <Area type='stepAfter' dataKey='base' stroke={color} strokeWidth={2} fill={`url(#${gid})`} dot={false} animationDuration={600} />
        )}
        {primary.breach ? (
          <ReferenceDot
            x={primary.breach.day}
            y={primary.breach.balance}
            r={compact ? 4 : 6}
            fill='#c2410c'
            stroke='#fffdf9'
            strokeWidth={2}
          />
        ) : (
          <ReferenceDot x={primary.minDay} y={primary.min} r={compact ? 3.5 : 5} fill={color} stroke='#fffdf9' strokeWidth={2} />
        )}
      </ComposedChart>
    </ResponsiveContainer>
  );
}
