from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import yaml

DEFAULT_CONFIG_PATHS = (
    Path("/etc/wifi-speed/config.yaml"),
    Path("config.yaml"),
)


@dataclass
class Config:
    interval_minutes: int = 30
    database_path: Path = Path("/var/lib/wifi-speed/results.db")
    speedtest_command: str = "speedtest-cli"
    speedtest_args: list[str] = field(default_factory=lambda: ["--json"])
    collect_wifi_signal: bool = True
    retry_count: int = 2
    retry_delay_seconds: int = 60
    web_host: str = "0.0.0.0"
    web_port: int = 8080
    config_path: Optional[Path] = field(default=None, repr=False)

    @classmethod
    def load(cls, path: Optional[Path] = None) -> Config:
        config_path = path or _find_config_path()
        if config_path is None:
            return cls()

        with config_path.open(encoding="utf-8") as f:
            data: dict[str, Any] = yaml.safe_load(f) or {}

        return cls(
            interval_minutes=int(data.get("interval_minutes", 30)),
            database_path=Path(data.get("database_path", "/var/lib/wifi-speed/results.db")),
            speedtest_command=str(data.get("speedtest_command", "speedtest-cli")),
            speedtest_args=list(data.get("speedtest_args", ["--json"])),
            collect_wifi_signal=bool(data.get("collect_wifi_signal", True)),
            retry_count=int(data.get("retry_count", 2)),
            retry_delay_seconds=int(data.get("retry_delay_seconds", 60)),
            web_host=str(data.get("web_host", "0.0.0.0")),
            web_port=int(data.get("web_port", 8080)),
            config_path=config_path,
        )


def _find_config_path() -> Optional[Path]:
    for candidate in DEFAULT_CONFIG_PATHS:
        if candidate.exists():
            return candidate
    return None
