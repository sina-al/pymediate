# Shop bindings

`shop-bindings` turns a deployment configuration into Dependency Injector providers. It is the
composition root shared by the CLI, OpenAPI server, outbox relay, and queue consumer.

The package contains no business rules and implements no application port. Its job is to choose
concrete implementations, supply them to an executable role, and own their runtime lifecycle.

This example uses a data-driven composition root to demonstrate deployments that mix several hosts
with local, Amazon Web Services (AWS), and Azure infrastructure. That amount of indirection is not
a starting requirement for a PyMediate application. A Python function with container overrides is
often sufficient when an
application has only one or two deployment shapes.

## Dependency direction

Bindings sit outside the application. They may import the application container and the concrete
implementations selected by a configuration file. The application does not import bindings or any
adapter package.

The package has required dependencies on the application, common stateless implementations, and
the document renderer used by every profile. Optional extras install coherent infrastructure sets:

- `default` installs SQLite and process-local implementations;
- `aws` installs PostgreSQL, S3-compatible storage, Amazon Simple Queue Service (SQS), and
  process-local implementations for services not represented by those AWS services;
- `azure` installs PostgreSQL, Blob Storage/Service Bus, and the same process-local support services;
- `observability` installs the OpenTelemetry software development kit (SDK) and OpenTelemetry
  Protocol (OTLP) gRPC exporters.

Host dependencies remain separate at the workspace root. An OpenAPI image therefore need not
install the worker package, and a worker image need not install FastAPI.

## Provider configuration

Each file in [`configuration/`](../../configuration/) contains a named provider graph and the
bindings for executable roles. The checked-in [JSON Schema](../../configuration.schema.json)
provides completion, hover descriptions, required-field diagnostics, and strict unknown-property
validation in VS Code.

```yaml
providers:
  database:
    impl: shop.adapters.postgres.PostgresDbGateway
    lifetime: resource
    arguments:
      dsn: { env: SHOP_POSTGRES_URL }
  unit:
    impl: shop.adapters.postgres.PostgresUnitOfWork
    lifetime: factory
    arguments:
      database: { $ref: database }
  telemetry:
    impl: shop.bindings.opentelemetry.configure_opentelemetry
    lifetime: resource

bindings:
  application:
    providers:
      database: database
      unit: unit
      # Remaining ApplicationContainer dependencies are listed here.
    resources: [telemetry]
  relay:
    providers:
      outbox: database
      publisher: broker
    resources: [telemetry]
  consumer:
    providers:
      queue: broker
      inbox: database
    resources: [telemetry]
```

A provider selects exactly one construction form:

- `impl` imports and calls a concrete class or factory;
- `$ref` aliases another named provider without changing its lifetime.

References are independent of declaration order. A reference cycle, missing provider, invalid
environment lookup, non-callable implementation, or unknown property stops startup with its
configuration path.

Constructor arguments can be literals, `{ $ref: provider_name }`, or
`{ env: VARIABLE, default: value }`. An omitted environment default makes the value required. Empty
environment values are treated as missing so a container fails with the variable name instead of
starting with an unusable connection string.

## Provider lifetimes

The supported lifetimes map to Dependency Injector providers:

- `singleton` constructs one value lazily for the wiring graph;
- `factory` constructs a value on every resolution;
- `resource` is a `providers.Resource` whose implementation returns an asynchronous context
  manager.

Resource providers are also the providers injected into the application and worker containers.
There is no separate singleton and shadow lifecycle provider for the same client. Provider
dependencies therefore retain their actual graph: a unit-of-work factory references the database
resource that it will use.

## Executable roles

The nested `bindings` section separates three independently executable roles:

- `application` supplies every outward dependency of `ApplicationContainer`;
- `relay` supplies only the outbox source and queue publisher;
- `consumer` supplies the queue delivery source and inbox. It runs alongside `application` because
  decoded messages are dispatched through the application mediator.

Each role has two parts. `providers` maps the dependency name expected by its container to a named
provider. `resources` names process setup that is not injected, such as installing the OpenTelemetry
SDK.

Resources reachable through injected providers are discovered automatically. For example,
activating `application` starts its database and storage clients because those providers have
resource lifetime. They should not also appear in `resources`. When several selected roles reach
the same database or telemetry provider, it is initialized and shut down once.

The API and CLI need only `application`. The relay activates only `relay`, so it does not construct
the mediator or initialize object storage. The consumer activates `application` and `consumer` as
one lifecycle scope.

## Lifecycle API

`load_wiring()` validates and resolves the provider graph without opening external resources.
Executable code then selects an explicit lifecycle:

```python
from shop.bindings.loading import application_context

async with application_context() as application:
    mediator = application.mediator()
```

Code that composes more than one role uses `Wiring` directly:

```python
from shop.bindings.loading import create_application_container, load_wiring

wiring = load_wiring()
async with wiring.activate("application", "consumer"):
    application = create_application_container(wiring)
    consumer_providers = wiring.role("consumer", {"queue", "inbox"}).providers
```

Activation initializes the deduplicated resource closure before yielding. If startup fails after a
dependency has opened, that dependency is shut down before the error leaves the context. Normal and
exceptional exits shut down only the resources belonging to the selected roles, in dependency
order. Nested or concurrent activation of one `Wiring` instance is rejected.

Dependency Injector treats an asynchronously initialized resource, and factories depending on it,
as asynchronous providers. PyMediate resolves handler providers synchronously even
though handlers themselves are asynchronous. After initialization, activation temporarily disables
async provider mode across the selected graph so the already-open resource values can be injected
synchronously. It re-enables resource async mode for awaited shutdown and restores every provider's
previous mode afterward. A regression test covers this boundary.

`load_container()` remains available for inspecting composition without resolving its resource
providers. Executable code should use `application_context()` or `Wiring.activate()` so it cannot
outlive an open database, broker, storage client, or telemetry exporter.

## OpenTelemetry setup

`shop.bindings.opentelemetry` installs the standard OpenTelemetry SDK providers and maintained OTLP
gRPC exporters. It does not add a Shop telemetry port. Instrumentation depends on the OpenTelemetry
API; bindings select its SDK implementation and the collector remains the deployment boundary.

The SDK reads its standard `OTEL_*` variables directly. Bindings does not duplicate the parsing of
service names, resource attributes, sampling, endpoints, headers, export intervals, or the SDK
disabled flag. Cloud manifests list telemetry as an explicit process resource because installing SDK
providers is setup rather than an injected application dependency.

See [Reusing third-party abstractions](../../docs/third-party-abstractions.md) for the API/SDK and
collector rationale.

## A Python composition root

Data-driven wiring is useful here because infrastructure and host choices can vary independently.
An application with fewer deployment variants can keep the same package boundaries and compose the
container in ordinary Python:

```python
from dependency_injector import providers

from shop.application.container import ApplicationContainer

container = ApplicationContainer()
container.database.override(providers.Singleton(MyDatabase))
container.unit.override(providers.Factory(MyUnitOfWork, database=container.database))
# Override the remaining deployment dependencies.
container.check_dependencies()
```

This form has less machinery and exposes every choice to static tooling. Moving composition into
data becomes useful only when independently changing deployment dimensions justify the additional
validation and lifecycle code.

## Tests

The package tests cover runtime/schema agreement, required role dependencies, order-independent
references, cycles, environment failures, resource reachability, role isolation, shared-resource
deduplication, synchronous injection after async startup, startup-failure cleanup, normal shutdown,
and profile dependency metadata.

Use the flagship project's focused checks from the example root. The complete application journey
and deployment commands are documented in the [Shop example guide](../../README.md).
