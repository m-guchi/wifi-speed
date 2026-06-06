from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import List, Optional

from wifi_speed.config import Config
from wifi_speed.runner import run_and_save
from wifi_speed.storage import ResultStore
from wifi_speed.web import run_server


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Raspberry Pi Zero W 用 WiFi 速度監視ツール",
    )
    parser.add_argument(
        "--config",
        type=Path,
        help="設定ファイルのパス（省略時は config.yaml または /etc/wifi-speed/config.yaml）",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("run", help="速度測定を1回実行して保存")

    list_parser = subparsers.add_parser("list", help="直近の測定結果を表示")
    list_parser.add_argument("-n", "--limit", type=int, default=10, help="表示件数")

    summary_parser = subparsers.add_parser("summary", help="集計を表示")
    summary_parser.add_argument(
        "--hours",
        type=int,
        default=24,
        help="集計対象の時間（時間）",
    )

    serve_parser = subparsers.add_parser("serve", help="Web ダッシュボードを起動")
    serve_parser.add_argument("--host", help="バインド先（設定より優先）")
    serve_parser.add_argument("--port", type=int, help="ポート（設定より優先）")

    args = parser.parse_args(argv)
    config = Config.load(args.config)

    if args.command == "run":
        return _cmd_run(config)
    if args.command == "list":
        return _cmd_list(config, args.limit)
    if args.command == "summary":
        return _cmd_summary(config, args.hours)
    if args.command == "serve":
        return _cmd_serve(config, args.host, args.port)

    return 1


def _cmd_run(config: Config) -> int:
    result = run_and_save(config)
    if result.error:
        print(f"測定失敗: {result.error}", file=sys.stderr)
        return 1

    print(
        f"OK  DL: {result.download_mbps:.2f} Mbps  "
        f"UL: {result.upload_mbps:.2f} Mbps  "
        f"Ping: {result.ping_ms:.2f} ms"
    )
    if result.ssid:
        signal = f"{result.signal_dbm} dBm" if result.signal_dbm is not None else "N/A"
        print(f"WiFi: {result.ssid} ({signal})")
    return 0


def _cmd_list(config: Config, limit: int) -> int:
    store = ResultStore(config.database_path)
    results = store.recent(limit)

    if not results:
        print("測定結果がありません。")
        return 0

    for result in results:
        ts = result.measured_at.strftime("%Y-%m-%d %H:%M:%S UTC")
        if result.error:
            print(f"{ts}  ERROR: {result.error}")
            continue

        signal = ""
        if result.ssid:
            dbm = result.signal_dbm if result.signal_dbm is not None else "?"
            signal = f"  [{result.ssid} {dbm}dBm]"

        print(
            f"{ts}  DL {result.download_mbps:7.2f} Mbps  "
            f"UL {result.upload_mbps:7.2f} Mbps  "
            f"Ping {result.ping_ms:6.2f} ms{signal}"
        )
    return 0


def _cmd_summary(config: Config, hours: int) -> int:
    store = ResultStore(config.database_path)
    stats = store.summary(hours)

    print(f"直近 {hours} 時間の集計")
    print(f"  測定回数: {stats['total']}（成功 {stats['success_count']}）")

    if stats["success_count"] == 0:
        print("  成功した測定がありません。")
        return 0

    print(f"  平均 DL: {stats['avg_download']:.2f} Mbps")
    print(f"  平均 UL: {stats['avg_upload']:.2f} Mbps")
    print(f"  平均 Ping: {stats['avg_ping']:.2f} ms")
    print(f"  DL 最小/最大: {stats['min_download']:.2f} / {stats['max_download']:.2f} Mbps")
    return 0


def _cmd_serve(config: Config, host: Optional[str], port: Optional[int]) -> int:
    if host:
        config.web_host = host
    if port:
        config.web_port = port

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    print(f"Web ダッシュボード: http://{config.web_host}:{config.web_port}/")
    print("同一 WiFi 内の端末から http://<ラズパイのIP>:{0}/ でアクセスできます。".format(config.web_port))
    run_server(config)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
