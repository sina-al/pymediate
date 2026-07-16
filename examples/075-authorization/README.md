# 075-authorization

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/sina-al/pymediate?devcontainer_path=.devcontainer%2F075-authorization%2Fdevcontainer.json)

Where does authentication end and authorization begin — the adapter layer, or the core? This
example draws the line in three places, grounded in the ASP.NET Core model: **authentication is
a transport concern** (an adapter parses a credential into an identity), **coarse authorization
is a selective pipeline behavior** in the core (logged in? right role? MFA for a mutation?), and
**resource authorization is an imperative check inside the handler**, run after the entity
loads — a pre-dispatch behavior can't see a document that doesn't exist yet.

## Run it

```bash
cd examples/075-authorization
uv sync
uv run pytest
```

```text
14 passed
```

Those fourteen tests drive all three layers independently — each coarse-authz behavior denying
on its own, the in-handler ownership check, and both edges (HTTP, CLI) mapping the same denial.

Try the CLI yourself — identity comes from a `--token` flag instead of a header, but the
authorization is the *same* code:

```console
$ uv run vault view 1
denied: authentication required          # no --token: RequireAuthentication denies it, exit 13

$ uv run vault --token "bob;user;mfa" edit 1 "hacked"
denied: bob may not edit document 1      # bob is authenticated, but doesn't own doc 1, exit 13

$ uv run vault --token "alice;user;mfa" edit 1 "updated notes"
Document(doc_id=1, owner_id='alice', body='updated notes')                        # exit 0
```

## Layer 1 — authentication is an adapter concern

```python
# authn.py
def from_http(headers: Mapping[str, str]) -> Principal | None:
    header = headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        return None
    return parse_token(header.removeprefix("Bearer "))

# api.py
@app.get("/documents/{doc_id}")
async def view(doc_id: int, http_request: HTTPRequest) -> Document:
    principal = from_http(http_request.headers)
    return await mediator.send(ViewDocument(doc_id=doc_id, principal=principal))
```

Parsing a credential is the *only* transport-specific auth code in the whole example. The
`Principal` it produces travels in the request as a plain field — there's no ambient
`HttpContext` the core reaches into. `cli.py` builds the same `Principal` from a `--token` flag.

## Layer 2 — coarse authorization is a selective behavior

```python
@dataclass
class AuthenticatedRequest(Request[Any]):        # the [Authorize] analog
    principal: Principal | None = field(default=None, kw_only=True)

class RequireAuthentication(PipelineBehavior[AuthenticatedRequest]):
    async def __call__(self, request, next):
        if request.principal is None:
            raise AuthorizationError("authentication required")
        return await next()
```

Wearing `AuthenticatedRequest` is like wearing `[Authorize]` — the type parameter *is* the
routing. `RequiresRole` narrows it further (the `[Authorize(Roles=…)]` analog), and
`RequireMfa` uses `should_apply` to gate only mutating commands at runtime — a read and a write
of the same base type are treated differently, which a static attribute can't express:

```python
class RequireMfa(PipelineBehavior[AuthenticatedRequest]):
    @classmethod
    def should_apply(cls, request: Request[Any]) -> bool:
        return isinstance(request, MutatingCommand)   # only EditDocument, not ViewDocument
```

## Layer 3 — resource authorization is imperative, inside the handler

```python
class EditDocumentHandler(RequestHandler[EditDocument]):
    async def __call__(self, request: EditDocument) -> Document:
        document = self._store.get(request.doc_id)
        if document is None:
            raise DocumentNotFoundError(request.doc_id)
        principal = request.principal
        if not self._authorizer.can_edit(principal, document):
            raise AuthorizationError(f"{principal.id} may not edit document {document.doc_id}")
        ...
```

"May Bob edit *this* document?" depends on the document's owner — data that doesn't exist until
this handler loads it. A behavior runs *before* dispatch, so it structurally cannot make this
check; the `DocumentAuthorizer` (the `IAuthorizationService` analog) is injected and called
here instead, once the resource is in hand.

## The files

| File | What it is |
| --- | --- |
| [`src/vault/core.py`](src/vault/core.py) | **Start here.** The marker bases, the three coarse-authz behaviors, and the resource-authz handler. |
| [`src/vault/authn.py`](src/vault/authn.py) | The only transport-specific code: parsing a token into a `Principal`. |
| [`src/vault/api.py`](src/vault/api.py) | The HTTP edge: attach the principal, map `AuthorizationError` → 403. |
| [`src/vault/cli.py`](src/vault/cli.py) | The CLI edge: the same core, a `--token` flag, and exit code 13 for a denial. |
| [`tests/test_authorization.py`](tests/test_authorization.py) | All three layers, each denying independently: `uv run pytest` → `14 passed`. |

## Small print

- **One revelation, three layers.** How to *design* the request itself is
  [060-messages](../060-messages/); where to place *validation* (a related but different
  question) is [065-validation](../065-validation/). This example is only about the
  authn/authz split.
- Both a missing document and a denial could plausibly be "not found" from an attacker's
  perspective (hiding whether a resource exists at all). This example keeps them distinct —
  `DocumentNotFoundError` → 404, `AuthorizationError` → 403 — for clarity; a security-sensitive
  system might deliberately collapse them.

## Where next

- [075-authorization-sync](../075-authorization-sync/) — the same three layers on
  `pymediate.sync`.
- [070-error-handling](../070-error-handling/) — the edge-vs-core split for errors in general,
  one layer down from authorization specifically.
- The docs: [dependency injection guide](https://pymediate.sina-al.uk/docs/guide/dependency-injection).
