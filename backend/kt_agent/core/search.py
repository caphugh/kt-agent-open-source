"""Deterministic search over the knowledge base (no LLM)."""

# TODO: import your models (e.g. from kt_agent.models import SearchResult)


def search(query: str, limit: int = 10):
    """Run a deterministic search and return structured results.

    This is the single source of truth. cli.py will format the return
    value for the terminal; api/routes.py will serialize it to JSON.

    TODO:
      1. Decide the return type (a list of pydantic models is ideal here —
         it serializes to JSON for free and prints cleanly for the CLI).
      2. Query SQLite via kt_agent.db for rows matching `query`.
      3. Map rows -> your result model(s).
      4. Respect `limit`.
    """
    raise NotImplementedError  # TODO: implement
