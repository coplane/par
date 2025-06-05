"""Tests for par checkout functionality."""

import pytest

from . import checkout


def test_parse_pr_number():
    """Test parsing PR by number."""
    branch_name, strategy = checkout.parse_checkout_target("pr/123")

    assert branch_name == "pr-123"
    assert strategy.ref == "origin/pull/123/head"
    assert strategy.fetch_remote is True
    assert strategy.is_pr is True


def test_parse_pr_url():
    """Test parsing GitHub PR URL."""
    url = "https://github.com/owner/repo/pull/456"
    branch_name, strategy = checkout.parse_checkout_target(url)

    assert branch_name == "pr-456"
    assert strategy.ref == "origin/pull/456/head"
    assert strategy.fetch_remote is True
    assert strategy.is_pr is True


def test_parse_pr_url_with_params():
    """Test parsing GitHub PR URL with query parameters."""
    url = "https://github.com/owner/repo/pull/789?tab=files"
    branch_name, strategy = checkout.parse_checkout_target(url)

    assert branch_name == "pr-789"
    assert strategy.ref == "origin/pull/789/head"


def test_parse_remote_branch_colon():
    """Test parsing remote branch with colon format."""
    branch_name, strategy = checkout.parse_checkout_target("alice:feature-branch")

    assert branch_name == "feature-branch"
    assert strategy.ref == "alice/feature-branch"
    assert strategy.remote == "alice"
    assert strategy.fetch_remote is True


def test_parse_remote_branch_slash():
    """Test parsing remote branch with slash format."""
    branch_name, strategy = checkout.parse_checkout_target("upstream/develop")

    assert branch_name == "develop"
    assert strategy.ref == "upstream/develop"
    assert strategy.remote == "upstream"
    assert strategy.fetch_remote is True


def test_parse_origin_branch():
    """Test parsing origin branch."""
    branch_name, strategy = checkout.parse_checkout_target("origin/feature")

    assert branch_name == "feature"
    assert strategy.ref == "origin/feature"
    assert strategy.remote == "origin"
    assert strategy.fetch_remote is False


def test_parse_simple_branch():
    """Test parsing simple local branch name."""
    branch_name, strategy = checkout.parse_checkout_target("main")

    assert branch_name == "main"
    assert strategy.ref == "main"
    assert strategy.remote == "origin"
    assert strategy.fetch_remote is False


def test_parse_invalid_pr_number():
    """Test parsing invalid PR number."""
    with pytest.raises(ValueError, match="Invalid PR number"):
        checkout.parse_checkout_target("pr/abc")


def test_parse_invalid_pr_url():
    """Test parsing invalid GitHub URL."""
    with pytest.raises(ValueError, match="Could not parse PR URL"):
        checkout.parse_checkout_target("https://github.com/owner/repo/issues/123")


def test_parse_invalid_remote_format():
    """Test parsing invalid remote format."""
    with pytest.raises(ValueError, match="Invalid remote branch format"):
        checkout.parse_checkout_target(":")

    with pytest.raises(ValueError, match="Invalid remote branch format"):
        checkout.parse_checkout_target("alice:")


def test_generate_label_from_branch():
    """Test label generation from branch names."""
    # Normal branch
    assert checkout.generate_label_from_branch("feature-branch") == "feature-branch"

    # Branch with slashes
    assert checkout.generate_label_from_branch("feature/new-ui") == "feature-new-ui"

    # Branch with underscores
    assert checkout.generate_label_from_branch("bug_fix_123") == "bug-fix-123"

    # Mixed case
    assert checkout.generate_label_from_branch("Feature-Branch") == "feature-branch"

    # Special characters
    assert checkout.generate_label_from_branch("fix@issue#123") == "fixissue123"

    # Multiple consecutive separators
    assert checkout.generate_label_from_branch("feature//new___ui") == "feature-new-ui"

    # Leading/trailing separators
    assert checkout.generate_label_from_branch("/feature-branch/") == "feature-branch"

    # Empty result
    assert checkout.generate_label_from_branch("@#$%") == "session"


def test_generate_label_edge_cases():
    """Test edge cases for label generation."""
    # Only separators
    assert checkout.generate_label_from_branch("///___") == "session"

    # Empty string
    assert checkout.generate_label_from_branch("") == "session"

    # Single character
    assert checkout.generate_label_from_branch("a") == "a"

    # Numbers only
    assert checkout.generate_label_from_branch("123") == "123"


class TestCheckoutStrategy:
    """Test CheckoutStrategy dataclass."""

    def test_default_values(self):
        """Test default strategy values."""
        strategy = checkout.CheckoutStrategy(ref="main")

        assert strategy.ref == "main"
        assert strategy.remote == "origin"
        assert strategy.fetch_remote is False
        assert strategy.is_pr is False

    def test_custom_values(self):
        """Test custom strategy values."""
        strategy = checkout.CheckoutStrategy(
            ref="feature/branch", remote="upstream", fetch_remote=True, is_pr=True
        )

        assert strategy.ref == "feature/branch"
        assert strategy.remote == "upstream"
        assert strategy.fetch_remote is True
        assert strategy.is_pr is True
