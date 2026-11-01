# CLAUDE.md

## Git

- **Never run `git commit` or `git push`.** The user makes all commits themselves.
- When work is ready, say which files changed and suggest a commit message; don't stage or commit.

## Project

Single-user Flask + SQLite app for tracking fridge leftovers with QR-code labels. Deployed to
PythonAnywhere (see README.md).

- `app.py`: routes, API, and database schema
- `labels.py`: label PDFs (Avery 8460 sheets and roll label printer)
- `templates/`, `static/`: phone web front end (vanilla JS)

## Commands

Packages are managed with uv; don't use pip or requirements.txt.

```sh
uv sync            # install dependencies
uv run app.py      # run locally at http://localhost:5000
uv run pytest -q   # run tests
uv add <package>   # add a dependency
```
