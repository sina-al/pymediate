# Shop common adapter

`shop-adapter-common` provides small, stateless implementations used by every Shop deployment.
These are outside implementations of application ports, but they do not require a database, cloud
account, process-local store, or shutdown lifecycle.

The package depends only on `shop-ports`. It does not import the application, bindings, a host, or
another adapter.

## Why this package exists

The default, AWS, and Azure profiles all need a clock and an exchange-rate source. Keeping these
implementations in the ephemeral package would suggest that they are memory-backed test doubles.
They are not: they retain no observable state and behave the same in every profile.

This package is required directly by `shop-bindings`, while infrastructure-specific adapters remain
optional extras.

## Modules

### `shop.adapters.common.clock`

`SystemClock` implements the clock port with the current UTC business date. Handlers depend on the
clock rather than calling the system clock directly, so tests and another deployment can provide a
different implementation without changing application code.

### `shop.adapters.common.rates`

`FixedExchangeRates` implements the exchange-rate port for the example's GBP, EUR, and USD statement
flows. It is deterministic and is not presented as a live financial market feed. A production rate
service would belong in its own adapter package with credentials, client lifecycle, timeout, and
failure policy.

### `shop.adapters.common`

The package initializer exposes the intended public implementations. Configuration files may use
the explicit module paths so the selected capability remains visible.

## Configuration and lifecycle

All three YAML profiles select `SystemClock` and `FixedExchangeRates`. They use the default
singleton lifetime. Neither object opens a connection or needs resource shutdown.

If a common implementation starts retaining mutable state, taking credentials, or owning a client,
move it to a focused adapter package. "Common" means reusable and stateless, not a place for code
that has not found another home.

## Testing

Unit-test each implementation against the behavior its port promises. Bindings tests separately
verify that the dotted configuration references import correctly.

See the [complete Shop guide](../../README.md) for how common adapters participate in every
deployment profile.
