# Staleness Detection

Stale documentation is **worse than no documentation**—it actively misleads developers. The audit tools detect when documentation no longer matches code.

## Issue Types

| Issue | Severity | Description |
|-------|----------|-------------|
| `stale_param` | ⚠️ High | Parameter documented but doesn't exist in signature |
| `stale_return` | ⚠️ High | Return value documented but function returns void/None |
| `undocumented_param` | 🔵 Medium | Parameter exists in signature but not documented |
| `undocumented_return` | 🔵 Medium | Non-void return but no return documentation |
| `param_type_mismatch` | 🟡 Low | Documented type doesn't match signature type |
| `missing_exception` | 🟡 Low | Exception raised in code but not documented |

## Detection Rules

### Stale Parameter (`stale_param`)

**Detected when:** A parameter name appears in documentation but not in the function signature.

```python
def create_user(name: str, email: str) -> User:
    """Create a new user.
    
    Args:
        name: The user's name.
        email: The user's email.
        role: The user's role.  # ⚠️ STALE - 'role' param was removed
    """
```

**Common causes:**
- Parameter removed during refactoring
- Parameter renamed without updating docs
- Copy-paste from similar function

### Stale Return (`stale_return`)

**Detected when:** Return documentation exists but function signature shows void/None.

```python
def send_notification(user_id: int) -> None:
    """Send notification to user.
    
    Returns:
        bool: True if sent successfully.  # ⚠️ STALE - function returns None
    """
```

**Common causes:**
- Return type changed to void
- Function refactored to raise exceptions instead of returning status

### Undocumented Parameter (`undocumented_param`)

**Detected when:** A parameter in the signature has no corresponding documentation.

```python
def create_user(name: str, email: str, role: str = "user") -> User:
    """Create a new user.
    
    Args:
        name: The user's name.
        email: The user's email.
        # 🔵 MISSING - 'role' param not documented
    """
```

### Undocumented Return (`undocumented_return`)

**Detected when:** Function has non-void return type but no return documentation.

```python
def get_user_count() -> int:
    """Get total number of users."""  # 🔵 MISSING - no Returns section
    return len(self.users)
```

### Type Mismatch (`param_type_mismatch`)

**Detected when:** Documented type differs from signature type.

```python
def fetch_users(limit: int = 100) -> list[User]:
    """Fetch users from database.
    
    Args:
        limit: Maximum users to return.  # 🟡 Type says 'str' but signature is 'int'
            Type: str
    """
```

## Audit Output Example

```markdown
## Summary
| Metric | Value |
|--------|-------|
| Total Elements | 234 |
| Documented | 189 |
| Coverage | 80.8% |
| Stale Docs | 5 ⚠️ |
| Health Score | 70.8% 🟡 |

## Files with Issues

### ⚠️ `services/user_service.py` — 68% coverage

**Stale documentation:**
- ⚠️ Line 45: `create_user` - Documented param 'role' not in signature
- ⚠️ Line 89: `delete_user` - Documents return but function returns None

**Missing documentation:**
- 🔵 Line 23: `get_user` - Missing Returns section
- 🔵 Line 67: `update_user` - Param 'metadata' not documented
```

## Health Score Calculation

```
health_score = coverage - (stale_count * 2)
```

Stale docs are penalized more heavily because they actively mislead.

| Health Score | Grade | Meaning |
|--------------|-------|---------|
| 90-100% | 🟢 A | Excellent |
| 80-89% | 🟢 B | Good |
| 70-79% | 🟡 C | Needs attention |
| 60-69% | 🟠 D | Poor |
| <60% | 🔴 F | Critical |

## Prioritization

1. **Fix stale docs first** — Wrong information is actively harmful
2. **Document public APIs** — These are user-facing
3. **Add missing returns** — Callers need to know what they get
4. **Fill in parameters** — Especially those with non-obvious types or purposes
5. **Skip obvious** — `self.x = x` assignments don't need detailed docs
