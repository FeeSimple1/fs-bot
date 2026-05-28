"""Entry point for `python -m fs_bot` — Phase 6 CLI.

See fs_bot.cli.app for the actual implementation. This module only
forwards to main() so the package is launchable from the command line.
"""

from fs_bot.cli.app import main


if __name__ == "__main__":
    raise SystemExit(main())
