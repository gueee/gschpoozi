#!/bin/bash
#
# gschpoozi Configuration Wizard - Bootstrap
# 
# This script checks dependencies and launches the Python wizard.
# https://github.com/gm-tc-collaborators/gschpoozi
#
# Usage: ./configure.sh [--help]
#

set -e

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
WIZARD_DIR="${SCRIPT_DIR}/wizard"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

# ═══════════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

print_header() {
    echo ""
    echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║              gschpoozi Configuration Wizard                ║${NC}"
    echo -e "${GREEN}║                      Version 2.0                           ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
    echo ""
}

print_status() {
    echo -e "${GREEN}[✓]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[!]${NC} $1"
}

print_error() {
    echo -e "${RED}[✗]${NC} $1"
}

# ═══════════════════════════════════════════════════════════════════════════════
# DEPENDENCY CHECKS
# ═══════════════════════════════════════════════════════════════════════════════

check_python() {
    if command -v python3 &> /dev/null; then
        PYTHON_VERSION=$(python3 --version 2>&1 | cut -d' ' -f2)
        print_status "Python 3 found: ${PYTHON_VERSION}"
        return 0
    else
        print_error "Python 3 not found!"
        echo "       Install with: sudo apt-get install python3"
        return 1
    fi
}

check_whiptail() {
    if command -v whiptail &> /dev/null; then
        print_status "whiptail found"
        return 0
    else
        print_warning "whiptail not found - installing..."
        if sudo apt-get update -qq && sudo apt-get install -y -qq whiptail; then
            print_status "whiptail installed successfully"
            return 0
        else
            print_error "Failed to install whiptail"
            echo "       Try manually: sudo apt-get install whiptail"
            return 1
        fi
    fi
}

check_wizard_files() {
    if [[ -f "${WIZARD_DIR}/main.py" ]]; then
        print_status "Wizard files found"
        return 0
    else
        print_error "Wizard files not found at ${WIZARD_DIR}"
        echo "       Make sure you're running from the gschpoozi repository"
        return 1
    fi
}

# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

show_help() {
    echo "gschpoozi Configuration Wizard"
    echo ""
    echo "Usage: $0 [options]"
    echo ""
    echo "Options:"
    echo "  --help, -h     Show this help message"
    echo "  --version, -v  Show version information"
    echo "  --check        Check dependencies only"
    echo "  --dark         Force a dark whiptail theme (sets NEWT_COLORS)"
    echo "  --theme THEME  UI theme: dark|default (default: respects terminal/newt defaults)"
    echo ""
    echo "The wizard will guide you through configuring your Klipper printer."
    echo ""
    echo "For more information: https://github.com/gm-tc-collaborators/gschpoozi"
}

show_version() {
    echo "gschpoozi v2.0.0"
    echo "Klipper Configuration Wizard"
}

check_dependencies() {
    local errors=0
    
    echo "Checking dependencies..."
    echo ""
    
    check_python || ((errors++))
    check_whiptail || ((errors++))
    check_wizard_files || ((errors++))
    
    echo ""
    
    if [[ $errors -gt 0 ]]; then
        print_error "${errors} dependency check(s) failed"
        return 1
    else
        print_status "All dependencies satisfied"
        return 0
    fi
}

main() {
    # Parse arguments
    # - Wrapper-only flags are handled here and NOT passed to the Python wizard.
    # - Unknown flags/args are passed through to the Python wizard.
    local action=""
    local theme="${GSCHPOOZI_THEME:-}"
    local passthrough_args=()

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --help|-h)
                action="help"
                shift
                ;;
            --version|-v)
                action="version"
                shift
                ;;
            --check)
                action="check"
                shift
                ;;
            --dark)
                theme="dark"
                shift
                ;;
            --theme)
                theme="${2:-}"
                shift 2
                ;;
            *)
                passthrough_args+=("$1")
                shift
                ;;
        esac
    done

    case "${action}" in
        help)
            show_help
            exit 0
            ;;
        version)
            show_version
            exit 0
            ;;
        check)
            print_header
            check_dependencies
            exit $?
            ;;
    esac
    
    # Show header
    print_header
    
    # Check dependencies
    if ! check_dependencies; then
        echo ""
        print_error "Please resolve the issues above and try again."
        exit 1
    fi
    
    echo ""
    echo "Starting wizard..."
    echo ""
    
    # Launch Python wizard
    cd "${REPO_ROOT}"

    # Optional: force a dark theme for whiptail/newt UIs (users can also export NEWT_COLORS themselves)
    if [[ -n "${theme}" && "${theme}" != "default" && "${theme}" != "dark" ]]; then
        print_error "Invalid theme: '${theme}' (expected: dark|default)"
        exit 2
    fi
    if [[ "${theme}" == "dark" && -z "${NEWT_COLORS:-}" ]]; then
        export NEWT_COLORS='root=white,black;window=white,black;shadow=black,black;border=white,black;title=white,black;button=black,white;actbutton=white,blue;compactbutton=white,black;checkbox=white,black;actcheckbox=black,white;entry=white,black;label=white,black;listbox=white,black;actsellistbox=black,white;textbox=white,black;acttextbox=black,white;helpline=white,black;roottext=white,black'
    fi

    exec python3 "${WIZARD_DIR}/main.py" "${passthrough_args[@]}"
}

# Run main function
main "$@"
