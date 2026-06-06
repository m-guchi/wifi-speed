from __future__ import annotations

import subprocess
from pathlib import Path

APPLY_SETTINGS_SCRIPT = Path("/opt/wifi-speed/scripts/apply-settings.sh")
INTERVAL_MIN = 5
INTERVAL_MAX = 1440


def settings_payload(interval_minutes: int) -> dict[str, int]:
    return {
        "interval_minutes": interval_minutes,
        "interval_minutes_min": INTERVAL_MIN,
        "interval_minutes_max": INTERVAL_MAX,
    }


def apply_interval_minutes(minutes: int) -> tuple[bool, str]:
    if minutes < INTERVAL_MIN or minutes > INTERVAL_MAX:
        return False, f"測定間隔は {INTERVAL_MIN}〜{INTERVAL_MAX} 分で指定してください"

    if not APPLY_SETTINGS_SCRIPT.is_file():
        return False, "設定反映スクリプトが見つかりません（install.sh を再実行してください）"

    try:
        completed = subprocess.run(
            ["sudo", str(APPLY_SETTINGS_SCRIPT), str(minutes)],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return False, str(exc)

    message = (completed.stdout or completed.stderr or "").strip()
    if completed.returncode != 0:
        if not message:
            message = f"設定の反映に失敗しました（終了コード {completed.returncode}）"
        return False, message

    return True, message or f"測定間隔を {minutes} 分に更新しました"
