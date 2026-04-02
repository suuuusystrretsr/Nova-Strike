from dataclasses import dataclass
from pathlib import Path


DEFAULT_ROOT = Path(r"C:\UpdateStudios")


@dataclass(frozen=True)
class AppPaths:
    root: Path
    data_dir: Path
    games_dir: Path
    installed_games_dir: Path
    state_dir: Path
    security_dir: Path
    temp_dir: Path
    backups_dir: Path
    studio_drop_dir: Path
    incoming_drop_dir: Path
    processed_drop_dir: Path
    rejected_drop_dir: Path
    repository_dir: Path
    logs_dir: Path

    @classmethod
    def create(cls, root: Path | str | None = None) -> "AppPaths":
        base_root = Path(root) if root is not None else DEFAULT_ROOT
        base = base_root.resolve()
        data_dir = base / "data"
        games_dir = data_dir / "games"
        installed_games_dir = games_dir / "installed"
        state_dir = data_dir / "state"
        security_dir = data_dir / "security"
        temp_dir = data_dir / "temp"
        backups_dir = data_dir / "backups"
        studio_drop_dir = base / "studio_drop"
        incoming_drop_dir = studio_drop_dir / "incoming"
        processed_drop_dir = studio_drop_dir / "processed"
        rejected_drop_dir = studio_drop_dir / "rejected"
        repository_dir = base / "repository"
        logs_dir = base / "logs"
        return cls(
            root=base,
            data_dir=data_dir,
            games_dir=games_dir,
            installed_games_dir=installed_games_dir,
            state_dir=state_dir,
            security_dir=security_dir,
            temp_dir=temp_dir,
            backups_dir=backups_dir,
            studio_drop_dir=studio_drop_dir,
            incoming_drop_dir=incoming_drop_dir,
            processed_drop_dir=processed_drop_dir,
            rejected_drop_dir=rejected_drop_dir,
            repository_dir=repository_dir,
            logs_dir=logs_dir,
        )

    def ensure(self) -> None:
        for folder in (
            self.root,
            self.data_dir,
            self.games_dir,
            self.installed_games_dir,
            self.state_dir,
            self.security_dir,
            self.temp_dir,
            self.backups_dir,
            self.studio_drop_dir,
            self.incoming_drop_dir,
            self.processed_drop_dir,
            self.rejected_drop_dir,
            self.repository_dir,
            self.logs_dir,
        ):
            folder.mkdir(parents=True, exist_ok=True)
