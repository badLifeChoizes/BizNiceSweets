# Documentation Standards by Language

## Python — Docstrings

Three common styles. Match existing codebase style or default to Google.

### Google Style (Recommended)
```python
def fetch_user(user_id: int, include_deleted: bool = False) -> User:
    """Fetch user by ID from the database.

    Retrieves the user record, optionally including soft-deleted users.
    Returns None if not found rather than raising.

    Args:
        user_id: The unique user identifier.
        include_deleted: If True, include soft-deleted users. Default False.

    Returns:
        User object if found, None otherwise.

    Raises:
        DatabaseError: If connection fails.

    Example:
        >>> user = fetch_user(123)
        >>> print(user.name)
    """
```

### Sphinx Style
```python
def fetch_user(user_id: int, include_deleted: bool = False) -> User:
    """Fetch user by ID from the database.

    :param user_id: The unique user identifier.
    :type user_id: int
    :param include_deleted: If True, include soft-deleted users.
    :type include_deleted: bool
    :returns: User object if found, None otherwise.
    :rtype: User
    :raises DatabaseError: If connection fails.
    """
```

### NumPy Style
```python
def fetch_user(user_id: int, include_deleted: bool = False) -> User:
    """
    Fetch user by ID from the database.

    Parameters
    ----------
    user_id : int
        The unique user identifier.
    include_deleted : bool, optional
        If True, include soft-deleted users (default is False).

    Returns
    -------
    User
        User object if found, None otherwise.

    Raises
    ------
    DatabaseError
        If connection fails.
    """
```

---

## JavaScript/TypeScript — JSDoc

```javascript
/**
 * Fetch user by ID from the database.
 *
 * Retrieves the user record, optionally including soft-deleted users.
 *
 * @param {number} userId - The unique user identifier.
 * @param {boolean} [includeDeleted=false] - If true, include soft-deleted users.
 * @returns {Promise<User|null>} User object if found, null otherwise.
 * @throws {DatabaseError} If connection fails.
 *
 * @example
 * const user = await fetchUser(123);
 * console.log(user.name);
 */
async function fetchUser(userId, includeDeleted = false) {
```

### TypeScript-specific
```typescript
/**
 * Configuration options for the API client.
 */
interface ApiConfig {
  /** Base URL for API requests. */
  baseUrl: string;
  /** Request timeout in milliseconds. Default 5000. */
  timeout?: number;
}
```

---

## C/C++ — Doxygen

### Function Documentation
```c
/**
 * @brief Fetch user by ID from the database.
 *
 * Retrieves the user record. Caller must free the returned struct.
 *
 * @param[in]  user_id         The unique user identifier.
 * @param[in]  include_deleted If true, include soft-deleted users.
 * @param[out] error           Error code on failure, 0 on success.
 *
 * @return Pointer to User struct if found, NULL otherwise.
 *
 * @note Thread-safe. Uses internal mutex.
 * @warning Caller responsible for freeing returned memory.
 *
 * @code
 * int err;
 * User* user = fetch_user(123, false, &err);
 * if (user) {
 *     printf("%s\n", user->name);
 *     free_user(user);
 * }
 * @endcode
 */
User* fetch_user(int user_id, bool include_deleted, int* error);
```

### Struct Documentation
```c
/**
 * @brief Represents a user in the system.
 */
typedef struct {
    int id;           /**< Unique identifier. */
    char name[64];    /**< Display name (max 63 chars). */
    bool is_active;   /**< False if soft-deleted. */
} User;
```

---

## C# — XML Documentation

```csharp
/// <summary>
/// Fetches a user by ID from the database.
/// </summary>
/// <remarks>
/// Retrieves the user record, optionally including soft-deleted users.
/// </remarks>
/// <param name="userId">The unique user identifier.</param>
/// <param name="includeDeleted">If true, include soft-deleted users.</param>
/// <returns>User object if found; otherwise, null.</returns>
/// <exception cref="DatabaseException">Thrown when connection fails.</exception>
/// <example>
/// <code>
/// var user = await FetchUserAsync(123);
/// Console.WriteLine(user.Name);
/// </code>
/// </example>
public async Task<User?> FetchUserAsync(int userId, bool includeDeleted = false)
```

### Property Documentation
```csharp
/// <summary>
/// Gets or sets the user's display name.
/// </summary>
/// <value>The display name, max 64 characters.</value>
public string Name { get; set; }
```

---

## Go — Go Doc

Go doc uses comments immediately preceding declarations. First sentence becomes synopsis.

```go
// FetchUser retrieves a user by ID from the database.
//
// If includeDeleted is true, soft-deleted users are included.
// Returns nil and an error if the user is not found or if the
// database connection fails.
//
// Example:
//
//	user, err := FetchUser(ctx, 123, false)
//	if err != nil {
//	    log.Fatal(err)
//	}
//	fmt.Println(user.Name)
func FetchUser(ctx context.Context, userID int, includeDeleted bool) (*User, error)
```

### Type Documentation
```go
// User represents a user in the system.
//
// The zero value is not valid; use NewUser to create instances.
type User struct {
    ID       int    // Unique identifier.
    Name     string // Display name.
    IsActive bool   // False if soft-deleted.
}
```

---

## Rust — Rust Doc

Rust uses `///` for item docs and `//!` for module docs.

```rust
/// Fetches a user by ID from the database.
///
/// Retrieves the user record, optionally including soft-deleted users.
///
/// # Arguments
///
/// * `user_id` - The unique user identifier.
/// * `include_deleted` - If true, include soft-deleted users.
///
/// # Returns
///
/// `Some(User)` if found, `None` otherwise.
///
/// # Errors
///
/// Returns `DatabaseError` if connection fails.
///
/// # Examples
///
/// ```
/// let user = fetch_user(123, false)?;
/// println!("{}", user.name);
/// ```
pub fn fetch_user(user_id: i32, include_deleted: bool) -> Result<Option<User>, DatabaseError>
```

### Struct Documentation
```rust
/// Represents a user in the system.
///
/// # Fields
///
/// * `id` - Unique identifier.
/// * `name` - Display name (max 64 chars).
/// * `is_active` - False if soft-deleted.
#[derive(Debug, Clone)]
pub struct User {
    pub id: i32,
    pub name: String,
    pub is_active: bool,
}
```
