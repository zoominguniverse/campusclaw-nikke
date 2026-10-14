"""Operator commands: run inside the API environment after taking a backup."""
import argparse
import json

from app import create_app
from app.generation_restore import restore_generation
from app.indexing import backfill_entries


def main():
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    restore = commands.add_parser("restore")
    restore.add_argument("--entry-id", type=int, required=True)
    restore.add_argument("--generation-id", type=int, required=True)
    restore.add_argument("--legacy-only", action="store_true")
    restore.add_argument("--dry-run", action="store_true")
    rebuild = commands.add_parser("backfill")
    rebuild.add_argument("--limit", type=int, default=100)
    rebuild.add_argument("--after", type=int, default=0)
    rebuild.add_argument("--dry-run", action="store_true")
    rebuild.add_argument("--force", action="store_true")
    rebuild.add_argument("--profile-id", type=int)
    args = parser.parse_args()
    app = create_app({"INITIALIZE_DATABASE": False, "SEMANTIC_RELEASE": False})
    with app.app_context():
        try:
            result = restore_generation(args.entry_id, args.generation_id, legacy_only=args.legacy_only, dry_run=args.dry_run) if args.command == "restore" else backfill_entries(args.limit, after=args.after, dry_run=args.dry_run, force=args.force, profile_id=args.profile_id)
        except ValueError as error:
            parser.error(str(error))
        print(json.dumps(result))


if __name__ == "__main__":
    main()
