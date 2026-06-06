# wifi-speed

insight-myroom で使用している Raspberry Pi Zero W 向けの、自宅 WiFi 回線速度を定期監視するツールです。

Pi Zero W のリソース制約を考慮し、軽量な `speedtest-cli` と SQLite による履歴保存に絞った構成にしています。

## 機能

- 定期的なインターネット速度測定（ダウンロード / アップロード / Ping）
- WiFi 信号強度（dBm）と SSID の記録
- SQLite への履歴保存
- CLI での結果確認・集計
- **Web ダッシュボード**（`http://<ラズパイのIP>:8080/` で閲覧）
- systemd timer による自動実行（デフォルト 30 分間隔）

## 前提

- Raspberry Pi Zero W（Raspberry Pi OS）
- WiFi 接続済み（`wlan0`）
- `speedtest-cli`（Ookla 公式 CLI でも可）

## インストール（Pi 上）

```bash
git clone <このリポジトリ> wifi-speed
cd wifi-speed
chmod +x scripts/install.sh
sudo ./scripts/install.sh
```

インストール後、30 分ごとに自動測定が始まります。初回は起動 5 分後です。

同一 WiFi 内のスマホや PC から、ラズパイの IP アドレスでダッシュボードを開けます。

```
http://192.168.x.x:8080/
```

IP の確認（Pi 上）:

```bash
hostname -I
```

## 手動操作

```bash
# 1 回測定
wifi-speed --config /etc/wifi-speed/config.yaml run

# 直近 10 件を表示
wifi-speed --config /etc/wifi-speed/config.yaml list

# 直近 24 時間の集計
wifi-speed --config /etc/wifi-speed/config.yaml summary

# Web ダッシュボードを手動起動（開発用）
wifi-speed --config /etc/wifi-speed/config.yaml serve
```

開発環境では仮想環境を有効化してから実行してください。

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
cp config.example.yaml config.yaml
wifi-speed run
```

## 設定

`/etc/wifi-speed/config.yaml`（またはプロジェクト直下の `config.yaml`）で変更できます。

| 項目 | デフォルト | 説明 |
|------|-----------|------|
| `interval_minutes` | 30 | 測定間隔の目安（timer と合わせて調整） |
| `database_path` | `/var/lib/wifi-speed/results.db` | 結果 DB |
| `speedtest_command` | `speedtest-cli` | 測定コマンド |
| `collect_wifi_signal` | `true` | WiFi 信号強度の記録 |
| `retry_count` | 2 | 失敗時リトライ回数 |
| `web_host` | `0.0.0.0` | Web サーバーのバインド先 |
| `web_port` | `8080` | Web サーバーのポート |

測定間隔を変える場合は `config.yaml` に加え、`systemd/wifi-speed.timer` の `OnUnitActiveSec` も合わせて変更し、`sudo systemctl daemon-reload && sudo systemctl restart wifi-speed.timer` を実行してください。

## Web ダッシュボード

ブラウザから以下が確認できます。

- 最新の測定値（DL / UL / Ping）
- 直近 24 時間のグラフ
- 集計（平均・最小・最大）
- 測定履歴テーブル

60 秒ごとに自動更新されます。追加の Python パッケージは不要です（標準ライブラリのみで動作）。

本ツールは insight-myroom とは独立して動作します。同一 Pi で併用する場合は、測定間隔を 30〜60 分程度に設定することを推奨します。

### セキュリティについて

認証機能はありません。自宅 LAN 内での利用を想定しています。インターネットから直接アクセスできないよう、ルーターの設定に注意してください。

## データベース

`speed_results` テーブルに以下を保存します。

- 測定日時（UTC）
- ダウンロード / アップロード速度（Mbps）
- Ping（ms）
- 接続先 speedtest サーバー
- SSID、信号強度（dBm）
- エラー内容（失敗時）

## トラブルシューティング

```bash
# タイマーの状態
systemctl status wifi-speed.timer
systemctl list-timers wifi-speed.timer

# Web サーバーの状態
systemctl status wifi-speed-web.service
journalctl -u wifi-speed-web.service -n 50

# 手動でサービス実行
sudo systemctl start wifi-speed.service
journalctl -u wifi-speed.service -n 50

# speedtest 単体確認
speedtest-cli --json
iwconfig wlan0
```

測定に 1〜3 分かかることがあります。Pi Zero W ではこれが正常です。

## ライセンス

MIT（必要に応じて変更してください）
