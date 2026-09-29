#!/usr/bin/env python3
"""Compatibility entry point for running the CLI from a source checkout."""

import sys

from blipkit.cli import main

if __name__ == "__main__":
    sys.exit(main())
