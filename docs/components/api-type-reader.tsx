'use client';

import { ChevronLeft, ChevronRight, Pause, Play, RotateCcw } from 'lucide-react';
import { useEffect, useState } from 'react';

const LAST_STEP = 6;
const STEP_ANNOUNCEMENTS = [
  'OrderReceipt is the response returned after an order is placed.',
  'PlaceOrder is the request name.',
  'PlaceOrder is a request.',
  'PlaceOrder is a request for an OrderReceipt.',
  'PlaceOrderHandler is the handler name.',
  'PlaceOrderHandler handles requests.',
  'PlaceOrderHandler handles PlaceOrder requests.',
] as const;

function isActive(step: number, currentStep: number) {
  return currentStep === step;
}

export function ApiTypeReader() {
  const [step, setStep] = useState(-1);
  const [playing, setPlaying] = useState(false);

  useEffect(() => {
    if (!playing || step >= LAST_STEP) return;

    const timer = window.setTimeout(() => {
      const nextStep = step + 1;
      setStep(nextStep);
      if (nextStep >= LAST_STEP) setPlaying(false);
    }, 2000);
    return () => window.clearTimeout(timer);
  }, [playing, step]);

  const play = () => {
    if (step < 0 || step >= LAST_STEP) setStep(0);
    setPlaying(true);
  };

  const reset = () => {
    setPlaying(false);
    setStep(-1);
  };

  const previous = () => {
    setPlaying(false);
    setStep((current) => Math.max(-1, current - 1));
  };

  const next = () => {
    setPlaying(false);
    setStep((current) => Math.min(LAST_STEP, current + 1));
  };

  return (
    <figure className="not-prose my-8 overflow-hidden rounded-xl border border-fd-border bg-fd-card/40">
      <div className="grid gap-px bg-fd-border lg:grid-cols-[1.1fr_1fr]">
        <div className="min-w-0 bg-fd-background p-5 sm:p-7">
          <p className="mb-4 text-xs font-medium tracking-wide text-fd-muted-foreground uppercase">
            Python
          </p>
          <pre className="text-xs leading-7 sm:text-[0.95rem] sm:leading-8">
            <code className="whitespace-pre-wrap [overflow-wrap:anywhere]">
              <span className={isActive(0, step) ? 'pm-type-reader-active' : undefined}>
                class OrderReceipt:
              </span>
              {'\n    ...\n\n'}
              <span className={isActive(1, step) ? 'pm-type-reader-active' : undefined}>
                class PlaceOrder
              </span>
              <span className={isActive(2, step) ? 'pm-type-reader-active' : undefined}>
                (Request[
              </span>
              <span className={isActive(3, step) ? 'pm-type-reader-active' : undefined}>
                OrderReceipt
              </span>
              <span className={isActive(2, step) ? 'pm-type-reader-active' : undefined}>
                ]):
              </span>
              {'\n    ...\n\n'}
              <span className={isActive(4, step) ? 'pm-type-reader-active' : undefined}>
                class PlaceOrderHandler
              </span>
              <span className={isActive(5, step) ? 'pm-type-reader-active' : undefined}>
                (RequestHandler[
              </span>
              <span className={isActive(6, step) ? 'pm-type-reader-active' : undefined}>
                PlaceOrder
              </span>
              <span className={isActive(5, step) ? 'pm-type-reader-active' : undefined}>
                ]):
              </span>
              {'\n    ...'}
            </code>
          </pre>
          <p
            className="mt-5 border-t border-fd-border pt-4 text-sm leading-6 text-fd-muted-foreground lg:hidden"
            aria-hidden
          >
            <span className="font-medium text-fd-foreground">Current reading: </span>
            {step < 0
              ? 'Each declaration is paired with its reading.'
              : STEP_ANNOUNCEMENTS[step]}
          </p>
        </div>

        <div className="min-w-0 bg-fd-card p-5 sm:p-7">
          <p className="mb-4 text-xs font-medium tracking-wide text-fd-muted-foreground uppercase">
            Read it as
          </p>
          <div className="space-y-5 text-sm leading-7 sm:text-[0.95rem]">
            <p>
              <span className={isActive(0, step) ? 'pm-type-reader-active' : undefined}>
                <code>OrderReceipt</code> is the response returned after an order is placed.
              </span>
            </p>
            <p>
              <span className={isActive(1, step) ? 'pm-type-reader-active' : undefined}>
                <code>PlaceOrder</code>
              </span>{' '}
              <span className={isActive(2, step) ? 'pm-type-reader-active' : undefined}>
                is a request
              </span>{' '}
              <span className={isActive(3, step) ? 'pm-type-reader-active' : undefined}>
                for an <code>OrderReceipt</code>.
              </span>
            </p>
            <p>
              <span className={isActive(4, step) ? 'pm-type-reader-active' : undefined}>
                <code>PlaceOrderHandler</code>
              </span>{' '}
              <span className={isActive(5, step) ? 'pm-type-reader-active' : undefined}>
                handles
              </span>{' '}
              <span className={isActive(6, step) ? 'pm-type-reader-active' : undefined}>
                <code>PlaceOrder</code> requests.
              </span>
            </p>
          </div>
        </div>
      </div>

      <div className="pm-type-reader-controls flex flex-wrap items-center justify-between gap-3 border-t border-fd-border bg-fd-background px-5 py-3">
        <button
          type="button"
          onClick={playing ? () => setPlaying(false) : play}
          className="inline-flex items-center gap-2 rounded-md border border-fd-border px-3 py-1.5 text-sm font-medium hover:bg-fd-accent focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-fd-ring"
        >
          {playing ? <Pause aria-hidden className="size-4" /> : <Play aria-hidden className="size-4" />}
          {playing ? 'Pause' : step < 0 ? 'Play' : step >= LAST_STEP ? 'Replay' : 'Continue'}
        </button>

        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={previous}
            disabled={step < 0}
            aria-label="Previous part"
            className="rounded-md p-2 hover:bg-fd-accent disabled:opacity-40 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-fd-ring"
          >
            <ChevronLeft aria-hidden className="size-4" />
          </button>
          <span className="min-w-16 text-center text-xs tabular-nums text-fd-muted-foreground">
            {step < 0 ? 'Ready' : `${step + 1} of ${LAST_STEP + 1}`}
          </span>
          <button
            type="button"
            onClick={next}
            disabled={step >= LAST_STEP}
            aria-label="Next part"
            className="rounded-md p-2 hover:bg-fd-accent disabled:opacity-40 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-fd-ring"
          >
            <ChevronRight aria-hidden className="size-4" />
          </button>
          <button
            type="button"
            onClick={reset}
            aria-label="Reset type reading"
            className="ml-1 rounded-md p-2 hover:bg-fd-accent focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-fd-ring"
          >
            <RotateCcw aria-hidden className="size-4" />
          </button>
        </div>
      </div>
      <p className="sr-only" aria-live="polite" aria-atomic="true">
        {step < 0 ? 'The type-reading guide is ready.' : STEP_ANNOUNCEMENTS[step]}
      </p>
    </figure>
  );
}
