# 075-authorization-sync

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/sina-al/pymediate?devcontainer_path=.devcontainer%2F075-authorization-sync%2Fdevcontainer.json)

The synchronous mirror of [075-authorization](../075-authorization/), on `pymediate.sync`.
Same three-layer split: **authentication** is an adapter concern (`authn.py` parses a
credential), **coarse authorization** is a selective `PipelineBehavior` in the core, and
**resource authorization** is an imperative check inside the handler, after the entity loads.

## Run it

```bash
cd examples/075-authorization-sync
uv sync
uv run pytest
```

```text
15 passed
```

Try the CLI yourself — the same core, no web server in sight:

```console
$ uv run vault view 1
denied: authentication required          # no --token: RequireAuthentication denies it, exit 13

$ uv run vault --token "bob;user;mfa" edit 1 "hacked"
denied: bob may not edit document 1      # bob is authenticated, but doesn't own doc 1, exit 13

$ uv run vault --token "alice;user;mfa" edit 1 "updated notes"
Document(doc_id=1, owner_id='alice', body='updated notes')                        # exit 0
```

## What changes from the async version

Only the API import and the mechanics — the placement rule is identical:

```python
# core.py
from pymediate.sync import Mediator, Next, PipelineBehavior, Request, RequestHandler, Services

class RequireAuthentication(PipelineBehavior[AuthenticatedRequest]):
    def __call__(self, request: AuthenticatedRequest, next: Next[Any]) -> Any:   # no async
        if request.principal is None:
            raise AuthorizationError("authentication required")
        return next()                                                            # no await
```

Every behavior, marker base, and the in-handler ownership check in
[`core.py`](src/vault/core.py) are byte-for-byte the same shape as the async twin, minus
`async`/`await`. The FastAPI routes in [`api.py`](src/vault/api.py) become plain `def`; the CLI
in [`cli.py`](src/vault/cli.py) drops the `asyncio.run` wrapper.

## The files

| File | What it is |
| --- | --- |
| [`src/vault/core.py`](src/vault/core.py) | **Start here.** The marker bases, the three coarse-authz behaviors, and the resource-authz handler. |
| [`src/vault/authn.py`](src/vault/authn.py) | The only transport-specific code: parsing a token into a `Principal`. |
| [`src/vault/api.py`](src/vault/api.py) | The HTTP edge: attach the principal, map `AuthorizationError` → 403. |
| [`src/vault/cli.py`](src/vault/cli.py) | The CLI edge: the same core, a `--token` flag, and exit code 13 for a denial. |
| [`tests/test_authorization.py`](tests/test_authorization.py) | All three layers, each denying independently: `uv run pytest` → `15 passed`. |

## Where next

- [075-authorization](../075-authorization/) — the async default, with the full explanation of
  the three-layer split.
- [070-error-handling-sync](../070-error-handling-sync/) — the edge-vs-core split for errors in
  general, on `pymediate.sync`.
- The docs: [dependency injection guide](https://pymediate.sina-al.uk/docs/guide/dependency-injection).
