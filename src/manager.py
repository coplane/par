# src/par/manager.py
import datetime
import json
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

import typer

from .utils import get_data_dir, get_git_repo_root  # Added get_repo_worktrees_dir

STATE_FILENAME = "state.json"


class SessionManager:
    def __init__(self):
        self.data_dir = get_data_dir()
        self.state_file = self.data_dir / STATE_FILENAME
        self._full_state = self._load_full_state()  # Load the entire state file

    def _load_full_state(self) -> Dict[str, Any]:
        if self.state_file.exists():
            try:
                with open(self.state_file, "r") as f:
                    content = f.read()
                    if not content.strip():  # Handle empty file case
                        return {}
                    return json.loads(content)
            except json.JSONDecodeError:
                typer.secho(
                    f"Warning: State file {self.state_file} is corrupted. Backing up and starting fresh.",
                    fg=typer.colors.YELLOW,
                    err=True,
                )
                # Optional: Backup corrupted file
                # self.state_file.rename(self.state_file.with_suffix('.corrupted'))
                return {}
        return {}

    def _save_full_state(self):
        self.data_dir.mkdir(parents=True, exist_ok=True)
        with open(self.state_file, "w") as f:
            json.dump(self._full_state, f, indent=4)

    def _get_current_repo_key(self) -> str:  # New private helper
        """Gets the key for the current repository in the state."""
        repo_root = (
            get_git_repo_root()
        )  # This will raise typer.Exit if not in a git repo
        return str(repo_root.resolve())

    def _get_current_repo_state(self) -> Dict[str, Any]:  # New private helper
        """Gets the state dictionary for the current repository."""
        repo_key = self._get_current_repo_key()
        return self._full_state.setdefault(repo_key, {})  # Ensure repo key exists

    def add_session(
        self, label: str, worktree_path: Path, tmux_session_name: str, branch_name: str
    ):
        current_repo_sessions = self._get_current_repo_state()

        if label in current_repo_sessions:
            # This check should ideally be done before creating resources too
            typer.secho(
                f"Error: Session with label '{label}' already exists in state for this repository.",
                fg=typer.colors.RED,
                err=True,
            )
            # Potentially offer to clean up or adopt if resources exist but state is inconsistent
            raise typer.Exit(1)

        current_repo_sessions[label] = {
            "worktree_path": str(worktree_path.resolve()),  # Store resolved path
            "tmux_session_name": tmux_session_name,
            "branch_name": branch_name,
            "created_at": datetime.datetime.utcnow().isoformat(),
        }
        self._save_full_state()
        typer.secho(
            f"Session '{label}' added to state for current repository.",
            fg=typer.colors.GREEN,
        )

    def remove_session(self, label: str) -> Optional[Dict[str, Any]]:
        current_repo_sessions = self._get_current_repo_state()

        if label in current_repo_sessions:
            session_data = current_repo_sessions.pop(label)

            # If this was the last session for the repo, remove the repo key itself
            if not current_repo_sessions:
                repo_key = self._get_current_repo_key()
                self._full_state.pop(repo_key, None)

            # Attempt to remove the physical worktree directory
            # Ensure it's a path managed by par before deleting
            worktree_physical_path = Path(session_data["worktree_path"])
            # Check if worktree_physical_path is inside any of the repo-specific worktree dirs
            # This is a bit tricky as get_repo_worktrees_dir needs a repo_root.
            # Assuming the worktree_path stored is correct and was created by par:
            if (
                worktree_physical_path.exists()
                and get_data_dir() in worktree_physical_path.parents
            ):
                try:
                    shutil.rmtree(worktree_physical_path)
                    typer.secho(
                        f"Removed physical worktree directory: {worktree_physical_path}",
                        fg=typer.colors.GREEN,
                    )
                except OSError as e:
                    typer.secho(
                        f"Warning: Could not remove physical worktree directory {worktree_physical_path}: {e}",
                        fg=typer.colors.YELLOW,
                        err=True,
                    )

            self._save_full_state()
            typer.secho(
                f"Session '{label}' removed from state for current repository.",
                fg=typer.colors.GREEN,
            )
            return session_data

        # If not in state, don't print error, as actions.py might call this during cleanup
        # typer.secho(f"Session '{label}' not found in state for this repository.", fg=typer.colors.YELLOW)
        return None

    def get_session(self, label: str) -> Optional[Dict[str, Any]]:
        current_repo_sessions = self._get_current_repo_state()
        return current_repo_sessions.get(label)

    def get_all_sessions_for_current_repo(self) -> List[Dict[str, Any]]:
        current_repo_sessions = self._get_current_repo_state()
        sessions_list = []
        for label, data in current_repo_sessions.items():
            data_copy = data.copy()
            data_copy["label"] = label  # Add label into the session data itself
            sessions_list.append(data_copy)
        return sessions_list
