#!/usr/bin/env bash
set -euo pipefail

# Guided Katapult + firmware flashing helper (DFU + CAN).
#
# Goals:
# - Provide a KIAUH-like path to do a *clean* bootloader/firmware workflow.
# - Keep the tool generic across USB-to-CAN adapters (BTT U2C, FLY, etc.) and mainboard CAN bridges.
#
# IMPORTANT:
# - This tool cannot know your MCU model/flash layout. For DFU, it asks you for the exact
#   dfu-util args (and suggests a common default).
# - For CAN flashing, it uses Klipper's flash_can.py (if installed).
#

bold() { printf '\033[1m%s\033[0m\n' "$*"; }
warn() { printf '\033[33m[WARN]\033[0m %s\n' "$*"; }
err()  { printf '\033[31m[ERR]\033[0m %s\n' "$*"; }
ok()   { printf '\033[32m[OK]\033[0m %s\n' "$*"; }

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || { err "Missing command: $1"; return 1; }
}

pause() {
  read -r -p "Press Enter to continue..." _
}

confirm_phrase() {
  local phrase="$1"
  echo
  warn "Type '${phrase}' to continue:"
  read -r resp
  [[ "${resp}" == "${phrase}" ]]
}

install_deps() {
  bold "Installing dependencies (dfu-util, can-utils, python3-serial)..."
  sudo apt-get update -qq
  sudo apt-get install -y -qq dfu-util can-utils python3-serial
  ok "Dependencies installed."
}

dfu_flash() {
  need_cmd dfu-util || return 1

  bold "USB DFU Flash (Katapult bootloader)"
  warn "Put your board into DFU mode now, then we will list DFU devices."
  pause

  echo
  bold "dfu-util -l output:"
  dfu-util -l || true

  echo
  local fw
  read -r -p "Path to Katapult bootloader file (bin/dfu/hex): " fw
  if [[ -z "${fw}" || ! -f "${fw}" ]]; then
    err "File not found: ${fw}"
    return 1
  fi

  echo
  warn "DFU flashing parameters are MCU/bootloader specific."
  warn "If you are not sure, stop and follow Katapult documentation for your board."
  echo

  local default_args
  default_args="-a 0 -s 0x08000000:leave -D \"${fw}\""
  echo "Suggested dfu-util args (common for STM32 internal flash):"
  echo "  ${default_args}"
  echo
  read -r -p "Enter dfu-util args to use (blank = use suggested): " args
  if [[ -z "${args}" ]]; then
    args="${default_args}"
  fi

  echo
  warn "About to run:"
  echo "  dfu-util ${args}"

  if ! confirm_phrase "FLASH_DFU"; then
    warn "Cancelled."
    return 1
  fi

  # shellcheck disable=SC2086
  eval "dfu-util ${args}"
  ok "DFU flash command completed."
}

can_flash() {
  need_cmd ip || return 1

  bold "CAN Flash (Klipper flash_can.py)"

  local klipper_dir="${HOME}/klipper"
  local flash_py="${klipper_dir}/scripts/flash_can.py"
  if [[ ! -f "${flash_py}" ]]; then
    err "Klipper flash tool not found at: ${flash_py}"
    err "Install Klipper first (Klipper Setup -> Manage Components -> install klipper)."
    return 1
  fi

  local iface
  read -r -p "CAN interface (default: can0): " iface
  iface="${iface:-can0}"

  if ! ip link show "${iface}" >/dev/null 2>&1; then
    err "Interface '${iface}' does not exist. Run CAN Interface Setup first."
    return 1
  fi

  echo
  bold "Tip: discover UUIDs with:"
  echo "  ~/klippy-env/bin/python3 ~/klipper/scripts/canbus_query.py ${iface}"
  echo
  read -r -p "Target canbus UUID: " uuid
  if [[ -z "${uuid}" ]]; then
    err "Missing UUID."
    return 1
  fi

  read -r -p "Path to firmware file (.bin): " fw
  if [[ -z "${fw}" || ! -f "${fw}" ]]; then
    err "File not found: ${fw}"
    return 1
  fi

  echo
  bold "flash_can.py help (for reference):"
  python3 "${flash_py}" -h || true
  echo

  # Attempt a common invocation. If it fails, user can re-run with custom args.
  local cmd
  cmd="python3 \"${flash_py}\" -i \"${iface}\" -u \"${uuid}\" -f \"${fw}\""
  warn "About to run:"
  echo "  ${cmd}"

  if ! confirm_phrase "FLASH_CAN"; then
    warn "Cancelled."
    return 1
  fi

  eval "${cmd}"
  ok "CAN flash command completed."
}

main_menu() {
  while true; do
    echo
    bold "Katapult / Flashing Helper"
    echo "  1) Install dependencies"
    echo "  2) Flash Katapult via USB DFU (advanced)"
    echo "  3) Flash firmware via CAN (flash_can.py)"
    echo "  4) Exit"
    echo
    read -r -p "Select option: " choice
    case "${choice}" in
      1) install_deps ;;
      2) dfu_flash ;;
      3) can_flash ;;
      4) return 0 ;;
      *) echo "Invalid option." ;;
    esac
  done
}

main_menu


