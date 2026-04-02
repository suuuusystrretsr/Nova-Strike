import argparse
import json
from pathlib import Path

from update_studios.paths import AppPaths
from update_studios.security import ensure_developer_key, sign_payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Sign a developer package payload for Update Studios.")
    parser.add_argument("--root", default=r"C:\UpdateStudios", help="Update Studios install root.")
    parser.add_argument("--payload", required=True, help="Path to payload JSON file.")
    parser.add_argument(
        "--out",
        default="",
        help="Output path for signed envelope JSON. Default goes to studio_drop/incoming/<payload_name>.signed.json",
    )
    args = parser.parse_args()

    root = Path(args.root).expanduser().resolve()
    payload_path = Path(args.payload).expanduser().resolve()
    if not payload_path.exists():
        raise SystemExit(f"Payload file not found: {payload_path}")

    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit("Payload must be a JSON object.")

    paths = AppPaths.create(root=root)
    paths.ensure()
    secret = ensure_developer_key(paths)
    envelope = {"payload": payload, "signature": sign_payload(payload, secret)}

    if args.out:
        out_path = Path(args.out).expanduser().resolve()
    else:
        out_path = paths.incoming_drop_dir / f"{payload_path.stem}.signed.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(envelope, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Signed package written: {out_path}")


if __name__ == "__main__":
    main()
