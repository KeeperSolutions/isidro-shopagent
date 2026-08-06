"""Rich console helpers for terminal output."""

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

from shopagent.costs import total_tokens

console = Console()


def print_welcome():
    console.print(
        Panel.fit(
            "[bold]ShopAgent[/bold]\n"
            "A Conversational Commerce Assistant\n"
            "[dim]Type [bold]quit[/bold] or [bold]exit[/bold] to leave[/dim]",
            border_style="cyan",
            padding=(1, 2),
        )
    )
    console.print()


def ask_user() -> str:
    return Prompt.ask("[bold cyan]You[/bold cyan]").strip()


def print_agent_prefix():
    console.print("[bold magenta]ShopAgent:[/bold magenta] ", end="")


def print_moderation_message():
    console.print(
        "I'm sorry, I can't help with that request.",
        markup=False,
    )


def print_message(text: str):
    console.print(text, markup=False)
    console.print()


def print_usage(message_usage, message_cost, session_usage, session_cost):
    table = Table(show_header=True, header_style="bold", box=None, padding=(0, 1))
    table.add_column("Usage", style="dim")
    table.add_column("Input", justify="right")
    table.add_column("Output", justify="right")
    table.add_column("Total", justify="right")
    table.add_column("Cost", justify="right")

    def add_row(label, usage, cost):
        table.add_row(
            label,
            f"{usage['input_tokens']:,}",
            f"{usage['output_tokens']:,}",
            f"{total_tokens(usage):,}",
            f"${cost:.4f}",
        )

    add_row("Last message", message_usage, message_cost)
    add_row("Session total", session_usage, session_cost)

    console.print()
    console.print()
    console.print(table)
    console.print()


def print_goodbye():
    console.print("[bold]Goodbye![/bold]")
