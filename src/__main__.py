"""
Entry point for running dns_speedchecker as a module.

Usage: python -m dns_speedchecker [OPTIONS] COMMAND [ARGS]...
"""

from .cli import main

if __name__ == "__main__":
    main()
