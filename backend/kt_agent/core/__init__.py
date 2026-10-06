"""Core logic shared by the CLI and the FastAPI layer.

Rule: this package must NOT import typer or fastapi.
It only knows about the knowledge base — pure functions in, data out.
Both cli.py and api/ are thin adapters that call into here.
"""
