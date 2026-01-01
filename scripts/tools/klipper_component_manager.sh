#!/usr/bin/env bash
set -euo pipefail

# KIAUH-like component manager wrapper.
#
# This script exists so the Python wizard can safely invoke the existing
# installation/update/remove functions in scripts/lib/klipper-install.sh.
#
# Usage:
#   ./scripts/tools/klipper_component_manager.sh install klipper
#   ./scripts/tools/klipper_component_manager.sh update moonraker
#   ./scripts/tools/klipper_component_manager.sh remove mainsail
#   ./scripts/tools/klipper_component_manager.sh reinstall fluidd
#   ./scripts/tools/klipper_component_manager.sh update-all

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

action="${1:-}"
component="${2:-}"

if [[ -z "${action}" ]]; then
  echo "Usage: $0 <install|update|remove|reinstall|update-all> [component]" >&2
  exit 2
fi

# ------------------------------------------------------------------------------
# Minimal UI helpers
#
# scripts/lib/klipper-install.sh expects a handful of UI helper functions and
# color/box constants (ported from earlier bash wizard versions). When invoked
# from the Python wizard we want these routines to run in a plain TTY.
# ------------------------------------------------------------------------------

# Colors (ANSI)
RED="${RED:-$'\033[0;31m'}"
GREEN="${GREEN:-$'\033[0;32m'}"
YELLOW="${YELLOW:-$'\033[0;33m'}"
BLUE="${BLUE:-$'\033[0;34m'}"
MAGENTA="${MAGENTA:-$'\033[0;35m'}"
CYAN="${CYAN:-$'\033[0;36m'}"
WHITE="${WHITE:-$'\033[0;37m'}"

BRED="${BRED:-$'\033[1;31m'}"
BGREEN="${BGREEN:-$'\033[1;32m'}"
BYELLOW="${BYELLOW:-$'\033[1;33m'}"
BBLUE="${BBLUE:-$'\033[1;34m'}"
BMAGENTA="${BMAGENTA:-$'\033[1;35m'}"
BCYAN="${BCYAN:-$'\033[1;36m'}"
BWHITE="${BWHITE:-$'\033[1;37m'}"

NC="${NC:-$'\033[0m'}"

# Box drawing
BOX_TL="${BOX_TL:-"╔"}"
BOX_TR="${BOX_TR:-"╗"}"
BOX_BL="${BOX_BL:-"╚"}"
BOX_BR="${BOX_BR:-"╝"}"
BOX_H="${BOX_H:-"═"}"
BOX_V="${BOX_V:-"║"}"
BOX_LT="${BOX_LT:-"╠"}"
BOX_RT="${BOX_RT:-"╣"}"

clear_screen() {
  # Best-effort clear that works in most TTY contexts
  command -v clear >/dev/null 2>&1 && clear || printf '\033c'
}

print_header() {
  local title="${1:-}"
  local width="${2:-60}"
  local line
  line="$(printf '%*s' "${width}" '' | tr ' ' "${BOX_H}")"
  local padding
  padding=$(( (width - ${#title} - 2) / 2 ))
  if [[ "${padding}" -lt 0 ]]; then padding=0; fi
  printf "%b\n" "${BCYAN}${BOX_TL}${line}${BOX_TR}${NC}"
  printf "%b\n" "${BCYAN}${BOX_V}${NC}$(printf '%*s' "${padding}" "")${BWHITE} ${title} ${NC}$(printf '%*s' "$((width - padding - ${#title} - 2))" "")${BCYAN}${BOX_V}${NC}"
  printf "%b\n" "${BCYAN}${BOX_LT}${line}${BOX_RT}${NC}"
}

print_footer() {
  local width="${1:-60}"
  local line
  line="$(printf '%*s' "${width}" '' | tr ' ' "${BOX_H}")"
  printf "%b\n" "${BCYAN}${BOX_BL}${line}${BOX_BR}${NC}"
}

print_separator() {
  local width="${1:-60}"
  printf "%b\n" "${BCYAN}${BOX_LT}$(printf '%*s' "${width}" "" | tr ' ' "${BOX_H}")${BOX_RT}${NC}"
}

print_action_item() {
  local key="${1:-}"
  local label="${2:-}"
  printf "%b\n" "${BCYAN}${BOX_V}${NC}  ${BGREEN}${key})${NC} ${label}"
}

wait_for_key() {
  printf "%b" "${WHITE}Press Enter to continue...${NC}"
  read -r _ || true
}

confirm() {
  # Two modes:
  # - Default: y/N prompt
  # - If prompt contains "Type 'yes'", require literal 'yes' (safety double-confirm)
  local prompt="${1:-Are you sure?}"
  local answer

  if [[ "${prompt}" == *"Type 'yes'"* ]]; then
    printf "%b" "${BYELLOW}${prompt}${NC}: "
    read -r answer || answer=""
    [[ "${answer}" == "yes" ]]
    return $?
  fi

  printf "%b" "${BYELLOW}${prompt}${NC} [y/N]: "
  read -r answer || answer=""
  case "${answer,,}" in
    y|yes) return 0 ;;
    *) return 1 ;;
  esac
}

# Read Klipper variant from state file
# State file is at ~/printer_data/config/.gschpoozi_state.json
STATE_FILE="${HOME}/printer_data/config/.gschpoozi_state.json"
KLIPPER_VARIANT="standard"  # Default

if [[ -f "${STATE_FILE}" ]]; then
  # Use Python to safely parse JSON (more reliable than jq which may not be installed)
  VARIANT=$(python3 -c "
import json
import sys
try:
    with open('${STATE_FILE}', 'r') as f:
        data = json.load(f)
        variant = data.get('config', {}).get('klipper', {}).get('variant', 'standard')
        print(variant)
except Exception:
    print('standard')
" 2>/dev/null || echo "standard")

  if [[ -n "${VARIANT}" ]]; then
    KLIPPER_VARIANT="${VARIANT}"
  fi
fi

# Export variant for use by klipper-install.sh
export KLIPPER_VARIANT

# Source installer library (expects INSTALL_LIB_DIR to point at scripts/lib)
export INSTALL_LIB_DIR="${REPO_ROOT}/scripts/lib"
# shellcheck source=/dev/null
source "${REPO_ROOT}/scripts/lib/klipper-install.sh"

case "${action}" in
  install)
    case "${component}" in
      host-mcu)     do_install_host_mcu ;;
      klipper)      do_install_klipper ;;
      moonraker)    do_install_moonraker ;;
      mainsail)     do_install_mainsail ;;
      fluidd)       do_install_fluidd ;;
      crowsnest)    do_install_crowsnest ;;
      sonar)        do_install_sonar ;;
      timelapse)    do_install_timelapse ;;
      beacon)       do_install_beacon ;;
      cartographer) do_install_cartographer ;;
      *) echo "Unknown component for install: ${component}" >&2; exit 2 ;;
    esac
    ;;
  update)
    case "${component}" in
      klipper)      do_update_klipper ;;
      moonraker)    do_update_moonraker ;;
      mainsail)     do_update_mainsail ;;
      fluidd)       do_update_fluidd ;;
      crowsnest)    do_update_crowsnest ;;
      sonar)        do_update_sonar ;;
      timelapse)    do_update_timelapse ;;
      beacon)       do_update_beacon ;;
      cartographer) do_update_cartographer ;;
      *) echo "Unknown component for update: ${component}" >&2; exit 2 ;;
    esac
    ;;
  remove)
    case "${component}" in
      klipper)      do_remove_klipper ;;
      moonraker)    do_remove_moonraker ;;
      mainsail)     do_remove_mainsail ;;
      fluidd)       do_remove_fluidd ;;
      crowsnest)    do_remove_crowsnest ;;
      sonar)        do_remove_sonar ;;
      timelapse)    do_remove_timelapse ;;
      beacon)       do_remove_beacon ;;
      cartographer) do_remove_cartographer ;;
      *) echo "Unknown component for remove: ${component}" >&2; exit 2 ;;
    esac
    ;;
  reinstall)
    # Full uninstall + re-install. This mirrors KIAUH's "clean reinstall" behavior.
    case "${component}" in
      klipper)      do_remove_klipper;       do_install_klipper ;;
      moonraker)    do_remove_moonraker;     do_install_moonraker ;;
      mainsail)     do_remove_mainsail;      do_install_mainsail ;;
      fluidd)       do_remove_fluidd;        do_install_fluidd ;;
      crowsnest)    do_remove_crowsnest;     do_install_crowsnest ;;
      sonar)        do_remove_sonar;         do_install_sonar ;;
      timelapse)    do_remove_timelapse;     do_install_timelapse ;;
      beacon)       do_remove_beacon;        do_install_beacon ;;
      cartographer) do_remove_cartographer;  do_install_cartographer ;;
      *) echo "Unknown component for reinstall: ${component}" >&2; exit 2 ;;
    esac
    ;;
  update-all)
    do_update_all
    ;;
  *)
    echo "Unknown action: ${action}" >&2
    exit 2
    ;;
esac


