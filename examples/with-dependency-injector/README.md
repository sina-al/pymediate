# with-dependency-injector

A small user directory whose handlers are wired by a
[dependency-injector](https://python-dependency-injector.ets-labs.org/) container instead
of manual `Services` registration — PyMediate's optional `di` extra.

What it shows:

- **The `di` extra** — this project depends on `pymediate[di]`, which pulls in
  `dependency-injector`; the integration lives in `pymediate.providers`.
- **Container as composition root** — `AppContainer` declares a `Singleton` repository and
  `Factory` handlers that receive it through their constructors; PyMediate never sees the
  wiring, only the finished container.
- **`DependencyInjectorServiceProvider`** — wraps the container in PyMediate's
  `ServiceProvider` protocol so `Mediator` can resolve handlers from it. Provider lifetimes
  are respected: `Factory` handlers are rebuilt per dispatch, while every one of them
  shares the single `Singleton` repository.

Run it:

```bash
uv sync
uv run python app.py   # short demo
uv run pytest          # the tests double as the examples-contract entrypoint
```
