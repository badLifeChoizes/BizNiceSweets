# Code Style Conventions Reference

Quick reference for common style conventions and why they matter.

---

## Naming Conventions

### snake_case
```python
user_name = "john"
def get_user_data():
    pass
```
**Used in:** Python functions, variables, modules

### camelCase
```javascript
userName = "john";
function getUserData() {}
```
**Used in:** JavaScript functions, variables

### PascalCase
```python
class UserAccount:
    pass
```
```javascript
class UserAccount {}
```
**Used in:** Classes in both Python and JavaScript

### SCREAMING_SNAKE_CASE
```python
MAX_CONNECTIONS = 100
API_BASE_URL = "https://api.example.com"
```
**Used in:** Constants in both languages

---

## Python Style

### Indentation
- **Standard:** 4 spaces
- **Never:** Mix tabs and spaces
- PEP 8 recommends 4 spaces

### Quotes
- **Double quotes:** Most common for strings
- **Single quotes:** Often used for dict keys, short strings
- **Consistency matters more than choice**

### Line Length
- **79-80:** Traditional PEP 8 limit
- **100:** Common modern limit
- **120:** Extended limit for wide screens

### Imports Order
```python
# 1. Standard library
import os
import sys

# 2. Third-party packages
import requests
import pandas as pd

# 3. Local imports
from .models import User
from .utils import helper
```

### Type Hints
```python
def greet(name: str, times: int = 1) -> str:
    return f"Hello, {name}!" * times
```

### Docstrings

**Google Style:**
```python
def fetch_data(url: str, timeout: int = 30) -> dict:
    """Fetch data from URL.

    Args:
        url: The URL to fetch from.
        timeout: Request timeout in seconds.

    Returns:
        Parsed JSON response.

    Raises:
        RequestError: If the request fails.
    """
```

**Sphinx Style:**
```python
def fetch_data(url: str, timeout: int = 30) -> dict:
    """Fetch data from URL.

    :param url: The URL to fetch from.
    :param timeout: Request timeout in seconds.
    :returns: Parsed JSON response.
    :raises RequestError: If the request fails.
    """
```

---

## JavaScript/TypeScript Style

### Indentation
- **2 spaces:** Most common in JS ecosystem
- **4 spaces:** Also widely used

### Semicolons
- **With semicolons:** Traditional, explicit
- **Without:** Modern, relies on ASI
- **Pick one and be consistent**

### Quotes
- **Single quotes:** Most common in JS
- **Double quotes:** Common in JSX
- **Template literals:** For interpolation

### Variable Declarations
```javascript
// Preferred
const API_URL = "https://api.example.com";  // Constants
const user = { name: "John" };               // Objects (const doesn't prevent mutation)
let count = 0;                               // Will be reassigned

// Avoid
var oldStyle = "legacy";  // Function-scoped, hoisted
```

### Arrow Functions vs Regular
```javascript
// Arrow: Concise, lexical `this`
const double = (x) => x * 2;
const items = arr.map(x => x.id);

// Regular: When you need `this`, `arguments`, or named function
function handleClick() {
    this.setState({ clicked: true });
}
```

### Object Shorthand
```javascript
// Good
const name = "John";
const user = { name, age: 30 };

// Verbose
const user = { name: name, age: 30 };
```

---

## Common Anti-Patterns

### Python
```python
# Bad: Mutable default argument
def append_to(item, target=[]):  # Bug! Shared list
    target.append(item)
    return target

# Good
def append_to(item, target=None):
    if target is None:
        target = []
    target.append(item)
    return target
```

```python
# Bad: Bare except
try:
    something()
except:  # Catches everything including KeyboardInterrupt
    pass

# Good
try:
    something()
except Exception as e:
    logger.error(f"Failed: {e}")
```

### JavaScript
```javascript
// Bad: == vs ===
if (x == null)   // True for null AND undefined

// Good: Be explicit
if (x === null)
if (x === undefined)
if (x == null)  // OK if you intentionally want both
```

```javascript
// Bad: Modifying array while iterating
arr.forEach((item, i) => {
    if (condition) arr.splice(i, 1);  // Bugs!
});

// Good: Filter creates new array
arr = arr.filter(item => !condition);
```

---

## Consistency Checklist

When contributing to a project:

1. **Match existing style** - Don't introduce new conventions
2. **Run formatters** - Black, Prettier, etc.
3. **Check linters** - ESLint, Ruff, etc.
4. **Follow naming patterns** - Look at similar code
5. **Document like neighbors** - Match docstring style
