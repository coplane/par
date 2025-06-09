"""Unified state management for Par sessions and workspaces."""

import json
import shutil
import time
from typing import Any, Dict, Optional

import typer

from . import utils
from .constants import Config


class StateManager:
    """Unified state manager for both sessions and workspaces."""
    
    def __init__(self, filename: str, cache_ttl: int = 30):
        """Initialize state manager.
        
        Args:
            filename: Name of the state file (e.g., "state.json", "workspaces.json")
            cache_ttl: Cache time-to-live in seconds
        """
        self.state_file = utils.get_data_dir() / filename
        self.cache_ttl = cache_ttl
        self._cache: Optional[Dict[str, Any]] = None
        self._cache_time: float = 0
    
    def load(self) -> Dict[str, Any]:
        """Load state from file with caching."""
        now = time.time()
        
        # Return cached data if still valid
        if (self._cache is not None and 
            now - self._cache_time < self.cache_ttl):
            return self._cache
        
        # Load fresh data from disk
        if not self.state_file.exists():
            self._cache = {}
            self._cache_time = now
            return self._cache

        try:
            with open(self.state_file, "r") as f:
                content = f.read().strip()
                self._cache = json.loads(content) if content else {}
                self._cache_time = now
                return self._cache
        except json.JSONDecodeError as e:
            # Create backup before starting fresh
            backup_file = self.state_file.with_suffix('.json.backup')
            if self.state_file.exists():
                shutil.copy2(self.state_file, backup_file)
                typer.secho(
                    f"Warning: State file corrupted ({e}). Backed up to {backup_file.name}",
                    fg="yellow"
                )
            else:
                typer.secho(f"Warning: State file corrupted ({e}).", fg="yellow")
            
            typer.secho("Starting with fresh state.", fg="yellow")
            self._cache = {}
            self._cache_time = now
            return self._cache
        except Exception as e:
            typer.secho(f"Error reading state file: {e}", fg="red", err=True)
            raise typer.Exit(1)

    def save(self, state: Dict[str, Any]) -> None:
        """Save state to file and update cache."""
        try:
            # Ensure directory exists
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Create temporary file for atomic write
            temp_file = self.state_file.with_suffix('.tmp')
            
            with open(temp_file, "w") as f:
                json.dump(state, f, indent=2)
            
            # Atomic move
            temp_file.replace(self.state_file)
            
            # Update cache
            self._cache = state.copy()
            self._cache_time = time.time()
            
        except Exception as e:
            typer.secho(f"Error saving state: {e}", fg="red", err=True)
            # Clean up temp file if it exists
            if 'temp_file' in locals():
                temp_file.unlink(missing_ok=True)
            raise typer.Exit(1)

    def get_scoped_data(self, scope_key: str) -> Dict[str, Any]:
        """Get data for a specific scope (e.g., repository or workspace)."""
        state = self.load()
        return state.get(scope_key, {})

    def update_scoped_data(self, scope_key: str, data: Dict[str, Any]) -> None:
        """Update data for a specific scope."""
        state = self.load()
        
        if data:
            state[scope_key] = data
        else:
            # Remove empty scope entries to keep state file clean
            state.pop(scope_key, None)
        
        self.save(state)

    def remove_scope(self, scope_key: str) -> None:
        """Remove all data for a specific scope."""
        state = self.load()
        if scope_key in state:
            del state[scope_key]
            self.save(state)

    def invalidate_cache(self) -> None:
        """Invalidate the cache to force reload on next access."""
        self._cache = None
        self._cache_time = 0


# Global state managers
_session_manager: Optional[StateManager] = None
_workspace_manager: Optional[StateManager] = None


def get_session_state_manager() -> StateManager:
    """Get the singleton session state manager."""
    global _session_manager
    if _session_manager is None:
        _session_manager = StateManager(Config.SESSION_STATE_FILE, Config.STATE_CACHE_TTL)
    return _session_manager


def get_workspace_state_manager() -> StateManager:
    """Get the singleton workspace state manager."""
    global _workspace_manager
    if _workspace_manager is None:
        _workspace_manager = StateManager(Config.WORKSPACE_STATE_FILE, Config.STATE_CACHE_TTL)
    return _workspace_manager