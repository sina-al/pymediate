/**
 * Animated diagram of a request dispatch: a typed request enters the
 * mediator, passes through pipeline behaviors, reaches its handler, and the
 * typed response travels back. Pure SVG + SMIL — no JS, and the moving dots
 * are hidden under `prefers-reduced-motion` (see `.pm-flow-motion`).
 */
export function DispatchFlow() {
  return (
    <div className="overflow-x-auto">
      <svg
        viewBox="0 0 760 168"
        className="w-full min-w-160"
        role="img"
        aria-label="A CreateUser request flows through the mediator and pipeline behaviors to its handler, and the typed response returns"
        style={{ fontFamily: 'var(--font-mono)' }}
      >
        <defs>
          <linearGradient id="pm-flow-g" x1="220" y1="75" x2="260" y2="115" gradientUnits="userSpaceOnUse">
            <stop offset="0" stopColor="#22d3ee" />
            <stop offset="1" stopColor="#8b5cf6" />
          </linearGradient>
        </defs>

        {/* transport line */}
        <line x1="134" y1="95" x2="596" y2="95" stroke="var(--color-fd-border)" strokeWidth="1.5" />

        {/* request node */}
        <rect x="16" y="72" width="118" height="46" rx="12" fill="var(--color-fd-card)" stroke="var(--color-fd-border)" />
        <text x="75" y="99" textAnchor="middle" fontSize="12" fill="var(--color-fd-foreground)">
          CreateUser
        </text>
        <text x="75" y="146" textAnchor="middle" fontSize="10.5" fill="var(--color-fd-muted-foreground)">
          request
        </text>

        {/* mediator node */}
        <path
          d="M240 67 L268 95 L240 123 L212 95 Z"
          fill="none"
          stroke="url(#pm-flow-g)"
          strokeWidth="1"
          className="pm-node-pulse"
        />
        <path d="M240 75 L260 95 L240 115 L220 95 Z" fill="url(#pm-flow-g)" />
        <text x="240" y="146" textAnchor="middle" fontSize="10.5" fill="var(--color-fd-muted-foreground)">
          mediator
        </text>

        {/* pipeline behaviors */}
        <rect x="318" y="79" width="84" height="32" rx="16" fill="var(--color-fd-card)" stroke="var(--color-fd-border)" />
        <text x="360" y="99" textAnchor="middle" fontSize="11" fill="var(--color-fd-foreground)">
          Logging
        </text>
        <rect x="426" y="79" width="94" height="32" rx="16" fill="var(--color-fd-card)" stroke="var(--color-fd-border)" />
        <text x="473" y="99" textAnchor="middle" fontSize="11" fill="var(--color-fd-foreground)">
          Validation
        </text>
        <text x="419" y="146" textAnchor="middle" fontSize="10.5" fill="var(--color-fd-muted-foreground)">
          pipeline behaviors
        </text>

        {/* handler node */}
        <rect x="596" y="72" width="148" height="46" rx="12" fill="var(--color-fd-card)" stroke="var(--color-fd-border)" />
        <text x="670" y="99" textAnchor="middle" fontSize="11.5" fill="var(--color-fd-foreground)">
          CreateUserHandler
        </text>
        <text x="670" y="146" textAnchor="middle" fontSize="10.5" fill="var(--color-fd-muted-foreground)">
          handler
        </text>

        {/* request dot: left → right in the first half of the cycle */}
        <g className="pm-flow-motion">
          <circle r="4" fill="#22d3ee" opacity="0">
            <animateMotion
              dur="3.6s"
              repeatCount="indefinite"
              path="M134 95 L596 95"
              calcMode="linear"
              keyPoints="0;1;1"
              keyTimes="0;0.45;1"
            />
            <animate
              attributeName="opacity"
              values="0;1;1;0;0"
              keyTimes="0;0.02;0.43;0.45;1"
              dur="3.6s"
              repeatCount="indefinite"
            />
          </circle>
          {/* response dot: right → left in the second half */}
          <circle r="4" fill="#8b5cf6" opacity="0">
            <animateMotion
              dur="3.6s"
              repeatCount="indefinite"
              path="M596 95 L134 95"
              calcMode="linear"
              keyPoints="0;0;1;1"
              keyTimes="0;0.52;0.97;1"
            />
            <animate
              attributeName="opacity"
              values="0;0;1;1;0"
              keyTimes="0;0.52;0.54;0.95;0.97"
              dur="3.6s"
              repeatCount="indefinite"
            />
          </circle>
        </g>
      </svg>
    </div>
  );
}
