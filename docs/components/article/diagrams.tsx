/**
 * Static SVG illustrations for the articles collection, in the same visual
 * language as the home page's dispatch-flow diagram: fd-* theme tokens for
 * fills and strokes, the cyan→violet brand gradient for emphasis, mono labels.
 */

const mono = { fontFamily: 'var(--font-mono)' };

function Node({ x, y, label }: { x: number; y: number; label: string }) {
  return (
    <g>
      <circle cx={x} cy={y} r="4" fill="var(--color-fd-muted-foreground)" />
      <text
        x={x}
        y={y + 16}
        textAnchor="middle"
        fontSize="9.5"
        fill="var(--color-fd-muted-foreground)"
      >
        {label}
      </text>
    </g>
  );
}

function Edge({
  from,
  to,
  accent = false,
}: {
  from: [number, number];
  to: [number, number];
  accent?: boolean;
}) {
  return (
    <line
      x1={from[0]}
      y1={from[1]}
      x2={to[0]}
      y2={to[1]}
      stroke={accent ? 'var(--color-pm-violet)' : 'var(--color-fd-border)'}
      strokeWidth={accent ? 1.4 : 1.2}
      opacity={accent ? 0.85 : 1}
    />
  );
}

/** The same modules over three years: the nodes barely change, the edges take over. */
export function TangleDiagram() {
  // panel-local node positions, shared across panels so growth reads as edges, not layout
  const p: Record<string, [number, number]> = {
    routes: [115, 32],
    orders: [45, 92],
    billing: [185, 92],
    customers: [45, 162],
    mailer: [185, 162],
    db: [115, 124],
    pdf: [152, 196],
    payments: [78, 196],
  };
  const panel = (
    origin: number,
    nodes: (keyof typeof p)[],
    edges: [keyof typeof p, keyof typeof p, boolean?][],
    caption: string,
    count: string,
  ) => (
    <g transform={`translate(${origin} 0)`}>
      {edges.map(([a, b, accent]) => (
        <Edge key={`${a}-${b}`} from={p[a]} to={p[b]} accent={accent} />
      ))}
      {nodes.map((n) => (
        <Node key={n} x={p[n][0]} y={p[n][1]} label={n} />
      ))}
      <text
        x="115"
        y="240"
        textAnchor="middle"
        fontSize="11"
        fill="var(--color-fd-foreground)"
      >
        {caption}
      </text>
      <text
        x="115"
        y="256"
        textAnchor="middle"
        fontSize="9.5"
        fill="var(--color-fd-muted-foreground)"
      >
        {count}
      </text>
    </g>
  );

  return (
    <figure className="not-prose my-8">
      <div className="overflow-x-auto rounded-xl border border-fd-border bg-fd-card/40 p-4">
        <svg
          viewBox="0 0 760 268"
          className="w-full min-w-140"
          role="img"
          aria-label="Three snapshots of the same module graph: two edges in the first month, eight after year one, and a dense tangle including circular dependencies by year three"
          style={mono}
        >
          {panel(
            10,
            ['routes', 'orders', 'db'],
            [
              ['routes', 'orders'],
              ['orders', 'db'],
            ],
            'the first month',
            '3 modules · 2 edges',
          )}
          {panel(
            265,
            ['routes', 'orders', 'billing', 'customers', 'mailer', 'db'],
            [
              ['routes', 'orders'],
              ['routes', 'billing'],
              ['orders', 'db'],
              ['billing', 'db'],
              ['orders', 'billing'],
              ['billing', 'mailer'],
              ['customers', 'orders'],
              ['customers', 'db'],
            ],
            'year one',
            '6 modules · 8 edges',
          )}
          {panel(
            520,
            ['routes', 'orders', 'billing', 'customers', 'mailer', 'db', 'pdf', 'payments'],
            [
              ['routes', 'orders'],
              ['routes', 'billing'],
              ['routes', 'customers'],
              ['orders', 'db'],
              ['billing', 'db'],
              ['customers', 'db'],
              ['orders', 'billing', true],
              ['billing', 'orders', true],
              ['billing', 'mailer'],
              ['orders', 'mailer'],
              ['customers', 'mailer'],
              ['customers', 'orders', true],
              ['orders', 'customers', true],
              ['orders', 'pdf'],
              ['billing', 'payments'],
              ['payments', 'orders'],
              ['pdf', 'db'],
              ['customers', 'billing'],
            ],
            'year three',
            '8 modules · 18 edges · cycles',
          )}
        </svg>
      </div>
      <figcaption className="mt-3 text-center text-sm text-fd-muted-foreground">
        The modules barely change. The <em>knowledge between them</em> is what grows — and by
        year three some of it points both ways.
      </figcaption>
    </figure>
  );
}

/** The staircase of prerequisite changes hiding behind one simple request. */
export function CascadeDiagram() {
  const steps: { x: number; y: number; w: number; label: string; first?: boolean }[] = [
    { x: 12, y: 18, w: 212, label: 'move the export to a worker', first: true },
    { x: 152, y: 76, w: 176, label: 'imports orders.service' },
    { x: 258, y: 134, w: 252, label: 'which imports payments, mailer, pdf…' },
    { x: 416, y: 192, w: 188, label: 'which need the app context' },
    { x: 548, y: 250, w: 184, label: 'which needs a live request' },
  ];
  return (
    <figure className="not-prose my-8">
      <div className="overflow-x-auto rounded-xl border border-fd-border bg-fd-card/40 p-4">
        <svg
          viewBox="0 0 760 316"
          className="w-full min-w-140"
          role="img"
          aria-label="A staircase of five boxes descending to the right: the change you wanted at the top, followed by the chain of imports and ambient context it turned out to require"
          style={mono}
        >
          <defs>
            <linearGradient id="pm-cascade-g" x1="0" y1="0" x2="1" y2="1">
              <stop offset="0" stopColor="#22d3ee" />
              <stop offset="1" stopColor="#8b5cf6" />
            </linearGradient>
            <marker
              id="pm-cascade-arrow"
              viewBox="0 0 8 8"
              refX="7"
              refY="4"
              markerWidth="7"
              markerHeight="7"
              orient="auto-start-reverse"
            >
              <path d="M0 0 L8 4 L0 8 z" fill="var(--color-fd-muted-foreground)" />
            </marker>
          </defs>
          {steps.map((s, i) => {
            const next = steps[i + 1];
            return (
              <g key={s.label}>
                <rect
                  x={s.x}
                  y={s.y}
                  width={s.w}
                  height="36"
                  rx="10"
                  fill="var(--color-fd-card)"
                  stroke={s.first ? 'url(#pm-cascade-g)' : 'var(--color-fd-border)'}
                  strokeWidth={s.first ? 1.4 : 1}
                />
                <text
                  x={s.x + s.w / 2}
                  y={s.y + 23}
                  textAnchor="middle"
                  fontSize="11.5"
                  fill="var(--color-fd-foreground)"
                >
                  {s.label}
                </text>
                {next && (
                  <path
                    d={`M${s.x + s.w / 2 + 46} ${s.y + 36} L${s.x + s.w / 2 + 46} ${next.y + 18} L${next.x - 4} ${next.y + 18}`}
                    fill="none"
                    stroke="var(--color-fd-muted-foreground)"
                    strokeWidth="1.2"
                    markerEnd="url(#pm-cascade-arrow)"
                  />
                )}
              </g>
            );
          })}
          <text x="12" y="72" fontSize="10" fill="var(--color-fd-muted-foreground)">
            the change you asked for
          </text>
          <text x="548" y="306" fontSize="10" fill="var(--color-fd-muted-foreground)">
            the change you got
          </text>
        </svg>
      </div>
      <figcaption className="mt-3 text-center text-sm text-fd-muted-foreground">
        Change amplification: each step is discovered only after committing to the previous
        one, so the true cost is invisible from the top of the stairs.
      </figcaption>
    </figure>
  );
}

/** Before/after: what the call site has to know, with and without a seam. */
export function SeamDiagram() {
  return (
    <figure className="not-prose my-8">
      <div className="overflow-x-auto rounded-xl border border-fd-border bg-fd-card/40 p-4">
        <svg
          viewBox="0 0 760 252"
          className="w-full min-w-140"
          role="img"
          aria-label="Before: the call site connects directly to the module, its import block, and the framework. After: the call site connects only to a message that crosses a seam; the handler on the far side owns the dependencies"
          style={mono}
        >
          <style>{`
            .pm-seam-msg {
              transform: translate(580px, 87px);
              opacity: 0.95;
              animation: pm-seam-cross 3.2s ease-in-out infinite;
            }
            @keyframes pm-seam-cross {
              0% { transform: translate(524px, 87px); opacity: 0; }
              12% { opacity: 0.95; }
              55% { transform: translate(636px, 87px); opacity: 0.95; }
              68% { transform: translate(636px, 87px); opacity: 0; }
              100% { transform: translate(636px, 87px); opacity: 0; }
            }
            @media (prefers-reduced-motion: reduce) {
              .pm-seam-msg { animation: none; opacity: 0; }
            }
          `}</style>
          <defs>
            <linearGradient id="pm-seam-g" x1="0" y1="0" x2="1" y2="1">
              <stop offset="0" stopColor="#22d3ee" />
              <stop offset="1" stopColor="#8b5cf6" />
            </linearGradient>
          </defs>

          {/* before */}
          <g>
            <rect
              x="100"
              y="20"
              width="120"
              height="34"
              rx="10"
              fill="var(--color-fd-card)"
              stroke="var(--color-fd-border)"
            />
            <text x="160" y="42" textAnchor="middle" fontSize="11.5" fill="var(--color-fd-foreground)">
              call site
            </text>
            {(
              [
                [62, 118, 'orders.service'],
                [165, 118, 'its import block'],
                [268, 118, 'db session'],
                [112, 168, 'mailer'],
                [218, 168, 'app config'],
              ] as [number, number, string][]
            ).map(([cx, cy, label]) => (
              <g key={label}>
                <line
                  x1="160"
                  y1="54"
                  x2={cx}
                  y2={cy}
                  stroke="var(--color-fd-border)"
                  strokeWidth="1.2"
                />
                <rect
                  x={cx - 46}
                  y={cy}
                  width="92"
                  height="26"
                  rx="8"
                  fill="var(--color-fd-card)"
                  stroke="var(--color-fd-border)"
                />
                <text
                  x={cx}
                  y={cy + 17}
                  textAnchor="middle"
                  fontSize="9"
                  fill="var(--color-fd-muted-foreground)"
                >
                  {label}
                </text>
              </g>
            ))}
            <text x="160" y="205" textAnchor="middle" fontSize="11" fill="var(--color-fd-foreground)">
              before
            </text>
            <text
              x="160"
              y="222"
              textAnchor="middle"
              fontSize="9.5"
              fill="var(--color-fd-muted-foreground)"
            >
              the call site knows how
            </text>
          </g>

          {/* divider */}
          <line
            x1="380"
            y1="20"
            x2="380"
            y2="230"
            stroke="var(--color-fd-border)"
            strokeWidth="1"
          />

          {/* after */}
          <g>
            <rect
              x="420"
              y="70"
              width="100"
              height="34"
              rx="10"
              fill="var(--color-fd-card)"
              stroke="var(--color-fd-border)"
            />
            <text x="470" y="92" textAnchor="middle" fontSize="11.5" fill="var(--color-fd-foreground)">
              call site
            </text>

            <line x1="520" y1="87" x2="556" y2="87" stroke="var(--color-fd-border)" strokeWidth="1.2" />
            {/* the message: a static outline marks its lane; a filled twin crosses the seam */}
            <path
              d="M580 71 L596 87 L580 103 L564 87 Z"
              fill="none"
              stroke="url(#pm-seam-g)"
              strokeWidth="1.2"
              opacity="0.55"
            />
            <path className="pm-seam-msg" d="M0 -8 L8 0 L0 8 L-8 0 Z" fill="url(#pm-seam-g)" />
            <text
              x="580"
              y="126"
              textAnchor="middle"
              fontSize="9.5"
              fill="var(--color-fd-muted-foreground)"
            >
              ExportOrders
            </text>

            {/* the seam */}
            <line
              x1="620"
              y1="40"
              x2="620"
              y2="180"
              stroke="var(--color-pm-violet)"
              strokeWidth="1.2"
              strokeDasharray="4 4"
              opacity="0.7"
            />
            <text x="620" y="30" textAnchor="middle" fontSize="9.5" fill="var(--color-fd-muted-foreground)">
              the seam
            </text>

            <rect
              x="638"
              y="70"
              width="108"
              height="34"
              rx="10"
              fill="var(--color-fd-card)"
              stroke="var(--color-fd-border)"
            />
            <text x="692" y="92" textAnchor="middle" fontSize="11.5" fill="var(--color-fd-foreground)">
              handler
            </text>
            <line x1="602" y1="87" x2="638" y2="87" stroke="var(--color-fd-border)" strokeWidth="1.2" />

            {(
              [
                [660, 'db session'],
                [724, 'storage'],
              ] as [number, string][]
            ).map(([cx, label]) => (
              <g key={label}>
                <line
                  x1="692"
                  y1="104"
                  x2={cx}
                  y2="150"
                  stroke="var(--color-fd-border)"
                  strokeWidth="1.2"
                />
                <rect
                  x={cx - 32}
                  y={150}
                  width="64"
                  height="24"
                  rx="8"
                  fill="var(--color-fd-card)"
                  stroke="var(--color-fd-border)"
                />
                <text
                  x={cx}
                  y={166}
                  textAnchor="middle"
                  fontSize="8.5"
                  fill="var(--color-fd-muted-foreground)"
                >
                  {label}
                </text>
              </g>
            ))}
            <text x="570" y="205" textAnchor="middle" fontSize="11" fill="var(--color-fd-foreground)">
              after
            </text>
            <text
              x="570"
              y="222"
              textAnchor="middle"
              fontSize="9.5"
              fill="var(--color-fd-muted-foreground)"
            >
              the call site knows what
            </text>
          </g>
        </svg>
      </div>
      <figcaption className="mt-3 text-center text-sm text-fd-muted-foreground">
        The function call was never the problem. The edges are the problem — and the seam
        moves all of them to one side.
      </figcaption>
    </figure>
  );
}

/** The splitting, felt: the smaller each class gets, the less its callers are wired to. */
export function SplitDiagram() {
  const callers: [string, number][] = [
    ['route', 56],
    ['worker', 100],
    ['cli', 144],
    ['tests', 188],
  ];
  const callerCol = (
    <>
      {callers.map(([label, y]) => (
        <g key={label}>
          <circle cx="80" cy={y} r="4" fill="var(--color-fd-muted-foreground)" />
          <text
            x="70"
            y={y + 3.5}
            textAnchor="end"
            fontSize="9.5"
            fill="var(--color-fd-muted-foreground)"
          >
            {label}
          </text>
        </g>
      ))}
    </>
  );
  const bars = (coupling: number, cohesion: number) => (
    <>
      <text x="70" y="243" textAnchor="end" fontSize="8.5" fill="var(--color-fd-muted-foreground)">
        coupling
      </text>
      <rect x="80" y="237" width={coupling} height="6" rx="3" fill="var(--color-pm-violet)" opacity="0.75" />
      <text x="70" y="259" textAnchor="end" fontSize="8.5" fill="var(--color-fd-muted-foreground)">
        cohesion
      </text>
      <rect x="80" y="253" width={cohesion} height="6" rx="3" fill="#22d3ee" opacity="0.75" />
    </>
  );
  const caption = (label: string) => (
    <text x="130" y="222" textAnchor="middle" fontSize="11" fill="var(--color-fd-foreground)">
      {label}
    </text>
  );
  return (
    <figure className="not-prose my-8">
      <div className="overflow-x-auto rounded-xl border border-fd-border bg-fd-card/40 p-4">
        <svg
          viewBox="0 0 760 272"
          className="w-full min-w-140"
          role="img"
          aria-label="Three stages of splitting a service: first, four callers all wired to one god service with fifteen methods and seven dependencies; then callers wired to their own slice of three smaller services; finally each caller wired to a single one-operation class. A coupling bar shrinks across the stages while a cohesion bar grows"
          style={mono}
        >
          {/* panel 1: the god service */}
          <g transform="translate(10 0)">
            {callers.map(([label, y], i) => (
              <line
                key={label}
                x1="84"
                y1={y}
                x2="126"
                y2={70 + i * 35}
                stroke="var(--color-fd-border)"
                strokeWidth="1.2"
              />
            ))}
            {callerCol}
            <rect
              x="126"
              y="42"
              width="110"
              height="160"
              rx="10"
              fill="var(--color-fd-card)"
              stroke="var(--color-fd-border)"
            />
            <text x="181" y="66" textAnchor="middle" fontSize="10.5" fill="var(--color-fd-foreground)">
              OrderService
            </text>
            {['place · cancel', 'refund · invoice', 'statement · export', '…nine more'].map(
              (line, i) => (
                <text
                  key={line}
                  x="181"
                  y={92 + i * 17}
                  textAnchor="middle"
                  fontSize="8.5"
                  fill="var(--color-fd-muted-foreground)"
                >
                  {line}
                </text>
              ),
            )}
            <text x="181" y="176" textAnchor="middle" fontSize="8.5" fill="var(--color-fd-muted-foreground)">
              15 methods · 7 deps
            </text>
            {caption('the god service')}
            {bars(140, 28)}
          </g>

          {/* panel 2: split by what changes together */}
          <g transform="translate(262 0)">
            <line x1="84" y1="56" x2="126" y2="70" stroke="var(--color-fd-border)" strokeWidth="1.2" />
            <line x1="84" y1="100" x2="126" y2="128" stroke="var(--color-fd-border)" strokeWidth="1.2" />
            <line x1="84" y1="144" x2="126" y2="130" stroke="var(--color-fd-border)" strokeWidth="1.2" />
            <line x1="84" y1="188" x2="126" y2="184" stroke="var(--color-fd-border)" strokeWidth="1.2" />
            {callerCol}
            {(
              [
                [48, 'InvoiceService', '4 methods · 3 deps'],
                [106, 'ExportService', '3 methods · 2 deps'],
                [164, 'RefundService', '3 methods · 3 deps'],
              ] as [number, string, string][]
            ).map(([y, label, sub]) => (
              <g key={label}>
                <rect
                  x="126"
                  y={y}
                  width="110"
                  height="44"
                  rx="10"
                  fill="var(--color-fd-card)"
                  stroke="var(--color-fd-border)"
                />
                <text x="181" y={y + 19} textAnchor="middle" fontSize="10" fill="var(--color-fd-foreground)">
                  {label}
                </text>
                <text x="181" y={y + 34} textAnchor="middle" fontSize="8" fill="var(--color-fd-muted-foreground)">
                  {sub}
                </text>
              </g>
            ))}
            {caption('split by what changes together')}
            {bars(84, 84)}
          </g>

          {/* panel 3: one operation per class */}
          <g transform="translate(514 0)">
            {callers.map(([label, y]) => (
              <line
                key={label}
                x1="84"
                y1={y}
                x2="126"
                y2={y}
                stroke="var(--color-fd-border)"
                strokeWidth="1.2"
              />
            ))}
            {callerCol}
            {(
              [
                [56, 'invoice pdf'],
                [100, 'export orders'],
                [144, 'refund'],
                [188, 'statement'],
              ] as [number, string][]
            ).map(([y, label]) => (
              <g key={label}>
                <rect
                  x="126"
                  y={y - 14}
                  width="110"
                  height="28"
                  rx="9"
                  fill="var(--color-fd-card)"
                  stroke="var(--color-fd-border)"
                />
                <text x="181" y={y + 3.5} textAnchor="middle" fontSize="9.5" fill="var(--color-fd-foreground)">
                  {label}
                </text>
              </g>
            ))}
            <text x="181" y="212" textAnchor="middle" fontSize="8.5" fill="var(--color-fd-muted-foreground)">
              1 method · 2 deps each
            </text>
            {caption('the logical end')}
            {bars(28, 140)}
          </g>
        </svg>
      </div>
      <figcaption className="mt-3 text-center text-sm text-fd-muted-foreground">
        The operations never change. What changes is how much anyone touching them
        has to hold.
      </figcaption>
    </figure>
  );
}

/**
 * One dispatcher for every operation: requests cross the seam through a single
 * mediator to the handler that owns them. Same cloth as the home page's
 * dispatch-flow — SMIL dots, hidden under `prefers-reduced-motion` via
 * `.pm-flow-motion`; the diamond pulse reuses `.pm-node-pulse`.
 */
export function SeamFlowDiagram() {
  const lanes: { cx: number; request: string; handler: string; rw: number; hw: number }[] = [
    { cx: 160, request: 'PlaceOrder', handler: 'PlaceOrderHandler', rw: 116, hw: 164 },
    { cx: 380, request: 'Refund', handler: 'RefundHandler', rw: 96, hw: 138 },
    { cx: 600, request: 'ExportOrders', handler: 'ExportOrdersHandler', rw: 130, hw: 178 },
  ];
  // each dot: request → mediator centre → its handler, one lane per third of the cycle
  const dot = (cx: number, offset: number) => {
    const path = `M${cx} 60 L380 152 L380 192 L${cx} 284`;
    const [t0, t1] = [offset, offset + 0.3];
    return (
      <circle key={cx} r="4" fill="#22d3ee" opacity="0">
        <animateMotion
          dur="7.2s"
          repeatCount="indefinite"
          path={path}
          calcMode="linear"
          keyPoints="0;0;1;1"
          keyTimes={`0;${t0};${t1};1`}
        />
        <animate
          attributeName="opacity"
          values="0;0;1;1;0;0"
          keyTimes={`0;${t0};${t0 + 0.02};${t1 - 0.02};${t1};1`}
          dur="7.2s"
          repeatCount="indefinite"
        />
        <animate
          attributeName="fill"
          values="#22d3ee;#22d3ee;#8b5cf6;#8b5cf6"
          keyTimes={`0;${t0 + 0.15};${t0 + 0.16};1`}
          dur="7.2s"
          repeatCount="indefinite"
        />
      </circle>
    );
  };
  return (
    <figure className="not-prose my-8">
      <div className="overflow-x-auto rounded-xl border border-fd-border bg-fd-card/40 p-4">
        <svg
          viewBox="0 0 760 344"
          className="w-full min-w-160"
          role="img"
          aria-label="Three request types at the top — PlaceOrder, Refund, ExportOrders — each travel in turn through a single mediator at the centre, across a dotted seam line, down to their own handler at the bottom"
          style={mono}
        >
          <defs>
            <linearGradient
              id="pm-seamflow-g"
              x1="356"
              y1="148"
              x2="404"
              y2="196"
              gradientUnits="userSpaceOnUse"
            >
              <stop offset="0" stopColor="#22d3ee" />
              <stop offset="1" stopColor="#8b5cf6" />
            </linearGradient>
          </defs>

          {/* static lanes */}
          {lanes.map(({ cx }) => (
            <g key={cx}>
              <line
                x1={cx}
                y1="60"
                x2="380"
                y2="152"
                stroke="var(--color-fd-border)"
                strokeWidth="1.2"
              />
              <line
                x1="380"
                y1="192"
                x2={cx}
                y2="284"
                stroke="var(--color-fd-border)"
                strokeWidth="1.2"
              />
            </g>
          ))}

          {/* the seam */}
          <line
            x1="30"
            y1="172"
            x2="730"
            y2="172"
            stroke="var(--color-pm-violet)"
            strokeWidth="1.2"
            strokeDasharray="4 4"
            opacity="0.7"
          />
          <text x="730" y="160" textAnchor="end" fontSize="9.5" fill="var(--color-fd-muted-foreground)">
            the seam
          </text>

          {/* requests */}
          {lanes.map(({ cx, request, rw }) => (
            <g key={request}>
              <rect
                x={cx - rw / 2}
                y="24"
                width={rw}
                height="36"
                rx="10"
                fill="var(--color-fd-card)"
                stroke="var(--color-fd-border)"
              />
              <text x={cx} y="46" textAnchor="middle" fontSize="11.5" fill="var(--color-fd-foreground)">
                {request}
              </text>
            </g>
          ))}
          <text x="30" y="46" fontSize="9.5" fill="var(--color-fd-muted-foreground)">
            what
          </text>

          {/* mediator */}
          <path
            d="M380 144 L408 172 L380 200 L352 172 Z"
            fill="none"
            stroke="url(#pm-seamflow-g)"
            strokeWidth="1"
            className="pm-node-pulse"
          />
          <path d="M380 152 L400 172 L380 192 L360 172 Z" fill="url(#pm-seamflow-g)" />
          <text x="380" y="222" textAnchor="middle" fontSize="10.5" fill="var(--color-fd-muted-foreground)">
            mediator
          </text>

          {/* handlers */}
          {lanes.map(({ cx, handler, hw }) => (
            <g key={handler}>
              <rect
                x={cx - hw / 2}
                y="284"
                width={hw}
                height="36"
                rx="10"
                fill="var(--color-fd-card)"
                stroke="var(--color-fd-border)"
              />
              <text x={cx} y="306" textAnchor="middle" fontSize="11" fill="var(--color-fd-foreground)">
                {handler}
              </text>
            </g>
          ))}
          <text x="30" y="306" fontSize="9.5" fill="var(--color-fd-muted-foreground)">
            how
          </text>

          {/* travelling intent */}
          <g className="pm-flow-motion">
            {dot(160, 0.03)}
            {dot(380, 0.36)}
            {dot(600, 0.69)}
          </g>
        </svg>
      </div>
      <figcaption className="mt-3 text-center text-sm text-fd-muted-foreground">
        Ten operations or two hundred — every request crosses the same seam, through the
        same dispatcher, to the one handler that owns it.
      </figcaption>
    </figure>
  );
}
