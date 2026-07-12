'use client';

/**
 * Interactive companion to the TangleDiagram: pick any function of
 * orders/service.py and see that the *used* imports change while the *loaded*
 * set never does — the import block runs whole, whichever name you came for.
 * Same visual language as the static diagrams (fd-* tokens, pm brand accents,
 * mono labels); renders fully lit around a default selection so the point
 * survives without JavaScript.
 */

import { useState } from 'react';

const mono = { fontFamily: 'var(--font-mono)' };

type DepId =
  | 'session'
  | 'payment_client'
  | 'mailer'
  | 'pdf_renderer'
  | 'stock_levels'
  | 'exchange_rates'
  | 'audit_log';

const DEPS: { id: DepId; cx: number; y: number }[] = [
  { id: 'session', cx: 330, y: 36 },
  { id: 'payment_client', cx: 472, y: 28 },
  { id: 'mailer', cx: 618, y: 36 },
  { id: 'pdf_renderer', cx: 348, y: 116 },
  { id: 'stock_levels', cx: 498, y: 108 },
  { id: 'exchange_rates', cx: 648, y: 116 },
  { id: 'audit_log', cx: 400, y: 196 },
];

const FUNCTIONS: { id: string; uses: DepId[] }[] = [
  { id: 'place_order', uses: ['session', 'payment_client', 'stock_levels', 'mailer'] },
  { id: 'cancel_order', uses: ['session', 'payment_client', 'stock_levels'] },
  {
    id: 'refund',
    uses: ['session', 'payment_client', 'mailer', 'exchange_rates', 'audit_log'],
  },
  { id: 'invoice_pdf', uses: ['session', 'pdf_renderer'] },
  { id: 'monthly_statement', uses: ['session', 'pdf_renderer', 'mailer'] },
  { id: 'export_orders', uses: ['session'] },
];

// the import block's spot on the module box; every "loaded" edge starts here
const ORIGIN: [number, number] = [252, 60];
const CONFIG: { cx: number; y: number } = { cx: 585, y: 196 };

const rowY = (i: number) => 88 + i * 32;
const depLeft = (d: { cx: number; y: number }): [number, number] => [d.cx - 54, d.y + 12];

export function BlastRadiusDiagram() {
  const [selected, setSelected] = useState('export_orders');
  const fn = FUNCTIONS.find((f) => f.id === selected) ?? FUNCTIONS[5];

  return (
    <figure className="not-prose my-8">
      <style>{`
        .pm-blast-row { cursor: pointer; }
        .pm-blast-row:focus { outline: none; }
        .pm-blast-row:hover rect, .pm-blast-row:focus-visible rect {
          stroke: var(--color-pm-cyan);
        }
        .pm-blast-loaded { animation: pm-blast-flash 700ms ease-out; }
        @keyframes pm-blast-flash {
          from { opacity: 1; }
          to { opacity: 0.55; }
        }
        @media (prefers-reduced-motion: reduce) {
          .pm-blast-loaded { animation: none; }
        }
      `}</style>
      <div className="overflow-x-auto rounded-xl border border-fd-border bg-fd-card/40 p-4">
        <svg
          viewBox="0 0 760 348"
          className="w-full min-w-140"
          role="group"
          aria-label="Interactive module graph: selecting any function of orders/service.py highlights the imports it uses, while the full set of seven imports is loaded regardless of the selection"
          style={mono}
        >
          {/* module box */}
          <rect
            x="16"
            y="16"
            width="236"
            height="296"
            rx="12"
            fill="var(--color-fd-card)"
            stroke="var(--color-fd-border)"
          />
          <text x="134" y="38" textAnchor="middle" fontSize="12" fill="var(--color-fd-foreground)">
            orders/service.py
          </text>
          <rect
            x="28"
            y="50"
            width="212"
            height="20"
            rx="6"
            fill="none"
            stroke="var(--color-pm-violet)"
            strokeWidth="1"
            strokeDasharray="3 3"
            opacity="0.7"
          />
          <text x="134" y="63.5" textAnchor="middle" fontSize="9" fill="var(--color-fd-muted-foreground)">
            import block · 7 imports
          </text>

          {/* loaded edges — identical whatever is selected; re-keyed to flash on change */}
          <g key={selected} className="pm-blast-loaded" opacity="0.55">
            {DEPS.map((d) => {
              const [x2, y2] = depLeft(d);
              return (
                <line
                  key={d.id}
                  x1={ORIGIN[0]}
                  y1={ORIGIN[1]}
                  x2={x2}
                  y2={y2}
                  stroke="var(--color-pm-violet)"
                  strokeWidth="1.2"
                />
              );
            })}
            {/* transitive, at import time: payments and mail read app config */}
            <line
              x1="472"
              y1="52"
              x2={CONFIG.cx - 20}
              y2={CONFIG.y}
              stroke="var(--color-pm-violet)"
              strokeWidth="1.2"
              strokeDasharray="3 3"
            />
            <line
              x1="618"
              y1="60"
              x2={CONFIG.cx + 10}
              y2={CONFIG.y}
              stroke="var(--color-pm-violet)"
              strokeWidth="1.2"
              strokeDasharray="3 3"
            />
          </g>

          {/* uses edges — from the selected function's row to what it actually needs */}
          <g>
            {fn.uses.map((id) => {
              const d = DEPS.find((dep) => dep.id === id);
              if (!d) return null;
              const [x2, y2] = depLeft(d);
              const i = FUNCTIONS.findIndex((f) => f.id === fn.id);
              return (
                <line
                  key={id}
                  x1="252"
                  y1={rowY(i) + 12}
                  x2={x2}
                  y2={y2}
                  stroke="var(--color-pm-cyan)"
                  strokeWidth="2"
                  opacity="0.9"
                />
              );
            })}
          </g>

          {/* function rows */}
          {FUNCTIONS.map((f, i) => {
            const active = f.id === selected;
            return (
              <g
                key={f.id}
                className="pm-blast-row"
                role="button"
                tabIndex={0}
                aria-pressed={active}
                aria-label={`${f.id}: uses ${f.uses.length} of 7 imports; importing it loads all 7`}
                onClick={() => setSelected(f.id)}
                onMouseEnter={() => setSelected(f.id)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    setSelected(f.id);
                  }
                }}
              >
                <rect
                  x="28"
                  y={rowY(i)}
                  width="212"
                  height="24"
                  rx="6"
                  fill="var(--color-fd-card)"
                  stroke={active ? 'var(--color-pm-cyan)' : 'var(--color-fd-border)'}
                  strokeWidth={active ? 1.5 : 1}
                />
                <text
                  x="38"
                  y={rowY(i) + 16}
                  fontSize="11"
                  fill={active ? 'var(--color-fd-foreground)' : 'var(--color-fd-muted-foreground)'}
                >
                  {f.id}
                </text>
              </g>
            );
          })}
          <text x="38" y="296" fontSize="10" fill="var(--color-fd-muted-foreground)">
            # ...nine more
          </text>

          {/* dependency nodes — all loaded, always */}
          {DEPS.map((d) => {
            const used = fn.uses.includes(d.id);
            return (
              <g key={d.id}>
                <rect
                  x={d.cx - 54}
                  y={d.y}
                  width="108"
                  height="24"
                  rx="8"
                  fill="var(--color-fd-card)"
                  stroke={used ? 'var(--color-pm-cyan)' : 'var(--color-pm-violet)'}
                  strokeWidth={used ? 1.6 : 1}
                  opacity={used ? 1 : 0.75}
                />
                <text
                  x={d.cx}
                  y={d.y + 16}
                  textAnchor="middle"
                  fontSize="9.5"
                  fill={used ? 'var(--color-fd-foreground)' : 'var(--color-fd-muted-foreground)'}
                >
                  {d.id}
                </text>
              </g>
            );
          })}

          {/* app config — reached transitively, at import time */}
          <g opacity="0.85">
            <rect
              x={CONFIG.cx - 54}
              y={CONFIG.y}
              width="108"
              height="24"
              rx="8"
              fill="var(--color-fd-card)"
              stroke="var(--color-pm-violet)"
              strokeWidth="1"
              strokeDasharray="3 3"
            />
            <text
              x={CONFIG.cx}
              y={CONFIG.y + 16}
              textAnchor="middle"
              fontSize="9.5"
              fill="var(--color-fd-muted-foreground)"
            >
              app config
            </text>
            <text
              x={CONFIG.cx}
              y={CONFIG.y + 38}
              textAnchor="middle"
              fontSize="8.5"
              fill="var(--color-fd-muted-foreground)"
            >
              read at import time
            </text>
          </g>

          {/* the score */}
          <text x="380" y="336" textAnchor="middle" fontSize="10.5" fill="var(--color-fd-muted-foreground)">
            <tspan fill="var(--color-pm-cyan)">
              {fn.id}() uses {fn.uses.length} of 7 imports
            </tspan>
            <tspan> — importing it </tspan>
            <tspan fill="var(--color-pm-violet)">runs all 7, every time</tspan>
          </text>
        </svg>
      </div>
      <figcaption className="mt-3 text-center text-sm text-fd-muted-foreground">
        What a function <em>uses</em> changes with the function. What calling it{' '}
        <em>loads</em> never does.
      </figcaption>
    </figure>
  );
}
