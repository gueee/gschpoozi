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

# Source installer library (expects INSTALL_LIB_DIR to point at scripts/lib)
export INSTALL_LIB_DIR="${REPO_ROOT}/scripts/lib"
# shellcheck source=/dev/null
source "${REPO_ROOT}/scripts/lib/klipper-install.sh"

case "${action}" in
  install)
    case "${component}" in
      klipper)    do_install_klipper ;;
      moonraker)  do_install_moonraker ;;
      mainsail)   do_install_mainsail ;;
      fluidd)     do_install_fluidd ;;
      crowsnest)  do_install_crowsnest ;;
      sonar)      do_install_sonar ;;
      timelapse)  do_install_timelapse ;;
      *) echo "Unknown component for install: ${component}" >&2; exit 2 ;;
    esac
    ;;
  update)
    case "${component}" in
      klipper)    do_update_klipper ;;
      moonraker)  do_update_moonraker ;;
      mainsail)   do_update_mainsail ;;
      fluidd)     do_update_fluidd ;;
      crowsnest)  do_update_crowsnest ;;
      sonar)      do_update_sonar ;;
      timelapse)  do_update_timelapse ;;
      *) echo "Unknown component for update: ${component}" >&2; exit 2 ;;
    esac
    ;;
  remove)
    case "${component}" in
      klipper)    do_remove_klipper ;;
      moonraker)  do_remove_moonraker ;;
      mainsail)   do_remove_mainsail ;;
      fluidd)     do_remove_fluidd ;;
      crowsnest)  do_remove_crowsnest ;;
      sonar)      do_remove_sonar ;;
      timelapse)  do_remove_timelapse ;;
      *) echo "Unknown component for remove: ${component}" >&2; exit 2 ;;
    esac
    ;;
  reinstall)
    # Full uninstall + re-install. This mirrors KIAUH's "clean reinstall" behavior.
    case "${component}" in
      klipper)    do_remove_klipper;   do_install_klipper ;;
      moonraker)  do_remove_moonraker; do_install_moonraker ;;
      mainsail)   do_remove_mainsail;  do_install_mainsail ;;
      fluidd)     do_remove_fluidd;    do_install_fluidd ;;
      crowsnest)  do_remove_crowsnest; do_install_crowsnest ;;
      sonar)      do_remove_sonar;     do_install_sonar ;;
      timelapse)  do_remove_timelapse; do_install_timelapse ;;
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


