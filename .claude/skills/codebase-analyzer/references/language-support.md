# Language Support Reference

## Supported Languages

Python, JavaScript/TypeScript, Go, Rust, Java, C/C++, C#

## Dependencies Analysis

Parses config files:

- **JavaScript:** package.json (npm/yarn/pnpm workspaces)
- **Python:** requirements.txt, pyproject.toml, Pipfile
- **Rust:** Cargo.toml (workspaces)
- **Go:** go.mod
- **Java:** build.gradle, build.gradle.kts
- **C/C++:** CMakeLists.txt
- **Ruby:** Gemfile
- **PHP:** composer.json
- **Docker:** Dockerfile
- **Build:** Makefile

## Patterns Detected

| Language              | Patterns Detected                                      |
| --------------------- | ------------------------------------------------------ |
| Python                | Type hints, docstrings, decorators, async, dataclasses |
| JavaScript/TypeScript | Arrow functions, React components, hooks, exports      |
| Go                    | Goroutines, channels, interfaces, exported/unexported  |
| Rust                  | Traits, impls, async, unsafe blocks, macros            |
| Java                  | Annotations, interfaces, extends/implements            |
| C/C++                 | Structs, classes, templates, namespaces                |
| C#                    | Async, LINQ, attributes, interfaces, properties        |

## Confidence Levels

| Level      | Meaning                               | Claude Action       |
| ---------- | ------------------------------------- | ------------------- |
| `detected` | High confidence from explicit signals | Trust this          |
| `inferred` | Heuristic guess from patterns         | Verify if important |
| `unknown`  | Needs human/Claude verification       | Ask or investigate  |