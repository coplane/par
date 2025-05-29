import json
import os
import subprocess
from pathlib import Path

import typer

STATE_DIR = Path.home() / ".local" / "share" / "par"
STATE_FILE = STATE_DIR / "state.json"
app = typer.Typer()


def load_state():
    if not STATE_FILE.exists():
        return {}
    return json.loads(STATE_FILE.read_text())


def save_state(state):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2))


@app.command()
def start(label: str):
    """Start a git worktree and tmux session"""
    branch = label
    worktree = Path.cwd() / ".par" / f"{label}"
    subprocess.run(["git", "worktree", "add", "-b", branch, str(worktree)], check=True)
    session = f"par-{label}"
    subprocess.run(
        ["tmux", "new-session", "-d", "-s", session, "-c", str(worktree)], check=True
    )
    state = load_state()
    state[label] = {"branch": branch, "worktree": str(worktree), "session": session}
    save_state(state)
    typer.echo(f"Started session {label}")


@app.command()
def list():
    """List all sessions"""
    state = load_state()
    for label, info in state.items():
        typer.echo(f"{label}\tworktree={info['worktree']}\tsession={info['session']}")


@app.command()
def send(cmd: str, label: str = typer.Option(None, "-l", "--label")):
    """Send a command to session(s)"""
    state = load_state()
    targets = [state[label]] if label else state.values()
    for info in targets:
        session = info["session"]
        subprocess.run(
            ["tmux", "send-keys", "-t", f"{session}:", cmd, "Enter"], check=False
        )
        typer.echo(f"Sent to {session}")


@app.command()
def delete(label: str):
    """Delete session and worktree"""
    state = load_state()
    if label not in state:
        typer.echo("Label not found", err=True)
        raise typer.Exit(code=1)
    info = state.pop(label)
    subprocess.run(["tmux", "kill-session", "-t", info["session"]], check=False)
    subprocess.run(["git", "worktree", "remove", "-f", info["worktree"]], check=False)
    subprocess.run(["git", "branch", "-D", info["branch"]])
    save_state(state)
    typer.echo(f"Deleted {label}")


@app.command()
def attach(label: str):
    """Attach to a session in current tmux window"""
    state = load_state()
    info = state.get(label)
    if not info:
        typer.echo("Label not found", err=True)
        raise typer.Exit(code=1)
    session = info["session"]

    # Check if we're already inside tmux
    if os.environ.get("TMUX"):
        # We're inside tmux, so switch to the session instead of attaching
        os.execvp("tmux", ["tmux", "switch-client", "-t", session])
    else:
        # We're not inside tmux, so attach normally
        os.execvp("tmux", ["tmux", "attach-session", "-t", session])


@app.command()
def attach_all():
    """Open all sessions in tmux panes"""
    state = load_state()
    if not state:
        typer.echo("No sessions found", err=True)
        return

    control_session = "par-control"

    # Check if the control session already exists
    result = subprocess.run(
        ["tmux", "has-session", "-t", control_session], capture_output=True
    )

    if result.returncode == 0:
        # Session exists, just attach to it
        typer.echo("Control session already exists, attaching...")
        os.execvp("tmux", ["tmux", "attach-session", "-t", control_session])
        return

    # Session doesn't exist, create it
    (first_label, first_info), *remaining_items = state.items()

    # Create the control session
    subprocess.run(
        [
            "tmux",
            "new-session",
            "-d",
            "-s",
            control_session,
            "-c",
            first_info["worktree"],
        ]
    )

    subprocess.run(
        [
            "tmux",
            "send-keys",
            "-t",
            control_session,
            f"echo 'Session: {first_label} ({first_info['session']})'",
            "Enter",
        ]
    )

    # Add panes for the remaining sessions
    for label, info in remaining_items:
        worktree = info["worktree"]
        session = info["session"]

        subprocess.run(
            ["tmux", "split-window", "-h", "-t", control_session, "-c", worktree]
        )
        # Send a command to show which session this pane represents
        subprocess.run(
            [
                "tmux",
                "send-keys",
                "-t",
                control_session,
                f"echo 'Session: {label} ({session})'",
                "Enter",
            ]
        )

    # Balance the panes for better layout
    subprocess.run(["tmux", "select-layout", "-t", control_session, "tiled"])

    # Now attach to the control session
    os.execvp("tmux", ["tmux", "attach-session", "-t", control_session])
