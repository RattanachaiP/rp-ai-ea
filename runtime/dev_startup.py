"""Development entrypoint for the governed production startup chain.

This module intentionally contains no alternative Runtime composition.  Development
and production therefore cross the same PR184 through PR190 fail-closed boundaries.
"""

from typing import Optional, Sequence

from runtime import production_startup


def main(argv: Optional[Sequence[str]] = None):
    """Delegate development startup to the sole governed production entrypoint."""
    return production_startup.main(argv)


if __name__ == "__main__":
    main()
