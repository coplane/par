"""Tests for the unified state manager."""

import json
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from .state_manager import StateManager


@pytest.fixture
def temp_state_file():
    """Create a temporary state file for testing."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        state_file = Path(f.name)
    yield state_file
    # Cleanup
    state_file.unlink(missing_ok=True)
    backup_file = state_file.with_suffix(".json.backup")
    backup_file.unlink(missing_ok=True)
    temp_file = state_file.with_suffix(".tmp")
    temp_file.unlink(missing_ok=True)


@pytest.fixture
def state_manager(temp_state_file):
    """Create a StateManager instance for testing."""
    with patch("par.utils.get_data_dir", return_value=temp_state_file.parent):
        manager = StateManager(
            temp_state_file.name, cache_ttl=1
        )  # Short TTL for testing
        return manager


class TestStateManager:
    """Test cases for StateManager class."""

    def test_load_empty_state(self, state_manager):
        """Test loading state when file doesn't exist."""
        state = state_manager.load()
        assert state == {}

    def test_save_and_load_state(self, state_manager):
        """Test saving and loading state."""
        test_state = {
            "test_key": {"session1": {"data": "value"}},
            "another_key": {"session2": {"data": "value2"}},
        }

        state_manager.save(test_state)
        loaded_state = state_manager.load()

        assert loaded_state == test_state

    def test_atomic_write(self, state_manager, temp_state_file):
        """Test that writes are atomic (no partial writes)."""
        test_state = {"key": "value"}

        # Simulate interruption during write by mocking json.dump to fail
        with patch("json.dump", side_effect=Exception("Write interrupted")):
            with pytest.raises(
                (SystemExit, Exception)
            ):  # StateManager calls typer.Exit(1)
                state_manager.save(test_state)

        # Ensure no partial write occurred
        if temp_state_file.exists():
            content = temp_state_file.read_text()
            if content:  # If file has content, it should be valid JSON
                json.loads(content)  # Should not raise exception

    def test_corrupted_state_backup(self, state_manager, temp_state_file):
        """Test handling of corrupted state files."""
        # Write invalid JSON
        temp_state_file.write_text("invalid json {")

        with patch("typer.secho"):  # Suppress warning output
            state = state_manager.load()

        # Should return empty state
        assert state == {}

        # Should create backup
        backup_file = temp_state_file.with_suffix(".json.backup")
        assert backup_file.exists()
        assert backup_file.read_text() == "invalid json {"

    def test_caching_behavior(self, state_manager):
        """Test that caching works correctly."""
        test_state = {"key": "value"}
        state_manager.save(test_state)

        # First load should read from disk
        state1 = state_manager.load()

        # Modify file directly (simulating external change)
        state_manager.state_file.write_text('{"key": "modified"}')

        # Second load should return cached value (within TTL)
        state2 = state_manager.load()
        assert state2 == state1  # Should be cached

        # Wait for cache to expire
        time.sleep(1.1)  # TTL is 1 second

        # Third load should read from disk again
        state3 = state_manager.load()
        assert state3 == {"key": "modified"}

    def test_cache_invalidation(self, state_manager):
        """Test manual cache invalidation."""
        test_state = {"key": "value"}
        state_manager.save(test_state)

        # Load to populate cache
        state_manager.load()

        # Modify file and invalidate cache
        state_manager.state_file.write_text('{"key": "modified"}')
        state_manager.invalidate_cache()

        # Should read fresh data
        state = state_manager.load()
        assert state == {"key": "modified"}

    def test_scoped_data_operations(self, state_manager):
        """Test scoped data operations."""
        # Test getting empty scoped data
        data = state_manager.get_scoped_data("test_scope")
        assert data == {}

        # Test updating scoped data
        test_data = {"session1": {"value": "test"}}
        state_manager.update_scoped_data("test_scope", test_data)

        # Verify update
        data = state_manager.get_scoped_data("test_scope")
        assert data == test_data

        # Test removing empty scope
        state_manager.update_scoped_data("test_scope", {})

        # Verify removal
        full_state = state_manager.load()
        assert "test_scope" not in full_state

    def test_remove_scope(self, state_manager):
        """Test scope removal."""
        # Add some scoped data
        state_manager.update_scoped_data("scope1", {"data": "value1"})
        state_manager.update_scoped_data("scope2", {"data": "value2"})

        # Remove one scope
        state_manager.remove_scope("scope1")

        # Verify removal
        full_state = state_manager.load()
        assert "scope1" not in full_state
        assert "scope2" in full_state

    def test_concurrent_access_safety(self, state_manager):
        """Test that state manager handles concurrent access gracefully."""
        # This is a basic test - in practice, more sophisticated locking might be needed
        test_state = {"key": "value"}
        state_manager.save(test_state)

        # Simulate concurrent modification by directly writing to file
        state_manager.state_file.write_text('{"key": "concurrent_change"}')

        # Manager should handle this gracefully
        state = state_manager.load()
        assert isinstance(state, dict)  # Should at least return a dict

    def test_directory_creation(self, temp_state_file):
        """Test that StateManager creates necessary directories."""
        # Create a nested path that doesn't exist
        nested_path = temp_state_file.parent / "new_subdir" / "test_state.json"

        with patch("par.utils.get_data_dir", return_value=temp_state_file.parent):
            manager = StateManager(str(nested_path), cache_ttl=1)
            manager.save({"test": "data"})

        # Directory and file should be created
        assert nested_path.exists()
        assert nested_path.parent.exists()


class TestStateManagerSingletons:
    """Test the singleton state manager functions."""

    @patch("par.utils.get_data_dir")
    def test_session_state_manager_singleton(self, mock_get_data_dir):
        """Test that session state manager is a singleton."""
        from .state_manager import get_session_state_manager

        mock_get_data_dir.return_value = Path("/tmp")

        manager1 = get_session_state_manager()
        manager2 = get_session_state_manager()

        assert manager1 is manager2

    @patch("par.utils.get_data_dir")
    def test_workspace_state_manager_singleton(self, mock_get_data_dir):
        """Test that workspace state manager is a singleton."""
        from .state_manager import get_workspace_state_manager

        mock_get_data_dir.return_value = Path("/tmp")

        manager1 = get_workspace_state_manager()
        manager2 = get_workspace_state_manager()

        assert manager1 is manager2

    @patch("par.utils.get_data_dir")
    def test_different_managers_are_distinct(self, mock_get_data_dir):
        """Test that session and workspace managers are different instances."""
        from .state_manager import (
            get_session_state_manager,
            get_workspace_state_manager,
        )

        mock_get_data_dir.return_value = Path("/tmp")

        session_manager = get_session_state_manager()
        workspace_manager = get_workspace_state_manager()

        assert session_manager is not workspace_manager
        assert session_manager.state_file.name == "state.json"
        assert workspace_manager.state_file.name == "workspaces.json"


# Performance tests (optional, for larger state files)
class TestStateManagerPerformance:
    """Performance tests for StateManager."""

    def test_large_state_performance(self, state_manager):
        """Test performance with large state files."""
        # Create a moderately large state (simulating many sessions)
        large_state = {}
        for i in range(100):
            large_state[f"repo_{i}"] = {
                f"session_{j}": {
                    "worktree_path": f"/path/to/worktree_{i}_{j}",
                    "tmux_session_name": f"par-repo_{i}-{j}",
                    "branch_name": f"branch_{j}",
                    "created_at": "2025-01-01T00:00:00",
                }
                for j in range(10)
            }

        # Test save performance
        start_time = time.time()
        state_manager.save(large_state)
        save_time = time.time() - start_time

        # Test load performance
        start_time = time.time()
        loaded_state = state_manager.load()
        load_time = time.time() - start_time

        # Basic performance checks (adjust thresholds as needed)
        assert save_time < 1.0, f"Save took too long: {save_time}s"
        assert load_time < 1.0, f"Load took too long: {load_time}s"
        assert loaded_state == large_state


if __name__ == "__main__":
    # Basic smoke test when run directly
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        with patch("par.utils.get_data_dir", return_value=tmpdir):
            manager = StateManager("test.json", cache_ttl=1)

            # Test basic operations
            manager.save({"test": "data"})
            data = manager.load()
            assert data == {"test": "data"}

            # Basic StateManager functionality verified
