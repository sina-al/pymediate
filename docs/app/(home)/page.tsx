import Link from 'next/link';
import { ArrowRight, Layers, Plug, Send, ShieldCheck, Workflow, Zap } from 'lucide-react';
import { Tab, Tabs } from 'fumadocs-ui/components/tabs';
import { CodeWindow } from '@/components/code-window';
import { DispatchFlow } from '@/components/dispatch-flow';
import { InstallCmd } from '@/components/install-cmd';
import { LogoMark } from '@/components/logo';
import { gitConfig, pypiUrl } from '@/lib/shared';

const asyncExample = `import asyncio
from dataclasses import dataclass
from typing import override

from pymediate import Mediator, Request, RequestHandler, Services

@dataclass(frozen=True)
class OrderReceipt:
    order_id: int
    summary: str

@dataclass(frozen=True)
class PlaceOrder(Request[OrderReceipt]):
    customer_id: int
    item: str
    quantity: int

class PlaceOrderHandler(RequestHandler[PlaceOrder]):
    @override
    async def __call__(self, request: PlaceOrder) -> OrderReceipt:
        return OrderReceipt(
            order_id=42,
            summary=f"{request.quantity} × {request.item}",
        )

async def main() -> None:
    services = Services()
    services.add(PlaceOrderHandler())

    mediator = Mediator(services.provider())
    request = PlaceOrder(customer_id=7, item="tea", quantity=2)
    receipt = await mediator.send(request)

    print(receipt.summary)

asyncio.run(main())`;

const syncExample = `from dataclasses import dataclass
from typing import override

from pymediate.sync import Mediator, Request, RequestHandler, Services

@dataclass(frozen=True)
class OrderReceipt:
    order_id: int
    summary: str

@dataclass(frozen=True)
class PlaceOrder(Request[OrderReceipt]):
    customer_id: int
    item: str
    quantity: int

class PlaceOrderHandler(RequestHandler[PlaceOrder]):
    @override
    def __call__(self, request: PlaceOrder) -> OrderReceipt:
        return OrderReceipt(
            order_id=42,
            summary=f"{request.quantity} × {request.item}",
        )

services = Services()
services.add(PlaceOrderHandler())

mediator = Mediator(services.provider())
request = PlaceOrder(customer_id=7, item="tea", quantity=2)
receipt = mediator.send(request)

print(receipt.summary)`;

const behaviorExample = `from typing import override

from pymediate import Mediator, Next, PipelineBehavior, Services

from shop import OrderReceipt, PlaceOrder, PlaceOrderHandler


class ValidatePlaceOrder(PipelineBehavior[PlaceOrder]):
    @override
    async def __call__(
        self,
        request: PlaceOrder,
        next: Next[OrderReceipt],
    ) -> OrderReceipt:
        if request.quantity < 1:
            raise ValueError("quantity must be at least 1")

        return await next()


services = Services()
services.add(ValidatePlaceOrder())
services.add(PlaceOrderHandler())

mediator = Mediator(services.provider())
receipt = await mediator.send(
    PlaceOrder(customer_id=7, item="tea", quantity=2),
)`;

const eventExample = `from dataclasses import dataclass
from typing import override

from pymediate import Event, EventHandler, Mediator, Services


@dataclass(frozen=True)
class OrderPlaced(Event):
    order_id: int
    item: str


class RecordOrder(EventHandler[OrderPlaced]):
    @override
    async def __call__(self, event: OrderPlaced) -> None:
        print(f"recorded order {event.order_id}")


services = Services()
services.add(RecordOrder())

mediator = Mediator(services.provider())
await mediator.publish(
    OrderPlaced(order_id=42, item="tea"),
)`;

const features = [
  {
    icon: ShieldCheck,
    title: 'Declared response types',
    body: 'A Request[T] declaration gives send() its return type. Type checkers and editors preserve that relationship at each call site.',
  },
  {
    icon: Zap,
    title: 'Checked handler annotations',
    body: 'PyMediate checks request-handler parameter and return annotations when Python defines the handler class.',
  },
  {
    icon: Workflow,
    title: 'Asynchronous and synchronous APIs',
    body: 'The top-level package is asynchronous. pymediate.sync provides the corresponding blocking mediator and handler classes.',
  },
  {
    icon: Send,
    title: 'Requests, streams, and events',
    body: 'send() returns one response, stream() yields typed chunks, and publish() delivers an event to zero or more subscribers.',
  },
  {
    icon: Layers,
    title: 'Pipeline behaviors',
    body: 'Behaviors wrap send() with shared processing such as logging, validation, caching, or transaction management.',
  },
  {
    icon: Plug,
    title: 'Built-in or custom service providers',
    body: 'Use the built-in Services collection or another ServiceProvider implementation. The core package has no required dependencies.',
  },
];

export default function HomePage() {
  return (
    <main className="min-w-0 flex-1">
      <section className="relative overflow-hidden">
        <div aria-hidden className="pm-hero-glow absolute inset-0" />
        <div aria-hidden className="pm-grid-bg absolute inset-0" />
        <div className="relative mx-auto flex max-w-5xl flex-col items-center px-6 pt-24 pb-16 text-center">
          <p className="pm-fade-up mb-6 inline-flex items-center gap-2 rounded-full border border-fd-border bg-fd-card/60 px-3.5 py-1 text-xs text-fd-muted-foreground backdrop-blur">
            Python 3.12+ <span aria-hidden>·</span> async and sync <span aria-hidden>·</span> MIT
          </p>
          <h1
            className="pm-fade-up max-w-3xl text-balance text-4xl font-semibold tracking-tight sm:text-6xl"
            style={{ animationDelay: '60ms' }}
          >
            A typed <span className="pm-gradient-text">mediator</span> for Python
          </h1>
          <p
            className="pm-fade-up mt-6 max-w-2xl text-pretty text-base text-fd-muted-foreground sm:text-lg"
            style={{ animationDelay: '120ms' }}
          >
            PyMediate routes in-process requests to handlers. Each request declares its response
            type, so static type checkers and editors infer what{' '}
            <code className="font-mono text-[0.9em]">send()</code> returns.
          </p>
          <div
            className="pm-fade-up mt-8 flex flex-col items-center gap-5"
            style={{ animationDelay: '180ms' }}
          >
            <div className="flex flex-wrap items-center justify-center gap-3">
              <Link
                href="/docs"
                className="inline-flex items-center gap-1.5 rounded-full bg-fd-primary px-5 py-2.5 text-sm font-medium text-fd-primary-foreground transition-opacity hover:opacity-90"
              >
                Read the introduction
                <ArrowRight aria-hidden className="size-4" />
              </Link>
              <Link
                href="/docs/getting-started/quick-start"
                className="inline-flex items-center rounded-full border border-fd-border px-5 py-2.5 text-sm font-medium transition-colors hover:bg-fd-accent"
              >
                Quick start
              </Link>
            </div>
            <InstallCmd />
          </div>

          <div className="pm-fade-up mt-16 w-full" style={{ animationDelay: '260ms' }}>
            <DispatchFlow />
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-5xl px-6 py-20">
        <div className="max-w-2xl">
          <h2 className="text-3xl font-semibold tracking-tight">
            One request, one handler, one response type
          </h2>
          <p className="mt-4 text-fd-muted-foreground">
            <code className="font-mono text-[0.9em]">PlaceOrder</code> declares that it returns an{' '}
            <code className="font-mono text-[0.9em]">OrderReceipt</code>. The handler accepts that
            request, and the mediator dispatches it. The Behavior and Event tabs are focused
            excerpts built on the same shop domain.
          </p>
          <Link
            href="/docs#how-to-read-the-types"
            className="mt-6 inline-flex items-center gap-1.5 text-sm font-medium text-fd-primary hover:underline"
          >
            See how to read the types
            <ArrowRight aria-hidden className="size-4" />
          </Link>
        </div>
        <div className="mt-10 min-w-0 max-w-full">
          <Tabs className="min-w-0 max-w-full" items={['Async', 'Sync', 'Behavior', 'Event']}>
            <Tab value="Async" className="min-w-0 max-w-full">
              <CodeWindow code={asyncExample} title="async_request.py" className="not-prose" />
            </Tab>
            <Tab value="Sync" className="min-w-0 max-w-full">
              <CodeWindow code={syncExample} title="sync_request.py" className="not-prose" />
            </Tab>
            <Tab value="Behavior" className="min-w-0 max-w-full">
              <CodeWindow code={behaviorExample} title="behavior.py · excerpt" className="not-prose" />
            </Tab>
            <Tab value="Event" className="min-w-0 max-w-full">
              <CodeWindow code={eventExample} title="event.py · excerpt" className="not-prose" />
            </Tab>
          </Tabs>
        </div>
      </section>

      <section className="border-t border-fd-border bg-fd-card/40">
        <div className="mx-auto max-w-5xl px-6 py-20">
          <h2 className="text-center text-3xl font-semibold tracking-tight">
            What the package provides
          </h2>
          <p className="mx-auto mt-4 max-w-xl text-center text-fd-muted-foreground">
            Start with a request and its handler. Use streams for results over time, events for
            notifications, behaviors for shared processing, and a service provider to resolve the
            registered instances.
          </p>
          <div className="mt-12 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {features.map((feature) => (
              <div
                key={feature.title}
                className="rounded-xl border border-fd-border bg-fd-background/60 p-5"
              >
                <feature.icon aria-hidden className="size-5 text-fd-primary" />
                <h3 className="mt-3 font-medium">{feature.title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-fd-muted-foreground">
                  {feature.body}
                </p>
              </div>
            ))}
          </div>
          <div className="mt-8 text-center">
            <Link
              href="/docs/getting-started/concepts"
              className="inline-flex items-center gap-1.5 text-sm font-medium text-fd-primary hover:underline"
            >
              Read the core concepts
              <ArrowRight aria-hidden className="size-4" />
            </Link>
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-5xl px-6 py-20">
        <div className="max-w-2xl">
          <h2 className="text-3xl font-semibold tracking-tight">
            Nobody wants to touch that code
          </h2>
          <p className="mt-4 text-fd-muted-foreground">
            Direct calls are often the clearest design. A mediator becomes relevant when repeated
            handler lookup and shared processing spread across callers. The article follows that
            progression, including the cases where direct calls or a small dictionary remain
            sufficient.
          </p>
          <Link
            href="/articles/nobody-wants-to-touch-that-code"
            className="mt-6 inline-flex items-center gap-1.5 text-sm font-medium text-fd-primary hover:underline"
          >
            Read the article
            <ArrowRight aria-hidden className="size-4" />
          </Link>
        </div>
      </section>

      <section className="mx-auto max-w-5xl px-6 pb-24">
        <div className="pm-gradient-border rounded-2xl p-10 text-center sm:p-14">
          <LogoMark accessibleLabel="PyMediate" size={36} className="mx-auto" />
          <h2 className="mt-5 text-2xl font-semibold tracking-tight sm:text-3xl">
            Build the first request flow
          </h2>
          <p className="mx-auto mt-3 max-w-md text-fd-muted-foreground">
            The quick start defines <code className="font-mono text-[0.9em]">PlaceOrder</code>,
            runs its handler through a mediator, and prints the returned receipt.
          </p>
          <div className="mt-7 flex flex-wrap items-center justify-center gap-3">
            <Link
              href="/docs/getting-started/quick-start"
              className="inline-flex items-center gap-1.5 rounded-full bg-fd-primary px-5 py-2.5 text-sm font-medium text-fd-primary-foreground transition-opacity hover:opacity-90"
            >
              Quick start
              <ArrowRight aria-hidden className="size-4" />
            </Link>
            <Link
              href="/docs/api"
              className="inline-flex items-center rounded-full border border-fd-border px-5 py-2.5 text-sm font-medium transition-colors hover:bg-fd-accent"
            >
              API reference
            </Link>
          </div>
        </div>
      </section>

      <footer className="border-t border-fd-border">
        <div className="mx-auto flex max-w-5xl flex-col items-center justify-between gap-4 px-6 py-8 text-sm text-fd-muted-foreground sm:flex-row">
          <span className="inline-flex items-center gap-2">
            <LogoMark size={16} />
            pymediate · MIT License
          </span>
          <span className="flex items-center gap-5">
            <a
              href={`https://github.com/${gitConfig.user}/${gitConfig.repo}`}
              rel="noreferrer noopener"
              className="transition-colors hover:text-fd-foreground"
            >
              GitHub
            </a>
            <a
              href={pypiUrl}
              rel="noreferrer noopener"
              className="transition-colors hover:text-fd-foreground"
            >
              PyPI
            </a>
          </span>
        </div>
      </footer>
    </main>
  );
}
