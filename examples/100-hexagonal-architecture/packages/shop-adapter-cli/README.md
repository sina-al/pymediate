# Shop CLI adapter

`shop-adapter-cli` turns terminal input into typed Shop requests and presents their explicit
responses with Typer and Rich. It is another way into the same application used by FastAPI and the
background worker.

The package depends inward on `shop-application`, `shop-domain`, and `shop-bindings`. The domain and
application do not import the CLI. Commands do not call database gateways or select infrastructure
directly.

## Command tree

The `shop` console script exposes commands grouped by business area:

```text
shop
├── orders
│   ├── place
│   ├── export
│   ├── request-export
│   └── history
├── customers
│   ├── open
│   └── credit
├── invoices
│   └── get
└── statements
    └── create
```

`orders export` sends `ExportOrdersRequest` immediately in the CLI process. `orders request-export`
sends `RequestOrderExportRequest`, which records an integration message for a worker to translate
into `ExportOrdersRequest` later. The distinction is visible because the immediate command returns
a file location, while the durable command returns a job identifier.

`orders history --order ORDER_ID` reads the allowlisted public audit projection.
`invoices get --order ORDER_ID` retrieves an invoice after the background consumer creates it.

## Modules

### `shop.cli.app`

Defines the root Typer application, `--wiring` option, command groups, and `shop` entry point. It
loads one `Wiring` instance and one application container for the invocation.

### `shop.cli.context`

Holds the mediator and wiring lifecycle shared by subcommands. It provides the small interface used
to send an asynchronous request and render consistent terminal output. `get_context()` is the one
typed accessor used by every command group, including the runtime check for an initialized root
context.

### `shop.cli.commands`

Contains the business-oriented Typer groups beneath the root application:

- `commands.orders` parses human-friendly `SKU:QUANTITY` values and sends order creation, export,
  and public-history requests;
- `commands.customers` opens accounts and adjusts their store-credit balance;
- `commands.invoices` retrieves an invoice generated for an order by the background consumer;
- `commands.statements` sends `CreateMonthlyStatementRequest` and presents the stored document.

Parsing and terminal presentation remain command concerns. Business rules remain in the domain and
application packages.

## Boundary rules

Keep option names, terminal validation, colors, tables, and exit behavior in this package. Put a
rule in the domain or application request when it must apply equally to HTTP, CLI, and worker
callers. A command sends a named request and renders its response; it does not recreate handler
logic.

Adding a CLI command for another existing use case, such as refunds or customer-account closure,
would only require input/output translation. The application use case remains unchanged. A future
interactive shell could use the mediator in the same way.

## Configuration and lifecycle

Install one infrastructure extra and the CLI host extra, for example:

```bash
uv sync --extra default --extra cli
uv run shop --help
```

The CLI activates the `application` role and shuts down its resources in the same event loop as the
command. Use `--wiring PATH` to override `SHOP_WIRING` for one invocation.

The default profile is process-local. Each standalone `shop` invocation receives a fresh SQLite
database, so `customers open` followed by `customers credit` in a second process is not a persistent
workflow. Use `poe demo`, the long-running API, or a cloud administration container when operations
must share state.

The `shop` entry point defaults the standard `OTEL_SDK_DISABLED` variable to `true`. Short-lived
local commands therefore do not start telemetry unless the caller explicitly opts in with
`OTEL_SDK_DISABLED=false`.

Cloud Compose deployments include a dedicated `shop-administration` container containing this
adapter and the selected infrastructure profile. It shares the API's wiring and environment but
runs no daemon of its own. Compose explicitly enables its OpenTelemetry SDK, assigns the resource
name `shop-administration`, and sends its mediator spans and metrics to the shared collector.
Open a shell or execute one command directly, for example:

```bash
uv run poe compose:shell --cloud aws
# Or:
docker compose -f compose.yaml -f compose.aws.yaml exec shop-administration shop --help
```

## Testing

Integration tests invoke the public Typer application through its runner and use the default
configuration. They verify parsing, output, and translated failures. Business-rule combinations
belong in mediator-first application tests rather than command-function tests.

See the [complete Shop guide](../../README.md) for runnable commands and the shared application
story.
