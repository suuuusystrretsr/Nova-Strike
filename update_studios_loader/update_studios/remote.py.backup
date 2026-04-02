import json
import os
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse, unquote
from urllib.request import urlopen


class RemoteError(Exception):
    pass


class RemoteRepository:
    def __init__(
        self,
        allowed_local_roots: list[Path] | None = None,
        max_download_bytes: int = 512 * 1024 * 1024,
    ) -> None:
        self.allowed_local_roots = [Path(root).expanduser().resolve() for root in (allowed_local_roots or [])]
        self.max_download_bytes = max(1_048_576, int(max_download_bytes))

    def read_bytes(self, uri: str, timeout: float = 20.0) -> bytes:
        uri = str(uri or "").strip()
        if not uri:
            raise RemoteError("Empty update source URI")
        parsed = urlparse(uri)
        if parsed.scheme in ("http", "https"):
            try:
                with urlopen(uri, timeout=timeout) as response:
                    expected_length = self._content_length(response)
                    if expected_length is not None and expected_length > self.max_download_bytes:
                        raise RemoteError("Remote file is too large.")
                    data = response.read(self.max_download_bytes + 1)
                    if len(data) > self.max_download_bytes:
                        raise RemoteError("Remote file exceeds size limit.")
                    return data
            except Exception as exc:
                raise RemoteError(str(exc)) from exc
        path = self._resolve_local_path(uri)
        if not path.exists():
            raise RemoteError(f"Missing file: {path}")
        try:
            size = path.stat().st_size
            if size > self.max_download_bytes:
                raise RemoteError("Local file is too large.")
            return path.read_bytes()
        except OSError as exc:
            raise RemoteError(str(exc)) from exc

    def stream_to_file(self, uri: str, destination: Path, timeout: float = 20.0) -> tuple[int, str]:
        destination.parent.mkdir(parents=True, exist_ok=True)
        parsed = urlparse(str(uri or "").strip())
        if parsed.scheme in ("http", "https"):
            try:
                with urlopen(str(uri), timeout=timeout) as response:
                    expected_length = self._content_length(response)
                    if expected_length is not None and expected_length > self.max_download_bytes:
                        raise RemoteError("Remote file is too large.")
                    written, digest = self._copy_stream_with_hash(response, destination)
                    return written, digest
            except Exception as exc:
                raise RemoteError(str(exc)) from exc

        source_path = self._resolve_local_path(str(uri or ""))
        if not source_path.exists() or not source_path.is_file():
            raise RemoteError(f"Missing file: {source_path}")
        try:
            with source_path.open("rb") as source:
                written, digest = self._copy_stream_with_hash(source, destination)
            return written, digest
        except OSError as exc:
            raise RemoteError(str(exc)) from exc

    def read_json(self, uri: str, timeout: float = 20.0) -> dict[str, Any]:
        raw = self.read_bytes(uri, timeout=timeout)
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RemoteError(f"Invalid JSON from source: {uri}") from exc
        if not isinstance(payload, dict):
            raise RemoteError(f"Expected JSON object from source: {uri}")
        return payload

    def resolve_uri(self, base_uri: str, relative_or_absolute: str) -> str:
        ref = str(relative_or_absolute or "").strip()
        if not ref:
            return str(base_uri or "").strip()
        parsed = urlparse(ref)
        if parsed.scheme:
            if parsed.scheme in ("http", "https"):
                return ref
            if parsed.scheme == "file":
                path = self._resolve_local_path(ref)
                return path.as_uri()
            if self._looks_like_windows_drive_path(ref):
                return str(self._resolve_local_path(ref, allow_missing=True))
            raise RemoteError(f"Unsupported URI scheme: {parsed.scheme}")

        base = str(base_uri or "").strip()
        parsed_base = urlparse(base)
        if parsed_base.scheme in ("http", "https"):
            return urljoin(base, ref)
        if parsed_base.scheme == "file":
            base_path = self._resolve_local_path(base, allow_missing=True)
            if base_path.is_file():
                return self._resolve_local_path(str((base_path.parent / ref).resolve()), allow_missing=True).as_uri()
            return self._resolve_local_path(str((base_path / ref).resolve()), allow_missing=True).as_uri()

        base_path = self._resolve_local_path(base, allow_missing=True)
        if base_path.is_file():
            return str(self._resolve_local_path(str((base_path.parent / ref).resolve()), allow_missing=True))
        return str(self._resolve_local_path(str((base_path / ref).resolve()), allow_missing=True))

    def _resolve_local_path(self, uri_or_path: str, allow_missing: bool = False) -> Path:
        raw = str(uri_or_path or "").strip()
        parsed = urlparse(raw)
        if parsed.scheme == "file":
            if parsed.netloc and parsed.path:
                raw_path = f"//{parsed.netloc}{unquote(parsed.path)}"
            elif parsed.netloc:
                raw_path = unquote(parsed.netloc)
            else:
                raw_path = unquote(parsed.path)
            if os.name == "nt" and len(raw_path) >= 3 and raw_path[0] == "/" and raw_path[2] == ":":
                raw_path = raw_path[1:]
        elif parsed.scheme and not self._looks_like_windows_drive_path(raw):
            raise RemoteError(f"Unsupported URI scheme: {parsed.scheme}")
        else:
            raw_path = raw
        path = Path(raw_path).expanduser().resolve()
        self._ensure_allowed_local_path(path, allow_missing=allow_missing)
        return path

    def _ensure_allowed_local_path(self, path: Path, allow_missing: bool = False) -> None:
        if not self.allowed_local_roots:
            return
        if (not path.exists()) and (not allow_missing):
            return
        path_text = str(path)
        for root in self.allowed_local_roots:
            root_text = str(root)
            try:
                common = os.path.commonpath([path_text, root_text])
            except ValueError:
                continue
            if common == root_text:
                return
        raise RemoteError(f"Blocked local path outside repository root: {path}")

    def _copy_stream_with_hash(self, source, destination: Path) -> tuple[int, str]:
        import hashlib

        digest = hashlib.sha256()
        written = 0
        chunk_size = 64 * 1024
        with destination.open("wb") as target:
            while True:
                chunk = source.read(chunk_size)
                if not chunk:
                    break
                written += len(chunk)
                if written > self.max_download_bytes:
                    raise RemoteError("Download exceeds size limit.")
                digest.update(chunk)
                target.write(chunk)
        return written, digest.hexdigest().lower()

    def _content_length(self, response) -> int | None:
        try:
            header_value = response.headers.get("Content-Length")
            if header_value is None:
                return None
            parsed = int(str(header_value).strip())
            if parsed < 0:
                return None
            return parsed
        except Exception:
            return None

    def _looks_like_windows_drive_path(self, value: str) -> bool:
        text = str(value or "").strip()
        return len(text) >= 3 and text[1] == ":" and text[0].isalpha()
