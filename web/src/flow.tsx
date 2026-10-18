import { createContext, useContext, useMemo, useState, type ReactNode } from 'react';
import { analyze, bundleTotal, dealKey, type Analysis, type DealOutcome, type Scenario } from '@/engine';
import { business, intake } from '@/mock';

export const STEPS = [
  { id: 'intake', title: 'Intake', hint: 'What you need' },
  { id: 'cash', title: 'Cash picture', hint: '35-day forecast' },
  { id: 'constraints', title: 'Constraints', hint: 'Floor & quantity' },
  { id: 'offers', title: 'Offers', hint: '3 supplier agents' },
  { id: 'negotiation', title: 'Negotiation', hint: 'Offer · counter · accept' },
  { id: 'compare', title: 'Compare', hint: 'Every feasible deal' },
  { id: 'approve', title: 'Approve', hint: 'Exact amount & terms' },
  { id: 'execute', title: 'Execute', hint: 'Checkout & ledger' },
] as const;

type Approval = { key: string; amount: number; supplier: string };
type Execution = { key: string; outcome: DealOutcome; delayDays: number };

type Flow = {
  step: number;
  setStep: (n: number) => void;
  next: () => void;
  back: () => void;
  reached: number;

  scenario: Scenario;
  analysis: Analysis;
  delay: number;
  setDelay: (n: number) => void;
  floor: number;
  setFloor: (n: number) => void;
  quantityFirm: boolean;
  setQuantityFirm: (b: boolean) => void;

  intakeSent: boolean;
  sendIntake: () => void;
  constraintsLocked: boolean;
  lockConstraints: () => void;

  approval: Approval | null;
  approvalValid: boolean;
  approve: () => void;
  execution: Execution | null;
  execute: () => void;
  reset: () => void;
};

const Ctx = createContext<Flow | null>(null);

export function FlowProvider({ children }: { children: ReactNode }) {
  const [step, setStepRaw] = useState(0);
  const [reached, setReached] = useState(0);
  const [delay, setDelay] = useState(0);
  const [floor, setFloor] = useState(business.defaultFloor);
  const [quantityFirm, setQuantityFirm] = useState(intake.need.quantityFirm);
  const [intakeSent, setIntakeSent] = useState(false);
  const [constraintsLocked, setConstraintsLocked] = useState(false);
  const [approval, setApproval] = useState<Approval | null>(null);
  const [execution, setExecution] = useState<Execution | null>(null);

  const scenario = useMemo<Scenario>(
    () => ({ delayDays: delay, floor, needByDay: intake.need.needByDay, quantity: intake.need.quantity }),
    [delay, floor]
  );
  const analysis = useMemo(() => analyze(scenario), [scenario]);
  const approvalValid = !!approval && approval.key === dealKey(analysis.best);

  const setStep = (n: number) => {
    const clamped = Math.max(0, Math.min(STEPS.length - 1, n));
    setStepRaw(clamped);
    setReached((r) => Math.max(r, clamped));
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const value: Flow = {
    step,
    setStep,
    next: () => setStep(step + 1),
    back: () => setStep(step - 1),
    reached,
    scenario,
    analysis,
    delay,
    setDelay,
    floor,
    setFloor,
    quantityFirm,
    setQuantityFirm,
    intakeSent,
    sendIntake: () => setIntakeSent(true),
    constraintsLocked,
    lockConstraints: () => setConstraintsLocked(true),
    approval,
    approvalValid,
    approve: () => {
      const best = analysis.best;
      if (!best?.final) return;
      setApproval({ key: dealKey(best), amount: bundleTotal(best.final), supplier: best.supplier.name });
    },
    execution,
    execute: () => {
      const best = analysis.best;
      if (!best || !approvalValid) return;
      setExecution({ key: dealKey(best), outcome: best, delayDays: delay });
    },
    reset: () => {
      setStepRaw(0);
      setReached(0);
      setDelay(0);
      setFloor(business.defaultFloor);
      setQuantityFirm(true);
      setIntakeSent(false);
      setConstraintsLocked(false);
      setApproval(null);
      setExecution(null);
    },
  };

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

// eslint-disable-next-line react-refresh/only-export-components
export function useFlow() {
  const v = useContext(Ctx);
  if (!v) throw new Error('useFlow outside FlowProvider');
  return v;
}
