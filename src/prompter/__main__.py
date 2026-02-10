"""Entry point for running prompter as a module.

Allows execution via: python -m prompter
"""

from .cli import app

if __name__ == "__main__":
    app()
