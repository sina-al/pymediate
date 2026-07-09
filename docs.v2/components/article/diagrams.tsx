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
    { x: 152, y: 76, w: 172, label: 'needs OrderService' },
    { x: 264, y: 134, w: 232, label: 'needs mailer, payments, pdf…' },
    { x: 416, y: 192, w: 180, label: 'needs the app context' },
    { x: 548, y: 250, w: 176, label: 'needs a live request' },
  ];
  return (
    <figure className="not-prose my-8">
      <div className="overflow-x-auto rounded-xl border border-fd-border bg-fd-card/40 p-4">
        <svg
          viewBox="0 0 760 316"
          className="w-full min-w-140"
          role="img"
          aria-label="A staircase of five boxes descending to the right: the change you wanted at the top, followed by the chain of prerequisite changes it turned out to require"
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
          aria-label="Before: the call site connects directly to the service, its dependencies, and the framework. After: the call site connects only to a message; a seam separates it from the handler, which owns the dependencies"
          style={mono}
        >
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
                [62, 118, 'OrderService'],
                [165, 118, 'its constructor'],
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
            <path d="M580 65 L602 87 L580 109 L558 87 Z" fill="url(#pm-seam-g)" />
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
                [724, 'mailer'],
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
