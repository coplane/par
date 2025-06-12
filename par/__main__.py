#!/usr/bin/env python3
"""Entry point for running par as a module with `python -m par`."""

from .cli import app

if __name__ == "__main__":
    app()