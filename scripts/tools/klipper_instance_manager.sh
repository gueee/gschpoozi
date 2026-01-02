#!/usr/bin/env bash
set -euo pipefail

# gschpoozi Multi-Instance Manager
#
# Manages multiple parallel Klipper+Moonraker instances with distinct:
# - printer_data directories
# - systemd service names (klipper-<id>, moonraker-<id>)
# - Moonraker ports
# - nginx web UI sites + ports
#
# Usage:
#   ./klipper_instance_manager.sh create <instance_id> <moonraker_port> <webui> <webui_port>
#   ./klipper_instance_manager.sh list
#   ./klipper_instance_manager.sh start <instance_id>
#   ./klipper_instance_manager.sh stop <instance_id>
#   ./klipper_instance_manager.sh restart <instance_id>
#   ./klipper_instance_manager.sh remove <instance_id>

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
INSTALL_LIB_DIR="${REPO_ROOT}/scripts/lib"

# ------------------------------------------------------------------------------
# UI helpers (copied from component manager for standalone usage)
# ------------------------------------------------------------------------------

# Colors (ANSI)
RED="${RED:-$'\033[0;31m'}"
GREEN="${GREEN:-$'\033[0;32m'}"
YELLOW="${YELLOW:-$'\033[0;33m'}"
BLUE="${BLUE:-$'\033[0;34m'}"
CYAN="${CYAN:-$'\033[0;36m'}"
WHITE="${WHITE:-$'\033[0;37m'}"

BRED="${BRED:-$'\033[1;31m'}"
BGREEN="${BGREEN:-$'\033[1;32m'}"
BYELLOW="${BYELLOW:-$'\033[1;33m'}"
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

clear_screen() {
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
  printf "%b\n" "${BCYAN}${BOX_V}$(printf '%*s' "${width}" '')${BOX_V}${NC}"
}

print_footer() {
  local width="${1:-60}"
  local line
  line="$(printf '%*s' "${width}" '' | tr ' ' "${BOX_H}")"
  printf "%b\n" "${BCYAN}${BOX_BL}${line}${BOX_BR}${NC}"
}

wait_for_key() {
  printf "%b" "${WHITE}Press Enter to continue...${NC}"
  read -r _ || true
}

confirm() {
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
  case "${answer}" in
    [yY]|[yY][eE][sS]) return 0 ;;
    *) return 1 ;;
  esac
}

status_msg() {
    echo -e "${CYAN}###### $1${NC}"
}

ok_msg() {
    echo -e "${GREEN}[OK] $1${NC}"
}

error_msg() {
    echo -e "${RED}[ERROR] $1${NC}"
}

warn_msg() {
    echo -e "${YELLOW}[WARN] $1${NC}"
}

# Source the klipper-install library for helper functions
# shellcheck disable=SC1091
source "${INSTALL_LIB_DIR}/klipper-install.sh"

ACTION="${1:-}"
INSTANCE_ID="${2:-}"

# ═══════════════════════════════════════════════════════════════════════════════
# INSTANCE HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

validate_instance_id() {
    local id="$1"
    # Must be alphanumeric + dash/underscore only (safe for filenames + systemd units)
    if [[ ! "$id" =~ ^[a-zA-Z0-9_-]+$ ]]; then
        error_msg "Invalid instance ID: must be alphanumeric with dashes/underscores only"
        return 1
    fi
    return 0
}

get_instance_printer_data() {
    local id="$1"
    if [[ "$id" == "default" ]]; then
        echo "${HOME}/printer_data"
    else
        echo "${HOME}/printer_data-${id}"
    fi
}

get_instance_klipper_service() {
    local id="$1"
    if [[ "$id" == "default" ]]; then
        echo "klipper"
    else
        echo "klipper-${id}"
    fi
}

get_instance_moonraker_service() {
    local id="$1"
    if [[ "$id" == "default" ]]; then
        echo "moonraker"
    else
        echo "moonraker-${id}"
    fi
}

# ═══════════════════════════════════════════════════════════════════════════════
# ACTIONS
# ═══════════════════════════════════════════════════════════════════════════════

do_create_instance() {
    local instance_id="$1"
    local moonraker_port="$2"
    local webui_kind="$3"      # "mainsail" or "fluidd"
    local webui_port="$4"
    local skip_confirm="${5:-}"  # "yes" to skip confirmation (for wizard automation)

    if [[ -z "$instance_id" ]] || [[ -z "$moonraker_port" ]] || [[ -z "$webui_kind" ]] || [[ -z "$webui_port" ]]; then
        error_msg "Usage: $0 create <instance_id> <moonraker_port> <webui> <webui_port> [yes]"
        error_msg "Example: $0 create vzbot1 7125 mainsail 80"
        error_msg "         $0 create vzbot1 7125 mainsail 80 yes  # skip confirmation"
        return 1
    fi

    validate_instance_id "$instance_id" || return 1

    local printer_data_path
    printer_data_path="$(get_instance_printer_data "$instance_id")"
    local klipper_service
    klipper_service="$(get_instance_klipper_service "$instance_id")"
    local moonraker_service
    moonraker_service="$(get_instance_moonraker_service "$instance_id")"

    clear_screen
    print_header "Creating Klipper Instance: ${instance_id}"
    echo ""
    echo "  printer_data:     ${printer_data_path}"
    echo "  klipper service:  ${klipper_service}"
    echo "  moonraker service: ${moonraker_service}"
    echo "  moonraker port:   ${moonraker_port}"
    echo "  web UI:           ${webui_kind} on port ${webui_port}"
    echo ""
    print_footer
    echo ""

    if [[ "$skip_confirm" != "yes" ]]; then
        if ! confirm "Create this instance?"; then
            return 1
        fi
    fi

    echo ""

    # Preflight checks
    check_not_root || return 1
    check_sudo_access || return 1

    # Ensure Klipper is installed (shared by all instances)
    if ! is_klipper_installed; then
        warn_msg "Klipper not installed - installing shared Klipper first..."
        echo ""
        echo "Multi-instance setup requires a shared Klipper installation."
        echo "Installing Klipper to ~/klipper/ (used by all instances)..."
        echo ""
        if ! confirm "Install Klipper now?"; then
            error_msg "Klipper installation required. Exiting."
            return 1
        fi
        do_install_klipper || {
            error_msg "Klipper installation failed"
            return 1
        }
        echo ""
    fi

    # Ensure Moonraker is installed (shared by all instances)
    if ! is_moonraker_installed; then
        warn_msg "Moonraker not installed - installing shared Moonraker first..."
        echo ""
        echo "Multi-instance setup requires a shared Moonraker installation."
        echo "Installing Moonraker to ~/moonraker/ (used by all instances)..."
        echo ""
        if ! confirm "Install Moonraker now?"; then
            error_msg "Moonraker installation required. Exiting."
            return 1
        fi
        do_install_moonraker || {
            error_msg "Moonraker installation failed"
            return 1
        }
        echo ""
    fi

    # Ensure web UI is installed (shared by all instances)
    if [[ "$webui_kind" == "mainsail" ]] && ! is_mainsail_installed; then
        warn_msg "Mainsail not installed - installing shared Mainsail first..."
        echo ""
        if ! confirm "Install Mainsail now?"; then
            error_msg "Mainsail installation required. Exiting."
            return 1
        fi
        do_install_mainsail || {
            error_msg "Mainsail installation failed"
            return 1
        }
        echo ""
    fi
    if [[ "$webui_kind" == "fluidd" ]] && ! is_fluidd_installed; then
        warn_msg "Fluidd not installed - installing shared Fluidd first..."
        echo ""
        if ! confirm "Install Fluidd now?"; then
            error_msg "Fluidd installation required. Exiting."
            return 1
        fi
        do_install_fluidd || {
            error_msg "Fluidd installation failed"
            return 1
        }
        echo ""
    fi

    # 1. Create printer_data directory structure
    create_printer_data_dirs_for_instance "$printer_data_path" || return 1

    # 2. Create instance-specific moonraker.conf
    create_moonraker_conf_for_instance "$printer_data_path" "$moonraker_port" || return 1

    # 3. Create basic printer.cfg (so Klipper can start)
    create_basic_printer_cfg_for_instance "$printer_data_path" || return 1

    # 4. Create Klipper service
    local klipper_template="${SERVICE_TEMPLATES}/klipper.service"
    export PRINTER_DATA="$printer_data_path"
    create_systemd_service_for_instance "$klipper_service" "$klipper_template" "$printer_data_path" || return 1

    # 5. Create Moonraker service
    local moonraker_template="${SERVICE_TEMPLATES}/moonraker.service"
    create_systemd_service_for_instance "$moonraker_service" "$moonraker_template" "$printer_data_path" || return 1

    # 6. Enable services
    enable_service "${klipper_service}" || true
    enable_service "${moonraker_service}" || return 1

    # 7. Setup nginx for web UI
    local site_name="${webui_kind}-${instance_id}"
    if [[ "$instance_id" == "default" ]]; then
        site_name="$webui_kind"
    fi
    export MOONRAKER_PORT="$moonraker_port"
    setup_nginx_for_instance "$webui_kind" "$site_name" "$webui_port" "$moonraker_port" || return 1

    echo ""
    ok_msg "Instance '${instance_id}' created successfully!"
    echo ""
    echo "  Services:  ${klipper_service}.service, ${moonraker_service}.service"
    echo "  Web UI:    http://localhost:${webui_port}"
    echo "  Config:    ${printer_data_path}/config/"
    echo ""
    echo "Run the wizard with:  ./scripts/configure.sh --instance ${instance_id}"
    echo ""
    wait_for_key
    return 0
}

do_list_instances() {
    clear_screen
    print_header "Klipper Instances"
    echo ""

    # Find all printer_data-* directories
    local instances=()

    # Default instance
    if [[ -d "${HOME}/printer_data" ]]; then
        instances+=("default")
    fi

    # Additional instances
    for dir in "${HOME}"/printer_data-*; do
        if [[ -d "$dir" ]]; then
            local id
            id="$(basename "$dir" | sed 's/^printer_data-//')"
            instances+=("$id")
        fi
    done

    if [[ ${#instances[@]} -eq 0 ]]; then
        warn_msg "No instances found"
        echo ""
        echo "  Create an instance with:"
        echo "    $0 create <instance_id> <moonraker_port> <webui> <webui_port>"
        echo ""
        wait_for_key
        return 0
    fi

    printf "%-15s %-20s %-20s %-10s %-10s\n" "INSTANCE" "KLIPPER SERVICE" "MOONRAKER SERVICE" "WEBUI" "PORT"
    printf "%s\n" "────────────────────────────────────────────────────────────────────────────"

    for id in "${instances[@]}"; do
        local printer_data
        printer_data="$(get_instance_printer_data "$id")"
        local k_svc
        k_svc="$(get_instance_klipper_service "$id")"
        local m_svc
        m_svc="$(get_instance_moonraker_service "$id")"

        # Detect web UI and port from nginx
        local webui="none"
        local webui_port="-"

        if [[ "$id" == "default" ]]; then
            for ui in mainsail fluidd; do
                if [[ -f "/etc/nginx/sites-enabled/${ui}" ]]; then
                    webui="$ui"
                    webui_port=$(grep -oP 'listen \K[0-9]+' "/etc/nginx/sites-available/${ui}" 2>/dev/null | head -1 || echo "-")
                    break
                fi
            done
        else
            for ui in mainsail fluidd; do
                local site="${ui}-${id}"
                if [[ -f "/etc/nginx/sites-enabled/${site}" ]]; then
                    webui="$ui"
                    webui_port=$(grep -oP 'listen \K[0-9]+' "/etc/nginx/sites-available/${site}" 2>/dev/null | head -1 || echo "-")
                    break
                fi
            done
        fi

        # Service status
        local k_status="-"
        local m_status="-"
        if systemctl is-active --quiet "${k_svc}" 2>/dev/null; then
            k_status="running"
        elif systemctl is-enabled --quiet "${k_svc}" 2>/dev/null; then
            k_status="stopped"
        fi
        if systemctl is-active --quiet "${m_svc}" 2>/dev/null; then
            m_status="running"
        elif systemctl is-enabled --quiet "${m_svc}" 2>/dev/null; then
            m_status="stopped"
        fi

        printf "%-15s %-20s %-20s %-10s %-10s\n" \
            "$id" \
            "${k_svc} (${k_status})" \
            "${m_svc} (${m_status})" \
            "$webui" \
            "$webui_port"
    done

    echo ""
    wait_for_key
    return 0
}

do_start_instance() {
    local instance_id="$1"

    if [[ -z "$instance_id" ]]; then
        error_msg "Usage: $0 start <instance_id>"
        return 1
    fi

    validate_instance_id "$instance_id" || return 1

    local k_svc
    k_svc="$(get_instance_klipper_service "$instance_id")"
    local m_svc
    m_svc="$(get_instance_moonraker_service "$instance_id")"

    status_msg "Starting instance '${instance_id}'..."
    sudo systemctl start "${k_svc}" || warn_msg "${k_svc} start failed"
    sudo systemctl start "${m_svc}" || warn_msg "${m_svc} start failed"

    sleep 2

    if systemctl is-active --quiet "${k_svc}" && systemctl is-active --quiet "${m_svc}"; then
        ok_msg "Instance '${instance_id}' started successfully"
        return 0
    else
        error_msg "Instance '${instance_id}' failed to start - check service status"
        return 1
    fi
}

do_stop_instance() {
    local instance_id="$1"

    if [[ -z "$instance_id" ]]; then
        error_msg "Usage: $0 stop <instance_id>"
        return 1
    fi

    validate_instance_id "$instance_id" || return 1

    local k_svc
    k_svc="$(get_instance_klipper_service "$instance_id")"
    local m_svc
    m_svc="$(get_instance_moonraker_service "$instance_id")"

    status_msg "Stopping instance '${instance_id}'..."
    sudo systemctl stop "${k_svc}" || true
    sudo systemctl stop "${m_svc}" || true

    ok_msg "Instance '${instance_id}' stopped"
    return 0
}

do_restart_instance() {
    local instance_id="$1"

    if [[ -z "$instance_id" ]]; then
        error_msg "Usage: $0 restart <instance_id>"
        return 1
    fi

    validate_instance_id "$instance_id" || return 1

    local k_svc
    k_svc="$(get_instance_klipper_service "$instance_id")"
    local m_svc
    m_svc="$(get_instance_moonraker_service "$instance_id")"

    status_msg "Restarting instance '${instance_id}'..."
    sudo systemctl restart "${k_svc}" || warn_msg "${k_svc} restart failed"
    sudo systemctl restart "${m_svc}" || warn_msg "${m_svc} restart failed"

    sleep 2

    if systemctl is-active --quiet "${k_svc}" && systemctl is-active --quiet "${m_svc}"; then
        ok_msg "Instance '${instance_id}' restarted successfully"
        return 0
    else
        error_msg "Instance '${instance_id}' failed to restart - check service status"
        return 1
    fi
}

do_remove_instance() {
    local instance_id="$1"

    if [[ -z "$instance_id" ]]; then
        error_msg "Usage: $0 remove <instance_id>"
        return 1
    fi

    # Allow removing default instance, but validate non-default IDs
    if [[ "$instance_id" != "default" ]]; then
        validate_instance_id "$instance_id" || return 1
    fi

    local printer_data
    printer_data="$(get_instance_printer_data "$instance_id")"
    local k_svc
    k_svc="$(get_instance_klipper_service "$instance_id")"
    local m_svc
    m_svc="$(get_instance_moonraker_service "$instance_id")"

    clear_screen
    print_header "Remove Instance: ${instance_id}"
    echo ""
    echo "  This will:"
    echo "  - Stop and disable services: ${k_svc}, ${m_svc}"
    echo "  - Remove systemd unit files"
    echo "  - Remove nginx sites"
    echo "  - OPTIONALLY delete: ${printer_data}"
    echo ""
    print_footer
    echo ""

    if ! confirm "Remove instance '${instance_id}'? (Type 'yes' to confirm)"; then
        return 1
    fi

    echo ""

    # 1. Stop and disable services
    status_msg "Stopping services..."
    sudo systemctl stop "${k_svc}" 2>/dev/null || true
    sudo systemctl stop "${m_svc}" 2>/dev/null || true
    sudo systemctl disable "${k_svc}" 2>/dev/null || true
    sudo systemctl disable "${m_svc}" 2>/dev/null || true

    # 2. Remove systemd unit files
    status_msg "Removing systemd units..."
    sudo rm -f "${SYSTEMD_DIR}/${k_svc}.service"
    sudo rm -f "${SYSTEMD_DIR}/${m_svc}.service"
    sudo systemctl daemon-reload

    # 3. Remove nginx sites
    status_msg "Removing nginx sites..."
    for ui in mainsail fluidd; do
        local site="${ui}-${instance_id}"
        sudo rm -f "/etc/nginx/sites-enabled/${site}" 2>/dev/null || true
        sudo rm -f "/etc/nginx/sites-available/${site}" 2>/dev/null || true
    done

    # Test and reload nginx
    if sudo nginx -t 2>/dev/null; then
        sudo systemctl reload nginx 2>/dev/null || true
    fi

    # 4. Optionally delete printer_data directory
    if [[ -d "$printer_data" ]]; then
        echo ""
        if confirm "Delete printer_data directory at ${printer_data}? (configs + logs + gcodes)"; then
            status_msg "Deleting ${printer_data}..."
            rm -rf "$printer_data"
            ok_msg "Deleted ${printer_data}"
        else
            warn_msg "Kept ${printer_data} (manual cleanup required)"
        fi
    fi

    echo ""
    ok_msg "Instance '${instance_id}' removed"
    echo ""
    wait_for_key
    return 0
}

# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

case "$ACTION" in
    create)
        MOONRAKER_PORT="${3:-}"
        WEBUI_KIND="${4:-}"
        WEBUI_PORT="${5:-}"
        SKIP_CONFIRM="${6:-}"
        do_create_instance "$INSTANCE_ID" "$MOONRAKER_PORT" "$WEBUI_KIND" "$WEBUI_PORT" "$SKIP_CONFIRM"
        ;;
    list)
        do_list_instances
        ;;
    start)
        do_start_instance "$INSTANCE_ID"
        ;;
    stop)
        do_stop_instance "$INSTANCE_ID"
        ;;
    restart)
        do_restart_instance "$INSTANCE_ID"
        ;;
    remove)
        do_remove_instance "$INSTANCE_ID"
        ;;
    *)
        echo "gschpoozi Multi-Instance Manager" >&2
        echo "" >&2
        echo "Usage:" >&2
        echo "  $0 create <instance_id> <moonraker_port> <webui> <webui_port>" >&2
        echo "  $0 list" >&2
        echo "  $0 start <instance_id>" >&2
        echo "  $0 stop <instance_id>" >&2
        echo "  $0 restart <instance_id>" >&2
        echo "  $0 remove <instance_id>" >&2
        echo "" >&2
        echo "Examples:" >&2
        echo "  $0 create vzbot1 7125 mainsail 80" >&2
        echo "  $0 create vzbot2 7126 mainsail 81" >&2
        echo "  $0 list" >&2
        echo "  $0 start vzbot1" >&2
        echo "  $0 stop vzbot2" >&2
        echo "  $0 restart vzbot1" >&2
        echo "  $0 remove vzbot2" >&2
        echo "" >&2
        exit 1
        ;;
esac
