# memento-core

Shared database access and Alembic migrations for the memento memory stack.

Install inside an activated repo-root virtualenv:

```bash
pip install -e ./shared/memento_core
```

Run migrations from this directory with `DATABASE_URL` set (after loading root `.env` via `MEMENTO_ENV_ROOT`):

```bash
export MEMENTO_ENV_ROOT=/absolute/path/to/memento
set -a && source "$MEMENTO_ENV_ROOT/.env" && set +a
cd shared/memento_core && alembic upgrade head
```
