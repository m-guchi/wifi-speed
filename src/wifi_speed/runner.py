from __future__ import annotations

import json
import subprocess
import time
from datetime import datetime, timezone

from wifi_speed.config import Config
from wifi_speed.storage import ResultStore, SpeedResult
from wifi_speed.wifi_signal import WifiSignal, collect_wifi_signal


def run_speedtest(config: Config) -> SpeedResult:
    """1回の速度測定を実行し、結果を返す。"""
    measured_at = datetime.now(timezone.utc)
    wifi = collect_wifi_signal() if config.collect_wifi_signal else WifiSignal(None, None, None, None)

    last_error: str | None = None
    for attempt in range(config.retry_count + 1):
        try:
            raw = _execute_speedtest(config)
            parsed = _parse_speedtest_output(raw)
            return SpeedResult(
                measured_at=measured_at,
                download_mbps=parsed["download_mbps"],
                upload_mbps=parsed["upload_mbps"],
                ping_ms=parsed["ping_ms"],
                server_name=parsed.get("server_name"),
                server_id=parsed.get("server_id"),
                ssid=wifi.ssid,
                signal_dbm=wifi.signal_dbm,
                link_quality=wifi.link_quality,
            )
        except SpeedtestError as exc:
            last_error = str(exc)
            if attempt < config.retry_count:
                time.sleep(config.retry_delay_seconds)

    return SpeedResult(
        measured_at=measured_at,
        download_mbps=0.0,
        upload_mbps=0.0,
        ping_ms=0.0,
        server_name=None,
        server_id=None,
        ssid=wifi.ssid,
        signal_dbm=wifi.signal_dbm,
        link_quality=wifi.link_quality,
        error=last_error,
    )


def run_and_save(config: Config) -> SpeedResult:
    """測定して DB に保存する。"""
    result = run_speedtest(config)
    store = ResultStore(config.database_path)
    store.save(result)
    return result


class SpeedtestError(Exception):
    pass


def _execute_speedtest(config: Config) -> str:
    command = [config.speedtest_command, *config.speedtest_args]
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )
    except FileNotFoundError as exc:
        raise SpeedtestError(
            f"speedtest コマンドが見つかりません: {config.speedtest_command}"
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise SpeedtestError("speedtest がタイムアウトしました（300秒）") from exc

    output = (completed.stdout or "") + (completed.stderr or "")
    if completed.returncode != 0:
        raise SpeedtestError(output.strip() or f"speedtest が終了コード {completed.returncode} で失敗")

    return output.strip()


def _parse_speedtest_output(raw: str) -> dict[str, float | str | None]:
    """speedtest-cli --json または Ookla speedtest --format=json を解析する。"""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SpeedtestError("speedtest の JSON 出力を解析できませんでした") from exc

    # speedtest-cli (sivel) 形式
    if "download" in data and isinstance(data["download"], (int, float)):
        return {
            "download_mbps": round(data["download"] / 1_000_000, 2),
            "upload_mbps": round(data["upload"] / 1_000_000, 2),
            "ping_ms": round(float(data.get("ping", 0)), 2),
            "server_name": data.get("server", {}).get("name"),
            "server_id": str(data.get("server", {}).get("id", "")),
        }

    # Ookla speedtest CLI 形式
    if "download" in data and isinstance(data["download"], dict):
        download = data["download"].get("bandwidth", 0) * 8 / 1_000_000
        upload = data["upload"].get("bandwidth", 0) * 8 / 1_000_000
        ping = data.get("ping", {}).get("latency", 0)
        server = data.get("server", {})
        return {
            "download_mbps": round(download, 2),
            "upload_mbps": round(upload, 2),
            "ping_ms": round(float(ping), 2),
            "server_name": server.get("name"),
            "server_id": str(server.get("id", "")),
        }

    raise SpeedtestError("未対応の speedtest JSON 形式です")
