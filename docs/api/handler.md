# Handler

## Synchronous handler

For synchronous request processing:

::: pymediate.handler.Handler
    options:
      show_root_heading: true
      show_source: true
      members_order: source
      heading_level: 3

## Asynchronous handler

For asynchronous request processing with `async`/`await`:

::: pymediate.aio.handler.Handler
    options:
      show_root_heading: true
      show_source: true
      members_order: source
      heading_level: 3

---

## Usage

### Sync Handler

```python
from dataclasses import dataclass
from pymediate import Handler, Request

@dataclass
class MyResponse:
    value: int

@dataclass
class MyRequest(Request[MyResponse]):
    data: str

class MyHandler(Handler[MyRequest]):
    def __call__(self, request: MyRequest) -> MyResponse:
        return MyResponse(value=len(request.data))
```

### Async handler

```python
from dataclasses import dataclass
from pymediate.aio import Handler
from pymediate import Request

@dataclass
class MyResponse:
    value: int

@dataclass
class MyRequest(Request[MyResponse]):
    data: str

class MyAsyncHandler(Handler[MyRequest]):
    async def __call__(self, request: MyRequest) -> MyResponse:
        # Can use await for async operations
        result = await some_async_operation(request.data)
        return MyResponse(value=result)
```

---

For detailed usage guide, see:

- [Handlers guide](../guide/handlers.md)
- [Async/await examples](../examples/async.md)
