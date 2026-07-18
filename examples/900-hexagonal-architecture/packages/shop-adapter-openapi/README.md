# Shop OpenAPI adapter

`shop-adapter-openapi` exposes the Shop through FastAPI and documents the HTTP contract with
OpenAPI. Routes translate transport models into the same typed requests used by the CLI and worker.

The package depends inward on `shop-application`, `shop-domain`, and `shop-bindings`. The application
and domain do not import FastAPI or Pydantic transport models. Routes do not use a database gateway
directly.

## HTTP operations

The API exposes operations for:

- placing, refunding, and cancelling orders;
- opening and closing customer accounts;
- requesting a background order export;
- retrieving an invoice created by the worker;
- creating a monthly customer statement;
- adjusting customer store credit;
- querying an allowlisted order-history projection.

The export endpoint returns `202 Accepted` after the durable request is recorded. It does not wait
for CSV or JSON Lines generation. The invoice endpoint demonstrates the other side of that journey:
it retrieves a document created after a queue message was consumed.

The journal is not exposed as a generic `{aggregate_type}/{aggregate_id}` endpoint. Raw audit
payloads can contain internal fields and future events unknown to this API version. The order
history route maps known facts to explicit response fields and omits unknown event types. Production
code must also authenticate callers and authorize access to the requested order; identity is outside
this example's scope.

## Modules

### `shop.openapi.web`

Defines `create_app`, the Asynchronous Server Gateway Interface (ASGI) factory. It loads wiring, composes the application
container, wires each feature route module, registers error handlers, and activates the
`application` role through ASGI lifespan.

The factory also applies OpenTelemetry's maintained FastAPI instrumentation. It creates HTTP server
spans when a deployment configures a software development kit (SDK); otherwise the OpenTelemetry
API remains a no-op. The
mediator tracing behaviour appears beneath that server span rather than duplicating HTTP metadata.

Uvicorn remains the process runner. The [complete Shop guide](../../README.md#run-the-api) contains
the documented startup command and request output; this package does not add a wrapper console
script around Uvicorn.

### `shop.openapi.api` and `shop.openapi.routes`

`api` aggregates routers. Feature modules under `routes` own orders, customers, invoices,
and statements separately. Each route receives the mediator through Dependency Injector's
`Provide` and FastAPI's `Depends`, creates an application request, sends it, and maps the explicit
result to a response model.

### `shop.openapi.dto`

Defines Pydantic request, response, and problem-detail models. HTTP aliases, examples, field
constraints, and generated OpenAPI schemas belong here. Application request and response types
remain ordinary typed objects independent of HTTP.

### `shop.openapi.errors`

Translates each known structured domain error to a Problem Details (RFC 9457)
`application/problem+json` response.
The module owns status codes, titles, public detail, instance paths, and logging policy.

Individual handlers make each mapping visible. A final `DomainError` handler catches an error that
was not registered, logs it with a traceback, and returns a safe problem response without exposing
internal detail.

## Response safety

Routes return data-transfer objects (DTOs) built field by field from application responses. They do not serialize domain
entities. If a customer or order later gains a password hash, fraud score, or internal note, it
does not enter the HTTP schema automatically.

This also keeps OpenAPI evolution separate from business state. A transport alias or deprecation
can change without renaming a domain field.

## Configuration and deployment

The root workspace extra `openapi` installs this host alongside the selected infrastructure
profile. Cloud Compose images install `openapi` with either `aws` or `azure`. They do not contain the worker
package. The ASGI lifespan opens database, storage, and other configured resources and closes them
on shutdown or failed startup.

A gRPC or Model Context Protocol (MCP) adapter could sit beside this package. It would translate
its own transport models to the same application requests and would not copy route or handler
logic.

## Testing

Tests call the in-process ASGI application and verify status codes, schemas, response allowlists,
problem objects, logging policy, Dependency Injector wiring, and lifespan cleanup. Application
behavior is tested separately through the mediator.

See the [complete Shop guide](../../README.md) for API startup, Swagger UI, and deployment
profiles.
