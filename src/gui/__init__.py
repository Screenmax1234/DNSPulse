"""
GUI package for DNS Speed Checker.

Provides a modern web-based interface for running benchmarks.
"""

from .app import create_app, run_gui

__all__ = ["create_app", "run_gui"]
