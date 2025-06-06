# src/par/cli.py
import typer
from typing import Optional
from click.shell_completion import CompletionItem
from typing_extensions import Annotated

from . import core

app = typer.Typer(
    name="par",
    help="Manage parallel git worktrees and tmux sessions.",
    add_completion=False,
)


def _session_label_complete(
    ctx: typer.Context, param: typer.CallbackParam, incomplete: str
) -> list[CompletionItem]:
    """Provide shell completions for existing session labels."""
    labels = [l for l in core.get_session_labels() if l.startswith(incomplete)]
    return [CompletionItem(label) for label in labels]


def _target_complete(
    ctx: typer.Context, param: typer.CallbackParam, incomplete: str
) -> list[CompletionItem]:
    """Completion for commands that take 'all' or a session label."""
    options = ["all"] + core.get_session_labels()
    matches = [o for o in options if o.startswith(incomplete)]
    return [CompletionItem(m) for m in matches]


def version_callback(value: bool):
    if value:
        typer.echo("par version: 0.1.0")
        raise typer.Exit()


@app.callback()
def main_callback(
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            "-v",
            callback=version_callback,
            is_eager=True,
            help="Show version and exit.",
        ),
    ] = False,
):
    """
    Par: Parallel Worktree & Tmux Manager
    """
    pass


@app.command()
def start(
    label: Annotated[
        str,
        typer.Argument(
            help="A unique label for the new worktree, branch, and tmux session."
        ),
    ],
):
    """
    Start a new git worktree and tmux session.
    Creates a worktree, a git branch (both named <label>), and a tmux session.
    """
    core.start_session(label)


@app.command()
def send(
    target: Annotated[
        str,
        typer.Argument(
            help="The label of the session to send the command to, or 'all'.",
            shell_complete=_target_complete,
        ),
    ],
    command_to_send: Annotated[
        str, typer.Argument(help="The command string to send to the tmux session(s).")
    ],
):
    """
    Send a command to a specific session or all sessions.
    The command will be followed by an 'Enter' key press in the tmux session.
    """
    core.send_command(target, command_to_send)


@app.command(name="ls")
def list_sessions():
    """
    List all 'par'-managed sessions for the current repository.
    Shows label, tmux session name, worktree path, and branch.
    """
    core.list_sessions()


@app.command()
def rm(
    target: Annotated[
        str,
        typer.Argument(
            help="The label of the session to remove, or 'all'.",
            shell_complete=_target_complete,
        )
    ],
):
    """
    Remove a 'par'-managed session (or all sessions).
    This kills the tmux session, removes the git worktree, and deletes the associated git branch.
    """
    if target.lower() == "all":
        core.remove_all_sessions()
    else:
        core.remove_session(target)


@app.command()
def checkout(
    target: Annotated[
        str,
        typer.Argument(
            help="Branch name, PR number (pr/123), PR URL, or remote branch (user:branch)"
        ),
    ],
    label: Annotated[
        Optional[str],
        typer.Option(
            "--label", "-l",
            help="Custom label for the session (defaults to branch name)"
        ),
    ] = None,
):
    """
    Checkout an existing branch or PR into a new par session.
    Creates a worktree from existing branch/PR without creating a new branch.
    """
    core.checkout_session(target, label)


@app.command()
def open(
    label: Annotated[
        str,
        typer.Argument(
            help="The label of the session to open/attach to.",
            shell_complete=_session_label_complete,
        )
    ],
):
    """
    Open/attach to a specific 'par'-managed tmux session.
    If inside tmux, switches client. If outside, attaches.
    """
    core.open_session(label)


@app.command(name="control-center")
def control_center():
    """
    Open all 'par'-managed sessions in a tiled tmux window (control center view).
    Must be run from within an existing tmux session.
    """
    core.open_control_center()


# This is for `python -m par`
if __name__ == "__main__":
    app()
