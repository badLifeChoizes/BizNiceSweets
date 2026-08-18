# BizNiceSweets

An open-source, self-hostable **modular business suite for small-to-medium manufacturers** —
one application, installable modules ("suites" with deliciously sweet names) over one shared
PostgreSQL database, deployed on your own infrastructure with no per-seat SaaS lock-in.

Built first to run a healthcare-simulation-device manufacturing business, and designed for any
business that designs, manufactures, and sells physical products.

## Suites

| Suite | Name | Description | Status |
|-------|------|-------------|--------|
| ERP | **SYERP** | Enterprise Resource Planning — partners, inventory, purchasing, double-entry GL, AP, AR, financial reporting. **The hub.** | Shipped |
| PLM | **PLUM** | Product Lifecycle Management — parts, revisions, multi-level BOM, cost roll-up, AVL, import/export | Shipped |
| MES | **MOUSSE** | Manufacturing Execution — work orders that consume PLUM BOMs and inventory (materials-only) | Shipped |
| CRM | **CRUMB** | Customer Relationship Management — leads → opportunities → quotes → sales orders, communication log | Shipped |
| WMS | **GELATO** | Warehouse Management — bins, directed putaway, pick → pack → ship | Shipped |
| PRJ-MGMT | **FLAN** | Project Management | Prototype only — port pending |
| QMS | **CRISP** | Quality Management System | Planned |

Modules are individually installable and can be toggled per deployment.

## Quick Start

Requires **Podman** (or Docker) with `podman-compose`. Nothing else — the containers carry the
Python and Node toolchains.

```bash
git clone <repo-url> && cd BizNiceSweets

# Both env files are required. Fill in the secrets — they have no defaults
# and the stack refuses to start without them.
cp .env.example .env          # JWT_SECRET, BNS_ADMIN_PASSWORD
cp .env.db.example .env.db    # POSTGRES_PASSWORD

podman-compose -f compose/compose.yml up -d
```

The app is then at **http://localhost:8000**. On first boot the entrypoint waits for
PostgreSQL, runs `alembic upgrade head`, and applies idempotent seeds (chart of accounts, the
first admin user from `BNS_ADMIN_*`).

> **Both** `.env` **and** `.env.db` are needed. Skipping `.env.db` leaves the database without a
> password on a fresh volume and it refuses to initialize.

### Development stack

```bash
./scripts/uat.sh          # bash — Vite HMR + backend --reload; --fresh/--detach/--down
./scripts/uat.ps1         # PowerShell equivalent (needs pwsh)
```

Both create `.env` / `.env.db` from the templates if either is missing. The dev frontend serves
on **:5173**.

## Architecture

A **modular monolith**: installable modules over one shared PostgreSQL database, integrating via
foreign keys with SYERP as the hub. Backend and frontend ship as a single deployable unit — the
FastAPI app serves `/api/v1` and also serves the built React SPA.

- **Backend:** FastAPI + SQLAlchemy 2.0 (async) + PostgreSQL 17, Alembic migrations — `backend/`
- **Frontend:** React 19 + TypeScript + Vite + Tailwind CSS + shadcn/ui + TanStack Query — `frontend/`
- **Deployment:** Podman Compose, rootless — `compose/`
- **Auth:** JWT two-token (access/refresh), Argon2 hashing, server-enforced RBAC

Audit trail and traceability are first-class concerns throughout — a consequence of the
medical-device origin.

```
BizNiceSweets/
├── backend/        # FastAPI app, modules, migrations, tests, verify scripts
├── frontend/       # React SPA
├── compose/        # Podman Compose (prod + dev overlay)
├── scripts/        # uat.sh / uat.ps1 dev-stack launchers
├── docs/           # Feature documentation and task tracking
├── plum/ flan/     # Frozen legacy HTML prototypes (reference only)
└── .zj/            # Planning: requirements, roadmap, decisions
```

## Legacy prototypes

`plum/app/plm_v54.html` and `flan/app/prj-mgmt-v24.html` are the original single-file browser
apps. They are **frozen reference implementations** — no further development or bug fixes. PLUM
has been re-platformed onto the stack above; FLAN has not yet.

## Development

- **Backend:** `pytest`, `ruff check .`, `alembic upgrade head` — from `backend/`
- **Frontend:** `npm run dev`, `npm run build`, `npm run lint`, `npm run test` — from `frontend/`
- **CI:** GitHub Actions runs both lint gates, the full pytest suite against a live PostgreSQL
  service, Vitest, the production build, the `verify_*` scripts, and a container image build on
  every push.

### Workflow

- **Branch naming:** `feature-*`, `bugfix-*`, `hotfix-*`, `chore-*`
- **Commits:** conventional — `feat:`, `fix:`, `chore:`, `docs:`, `refactor:`, `test:`
- **Task files:** `docs/tasks/{branch-name}.md`
- `CHANGELOG.md` is generated from commits — never edited by hand

## Documentation

- [Suite Index](docs/features/INDEX.md) — suite relationships and integration vision
- [Codebase Map](.zj/codebase/MAP.md) — stack, layout, and verified commands
- [CLAUDE.md](CLAUDE.md) — development workflow and conventions

## License

Open core — the core suite is open source, built on permissively licensed dependencies only.
