# Par Tool

`par` is a command-line tool to simplify managing parallel development efforts using Git worktrees and tmux sessions within a single repository.

## Features

- **Start**: Quickly create a new Git worktree and an associated tmux session, isolated by a user-defined label.
- **Send**: Broadcast commands to specific or all managed tmux sessions.
- **List (ls)**: View all `par`-managed sessions for the current repository.
- **Remove (rm)**: Clean up by deleting a worktree and its corresponding tmux session and branch.
- **Open**: Attach to a specific `par` tmux session.
- **Control Center**: View all managed sessions simultaneously in a tiled tmux window layout.

## Prerequisites

- Git
- tmux
- Python 3.8+
- `uv` (for installation, optional if using other Python packaging tools)

## Installation

1.  Clone this repository (or ensure you have the source code).
2.  Navigate to the project root directory.
3.  Install using `uv`:
    ```bash
    uv tool install .
    # or, if you prefer a virtual environment
    # uv venv
    # source .venv/bin/activate
    # uv pip install .
    ```
After installation, the `par` command should be available in your shell.

## Usage

```bash
par --help
par start <label>
par ls
par send <label|all> "your command here"
par open <label>
par control-center
par rm <label|all>