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
    echo -e "${GREEN}║                      Version 3.0                           ║${NC}"
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

install_pip_package() {
    local package="$1"
    local apt_package="${2:-python3-$package}"

    # Try multiple installation methods in order of preference
    # 1. User-level install (safest, no sudo needed)
    if pip3 install --user "$package" --quiet 2>/dev/null; then
        if python3 -c "import $package" 2>/dev/null; then
            print_status "$package installed successfully (user)"
            return 0
        fi
    fi

    # 2. Try with --break-system-packages (Debian 12+ / Ubuntu 23.04+)
    if pip3 install "$package" --quiet --break-system-packages 2>/dev/null; then
        if python3 -c "import $package" 2>/dev/null; then
            print_status "$package installed successfully"
            return 0
        fi
    fi

    # 3. Try system-wide with sudo (like whiptail install)
    print_warning "Trying system-wide install with sudo..."
    if sudo pip3 install "$package" --quiet --break-system-packages 2>/dev/null || \
       sudo pip3 install "$package" --quiet 2>/dev/null; then
        if python3 -c "import $package" 2>/dev/null; then
            print_status "$package installed successfully (system)"
            return 0
        fi
    fi

    # 4. Last resort: apt package
    print_warning "Trying apt package..."
    if sudo apt-get update -qq && sudo apt-get install -y -qq "$apt_package" 2>/dev/null; then
        if python3 -c "import $package" 2>/dev/null; then
            print_status "$package installed successfully (apt)"
            return 0
        fi
    fi

    return 1
}

check_python_deps() {
    local errors=0

    # Check jinja2
    if ! python3 -c "import jinja2" 2>/dev/null; then
        print_warning "jinja2 not found - installing..."
        if ! install_pip_package "jinja2" "python3-jinja2"; then
            print_error "Failed to install jinja2"
            echo "       Try: pip3 install --user jinja2"
            ((errors++))
        fi
    fi

    # Check yaml (pyyaml)
    if ! python3 -c "import yaml" 2>/dev/null; then
        print_warning "pyyaml not found - installing..."
        if ! install_pip_package "pyyaml" "python3-yaml"; then
            print_error "Failed to install pyyaml"
            echo "       Try: pip3 install --user pyyaml"
            ((errors++))
        fi
    fi

    if [[ $errors -gt 0 ]]; then
        return 1
    fi

    print_status "Python dependencies satisfied"
    return 0
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
    echo "gschpoozi v3.0.0"
    echo "Klipper Configuration Wizard"
}

check_dependencies() {
    local errors=0

    echo "Checking dependencies..."
    echo ""

    check_python || ((errors++))
    check_python_deps || ((errors++))
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
                passthrough_args+=("--dark")  # Pass to Python wizard
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

    # Validate theme if explicitly provided (Python wizard handles the actual theming)
    if [[ -n "${theme}" && "${theme}" != "default" && "${theme}" != "dark" ]]; then
        print_error "Invalid theme: '${theme}' (expected: dark|default)"
        exit 2
    fi

    exec python3 "${WIZARD_DIR}/main.py" "${passthrough_args[@]}"
}

# Run main function
main "$@"
