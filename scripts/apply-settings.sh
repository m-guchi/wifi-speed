#!/usr/bin/env bash
set -euo pipefail

INSTALL_DIR="/opt/wifi-speed"
CONFIG_PATH="/etc/wifi-speed/config.yaml"
TIMER_PATH="/etc/systemd/system/wifi-speed.timer"
TIMER_TEMPLATE="${INSTALL_DIR}/systemd/wifi-speed.timer"

if [[ "${EUID}" -ne 0 ]]; then
  echo "root 権限が必要です" >&2
  exit 1
fi

INTERVAL="${1:-}"
if ! [[ "${INTERVAL}" =~ ^[0-9]+$ ]] || [[ "${INTERVAL}" -lt 5 ]] || [[ "${INTERVAL}" -gt 1440 ]]; then
  echo "測定間隔は 5〜1440 分で指定してください" >&2
  exit 1
fi

if [[ ! -f "${CONFIG_PATH}" ]]; then
  echo "設定ファイルが見つかりません: ${CONFIG_PATH}" >&2
  exit 1
fi

if [[ ! -f "${TIMER_TEMPLATE}" ]]; then
  echo "タイマーテンプレートが見つかりません: ${TIMER_TEMPLATE}" >&2
  exit 1
fi

if grep -qE '^interval_minutes:' "${CONFIG_PATH}"; then
  sed -i "s/^interval_minutes:.*/interval_minutes: ${INTERVAL}/" "${CONFIG_PATH}"
else
  printf '\ninterval_minutes: %s\n' "${INTERVAL}" >> "${CONFIG_PATH}"
fi

sed -e "s/^OnUnitActiveSec=.*/OnUnitActiveSec=${INTERVAL}min/" \
  "${TIMER_TEMPLATE}" > "${TIMER_PATH}"

systemctl daemon-reload
systemctl restart wifi-speed.timer

echo "測定間隔を ${INTERVAL} 分に更新しました"
