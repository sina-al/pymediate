# Troubleshooting

This guide covers common issues you might encounter when using PyMediate and how to resolve them.

## Installation Issues

### DependencyInjectorResolver Not Available

**Problem:** You get an error when trying to use `DependencyInjectorResolver`:

```python
from pymediate import DependencyInjectorResolver

resolver = DependencyInjectorResolver(container)
# ImportError: DependencyInjectorResolver requires the 'dependency-injector' package.
```

**Cause:** The `dependency-injector` package is an optional dependency and is not installed by default.

**Solution:** Install PyMediate with the `[di]` extra:

=== "pip"

    ```bash
    pip install pymediate[di]
    ```

=== "uv"

    ```bash
    uv add 'pymediate[di]'
    ```

=== "poetry"

    ```bash
    poetry add pymediate[di]
    ```

**Alternative Solution:** Install `dependency-injector` separately:

```bash
pip install dependency-injector
# or
uv add dependency-injector
```

**Verification:** After installation, verify it works:

```python
from pymediate import DependencyInjectorResolver
print("DependencyInjectorResolver is available!")
```

### Import Errors After Installation

**Problem:** You installed PyMediate but imports are failing.

**Cause:** Possible version conflicts or incomplete installation.

**Solution:**

1. Verify the installation:
   ```bash
   pip show pymediate
   ```

2. Reinstall PyMediate:
   ```bash
   pip uninstall pymediate
   pip install pymediate
   ```

3. Check Python version (PyMediate requires Python 3.12+):
   ```python
   python --version  # Should be 3.12 or higher
   ```

## Runtime Issues

### HandlerNotFoundError

**Problem:** You get `HandlerNotFoundError` when sending a request:

```python
response = mediator.send(MyRequest())
# HandlerNotFoundError: No handler registered for request type 'MyRequest'
```

**Causes and Solutions:**

1. **Handler not registered:**
   ```python
   # Problem
   resolver = SimpleResolver()
   mediator = Mediator(resolver)
   response = mediator.send(MyRequest())  # ❌ Handler not registered

   # Solution
   resolver = SimpleResolver()
   resolver.register(MyRequest, MyHandler())  # ✅ Register the handler
   mediator = Mediator(resolver)
   response = mediator.send(MyRequest())
   ```

2. **Request class not inheriting from Request[ResponseT]:**
   ```python
   # Problem
   class MyRequest:  # ❌ Missing Request[ResponseT] inheritance
       pass

   # Solution
   class MyRequest(Request[MyResponse]):  # ✅ Proper inheritance
       pass
   ```

3. **Using DependencyInjectorResolver but provider is missing:**
   ```python
   # Problem
   class AppContainer(containers.DeclarativeContainer):
       # Missing handler provider
       pass

   # Solution
   class AppContainer(containers.DeclarativeContainer):
       my_handler = providers.Factory(MyHandler)  # ✅ Add provider
   ```

**Debugging:** The error message includes a list of available handlers:

```
HandlerNotFoundError: No handler registered for request type 'MyRequest'

Available handlers: CreateUserRequest, UpdateUserRequest, DeleteUserRequest
```

### HandlerTypeMismatchError

**Problem:** You get `HandlerTypeMismatchError` when registering a handler:

```python
resolver.register(CreateUserRequest, UpdateUserHandler())
# HandlerTypeMismatchError: Handler type mismatch
```

**Cause:** You're trying to register a handler for the wrong request type.

**Solution:** Make sure the handler matches the request:

```python
# ❌ Wrong
resolver.register(CreateUserRequest, UpdateUserHandler())

# ✅ Correct
resolver.register(CreateUserRequest, CreateUserHandler())
resolver.register(UpdateUserRequest, UpdateUserHandler())
```

### InvalidHandlerSignatureError

**Problem:** You get `InvalidHandlerSignatureError` when defining a handler:

```python
class MyHandler(Handler[MyRequest]):
    def __call__(self, request):  # Missing type annotation
        return MyResponse()
# InvalidHandlerSignatureError: __call__ request parameter must have type annotation
```

**Cause:** The `__call__` method signature doesn't match requirements.

**Solutions:**

1. **Missing parameter type annotation:**
   ```python
   # ❌ Wrong
   def __call__(self, request):
       return MyResponse()

   # ✅ Correct
   def __call__(self, request: MyRequest) -> MyResponse:
       return MyResponse()
   ```

2. **Missing return type annotation:**
   ```python
   # ❌ Wrong
   def __call__(self, request: MyRequest):
       return MyResponse()

   # ✅ Correct
   def __call__(self, request: MyRequest) -> MyResponse:
       return MyResponse()
   ```

3. **Wrong parameter type:**
   ```python
   # ❌ Wrong - parameter type doesn't match Handler[MyRequest]
   class MyHandler(Handler[MyRequest]):
       def __call__(self, request: DifferentRequest) -> MyResponse:
           return MyResponse()

   # ✅ Correct
   class MyHandler(Handler[MyRequest]):
       def __call__(self, request: MyRequest) -> MyResponse:
           return MyResponse()
   ```

4. **Wrong return type:**
   ```python
   # ❌ Wrong - return type doesn't match Request[MyResponse]
   class MyRequest(Request[MyResponse]):
       pass

   class MyHandler(Handler[MyRequest]):
       def __call__(self, request: MyRequest) -> WrongResponse:
           return WrongResponse()

   # ✅ Correct
   class MyHandler(Handler[MyRequest]):
       def __call__(self, request: MyRequest) -> MyResponse:
           return MyResponse()
   ```

### DIContainerError

**Problem:** You get `DIContainerError` when using DependencyInjectorResolver:

```python
handler = resolver.resolve(MyRequest)
# DIContainerError: Failed to resolve handler for 'MyRequest' from DI container
```

**Causes and Solutions:**

1. **Missing dependencies in handler:**
   ```python
   # Problem
   class MyHandler(Handler[MyRequest]):
       def __init__(self, database: Database):  # Database not provided
           self.database = database

   class AppContainer(containers.DeclarativeContainer):
       # Missing database provider
       my_handler = providers.Factory(MyHandler)  # ❌ Will fail

   # Solution
   class AppContainer(containers.DeclarativeContainer):
       database = providers.Singleton(Database)  # ✅ Provide dependency
       my_handler = providers.Factory(MyHandler, database=database)
   ```

2. **Circular dependencies:**
   ```python
   # Problem
   class AppContainer(containers.DeclarativeContainer):
       handler_a = providers.Factory(HandlerA, handler_b=handler_b)
       handler_b = providers.Factory(HandlerB, handler_a=handler_a)  # ❌ Circular

   # Solution: Use Singleton or rethink the design
   class AppContainer(containers.DeclarativeContainer):
       handler_a = providers.Singleton(HandlerA)
       handler_b = providers.Factory(HandlerB, handler_a=handler_a)  # ✅
   ```

## Type Checking Issues

### MyPy Errors

**Problem:** MyPy reports type errors with PyMediate code.

**Solution:** Ensure you're using the correct type annotations:

```python
from pymediate import Request, Handler, Mediator, SimpleResolver

# ✅ Properly typed
@dataclass
class UserResponse:
    user_id: int
    username: str

@dataclass
class CreateUserRequest(Request[UserResponse]):
    username: str
    email: str

class CreateUserHandler(Handler[CreateUserRequest]):
    def __call__(self, request: CreateUserRequest) -> UserResponse:
        return UserResponse(user_id=1, username=request.username)

# Type inference works correctly
mediator = Mediator(SimpleResolver())
response = mediator.send(CreateUserRequest(username="alice", email="alice@example.com"))
# response is correctly inferred as UserResponse
```

### Response Type Not Inferred

**Problem:** Your IDE or type checker doesn't infer the response type correctly.

**Solution:** Make sure you're using the generic type parameter:

```python
# ❌ Wrong - no type parameter
class CreateUserRequest(Request):
    username: str

# ✅ Correct - includes type parameter
class CreateUserRequest(Request[UserResponse]):
    username: str
```

## Documentation Build Issues

### MkDocs Build Fails

**Problem:** Documentation build fails with errors.

**Solution:**

1. Install documentation dependencies:
   ```bash
   pip install mkdocs mkdocs-material "mkdocstrings[python]"
   ```

2. Build with verbose output to see the error:
   ```bash
   mkdocs build --verbose
   ```

3. Common issues:
   - **Broken links:** Check all internal links in markdown files
   - **Missing files:** Ensure all referenced files exist
   - **Invalid YAML:** Check `mkdocs.yml` syntax

## Getting Help

If you encounter an issue not covered here:

1. **Check the documentation:**
   - [User Guide](../guide/requests-responses.md)
   - [API Reference](../api/request.md)
   - [Examples](../examples/basic.md)

2. **Search existing issues:**
   - [GitHub Issues](https://github.com/sina-al/pymediate/issues)

3. **Ask for help:**
   - [GitHub Discussions](https://github.com/sina-al/pymediate/discussions)

4. **Report a bug:**
   - [Create an issue](https://github.com/sina-al/pymediate/issues/new)

## Common Best Practices

To avoid common issues:

1. **Always use type annotations:**
   ```python
   # ✅ Good
   def __call__(self, request: MyRequest) -> MyResponse:
       ...

   # ❌ Bad
   def __call__(self, request):
       ...
   ```

2. **Register handlers before using the mediator:**
   ```python
   # ✅ Good
   resolver.register(MyRequest, MyHandler())
   mediator = Mediator(resolver)
   response = mediator.send(MyRequest())

   # ❌ Bad
   mediator = Mediator(resolver)
   response = mediator.send(MyRequest())  # Handler not registered yet!
   ```

3. **Use dataclasses for requests and responses:**
   ```python
   # ✅ Good
   @dataclass
   class MyRequest(Request[MyResponse]):
       field: str

   # ❌ Less ideal
   class MyRequest(Request[MyResponse]):
       def __init__(self, field: str):
           self.field = field
   ```

4. **Keep handlers focused:**
   ```python
   # ✅ Good - one handler per request type
   class CreateUserHandler(Handler[CreateUserRequest]):
       ...

   class UpdateUserHandler(Handler[UpdateUserRequest]):
       ...

   # ❌ Bad - handler trying to handle multiple types
   class UserHandler:
       def handle(self, request):
           if isinstance(request, CreateUserRequest):
               ...
           elif isinstance(request, UpdateUserRequest):
               ...
   ```
