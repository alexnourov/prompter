"""Pytest configuration for Prompter tests."""

import pytest


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers",
        "e2e: end-to-end tests (require real claude CLI)"
    )
