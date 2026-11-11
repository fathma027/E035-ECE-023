#!/usr/bin/env python3
"""Usage: python main.py <commands.txt> [output_dir]     (Python 3.10+, standard library only)

Writes bills.csv and collection_summary.csv to output_dir (default ./output);
prints readable bills/summaries on stdout and ERROR/WARN/INFO on stderr."""
import sys

from billing.commands import CommandRunner


def main(argv):
    if len(argv) not in (2, 3):
        print(__doc__.strip(), file=sys.stderr)
        return 2
    runner = CommandRunner(out_dir=argv[2] if len(argv) == 3 else "output")
    try:
        runner.run_file(argv[1])
    except OSError as e:
        print(f"FATAL: {e}", file=sys.stderr)
        return 2
    return 1 if runner.error_count else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
