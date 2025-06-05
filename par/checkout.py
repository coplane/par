"""Checkout support for existing branches and PRs."""

import re
from dataclasses import dataclass
from typing import Tuple
from urllib.parse import urlparse


@dataclass
class CheckoutStrategy:
    """Strategy for checking out different types of targets."""

    ref: str
    remote: str = "origin"
    fetch_remote: bool = False
    is_pr: bool = False


def parse_checkout_target(target: str) -> Tuple[str, CheckoutStrategy]:
    """Parse various target formats into branch name and checkout strategy."""

    # PR by number: pr/123
    if target.startswith("pr/"):
        pr_number = target[3:]
        if not pr_number.isdigit():
            raise ValueError(f"Invalid PR number: {pr_number}")
        return f"pr-{pr_number}", CheckoutStrategy(
            ref=f"origin/pull/{pr_number}/head", fetch_remote=True, is_pr=True
        )

    # PR by URL: https://github.com/owner/repo/pull/123
    if "github.com" in target:
        try:
            parsed = urlparse(target)
            path_parts = parsed.path.strip("/").split("/")

            # Check if it's a valid GitHub URL structure
            if len(path_parts) >= 4:
                if path_parts[2] == "pull":
                    pr_number = path_parts[3].split("?")[0]  # Remove query params
                    if not pr_number.isdigit():
                        raise ValueError(f"Invalid PR number in URL: {pr_number}")
                    return f"pr-{pr_number}", CheckoutStrategy(
                        ref=f"origin/pull/{pr_number}/head",
                        fetch_remote=True,
                        is_pr=True,
                    )
                else:
                    # It's a GitHub URL but not a pull request
                    raise ValueError(f"Could not parse PR URL: {target}")
            else:
                raise ValueError(f"Could not parse PR URL: {target}")
        except ValueError:
            # Re-raise ValueError as-is
            raise
        except Exception as e:
            raise ValueError(f"Invalid GitHub PR URL: {target}") from e

    # Remote branch: username:branch-name or remote/branch-name
    if ":" in target and not target.startswith("http"):
        remote_user, branch = target.split(":", 1)
        if not remote_user or not branch:
            raise ValueError(f"Invalid remote branch format: {target}")
        return generate_label_from_branch(branch), CheckoutStrategy(
            ref=f"{remote_user}/{branch}", remote=remote_user, fetch_remote=True
        )

    # Remote branch with slash: remote/branch-name
    if "/" in target and not target.startswith("origin/"):
        parts = target.split("/", 1)
        if len(parts) == 2:
            remote, branch = parts
            return generate_label_from_branch(branch), CheckoutStrategy(
                ref=target, remote=remote, fetch_remote=True
            )

    # Simple branch name (local or origin/branch)
    branch_name = target
    if target.startswith("origin/"):
        branch_name = target[7:]  # Remove "origin/" prefix

    return generate_label_from_branch(branch_name), CheckoutStrategy(ref=target)


def generate_label_from_branch(branch_name: str) -> str:
    """Generate session label from branch name."""
    # Clean up branch name for use as label
    # Replace slashes and underscores with hyphens, convert to lowercase
    label = re.sub(r"[/_]", "-", branch_name.lower())
    # Remove any other special characters except hyphens and alphanumeric
    label = re.sub(r"[^a-z0-9-]", "", label)
    # Remove leading/trailing hyphens and collapse multiple hyphens
    label = re.sub(r"-+", "-", label).strip("-")

    # Ensure we have a valid label
    if not label:
        label = "session"

    return label
