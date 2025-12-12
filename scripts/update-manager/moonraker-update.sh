#!/bin/bash
#
# Moonraker Update Script - Entry point for Moonraker Update Manager
# This script is called by Moonraker when updates are detected.
#
# https://github.com/gm-tc-collaborators/gschpoozi
#

set -eo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

LOG_FILE="${HOME}/printer_data/logs/gschpoozi-update.log"
INSTALL_SCRIPT="${SCRIPT_DIR}/install-config.sh"

# Create log directory
mkdir -p "$(dirname "${LOG_FILE}")" 2>/dev/null || true

# Log function
log() {
    echo "[moonraker-update] $*"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [moonraker-update] $*" >> "${LOG_FILE}"
}

# Start logging
log "=== Moonraker Update Triggered ==="
log "User: ${USER:-unknown}"
log "PWD: ${PWD:-unknown}"

# Check if we're in the repo directory
if [[ ! -d "${REPO_ROOT}/.git" ]]; then
    log "ERROR: Not in git repository at ${REPO_ROOT}"
    exit 1
fi

# Get current git status
cd "${REPO_ROOT}" || exit 1
log "Git branch: $(git branch --show-current 2>/dev/null || echo 'unknown')"
log "Git commit: $(git rev-parse --short HEAD 2>/dev/null || echo 'unknown')"

# Check if install script exists
if [[ ! -f "${INSTALL_SCRIPT}" ]]; then
    log "ERROR: Install script not found at ${INSTALL_SCRIPT}"
    exit 1
fi

# Run the install script
log "Executing install script..."
export MOONRAKER_UPDATE=1

if "${INSTALL_SCRIPT}" 2>&1 | tee -a "${LOG_FILE}"; then
    log "Install script completed successfully"
else
    log "WARNING: Install script returned non-zero exit code"
fi

log "=== Moonraker Update Completed ==="

# Always exit 0 for Moonraker (don't block updates on errors)
exit 0

