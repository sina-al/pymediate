# Error Handling

PyMediate provides a comprehensive error handling system with helpful error messages, documentation links, and best practices for managing errors in your application.

## Table of Contents

- [Error Philosophy](#error-philosophy)
- [Built-in Error Types](#built-in-error-types)
- [Handling Errors](#handling-errors)
- [Custom Error Types](#custom-error-types)
- [Error Messages](#error-messages)
- [Error Propagation](#error-propagation)
- [Validation Errors](#validation-errors)
- [Domain Errors](#domain-errors)
- [Result Types](#result-types)
- [Error Recovery](#error-recovery)
- [Testing Error Cases](#testing-error-cases)
- [Best Practices](#best-practices)

## Error Philosophy

PyMediate follows these principles for error handling:

1. **Fail Fast**: Errors should be caught as early as possible
2. **Helpful Messages**: Errors include solutions and documentation links
3. **Type Safety**: Custom exception hierarchy for precise error handling
4. **Framework Independent**: Errors work with any adapter (web, CLI, etc.)
5. **Testable**: Easy to test error conditions

## Built-in Error Types

PyMediate provides several custom exception types, all inheriting from `PyMediateError`.

### PyMediateError

Base exception for all PyMediate errors.

```python
from pymediate import PyMediateError

try:
    # PyMediate operation
    response = mediator.send(request)
except PyMediateError as e:
    # Catch any PyMediate error
    print(f"PyMediate error: {e}")
```

### HandlerNotFoundError

Raised when no handler is registered for a request type.

```python
from pymediate import HandlerNotFoundError

try:
    response = mediator.send(UnregisteredRequest())
except HandlerNotFoundError as e:
    print(f"No handler for: {e.request_type.__name__}")
    print(f"Available handlers: {e.available_handlers}")
```

**Error Message Example:**
```
No handler registered for request type 'CreateUserRequest'

💡 Possible solutions:
  1. Register a handler: resolver.register(CreateUserRequest, handler)
  2. Ensure your DI container has a provider for this handler
  3. Verify CreateUserRequest inherits from Request[ResponseType]

📋 Available handlers: GetUserRequest, DeleteUserRequest, UpdateUserRequest

📚 Learn more: https://sina-al.github.io/pymediate/guide/handlers
```

### HandlerTypeMismatchError

Raised when trying to register a handler for the wrong request type.

```python
from pymediate import HandlerTypeMismatchError

# Handler1 is designed for Request1
handler1 = Handler1()

try:
    # But trying to register for Request2
    resolver.register(Request2, handler1)
except HandlerTypeMismatchError as e:
    print(f"Handler: {e.handler_type.__name__}")
    print(f"Expected: {e.expected_request.__name__}")
    print(f"Got: {e.actual_request.__name__}")
```

**Error Message Example:**
```
Handler type mismatch: CreateUserHandler is designed to handle 'CreateUserRequest',
but you're trying to register it for 'UpdateUserRequest'

💡 Solution: Ensure the handler is registered with the correct request type:
  resolver.register(CreateUserRequest, CreateUserHandler())

📚 Learn more: https://sina-al.github.io/pymediate/guide/resolvers
```

### InvalidHandlerSignatureError

Raised when a handler has an invalid `__call__` signature.

```python
from pymediate import InvalidHandlerSignatureError, Handler

try:
    class BadHandler(Handler[MyRequest]):
        def __call__(self):  # Missing request parameter!
            pass
except InvalidHandlerSignatureError as e:
    print(f"Handler: {e.handler_type.__name__}")
    print(f"Issue: {e.issue}")
```

**Error Message Example:**
```
Invalid handler signature in CreateUserHandler: __call__ must have exactly one parameter

✅ Correct handler signature:
  class MyHandler(Handler[MyRequest]):
      def __call__(self, request: MyRequest) -> MyResponse:
          return MyResponse(...)

Common mistakes:
  ❌ Missing request parameter
  ❌ Wrong parameter type annotation
  ❌ Missing or wrong return type annotation
  ❌ Extra parameters (only 'self' and 'request' allowed)

📚 Learn more: https://sina-al.github.io/pymediate/guide/handlers
```

### InvalidRequestTypeError

Raised when a request doesn't properly inherit from `Request[ResponseType]`.

```python
from pymediate import InvalidRequestTypeError

try:
    class MyRequest:  # Missing Request[T] inheritance!
        pass

    class MyHandler(Handler[MyRequest]):
        pass
except InvalidRequestTypeError as e:
    print(f"Invalid request: {e.request_type.__name__}")
```

### DIContainerError

Raised when there's an issue with DI container configuration.

```python
from pymediate import DIContainerError

try:
    resolver = DependencyInjectorResolver(container)
    response = mediator.send(MyRequest())
except DIContainerError as e:
    print(f"Request: {e.request_type.__name__}")
    print(f"Reason: {e.reason}")
```

### ResponseTypeMismatchError

Raised when a handler returns the wrong response type.

```python
from pymediate import ResponseTypeMismatchError

try:
    class MyHandler(Handler[MyRequest]):
        def __call__(self, request: MyRequest) -> WrongResponse:  # Should be MyResponse!
            return WrongResponse()
except ResponseTypeMismatchError as e:
    print(f"Handler: {e.handler_type.__name__}")
    print(f"Expected: {e.expected_type.__name__}")
    print(f"Got: {e.actual_type.__name__}")
```

## Handling Errors

### Basic Error Handling

```python
from pymediate import HandlerNotFoundError

try:
    response = mediator.send(CreateUserRequest(username="alice", email="alice@example.com"))
except HandlerNotFoundError:
    # Handle missing handler
    print("Handler not registered")
except ValueError:
    # Handle validation errors
    print("Invalid request data")
except Exception as e:
    # Catch-all for unexpected errors
    print(f"Unexpected error: {e}")
```

### Specific Error Handling

```python
from pymediate import HandlerNotFoundError, HandlerTypeMismatchError

try:
    resolver.register(MyRequest, MyHandler())
    response = mediator.send(MyRequest())
except HandlerTypeMismatchError as e:
    # Handler registered for wrong request type
    print(f"Type mismatch: {e}")
except HandlerNotFoundError as e:
    # Handler not found
    print(f"Handler not found: {e}")
```

### Error Context

```python
from pymediate import PyMediateError

try:
    response = mediator.send(request)
except PyMediateError as e:
    # All PyMediate errors include docs_path
    if e.docs_path:
        print(f"See documentation: https://docs.pymediate.com/{e.docs_path}")
    raise
```

## Custom Error Types

### Domain-Specific Errors

```python
class UserAlreadyExistsError(Exception):
    """Raised when trying to create a user that already exists."""
    def __init__(self, username: str):
        self.username = username
        super().__init__(f"User '{username}' already exists")

class CreateUserHandler(Handler[CreateUserRequest]):
    def __call__(self, request: CreateUserRequest) -> CreateUserResponse:
        if self.database.user_exists(request.username):
            raise UserAlreadyExistsError(request.username)

        user_id = self.database.create_user(request.username, request.email)
        return CreateUserResponse(user_id=user_id, username=request.username)
```

### Error with Context

```python
class PaymentFailedError(Exception):
    """Raised when payment processing fails."""
    def __init__(self, reason: str, payment_id: str, amount: float):
        self.reason = reason
        self.payment_id = payment_id
        self.amount = amount
        super().__init__(
            f"Payment {payment_id} failed: {reason} (amount: ${amount:.2f})"
        )

class ProcessPaymentHandler(Handler[ProcessPaymentRequest]):
    def __call__(self, request: ProcessPaymentRequest) -> ProcessPaymentResponse:
        try:
            payment_id = self.payment_service.charge(
                amount=request.amount,
                method=request.payment_method
            )
        except Exception as e:
            raise PaymentFailedError(
                reason=str(e),
                payment_id=request.payment_id,
                amount=request.amount
            )

        return ProcessPaymentResponse(payment_id=payment_id, status="success")
```

### Error Hierarchy

```python
class ApplicationError(Exception):
    """Base error for all application errors."""
    pass

class ValidationError(ApplicationError):
    """Base error for validation failures."""
    pass

class BusinessRuleError(ApplicationError):
    """Base error for business rule violations."""
    pass

class InsufficientFundsError(BusinessRuleError):
    """Raised when account has insufficient funds."""
    def __init__(self, account_id: str, required: float, available: float):
        self.account_id = account_id
        self.required = required
        self.available = available
        super().__init__(
            f"Account {account_id} has insufficient funds: "
            f"required ${required:.2f}, available ${available:.2f}"
        )

class InvalidEmailError(ValidationError):
    """Raised when email format is invalid."""
    def __init__(self, email: str):
        self.email = email
        super().__init__(f"Invalid email format: {email}")
```

## Error Messages

### Helpful Error Messages

```python
class CreateUserHandler(Handler[CreateUserRequest]):
    def __call__(self, request: CreateUserRequest) -> CreateUserResponse:
        # ✅ GOOD: Helpful error message
        if len(request.username) < 3:
            raise ValueError(
                f"Username must be at least 3 characters (got {len(request.username)})"
            )

        # ❌ BAD: Vague error message
        if len(request.username) < 3:
            raise ValueError("Invalid username")
```

### Error Messages with Solutions

```python
class ValidateOrderHandler(Handler[ValidateOrderRequest]):
    def __call__(self, request: ValidateOrderRequest) -> ValidateOrderResponse:
        if not request.items:
            raise ValueError(
                "Order must contain at least one item.\n\n"
                "💡 Solutions:\n"
                "  1. Add items to the order before validating\n"
                "  2. Check if items were properly loaded from cart\n"
                "  3. Ensure items weren't filtered out during processing"
            )
```

### Error Messages with Context

```python
class UpdateProductHandler(Handler[UpdateProductRequest]):
    def __call__(self, request: UpdateProductRequest) -> UpdateProductResponse:
        product = self.database.get_product(request.product_id)

        if not product:
            # Include context about what was being updated
            raise ValueError(
                f"Product not found: {request.product_id}\n\n"
                f"Attempted update:\n"
                f"  - Name: {request.name}\n"
                f"  - Price: ${request.price:.2f}\n"
                f"  - Stock: {request.stock}\n\n"
                "Possible causes:\n"
                "  - Product was deleted\n"
                "  - Incorrect product ID\n"
                "  - Database connection issue"
            )
```

## Error Propagation

### Let Errors Propagate

```python
# ✅ GOOD: Let errors propagate naturally
class CreateUserHandler(Handler[CreateUserRequest]):
    def __call__(self, request: CreateUserRequest) -> CreateUserResponse:
        # Validation errors propagate automatically
        user_id = self.database.create_user(request.username, request.email)
        return CreateUserResponse(user_id=user_id, username=request.username)

# Caller handles errors
try:
    response = mediator.send(CreateUserRequest(username="", email="bad-email"))
except ValueError as e:
    print(f"Validation failed: {e}")
```

### Don't Swallow Errors

```python
# ❌ BAD: Swallowing errors
class CreateUserHandler(Handler[CreateUserRequest]):
    def __call__(self, request: CreateUserRequest) -> CreateUserResponse:
        try:
            user_id = self.database.create_user(request.username, request.email)
            return CreateUserResponse(user_id=user_id, username=request.username)
        except Exception:
            # Swallowed! Caller doesn't know what happened
            return CreateUserResponse(user_id=0, username="")

# ✅ GOOD: Let errors propagate
class CreateUserHandler(Handler[CreateUserRequest]):
    def __call__(self, request: CreateUserRequest) -> CreateUserResponse:
        # Errors propagate to caller
        user_id = self.database.create_user(request.username, request.email)
        return CreateUserResponse(user_id=user_id, username=request.username)
```

### Wrap and Re-raise

```python
class CreateUserHandler(Handler[CreateUserRequest]):
    def __call__(self, request: CreateUserRequest) -> CreateUserResponse:
        try:
            user_id = self.database.create_user(request.username, request.email)
            return CreateUserResponse(user_id=user_id, username=request.username)
        except DatabaseError as e:
            # Wrap with more context
            raise UserCreationError(
                f"Failed to create user '{request.username}': {e}"
            ) from e
```

## Validation Errors

### Request Validation

```python
@dataclass
class CreateUserRequest(Request[CreateUserResponse]):
    username: str
    email: str
    age: int

    def __post_init__(self):
        # Validate at request creation time
        errors = []

        if not self.username:
            errors.append("Username is required")
        elif len(self.username) < 3:
            errors.append("Username must be at least 3 characters")

        if not self.email:
            errors.append("Email is required")
        elif "@" not in self.email:
            errors.append("Invalid email format")

        if self.age < 0:
            errors.append("Age cannot be negative")
        elif self.age < 18:
            errors.append("Must be 18 or older")

        if errors:
            raise ValueError(
                f"Invalid request:\n" + "\n".join(f"  - {err}" for err in errors)
            )
```

### Business Rule Validation

```python
class TransferMoneyHandler(Handler[TransferMoneyRequest]):
    def __call__(self, request: TransferMoneyRequest) -> TransferMoneyResponse:
        # Get account balances
        from_balance = self.database.get_balance(request.from_account)
        to_account = self.database.get_account(request.to_account)

        # Validate business rules
        if from_balance < request.amount:
            raise InsufficientFundsError(
                account_id=request.from_account,
                required=request.amount,
                available=from_balance
            )

        if not to_account:
            raise AccountNotFoundError(request.to_account)

        if to_account.is_closed:
            raise AccountClosedError(request.to_account)

        # Process transfer
        self.database.transfer(
            from_account=request.from_account,
            to_account=request.to_account,
            amount=request.amount
        )

        return TransferMoneyResponse(
            transaction_id=generate_id(),
            status="completed"
        )
```

## Domain Errors

### Specific Domain Errors

```python
# E-commerce domain errors
class ProductNotFoundError(Exception):
    def __init__(self, product_id: int):
        self.product_id = product_id
        super().__init__(f"Product not found: {product_id}")

class OutOfStockError(Exception):
    def __init__(self, product_id: int, requested: int, available: int):
        self.product_id = product_id
        self.requested = requested
        self.available = available
        super().__init__(
            f"Product {product_id} out of stock: "
            f"requested {requested}, available {available}"
        )

class InvalidCouponError(Exception):
    def __init__(self, coupon_code: str, reason: str):
        self.coupon_code = coupon_code
        self.reason = reason
        super().__init__(f"Invalid coupon '{coupon_code}': {reason}")

# Usage in handler
class PlaceOrderHandler(Handler[PlaceOrderRequest]):
    def __call__(self, request: PlaceOrderRequest) -> PlaceOrderResponse:
        # Check product availability
        for item in request.items:
            product = self.database.get_product(item.product_id)

            if not product:
                raise ProductNotFoundError(item.product_id)

            if product.stock < item.quantity:
                raise OutOfStockError(
                    product_id=item.product_id,
                    requested=item.quantity,
                    available=product.stock
                )

        # Validate coupon if provided
        if request.coupon_code:
            coupon = self.database.get_coupon(request.coupon_code)

            if not coupon:
                raise InvalidCouponError(request.coupon_code, "Coupon not found")

            if coupon.is_expired():
                raise InvalidCouponError(request.coupon_code, "Coupon expired")

        # Process order...
        order_id = self.database.create_order(request)
        return PlaceOrderResponse(order_id=order_id)
```

## Result Types

Instead of throwing exceptions, use result types for expected failures.

### Simple Result Type

```python
from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar('T')
E = TypeVar('E')

@dataclass
class Success[T]:
    value: T

    def is_success(self) -> bool:
        return True

    def is_failure(self) -> bool:
        return False

@dataclass
class Failure[E]:
    error: E

    def is_success(self) -> bool:
        return False

    def is_failure(self) -> bool:
        return True

Result = Success[T] | Failure[E]

# Usage
@dataclass
class ProcessPaymentResponse:
    result: Result[Payment, str]

class ProcessPaymentHandler(Handler[ProcessPaymentRequest]):
    def __call__(self, request: ProcessPaymentRequest) -> ProcessPaymentResponse:
        try:
            payment = self.payment_service.charge(request.amount)
            return ProcessPaymentResponse(result=Success(payment))
        except PaymentError as e:
            return ProcessPaymentResponse(result=Failure(str(e)))

# Caller handles both cases
response = mediator.send(ProcessPaymentRequest(amount=99.99))
if response.result.is_success():
    print(f"Payment successful: {response.result.value.id}")
else:
    print(f"Payment failed: {response.result.error}")
```

### Rich Result Type

```python
@dataclass
class OperationResult[T]:
    success: bool
    value: T | None = None
    error: str | None = None
    error_code: str | None = None
    metadata: dict = field(default_factory=dict)

    @staticmethod
    def ok(value: T) -> "OperationResult[T]":
        return OperationResult(success=True, value=value)

    @staticmethod
    def fail(error: str, error_code: str | None = None) -> "OperationResult[T]":
        return OperationResult(success=False, error=error, error_code=error_code)

# Usage
@dataclass
class CreateUserResponse:
    result: OperationResult[User]

class CreateUserHandler(Handler[CreateUserRequest]):
    def __call__(self, request: CreateUserRequest) -> CreateUserResponse:
        # Check if user exists
        if self.database.user_exists(request.username):
            return CreateUserResponse(
                result=OperationResult.fail(
                    error=f"User '{request.username}' already exists",
                    error_code="USER_EXISTS"
                )
            )

        # Create user
        try:
            user = self.database.create_user(request.username, request.email)
            return CreateUserResponse(result=OperationResult.ok(user))
        except DatabaseError as e:
            return CreateUserResponse(
                result=OperationResult.fail(
                    error=f"Database error: {e}",
                    error_code="DB_ERROR"
                )
            )
```

## Error Recovery

### Retry Logic

```python
from tenacity import retry, stop_after_attempt, wait_exponential

class FetchDataHandler(Handler[FetchDataRequest]):
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10)
    )
    def __call__(self, request: FetchDataRequest) -> FetchDataResponse:
        # Will retry up to 3 times with exponential backoff
        data = self.http_client.get(request.url)
        return FetchDataResponse(data=data)
```

### Fallback Values

```python
class GetUserHandler(Handler[GetUserRequest]):
    def __call__(self, request: GetUserRequest) -> GetUserResponse:
        try:
            # Try cache first
            user = self.cache.get(f"user:{request.user_id}")
            if user:
                return GetUserResponse(**user)
        except CacheError:
            # Cache failed, continue to database
            pass

        try:
            # Try database
            user = self.database.get_user(request.user_id)
            return GetUserResponse(
                user_id=user.id,
                username=user.username,
                email=user.email
            )
        except DatabaseError:
            # Database failed, return default
            return GetUserResponse(
                user_id=request.user_id,
                username="Unknown",
                email=""
            )
```

### Circuit Breaker

```python
from circuitbreaker import circuit

class ExternalAPIHandler(Handler[ExternalAPIRequest]):
    @circuit(failure_threshold=5, recovery_timeout=60)
    def __call__(self, request: ExternalAPIRequest) -> ExternalAPIResponse:
        # Circuit opens after 5 failures
        # Stays open for 60 seconds
        data = self.external_api.fetch(request.endpoint)
        return ExternalAPIResponse(data=data)
```

## Testing Error Cases

### Testing Validation Errors

```python
import pytest

def test_create_user_empty_username():
    with pytest.raises(ValueError, match="Username is required"):
        CreateUserRequest(username="", email="test@example.com", age=25)

def test_create_user_invalid_email():
    with pytest.raises(ValueError, match="Invalid email format"):
        CreateUserRequest(username="alice", email="invalid-email", age=25)

def test_create_user_underage():
    with pytest.raises(ValueError, match="Must be 18 or older"):
        CreateUserRequest(username="alice", email="alice@example.com", age=16)
```

### Testing Domain Errors

```python
def test_transfer_insufficient_funds():
    handler = TransferMoneyHandler(database=mock_db)

    # Setup: Account has $50
    mock_db.set_balance("account1", 50.0)

    # Try to transfer $100
    request = TransferMoneyRequest(
        from_account="account1",
        to_account="account2",
        amount=100.0
    )

    with pytest.raises(InsufficientFundsError) as exc_info:
        handler(request)

    assert exc_info.value.required == 100.0
    assert exc_info.value.available == 50.0
```

### Testing PyMediate Errors

```python
from pymediate import HandlerNotFoundError

def test_handler_not_found():
    resolver = SimpleResolver()
    mediator = Mediator(resolver)

    with pytest.raises(HandlerNotFoundError) as exc_info:
        mediator.send(UnregisteredRequest())

    assert exc_info.value.request_type == UnregisteredRequest
```

## Best Practices

### 1. Use Specific Exception Types

```python
# ✅ GOOD: Specific exception types
class UserNotFoundError(Exception):
    pass

class InvalidCredentialsError(Exception):
    pass

# Handler
def __call__(self, request):
    if not user:
        raise UserNotFoundError(request.user_id)
    if not valid:
        raise InvalidCredentialsError()

# Caller can handle specifically
try:
    response = mediator.send(request)
except UserNotFoundError:
    return {"error": "User not found"}, 404
except InvalidCredentialsError:
    return {"error": "Invalid credentials"}, 401
```

### 2. Include Context in Error Messages

```python
# ✅ GOOD: Context included
raise ValueError(
    f"Failed to process order {order_id}: "
    f"product {product_id} out of stock "
    f"(requested: {requested}, available: {available})"
)

# ❌ BAD: No context
raise ValueError("Out of stock")
```

### 3. Fail Fast with Validation

```python
# ✅ GOOD: Validate in __post_init__
@dataclass
class CreateUserRequest(Request[UserResponse]):
    email: str

    def __post_init__(self):
        if "@" not in self.email:
            raise ValueError("Invalid email")

# ❌ BAD: Validate in handler
class CreateUserHandler(Handler[CreateUserRequest]):
    def __call__(self, request):
        if "@" not in request.email:  # Too late!
            raise ValueError("Invalid email")
```

### 4. Don't Use Exceptions for Control Flow

```python
# ❌ BAD: Using exceptions for control flow
try:
    user = self.database.get_user(user_id)
except UserNotFoundError:
    user = self.create_default_user()

# ✅ GOOD: Check explicitly
user = self.database.get_user(user_id)
if not user:
    user = self.create_default_user()
```

### 5. Log Errors Before Re-raising

```python
class CreateUserHandler(Handler[CreateUserRequest]):
    def __call__(self, request: CreateUserRequest) -> CreateUserResponse:
        try:
            user_id = self.database.create_user(request.username, request.email)
            return CreateUserResponse(user_id=user_id, username=request.username)
        except DatabaseError as e:
            # Log before re-raising
            self.logger.error(
                f"Failed to create user '{request.username}': {e}",
                exc_info=True
            )
            raise
```

---

## Next Steps

- Learn about [Handlers](handlers.md) - Implementing error handling in handlers
- Explore [Validation](../advanced/best-practices.md#validation) - Advanced validation techniques
- See [Testing](../advanced/testing.md) - Testing error scenarios
- Read [API Reference](../api/errors.md) - Complete error API documentation
