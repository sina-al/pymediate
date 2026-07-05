# Mediator

## Synchronous mediator

For routing synchronous requests to handlers:

::: pymediate.mediator.Mediator
    options:
      show_root_heading: true
      show_source: true
      members_order: source
      heading_level: 3

## Asynchronous mediator

For routing asynchronous requests to async handlers:

::: pymediate.aio.mediator.Mediator
    options:
      show_root_heading: true
      show_source: true
      members_order: source
      heading_level: 3

---

## Usage

### Sync mediator

```python
from pymediate import Mediator, Services

services = Services()
services.add(MyHandler())
mediator = Mediator(services.provider())

# Send a request - blocks until handler completes
response = mediator.send(MyRequest(data="example"))
```

### Async mediator

```python
import asyncio
from pymediate.aio import Mediator
from pymediate import Services

async def main():
    services = Services()
    services.add(MyAsyncHandler())
    mediator = Mediator(services.provider())

    # Send a request - awaits handler completion
    response = await mediator.send(MyRequest(data="example"))

    # Process multiple requests concurrently
    responses = await asyncio.gather(
        mediator.send(MyRequest(data="first")),
        mediator.send(MyRequest(data="second")),
        mediator.send(MyRequest(data="third")),
    )

asyncio.run(main())
```

---

For detailed usage guide, see:

- [Mediator guide](../guide/mediator.md)
- [Async/await examples](../examples/async.md)
