# Language-Specific Parsing Notes

## Python

**Parser:** AST-based (100% accurate parsing)

**Extracts:**
- Function/method signatures with full type hints
- Default parameter values
- Decorators (`@property`, `@staticmethod`, `@classmethod`, custom)
- Async functions (`async def`)
- Class inheritance hierarchies
- Existing docstrings with style detection (Google, Sphinx, NumPy)

**Identifies:**
- Public vs private (`_private`, `__dunder__`)
- Instance methods vs class methods vs static methods
- Properties and their getters/setters
- Nested classes and functions

**Limitations:**
- Dynamic attributes added at runtime not detected
- Monkey-patched methods not visible

---

## JavaScript/TypeScript

**Parser:** Regex-based pattern matching

**Extracts:**
- Function declarations and expressions
- Arrow functions (including implicit returns)
- Class methods and properties
- Existing JSDoc comments
- Export statements (default, named, re-exports)

**Identifies:**
- Async functions
- Generator functions
- Static class members
- Module exports

**Limitations:**
- Complex TypeScript generics may not parse fully
- Deeply nested or unusual syntax patterns may be missed
- For complex TS projects, consider running `tsc` for authoritative type info

---

## C/C++

**Parser:** Regex-based, optimized for embedded patterns

**Extracts:**
- Function declarations and definitions
- Struct and typedef definitions
- Macro definitions (`#define`)
- Existing Doxygen comments (`/** */` and `///`)
- Header guards

**Identifies:**
- Static functions (file-scope)
- Inline functions
- Header vs implementation files
- Function pointer types

**Limitations:**
- Template metaprogramming not fully supported
- Preprocessor conditionals may affect accuracy
- Complex C++ features (SFINAE, concepts) not parsed

---

## C#

**Parser:** Regex-based

**Extracts:**
- Class, struct, interface, enum declarations
- Method signatures with full parameter info
- Property definitions (get/set)
- Existing XML documentation (`///`)
- Attributes (`[Serializable]`, `[HttpGet]`, etc.)

**Identifies:**
- Access modifiers (public, private, protected, internal)
- Async methods
- Static members
- Partial classes
- Extension methods

**Limitations:**
- Complex generic constraints may not parse fully
- Expression-bodied members may have reduced detail
- Roslyn provides more accurate parsing for complex cases

---

## Go

**Parser:** Regex-based

**Extracts:**
- Function declarations with receivers
- Type definitions (struct, interface, type aliases)
- Existing Go doc comments
- Package-level variables and constants

**Identifies:**
- Exported (capitalized) vs unexported
- Method receivers (value vs pointer)
- Interface implementations
- Grouped parameter declarations (`a, b int`)

**Limitations:**
- Embedded interfaces not fully resolved
- Generic types (Go 1.18+) have basic support
- Build constraints (`//go:build`) not evaluated

---

## Rust

**Parser:** Regex-based

**Extracts:**
- Function signatures with full type info
- Struct, enum, trait definitions
- Impl blocks and their methods
- Existing doc comments (`///` and `//!`)
- Attributes (`#[derive]`, `#[test]`, `#[cfg]`, etc.)

**Identifies:**
- Visibility (`pub`, `pub(crate)`, `pub(super)`)
- Async functions
- Generic parameters and lifetimes
- Trait implementations

**Limitations:**
- Complex lifetime annotations may not parse fully
- Macro-generated code not visible
- Procedural macro outputs not analyzed

---

## General Notes

**Regex vs AST Parsing:**
- Python uses AST: guaranteed accurate, handles all valid syntax
- Other languages use regex: covers common patterns, may miss edge cases

**When to Supplement:**
- TypeScript: Run `tsc --declaration` for authoritative types
- C#: Use Roslyn for complex codebases
- Rust: Use `cargo doc --document-private-items` for verification

**File Encoding:**
- All analyzers assume UTF-8
- Non-UTF-8 files may produce errors or partial results
