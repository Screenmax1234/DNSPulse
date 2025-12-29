# Contributing to DNS Speed Checker

Thank you for your interest in contributing! This document provides guidelines and instructions for contributing.

## Getting Started

1. Fork the repository
2. Clone your fork locally
3. Install development dependencies:
   ```bash
   pip install -e ".[dev]"
   ```

## Development Setup

```bash
# Create a virtual environment (recommended)
python -m venv venv

# Activate it
# Windows:
venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

# Install with all optional dependencies
pip install -e ".[all]"
```

## Running Tests

```bash
pytest
```

## Code Style

- Follow PEP 8 guidelines
- Use type hints where appropriate
- Write docstrings for public functions and classes

## Submitting Changes

1. Create a new branch for your feature/fix
2. Make your changes
3. Write/update tests as needed
4. Ensure all tests pass
5. Submit a pull request

## Reporting Issues

When reporting issues, please include:
- Python version
- Operating system
- Steps to reproduce
- Expected vs actual behavior
