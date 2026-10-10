"""Back up, verify, or restore an offline PRECISO graph. No provider calls."""

import argparse
import json

from core.backup import backup_graph, restore_graph, verify_backup


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="operation", required=True)
    for name in ("backup", "restore", "verify"):
        command = commands.add_parser(name)
        command.add_argument("source")
        if name != "verify":
            command.add_argument("destination")
    args = parser.parse_args()
    try:
        if args.operation == "verify":
            result = verify_backup(args.source)
        elif args.operation == "backup":
            result = backup_graph(args.source, args.destination)
        else:
            result = restore_graph(args.source, args.destination)
    except (OSError, ValueError, RuntimeError) as exc:
        parser.exit(1, f"{args.operation} failed: {exc}\n")
    print(json.dumps({"operation": args.operation, "status": "success", "artifacts": len(result["files"])}))


if __name__ == "__main__":
    main()
