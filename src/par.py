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
    worktree = Path.cwd() / f"{label}"
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
    os.execvp("tmux", ["tmux", "attach-session", "-t", session])


@app.command()
def attach_all():
    """Open all sessions in tmux panes"""
    state = load_state()
    first = True
    for info in state.values():
        session = info["session"]
        if first:
            subprocess.run(
                [
                    "tmux",
                    "new-window",
                    "-n",
                    "par",
                    "tmux",
                    "attach-session",
                    "-t",
                    session,
                ]
            )
            first = False
        else:
            subprocess.run(
                ["tmux", "split-window", "-h", "tmux", "attach-session", "-t", session]
            )
    typer.echo("Opened control center")
