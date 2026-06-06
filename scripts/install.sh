#!/usr/bin/env bash
set -euo pipefail

INSTALL_DIR="/opt/wifi-speed"
CONFIG_DIR="/etc/wifi-speed"
DATA_DIR="/var/lib/wifi-speed"
SERVICE_USER="${SUDO_USER:-pi}"
APT_PACKAGES=(python3 python3-venv python3-pip speedtest-cli wireless-tools)

QUICK=0
FULL=0

usage() {
  cat <<'EOF'
usage: sudo ./scripts/install.sh [OPTIONS]

  初回インストール、または git pull 後の更新に使います。

OPTIONS:
  --quick, -q   apt / venv 再作成をスキップ（コード更新のみ）
  --full, -f    apt update、venv 再作成、pip 更新を含む完全インストール
  --help, -h    このヘルプを表示

既に /opt/wifi-speed/.venv がある場合は --full を付けない限り自動で --quick 相当になります。
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --quick|-q)
      QUICK=1
      ;;
    --full|-f)
      FULL=1
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "不明なオプション: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
  shift
done

if [[ "${EUID}" -ne 0 ]]; then
  echo "root 権限で実行してください: sudo ./scripts/install.sh"
  exit 1
fi

if [[ "${FULL}" -eq 0 && "${QUICK}" -eq 0 && -d "${INSTALL_DIR}/.venv" ]]; then
  QUICK=1
fi

if [[ "${FULL}" -eq 1 ]]; then
  echo "==> モード: 完全インストール (--full)"
elif [[ "${QUICK}" -eq 1 ]]; then
  echo "==> モード: クイック更新（apt / venv 再作成をスキップ）"
else
  echo "==> モード: 初回インストール"
fi

install_apt_packages() {
  echo "==> 依存パッケージのインストール"
  apt-get update
  apt-get install -y "${APT_PACKAGES[@]}"
}

ensure_apt_packages() {
  local missing=()
  local pkg
  for pkg in "${APT_PACKAGES[@]}"; do
    if ! dpkg-query -W -f='${Status}' "${pkg}" 2>/dev/null | grep -q "install ok installed"; then
      missing+=("${pkg}")
    fi
  done

  if [[ "${#missing[@]}" -eq 0 ]]; then
    echo "==> 依存パッケージ: インストール済み（スキップ）"
    return
  fi

  echo "==> 不足パッケージをインストール: ${missing[*]}"
  apt-get install -y "${missing[@]}"
}

setup_venv() {
  echo "==> Python 仮想環境の作成"
  python3 -m venv "${INSTALL_DIR}/.venv"
  "${INSTALL_DIR}/.venv/bin/pip" install --upgrade pip
  "${INSTALL_DIR}/.venv/bin/pip" install -e "${INSTALL_DIR}"
}

update_venv() {
  echo "==> Python パッケージの更新"
  if [[ ! -x "${INSTALL_DIR}/.venv/bin/pip" ]]; then
    setup_venv
    return
  fi
  "${INSTALL_DIR}/.venv/bin/pip" install -e "${INSTALL_DIR}"
}

if [[ "${QUICK}" -eq 1 ]]; then
  ensure_apt_packages
elif [[ "${FULL}" -eq 1 ]]; then
  install_apt_packages
  rm -rf "${INSTALL_DIR}/.venv"
else
  install_apt_packages
fi

echo "==> アプリの配置: ${INSTALL_DIR}"
mkdir -p "${INSTALL_DIR}"
rsync -a --exclude '.venv' --exclude '__pycache__' ./ "${INSTALL_DIR}/"

if [[ "${QUICK}" -eq 1 ]]; then
  update_venv
else
  setup_venv
fi

echo "==> 設定・データディレクトリ"
mkdir -p "${CONFIG_DIR}" "${DATA_DIR}"
chown -R "${SERVICE_USER}:${SERVICE_USER}" "${DATA_DIR}"

if [[ ! -f "${CONFIG_DIR}/config.yaml" ]]; then
  cp "${INSTALL_DIR}/config.example.yaml" "${CONFIG_DIR}/config.yaml"
  sed -i "s|/var/lib/wifi-speed/results.db|${DATA_DIR}/results.db|" "${CONFIG_DIR}/config.yaml"
fi

echo "==> コマンドの登録"
ln -sf "${INSTALL_DIR}/.venv/bin/wifi-speed" /usr/local/bin/wifi-speed

echo "==> systemd ユニットの登録"
if ! id "${SERVICE_USER}" &>/dev/null; then
  echo "エラー: サービスユーザー '${SERVICE_USER}' が存在しません。" >&2
  echo "sudo -u <ユーザー名> ./scripts/install.sh で実行するか、SUDO_USER を設定してください。" >&2
  exit 1
fi
SERVICE_GROUP="$(id -gn "${SERVICE_USER}")"

for unit in wifi-speed.service wifi-speed-web.service; do
  sed \
    -e "s/^User=.*/User=${SERVICE_USER}/" \
    -e "s/^Group=.*/Group=${SERVICE_GROUP}/" \
    "${INSTALL_DIR}/systemd/${unit}" > "/etc/systemd/system/${unit}"
done

INTERVAL_MINUTES="$(grep -E '^interval_minutes:' "${CONFIG_DIR}/config.yaml" | awk '{print $2}' || echo 30)"
sed -e "s/^OnUnitActiveSec=.*/OnUnitActiveSec=${INTERVAL_MINUTES}min/" \
  "${INSTALL_DIR}/systemd/wifi-speed.timer" > /etc/systemd/system/wifi-speed.timer

chmod 755 "${INSTALL_DIR}/scripts/apply-settings.sh"
cat > /etc/sudoers.d/wifi-speed <<EOF
${SERVICE_USER} ALL=(root) NOPASSWD: ${INSTALL_DIR}/scripts/apply-settings.sh
EOF
chmod 440 /etc/sudoers.d/wifi-speed
visudo -cf /etc/sudoers.d/wifi-speed >/dev/null
systemctl daemon-reload
systemctl enable wifi-speed.timer
systemctl enable wifi-speed-web.service
systemctl restart wifi-speed-web.service

if [[ "${QUICK}" -eq 1 ]]; then
  systemctl restart wifi-speed.timer
else
  systemctl enable --now wifi-speed.timer
  systemctl enable --now wifi-speed-web.service
fi

PI_IP="$(hostname -I | awk '{print $1}')"
WEB_PORT="$(grep -E '^web_port:' "${CONFIG_DIR}/config.yaml" | awk '{print $2}' || echo 8080)"

echo ""
echo "インストール完了"
echo "  ダッシュボード: http://${PI_IP}:${WEB_PORT}/"
echo "  手動測定: sudo -u ${SERVICE_USER} ${INSTALL_DIR}/.venv/bin/wifi-speed --config ${CONFIG_DIR}/config.yaml run"
echo "  結果一覧: sudo -u ${SERVICE_USER} ${INSTALL_DIR}/.venv/bin/wifi-speed --config ${CONFIG_DIR}/config.yaml list"
echo "  タイマー確認: systemctl status wifi-speed.timer"
echo "  Web 確認: systemctl status wifi-speed-web.service"
if [[ "${QUICK}" -eq 1 ]]; then
  echo "  次回も git pull 後は: sudo ./scripts/install.sh  （自動クイック更新）"
fi
