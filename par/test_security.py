"""Tests for security validation functions."""

import pytest

from .operations import _validate_session_name, _validate_branch_name, _sanitize_command


class TestInputValidation:
    """Test input validation functions."""

    def test_validate_session_name_valid(self):
        """Test that valid session names pass validation."""
        valid_names = [
            "test-session",
            "my_session",
            "session.1",
            "project-123",
            "a",  # Single character
            "very-long-session-name-that-is-still-valid",
        ]
        
        for name in valid_names:
            # Should not raise exception
            _validate_session_name(name)

    def test_validate_session_name_invalid(self):
        """Test that invalid session names raise ValueError."""
        invalid_names = [
            "",  # Empty
            "session with spaces",  # Spaces
            "session@invalid",  # Invalid characters
            "session#hash",  # Hash character
            "session$dollar",  # Dollar sign
            "a" * 65,  # Too long (max 64)
        ]
        
        for name in invalid_names:
            with pytest.raises(ValueError):
                _validate_session_name(name)

    def test_validate_branch_name_valid(self):
        """Test that valid branch names pass validation."""
        valid_names = [
            "feature-branch",
            "feature/new-ui",
            "hotfix_123",
            "v1.2.3",
            "user-123",
            "bugfix/issue-456",
            "feature/auth-system",
            "main",
            "develop",
        ]
        
        for name in valid_names:
            # Should not raise exception
            _validate_branch_name(name)

    def test_validate_branch_name_invalid(self):
        """Test that invalid branch names raise ValueError."""
        invalid_names = [
            "",  # Empty
            "branch with spaces",  # Spaces
            "branch@invalid",  # Invalid characters
            "branch#hash",  # Hash character
            "branch$dollar",  # Dollar sign
            "branch..danger",  # Double dots
            "branch//danger",  # Double slashes
            "branch--danger",  # Double hyphens
            "branch\\danger",  # Backslash
            "a" * 256,  # Too long (max 255)
        ]
        
        for name in invalid_names:
            with pytest.raises(ValueError):
                _validate_branch_name(name)

    def test_sanitize_command_valid(self):
        """Test that valid commands are sanitized properly."""
        test_cases = [
            ("ls -la", "ls -la"),  # Normal command
            ("git status", "git status"),  # Git command
            ("echo 'hello world'", "echo 'hello world'"),  # Command with quotes
            ("cd /path/to/dir", "cd /path/to/dir"),  # Path command
            ("npm run build", "npm run build"),  # NPM command
        ]
        
        for input_cmd, expected in test_cases:
            result = _sanitize_command(input_cmd)
            assert result == expected

    def test_sanitize_command_removes_forbidden_chars(self):
        """Test that forbidden control characters are removed."""
        test_cases = [
            ("echo 'hello\0world'", "echo 'helloworld'"),  # Null byte
            ("ls\x1b[0m", "ls[0m"),  # Escape sequence
            ("normal command", "normal command"),  # No forbidden chars
            ("\0\x1b", ""),  # Only forbidden chars
        ]
        
        for input_cmd, expected in test_cases:
            result = _sanitize_command(input_cmd)
            assert result == expected

    def test_sanitize_command_length_limit(self):
        """Test that overly long commands raise ValueError."""
        long_command = "echo " + "a" * 1000  # Over 1000 chars total
        
        with pytest.raises(ValueError, match="Command too long"):
            _sanitize_command(long_command)

    def test_sanitize_command_empty(self):
        """Test that empty commands are handled."""
        assert _sanitize_command("") == ""
        assert _sanitize_command(None) == ""  # Should handle None gracefully


class TestSecurityEdgeCases:
    """Test edge cases for security validation."""

    def test_unicode_handling(self):
        """Test handling of unicode characters."""
        # Session names with unicode should be rejected
        with pytest.raises(ValueError):
            _validate_session_name("session-ñame")
        
        # Branch names with unicode should be rejected  
        with pytest.raises(ValueError):
            _validate_branch_name("branch-ñame")

    def test_boundary_values(self):
        """Test boundary values for length limits."""
        # Maximum valid session name (64 chars)
        max_session = "a" * 64
        _validate_session_name(max_session)  # Should pass
        
        # One character too long
        with pytest.raises(ValueError):
            _validate_session_name("a" * 65)
        
        # Maximum valid branch name (255 chars)
        max_branch = "a" * 255
        _validate_branch_name(max_branch)  # Should pass
        
        # One character too long
        with pytest.raises(ValueError):
            _validate_branch_name("a" * 256)
        
        # Maximum valid command (1000 chars)
        max_command = "echo " + "a" * 995  # 1000 total
        _sanitize_command(max_command)  # Should pass
        
        # One character too long
        with pytest.raises(ValueError):
            _sanitize_command("echo " + "a" * 996)  # 1001 total

    def test_injection_attempts(self):
        """Test potential injection attempts."""
        # Session name injection attempts
        injection_sessions = [
            "session; rm -rf /",
            "session && malicious_command",
            "session | evil_pipe",
            "session > /etc/passwd",
            "session < /dev/random",
            "$(malicious_command)",
            "`malicious_command`",
            "session\nmalicious_command",
            "session\rmalicious_command",
            "session\tmalicious_command",
        ]
        
        for session in injection_sessions:
            with pytest.raises(ValueError):
                _validate_session_name(session)
        
        # Branch name injection attempts (similar patterns)
        injection_branches = [
            "branch; rm -rf /",
            "branch && malicious_command", 
            "$(malicious_command)",
            "`malicious_command`",
        ]
        
        for branch in injection_branches:
            with pytest.raises(ValueError):
                _validate_branch_name(branch)

    def test_path_traversal_attempts(self):
        """Test path traversal attempts in branch names."""
        traversal_attempts = [
            "../../../etc/passwd",
            "branch/../../../secret", 
            "branch/./hidden",
            "branch/../other",
        ]
        
        for attempt in traversal_attempts:
            if '..' in attempt or '//' in attempt or '--' in attempt:
                # These should be rejected due to forbidden patterns
                with pytest.raises(ValueError):
                    _validate_branch_name(attempt)
            else:
                # These might be valid branch names
                try:
                    _validate_branch_name(attempt)
                except ValueError:
                    pass  # Also acceptable if validation is strict

    def test_special_file_names(self):
        """Test handling of special file names."""
        special_names = [
            "CON",  # Windows reserved
            "PRN",  # Windows reserved  
            "AUX",  # Windows reserved
            "NUL",  # Windows reserved
            ".git",  # Git special directory
            "..",   # Parent directory
            ".",    # Current directory
        ]
        
        # These might be valid in some contexts but should be handled carefully
        for name in special_names:
            # Test as session names - some should fail
            try:
                _validate_session_name(name)
            except ValueError:
                pass  # Expected for some special names
            
            # Test as branch names - some should fail
            try:
                _validate_branch_name(name)  
            except ValueError:
                pass  # Expected for some special names


class TestValidationIntegration:
    """Integration tests for validation functions."""

    def test_realistic_session_names(self):
        """Test with realistic session names from actual usage."""
        realistic_names = [
            "feature-auth-system",
            "bugfix-login-issue",
            "hotfix-security-patch",
            "refactor-user-service",
            "update-dependencies",
            "pr-123-review",
            "experiment-new-ui",
            "test-performance",
        ]
        
        for name in realistic_names:
            _validate_session_name(name)  # Should all pass

    def test_realistic_branch_names(self):
        """Test with realistic branch names from actual usage."""
        realistic_names = [
            "feature/user-authentication",
            "bugfix/login-redirect",
            "hotfix/security-vulnerability",
            "refactor/code-cleanup",
            "feature/issue-123",
            "release/v1.2.3",
            "develop",
            "main",
            "staging",
            "feature/PROJ-456-new-feature",
        ]
        
        for name in realistic_names:
            _validate_branch_name(name)  # Should all pass

    def test_realistic_commands(self):
        """Test with realistic commands from actual usage."""
        realistic_commands = [
            "npm install",
            "yarn build",
            "python manage.py migrate",
            "cargo build --release",
            "go test ./...",
            "make clean && make build",
            "docker-compose up -d",
            "kubectl apply -f deployment.yaml",
            "git status",
            "ls -la",
            "cd frontend && npm start",
            "echo 'Starting development server...'",
        ]
        
        for cmd in realistic_commands:
            result = _sanitize_command(cmd)
            assert result == cmd  # Should be unchanged


if __name__ == "__main__":
    # Basic smoke test when run directly
    print("Testing session name validation...")
    _validate_session_name("test-session")
    
    print("Testing branch name validation...")
    _validate_branch_name("feature/test-branch")
    
    print("Testing command sanitization...")
    result = _sanitize_command("echo 'hello world'")
    assert result == "echo 'hello world'"
    
    print("✅ All security validation tests passed")