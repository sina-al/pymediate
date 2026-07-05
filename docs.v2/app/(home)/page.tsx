import Link from 'next/link';
import {
  ArrowRight,
  Feather,
  FlaskConical,
  Layers,
  Plug,
  ShieldCheck,
  Workflow,
  Zap,
} from 'lucide-react';
import { Tab, Tabs } from 'fumadocs-ui/components/tabs';
import { CodeWindow } from '@/components/code-window';
import { DispatchFlow } from '@/components/dispatch-flow';
import { InstallCmd } from '@/components/install-cmd';
import { LogoMark } from '@/components/logo';
import { gitConfig, pypiUrl } from '@/lib/shared';

const syncExample = `from dataclasses import dataclass
from pymediate import Request, Handler, Mediator, Services

@dataclass
class UserCreated:
    user_id: int
    username: str

@dataclass
class CreateUser(Request[UserCreated]):
    username: str
    email: str

class CreateUserHandler(Handler[CreateUser]):
    def __call__(self, request: CreateUser) -> UserCreated:
        return UserCreated(user_id=1, username=request.username)

services = Services()
services.add(CreateUserHandler())
mediator = Mediator(services.provider())

response = mediator.send(CreateUser(username="alice", email="alice@example.com"))
# response is UserCreated — inferred from the request, checked by mypy`;

const asyncExample = `from dataclasses import dataclass
from pymediate import Request, Services
from pymediate.aio import Handler, Mediator

@dataclass
class UserCreated:
    user_id: int
    username: str

@dataclass
class CreateUser(Request[UserCreated]):
    username: str
    email: str

class CreateUserHandler(Handler[CreateUser]):
    async def __call__(self, request: CreateUser) -> UserCreated:
        user_id = await user_repository.save(request.username, request.email)
        return UserCreated(user_id=user_id, username=request.username)

mediator = Mediator(Services().add(CreateUserHandler()).provider())

response = await mediator.send(CreateUser(username="alice", email="alice@example.com"))`;

const pipelineExample = `from collections.abc import Callable
from typing import Any
from pymediate import PipelineBehavior, Request

class LoggingBehavior(PipelineBehavior[Request]):
    """Applies to every request — before and after its handler runs."""

    def __call__(self, request: Request, next: Callable[[], Any]) -> Any:
        print(f"handling {type(request).__name__}")
        response = next()
        print(f"returning {type(response).__name__}")
        return response

class AuditCreateUser(PipelineBehavior[CreateUser]):
    """Selective: only wraps CreateUser requests."""

    def __call__(self, request: CreateUser, next: Callable[[], Any]) -> Any:
        audit_log.record(request.email)
        return next()

services.add(LoggingBehavior())
services.add(AuditCreateUser())`;

const features = [
  {
    icon: ShieldCheck,
    title: 'Typed end to end',
    body: 'send() returns exactly what the request declares — response types are inferred from Request[T], validated by mypy --strict, no casts.',
  },
  {
    icon: Feather,
    title: 'Zero dependencies',
    body: 'The core is pure Python 3.12+ using PEP 695 generics. One optional extra when you want a DI container, nothing else.',
  },
  {
    icon: Workflow,
    title: 'Async mirror',
    body: 'pymediate.aio mirrors the sync API structurally — same classes, same semantics, await where it matters.',
  },
  {
    icon: Layers,
    title: 'Pipeline behaviors',
    body: 'Wrap every handler — or just some — with logging, validation, caching, or transactions, without touching handler code.',
  },
  {
    icon: Zap,
    title: 'Fails at definition time',
    body: 'Handler signatures are validated when the class is defined, so wiring mistakes surface at import — not in production.',
  },
  {
    icon: Plug,
    title: 'DI, your way',
    body: 'Use the built-in Services registry, or put a dependency-injector container behind the ServiceProvider protocol.',
  },
];

const reasons = [
  {
    title: 'Decouple callers from handlers',
    body: 'The code that sends CreateUser never imports the code that handles it. Features stay independent, and new handlers slot in without changing existing code.',
  },
  {
    title: 'CQRS by construction',
    body: 'Commands and queries are just request types. Separating writes from reads becomes a naming convention, not framework machinery.',
  },
  {
    title: 'Trivially testable',
    body: 'Handlers are plain callables — call them directly in tests. Consumers depend only on the mediator, so faking it is one line.',
  },
];

export default function HomePage() {
  return (
    <main className="flex-1">
      {/* hero */}
      <section className="relative overflow-hidden">
        <div aria-hidden className="pm-hero-glow absolute inset-0" />
        <div aria-hidden className="pm-grid-bg absolute inset-0" />
        <div className="relative mx-auto flex max-w-5xl flex-col items-center px-6 pt-24 pb-16 text-center">
          <p className="pm-fade-up mb-6 inline-flex items-center gap-2 rounded-full border border-fd-border bg-fd-card/60 px-3.5 py-1 text-xs text-fd-muted-foreground backdrop-blur">
            Python 3.12+ <span aria-hidden>·</span> PEP 695 generics <span aria-hidden>·</span> MIT
          </p>
          <h1
            className="pm-fade-up max-w-3xl text-balance text-4xl font-semibold tracking-tight sm:text-6xl"
            style={{ animationDelay: '60ms' }}
          >
            Type-safe <span className="pm-gradient-text">request dispatch</span> for modern Python
          </h1>
          <p
            className="pm-fade-up mt-6 max-w-2xl text-pretty text-base text-fd-muted-foreground sm:text-lg"
            style={{ animationDelay: '120ms' }}
          >
            PyMediate routes typed requests to their handlers through one mediator — response types
            inferred end to end, first-class async, zero runtime dependencies.
          </p>
          <div
            className="pm-fade-up mt-8 flex flex-col items-center gap-4 sm:flex-row"
            style={{ animationDelay: '180ms' }}
          >
            <InstallCmd />
            <div className="flex items-center gap-3">
              <Link
                href="/docs/getting-started/quick-start"
                className="inline-flex items-center gap-1.5 rounded-full bg-fd-primary px-5 py-2.5 text-sm font-medium text-fd-primary-foreground transition-opacity hover:opacity-90"
              >
                Get started
                <ArrowRight aria-hidden className="size-4" />
              </Link>
              <Link
                href="/docs"
                className="inline-flex items-center rounded-full border border-fd-border px-5 py-2.5 text-sm font-medium transition-colors hover:bg-fd-accent"
              >
                Documentation
              </Link>
            </div>
          </div>

          <div className="pm-fade-up mt-16 w-full" style={{ animationDelay: '260ms' }}>
            <DispatchFlow />
          </div>
        </div>
      </section>

      {/* code showcase */}
      <section className="mx-auto max-w-5xl px-6 py-20">
        <div className="grid items-start gap-10 lg:grid-cols-[1fr_1.4fr]">
          <div className="lg:sticky lg:top-24">
            <h2 className="text-3xl font-semibold tracking-tight">
              One <code className="pm-gradient-text font-mono text-[0.9em]">send()</code>, fully
              inferred
            </h2>
            <p className="mt-4 text-fd-muted-foreground">
              Declare the response type once, on the request. From there the mediator, the handler
              signature, and every call site agree — and <code className="font-mono text-[0.9em]">mypy</code>{' '}
              enforces it. The async API is a structural mirror: switch the import, add{' '}
              <code className="font-mono text-[0.9em]">await</code>, done.
            </p>
            <Link
              href="/docs/getting-started/concepts"
              className="mt-6 inline-flex items-center gap-1.5 text-sm font-medium text-fd-primary hover:underline"
            >
              Learn the core concepts
              <ArrowRight aria-hidden className="size-4" />
            </Link>
          </div>
          <Tabs items={['Sync', 'Async', 'Pipeline']}>
            <Tab value="Sync">
              <CodeWindow code={syncExample} title="app.py" className="not-prose" />
            </Tab>
            <Tab value="Async">
              <CodeWindow code={asyncExample} title="app.py" className="not-prose" />
            </Tab>
            <Tab value="Pipeline">
              <CodeWindow code={pipelineExample} title="behaviors.py" className="not-prose" />
            </Tab>
          </Tabs>
        </div>
      </section>

      {/* features */}
      <section className="border-t border-fd-border bg-fd-card/40">
        <div className="mx-auto max-w-5xl px-6 py-20">
          <h2 className="text-center text-3xl font-semibold tracking-tight">
            Small surface, sharp edges filed off
          </h2>
          <p className="mx-auto mt-4 max-w-xl text-center text-fd-muted-foreground">
            A handful of concepts — requests, handlers, behaviors, one mediator — designed to stay
            out of your way.
          </p>
          <div className="mt-12 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {features.map((feature) => (
              <div
                key={feature.title}
                className="rounded-xl border border-fd-border bg-fd-background/60 p-5 transition-colors hover:border-fd-primary/30"
              >
                <feature.icon aria-hidden className="size-5 text-fd-primary" />
                <h3 className="mt-3 font-medium">{feature.title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-fd-muted-foreground">
                  {feature.body}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* why mediator */}
      <section className="mx-auto max-w-5xl px-6 py-20">
        <div className="flex items-center gap-3">
          <FlaskConical aria-hidden className="size-5 text-fd-primary" />
          <h2 className="text-3xl font-semibold tracking-tight">Why a mediator?</h2>
        </div>
        <div className="mt-10 grid gap-8 md:grid-cols-3">
          {reasons.map((reason, i) => (
            <div key={reason.title}>
              <span aria-hidden className="pm-gradient-text font-mono text-sm font-semibold">
                0{i + 1}
              </span>
              <h3 className="mt-2 font-medium">{reason.title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-fd-muted-foreground">{reason.body}</p>
            </div>
          ))}
        </div>
      </section>

      {/* CTA */}
      <section className="mx-auto max-w-5xl px-6 pb-24">
        <div className="pm-gradient-border rounded-2xl p-10 text-center sm:p-14">
          <LogoMark size={36} className="mx-auto" />
          <h2 className="mt-5 text-2xl font-semibold tracking-tight sm:text-3xl">
            Ship your first handler in five minutes
          </h2>
          <p className="mx-auto mt-3 max-w-md text-fd-muted-foreground">
            Install the package, define a request, write a handler — the quick start walks you
            through the rest.
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
              href="/docs/api/request"
              className="inline-flex items-center rounded-full border border-fd-border px-5 py-2.5 text-sm font-medium transition-colors hover:bg-fd-accent"
            >
              API reference
            </Link>
          </div>
        </div>
      </section>

      {/* footer */}
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
