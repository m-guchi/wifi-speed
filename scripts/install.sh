#!/usr/bin/env bash
set -euo pipefail

INSTALL_DIR="/opt/wifi-speed"
CONFIG_DIR="/etc/wifi-speed"
DATA_DIR="/var/lib/wifi-speed"
SERVICE_USER="${SUDO_USER:-pi}"

if [[ "${EUID}" -ne 0 ]]; then
  echo "root 権限で実行してください: sudo ./scripts/install.sh"
  exit 1
fi

echo "==> 依存パッケージのインストール"
apt-get update
apt-get install -y python3 python3-venv python3-pip speedtest-cli wireless-tools

echo "==> アプリの配置: ${INSTALL_DIR}"
mkdir -p "${INSTALL_DIR}"
rsync -a --exclude '.venv' --exclude '__pycache__' ./ "${INSTALL_DIR}/"

echo "==> Python 仮想環境の作成"
python3 -m venv "${INSTALL_DIR}/.venv"
"${INSTALL_DIR}/.venv/bin/pip" install --upgrade pip
"${INSTALL_DIR}/.venv/bin/pip" install -e "${INSTALL_DIR}"

echo "==> 設定・データディレクトリ"
mkdir -p "${CONFIG_DIR}" "${DATA_DIR}"
chown -R "${SERVICE_USER}:${SERVICE_USER}" "${DATA_DIR}"

if [[ ! -f "${CONFIG_DIR}/config.yaml" ]]; then
  cp "${INSTALL_DIR}/config.example.yaml" "${CONFIG_DIR}/config.yaml"
  sed -i "s|/var/lib/wifi-speed/results.db|${DATA_DIR}/results.db|" "${CONFIG_DIR}/config.yaml"
fi

echo "==> systemd ユニットの登録"
cp "${INSTALL_DIR}/systemd/wifi-speed.service" /etc/systemd/system/
cp "${INSTALL_DIR}/systemd/wifi-speed.timer" /etc/systemd/system/
cp "${INSTALL_DIR}/systemd/wifi-speed-web.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now wifi-speed.timer
systemctl enable --now wifi-speed-web.service

PI_IP="$(hostname -I | awk '{print $1}')"
WEB_PORT="$(grep -E '^web_port:' "${CONFIG_DIR}/config.yaml" | awk '{print $2}' || echo 8080)"

echo ""
echo "インストール完了"
echo "  ダッシュボード: http://${PI_IP}:${WEB_PORT}/"
echo "  手動測定: sudo -u ${SERVICE_USER} ${INSTALL_DIR}/.venv/bin/wifi-speed --config ${CONFIG_DIR}/config.yaml run"
echo "  結果一覧: sudo -u ${SERVICE_USER} ${INSTALL_DIR}/.venv/bin/wifi-speed --config ${CONFIG_DIR}/config.yaml list"
echo "  タイマー確認: systemctl status wifi-speed.timer"
echo "  Web 確認: systemctl status wifi-speed-web.service"
