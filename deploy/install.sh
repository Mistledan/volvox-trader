#!/usr/bin/env bash
# Volvox Trader - one-shot server bootstrap for Ubuntu/Debian (x86_64 or arm64).
# Run as root or with sudo on a fresh host:
#   sudo bash deploy/install.sh
set -euo pipefail

APP_NAME="volvox-trader"
REPO="https://github.com/Mistledan/volvox-trader.git"
INSTALL_DIR="/opt/${APP_NAME}"
RUN_USER="volvox"
MODEL="${OLLAMA_MODEL:-qwen2.5:3b}"
BRANCH="${GIT_BRANCH:-main}"

echo "==> Installing system packages"
apt-get update
apt-get install -y --no-install-recommends curl git python3 python3-venv python3-pip ca-certificates

echo "==> Installing user"
id -u "${RUN_USER}" 2>/dev/null || useradd -r -m -d /home/${RUN_USER} -s /bin/bash ${RUN_USER}

echo "==> Installing Ollama"
curl -fsSL https://ollama.com/install.sh | sh
systemctl enable --now ollama

echo "==> Pulling model ${MODEL}"
for i in 1 2 3 4 5; do
  if ollama pull "${MODEL}"; then break; fi
  echo "retrying ollama pull (${i}/5)..."
  sleep 10
done

echo "==> Cloning ${APP_NAME}"
rm -rf "${INSTALL_DIR}"
git clone --depth 1 --branch "${BRANCH}" "${REPO}" "${INSTALL_DIR}"
chown -R ${RUN_USER}:${RUN_USER} "${INSTALL_DIR}"

echo "==> Creating virtualenv"
# Ubuntu 24.04 ships python3 as 3.12 (22.04 ships 3.10 - the bot requires 3.12).
PYVER=$(python3 -c 'import sys; print("%d.%d" % (sys.version_info[0], sys.version_info[1]))')
echo "Detected python ${PYVER}"
if [[ "${PYVER}" != "3.12" ]]; then
  echo "==> Need Python 3.12; enabling deadsnakes PPA"
  apt-get install -y software-properties-common
  add-apt-repository -y ppa:deadsnakes/ppa
  apt-get update
  apt-get install -y python3.12 python3.12-venv
  PY_BIN=python3.12
else
  PY_BIN=python3
fi
sudo -u ${RUN_USER} bash -c "cd ${INSTALL_DIR} && ${PY_BIN} -m venv .venv"

echo "==> Installing the app"
sudo -u ${RUN_USER} bash -c "cd ${INSTALL_DIR} && ./.venv/bin/pip install --upgrade pip && ./.venv/bin/pip install -e ."

echo "==> Installing services"
cp ${INSTALL_DIR}/deploy/volvox-bot.service ${INSTALL_DIR}/deploy/volvox-dashboard.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now volvox-bot.service volvox-dashboard.service

echo
echo "Done."
echo "Bot       : sudo systemctl status volvox-bot"
echo "Dashboard : sudo systemctl status volvox-dashboard"
echo "Open      : http://<server-ip>:8079"
echo
echo "IMPORTANT: open TCP port 8079 in your cloud firewall/NACL + OS firewall."
echo "For HTTPS/domain, put a reverse proxy (Caddy) in front of port 8079."