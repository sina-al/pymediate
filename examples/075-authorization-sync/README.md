# 075-authorization-sync

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/sina-al/pymediate?devcontainer_path=.devcontainer%2F075-authorization-sync%2Fdevcontainer.json)

The token parser in this example is unsigned and accepts caller-supplied roles and claims. It
exists only to provide deterministic input. Do not use it to authenticate real requests. A
production adapter must verify a signed token, session, or other credential before constructing
a trusted `Principal`.

This example separates authentication from two forms of authorization. The HTTP and CLI
adapters turn a credential into a principal. Synchronous pipeline behaviors enforce request-level
policies. The edit handler checks access to a document after loading that document.

## Run

From this directory:

```bash
uv sync
uv run pytest
```

```text
15 passed
```

The CLI adapter uses the same mediator and core:

```console
$ uv run vault --token "alice;user;mfa" edit 1 updated
Document(doc_id=1, owner_id='alice', body='updated')
$ echo $?
0

$ uv run vault view 1
denied: authentication required
$ echo $?
13
```

The role and claim values in the first command are not verified; they are demo input only.

## Establish identity at the boundary

Authentication establishes who the caller is. The adapter reads a credential, verifies it in a
production system, and supplies a `Principal` to the request. The core does not import FastAPI or
read command-line arguments.

```python
@app.get("/documents/{doc_id}")
def view(doc_id: int, http_request: HTTPRequest) -> Document:
    principal = from_http(http_request.headers)
    return mediator.send(ViewDocument(doc_id=doc_id, principal=principal))
```

`from_http` only parses the unsigned demo token. Replacing it with a credential verifier should
still leave the request and handler independent of HTTP.

## Apply request-level policies

The request hierarchy describes which policies apply:

- Every `AuthenticatedRequest` requires a principal.
- Every `RequiresRole` request requires the role declared by its concrete request type.
- A `MutatingCommand` also requires a multifactor authentication (MFA) claim.

The three behaviors use those types to select requests. `RequireMfa.should_apply` narrows its
broader type match to commands that change state.

```python
class RequireAuthentication(PipelineBehavior[AuthenticatedRequest]):
    def __call__(self, request, next):
        if request.principal is None:
            raise AuthenticationRequiredError("authentication required")
        return next()

class RequireMfa(PipelineBehavior[AuthenticatedRequest]):
    @classmethod
    def should_apply(cls, request: Request[Any]) -> bool:
        return isinstance(request, MutatingCommand)
```

Registration order matters. Authentication is registered outermost, so the role and MFA
behaviors can rely on a principal being present.

## Authorize a loaded resource

Request-level policies can decide whether a principal may attempt a type of operation. Editing a
specific document also depends on the loaded document's owner.

```python
document = self._store.get(request.doc_id)
if document is None:
    raise DocumentNotFoundError(request.doc_id)
principal = request.principal
assert principal is not None
if not self._authorizer.can_edit(principal, document):
    raise AuthorizationError(
        f"{principal.id} may not edit document {document.doc_id}"
    )
```

This check is in the handler because the handler already has the document. A behavior could
perform the same policy if it loaded or received the resource, but loading it separately would
duplicate or relocate the lookup. `DocumentAuthorizer` remains a separate dependency so the
policy can be tested and replaced independently.

## Map denials at each boundary

The core distinguishes a missing principal from an authenticated principal that lacks access.
The HTTP adapter maps those outcomes according to HTTP semantics:

| Core result | HTTP result | CLI result |
| --- | --- | --- |
| `AuthenticationRequiredError` | 401 with `WWW-Authenticate: Bearer` | exit code 13 |
| `AuthorizationError` | 403 | exit code 13 |
| `DocumentNotFoundError` | 404 | exit code 3 |

`AuthenticationRequiredError` and `AuthorizationError` share an `AccessError` base class. FastAPI
maps each specific error separately. The CLI maps their shared base class to
one access-denied exit code.

## Read the code

| File | What to read |
| --- | --- |
| [`src/vault/authn.py`](src/vault/authn.py) | The unsigned parser and the credential-verification warning. |
| [`src/vault/core.py`](src/vault/core.py) | Start here for principals, marker types, behaviors, and resource authorization. |
| [`src/vault/api.py`](src/vault/api.py) | Principal attachment and the HTTP 401, 403, and 404 mappings. |
| [`src/vault/cli.py`](src/vault/cli.py) | The same core exposed through CLI exit codes. |
| [`tests/test_authorization.py`](tests/test_authorization.py) | Behavior selection, ownership checks, and boundary mappings. |

## Details

Internal callers must also supply a principal established by a trusted mechanism. Constructing a
`Principal` directly does not verify an identity; it only carries identity data through the core.

Some systems return 404 instead of 403 to avoid revealing whether a protected resource exists.
This example keeps missing documents and authorization denials distinct so each mapping remains
visible.

## Where next

- [090-adapters-sync](../090-adapters-sync/) serves one application core through several
  synchronous framework adapters.
- [075-authorization](../075-authorization/) implements the same policies with the asynchronous
  API.
- Read the [pipeline behaviors guide](https://pymediate.sina-al.uk/docs/guide/pipeline-behaviors).
