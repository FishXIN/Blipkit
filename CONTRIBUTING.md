# Contributing

Blipkit is in early development. Before implementing a large feature, open an issue to confirm its scope and technical direction.

## Local setup

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
ruff check .
pytest
```

Keep pull requests focused, include tests for behavior changes, and update user-facing documentation when the product contract changes.
