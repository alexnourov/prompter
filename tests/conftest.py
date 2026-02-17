"""Pytest configuration: shared fixtures and markers."""

import pytest


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "e2e: end-to-end tests (require real AI assistant)"
    )
