#!/usr/bin/env bash
set -euo pipefail

# Minimal CAN interface setup helper.
#
# What this does:
# - Installs can-utils (optional)
# - Brings up an existing CAN interface (default: can0) at a given bitrate
# - Optionally creates a persistent systemd service to bring it up on boot
#
# What this does NOT do:
# - Hardware enablement (mcp2515 overlays), USB serial CAN (slcan), or udev naming rules
#
# Usage:
#   ./scripts/tools/setup_can_interface.sh --iface can0 --bitrate 1000000 --persist yes

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

iface="can0"
bitrate="1000000"
persist="yes"
install_pkgs="yes"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --iface) iface="${2:-}"; shift 2 ;;
    --bitrate) bitrate="${2:-}"; shift 2 ;;
    --persist) persist="${2:-}"; shift 2 ;;
    --install-pkgs) install_pkgs="${2:-}"; shift 2 ;;
    -h|--help)
      cat <<EOF
Usage: $0 [--iface can0] [--bitrate 1000000] [--persist yes|no] [--install-pkgs yes|no]
EOF
      exit 0
      ;;
    *)
      echo "Unknown arg: $1" >&2
      exit 2
      ;;
  esac
done

if [[ -z "${iface}" ]]; then
  echo "Missing --iface" >&2
  exit 2
fi
if [[ -z "${bitrate}" ]]; then
  echo "Missing --bitrate" >&2
  exit 2
fi

if [[ "${install_pkgs}" == "yes" ]]; then
  sudo apt-get update -qq
  sudo apt-get install -y -qq can-utils
fi

if ! command -v ip >/dev/null 2>&1; then
  echo "ip(8) not found (iproute2). Install iproute2." >&2
  exit 1
fi

if ! ip link show "${iface}" >/dev/null 2>&1; then
  cat >&2 <<EOF
CAN interface '${iface}' does not exist.

This script only configures an *existing* CAN interface.
You likely still need to enable your CAN hardware/driver (examples):
- USB CAN adapters: ensure kernel driver creates can0 (e.g. gs_usb)
- SPI CAN (mcp2515): enable device-tree overlay and reboot

Then re-run this setup.
EOF
  exit 2
fi

ip_bin="$(command -v ip)"

sudo "${ip_bin}" link set "${iface}" down >/dev/null 2>&1 || true
sudo "${ip_bin}" link set "${iface}" up type can bitrate "${bitrate}"

echo "CAN interface '${iface}' is up at bitrate ${bitrate}."

if [[ "${persist}" == "yes" ]]; then
  svc="can-${iface}.service"
  svc_path="/etc/systemd/system/${svc}"

  tmp="$(mktemp)"
  cat > "${tmp}" <<EOF
[Unit]
Description=Setup CAN interface ${iface}
After=network.target
Wants=network.target

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=${ip_bin} link set ${iface} down
ExecStart=${ip_bin} link set ${iface} up type can bitrate ${bitrate}
ExecStop=${ip_bin} link set ${iface} down

[Install]
WantedBy=multi-user.target
EOF

  sudo mv "${tmp}" "${svc_path}"
  sudo chmod 0644 "${svc_path}"
  sudo systemctl daemon-reload
  sudo systemctl enable --now "${svc}"
  echo "Installed and enabled ${svc}."
fi


