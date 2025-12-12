#!/bin/bash
#
# gschpoozi Configuration Installer
# Deploys generated configuration from the repository to ~/printer_data/config/gschpoozi/
#
# Usage:
#   ./install-config.sh                    # Normal install
#   ./install-config.sh --backup-only      # Only create backup
#
# https://github.com/gm-tc-collaborators/gschpoozi
#

set -eo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

# Paths
TARGET_CONFIG="${HOME}/printer_data/config"
TARGET_GSCHPOOZI="${TARGET_CONFIG}/gschpoozi"
BACKUP_DIR="${HOME}/printer_data/config-backups"
LOG_FILE="${HOME}/printer_data/logs/gschpoozi-install.log"

# Logging
LOG_PREFIX="[gschpoozi-install]"

log() {
    echo "${LOG_PREFIX} $*"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ${LOG_PREFIX} $*" >> "${LOG_FILE}" 2>/dev/null || true
}

fail() {
    echo "${LOG_PREFIX} ERROR: $*" >&2
    exit 1
}

ensure_prereqs() {
    command -v rsync >/dev/null 2>&1 || fail "rsync is required but not installed."
}

create_backup() {
    if [[ -d "${TARGET_GSCHPOOZI}" ]]; then
        mkdir -p "${BACKUP_DIR}"
        local ts
        ts="$(date +%Y%m%d-%H%M%S)"
        local backup_path="${BACKUP_DIR}/gschpoozi-${ts}.tar.gz"
        log "Creating backup at ${backup_path}"
        tar -czf "${backup_path}" -C "${TARGET_CONFIG}" gschpoozi 2>/dev/null || true
        
        # Keep only last 5 backups
        local backup_count
        backup_count=$(ls -1 "${BACKUP_DIR}"/gschpoozi-*.tar.gz 2>/dev/null | wc -l)
        if [[ ${backup_count} -gt 5 ]]; then
            log "Cleaning old backups (keeping last 5)"
            ls -1t "${BACKUP_DIR}"/gschpoozi-*.tar.gz | tail -n +6 | xargs rm -f 2>/dev/null || true
        fi
    fi
}

deploy_config() {
    # Only deploy if gschpoozi folder exists in target (meaning wizard was run)
    if [[ ! -d "${TARGET_GSCHPOOZI}" ]]; then
        log "No existing gschpoozi config found at ${TARGET_GSCHPOOZI}"
        log "Run the configuration wizard first: ~/gschpoozi/scripts/configure.sh"
        return 0
    fi
    
    log "Syncing gschpoozi configuration..."
    
    # Sync only the gschpoozi subfolder contents
    # We don't overwrite - only update existing files and add new ones
    # User's printer.cfg is NEVER touched
    
    # If we have generated templates that should be updated, sync them
    # For now, we just preserve the existing config
    log "Configuration preserved (user-generated files are not overwritten)"
    log "Re-run the wizard to regenerate: ~/gschpoozi/scripts/configure.sh"
}

make_scripts_executable() {
    chmod +x "${REPO_ROOT}/scripts"/*.sh 2>/dev/null || true
    chmod +x "${REPO_ROOT}/scripts/update-manager"/*.sh 2>/dev/null || true
    log "Made scripts executable"
}

verify_deployment() {
    log "=== Verifying deployment ==="
    
    if [[ -d "${TARGET_GSCHPOOZI}" ]]; then
        log "✓ gschpoozi folder exists"
        
        local file_count
        file_count=$(find "${TARGET_GSCHPOOZI}" -name "*.cfg" 2>/dev/null | wc -l)
        log "  Found ${file_count} config file(s)"
    else
        log "! gschpoozi folder not found - run wizard to generate"
    fi
    
    if [[ -f "${TARGET_CONFIG}/printer.cfg" ]]; then
        if grep -q "include gschpoozi/" "${TARGET_CONFIG}/printer.cfg" 2>/dev/null; then
            log "✓ printer.cfg includes gschpoozi"
        else
            log "! printer.cfg does not include gschpoozi - add [include gschpoozi/...] lines"
        fi
    fi
}

main() {
    # Create log directory
    mkdir -p "$(dirname "${LOG_FILE}")" 2>/dev/null || true
    
    log "=== gschpoozi Install Script Started ==="
    log "Invoked by: ${USER:-unknown}"
    log "Repository: ${REPO_ROOT}"
    log "Target: ${TARGET_GSCHPOOZI}"
    log "Environment: MOONRAKER_UPDATE=${MOONRAKER_UPDATE:-not_set}"
    
    # Parse arguments
    local backup_only=false
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --backup-only)
                backup_only=true
                ;;
            -h|--help)
                cat << 'EOF'
Usage: install-config.sh [OPTIONS]

Options:
  --backup-only    Only create backup, don't deploy
  -h, --help       Show this help

This script is typically called by Moonraker Update Manager.
For initial setup, run the wizard: ~/gschpoozi/scripts/configure.sh
EOF
                exit 0
                ;;
            *)
                log "Unknown argument: $1"
                ;;
        esac
        shift
    done
    
    # Ensure prerequisites
    ensure_prereqs
    
    # Create backup
    create_backup || { log "WARNING: Backup creation failed, continuing..."; true; }
    
    if ${backup_only}; then
        log "Backup-only mode, skipping deployment"
        exit 0
    fi
    
    # Make scripts executable
    make_scripts_executable
    
    # Deploy configuration (preserves user files)
    deploy_config
    
    # Verify
    verify_deployment
    
    log "=== Install script completed at $(date) ==="
}

# Execute main function when run directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi

