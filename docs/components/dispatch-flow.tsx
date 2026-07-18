/** Static overview of the core request flow used on the home page. */
export function DispatchFlow() {
  return (
    <div className="overflow-x-auto">
      <svg
        viewBox="0 0 760 190"
        className="w-full min-w-160"
        role="img"
        aria-label="A caller sends a PlaceOrder request through the mediator to PlaceOrderHandler, which returns an OrderReceipt to the caller"
        style={{ fontFamily: 'var(--font-mono)' }}
      >
        <defs>
          <linearGradient
            id="pm-flow-g"
            x1="350"
            y1="70"
            x2="410"
            y2="130"
            gradientUnits="userSpaceOnUse"
          >
            <stop offset="0" stopColor="var(--color-pm-cyan)" />
            <stop offset="1" stopColor="var(--color-pm-violet)" />
          </linearGradient>
          <marker
            id="pm-flow-arrow-request"
            viewBox="0 0 10 10"
            refX="9"
            refY="5"
            markerWidth="5"
            markerHeight="5"
            orient="auto-start-reverse"
          >
            <path d="M 0 0 L 10 5 L 0 10 z" fill="var(--color-pm-cyan)" />
          </marker>
          <marker
            id="pm-flow-arrow-response"
            viewBox="0 0 10 10"
            refX="9"
            refY="5"
            markerWidth="5"
            markerHeight="5"
            orient="auto-start-reverse"
          >
            <path d="M 0 0 L 10 5 L 0 10 z" fill="var(--color-pm-violet)" />
          </marker>
        </defs>

        <rect
          x="16"
          y="72"
          width="120"
          height="46"
          rx="12"
          fill="var(--color-fd-card)"
          stroke="var(--color-fd-border)"
        />
        <text
          x="76"
          y="99"
          textAnchor="middle"
          fontSize="13"
          fill="var(--color-fd-foreground)"
        >
          caller
        </text>

        <line
          x1="136"
          y1="83"
          x2="348"
          y2="83"
          stroke="var(--color-pm-cyan)"
          strokeWidth="1.5"
          markerEnd="url(#pm-flow-arrow-request)"
        />
        <text
          x="241"
          y="70"
          textAnchor="middle"
          fontSize="11.5"
          fill="var(--color-fd-muted-foreground)"
        >
          PlaceOrder
        </text>

        <path
          d="M380 67 L408 95 L380 123 L352 95 Z"
          fill="none"
          stroke="url(#pm-flow-g)"
          strokeWidth="1"
        />
        <path d="M380 75 L400 95 L380 115 L360 95 Z" fill="url(#pm-flow-g)" />
        <text
          x="380"
          y="146"
          textAnchor="middle"
          fontSize="12"
          fill="var(--color-fd-muted-foreground)"
        >
          mediator
        </text>

        <line
          x1="408"
          y1="83"
          x2="596"
          y2="83"
          stroke="var(--color-pm-cyan)"
          strokeWidth="1.5"
          markerEnd="url(#pm-flow-arrow-request)"
        />

        <rect
          x="596"
          y="72"
          width="148"
          height="46"
          rx="12"
          fill="var(--color-fd-card)"
          stroke="var(--color-fd-border)"
        />
        <text
          x="670"
          y="99"
          textAnchor="middle"
          fontSize="12.5"
          fill="var(--color-fd-foreground)"
        >
          PlaceOrderHandler
        </text>
        <text
          x="670"
          y="146"
          textAnchor="middle"
          fontSize="12"
          fill="var(--color-fd-muted-foreground)"
        >
          handler
        </text>

        <line
          x1="596"
          y1="108"
          x2="408"
          y2="108"
          stroke="var(--color-pm-violet)"
          strokeWidth="1.5"
          markerEnd="url(#pm-flow-arrow-response)"
        />
        <line
          x1="352"
          y1="108"
          x2="136"
          y2="108"
          stroke="var(--color-pm-violet)"
          strokeWidth="1.5"
          markerEnd="url(#pm-flow-arrow-response)"
        />
        <text
          x="242"
          y="132"
          textAnchor="middle"
          fontSize="11.5"
          fill="var(--color-fd-muted-foreground)"
        >
          OrderReceipt
        </text>
      </svg>
    </div>
  );
}
