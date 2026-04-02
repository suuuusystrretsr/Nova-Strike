from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class LaunchConfig:
    executable: str
    args: list[str] = field(default_factory=list)
    cwd: str = ""
    env: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LaunchConfig":
        return cls(
            executable=str(data.get("executable", "")).strip(),
            args=[str(item) for item in data.get("args", []) if str(item).strip()],
            cwd=str(data.get("cwd", "")).strip(),
            env={str(k): str(v) for k, v in dict(data.get("env", {})).items()},
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "executable": self.executable,
            "args": list(self.args),
            "cwd": self.cwd,
            "env": dict(self.env),
        }


@dataclass
class GameConfig:
    game_id: str
    display_name: str
    install_dir: str
    local_version: str
    update_source: str
    launch: LaunchConfig
    channel: str = "stable"
    description: str = ""
    icon: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GameConfig":
        launch = LaunchConfig.from_dict(dict(data.get("launch", {})))
        return cls(
            game_id=str(data.get("game_id", "")).strip(),
            display_name=str(data.get("display_name", "")).strip() or str(data.get("name", "")).strip(),
            install_dir=str(data.get("install_dir", "")).strip(),
            local_version=str(data.get("local_version", "")).strip() or "0.0.0",
            update_source=str(data.get("update_source", "")).strip(),
            launch=launch,
            channel=str(data.get("channel", "stable")).strip() or "stable",
            description=str(data.get("description", "")).strip(),
            icon=str(data.get("icon", "")).strip(),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "game_id": self.game_id,
            "display_name": self.display_name,
            "install_dir": self.install_dir,
            "local_version": self.local_version,
            "update_source": self.update_source,
            "channel": self.channel,
            "description": self.description,
            "icon": self.icon,
            "launch": self.launch.to_dict(),
        }

    def install_path(self) -> Path:
        return Path(self.install_dir).expanduser().resolve()


@dataclass
class UpdateFile:
    path: str
    sha256: str
    url: str
    size: int = 0

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "UpdateFile":
        return cls(
            path=str(data.get("path", "")).replace("\\", "/").lstrip("/"),
            sha256=str(data.get("sha256", "")).strip().lower(),
            url=str(data.get("url", "")).strip(),
            size=max(0, int(data.get("size", 0) or 0)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {"path": self.path, "sha256": self.sha256, "url": self.url, "size": int(self.size)}


@dataclass
class UpdateManifest:
    game_id: str
    version: str
    files: list[UpdateFile] = field(default_factory=list)
    remove: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "UpdateManifest":
        raw_files = data.get("files", [])
        files = [UpdateFile.from_dict(dict(item)) for item in raw_files if isinstance(item, dict)]
        remove = [str(item).replace("\\", "/").lstrip("/") for item in data.get("remove", []) if str(item).strip()]
        return cls(
            game_id=str(data.get("game_id", "")).strip(),
            version=str(data.get("version", "")).strip(),
            files=files,
            remove=remove,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "game_id": self.game_id,
            "version": self.version,
            "files": [entry.to_dict() for entry in self.files],
            "remove": list(self.remove),
        }


@dataclass
class ChannelInfo:
    game_id: str
    latest_version: str
    manifest: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ChannelInfo":
        return cls(
            game_id=str(data.get("game_id", "")).strip(),
            latest_version=str(data.get("latest_version", "")).strip(),
            manifest=str(data.get("manifest", "")).strip(),
        )
