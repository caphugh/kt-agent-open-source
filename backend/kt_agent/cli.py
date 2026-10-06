import typer

app = typer.Typer(help="CLI for the KT Agent application.")

init_app = typer.Typer(
    help="Initialize the knowledge-base directory and SQLite schema."
)
ingest_app = typer.Typer(
    help="Discover and ingest supported documents."
)
search_app = typer.Typer(
    help="Search the knowledge base without calling an LLM."
)
ask_app = typer.Typer(
    help="Ask a grounded question using the knowledge base."
)
eval_app = typer.Typer(help="Evaluate knowledge-base retrieval and answers.")

app.add_typer(init_app, name="init")
app.add_typer(ingest_app, name="ingest")
app.add_typer(search_app, name="search")
app.add_typer(ask_app, name="ask")
app.add_typer(eval_app, name="eval")


@init_app.callback(invoke_without_command=True)
def init() -> None:
    """Placeholder for knowledge-base initialization."""


@ingest_app.callback(invoke_without_command=True)
def ingest() -> None:
    """Placeholder for document ingestion."""


@search_app.callback(invoke_without_command=True)
def search() -> None:
    """Placeholder for deterministic search."""


@ask_app.callback(invoke_without_command=True)
def ask() -> None:
    """Placeholder for grounded answers."""


@eval_app.command("retrieval")
def eval_retrieval() -> None:
    """Placeholder for retrieval evaluation."""


@eval_app.command("answers")
def eval_answers() -> None:
    """Placeholder for answer evaluation."""


@app.command()
def status() -> None:
    """Placeholder for knowledge-base status."""


@app.command()
def metrics() -> None:
    """Placeholder for local run metrics."""
