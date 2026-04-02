import argparse
import hashlib
from pathlib import Path

from update_studios.json_store import load_json, write_json_atomic
from update_studios.paths import AppPaths
from update_studios.security import ensure_developer_key, sign_payload


def collect_files(game_dir: Path, patterns: list[str]) -> list[Path]:
    collected: dict[str, Path] = {}
    for pattern in patterns:
        matches = game_dir.glob(pattern)
        for path in matches:
            if path.is_file():
                collected[path.relative_to(game_dir).as_posix()] = path
    return [collected[key] for key in sorted(collected.keys())]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().lower()


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a signed Update Studios repository manifest.")
    parser.add_argument("--root", default=r"C:\UpdateStudios", help="Update Studios root directory.")
    parser.add_argument("--game-id", required=True, help="Game ID (for example: nova_strike).")
    parser.add_argument("--version", required=True, help="Version to publish (for example: 0.7.0).")
    parser.add_argument("--game-dir", required=True, help="Source game directory.")
    parser.add_argument(
        "--include",
        action="append",
        default=[],
        help="Glob pattern relative to game-dir. Can be used multiple times.",
    )
    parser.add_argument("--no-set-latest", action="store_true", help="Do not switch channel latest_version.")
    args = parser.parse_args()

    root = Path(args.root).expanduser().resolve()
    game_dir = Path(args.game_dir).expanduser().resolve()
    if not game_dir.exists():
        raise SystemExit(f"Game directory not found: {game_dir}")

    include_patterns = args.include or ["main.py", "requirements.txt", "README.md", "scripts/*.py"]
    files = collect_files(game_dir, include_patterns)
    if not files:
        raise SystemExit("No files matched include patterns.")

    paths = AppPaths.create(root=root)
    paths.ensure()
    secret = ensure_developer_key(paths)

    game_repo_root = paths.repository_dir / args.game_id
    files_root = game_repo_root / "files" / args.version
    files_root.mkdir(parents=True, exist_ok=True)

    entries = []
    for file in files:
        rel = file.relative_to(game_dir).as_posix()
        payload = file.read_bytes()
        digest = sha256_bytes(payload)
        target = files_root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
        entries.append(
            {
                "path": rel,
                "sha256": digest,
                "size": len(payload),
                "url": f"files/{args.version}/{rel}",
            }
        )

    manifest_payload = {
        "game_id": args.game_id,
        "version": args.version,
        "files": entries,
        "remove": [],
    }
    manifest_payload["signature"] = sign_payload(manifest_payload, secret)
    manifests_dir = game_repo_root / "manifests"
    manifests_dir.mkdir(parents=True, exist_ok=True)
    write_json_atomic(manifests_dir / f"{args.version}.json", manifest_payload)

    channel_path = game_repo_root / "channel.json"
    channel = load_json(channel_path, default={})
    if not isinstance(channel, dict):
        channel = {}
    channel["game_id"] = args.game_id
    if not args.no_set_latest or not channel.get("latest_version"):
        channel["latest_version"] = args.version
        channel["manifest"] = f"manifests/{args.version}.json"
    channel["signature"] = sign_payload({k: v for k, v in channel.items() if k != "signature"}, secret)
    write_json_atomic(channel_path, channel)
    print(f"Published {args.game_id} {args.version} with {len(entries)} file entries.")
    print(f"Manifest: {manifests_dir / f'{args.version}.json'}")


if __name__ == "__main__":
    main()
