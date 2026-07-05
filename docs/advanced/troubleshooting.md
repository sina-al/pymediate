# Troubleshooting

This guide covers common issues you might encounter when using PyMediate and how to resolve them.

## Installation issues

### `DependencyInjectorServiceProvider` not available

**Problem:** You get an error when trying to use `DependencyInjectorServiceProvider`:

```python
from pymediate.providers import DependencyInjectorServiceProvider
# ModuleNotFoundError: No module named 'dependency_injector'
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
from pymediate.providers import DependencyInjectorServiceProvider
print("DependencyInjectorServiceProvider is available!")
```

### Import errors after installation

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

## Runtime issues

### `HandlerNotFoundError`

**Problem:** You get `HandlerNotFoundError` when sending a request:

```python
response = mediator.send(MyRequest())
# HandlerNotFoundError: No handler registered for request type 'MyRequest'
```

**Causes and solutions:**

1. **Handler not registered:**
   ```python
   # Problem
   services = Services()
   mediator = Mediator(services.provider())
   response = mediator.send(MyRequest())  # ❌ Handler not registered

   # Solution
   services = Services()
   services.add(MyHandler())  # ✅ Register the handler
   mediator = Mediator(services.provider())
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

3. **Using DependencyInjectorServiceProvider but provider is missing:**
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
No handler registered for request type 'MyRequest'

💡 Possible solutions:
  1. Register a handler: services.add(your_handler_instance)
  2. Ensure your DI container has a provider for this handler
  3. Verify MyRequest inherits from Request[ResponseType]

📋 Available handlers: CreateUserRequest, UpdateUserRequest, DeleteUserRequest

📚 Learn more: https://sina-al.github.io/pymediate/guide/handlers
```

### `InvalidHandlerSignatureError`

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

### DI container resolution failures

**Problem:** Calling a provider through `DependencyInjectorServiceProvider` raises an error from
the `dependency-injector` container itself (e.g. a missing dependency or a circular reference),
rather than a PyMediate-specific exception.

**Causes and solutions:**

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

### `HandlerAlreadyRegisteredError`

**Problem:** You get `HandlerAlreadyRegisteredError` when trying to define a second handler for the same request:

```python
class CreateUserHandler(Handler[CreateUserRequest]):
    def __call__(self, request: CreateUserRequest) -> UserResponse:
        return UserResponse(user_id=1, username=request.username)

class CreateUserHandlerV2(Handler[CreateUserRequest]):  # ❌ Error!
    def __call__(self, request: CreateUserRequest) -> UserResponse:
        return UserResponse(user_id=2, username=request.username)

# HandlerAlreadyRegisteredError: Handler already registered for 'CreateUserRequest'
```

**Cause:** PyMediate enforces a strict one-handler-per-request-type policy. Each request type can only have a single handler. This prevents ambiguity about which handler should process a request and helps catch accidental duplicate registrations early.

**Why this policy exists:**

1. **Clarity.** Always know exactly which handler will process a request.
2. **Early detection.** Catch configuration mistakes at class-definition time.
3. **Simplicity.** No need to reason about handler precedence or ordering.

**Solutions:**

1. **Remove one of the handler definitions (most common):**

   If you accidentally created a duplicate, simply remove or comment out one:

   ```python
   # ✅ Keep only one handler
   class CreateUserHandler(Handler[CreateUserRequest]):
       def __call__(self, request: CreateUserRequest) -> UserResponse:
           return UserResponse(user_id=1, username=request.username)
   ```

2. **Use different request types for different behaviors:**

   If you genuinely need multiple handlers, use distinct request types:

   ```python
   # ✅ Different request types
   @dataclass
   class CreateUserRequest(Request[UserResponse]):
       username: str
       email: str

   @dataclass
   class CreateAdminUserRequest(Request[UserResponse]):
       username: str
       email: str
       admin_level: int

   class CreateUserHandler(Handler[CreateUserRequest]):
       def __call__(self, request: CreateUserRequest) -> UserResponse:
           return UserResponse(user_id=1, username=request.username)

   class CreateAdminUserHandler(Handler[CreateAdminUserRequest]):
       def __call__(self, request: CreateAdminUserRequest) -> UserResponse:
           # Admin-specific logic
           return UserResponse(user_id=2, username=request.username)
   ```

3. **Compose multiple behaviors into one handler:**

   If you want to combine behaviors, use composition within a single handler:

   ```python
   # ✅ Compose behaviors
   class CreateUserHandler(Handler[CreateUserRequest]):
       def __init__(self, validator: UserValidator, mailer: EmailService):
           self.validator = validator
           self.mailer = mailer

       def __call__(self, request: CreateUserRequest) -> UserResponse:
           # Combine validation and email sending
           self.validator.validate(request)
           user = self.create_user(request)
           self.mailer.send_welcome_email(user)
           return UserResponse(user_id=user.id, username=user.username)
   ```

**Understanding the error message:**

The error provides helpful context including:

- The request type that has a conflict
- The name of the existing handler
- The name of the new handler attempting to register
- The file and line number where the first handler was registered (when available)

```
⚠️  Handler already registered for 'CreateUserRequest'

Existing handler: CreateUserHandler
Attempting to register: CreateUserHandlerV2

📍 First handler was registered at:
   /path/to/handlers.py:42

💡 Each request type can only have ONE handler.

Solutions:
  1. Remove one of the handler class definitions
  2. Use different request types for different behaviors:
     class CreateUserRequestV1(Request[Response]): ...
     class CreateUserRequestV2(Request[Response]): ...

  3. Compose handlers to combine behaviors:
     class ComposedHandler(Handler[MyRequest]):
         def __call__(self, request):
             # Combine both behaviors here
             ...

📚 Learn more: https://sina-al.github.io/pymediate/advanced/troubleshooting
```

**Debugging tips:**

1. **Check for duplicate imports.** Sometimes the same handler class is imported and defined multiple times.
2. **Review test isolation.** If you see this error in tests, ensure your tests properly clean up registries between runs.
3. **Check module-level definitions.** If handlers are defined at module level and imported multiple times, this can cause issues.

## Type checking issues

### mypy errors

**Problem:** MyPy reports type errors with PyMediate code.

**Solution:** Ensure you're using the correct type annotations:

```python
from pymediate import Request, Handler, Mediator, Services

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
services = Services()
services.add(CreateUserHandler())
mediator = Mediator(services.provider())
response = mediator.send(CreateUserRequest(username="alice", email="alice@example.com"))
# response is correctly inferred as UserResponse
```

### Response type not inferred

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

## Documentation build issues

### MkDocs build fails

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
      - **Broken links.** Check all internal links in markdown files.
      - **Missing files.** Ensure all referenced files exist.
      - **Invalid YAML.** Check `mkdocs.yml` syntax.

## Getting help

If you encounter an issue not covered here:

1. **Check the documentation.**
      - [User guide](../guide/requests-responses.md)
      - [API reference](../api/request.md)
      - [Examples](../examples/basic.md)
2. **Search existing issues.** [GitHub Issues](https://github.com/sina-al/pymediate/issues).
3. **Ask for help.** [GitHub Discussions](https://github.com/sina-al/pymediate/discussions).
4. **Report a bug.** [Create an issue](https://github.com/sina-al/pymediate/issues/new).

## Common best practices

To avoid common issues:

1. **Always use type annotations.**
   ```python
   # ✅ Good
   def __call__(self, request: MyRequest) -> MyResponse:
       ...

   # ❌ Bad
   def __call__(self, request):
       ...
   ```

2. **Register handlers before using the mediator.**
   ```python
   # ✅ Good
   services.add(MyHandler())
   mediator = Mediator(services.provider())
   response = mediator.send(MyRequest())

   # ❌ Bad
   mediator = Mediator(services.provider())
   response = mediator.send(MyRequest())  # Handler not registered yet!
   ```

3. **Use dataclasses for requests and responses.**
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

4. **Keep handlers focused.**
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
