# src/par/cli.py
import typer
from typing_extensions import Annotated

from . import actions

app = typer.Typer(
    name="par",
    help="Manage parallel git worktrees and tmux sessions.",
    add_completion=False,
)


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
    actions.start_new_session(label)


@app.command()
def send(
    target: Annotated[
        str,
        typer.Argument(
            help="The label of the session to send the command to, or 'all'."
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
    actions.send_command_to_sessions(target, command_to_send)


@app.command(name="ls")
def list_sessions():
    """
    List all 'par'-managed sessions for the current repository.
    Shows label, tmux session name, worktree path, and branch.
    """
    actions.list_sessions_action()


@app.command()
def rm(
    target: Annotated[
        str, typer.Argument(help="The label of the session to remove, or 'all'.")
    ],
):
    """
    Remove a 'par'-managed session (or all sessions).
    This kills the tmux session, removes the git worktree, and deletes the associated git branch.
    """
    if target.lower() == "all":
        actions.remove_all_sessions_action()
    else:
        actions.remove_session_action(target)


@app.command()
def open(
    label: Annotated[
        str, typer.Argument(help="The label of the session to open/attach to.")
    ],
):
    """
    Open/attach to a specific 'par'-managed tmux session.
    If inside tmux, switches client. If outside, attaches.
    """
    actions.open_session_action(label)


@app.command(name="control-center")
def control_center():
    """
    Open all 'par'-managed sessions in a tiled tmux window (control center view).
    Must be run from within an existing tmux session.
    """
    actions.open_control_center_action()


# This is for `python -m par`
if __name__ == "__main__":
    app()
