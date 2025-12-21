# Conventions

> This file describes coding conventions for {{PROJECT_NAME}}.
> Read this when writing new code to match project style.

## Naming Conventions

### General

| Element | Convention | Example |
|---------|------------|---------|
| Files | [convention] | `user_service.py` |
| Classes | [convention] | `UserService` |
| Functions | [convention] | `get_user_by_id` |
| Constants | [convention] | `MAX_RETRY_COUNT` |
| Variables | [convention] | `user_count` |

### Domain-Specific

<!-- TODO: Add naming patterns specific to this project -->

| Pattern | Convention | Example |
|---------|------------|---------|
| [Handlers] | [pattern] | `on_user_created` |
| [DTOs] | [pattern] | `UserCreateRequest` |
| [Tests] | [pattern] | `test_user_creation_validates_email` |

## Code Organization

### File Structure

```
src/
├── [layer1]/          # [Purpose]
│   ├── [sublayer]/    # [Purpose]
│   └── ...
├── [layer2]/          # [Purpose]
└── ...
```

### Import Order

```python
# 1. Standard library
import os
import sys

# 2. Third-party packages
import requests
from fastapi import FastAPI

# 3. Local imports
from .models import User
from ..utils import helpers
```

## Patterns in Use

### [Pattern Name] (e.g., Repository Pattern)

**Where:** [Where this pattern is used]

**Structure:**
```
interface/repository.py  # Abstract interface
impl/sql_repository.py   # Concrete implementation
```

**Example:**
```python
# Define interface
class UserRepository(Protocol):
    def get_by_id(self, id: str) -> User: ...

# Implement
class SqlUserRepository(UserRepository):
    def get_by_id(self, id: str) -> User:
        return self.session.query(User).get(id)
```

### [Pattern Name]

**Where:** [Where this pattern is used]

**Example:**
```
[Code example]
```

## Error Handling

### Exception Hierarchy

```
BaseAppException
├── ValidationError
├── NotFoundError
├── AuthenticationError
└── ExternalServiceError
```

### Usage

```python
# Raise specific exceptions
raise NotFoundError(f"User {id} not found")

# Let handlers convert to HTTP responses
# Never catch generic Exception in business logic
```

## Documentation

### Docstring Style

```python
def process_payment(amount: Decimal, user_id: str) -> PaymentResult:
    """Process a payment for the specified user.

    Args:
        amount: Payment amount in USD
        user_id: The user's unique identifier

    Returns:
        PaymentResult with transaction details

    Raises:
        InsufficientFundsError: If user's balance is too low
        PaymentGatewayError: If external payment fails
    """
```

### When to Document

- [ ] Public API functions: Always
- [ ] Internal helpers: Only if non-obvious
- [ ] Classes: Always for public, brief for internal
- [ ] Modules: Always include module-level docstring

## Testing Conventions

### Test Naming

```
test_<what>_<condition>_<expected>
```

Examples:
- `test_create_user_with_valid_email_succeeds`
- `test_create_user_with_duplicate_email_raises_error`

### Test Structure (AAA)

```python
def test_something():
    # Arrange
    user = create_test_user()

    # Act
    result = service.process(user)

    # Assert
    assert result.status == "completed"
```
