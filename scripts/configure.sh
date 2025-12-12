#!/bin/bash
#
# gschpoozi Configuration Wizard
# A KIAUH-style text menu for generating Klipper configurations
#
# Usage: ./configure.sh
#
# https://github.com/gueee/gschpoozi
#

set -e

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
LIB_DIR="${SCRIPT_DIR}/lib"
TEMPLATES_DIR="${REPO_ROOT}/templates"

# Default output paths
DEFAULT_CONFIG_DIR="${HOME}/printer_data/config"
OUTPUT_DIR="${DEFAULT_CONFIG_DIR}/gschpoozi"
PRINTER_CFG="${DEFAULT_CONFIG_DIR}/printer.cfg"

# State file for wizard selections
STATE_FILE="${REPO_ROOT}/.wizard-state"

# Installation library path
INSTALL_LIB_DIR="${LIB_DIR}"

# ═══════════════════════════════════════════════════════════════════════════════
# COLORS AND FORMATTING
# ═══════════════════════════════════════════════════════════════════════════════

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'
WHITE='\033[0;37m'
NC='\033[0m' # No Color

# Bold variants
BRED='\033[1;31m'
BGREEN='\033[1;32m'
BYELLOW='\033[1;33m'
BBLUE='\033[1;34m'
BMAGENTA='\033[1;35m'
BCYAN='\033[1;36m'
BWHITE='\033[1;37m'

# Box drawing characters
BOX_TL="╔"
BOX_TR="╗"
BOX_BL="╚"
BOX_BR="╝"
BOX_H="═"
BOX_V="║"
BOX_LT="╠"
BOX_RT="╣"

# ═══════════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

# Box width constant - used by all print functions
BOX_WIDTH=70

# Strip ANSI escape codes to get visible length
strip_ansi() {
    echo -e "$1" | sed 's/\x1b\[[0-9;]*m//g'
}

# Truncate string to max length, adding "..." if truncated
truncate_string() {
    local str="$1"
    local max_len="$2"
    if [[ ${#str} -gt $max_len ]]; then
        echo "${str:0:$((max_len-3))}..."
    else
        echo "$str"
    fi
}

# Print a line with left and right borders, properly padded
# Usage: print_box_line "content" [indent]
print_box_line() {
    local content="$1"
    local indent="${2:-2}"  # Default 2 space indent

    # Get visible length (without ANSI codes)
    local visible_content=$(strip_ansi "$content")
    local visible_len=${#visible_content}

    # Calculate padding needed (box width - indent - content)
    local padding=$((BOX_WIDTH - indent - visible_len))
    if [[ $padding -lt 0 ]]; then padding=0; fi

    # Print: left border + indent + content + padding + right border
    # Use %b to interpret escape sequences in content
    printf "${BCYAN}${BOX_V}${NC}"
    printf "%${indent}s" ""
    printf "%b" "$content"
    printf "%${padding}s" ""
    printf "${BCYAN}${BOX_V}${NC}\n"
}

# Print empty line with borders
print_empty_line() {
    printf "${BCYAN}${BOX_V}${NC}"
    printf "%${BOX_WIDTH}s" ""
    printf "${BCYAN}${BOX_V}${NC}\n"
}

print_header() {
    local title="$1"
    local padding=$(( (BOX_WIDTH - ${#title} - 2) / 2 ))

    # Top border
    echo -en "${BCYAN}${BOX_TL}"
    printf "${BOX_H}%.0s" $(seq 1 $BOX_WIDTH)
    echo -e "${BOX_TR}${NC}"

    # Title line
    echo -en "${BCYAN}${BOX_V}${NC}"
    printf "%${padding}s" ""
    echo -n " ${title} "
    printf "%$((BOX_WIDTH - padding - ${#title} - 2))s" ""
    echo -e "${BCYAN}${BOX_V}${NC}"

    # Separator
    echo -en "${BCYAN}${BOX_LT}"
    printf "${BOX_H}%.0s" $(seq 1 $BOX_WIDTH)
    echo -e "${BOX_RT}${NC}"
}

print_footer() {
    echo -en "${BCYAN}${BOX_BL}"
    printf "${BOX_H}%.0s" $(seq 1 $BOX_WIDTH)
    echo -e "${BOX_BR}${NC}"
}

print_menu_item() {
    local num="$1"
    local status="$2"
    local label="$3"
    local value="$4"

    local status_icon
    if [[ "$status" == "done" ]]; then
        status_icon="${GREEN}[✓]${NC}"
    elif [[ "$status" == "partial" ]]; then
        status_icon="${YELLOW}[~]${NC}"
    else
        status_icon="${WHITE}[ ]${NC}"
    fi

    # Calculate max value length (box width - prefix - label - ": " - margins)
    local prefix_len=12  # "║  X) [✓] "
    local max_value_len=$((BOX_WIDTH - prefix_len - ${#label} - 2 - 4))

    local line_content
    if [[ -n "$value" ]]; then
        local truncated_value=$(truncate_string "$value" $max_value_len)
        line_content="${BWHITE}${num})${NC} ${status_icon} ${label}: ${CYAN}${truncated_value}${NC}"
    else
        line_content="${BWHITE}${num})${NC} ${status_icon} ${label}"
    fi
    print_box_line "$line_content"
}

print_separator() {
    echo -e "${BCYAN}${BOX_LT}$(printf "${BOX_H}%.0s" $(seq 1 $BOX_WIDTH))${BOX_RT}${NC}"
}

print_action_item() {
    local key="$1"
    local label="$2"
    print_box_line "${BGREEN}${key})${NC} ${label}"
}

prompt_input() {
    local prompt="$1"
    local default="$2"
    local result
    
    # Send prompt to stderr so it displays when used in $()
    if [[ -n "$default" ]]; then
        echo -en "${BYELLOW}${prompt}${NC} [${default}]: " >&2
    else
        echo -en "${BYELLOW}${prompt}${NC}: " >&2
    fi
    
    read -r result
    
    if [[ -z "$result" && -n "$default" ]]; then
        echo "$default"
    else
        echo "$result"
    fi
}

confirm() {
    local prompt="$1"
    local response
    
    echo -en "${BYELLOW}${prompt}${NC} [y/N]: "
    read -r response
    
    case "$response" in
        [yY][eE][sS]|[yY]) return 0 ;;
        *) return 1 ;;
    esac
}

clear_screen() {
    clear
}

wait_for_key() {
    echo -en "\n${WHITE}Press any key to continue...${NC}"
    read -n 1 -s -r
    echo
}

# ═══════════════════════════════════════════════════════════════════════════════
# PROBE INSTALLATION FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

# Check if a probe module is installed
is_probe_installed() {
    local probe="$1"
    local klipper_extras="${HOME}/klipper/klippy/extras"
    case "$probe" in
        beacon)
            # Check both repo exists AND symlink in Klipper extras
            [[ -d "${HOME}/beacon_klipper" ]] && [[ -L "${klipper_extras}/beacon.py" || -f "${klipper_extras}/beacon.py" ]]
            ;;
        cartographer)
            # Check both repo exists AND symlink in Klipper extras
            [[ -d "${HOME}/cartographer-klipper" ]] && [[ -L "${klipper_extras}/cartographer.py" || -f "${klipper_extras}/cartographer.py" ]]
            ;;
        btt-eddy)
            # BTT Eddy may be built into recent Klipper or installed separately
            [[ -f "${klipper_extras}/eddyprobe.py" ]] || [[ -f "${klipper_extras}/btt_eddy.py" ]] || \
            ([[ -d "${HOME}/Eddy" ]] && [[ -L "${klipper_extras}/btt_eddy.py" || -L "${klipper_extras}/eddy.py" ]])
            ;;
        *)
            return 1
            ;;
    esac
}

# Install probe module
install_probe_module() {
    local probe="$1"
    local klipper_extras="${HOME}/klipper/klippy/extras"
    
    # Disable exit-on-error for installation (we handle errors ourselves)
    set +e
    
    case "$probe" in
        beacon)
            echo -e "\n${CYAN}Installing Beacon Klipper module...${NC}"
            cd "${HOME}"
            if [[ -d "${HOME}/beacon_klipper" ]]; then
                # Check if it's a valid git repo
                if [[ -d "${HOME}/beacon_klipper/.git" ]]; then
                    echo -e "${YELLOW}Beacon directory exists, updating...${NC}"
                    cd "${HOME}/beacon_klipper"
                    git fetch --all
                    git reset --hard origin/main || git reset --hard origin/master
                    git pull || true
                else
                    # Directory exists but not a valid git repo - remove and re-clone
                    echo -e "${YELLOW}Beacon directory exists but is not a valid git repo, removing...${NC}"
                    rm -rf "${HOME}/beacon_klipper"
                    if ! git clone https://github.com/beacon3d/beacon_klipper.git; then
                        echo -e "${RED}Failed to clone Beacon repository${NC}"
                        set -e
                        return 1
                    fi
                fi
            else
                if ! git clone https://github.com/beacon3d/beacon_klipper.git; then
                    echo -e "${RED}Failed to clone Beacon repository${NC}"
                    set -e
                    return 1
                fi
            fi
            echo -e "${CYAN}Running Beacon install script...${NC}"
            if [[ -x "${HOME}/beacon_klipper/install.sh" ]]; then
                "${HOME}/beacon_klipper/install.sh" || echo -e "${YELLOW}Install script returned non-zero (may be OK)${NC}"
            fi
            # Verify symlink was created, create manually if not
            if [[ ! -L "${klipper_extras}/beacon.py" ]]; then
                echo -e "${YELLOW}Symlink not found, creating manually...${NC}"
                ln -sf "${HOME}/beacon_klipper/beacon.py" "${klipper_extras}/beacon.py"
            fi
            if [[ -L "${klipper_extras}/beacon.py" ]]; then
                echo -e "${GREEN}✓ Beacon module linked to Klipper${NC}"
            else
                echo -e "${RED}✗ Failed to link Beacon module${NC}"
            fi
            add_probe_update_manager "beacon"
            echo -e "${GREEN}Beacon installation complete!${NC}"
            ;;
        cartographer)
            echo -e "\n${CYAN}Installing Cartographer Klipper module...${NC}"
            cd "${HOME}"
            if [[ -d "${HOME}/cartographer-klipper" ]]; then
                if [[ -d "${HOME}/cartographer-klipper/.git" ]]; then
                    echo -e "${YELLOW}Cartographer directory exists, updating...${NC}"
                    cd "${HOME}/cartographer-klipper"
                    git fetch --all
                    git reset --hard origin/main || git reset --hard origin/master
                    git pull || true
                else
                    echo -e "${YELLOW}Cartographer directory exists but is not a valid git repo, removing...${NC}"
                    rm -rf "${HOME}/cartographer-klipper"
                    if ! git clone https://github.com/Cartographer3D/cartographer-klipper.git; then
                        echo -e "${RED}Failed to clone Cartographer repository${NC}"
                        set -e
                        return 1
                    fi
                fi
            else
                if ! git clone https://github.com/Cartographer3D/cartographer-klipper.git; then
                    echo -e "${RED}Failed to clone Cartographer repository${NC}"
                    set -e
                    return 1
                fi
            fi
            echo -e "${CYAN}Running Cartographer install script...${NC}"
            if [[ -x "${HOME}/cartographer-klipper/install.sh" ]]; then
                "${HOME}/cartographer-klipper/install.sh" || echo -e "${YELLOW}Install script returned non-zero (may be OK)${NC}"
            fi
            # Verify symlink was created, create manually if not
            if [[ ! -L "${klipper_extras}/cartographer.py" ]]; then
                echo -e "${YELLOW}Symlink not found, creating manually...${NC}"
                ln -sf "${HOME}/cartographer-klipper/cartographer.py" "${klipper_extras}/cartographer.py"
            fi
            if [[ -L "${klipper_extras}/cartographer.py" ]]; then
                echo -e "${GREEN}✓ Cartographer module linked to Klipper${NC}"
            else
                echo -e "${RED}✗ Failed to link Cartographer module${NC}"
            fi
            add_probe_update_manager "cartographer"
            echo -e "${GREEN}Cartographer installation complete!${NC}"
            ;;
        btt-eddy)
            echo -e "\n${CYAN}Installing BTT Eddy module...${NC}"
            cd "${HOME}"
            if [[ -d "${HOME}/Eddy" ]]; then
                if [[ -d "${HOME}/Eddy/.git" ]]; then
                    echo -e "${YELLOW}BTT Eddy directory exists, updating...${NC}"
                    cd "${HOME}/Eddy"
                    git fetch --all
                    git reset --hard origin/main || git reset --hard origin/master
                    git pull || true
                else
                    echo -e "${YELLOW}BTT Eddy directory exists but is not a valid git repo, removing...${NC}"
                    rm -rf "${HOME}/Eddy"
                    if ! git clone https://github.com/bigtreetech/Eddy.git; then
                        echo -e "${RED}Failed to clone BTT Eddy repository${NC}"
                        set -e
                        return 1
                    fi
                fi
            else
                if ! git clone https://github.com/bigtreetech/Eddy.git; then
                    echo -e "${RED}Failed to clone BTT Eddy repository${NC}"
                    set -e
                    return 1
                fi
            fi
            echo -e "${CYAN}Running BTT Eddy install script...${NC}"
            if [[ -x "${HOME}/Eddy/install.sh" ]]; then
                "${HOME}/Eddy/install.sh" || echo -e "${YELLOW}Install script returned non-zero (may be OK)${NC}"
            fi
            # BTT Eddy uses different file names - check for them
            local eddy_linked=false
            for eddy_file in btt_eddy.py eddy.py; do
                if [[ -f "${HOME}/Eddy/${eddy_file}" ]] && [[ ! -L "${klipper_extras}/${eddy_file}" ]]; then
                    echo -e "${YELLOW}Symlink for ${eddy_file} not found, creating manually...${NC}"
                    ln -sf "${HOME}/Eddy/${eddy_file}" "${klipper_extras}/${eddy_file}"
                fi
                if [[ -L "${klipper_extras}/${eddy_file}" ]]; then
                    eddy_linked=true
                fi
            done
            if $eddy_linked; then
                echo -e "${GREEN}✓ BTT Eddy module linked to Klipper${NC}"
            else
                echo -e "${RED}✗ Failed to link BTT Eddy module${NC}"
            fi
            add_probe_update_manager "btt-eddy"
            echo -e "${GREEN}BTT Eddy installation complete!${NC}"
            ;;
        *)
            echo -e "${YELLOW}No installation required for ${probe}${NC}"
            ;;
    esac
    
    # Restart Klipper to load the new module
    if [[ "$probe" == "beacon" || "$probe" == "cartographer" || "$probe" == "btt-eddy" ]]; then
        echo -e "${CYAN}Restarting Klipper to load module...${NC}"
        sudo systemctl restart klipper 2>/dev/null || echo -e "${YELLOW}Could not restart Klipper (may need manual restart)${NC}"
        sleep 2
        if systemctl is-active --quiet klipper 2>/dev/null; then
            echo -e "${GREEN}✓ Klipper restarted successfully${NC}"
        fi
    fi
    
    # Re-enable exit-on-error
    set -e
}

# Add probe update manager entry to moonraker.conf
add_probe_update_manager() {
    local probe="$1"
    local moonraker_conf="${DEFAULT_CONFIG_DIR}/moonraker.conf"
    local entry=""
    
    case "$probe" in
        beacon)
            if ! grep -q "\[update_manager beacon" "$moonraker_conf" 2>/dev/null; then
                entry="
[update_manager beacon]
type: git_repo
channel: dev
path: ~/beacon_klipper
origin: https://github.com/beacon3d/beacon_klipper.git
env: ~/klippy-env/bin/python
requirements: requirements.txt
install_script: install.sh
is_system_service: False
managed_services: klipper
info_tags:
  desc=Beacon Surface Scanner"
            fi
            ;;
        cartographer)
            if ! grep -q "\[update_manager cartographer" "$moonraker_conf" 2>/dev/null; then
                entry="
[update_manager cartographer]
type: git_repo
path: ~/cartographer-klipper
origin: https://github.com/Cartographer3D/cartographer-klipper.git
install_script: install.sh
is_system_service: False
managed_services: klipper
info_tags:
  desc=Cartographer Probe"
            fi
            ;;
        btt-eddy)
            if ! grep -q "\[update_manager Eddy" "$moonraker_conf" 2>/dev/null; then
                entry="
[update_manager Eddy]
type: git_repo
path: ~/Eddy
origin: https://github.com/bigtreetech/Eddy.git
install_script: install.sh
is_system_service: False
managed_services: klipper
info_tags:
  desc=BTT Eddy Probe"
            fi
            ;;
    esac
    
    if [[ -n "$entry" ]]; then
        echo -e "${CYAN}Adding ${probe} to Moonraker update manager...${NC}"
        echo "$entry" | sudo tee -a "$moonraker_conf" > /dev/null
    fi
}

# Check if Crowsnest is installed
is_crowsnest_installed() {
    [[ -d "${HOME}/crowsnest" ]] && [[ -f "${HOME}/crowsnest/crowsnest" ]]
}

# Install Crowsnest
install_crowsnest() {
    echo -e "\n${CYAN}Installing Crowsnest webcam streamer...${NC}"
    
    # Disable exit-on-error for installation
    set +e
    
    cd "${HOME}"
    
    if [[ -d "${HOME}/crowsnest" ]]; then
        if [[ -d "${HOME}/crowsnest/.git" ]]; then
            echo -e "${YELLOW}Crowsnest directory exists, updating...${NC}"
            cd "${HOME}/crowsnest"
            git fetch --all
            git reset --hard origin/master || git reset --hard origin/main
            git pull || true
        else
            echo -e "${YELLOW}Crowsnest directory exists but is not a valid git repo, removing...${NC}"
            rm -rf "${HOME}/crowsnest"
            if ! git clone https://github.com/mainsail-crew/crowsnest.git; then
                echo -e "${RED}Failed to clone Crowsnest repository${NC}"
                set -e
                return 1
            fi
        fi
    else
        if ! git clone https://github.com/mainsail-crew/crowsnest.git; then
            echo -e "${RED}Failed to clone Crowsnest repository${NC}"
            set -e
            return 1
        fi
    fi
    
    echo -e "${CYAN}Running Crowsnest install script...${NC}"
    cd "${HOME}/crowsnest"
    if [[ -x "tools/install.sh" ]]; then
        sudo tools/install.sh || echo -e "${YELLOW}Install script returned non-zero (may be OK)${NC}"
    elif [[ -f "tools/install.sh" ]]; then
        sudo bash tools/install.sh || echo -e "${YELLOW}Install script returned non-zero (may be OK)${NC}"
    fi
    
    add_crowsnest_update_manager
    echo -e "${GREEN}Crowsnest installation complete!${NC}"
    
    # Re-enable exit-on-error
    set -e
}

# Add Crowsnest update manager entry to moonraker.conf
add_crowsnest_update_manager() {
    local moonraker_conf="${DEFAULT_CONFIG_DIR}/moonraker.conf"
    
    if ! grep -q "\[update_manager crowsnest" "$moonraker_conf" 2>/dev/null; then
        local entry="
[update_manager crowsnest]
type: git_repo
path: ~/crowsnest
origin: https://github.com/mainsail-crew/crowsnest.git
managed_services: crowsnest
install_script: tools/install.sh"
        
        echo -e "${CYAN}Adding Crowsnest to Moonraker update manager...${NC}"
        echo "$entry" | sudo tee -a "$moonraker_conf" > /dev/null
    fi
}

# ═══════════════════════════════════════════════════════════════════════════════
# MCU FIRMWARE UPDATE FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

# Get Klipper host version
get_klipper_host_version() {
    if [[ -d "${HOME}/klipper" ]]; then
        cd "${HOME}/klipper"
        git describe --tags --always --dirty 2>/dev/null || echo "unknown"
    else
        echo "not installed"
    fi
}

# Check if Klipper is dirty (uncommitted changes, often from linux MCU build)
is_klipper_dirty() {
    local version=$(get_klipper_host_version)
    [[ "$version" == *"-dirty"* ]]
}

# Check if linux MCU service is installed
is_linux_mcu_installed() {
    systemctl list-unit-files 2>/dev/null | grep -q "klipper_mcu\|klipper-mcu"
}

# Check for MCU version mismatches and offer to fix
check_mcu_versions() {
    local host_version=$(get_klipper_host_version)
    local has_issues=false
    local is_dirty=false
    
    # Check if dirty
    if [[ "$host_version" == *"-dirty"* ]]; then
        is_dirty=true
        has_issues=true
    fi
    
    if $has_issues; then
        clear_screen
        print_header "MCU Version Check"
        
        print_box_line "${YELLOW}Potential MCU issues detected!${NC}"
        print_empty_line
        print_box_line "Host Version: ${BWHITE}${host_version}${NC}"
        
        if $is_dirty; then
            print_empty_line
            print_box_line "${YELLOW}⚠ Klipper marked as 'dirty'${NC}"
            print_box_line "${WHITE}This usually means the Linux MCU needs updating.${NC}"
            print_box_line "${WHITE}The Linux MCU runs on the Pi for GPIO/sensors.${NC}"
        fi
        
        print_separator
        print_box_line "${BWHITE}Recommended: Update Linux Process MCU${NC}"
        print_box_line "This will rebuild and reinstall the host MCU service."
        print_footer
        
        if confirm "Update Linux MCU now to fix version mismatch?"; then
            update_linux_mcu
            wait_for_key
            return 0
        fi
        
        return 1
    fi
    
    return 0
}

# Auto-check MCU versions on config generation
pre_generate_mcu_check() {
    local host_version=$(get_klipper_host_version)
    
    # If dirty, warn but don't block
    if is_klipper_dirty; then
        echo -e "${YELLOW}Warning: Klipper marked as 'dirty' - Linux MCU may need update${NC}"
        echo -e "${YELLOW}Use 'F' from main menu to update MCU firmware${NC}"
        echo ""
    fi
}

# Update the linux process MCU (runs on Pi, no hardware access needed)
update_linux_mcu() {
    echo -e "${CYAN}Updating Linux Process MCU...${NC}"
    
    local klipper_dir="${HOME}/klipper"
    
    if [[ ! -d "$klipper_dir" ]]; then
        echo -e "${RED}Klipper directory not found at ${klipper_dir}${NC}"
        return 1
    fi
    
    cd "$klipper_dir"
    
    # Stop Klipper and linux MCU service
    echo -e "${CYAN}Stopping services...${NC}"
    sudo systemctl stop klipper 2>/dev/null || true
    sudo systemctl stop klipper_mcu 2>/dev/null || sudo systemctl stop klipper-mcu 2>/dev/null || true
    
    # Clean previous builds
    echo -e "${CYAN}Cleaning previous build...${NC}"
    make clean 2>/dev/null || true
    
    # Create complete config for linux process MCU
    # This config includes all necessary options for GPIO, SPI, I2C, etc.
    echo -e "${CYAN}Configuring for Linux process...${NC}"
    cat > .config << 'EOF'
CONFIG_LOW_LEVEL_OPTIONS=y
CONFIG_MACH_LINUX=y
CONFIG_BOARD_DIRECTORY="linux"
CONFIG_CLOCK_FREQ=50000000
CONFIG_LINUX_SELECT=y
CONFIG_HAVE_GPIO=y
CONFIG_HAVE_GPIO_ADC=y
CONFIG_HAVE_GPIO_SPI=y
CONFIG_HAVE_GPIO_I2C=y
CONFIG_HAVE_GPIO_HARD_PWM=y
CONFIG_HAVE_STRICT_TIMING=y
CONFIG_HAVE_CHIPID=y
CONFIG_HAVE_STEPPER_BOTH_EDGE=y
CONFIG_HAVE_BOOTLOADER_REQUEST=y
CONFIG_INLINE_STEPPER_HACK=y
EOF
    
    # Run olddefconfig to fill in remaining defaults
    make olddefconfig 2>/dev/null || true
    
    # Build
    echo -e "${CYAN}Building firmware...${NC}"
    if ! make -j$(nproc) 2>&1; then
        echo -e "${RED}Build failed${NC}"
        sudo systemctl start klipper 2>/dev/null || true
        return 1
    fi
    
    # Install the linux MCU service using Klipper's script
    echo -e "${CYAN}Installing Linux MCU service...${NC}"
    
    # Use Klipper's flash script if available
    if [[ -f "${klipper_dir}/scripts/flash-linux.sh" ]]; then
        sudo "${klipper_dir}/scripts/flash-linux.sh"
    else
        # Manual installation
        sudo cp out/klipper.elf /usr/local/bin/klipper_mcu
        
        # Create systemd service if not exists
        if [[ ! -f /etc/systemd/system/klipper_mcu.service ]]; then
            sudo tee /etc/systemd/system/klipper_mcu.service > /dev/null << 'SVCEOF'
[Unit]
Description=Klipper MCU for Linux
After=local-fs.target

[Service]
ExecStart=/usr/local/bin/klipper_mcu -r
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
SVCEOF
            sudo systemctl daemon-reload
            sudo systemctl enable klipper_mcu
        fi
    fi
    
    # Start the linux MCU service
    echo -e "${CYAN}Starting Linux MCU service...${NC}"
    sudo systemctl start klipper_mcu 2>/dev/null || sudo systemctl start klipper-mcu 2>/dev/null || true
    sleep 1
    
    # Restart Klipper
    echo -e "${CYAN}Starting Klipper service...${NC}"
    sudo systemctl start klipper
    
    echo -e "${GREEN}Linux MCU update complete!${NC}"
    return 0
}

# Update USB-connected MCU
update_usb_mcu() {
    local serial_path="$1"
    local mcu_type="${2:-stm32}"
    
    echo -e "${CYAN}Updating MCU at ${serial_path}...${NC}"
    
    local klipper_dir="${HOME}/klipper"
    
    if [[ ! -d "$klipper_dir" ]]; then
        echo -e "${RED}Klipper directory not found${NC}"
        return 1
    fi
    
    if [[ ! -e "$serial_path" ]]; then
        echo -e "${RED}Serial device not found: ${serial_path}${NC}"
        return 1
    fi
    
    cd "$klipper_dir"
    
    # Stop Klipper
    echo -e "${CYAN}Stopping Klipper...${NC}"
    sudo systemctl stop klipper 2>/dev/null || true
    sleep 2
    
    # Flash using make flash (works for most USB devices in application mode)
    echo -e "${CYAN}Flashing firmware...${NC}"
    if make flash FLASH_DEVICE="$serial_path" 2>&1; then
        echo -e "${GREEN}Flash successful!${NC}"
    else
        echo -e "${YELLOW}Direct flash failed, MCU may need bootloader mode${NC}"
        echo -e "${YELLOW}Try: Double-press reset button to enter bootloader${NC}"
    fi
    
    # Restart Klipper
    echo -e "${CYAN}Starting Klipper...${NC}"
    sudo systemctl start klipper
    
    return 0
}

# Update CAN-connected MCU via Katapult
update_can_mcu() {
    local uuid="$1"
    local interface="${2:-can0}"
    
    echo -e "${CYAN}Updating CAN MCU ${uuid}...${NC}"
    
    local klipper_dir="${HOME}/klipper"
    local katapult_dir="${HOME}/katapult"
    
    if [[ ! -d "$katapult_dir" ]]; then
        echo -e "${RED}Katapult not installed. Install it first for CAN flashing.${NC}"
        return 1
    fi
    
    # Check if flashtool exists
    local flash_tool="${katapult_dir}/scripts/flash_can.py"
    if [[ ! -f "$flash_tool" ]]; then
        flash_tool="${katapult_dir}/scripts/flashtool.py"
    fi
    
    if [[ ! -f "$flash_tool" ]]; then
        echo -e "${RED}Katapult flash tool not found${NC}"
        return 1
    fi
    
    cd "$klipper_dir"
    
    # Stop Klipper
    echo -e "${CYAN}Stopping Klipper...${NC}"
    sudo systemctl stop klipper 2>/dev/null || true
    sleep 2
    
    # Flash via CAN
    local python_env="${HOME}/klippy-env/bin/python"
    echo -e "${CYAN}Flashing via CAN bus...${NC}"
    if "$python_env" "$flash_tool" -i "$interface" -u "$uuid" -f out/klipper.bin 2>&1; then
        echo -e "${GREEN}CAN flash successful!${NC}"
    else
        echo -e "${RED}CAN flash failed${NC}"
    fi
    
    # Restart Klipper
    echo -e "${CYAN}Starting Klipper...${NC}"
    sudo systemctl start klipper
    
    return 0
}

# ═══════════════════════════════════════════════════════════════════════════════
# STEPPER CALIBRATION MENU
# ═══════════════════════════════════════════════════════════════════════════════

menu_stepper_calibration() {
    local kinematics="${WIZARD_STATE[kinematics]:-corexy}"
    local is_awd=$([[ "$kinematics" == "corexy-awd" ]] && echo "yes" || echo "no")
    local z_count="${WIZARD_STATE[z_stepper_count]:-1}"
    local driver="${WIZARD_STATE[driver_X]:-TMC2209}"
    local is_tmc=$([[ "$driver" == TMC* ]] && echo "yes" || echo "no")

    while true; do
        clear_screen
        print_header "Stepper Calibration"

        print_box_line "${BWHITE}Stepper Identification & Direction Calibration${NC}"
        print_empty_line
        print_box_line "This generates macros to help you:"
        print_box_line "- Identify which physical motor is on which driver"
        print_box_line "- Verify motor directions are correct"
        if [[ "$is_awd" == "yes" ]]; then
            print_box_line "- ${GREEN}Test AWD motor pairs safely (one pair at a time)${NC}"
        fi
        print_empty_line

        print_separator
        print_box_line "${BWHITE}Your Configuration:${NC}"
        print_box_line "Kinematics: ${CYAN}${kinematics}${NC}"
        print_box_line "Z Motors: ${CYAN}${z_count}${NC}"
        print_box_line "Driver: ${CYAN}${driver}${NC}"
        if [[ "$is_tmc" == "yes" ]]; then
            print_box_line "TMC Status: ${GREEN}TMC query macros will be included${NC}"
        fi
        print_empty_line

        print_separator
        print_box_line "${BWHITE}Available Macros (after generation):${NC}"
        print_empty_line
        print_box_line "${CYAN}STEPPER_CALIBRATION_WIZARD${NC} - Display calibration instructions"
        print_box_line "${CYAN}IDENTIFY_ALL_STEPPERS${NC} - Buzz each motor for identification"
        print_box_line "${CYAN}IDENTIFY_STEPPER STEPPER=name${NC} - Buzz a single motor"
        if [[ "$is_tmc" == "yes" ]]; then
            print_box_line "${CYAN}QUERY_TMC_STATUS${NC} - Query all TMC driver registers"
        fi
        if [[ "$is_awd" == "yes" ]]; then
            print_empty_line
            print_box_line "${BWHITE}AWD-Specific (safe pair testing):${NC}"
            print_box_line "${CYAN}AWD_FULL_TEST${NC} - Complete pair-by-pair calibration"
            print_box_line "${CYAN}AWD_TEST_PAIR_A${NC} - Test X+Y only (X1+Y1 disabled)"
            print_box_line "${CYAN}AWD_TEST_PAIR_B${NC} - Test X1+Y1 only (X+Y disabled)"
            print_box_line "${CYAN}AWD_ENABLE_ALL${NC} - Re-enable all motors"
        else
            print_box_line "${CYAN}COREXY_DIRECTION_CHECK${NC} - Test CoreXY directions"
        fi
        if [[ "$z_count" -gt 1 ]]; then
            print_box_line "${CYAN}Z_DIRECTION_CHECK${NC} - Verify all Z motors match"
        fi
        print_empty_line

        print_separator
        print_action_item "D" "Interactive Discovery (live motor testing)"
        print_action_item "G" "Generate calibration.cfg now"
        print_action_item "I" "Show calibration instructions"
        print_action_item "B" "Back"
        print_footer

        echo -en "${BYELLOW}Select option${NC}: "
        read -r choice

        case "$choice" in
            [dD])
                run_motor_discovery
                ;;
            [gG])
                echo -e "\n${CYAN}Generating calibration.cfg...${NC}"
                python3 "${SCRIPT_DIR}/generate-config.py" --output-dir "${OUTPUT_DIR}" --calibration-only
                echo -e "${GREEN}✓ calibration.cfg generated!${NC}"
                echo -e "\n${WHITE}Add to your printer.cfg:${NC}"
                echo -e "${CYAN}[include gschpoozi/calibration.cfg]${NC}"
                wait_for_key
                ;;
            [iI])
                show_calibration_instructions "$is_awd" "$is_tmc" "$z_count"
                wait_for_key
                ;;
            [bB])
                return
                ;;
        esac
    done
}

run_motor_discovery() {
    # Pre-flight checks
    clear_screen
    print_header "Motor Discovery - Pre-flight Check"
    
    # Check if board is selected
    if [[ -z "${WIZARD_STATE[board]}" ]]; then
        print_box_line "${RED}Error: No main board selected!${NC}"
        print_box_line "Please select a board first in the wizard."
        print_footer
        wait_for_key
        return 1
    fi
    
    # Check if MCU serial is available
    local mcu_serial="${WIZARD_STATE[mcu_serial]:-}"
    if [[ -z "$mcu_serial" ]]; then
        print_box_line "${RED}Error: MCU serial not detected!${NC}"
        print_box_line "Please ensure:"
        print_box_line "- MCU is connected via USB/serial"
        print_box_line "- Klipper firmware is flashed on the board"
        print_footer
        wait_for_key
        return 1
    fi
    
    # Check if Klipper/Moonraker are running
    if ! systemctl is-active --quiet klipper 2>/dev/null; then
        print_box_line "${RED}Error: Klipper service is not running!${NC}"
        print_box_line "Start Klipper first: ${CYAN}sudo systemctl start klipper${NC}"
        print_footer
        wait_for_key
        return 1
    fi
    
    if ! systemctl is-active --quiet moonraker 2>/dev/null; then
        print_box_line "${RED}Error: Moonraker service is not running!${NC}"
        print_box_line "Start Moonraker first: ${CYAN}sudo systemctl start moonraker${NC}"
        print_footer
        wait_for_key
        return 1
    fi
    
    print_box_line "${GREEN}✓${NC} Board selected: ${CYAN}${WIZARD_STATE[board_name]}${NC}"
    print_box_line "${GREEN}✓${NC} MCU serial: ${CYAN}${mcu_serial}${NC}"
    print_box_line "${GREEN}✓${NC} Klipper running"
    print_box_line "${GREEN}✓${NC} Moonraker running"
    print_empty_line
    print_separator
    
    print_box_line "${YELLOW}WARNING: This will temporarily replace your printer.cfg${NC}"
    print_box_line "${YELLOW}with a discovery config. It will be restored after.${NC}"
    print_empty_line
    print_footer
    
    if ! confirm "Proceed with motor discovery?"; then
        return 0
    fi
    
    # Build arguments for motor-discovery.py
    local args=(
        "--board" "${WIZARD_STATE[board]}"
        "--mcu-serial" "${mcu_serial}"
    )
    
    # Add driver type
    if [[ -n "${WIZARD_STATE[driver_X]}" ]]; then
        args+=("--driver" "${WIZARD_STATE[driver_X]}")
    fi
    
    # Add kinematics
    if [[ -n "${WIZARD_STATE[kinematics]}" ]]; then
        args+=("--kinematics" "${WIZARD_STATE[kinematics]}")
    fi
    
    # Add Z count
    if [[ -n "${WIZARD_STATE[z_stepper_count]}" ]]; then
        args+=("--z-count" "${WIZARD_STATE[z_stepper_count]}")
    fi
    
    # Check for toolboard
    if [[ -n "${WIZARD_STATE[toolboard]}" && "${WIZARD_STATE[toolboard]}" != "none" ]]; then
        args+=("--has-toolboard")
    fi
    
    # Run the discovery script
    echo ""
    python3 "${SCRIPT_DIR}/motor-discovery.py" "${args[@]}"
    local result=$?
    
    # Check if results file exists
    local results_file="${HOME}/printer_data/config/.motor_mapping.json"
    if [[ $result -eq 0 && -f "$results_file" ]]; then
        echo -e "\n${GREEN}Motor discovery completed!${NC}"
        echo -e "${WHITE}Results saved to: ${CYAN}${results_file}${NC}"
        
        # Load results into wizard state
        if command -v jq &>/dev/null; then
            echo -e "\n${WHITE}Discovered mappings:${NC}"
            jq -r '.motor_mapping | to_entries[] | "  \(.key) → \(.value.port)" + (if .value.dir_invert then " (INVERT)" else "" end)' "$results_file"
        fi
    fi
    
    wait_for_key
    return $result
}

show_calibration_instructions() {
    local is_awd="$1"
    local is_tmc="$2"
    local z_count="$3"

    clear_screen
    print_header "Stepper Calibration Instructions"

    print_empty_line
    print_box_line "${BWHITE}STEP 1: Generate Configuration${NC}"
    print_box_line "Generate calibration.cfg and add to printer.cfg:"
    print_box_line "${CYAN}[include gschpoozi/calibration.cfg]${NC}"
    print_box_line "Then restart Klipper."
    print_empty_line

    print_box_line "${BWHITE}STEP 2: Identify Motors${NC}"
    print_box_line "Run from console: ${CYAN}IDENTIFY_ALL_STEPPERS${NC}"
    print_box_line "Watch each motor and note which one moves."
    print_box_line "This helps verify your wiring is correct."
    print_empty_line

    if [[ "$is_tmc" == "yes" ]]; then
        print_box_line "${BWHITE}STEP 3: Check TMC Communication${NC}"
        print_box_line "Run: ${CYAN}QUERY_TMC_STATUS${NC}"
        print_box_line "Verify no 00000000 or ffffffff errors."
        print_box_line "Look for 'ola'/'olb' flags = motor disconnected."
        print_empty_line
    fi

    if [[ "$is_awd" == "yes" ]]; then
        print_box_line "${BWHITE}STEP 4: AWD Safe Pair Testing${NC}"
        print_box_line "Run: ${CYAN}AWD_FULL_TEST${NC}"
        print_empty_line
        print_box_line "This tests motors in pairs to prevent fighting:"
        print_box_line "- First test: Only X+Y move (X1+Y1 disabled)"
        print_box_line "- Second test: Only X1+Y1 move (X+Y disabled)"
        print_empty_line
        print_box_line "Both pairs should move the toolhead identically."
        print_box_line "If they don't match, adjust dir_pins."
        print_empty_line
    else
        print_box_line "${BWHITE}STEP 4: Direction Check${NC}"
        print_box_line "Run: ${CYAN}COREXY_DIRECTION_CHECK${NC}"
        print_box_line "Verify +X goes right, +Y goes back."
        print_empty_line
    fi

    if [[ "$z_count" -gt 1 ]]; then
        print_box_line "${BWHITE}STEP 5: Z Axis Verification${NC}"
        print_box_line "Run: ${CYAN}Z_DIRECTION_CHECK${NC}"
        print_box_line "All ${z_count} Z motors should move the same direction."
        print_empty_line
    fi

    print_separator
    print_box_line "${BWHITE}Resources:${NC}"
    print_box_line "${CYAN}https://www.klipper3d.org/Config_checks.html${NC}"
    print_box_line "${CYAN}https://mpx.wiki/Troubleshooting/corexy-direction${NC}"
    print_footer
}

# Interactive MCU firmware update menu
menu_mcu_firmware_update() {
    while true; do
        clear_screen
        print_header "MCU Firmware Update"
        
        local host_version=$(get_klipper_host_version)
        print_box_line "Klipper Host Version: ${BWHITE}${host_version}${NC}"
        print_empty_line
        print_box_line "${YELLOW}Note: MCU firmware must match host version${NC}"
        print_box_line "${YELLOW}for Klipper to communicate properly.${NC}"
        print_empty_line
        
        print_separator
        
        # Linux MCU option
        local linux_status=""
        if is_linux_mcu_installed; then
            linux_status="${GREEN}[installed]${NC}"
        fi
        print_menu_item "1" "" "Update Linux Process MCU (Pi GPIO)" "${linux_status}"
        
        # USB MCU option
        print_menu_item "2" "" "Update USB MCU (mainboard/toolboard)" ""
        
        # CAN MCU option (requires Katapult)
        local katapult_status=""
        if is_katapult_installed; then
            katapult_status="${GREEN}[Katapult ready]${NC}"
        else
            katapult_status="${YELLOW}[needs Katapult]${NC}"
        fi
        print_menu_item "3" "" "Update CAN MCU via Katapult" "${katapult_status}"
        
        print_empty_line
        print_action_item "B" "Back"
        
        print_footer
        
        read -r -p "Select option: " choice
        
        case "$choice" in
            1)
                if confirm "Update Linux Process MCU firmware?"; then
                    update_linux_mcu
                    wait_for_key
                fi
                ;;
            2)
                menu_update_usb_mcu
                ;;
            3)
                if ! is_katapult_installed; then
                    echo -e "${YELLOW}Katapult must be installed for CAN flashing.${NC}"
                    if confirm "Install Katapult now?"; then
                        install_katapult
                    fi
                else
                    menu_update_can_mcu
                fi
                wait_for_key
                ;;
            [Bb])
                return
                ;;
        esac
    done
}

# USB MCU update submenu
menu_update_usb_mcu() {
    clear_screen
    print_header "Update USB MCU"
    
    print_box_line "Scanning for USB MCUs..."
    print_empty_line
    
    local -a devices
    mapfile -t devices < <(detect_usb_mcus)
    
    if [[ ${#devices[@]} -eq 0 ]]; then
        print_box_line "${YELLOW}No USB MCUs found.${NC}"
        print_footer
        wait_for_key
        return
    fi
    
    local num=1
    for device in "${devices[@]}"; do
        local desc=$(get_mcu_description "$device")
        local display_path="$device"
        if [[ ${#device} -gt 45 ]]; then
            display_path="...${device: -42}"
        fi
        print_box_line "${BWHITE}${num})${NC} ${desc}: ${display_path}"
        ((num++))
    done
    
    print_empty_line
    print_action_item "B" "Back"
    print_footer
    
    read -r -p "Select MCU to update: " choice
    
    if [[ "$choice" =~ ^[0-9]+$ ]] && [[ "$choice" -ge 1 ]] && [[ "$choice" -lt "$num" ]]; then
        local idx=$((choice - 1))
        local selected_device="${devices[$idx]}"
        
        echo -e "${YELLOW}WARNING: Ensure you have the correct firmware config for this MCU.${NC}"
        echo -e "${YELLOW}The last 'make menuconfig' settings will be used.${NC}"
        
        if confirm "Flash firmware to ${selected_device}?"; then
            update_usb_mcu "$selected_device"
        fi
    fi
    
    wait_for_key
}

# CAN MCU update submenu
menu_update_can_mcu() {
    clear_screen
    print_header "Update CAN MCU"
    
    print_box_line "Scanning CAN bus for devices..."
    print_empty_line
    
    local -a uuids
    mapfile -t uuids < <(detect_can_mcus)
    
    if [[ ${#uuids[@]} -eq 0 ]]; then
        print_box_line "${YELLOW}No CAN devices found.${NC}"
        print_box_line "${YELLOW}Make sure can0 is up and devices are powered.${NC}"
        print_footer
        wait_for_key
        return
    fi
    
    local num=1
    for uuid in "${uuids[@]}"; do
        print_box_line "${BWHITE}${num})${NC} UUID: ${uuid}"
        ((num++))
    done
    
    print_empty_line
    print_action_item "B" "Back"
    print_footer
    
    read -r -p "Select CAN device to update: " choice
    
    if [[ "$choice" =~ ^[0-9]+$ ]] && [[ "$choice" -ge 1 ]] && [[ "$choice" -lt "$num" ]]; then
        local idx=$((choice - 1))
        local selected_uuid="${uuids[$idx]}"
        
        echo -e "${YELLOW}WARNING: Ensure you have the correct firmware config for this MCU.${NC}"
        echo -e "${YELLOW}The last 'make menuconfig' settings will be used.${NC}"
        
        if confirm "Flash firmware to CAN device ${selected_uuid}?"; then
            update_can_mcu "$selected_uuid"
        fi
    fi
    
    wait_for_key
}

# ═══════════════════════════════════════════════════════════════════════════════
# MCU SERIAL DETECTION
# ═══════════════════════════════════════════════════════════════════════════════

# Detect USB MCUs by scanning /dev/serial/by-id/
# Returns array of paths, one per line
detect_usb_mcus() {
    local devices=()
    
    if [[ -d "/dev/serial/by-id" ]]; then
        for device in /dev/serial/by-id/*; do
            if [[ -e "$device" ]]; then
                # Filter for Klipper-flashed devices (contain "Klipper" or common MCU names)
                local basename=$(basename "$device")
                if [[ "$basename" == *Klipper* ]] || \
                   [[ "$basename" == *stm32* ]] || \
                   [[ "$basename" == *rp2040* ]] || \
                   [[ "$basename" == *BIGTREETECH* ]] || \
                   [[ "$basename" == *Mellow* ]] || \
                   [[ "$basename" == *Katapult* ]] || \
                   [[ "$basename" == *Beacon* ]] || \
                   [[ "$basename" == *beacon* ]]; then
                    echo "$device"
                fi
            fi
        done
    fi
}

# Get human-readable description from serial path
get_mcu_description() {
    local serial_path="$1"
    local basename=$(basename "$serial_path")
    
    # Extract useful info from the serial ID
    # Format: usb-Klipper_stm32h723xx_SERIALNUM-if00
    local desc=""
    
    if [[ "$basename" == *Klipper* ]]; then
        # Extract MCU type (e.g., stm32h723xx, rp2040)
        if [[ "$basename" =~ Klipper_([^_]+) ]]; then
            desc="${BASH_REMATCH[1]}"
        fi
    elif [[ "$basename" == *BIGTREETECH* ]]; then
        desc="BTT device"
    elif [[ "$basename" == *Mellow* ]]; then
        desc="Mellow device"
    elif [[ "$basename" == *Katapult* ]]; then
        desc="Katapult bootloader"
    elif [[ "$basename" == *[Bb]eacon* ]]; then
        desc="Beacon probe"
    else
        desc="USB device"
    fi
    
    echo "$desc"
}

# Detect CAN MCUs using canbus_query.py
# Returns UUIDs, one per line
detect_can_mcus() {
    local can_interface="${1:-can0}"
    local query_script="${HOME}/klipper/scripts/canbus_query.py"
    local python_env="${HOME}/klippy-env/bin/python"
    
    # Check if CAN interface exists
    if ! ip link show "$can_interface" &>/dev/null; then
        return
    fi
    
    # Check if query script exists
    if [[ ! -f "$query_script" ]]; then
        return
    fi
    
    # Run canbus query and parse UUIDs
    if [[ -x "$python_env" ]]; then
        "$python_env" "$query_script" "$can_interface" 2>/dev/null | \
            grep -oE '[0-9a-f]{12}' || true
    fi
}

# ═══════════════════════════════════════════════════════════════════════════════
# CAN BUS SETUP FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

# Check if CAN interface exists and is UP
# Returns: 0 if working, 1 if not
check_can_interface() {
    local interface="${1:-can0}"
    
    # Check if interface exists
    if ! ip link show "$interface" &>/dev/null; then
        return 1
    fi
    
    # Check if interface is UP
    if ! ip link show "$interface" 2>/dev/null | grep -q "state UP"; then
        return 2
    fi
    
    return 0
}

# Get current CAN interface bitrate
get_can_bitrate() {
    local interface="${1:-can0}"
    ip -details link show "$interface" 2>/dev/null | grep -oP 'bitrate \K[0-9]+' || echo "0"
}

# Check all CAN requirements
# Returns: 0 if all good, non-zero otherwise
check_can_requirements() {
    local interface="${1:-can0}"
    local -a issues=()
    
    # Check 1: Does interface exist?
    if ! ip link show "$interface" &>/dev/null; then
        issues+=("CAN interface '$interface' does not exist")
    else
        # Check 2: Is interface UP?
        if ! ip link show "$interface" 2>/dev/null | grep -q "state UP"; then
            issues+=("CAN interface '$interface' exists but is DOWN")
        fi
        
        # Check 3: Get bitrate
        local bitrate
        bitrate=$(get_can_bitrate "$interface")
        if [[ "$bitrate" == "0" ]]; then
            issues+=("Could not determine bitrate for '$interface'")
        fi
    fi
    
    # Check 4: Does canbus_query.py exist?
    if [[ ! -f "${HOME}/klipper/scripts/canbus_query.py" ]]; then
        issues+=("Klipper CAN query script not found")
    fi
    
    # Return issues
    if [[ ${#issues[@]} -gt 0 ]]; then
        printf '%s\n' "${issues[@]}"
        return 1
    fi
    
    return 0
}

# Setup CAN interface file
# Creates /etc/network/interfaces.d/can0
setup_can_interface() {
    local interface="${1:-can0}"
    local bitrate="${2:-1000000}"
    local interfaces_file="/etc/network/interfaces.d/${interface}"
    
    # Check if file already exists
    if [[ -f "$interfaces_file" ]]; then
        echo -e "${YELLOW}CAN interface file already exists at ${interfaces_file}${NC}"
        if confirm "Do you want to overwrite it?"; then
            :
        else
            return 0
        fi
    fi
    
    echo -e "${CYAN}Creating CAN interface configuration...${NC}"
    
    # Create interface file content
    local config_content="# CAN interface for Klipper
# Created by gschpoozi
allow-hotplug ${interface}
iface ${interface} can static
    bitrate ${bitrate}
    up ifconfig \$IFACE txqueuelen 1024
"
    
    # Write the file (requires sudo)
    echo "$config_content" | sudo tee "$interfaces_file" > /dev/null
    
    if [[ $? -eq 0 ]]; then
        echo -e "${GREEN}Created ${interfaces_file}${NC}"
        return 0
    else
        echo -e "${RED}Failed to create ${interfaces_file}${NC}"
        return 1
    fi
}

# Bring up CAN interface
bring_up_can_interface() {
    local interface="${1:-can0}"
    local bitrate="${2:-1000000}"
    
    echo -e "${CYAN}Bringing up CAN interface ${interface}...${NC}"
    
    # First try to bring it down if it exists
    sudo ip link set "$interface" down 2>/dev/null || true
    
    # Set up and bring up
    if sudo ip link set "$interface" up type can bitrate "$bitrate"; then
        echo -e "${GREEN}CAN interface ${interface} is UP at ${bitrate} bps${NC}"
        return 0
    else
        echo -e "${RED}Failed to bring up ${interface}${NC}"
        return 1
    fi
}

# Interactive CAN setup menu
menu_can_setup() {
    while true; do
        clear_screen
        print_header "CAN Bus Setup"
        
        local can_status
        local bitrate="N/A"
        
        if check_can_interface "can0"; then
            can_status="${GREEN}UP${NC}"
            bitrate=$(get_can_bitrate "can0")
        elif ip link show can0 &>/dev/null; then
            can_status="${YELLOW}DOWN${NC}"
        else
            can_status="${RED}Not configured${NC}"
        fi
        
        print_box_line "CAN Interface Status: ${can_status}"
        if [[ "$bitrate" != "N/A" && "$bitrate" != "0" ]]; then
            print_box_line "Bitrate: ${BWHITE}${bitrate} bps${NC}"
        fi
        
        # Show selected CAN adapter
        local can_adapter="${WIZARD_STATE[can_adapter]:-not selected}"
        print_box_line "CAN Adapter: ${BWHITE}${can_adapter}${NC}"
        print_empty_line
        print_separator
        
        print_menu_item "1" "" "Select CAN adapter"
        print_menu_item "2" "" "Setup CAN interface (create config file)"
        print_menu_item "3" "" "Bring up CAN interface manually"
        print_menu_item "4" "" "Check CAN requirements"
        print_menu_item "5" "" "Diagnose CAN issues"
        print_menu_item "6" "" "Install Katapult (optional bootloader)"
        print_empty_line
        print_action_item "B" "Back"
        
        print_footer
        
        read -r -p "Select option: " choice
        
        case "$choice" in
            1)
                menu_select_can_adapter
                ;;
            2)
                menu_can_interface_setup
                ;;
            3)
                menu_can_bring_up
                ;;
            4)
                menu_can_check
                ;;
            5)
                diagnose_can_issues
                wait_for_key
                ;;
            6)
                menu_katapult_install
                ;;
            [Bb])
                return
                ;;
        esac
    done
}

# CAN adapter selection menu
menu_select_can_adapter() {
    clear_screen
    print_header "Select CAN Adapter"
    
    print_box_line "How is your CAN bus connected to the Pi?"
    print_empty_line
    print_separator
    
    # List available CAN adapters from templates
    local -a adapters=()
    local -a adapter_names=()
    local num=1
    
    # Add USB-CAN Bridge mode option first
    adapters+=("usb-can-bridge")
    adapter_names+=("Mainboard USB-CAN Bridge Mode")
    print_menu_item "$num" "" "Mainboard USB-CAN Bridge Mode"
    ((num++))
    
    # Load CAN adapter templates
    if [[ -d "${TEMPLATES_DIR}/can-adapters" ]]; then
        for adapter_file in "${TEMPLATES_DIR}/can-adapters"/*.json; do
            if [[ -f "$adapter_file" ]]; then
                local adapter_id adapter_name
                adapter_id=$(basename "$adapter_file" .json)
                adapter_name=$(python3 -c "import json; print(json.load(open('$adapter_file'))['name'])" 2>/dev/null)
                
                if [[ -n "$adapter_name" ]]; then
                    adapters+=("$adapter_id")
                    adapter_names+=("$adapter_name")
                    print_menu_item "$num" "" "$adapter_name"
                    ((num++))
                fi
            fi
        done
    fi
    
    print_separator
    print_action_item "B" "Back"
    print_footer

    read -r -p "Select adapter: " choice

    case "$choice" in
        [bB]) return ;;
    esac

    if [[ "$choice" =~ ^[0-9]+$ ]] && [[ "$choice" -ge 1 ]] && [[ "$choice" -lt "$num" ]]; then
        local idx=$((choice - 1))
        WIZARD_STATE[can_adapter]="${adapter_names[$idx]}"
        WIZARD_STATE[can_adapter_id]="${adapters[$idx]}"
        save_state
        
        echo -e "${GREEN}Selected: ${adapter_names[$idx]}${NC}"
        
        # Show adapter-specific instructions
        if [[ "${adapters[$idx]}" != "usb-can-bridge" ]]; then
            local adapter_file="${TEMPLATES_DIR}/can-adapters/${adapters[$idx]}.json"
            if [[ -f "$adapter_file" ]]; then
                echo ""
                echo -e "${BWHITE}Setup instructions:${NC}"
                python3 -c "
import json
data = json.load(open('$adapter_file'))
if 'setup_instructions' in data:
    for i, step in enumerate(data['setup_instructions'], 1):
        print(f'  {step}')
" 2>/dev/null
            fi
        else
            echo ""
            echo -e "${BWHITE}USB-CAN Bridge Mode:${NC}"
            echo -e "  Your mainboard acts as the CAN adapter."
            echo -e "  Flash Klipper with USB-CAN Bridge mode enabled."
            echo -e "  See: https://canbus.esoterical.online/"
        fi
        
        wait_for_key
    fi
}

# CAN interface setup submenu
menu_can_interface_setup() {
    clear_screen
    print_header "Setup CAN Interface"
    
    print_box_line "This will create /etc/network/interfaces.d/can0"
    print_box_line "to automatically bring up the CAN interface on boot."
    print_empty_line
    print_separator
    
    print_box_line "Select CAN bitrate:"
    print_empty_line
    print_menu_item "1" "" "1000000 bps (1 Mbit - recommended)"
    print_menu_item "2" "" "500000 bps (500 Kbit)"
    print_menu_item "3" "" "250000 bps (250 Kbit)"
    print_separator
    print_action_item "B" "Back"
    print_footer

    read -r -p "Select bitrate: " choice

    local bitrate
    case "$choice" in
        1) bitrate=1000000 ;;
        2) bitrate=500000 ;;
        3) bitrate=250000 ;;
        [bB]) return ;;
        *) bitrate=1000000 ;;
    esac
    
    if setup_can_interface "can0" "$bitrate"; then
        echo ""
        echo -e "${GREEN}CAN interface configuration created.${NC}"
        echo -e "${YELLOW}You may need to reboot or run 'sudo ifup can0' to activate.${NC}"
    fi
    
    wait_for_key
}

# Bring up CAN interface manually
menu_can_bring_up() {
    clear_screen
    print_header "Bring Up CAN Interface"
    
    print_box_line "Select CAN bitrate:"
    print_empty_line
    print_menu_item "1" "" "1000000 bps (1 Mbit)"
    print_menu_item "2" "" "500000 bps (500 Kbit)"
    print_separator
    print_action_item "B" "Back"
    print_footer

    read -r -p "Select bitrate: " choice

    local bitrate
    case "$choice" in
        1) bitrate=1000000 ;;
        2) bitrate=500000 ;;
        [bB]) return ;;
        *) bitrate=1000000 ;;
    esac

    bring_up_can_interface "can0" "$bitrate"
    
    wait_for_key
}

# Check CAN requirements
menu_can_check() {
    clear_screen
    print_header "CAN Requirements Check"
    
    print_box_line "Checking CAN bus requirements..."
    print_empty_line
    
    local issues
    issues=$(check_can_requirements "can0")
    
    if [[ -z "$issues" ]]; then
        print_box_line "${GREEN}✓ All CAN requirements met!${NC}"
        print_empty_line
        print_box_line "Interface: can0"
        print_box_line "Bitrate: $(get_can_bitrate can0) bps"
        print_box_line "Status: UP"
    else
        print_box_line "${RED}Issues found:${NC}"
        while IFS= read -r issue; do
            print_box_line "${YELLOW}• ${issue}${NC}"
        done <<< "$issues"
    fi
    
    print_footer
    wait_for_key
}

# ═══════════════════════════════════════════════════════════════════════════════
# KATAPULT (CanBoot) FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

# Check if Katapult is installed
is_katapult_installed() {
    [[ -d "${HOME}/katapult" ]] || [[ -d "${HOME}/CanBoot" ]]
}

# Install Katapult bootloader tools
install_katapult() {
    echo -e "${CYAN}Installing Katapult...${NC}"
    
    if is_katapult_installed; then
        echo -e "${YELLOW}Katapult is already installed.${NC}"
        return 0
    fi
    
    # Temporarily disable errexit for clone
    set +e
    
    if git clone https://github.com/Arksine/katapult.git "${HOME}/katapult" 2>&1; then
        echo -e "${GREEN}Katapult installed successfully!${NC}"
        set -e
        return 0
    else
        echo -e "${RED}Failed to clone Katapult repository.${NC}"
        set -e
        return 1
    fi
}

# Add Katapult to Moonraker update manager
add_katapult_update_manager() {
    local moonraker_conf="${HOME}/printer_data/config/moonraker.conf"
    
    if [[ ! -f "$moonraker_conf" ]]; then
        echo -e "${YELLOW}moonraker.conf not found at ${moonraker_conf}${NC}"
        return 1
    fi
    
    # Check if entry already exists
    if grep -q "\[update_manager katapult\]" "$moonraker_conf" 2>/dev/null; then
        echo -e "${YELLOW}Katapult update manager entry already exists.${NC}"
        return 0
    fi
    
    local katapult_entry="
[update_manager katapult]
type: git_repo
path: ~/katapult
origin: https://github.com/Arksine/katapult.git
is_system_service: False
"
    
    echo "$katapult_entry" | sudo tee -a "$moonraker_conf" > /dev/null
    echo -e "${GREEN}Added Katapult to Moonraker update manager.${NC}"
}

# Katapult installation menu
menu_katapult_install() {
    clear_screen
    print_header "Katapult Installation"
    
    print_box_line "Katapult (formerly CanBoot) is a bootloader that allows"
    print_box_line "updating Klipper firmware over the CAN bus without"
    print_box_line "physically connecting USB cables."
    print_empty_line
    print_box_line "${YELLOW}Note: Katapult is optional but highly recommended${NC}"
    print_box_line "${YELLOW}for CAN-based toolhead boards.${NC}"
    print_empty_line
    
    if is_katapult_installed; then
        print_box_line "Status: ${GREEN}Installed${NC}"
    else
        print_box_line "Status: ${RED}Not installed${NC}"
    fi
    
    print_separator
    
    if is_katapult_installed; then
        print_menu_item "1" "" "Update Katapult (git pull)"
        print_menu_item "2" "" "Add to Moonraker update manager"
    else
        print_menu_item "1" "" "Install Katapult"
    fi
    print_empty_line
    print_action_item "B" "Back"
    
    print_footer
    
    read -r -p "Select option: " choice
    
    if is_katapult_installed; then
        case "$choice" in
            1)
                echo -e "${CYAN}Updating Katapult...${NC}"
                cd "${HOME}/katapult" 2>/dev/null || cd "${HOME}/CanBoot"
                git pull
                echo -e "${GREEN}Katapult updated!${NC}"
                wait_for_key
                ;;
            2)
                add_katapult_update_manager
                wait_for_key
                ;;
        esac
    else
        case "$choice" in
            1)
                if install_katapult; then
                    echo ""
                    if confirm "Add Katapult to Moonraker update manager?"; then
                        add_katapult_update_manager
                    fi
                fi
                wait_for_key
                ;;
        esac
    fi
}

# ═══════════════════════════════════════════════════════════════════════════════
# CAN DIAGNOSTICS
# ═══════════════════════════════════════════════════════════════════════════════

# Comprehensive CAN bus diagnostics
diagnose_can_issues() {
    clear_screen
    print_header "CAN Bus Diagnostics"
    
    print_box_line "Running diagnostics..."
    print_empty_line
    
    local has_issues=0
    
    # Check 1: CAN interface exists
    print_box_line "${BWHITE}1. CAN Interface (can0):${NC}"
    if ip link show can0 &>/dev/null; then
        print_box_line "   ${GREEN}✓ Interface exists${NC}"
        
        # Check if UP
        if ip link show can0 2>/dev/null | grep -q "state UP"; then
            print_box_line "   ${GREEN}✓ Interface is UP${NC}"
            local bitrate
            bitrate=$(get_can_bitrate can0)
            print_box_line "   ${GREEN}✓ Bitrate: ${bitrate} bps${NC}"
        else
            print_box_line "   ${RED}✗ Interface is DOWN${NC}"
            print_box_line "   ${YELLOW}  Fix: sudo ip link set can0 up type can bitrate 1000000${NC}"
            has_issues=1
        fi
    else
        print_box_line "   ${RED}✗ Interface does not exist${NC}"
        print_box_line "   ${YELLOW}  Check: Is your CAN adapter connected?${NC}"
        print_box_line "   ${YELLOW}  Fix: Create /etc/network/interfaces.d/can0${NC}"
        has_issues=1
    fi
    
    print_empty_line
    
    # Check 2: CAN adapter
    print_box_line "${BWHITE}2. CAN Adapter Detection:${NC}"
    local usb_can_devices
    usb_can_devices=$(lsusb 2>/dev/null | grep -iE "can|1d50:606f|gs_usb" || true)
    if [[ -n "$usb_can_devices" ]]; then
        print_box_line "   ${GREEN}✓ USB CAN device found:${NC}"
        while IFS= read -r device; do
            print_box_line "     $device"
        done <<< "$usb_can_devices"
    else
        print_box_line "   ${YELLOW}? No obvious USB CAN adapter detected${NC}"
        print_box_line "   ${YELLOW}  (May be using USB-CAN bridge mode on mainboard)${NC}"
    fi
    
    print_empty_line
    
    # Check 3: Klipper query script
    print_box_line "${BWHITE}3. Klipper CAN Query Script:${NC}"
    if [[ -f "${HOME}/klipper/scripts/canbus_query.py" ]]; then
        print_box_line "   ${GREEN}✓ canbus_query.py found${NC}"
    else
        print_box_line "   ${RED}✗ canbus_query.py not found${NC}"
        print_box_line "   ${YELLOW}  Check: Is Klipper installed?${NC}"
        has_issues=1
    fi
    
    print_empty_line
    
    # Check 4: Try to find CAN devices
    print_box_line "${BWHITE}4. CAN Device Discovery:${NC}"
    if check_can_interface can0; then
        local uuids
        uuids=$(detect_can_mcus)
        if [[ -n "$uuids" ]]; then
            print_box_line "   ${GREEN}✓ CAN devices found:${NC}"
            while IFS= read -r uuid; do
                print_box_line "     ${BWHITE}${uuid}${NC}"
            done <<< "$uuids"
        else
            print_box_line "   ${YELLOW}? No CAN devices responding${NC}"
            print_box_line "   ${YELLOW}  Check:${NC}"
            print_box_line "   ${YELLOW}  - Is the toolboard powered?${NC}"
            print_box_line "   ${YELLOW}  - Is Klipper/Katapult flashed on it?${NC}"
            print_box_line "   ${YELLOW}  - Are CAN H/L wires connected correctly?${NC}"
            print_box_line "   ${YELLOW}  - Is there a 120Ω termination resistor?${NC}"
            has_issues=1
        fi
    else
        print_box_line "   ${YELLOW}? Cannot query - can0 not ready${NC}"
        has_issues=1
    fi
    
    print_empty_line
    
    # Check 5: Klipper service
    print_box_line "${BWHITE}5. Klipper Service:${NC}"
    if systemctl is-active --quiet klipper 2>/dev/null; then
        print_box_line "   ${GREEN}✓ Klipper service is running${NC}"
        print_box_line "   ${YELLOW}  Note: Stop Klipper to flash firmware over CAN${NC}"
    else
        print_box_line "   ${YELLOW}? Klipper service is not running${NC}"
        print_box_line "   ${YELLOW}  (OK for flashing, needed for operation)${NC}"
    fi
    
    print_separator
    
    if [[ $has_issues -eq 0 ]]; then
        print_box_line "${GREEN}All checks passed!${NC}"
    else
        print_box_line "${YELLOW}Some issues found. See suggestions above.${NC}"
        print_empty_line
        print_box_line "${BWHITE}Helpful resources:${NC}"
        print_box_line "• https://canbus.esoterical.online/"
        print_box_line "• Voron Discord #can-and-usb_toolhead_boards"
    fi
    
    print_footer
}

# Interactive menu to select MCU serial
select_mcu_serial() {
    local role="$1"  # "main" or "toolboard"
    local connection_type="${2:-usb}"  # "usb" or "can"
    
    clear_screen
    print_header "Select ${role^} MCU"
    
    if [[ "$connection_type" == "can" ]]; then
        print_box_line "Scanning CAN bus for devices..."
        print_empty_line
        
        local -a uuids
        mapfile -t uuids < <(detect_can_mcus)
        
        if [[ ${#uuids[@]} -eq 0 ]]; then
            print_box_line "${YELLOW}No CAN devices found.${NC}"
            print_box_line "Make sure:"
            print_box_line "- CAN interface is up (can0)"
            print_box_line "- Device is powered and connected"
            print_box_line "- Device has Klipper/Katapult firmware"
            print_footer
            wait_for_key
            return 1
        fi
        
        local num=1
        for uuid in "${uuids[@]}"; do
            print_box_line "${BWHITE}${num})${NC} ${uuid}"
            ((num++))
        done
        
        print_separator
        print_action_item "M" "Enter manually"
        print_action_item "B" "Back"
        print_footer
        
        echo -en "${BYELLOW}Select device${NC}: "
        read -r choice
        
        if [[ "$choice" == [mM] ]]; then
            echo -en "${BYELLOW}Enter canbus_uuid${NC}: "
            read -r manual_uuid
            if [[ "$role" == "main" ]]; then
                WIZARD_STATE[mcu_canbus_uuid]="$manual_uuid"
            else
                WIZARD_STATE[toolboard_canbus_uuid]="$manual_uuid"
            fi
        elif [[ "$choice" == [bB] ]]; then
            return 1
        else
            local idx=$((choice - 1))
            if [[ $idx -ge 0 && $idx -lt ${#uuids[@]} ]]; then
                if [[ "$role" == "main" ]]; then
                    WIZARD_STATE[mcu_canbus_uuid]="${uuids[$idx]}"
                else
                    WIZARD_STATE[toolboard_canbus_uuid]="${uuids[$idx]}"
                fi
            fi
        fi
    else
        # USB device selection
        print_box_line "Scanning USB for Klipper MCUs..."
        print_empty_line
        
        local -a devices
        mapfile -t devices < <(detect_usb_mcus)
        
        if [[ ${#devices[@]} -eq 0 ]]; then
            print_box_line "${YELLOW}No Klipper USB devices found.${NC}"
            print_box_line "Make sure:"
            print_box_line "- MCU is connected via USB"
            print_box_line "- MCU has Klipper firmware flashed"
            print_footer
            wait_for_key
            return 1
        fi
        
        local num=1
        for device in "${devices[@]}"; do
            local desc=$(get_mcu_description "$device")
            local basename=$(basename "$device")
            print_box_line "${BWHITE}${num})${NC} ${CYAN}${desc}${NC}"
            print_box_line "    ${WHITE}${basename}${NC}"
            ((num++))
        done
        
        print_separator
        print_action_item "M" "Enter path manually"
        print_action_item "B" "Back"
        print_footer
        
        echo -en "${BYELLOW}Select device${NC}: "
        read -r choice
        
        if [[ "$choice" == [mM] ]]; then
            echo -en "${BYELLOW}Enter serial path${NC}: "
            read -r manual_path
            if [[ "$role" == "main" ]]; then
                WIZARD_STATE[mcu_serial]="$manual_path"
            else
                WIZARD_STATE[toolboard_serial]="$manual_path"
            fi
        elif [[ "$choice" == [bB] ]]; then
            return 1
        else
            local idx=$((choice - 1))
            if [[ $idx -ge 0 && $idx -lt ${#devices[@]} ]]; then
                if [[ "$role" == "main" ]]; then
                    WIZARD_STATE[mcu_serial]="${devices[$idx]}"
                else
                    WIZARD_STATE[toolboard_serial]="${devices[$idx]}"
                fi
            fi
        fi
    fi
    
    return 0
}

# ═══════════════════════════════════════════════════════════════════════════════
# STATE MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════════

# Wizard state variables
declare -A WIZARD_STATE
declare -A HARDWARE_STATE

# Hardware state file (from Python script)
HARDWARE_STATE_FILE="${REPO_ROOT}/.hardware-state.json"

# Load hardware state from JSON (created by setup-hardware.py)
load_hardware_state() {
    # Clear existing hardware state
    HARDWARE_STATE=()

    if [[ -f "${HARDWARE_STATE_FILE}" ]]; then
        # Parse JSON using Python (guaranteed to be available)
        # Note: Use 'or' to handle None values properly
        eval "$(python3 -c "
import json
try:
    with open('${HARDWARE_STATE_FILE}') as f:
        data = json.load(f)

    # Load board/toolboard info into WIZARD_STATE
    board_id = data.get('board_id') or ''
    board_name = data.get('board_name') or ''
    toolboard_id = data.get('toolboard_id') or ''
    toolboard_name = data.get('toolboard_name') or ''
    print(f\"WIZARD_STATE[board]='{board_id}'\")
    print(f\"WIZARD_STATE[board_name]='{board_name}'\")
    print(f\"WIZARD_STATE[toolboard]='{toolboard_id}'\")
    print(f\"WIZARD_STATE[toolboard_name]='{toolboard_name}'\")

    # Load port_assignments into HARDWARE_STATE
    port_assignments = data.get('port_assignments', {})
    for key, value in port_assignments.items():
        print(f\"HARDWARE_STATE[{key}]='{value}'\")

    # Load toolboard_assignments into HARDWARE_STATE with toolboard_ prefix
    toolboard_assignments = data.get('toolboard_assignments', {})
    for key, value in toolboard_assignments.items():
        print(f\"HARDWARE_STATE[toolboard_{key}]='{value}'\")

    # Load MCU serial IDs into WIZARD_STATE
    mcu_serial = data.get('mcu_serial') or ''
    toolboard_serial = data.get('toolboard_serial') or ''
    toolboard_canbus_uuid = data.get('toolboard_canbus_uuid') or ''
    probe_serial = data.get('probe_serial') or ''
    print(f\"WIZARD_STATE[mcu_serial]='{mcu_serial}'\")
    print(f\"WIZARD_STATE[toolboard_serial]='{toolboard_serial}'\")
    print(f\"WIZARD_STATE[toolboard_canbus_uuid]='{toolboard_canbus_uuid}'\")
    print(f\"WIZARD_STATE[probe_serial]='{probe_serial}'\")

except Exception as e:
    pass
" 2>/dev/null)"
    fi
}

# Get port assignment status for display
get_port_status() {
    if [[ ! -f "${HARDWARE_STATE_FILE}" ]]; then
        echo "not configured"
        return
    fi
    
    local count
    count=$(python3 -c "
import json
try:
    with open('${HARDWARE_STATE_FILE}') as f:
        data = json.load(f)
    assignments = data.get('port_assignments', {})
    print(len(assignments))
except:
    print(0)
" 2>/dev/null)
    
    if [[ "$count" -gt 0 ]]; then
        echo "${count} ports assigned"
    else
        echo "not configured"
    fi
}

init_state() {
    WIZARD_STATE=(
        [board]=""
        [board_name]=""
        [toolboard]=""
        [toolboard_name]=""
        [kinematics]=""
        [z_stepper_count]=""
        [leveling_method]=""
        [stepper_driver]=""
        [driver_X]=""
        [driver_X1]=""
        [driver_Y]=""
        [driver_Y1]=""
        [driver_Z]=""
        [driver_Z1]=""
        [driver_Z2]=""
        [driver_Z3]=""
        [driver_E]=""
        [bed_size_x]=""
        [bed_size_y]=""
        [bed_size_z]=""
        [extruder_type]=""
        [hotend_thermistor]=""
        [hotend_pullup_resistor]=""
        [bed_thermistor]=""
        [bed_pullup_resistor]=""
        [probe_type]=""
        [probe_mode]=""              # "proximity" or "touch" for eddy current probes
        [beacon_revision]=""         # "revd" or "revh" for Beacon hardware version
        [z_home_x]=""                # X position for Z homing (safe_z_home)
        [z_home_y]=""                # Y position for Z homing (safe_z_home)
        [mesh_margin]=""             # Edge margin for bed mesh (mm from edges)
        [has_filament_sensor]=""
        [filament_sensor_pin]=""
        [has_chamber_sensor]=""
        [chamber_sensor_type]=""
        [chamber_sensor_pin]=""
        [position_endstop_x]=""
        [position_endstop_y]=""
        [position_endstop_z]=""
        [position_min_x]=""
        [position_min_y]=""
        [home_x]=""
        [home_y]=""
        # Fan configuration
        [fan_part_cooling]=""
        [fan_part_cooling_multipin]=""
        [fan_hotend]=""
        [fan_hotend_multipin]=""
        [fan_controller]=""
        [fan_controller_multipin]=""
        [fan_exhaust]=""
        [fan_exhaust_multipin]=""
        [fan_chamber]=""
        [fan_chamber_multipin]=""
        [fan_chamber_type]=""
        [fan_chamber_sensor_type]=""
        [fan_chamber_sensor_pin]=""
        [fan_chamber_target_temp]=""
        [fan_rscs]=""
        [fan_rscs_multipin]=""
        [fan_radiator]=""
        [fan_radiator_multipin]=""
        # Fan advanced options (per-fan: pc=part cooling, hf=hotend, cf=controller, ex=exhaust, ch=chamber, rs=rscs, rd=radiator)
        [fan_pc_max_power]=""
        [fan_pc_cycle_time]=""
        [fan_pc_hardware_pwm]=""
        [fan_pc_shutdown_speed]=""
        [fan_pc_kick_start]=""
        [fan_hf_max_power]=""
        [fan_hf_cycle_time]=""
        [fan_hf_hardware_pwm]=""
        [fan_hf_shutdown_speed]=""
        [fan_hf_kick_start]=""
        [fan_cf_max_power]=""
        [fan_cf_cycle_time]=""
        [fan_cf_hardware_pwm]=""
        [fan_cf_shutdown_speed]=""
        [fan_cf_kick_start]=""
        [fan_ex_max_power]=""
        [fan_ex_cycle_time]=""
        [fan_ex_hardware_pwm]=""
        [fan_ex_shutdown_speed]=""
        [fan_ex_kick_start]=""
        [fan_ch_max_power]=""
        [fan_ch_cycle_time]=""
        [fan_ch_hardware_pwm]=""
        [fan_ch_shutdown_speed]=""
        [fan_ch_kick_start]=""
        [fan_rs_max_power]=""
        [fan_rs_cycle_time]=""
        [fan_rs_hardware_pwm]=""
        [fan_rs_shutdown_speed]=""
        [fan_rs_kick_start]=""
        [fan_rd_max_power]=""
        [fan_rd_cycle_time]=""
        [fan_rd_hardware_pwm]=""
        [fan_rd_shutdown_speed]=""
        [fan_rd_kick_start]=""
        # Lighting configuration
        [lighting_type]=""
        [lighting_pin]=""
        [lighting_count]=""
        [lighting_color_order]=""
        # Stepper configuration - per axis
        [stepper_x_step_angle]=""
        [stepper_x_microsteps]=""
        [stepper_x_rotation_distance]=""
        [stepper_y_step_angle]=""
        [stepper_y_microsteps]=""
        [stepper_y_rotation_distance]=""
        [stepper_z_step_angle]=""
        [stepper_z_microsteps]=""
        [stepper_z_rotation_distance]=""
        [stepper_e_step_angle]=""
        [stepper_e_microsteps]=""
        [stepper_e_rotation_distance]=""
    )
}

save_state() {
    echo "# gschpoozi wizard state - $(date)" > "${STATE_FILE}"
    for key in "${!WIZARD_STATE[@]}"; do
        echo "${key}=${WIZARD_STATE[$key]}" >> "${STATE_FILE}"
    done
}

load_state() {
    if [[ -f "${STATE_FILE}" ]]; then
        while IFS='=' read -r key value; do
            [[ "$key" =~ ^#.*$ ]] && continue
            [[ -z "$key" ]] && continue
            WIZARD_STATE[$key]="$value"
        done < "${STATE_FILE}"
        return 0
    fi
    return 1
}

get_step_status() {
    local step="$1"
    
    case "$step" in
        board)
            [[ -n "${WIZARD_STATE[board]}" ]] && echo "done" || echo ""
            ;;
        toolboard)
            [[ -n "${WIZARD_STATE[toolboard]}" ]] && echo "done" || echo ""
            ;;
        ports)
            # Check if hardware state file has port assignments
            if [[ -f "${HARDWARE_STATE_FILE}" ]]; then
                local count
                count=$(python3 -c "
import json
try:
    with open('${HARDWARE_STATE_FILE}') as f:
        data = json.load(f)
    print(len(data.get('port_assignments', {})))
except:
    print(0)
" 2>/dev/null)
                [[ "$count" -gt 0 ]] && echo "done" || echo ""
            else
                echo ""
            fi
            ;;
        kinematics)
            [[ -n "${WIZARD_STATE[kinematics]}" && -n "${WIZARD_STATE[z_stepper_count]}" ]] && echo "done" || echo ""
            ;;
        steppers)
            # Check if at least X driver is set
            [[ -n "${WIZARD_STATE[driver_X]}" || -n "${WIZARD_STATE[stepper_driver]}" ]] && echo "done" || echo ""
            ;;
        extruder)
            [[ -n "${WIZARD_STATE[extruder_type]}" ]] && echo "done" || echo ""
            ;;
        hotend)
            # Hotend is complete if thermistor is set AND heater port is assigned (mainboard or toolboard)
            local has_thermistor="${WIZARD_STATE[hotend_thermistor]}"
            local has_heater="${HARDWARE_STATE[heater_extruder]}${HARDWARE_STATE[toolboard_heater_extruder]}"
            [[ -n "$has_thermistor" && -n "$has_heater" ]] && echo "done" || echo ""
            ;;
        bed)
            [[ -n "${WIZARD_STATE[bed_size_x]}" ]] && echo "done" || echo ""
            ;;
        probe)
            [[ -n "${WIZARD_STATE[probe_type]}" ]] && echo "done" || echo ""
            ;;
        endstops)
            # Endstops complete when X/Y homing positions AND Z probe/endstop type are set
            local has_x="${WIZARD_STATE[home_x]}"
            local has_y="${WIZARD_STATE[home_y]}"
            local has_z="${WIZARD_STATE[probe_type]}"
            [[ -n "$has_x" && -n "$has_y" && -n "$has_z" ]] && echo "done" || echo ""
            ;;
        extras)
            # Check all extras options
            [[ "${WIZARD_STATE[has_filament_sensor]}" == "yes" || \
               "${WIZARD_STATE[has_chamber_sensor]}" == "yes" || \
               "${WIZARD_STATE[has_klipperscreen]}" == "yes" || \
               "${WIZARD_STATE[has_lcd_display]}" == "yes" || \
               "${WIZARD_STATE[has_leds]}" == "yes" || \
               "${WIZARD_STATE[has_caselight]}" == "yes" ]] && echo "done" || echo ""
            ;;
        macros)
            echo "done"  # Default macros always included
            ;;
    esac
}

# ═══════════════════════════════════════════════════════════════════════════════
# SOURCE INSTALLATION LIBRARY
# ═══════════════════════════════════════════════════════════════════════════════

# Source the Klipper installation library (provides do_install_* functions)
if [[ -f "${LIB_DIR}/klipper-install.sh" ]]; then
    source "${LIB_DIR}/klipper-install.sh"
fi

# ═══════════════════════════════════════════════════════════════════════════════
# KLIPPER COMPONENT DETECTION
# ═══════════════════════════════════════════════════════════════════════════════

# Check if Klipper is installed
is_klipper_installed() {
    [[ -d "${HOME}/klipper" ]] && [[ -d "${HOME}/klippy-env" ]]
}

# Check if Moonraker is installed
is_moonraker_installed() {
    [[ -d "${HOME}/moonraker" ]] && [[ -d "${HOME}/moonraker-env" ]]
}

# Check if Mainsail is installed
is_mainsail_installed() {
    [[ -d "${HOME}/mainsail" ]] || [[ -d "/home/${USER}/mainsail" ]]
}

# Check if Fluidd is installed
is_fluidd_installed() {
    [[ -d "${HOME}/fluidd" ]] || [[ -d "/home/${USER}/fluidd" ]]
}

# Check if Crowsnest is installed
is_crowsnest_installed() {
    [[ -d "${HOME}/crowsnest" ]]
}

# Check if Sonar is installed
is_sonar_installed() {
    [[ -d "${HOME}/sonar" ]]
}

# Check if Timelapse is installed (properly with symlink)
is_timelapse_installed() {
    [[ -d "${HOME}/moonraker-timelapse" ]] && [[ -L "${HOME}/moonraker/moonraker/components/timelapse.py" ]]
}

# Get Klipper version if installed
get_klipper_version() {
    if is_klipper_installed; then
        cd "${HOME}/klipper" 2>/dev/null && git describe --tags --always 2>/dev/null || echo "unknown"
    else
        echo "not installed"
    fi
}

# Get Moonraker version if installed
get_moonraker_version() {
    if is_moonraker_installed; then
        cd "${HOME}/moonraker" 2>/dev/null && git describe --tags --always 2>/dev/null || echo "unknown"
    else
        echo "not installed"
    fi
}

# ═══════════════════════════════════════════════════════════════════════════════
# STUB INSTALLATION FUNCTIONS (Phase 2 implementation)
# ═══════════════════════════════════════════════════════════════════════════════

install_klipper() {
    if type do_install_klipper &>/dev/null; then
        do_install_klipper
    else
        clear_screen
        print_header "Install Klipper"
        print_empty_line
        print_box_line "${RED}Installation library not found!${NC}"
        print_box_line "Please ensure scripts/lib/klipper-install.sh exists."
        print_empty_line
        print_footer
        wait_for_key
    fi
}

install_moonraker() {
    if type do_install_moonraker &>/dev/null; then
        do_install_moonraker
    else
        clear_screen
        print_header "Install Moonraker"
        print_empty_line
        print_box_line "${RED}Installation library not found!${NC}"
        print_box_line "Please ensure scripts/lib/klipper-install.sh exists."
        print_empty_line
        print_footer
        wait_for_key
    fi
}

install_mainsail() {
    if type do_install_mainsail &>/dev/null; then
        do_install_mainsail
    else
        clear_screen
        print_header "Install Mainsail"
        print_empty_line
        print_box_line "${RED}Installation library not found!${NC}"
        print_box_line "Please ensure scripts/lib/klipper-install.sh exists."
        print_empty_line
        print_footer
        wait_for_key
    fi
}

install_fluidd() {
    if type do_install_fluidd &>/dev/null; then
        do_install_fluidd
    else
        clear_screen
        print_header "Install Fluidd"
        print_empty_line
        print_box_line "${RED}Installation library not found!${NC}"
        print_box_line "Please ensure scripts/lib/klipper-install.sh exists."
        print_empty_line
        print_footer
        wait_for_key
    fi
}

install_crowsnest() {
    if type do_install_crowsnest &>/dev/null; then
        do_install_crowsnest
    else
        clear_screen
        print_header "Install Crowsnest"
        print_empty_line
        print_box_line "${RED}Installation library not found!${NC}"
        print_box_line "Please ensure scripts/lib/klipper-install.sh exists."
        print_empty_line
        print_footer
        wait_for_key
    fi
}

install_sonar() {
    if type do_install_sonar &>/dev/null; then
        do_install_sonar
    else
        clear_screen
        print_header "Install Sonar"
        print_empty_line
        print_box_line "${RED}Installation library not found!${NC}"
        print_box_line "Please ensure scripts/lib/klipper-install.sh exists."
        print_empty_line
        print_footer
        wait_for_key
    fi
}

install_timelapse() {
    if type do_install_timelapse &>/dev/null; then
        do_install_timelapse
    else
        clear_screen
        print_header "Install Timelapse"
        print_empty_line
        print_box_line "${RED}Installation library not found!${NC}"
        print_box_line "Please ensure scripts/lib/klipper-install.sh exists."
        print_empty_line
        print_footer
        wait_for_key
    fi
}

# ═══════════════════════════════════════════════════════════════════════════════
# TOP-LEVEL MENU
# ═══════════════════════════════════════════════════════════════════════════════

show_top_menu() {
    clear_screen
    print_header "gschpoozi"

    print_box_line "${WHITE}Klipper Configuration Generator${NC}"
    print_empty_line

    # Klipper Setup status
    local klipper_status=""
    local klipper_info=""
    if is_klipper_installed && is_moonraker_installed; then
        klipper_status="done"
        local web_ui=""
        is_mainsail_installed && web_ui="Mainsail"
        is_fluidd_installed && [[ -n "$web_ui" ]] && web_ui="${web_ui}+Fluidd" || { is_fluidd_installed && web_ui="Fluidd"; }
        [[ -z "$web_ui" ]] && web_ui="no web UI"
        klipper_info="Klipper + Moonraker + ${web_ui}"
    elif is_klipper_installed; then
        klipper_status="partial"
        klipper_info="Klipper only (Moonraker missing)"
    else
        klipper_info="Not installed"
    fi
    print_menu_item "1" "$klipper_status" "Klipper Setup" "${klipper_info}"
    
    # Machine Setup status
    local machine_status=""
    local machine_info=""
    if [[ -n "${WIZARD_STATE[board]}" ]]; then
        machine_status="partial"
        machine_info="${WIZARD_STATE[board_name]:-in progress}"
    else
        machine_info="Configure your 3D printer"
    fi
    print_menu_item "2" "$machine_status" "Machine Setup" "${machine_info}"
    
    print_separator
    print_action_item "Q" "Quit"
    print_footer
    
    echo -en "${BYELLOW}Select option${NC}: "
    read -r choice
    
    case "$choice" in
        1) show_klipper_setup_menu ;;
        2) show_machine_setup_menu ;;
        [qQ]) exit_wizard ;;
        *) ;;
    esac
}

# ═══════════════════════════════════════════════════════════════════════════════
# KLIPPER SETUP MENU
# ═══════════════════════════════════════════════════════════════════════════════

show_klipper_setup_menu() {
    while true; do
        clear_screen
        print_header "Klipper Setup"
        
        print_box_line "${BWHITE}CORE COMPONENTS${NC}"
        
        # Klipper
        local klipper_status=""
        local klipper_info=""
        if is_klipper_installed; then
            klipper_status="done"
            klipper_info="$(get_klipper_version)"
        else
            klipper_info="Not installed"
        fi
        print_menu_item "1" "$klipper_status" "Klipper" "${klipper_info}"
        
        # Moonraker
        local moonraker_status=""
        local moonraker_info=""
        if is_moonraker_installed; then
            moonraker_status="done"
            moonraker_info="$(get_moonraker_version)"
        else
            moonraker_info="Not installed"
        fi
        print_menu_item "2" "$moonraker_status" "Moonraker" "${moonraker_info}"
        
        print_empty_line
        print_box_line "${BWHITE}WEB INTERFACE${NC} ${WHITE}(choose one)${NC}"
        
        # Mainsail
        local mainsail_status=""
        local mainsail_info=""
        if is_mainsail_installed; then
            mainsail_status="done"
            local mainsail_port=$(grep -oP 'listen \K[0-9]+' "/etc/nginx/sites-available/mainsail" 2>/dev/null | head -1)
            mainsail_info="Port ${mainsail_port:-80}"
        else
            mainsail_info="Not installed"
        fi
        print_menu_item "3" "$mainsail_status" "Mainsail" "${mainsail_info}"
        
        # Fluidd
        local fluidd_status=""
        local fluidd_info=""
        if is_fluidd_installed; then
            fluidd_status="done"
            local fluidd_port=$(grep -oP 'listen \K[0-9]+' "/etc/nginx/sites-available/fluidd" 2>/dev/null | head -1)
            fluidd_info="Port ${fluidd_port:-80}"
        else
            fluidd_info="Not installed"
        fi
        print_menu_item "4" "$fluidd_status" "Fluidd" "${fluidd_info}"
        
        print_empty_line
        print_box_line "${BWHITE}OPTIONAL${NC}"
        
        # Crowsnest
        local crowsnest_status=""
        local crowsnest_info=""
        if is_crowsnest_installed; then
            crowsnest_status="done"
            crowsnest_info="Installed"
        else
            crowsnest_info="Camera streaming"
        fi
        print_menu_item "5" "$crowsnest_status" "Crowsnest" "${crowsnest_info}"
        
        # Sonar
        local sonar_status=""
        local sonar_info=""
        if is_sonar_installed; then
            sonar_status="done"
            sonar_info="Installed"
        else
            sonar_info="Network keepalive"
        fi
        print_menu_item "6" "$sonar_status" "Sonar" "${sonar_info}"
        
        # Timelapse
        local timelapse_status=""
        local timelapse_info=""
        if is_timelapse_installed; then
            timelapse_status="done"
            timelapse_info="Installed"
        else
            timelapse_info="Print recordings"
        fi
        print_menu_item "7" "$timelapse_status" "Timelapse" "${timelapse_info}"
        
        print_separator
        print_action_item "U" "Update all installed"
        print_action_item "R" "Remove component"
        print_action_item "B" "Back"
        print_footer
        
        echo -en "${BYELLOW}Select option${NC}: "
        read -r choice
        
        case "$choice" in
            1) install_klipper ;;
            2) install_moonraker ;;
            3) install_mainsail ;;
            4) install_fluidd ;;
            5) install_crowsnest ;;
            6) install_sonar ;;
            7) install_timelapse ;;
            [uU]) 
                if type do_update_all &>/dev/null; then
                    do_update_all
                else
                    echo -e "${RED}Update function not available${NC}"
                    wait_for_key
                fi
                ;;
            [rR]) 
                if type show_remove_menu &>/dev/null; then
                    show_remove_menu
                else
                    echo -e "${RED}Remove function not available${NC}"
                    wait_for_key
                fi
                ;;
            [bB]) return ;;
            *) ;;
        esac
    done
}

# ═══════════════════════════════════════════════════════════════════════════════
# MACHINE SETUP MENU (formerly show_main_menu)
# ═══════════════════════════════════════════════════════════════════════════════

show_machine_setup_menu() {
    while true; do
        # Load hardware state from Python script's output
        load_hardware_state

        clear_screen
        print_header "gschpoozi Configuration Wizard"

    # Calculate required motor ports based on selections
    local motor_count=2  # X, Y minimum
    local z_count="${WIZARD_STATE[z_stepper_count]:-1}"
    motor_count=$((motor_count + z_count))

    # Extruder on main board only if no toolboard
    local has_toolboard="no"
    if [[ -n "${WIZARD_STATE[toolboard]}" && "${WIZARD_STATE[toolboard]}" != "none" ]]; then
        has_toolboard="yes"
    else
        motor_count=$((motor_count + 1))  # Add extruder
    fi

    # ─────────────────────────────────────────────────────────────────────────
    # BOARDS
    # ─────────────────────────────────────────────────────────────────────────
    print_box_line "${BWHITE}BOARDS${NC}"

    local board_info="${WIZARD_STATE[board_name]:-not selected}"
    print_menu_item "1" "$(get_step_status board)" "Main Board" "${board_info}"

    print_menu_item "2" "$(get_step_status toolboard)" "Toolhead Board" "${WIZARD_STATE[toolboard_name]:-none}"

    # Misc MCUs (probes with USB/CAN, MMU, expansion boards)
    local misc_mcu_info=""
    local misc_mcu_count=0
    # Count configured misc MCUs
    if [[ -n "${WIZARD_STATE[probe_type]}" && "${WIZARD_STATE[probe_type]}" =~ ^(beacon|cartographer|btt-eddy)$ ]]; then
        misc_mcu_count=$((misc_mcu_count + 1))
        misc_mcu_info="${WIZARD_STATE[probe_type]}"
    fi
    if [[ -n "${WIZARD_STATE[mmu_type]}" && "${WIZARD_STATE[mmu_type]}" != "none" ]]; then
        misc_mcu_count=$((misc_mcu_count + 1))
        [[ -n "$misc_mcu_info" ]] && misc_mcu_info="${misc_mcu_info}, "
        misc_mcu_info="${misc_mcu_info}${WIZARD_STATE[mmu_type]}"
    fi
    [[ -z "$misc_mcu_info" ]] && misc_mcu_info="none configured"
    local misc_status=$([[ $misc_mcu_count -gt 0 ]] && echo "done" || echo "")
    print_menu_item "3" "$misc_status" "Misc MCUs" "${misc_mcu_info}"

    # Show CAN status if any CAN device is configured
    if [[ "${WIZARD_STATE[toolboard_connection]}" == "can" ]] || \
       [[ "${WIZARD_STATE[probe_type]}" =~ ^(beacon|cartographer|btt-eddy)$ && -n "${HARDWARE_STATE[probe_canbus_uuid]}" ]]; then
        local can_status=""
        if check_can_interface can0 2>/dev/null; then
            can_status="${GREEN}UP${NC}"
        else
            can_status="${RED}Not configured${NC}"
        fi
        print_box_line "${BWHITE}C)${NC} [ ] CAN Bus Setup: ${CYAN}${can_status}${NC}"
    fi

    # ─────────────────────────────────────────────────────────────────────────
    # MOTION
    # ─────────────────────────────────────────────────────────────────────────
    print_empty_line
    print_box_line "${BWHITE}MOTION${NC}"

    local kin_display="${WIZARD_STATE[kinematics]:-not set}"
    if [[ -n "${WIZARD_STATE[z_stepper_count]}" ]]; then
        kin_display="${kin_display}, ${WIZARD_STATE[z_stepper_count]}x Z"
        if [[ "${WIZARD_STATE[leveling_method]}" != "none" && -n "${WIZARD_STATE[leveling_method]}" ]]; then
            kin_display="${kin_display} (${WIZARD_STATE[leveling_method]})"
        fi
    fi
    if [[ -n "${WIZARD_STATE[driver_X]}" ]]; then
        kin_display="${kin_display}, ${WIZARD_STATE[driver_X]}"
    fi
    print_menu_item "4" "$(get_step_status kinematics)" "Kinematics" "${kin_display}"

    # ─────────────────────────────────────────────────────────────────────────
    # COMPONENTS
    # ─────────────────────────────────────────────────────────────────────────
    print_empty_line
    print_box_line "${BWHITE}COMPONENTS${NC}"

    # Extruder (motor configuration)
    local extruder_info=""
    if [[ -n "${WIZARD_STATE[extruder_type]}" ]]; then
        extruder_info="${WIZARD_STATE[extruder_type]}"
        [[ -n "${WIZARD_STATE[driver_E]}" ]] && extruder_info="${extruder_info}, ${WIZARD_STATE[driver_E]}"
    else
        extruder_info="not configured"
    fi
    local extruder_status=$([[ -n "${WIZARD_STATE[extruder_type]}" ]] && echo "done" || echo "")
    print_menu_item "5" "$extruder_status" "Extruder" "${extruder_info}"

    # Hotend (thermistor + heater)
    local hotend_info=""
    if [[ -n "${WIZARD_STATE[hotend_thermistor]}" ]]; then
        hotend_info="${WIZARD_STATE[hotend_thermistor]}"
    else
        hotend_info="not configured"
    fi
    print_menu_item "6" "$(get_step_status hotend)" "Hotend" "${hotend_info}"

    # Heated Bed
    local bed_info=""
    if [[ -n "${WIZARD_STATE[bed_size_x]}" ]]; then
        bed_info="${WIZARD_STATE[bed_size_x]}x${WIZARD_STATE[bed_size_y]}mm"
        [[ -n "${WIZARD_STATE[bed_thermistor]}" ]] && bed_info="${bed_info}, ${WIZARD_STATE[bed_thermistor]}"
    else
        bed_info="not configured"
    fi
    print_menu_item "7" "$(get_step_status bed)" "Heated Bed" "${bed_info}"

    # Endstops (including probe as Z endstop)
    local endstop_info=""
    local probe_type="${WIZARD_STATE[probe_type]:-none}"
    if [[ "$probe_type" != "none" && "$probe_type" != "endstop" && -n "$probe_type" ]]; then
        endstop_info="X/Y + ${probe_type}"
    else
        endstop_info="X/Y/Z physical"
    fi
    if [[ -n "${WIZARD_STATE[home_x]}" ]]; then
        endstop_info="${endstop_info} (X:${WIZARD_STATE[home_x]}, Y:${WIZARD_STATE[home_y]})"
    fi
    print_menu_item "8" "$(get_step_status endstops)" "Endstops" "${endstop_info}"

    # Fans - check HARDWARE_STATE port assignments (mainboard or toolboard)
    local fan_count=0
    [[ -n "${HARDWARE_STATE[fan_part_cooling]}" || -n "${HARDWARE_STATE[toolboard_fan_part_cooling]}" ]] && fan_count=$((fan_count + 1))
    [[ -n "${HARDWARE_STATE[fan_hotend]}" || -n "${HARDWARE_STATE[toolboard_fan_hotend]}" ]] && fan_count=$((fan_count + 1))
    [[ -n "${HARDWARE_STATE[fan_controller]}" ]] && fan_count=$((fan_count + 1))
    [[ -n "${HARDWARE_STATE[fan_exhaust]}" ]] && fan_count=$((fan_count + 1))
    [[ -n "${HARDWARE_STATE[fan_chamber]}" ]] && fan_count=$((fan_count + 1))
    [[ -n "${HARDWARE_STATE[fan_rscs]}" ]] && fan_count=$((fan_count + 1))
    [[ -n "${HARDWARE_STATE[fan_radiator]}" ]] && fan_count=$((fan_count + 1))
    local fan_info="${fan_count} configured"
    local fan_status=$([[ $fan_count -gt 0 ]] && echo "done" || echo "")
    print_menu_item "9" "$fan_status" "Fans" "${fan_info}"

    # Lighting
    local light_info="${WIZARD_STATE[lighting_type]:-not configured}"
    local light_status=$([[ -n "${WIZARD_STATE[lighting_type]}" && "${WIZARD_STATE[lighting_type]}" != "none" ]] && echo "done" || echo "")
    print_menu_item "A" "$light_status" "Lighting" "${light_info}"

    # ─────────────────────────────────────────────────────────────────────────
    # EXTRAS
    # ─────────────────────────────────────────────────────────────────────────
    print_empty_line
    print_box_line "${BWHITE}EXTRAS${NC}"
    print_menu_item "E" "$(get_step_status extras)" "Extras" ""
    print_menu_item "M" "$(get_step_status macros)" "Macros" ""

    print_separator
    print_action_item "T" "Stepper Calibration"
    print_action_item "F" "MCU Firmware Update"
    print_action_item "G" "Generate Configuration"
    print_action_item "S" "Save Progress"
    print_action_item "B" "Back to Main Menu"
    print_action_item "Q" "Quit"
    print_footer

    echo -en "${BYELLOW}Select option${NC}: "
    read -r choice

    case "$choice" in
        1) menu_board ;;
        2) menu_toolboard ;;
        3) menu_misc_mcus ;;
        4) menu_kinematics ;;
        5) menu_extruder ;;
        6) menu_hotend ;;
        7) menu_bed ;;
        8) menu_endstops ;;
        9) menu_fans ;;
        [aA]) menu_lighting ;;
        [eE]) menu_extras ;;
        [mM]) menu_macros ;;
        [cC]) menu_can_setup ;;
        [tT]) menu_stepper_calibration ;;
        [fF]) menu_mcu_firmware_update ;;
        [gG]) generate_config ;;
        [sS]) save_state; echo -e "${GREEN}Progress saved!${NC}"; wait_for_key ;;
        [bB]) return ;;
        [qQ]) exit_wizard ;;
        *) ;;
    esac
    done
}

# ═══════════════════════════════════════════════════════════════════════════════
# BOARD SELECTION
# ═══════════════════════════════════════════════════════════════════════════════

menu_board() {
    # Call the Python hardware setup script for board selection
    python3 "${SCRIPT_DIR}/setup-hardware.py" --board
    
    # Reload hardware state
    load_hardware_state
}

# ═══════════════════════════════════════════════════════════════════════════════
# TOOLBOARD SELECTION
# ═══════════════════════════════════════════════════════════════════════════════

menu_toolboard() {
    # Call the Python hardware setup script for toolboard selection
    python3 "${SCRIPT_DIR}/setup-hardware.py" --toolboard
    
    # Reload hardware state
    load_hardware_state
}

# ═══════════════════════════════════════════════════════════════════════════════
# PORT ASSIGNMENT (via Python script)
# ═══════════════════════════════════════════════════════════════════════════════

menu_ports() {
    if [[ -z "${WIZARD_STATE[board]}" ]]; then
        clear_screen
        print_header "Port Assignment"
        print_box_line "${RED}Please select a board first!${NC}"
        print_footer
        wait_for_key
        return
    fi
    
    # Save wizard state before running Python script (so it can read Z count etc)
    save_state
    
    # Call the Python hardware setup script for full port assignment
    python3 "${SCRIPT_DIR}/setup-hardware.py"
    
    # Reload hardware state
    load_hardware_state
}

# ═══════════════════════════════════════════════════════════════════════════════
# KINEMATICS SELECTION
# ═══════════════════════════════════════════════════════════════════════════════

menu_kinematics() {
    while true; do
        clear_screen
        print_header "Motion Configuration"

        # Current configuration summary
        print_box_line "${BWHITE}Current Configuration:${NC}"
        local kin_status=$([[ -n "${WIZARD_STATE[kinematics]}" ]] && echo "done" || echo "")
        print_menu_item "1" "$kin_status" "Kinematics Type" "${WIZARD_STATE[kinematics]:-not set}"

        local z_info="${WIZARD_STATE[z_stepper_count]:-1}x Z"
        [[ -n "${WIZARD_STATE[leveling_method]}" && "${WIZARD_STATE[leveling_method]}" != "none" ]] && z_info="${z_info} (${WIZARD_STATE[leveling_method]})"
        local z_status=$([[ -n "${WIZARD_STATE[z_stepper_count]}" ]] && echo "done" || echo "")
        print_menu_item "2" "$z_status" "Z Configuration" "${z_info}"

        local driver_status=$([[ -n "${WIZARD_STATE[driver_X]}" ]] && echo "done" || echo "")
        print_menu_item "3" "$driver_status" "Stepper Drivers" "${WIZARD_STATE[driver_X]:-not set}"

        # Motor port assignment requires board to be selected
        local motor_status=""
        local motor_info="not configured"
        if [[ -n "${WIZARD_STATE[board]}" ]]; then
            # Check if motor ports are assigned in hardware state JSON
            local has_motors
            has_motors=$(python3 -c "
import json
try:
    with open('${HARDWARE_STATE_FILE}') as f:
        data = json.load(f)
    assignments = data.get('port_assignments', {})
    print('yes' if 'stepper_x' in assignments else 'no')
except:
    print('no')
" 2>/dev/null)
            if [[ "$has_motors" == "yes" ]]; then
                motor_status="done"
                motor_info="configured"
            fi
            print_menu_item "4" "$motor_status" "Motor Port Assignment" "${motor_info}"
        else
            print_box_line "${BWHITE}4)${NC} ${YELLOW}[ ]${NC} Motor Port Assignment: ${YELLOW}select board first${NC}"
        fi

        # Rotation distance configuration - show per-axis status
        local rot_status=""
        local rot_parts=()
        [[ -n "${WIZARD_STATE[stepper_x_rotation_distance]}" ]] && rot_parts+=("X:${WIZARD_STATE[stepper_x_rotation_distance]}")
        [[ -n "${WIZARD_STATE[stepper_y_rotation_distance]}" ]] && rot_parts+=("Y:${WIZARD_STATE[stepper_y_rotation_distance]}")
        [[ -n "${WIZARD_STATE[stepper_z_rotation_distance]}" ]] && rot_parts+=("Z:${WIZARD_STATE[stepper_z_rotation_distance]}")
        [[ -n "${WIZARD_STATE[stepper_e_rotation_distance]}" ]] && rot_parts+=("E:${WIZARD_STATE[stepper_e_rotation_distance]}")
        if [[ ${#rot_parts[@]} -gt 0 ]]; then
            rot_status="done"
            local rot_info=$(IFS=", "; echo "${rot_parts[*]}")
        else
            local rot_info="not configured"
        fi
        print_menu_item "5" "$rot_status" "Rotation Distance" "${rot_info}"

        print_separator
        print_action_item "B" "Back to Main Menu"
        print_footer

        echo -en "${BYELLOW}Select option${NC}: "
        read -r choice

        case "$choice" in
            1) menu_kinematics_type ;;
            2) menu_z_config ;;
            3) menu_steppers ;;
            4)
                if [[ -n "${WIZARD_STATE[board]}" ]]; then
                    menu_motor_ports
                else
                    echo -e "\n${RED}Please select a main board first!${NC}"
                    sleep 1
                fi
                ;;
            5) menu_rotation_distance ;;
            [bB]) return ;;
            *) ;;
        esac
    done
}

menu_kinematics_type() {
    clear_screen
    print_header "Select Kinematics Type"

    print_menu_item "1" "" "CoreXY"
    print_menu_item "2" "" "CoreXY AWD (4 XY motors)"
    print_menu_item "3" "" "Cartesian (bed slinger)"
    print_menu_item "4" "" "CoreXZ"
    print_separator
    print_action_item "B" "Back"
    print_footer

    echo -en "${BYELLOW}Select kinematics${NC}: "
    read -r choice

    case "$choice" in
        1) WIZARD_STATE[kinematics]="corexy" ;;
        2) WIZARD_STATE[kinematics]="corexy-awd" ;;
        3) WIZARD_STATE[kinematics]="cartesian" ;;
        4) WIZARD_STATE[kinematics]="corexz" ;;
        [bB]) return ;;
        *) return ;;
    esac
}

menu_z_config() {
    clear_screen
    print_header "Z Axis Configuration"
    
    print_box_line "${BWHITE}How many Z stepper motors?${NC}"
    print_empty_line
    print_menu_item "1" "" "1 Z motor (single leadscrew)"
    print_menu_item "2" "" "2 Z motors (dual Z, uses Bed Tilt)"
    print_menu_item "3" "" "3 Z motors (triple Z, uses Z Tilt)"
    print_menu_item "4" "" "4 Z motors (Quad Gantry Level)"
    print_separator
    print_action_item "B" "Back"
    print_footer
    
    echo -en "${BYELLOW}Select Z configuration${NC}: "
    read -r choice
    
    case "$choice" in
        1) 
            WIZARD_STATE[z_stepper_count]="1"
            WIZARD_STATE[leveling_method]="none"
            ;;
        2) 
            WIZARD_STATE[z_stepper_count]="2"
            WIZARD_STATE[leveling_method]="bed_tilt"
            echo -e "\n${CYAN}Will configure: Z_TILT_ADJUST (2 points)${NC}"
            sleep 1
            ;;
        3) 
            WIZARD_STATE[z_stepper_count]="3"
            WIZARD_STATE[leveling_method]="z_tilt"
            echo -e "\n${CYAN}Will configure: Z_TILT_ADJUST (3 points)${NC}"
            sleep 1
            ;;
        4) 
            WIZARD_STATE[z_stepper_count]="4"
            WIZARD_STATE[leveling_method]="quad_gantry_level"
            echo -e "\n${CYAN}Will configure: QUAD_GANTRY_LEVEL${NC}"
            sleep 1
            ;;
        [bB]) return ;;
        *) ;;
    esac
    
    # Now ask about homing direction
    menu_homing
}

menu_homing() {
    clear_screen
    print_header "Homing Direction"
    
    print_box_line "${BWHITE}Where are your X/Y endstops located?${NC}"
    print_box_line "(This determines homing direction)"
    print_empty_line
    
    print_menu_item "1" "" "X=MAX, Y=MAX (back-right corner) - Voron style"
    print_menu_item "2" "" "X=MIN, Y=MIN (front-left corner) - Prusa/Ender style"
    print_menu_item "3" "" "X=MIN, Y=MAX (back-left corner)"
    print_menu_item "4" "" "X=MAX, Y=MIN (front-right corner)"
    print_separator
    print_action_item "B" "Back"
    print_footer
    
    echo -en "${BYELLOW}Select endstop location${NC}: "
    read -r choice
    
    case "$choice" in
        1) 
            WIZARD_STATE[home_x]="max"
            WIZARD_STATE[home_y]="max"
            ;;
        2) 
            WIZARD_STATE[home_x]="min"
            WIZARD_STATE[home_y]="min"
            ;;
        3) 
            WIZARD_STATE[home_x]="min"
            WIZARD_STATE[home_y]="max"
            ;;
        4) 
            WIZARD_STATE[home_x]="max"
            WIZARD_STATE[home_y]="min"
            ;;
        [bB]) return ;;
        *) return ;;
    esac
    
    # Now prompt for endstop position coordinates
    menu_endstop_positions
}

menu_endstop_positions() {
    clear_screen
    print_header "Endstop Position Coordinates"
    
    print_box_line "${BWHITE}Enter the physical endstop trigger positions:${NC}"
    print_box_line "(Where the nozzle is when each endstop triggers)"
    print_empty_line
    
    # Calculate defaults based on homing direction
    local default_x default_y default_min_x default_min_y
    if [[ "${WIZARD_STATE[home_x]}" == "max" ]]; then
        default_x="${WIZARD_STATE[bed_size_x]:-300}"
        default_min_x="0"
    else
        default_x="0"
        default_min_x="0"
    fi
    
    if [[ "${WIZARD_STATE[home_y]}" == "max" ]]; then
        default_y="${WIZARD_STATE[bed_size_y]:-300}"
        default_min_y="0"
    else
        default_y="0"
        default_min_y="0"
    fi
    
    print_box_line "${YELLOW}X axis (homing to ${WIZARD_STATE[home_x]:-max}):${NC}"
    echo -en "  " >&2
    WIZARD_STATE[position_endstop_x]=$(prompt_input "X position_endstop (mm)" "${WIZARD_STATE[position_endstop_x]:-$default_x}")
    echo -en "  " >&2
    WIZARD_STATE[position_min_x]=$(prompt_input "X position_min (mm, can be negative)" "${WIZARD_STATE[position_min_x]:-$default_min_x}")
    
    echo ""
    print_box_line "${YELLOW}Y axis (homing to ${WIZARD_STATE[home_y]:-max}):${NC}"
    echo -en "  " >&2
    WIZARD_STATE[position_endstop_y]=$(prompt_input "Y position_endstop (mm)" "${WIZARD_STATE[position_endstop_y]:-$default_y}")
    echo -en "  " >&2
    WIZARD_STATE[position_min_y]=$(prompt_input "Y position_min (mm, can be negative)" "${WIZARD_STATE[position_min_y]:-$default_min_y}")
    
    echo ""
    echo -e "${GREEN}✓${NC} Endstop positions configured"
    sleep 1
}

menu_z_endstop_position() {
    clear_screen
    print_header "Z Endstop Position"
    
    print_box_line "${BWHITE}Enter the Z endstop trigger position:${NC}"
    print_box_line "(Where the nozzle is when the Z endstop triggers)"
    print_empty_line
    print_box_line "${YELLOW}Typical values:${NC}"
    print_box_line "• 0 for bed-mounted endstop at bed level"
    print_box_line "• Positive value if endstop triggers above bed"
    print_empty_line
    
    echo -en "  " >&2
    WIZARD_STATE[position_endstop_z]=$(prompt_input "Z position_endstop (mm)" "${WIZARD_STATE[position_endstop_z]:-0}")
    
    echo ""
    echo -e "${GREEN}✓${NC} Z endstop position configured"
    sleep 1
}

# ═══════════════════════════════════════════════════════════════════════════════
# STEPPER CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

# Get available driver slots based on board
get_board_drivers() {
    local board="${WIZARD_STATE[board]}"
    case "$board" in
        btt-octopus-v1.1|btt-octopus-pro)
            echo "8"  # 8 driver slots
            ;;
        btt-manta-m8p-v2)
            echo "8"  # 8 driver slots
            ;;
        btt-skr-mini-e3-v3)
            echo "4"  # 4 driver slots (X, Y, Z, E)
            ;;
        btt-skr-3)
            echo "5"  # 5 driver slots
            ;;
        creality-v4.2.7)
            echo "4"  # 4 driver slots
            ;;
        mks-robin-nano-v3)
            echo "5"  # 5 driver slots
            ;;
        fysetc-spider-v2.2)
            echo "8"  # 8 driver slots
            ;;
        *)
            echo "4"  # Default
            ;;
    esac
}

# Get required axes based on kinematics and Z count
get_required_axes() {
    local kinematics="${WIZARD_STATE[kinematics]}"
    local z_count="${WIZARD_STATE[z_stepper_count]:-1}"
    local axes=""
    
    # XY axes based on kinematics
    case "$kinematics" in
        corexy)
            axes="X Y"
            ;;
        corexy-awd)
            axes="X X1 Y Y1"  # AWD has dual X and Y
            ;;
        cartesian)
            axes="X Y"
            ;;
        corexz)
            axes="X Y"
            ;;
        *)
            axes="X Y"
            ;;
    esac
    
    # Z axes based on count
    case "$z_count" in
        1) axes="$axes Z" ;;
        2) axes="$axes Z Z1" ;;
        3) axes="$axes Z Z1 Z2" ;;
        4) axes="$axes Z Z1 Z2 Z3" ;;
        *) axes="$axes Z" ;;
    esac
    
    # Always include extruder on main board
    # (Toolboard extruder config will be handled separately if needed)
    axes="$axes E"
    
    echo "$axes"
}

select_driver() {
    local axis="$1"
    local current="${WIZARD_STATE[driver_${axis}]}"
    
    clear_screen
    print_header "Select Driver for ${axis} Axis"
    
    local status_2209=$([[ "$current" == "TMC2209" ]] && echo "done" || echo "")
    local status_2240=$([[ "$current" == "TMC2240" ]] && echo "done" || echo "")
    local status_5160=$([[ "$current" == "TMC5160" ]] && echo "done" || echo "")
    local status_2208=$([[ "$current" == "TMC2208" ]] && echo "done" || echo "")
    local status_a4988=$([[ "$current" == "A4988" ]] && echo "done" || echo "")
    
    print_menu_item "1" "$status_2209" "TMC2209 (UART)"
    print_menu_item "2" "$status_2240" "TMC2240 (SPI)"
    print_menu_item "3" "$status_5160" "TMC5160 (SPI)"
    print_menu_item "4" "$status_2208" "TMC2208 (Standalone)"
    print_menu_item "5" "$status_a4988" "A4988 (Basic)"
    print_separator
    print_action_item "B" "Back"
    print_footer
    
    echo -en "${BYELLOW}Select driver for ${axis}${NC}: "
    read -r choice
    
    case "$choice" in
        1) WIZARD_STATE[driver_${axis}]="TMC2209" ;;
        2) WIZARD_STATE[driver_${axis}]="TMC2240" ;;
        3) WIZARD_STATE[driver_${axis}]="TMC5160" ;;
        4) WIZARD_STATE[driver_${axis}]="TMC2208" ;;
        5) WIZARD_STATE[driver_${axis}]="A4988" ;;
        [bB]) return ;;
        *) ;;
    esac
}

menu_steppers() {
    while true; do
        clear_screen
        print_header "Stepper Configuration"
        
        if [[ -z "${WIZARD_STATE[board]}" ]]; then
            print_box_line "${RED}Please select a board first!${NC}"
            print_footer
            wait_for_key
            return
        fi
        
        local axes
        axes=$(get_required_axes)
        
        print_box_line "${BWHITE}Configure driver for each axis:${NC}"
        print_box_line "${WHITE}(Based on: ${WIZARD_STATE[kinematics]:-not set})${NC}"
        print_empty_line
        
        local num=1
        for axis in $axes; do
            local driver="${WIZARD_STATE[driver_${axis}]}"
            local status=$([[ -n "$driver" ]] && echo "done" || echo "")
            print_menu_item "$num" "$status" "${axis} Axis" "$driver"
            num=$((num + 1))
        done
        
        print_separator
        print_action_item "A" "Set ALL axes to same driver"
        print_action_item "G" "Set all XY gantry drivers (X, X1, Y, Y1)"
        print_action_item "Z" "Set all Z drivers"
        print_action_item "B" "Back"
        print_footer
        
        echo -en "${BYELLOW}Select axis to configure${NC}: "
        read -r choice
        
        case "$choice" in
            [aA])
                # Set all axes to same driver
                clear_screen
                print_header "Set All Drivers"
                print_menu_item "1" "" "TMC2209 (UART)"
                print_menu_item "2" "" "TMC2240 (SPI)"
                print_menu_item "3" "" "TMC5160 (SPI)"
                print_menu_item "4" "" "TMC2208 (Standalone)"
                print_menu_item "5" "" "A4988 (Basic)"
                print_footer
                
                echo -en "${BYELLOW}Select driver for ALL axes${NC}: "
                read -r driver_choice
                
                local driver=""
                case "$driver_choice" in
                    1) driver="TMC2209" ;;
                    2) driver="TMC2240" ;;
                    3) driver="TMC5160" ;;
                    4) driver="TMC2208" ;;
                    5) driver="A4988" ;;
                esac
                
                if [[ -n "$driver" ]]; then
                    for axis in $axes; do
                        WIZARD_STATE[driver_${axis}]="$driver"
                    done
                    # Also set legacy stepper_driver for compatibility
                    WIZARD_STATE[stepper_driver]="$driver"
                fi
                ;;
            [gG])
                # Set all XY gantry drivers (X, X1, Y, Y1)
                clear_screen
                print_header "Set XY Gantry Drivers"
                print_box_line "${WHITE}Sets driver for: X, X1, Y, Y1${NC}"
                print_empty_line
                print_menu_item "1" "" "TMC2209 (UART)"
                print_menu_item "2" "" "TMC2240 (SPI)"
                print_menu_item "3" "" "TMC5160 (SPI)"
                print_menu_item "4" "" "TMC2208 (Standalone)"
                print_menu_item "5" "" "A4988 (Basic)"
                print_footer
                
                echo -en "${BYELLOW}Select driver for XY gantry${NC}: "
                read -r driver_choice
                
                local driver=""
                case "$driver_choice" in
                    1) driver="TMC2209" ;;
                    2) driver="TMC2240" ;;
                    3) driver="TMC5160" ;;
                    4) driver="TMC2208" ;;
                    5) driver="A4988" ;;
                esac
                
                if [[ -n "$driver" ]]; then
                    for axis in X X1 Y Y1; do
                        # Only set if this axis is in the required axes
                        if [[ " $axes " == *" $axis "* ]]; then
                            WIZARD_STATE[driver_${axis}]="$driver"
                        fi
                    done
                    # Update legacy stepper_driver
                    WIZARD_STATE[stepper_driver]="${WIZARD_STATE[driver_X]}"
                fi
                ;;
            [zZ])
                # Set all Z drivers
                clear_screen
                print_header "Set Z Drivers"
                print_box_line "${WHITE}Sets driver for: Z, Z1, Z2, Z3${NC}"
                print_empty_line
                print_menu_item "1" "" "TMC2209 (UART)"
                print_menu_item "2" "" "TMC2240 (SPI)"
                print_menu_item "3" "" "TMC5160 (SPI)"
                print_menu_item "4" "" "TMC2208 (Standalone)"
                print_menu_item "5" "" "A4988 (Basic)"
                print_footer
                
                echo -en "${BYELLOW}Select driver for Z axes${NC}: "
                read -r driver_choice
                
                local driver=""
                case "$driver_choice" in
                    1) driver="TMC2209" ;;
                    2) driver="TMC2240" ;;
                    3) driver="TMC5160" ;;
                    4) driver="TMC2208" ;;
                    5) driver="A4988" ;;
                esac
                
                if [[ -n "$driver" ]]; then
                    for axis in Z Z1 Z2 Z3; do
                        # Only set if this axis is in the required axes
                        if [[ " $axes " == *" $axis "* ]]; then
                            WIZARD_STATE[driver_${axis}]="$driver"
                        fi
                    done
                    # Update legacy stepper_driver if not already set by X driver
                    if [[ -z "${WIZARD_STATE[stepper_driver]}" ]]; then
                        WIZARD_STATE[stepper_driver]="$driver"
                    fi
                fi
                ;;
            [bB])
                return
                ;;
            [1-9])
                # Select specific axis
                local axis_num=$((choice))
                local axis_list=($axes)
                if [[ $axis_num -le ${#axis_list[@]} ]]; then
                    select_driver "${axis_list[$((axis_num - 1))]}"
                    # Update legacy stepper_driver with the most common
                    WIZARD_STATE[stepper_driver]="${WIZARD_STATE[driver_X]}"
                fi
                ;;
            *)
                ;;
        esac
    done
}

# ═══════════════════════════════════════════════════════════════════════════════
# ROTATION DISTANCE CONFIGURATION (PER-AXIS)
# ═══════════════════════════════════════════════════════════════════════════════

menu_rotation_distance() {
    while true; do
        clear_screen
        print_header "Rotation Distance Configuration"

        print_box_line "${BWHITE}Configure each axis individually:${NC}"
        print_empty_line
        print_box_line "Each axis can have different step angle, microsteps,"
        print_box_line "and rotation_distance settings."
        print_empty_line

        # X Axis status
        local x_status=$([[ -n "${WIZARD_STATE[stepper_x_rotation_distance]}" ]] && echo "done" || echo "")
        local x_info="not configured"
        if [[ -n "${WIZARD_STATE[stepper_x_rotation_distance]}" ]]; then
            x_info="${WIZARD_STATE[stepper_x_step_angle]:-1.8}°/${WIZARD_STATE[stepper_x_microsteps]:-16}µ, ${WIZARD_STATE[stepper_x_rotation_distance]}mm"
        fi
        print_menu_item "1" "$x_status" "X Axis" "$x_info"

        # Y Axis status
        local y_status=$([[ -n "${WIZARD_STATE[stepper_y_rotation_distance]}" ]] && echo "done" || echo "")
        local y_info="not configured"
        if [[ -n "${WIZARD_STATE[stepper_y_rotation_distance]}" ]]; then
            y_info="${WIZARD_STATE[stepper_y_step_angle]:-1.8}°/${WIZARD_STATE[stepper_y_microsteps]:-16}µ, ${WIZARD_STATE[stepper_y_rotation_distance]}mm"
        fi
        print_menu_item "2" "$y_status" "Y Axis" "$y_info"

        # Z Axis status
        local z_status=$([[ -n "${WIZARD_STATE[stepper_z_rotation_distance]}" ]] && echo "done" || echo "")
        local z_info="not configured"
        if [[ -n "${WIZARD_STATE[stepper_z_rotation_distance]}" ]]; then
            z_info="${WIZARD_STATE[stepper_z_step_angle]:-1.8}°/${WIZARD_STATE[stepper_z_microsteps]:-16}µ, ${WIZARD_STATE[stepper_z_rotation_distance]}mm"
        fi
        print_menu_item "3" "$z_status" "Z Axis" "$z_info"

        # Extruder status
        local e_status=$([[ -n "${WIZARD_STATE[stepper_e_rotation_distance]}" ]] && echo "done" || echo "")
        local e_info="not configured"
        if [[ -n "${WIZARD_STATE[stepper_e_rotation_distance]}" ]]; then
            e_info="${WIZARD_STATE[stepper_e_step_angle]:-1.8}°/${WIZARD_STATE[stepper_e_microsteps]:-16}µ, ${WIZARD_STATE[stepper_e_rotation_distance]}mm"
        fi
        print_menu_item "4" "$e_status" "Extruder" "$e_info"

        print_separator
        print_box_line "${BWHITE}Quick Setup:${NC}"
        print_menu_item "A" "" "Copy X to Y" "Apply X settings to Y axis"
        print_menu_item "S" "" "Same for X/Y/Z" "Apply same step angle & microsteps to all"

        print_separator
        print_action_item "B" "Back"
        print_footer

        echo -en "${BYELLOW}Select option${NC}: "
        read -r choice

        case "$choice" in
            1) menu_axis_config "x" "X Axis" "belt" ;;
            2) menu_axis_config "y" "Y Axis" "belt" ;;
            3) menu_axis_config "z" "Z Axis" "leadscrew" ;;
            4) menu_axis_config "e" "Extruder" "extruder" ;;
            [aA])
                # Copy X to Y
                WIZARD_STATE[stepper_y_step_angle]="${WIZARD_STATE[stepper_x_step_angle]}"
                WIZARD_STATE[stepper_y_microsteps]="${WIZARD_STATE[stepper_x_microsteps]}"
                WIZARD_STATE[stepper_y_rotation_distance]="${WIZARD_STATE[stepper_x_rotation_distance]}"
                save_state
                echo -e "\n${GREEN}✓${NC} Copied X settings to Y axis"
                sleep 1
                ;;
            [sS])
                # Apply same step angle and microsteps to all
                menu_shared_stepper_settings
                ;;
            [bB]) return ;;
        esac
    done
}

# Generic axis configuration menu
# Args: $1=axis (x/y/z/e), $2=display name, $3=type (belt/leadscrew/extruder)
menu_axis_config() {
    local axis="$1"
    local name="$2"
    local type="$3"

    while true; do
        clear_screen
        print_header "$name Configuration"

        # Current values
        local step="${WIZARD_STATE[stepper_${axis}_step_angle]:-1.8}"
        local micro="${WIZARD_STATE[stepper_${axis}_microsteps]:-16}"
        local rot="${WIZARD_STATE[stepper_${axis}_rotation_distance]:-}"

        print_box_line "${BWHITE}Current settings:${NC}"
        print_box_line "Step angle: ${CYAN}${step}°${NC} ($([ "$step" == "1.8" ] && echo "200" || echo "400") steps/rev)"
        print_box_line "Microsteps: ${CYAN}${micro}${NC}"
        print_box_line "Rotation distance: ${CYAN}${rot:-not set}${NC}${rot:+mm}"
        print_empty_line

        local s1=$([[ -n "${WIZARD_STATE[stepper_${axis}_step_angle]}" ]] && echo "done" || echo "")
        local s2=$([[ -n "${WIZARD_STATE[stepper_${axis}_microsteps]}" ]] && echo "done" || echo "")
        local s3=$([[ -n "${WIZARD_STATE[stepper_${axis}_rotation_distance]}" ]] && echo "done" || echo "")

        print_menu_item "1" "$s1" "Step Angle" "${step}°"
        print_menu_item "2" "$s2" "Microsteps" "${micro}"
        print_menu_item "3" "$s3" "Rotation Distance" "${rot:-not set}${rot:+mm}"

        print_separator
        print_action_item "B" "Back"
        print_footer

        echo -en "${BYELLOW}Select option${NC}: "
        read -r choice

        case "$choice" in
            1) menu_axis_step_angle "$axis" "$name" ;;
            2) menu_axis_microsteps "$axis" "$name" ;;
            3)
                case "$type" in
                    belt) menu_axis_belt_rotation "$axis" "$name" ;;
                    leadscrew) menu_axis_leadscrew_rotation "$axis" "$name" ;;
                    extruder) menu_axis_extruder_rotation "$axis" "$name" ;;
                esac
                ;;
            [bB]) return ;;
        esac
    done
}

menu_axis_step_angle() {
    local axis="$1"
    local name="$2"

    clear_screen
    print_header "$name - Step Angle"

    print_box_line "${BWHITE}Select stepper motor step angle:${NC}"
    print_empty_line

    local cur="${WIZARD_STATE[stepper_${axis}_step_angle]}"
    local s1=$([[ "$cur" == "1.8" ]] && echo "done" || echo "")
    local s2=$([[ "$cur" == "0.9" ]] && echo "done" || echo "")

    print_menu_item "1" "$s1" "1.8° (200 steps/rev)" "Most common, NEMA17"
    print_menu_item "2" "$s2" "0.9° (400 steps/rev)" "High resolution, LDO"
    print_separator
    print_action_item "B" "Back"
    print_footer

    echo -en "${BYELLOW}Select step angle${NC}: "
    read -r choice

    case "$choice" in
        1) WIZARD_STATE[stepper_${axis}_step_angle]="1.8" ;;
        2) WIZARD_STATE[stepper_${axis}_step_angle]="0.9" ;;
        [bB]) return ;;
    esac

    save_state
}

menu_axis_microsteps() {
    local axis="$1"
    local name="$2"

    clear_screen
    print_header "$name - Microsteps"

    print_box_line "${BWHITE}Select microstep resolution:${NC}"
    print_empty_line

    local cur="${WIZARD_STATE[stepper_${axis}_microsteps]}"
    local m1=$([[ "$cur" == "16" ]] && echo "done" || echo "")
    local m2=$([[ "$cur" == "32" ]] && echo "done" || echo "")
    local m3=$([[ "$cur" == "64" ]] && echo "done" || echo "")
    local m4=$([[ "$cur" == "128" ]] && echo "done" || echo "")
    local m5=$([[ "$cur" == "256" ]] && echo "done" || echo "")

    print_menu_item "1" "$m1" "16 microsteps" "Recommended default"
    print_menu_item "2" "$m2" "32 microsteps" "Higher resolution"
    print_menu_item "3" "$m3" "64 microsteps" "TMC drivers"
    print_menu_item "4" "$m4" "128 microsteps" "TMC drivers"
    print_menu_item "5" "$m5" "256 microsteps" "TMC drivers, max"
    print_separator
    print_action_item "B" "Back"
    print_footer

    echo -en "${BYELLOW}Select microsteps${NC}: "
    read -r choice

    case "$choice" in
        1) WIZARD_STATE[stepper_${axis}_microsteps]="16" ;;
        2) WIZARD_STATE[stepper_${axis}_microsteps]="32" ;;
        3) WIZARD_STATE[stepper_${axis}_microsteps]="64" ;;
        4) WIZARD_STATE[stepper_${axis}_microsteps]="128" ;;
        5) WIZARD_STATE[stepper_${axis}_microsteps]="256" ;;
        [bB]) return ;;
    esac

    save_state
}

menu_axis_belt_rotation() {
    local axis="$1"
    local name="$2"

    clear_screen
    print_header "$name - Rotation Distance"

    print_box_line "${BWHITE}Configure belt drive rotation distance:${NC}"
    print_empty_line
    print_box_line "rotation_distance = pulley_teeth × belt_pitch"
    print_empty_line

    print_menu_item "1" "" "GT2 (2mm) + 20T pulley" "40mm (most common)"
    print_menu_item "2" "" "GT2 (2mm) + 16T pulley" "32mm"
    print_menu_item "3" "" "GT3 (3mm) + 20T pulley" "60mm"
    print_menu_item "4" "" "GT2 (2mm) + 40T pulley" "80mm"
    print_menu_item "C" "" "Custom calculation" "Enter belt pitch and teeth"
    print_menu_item "D" "" "Direct entry" "Enter rotation_distance directly"
    print_separator
    print_action_item "B" "Back"
    print_footer

    echo -en "${BYELLOW}Select option${NC}: "
    read -r choice

    local rot=""
    case "$choice" in
        1) rot="40" ;;
        2) rot="32" ;;
        3) rot="60" ;;
        4) rot="80" ;;
        [cC])
            echo -en "  Belt pitch (mm, e.g. 2 for GT2): "
            read -r pitch
            echo -en "  Pulley tooth count: "
            read -r teeth
            if [[ -n "$pitch" && -n "$teeth" ]]; then
                rot=$((teeth * pitch))
                echo -e "  Calculated: ${teeth}T × ${pitch}mm = ${rot}mm"
            fi
            ;;
        [dD])
            echo -en "  Enter rotation_distance (mm): "
            read -r rot
            ;;
        [bB]) return ;;
    esac

    if [[ -n "$rot" ]]; then
        WIZARD_STATE[stepper_${axis}_rotation_distance]="$rot"
        echo -e "\n${GREEN}✓${NC} $name rotation_distance: ${CYAN}${rot}mm${NC}"
        save_state
        sleep 1
    fi
}

menu_axis_leadscrew_rotation() {
    local axis="$1"
    local name="$2"

    clear_screen
    print_header "$name - Rotation Distance"

    print_box_line "${BWHITE}Configure lead screw rotation distance:${NC}"
    print_empty_line
    print_box_line "rotation_distance = lead (pitch × starts)"
    print_box_line "Example: 2mm pitch × 4 starts = 8mm lead"
    print_empty_line

    print_menu_item "1" "" "8mm lead" "T8×8 4-start (most common, fast)"
    print_menu_item "2" "" "4mm lead" "T8×4 2-start"
    print_menu_item "3" "" "2mm lead" "T8×2 single-start (slow, precise)"
    print_menu_item "4" "" "1mm lead" "Fine pitch"
    print_separator
    print_box_line "${BWHITE}Or belt-driven Z:${NC}"
    print_menu_item "5" "" "Belt-driven" "Calculate from belt/pulley"
    print_menu_item "D" "" "Direct entry" "Enter rotation_distance directly"
    print_separator
    print_action_item "B" "Back"
    print_footer

    echo -en "${BYELLOW}Select option${NC}: "
    read -r choice

    local rot=""
    case "$choice" in
        1) rot="8" ;;
        2) rot="4" ;;
        3) rot="2" ;;
        4) rot="1" ;;
        5)
            echo -en "  Belt pitch (mm, e.g. 2 for GT2): "
            read -r pitch
            echo -en "  Pulley tooth count: "
            read -r teeth
            if [[ -n "$pitch" && -n "$teeth" ]]; then
                rot=$((teeth * pitch))
                echo -e "  Calculated: ${teeth}T × ${pitch}mm = ${rot}mm"
            fi
            ;;
        [dD])
            echo -en "  Enter rotation_distance (mm): "
            read -r rot
            ;;
        [bB]) return ;;
    esac

    if [[ -n "$rot" ]]; then
        WIZARD_STATE[stepper_${axis}_rotation_distance]="$rot"
        echo -e "\n${GREEN}✓${NC} $name rotation_distance: ${CYAN}${rot}mm${NC}"
        save_state
        sleep 1
    fi
}

menu_axis_extruder_rotation() {
    local axis="$1"
    local name="$2"

    clear_screen
    print_header "$name - Rotation Distance"

    print_box_line "${BWHITE}Configure extruder rotation distance:${NC}"
    print_empty_line
    print_box_line "${YELLOW}This is a starting value - calibrate after setup!${NC}"
    print_empty_line

    local cur="${WIZARD_STATE[stepper_e_rotation_distance]}"
    local e1=$([[ "$cur" == "22.6789511" ]] && echo "done" || echo "")
    local e2=$([[ "$cur" == "4.637" ]] && echo "done" || echo "")
    local e3=$([[ "$cur" == "33.500" ]] && echo "done" || echo "")
    local e4=$([[ "$cur" == "7.824" ]] && echo "done" || echo "")
    local e5=$([[ "$cur" == "5.7" ]] && echo "done" || echo "")

    print_menu_item "1" "$e1" "Bondtech LGX/LGX Lite" "22.6789511mm"
    print_menu_item "2" "$e2" "Bondtech BMG/Clockwork" "4.637mm"
    print_menu_item "3" "$e3" "Sherpa Mini" "33.500mm"
    print_menu_item "4" "$e4" "Orbiter 1.5/2.0" "7.824mm"
    print_menu_item "5" "$e5" "E3D Titan" "5.7mm"
    print_menu_item "D" "" "Direct entry" "Enter custom value"
    print_separator
    print_action_item "B" "Back"
    print_footer

    echo -en "${BYELLOW}Select extruder${NC}: "
    read -r choice

    local rot=""
    case "$choice" in
        1) rot="22.6789511" ;;
        2) rot="4.637" ;;
        3) rot="33.500" ;;
        4) rot="7.824" ;;
        5) rot="5.7" ;;
        [dD])
            echo -en "  Enter rotation_distance: "
            read -r rot
            ;;
        [bB]) return ;;
    esac

    if [[ -n "$rot" ]]; then
        WIZARD_STATE[stepper_${axis}_rotation_distance]="$rot"
        echo -e "\n${GREEN}✓${NC} Extruder rotation_distance: ${CYAN}${rot}mm${NC}"
        echo -e "${YELLOW}Remember to calibrate this value after setup!${NC}"
        save_state
        sleep 1
    fi
}

# Quick setup: Apply same step angle and microsteps to all axes
menu_shared_stepper_settings() {
    clear_screen
    print_header "Shared Stepper Settings"

    print_box_line "${BWHITE}Apply same step angle to X, Y, Z:${NC}"
    print_empty_line

    print_menu_item "1" "" "1.8° (200 steps/rev)" "Most common"
    print_menu_item "2" "" "0.9° (400 steps/rev)" "High resolution"
    print_separator
    print_action_item "B" "Back"
    print_footer

    echo -en "${BYELLOW}Select step angle${NC}: "
    read -r choice

    local step=""
    case "$choice" in
        1) step="1.8" ;;
        2) step="0.9" ;;
        [bB]) return ;;
    esac

    # Now microsteps
    clear_screen
    print_header "Shared Microsteps"

    print_box_line "${BWHITE}Apply same microsteps to X, Y, Z:${NC}"
    print_empty_line

    print_menu_item "1" "" "16 microsteps" "Recommended"
    print_menu_item "2" "" "32 microsteps" ""
    print_menu_item "3" "" "64 microsteps" "TMC"
    print_menu_item "4" "" "128 microsteps" "TMC"
    print_menu_item "5" "" "256 microsteps" "TMC max"
    print_separator
    print_action_item "B" "Back"
    print_footer

    echo -en "${BYELLOW}Select microsteps${NC}: "
    read -r choice

    local micro=""
    case "$choice" in
        1) micro="16" ;;
        2) micro="32" ;;
        3) micro="64" ;;
        4) micro="128" ;;
        5) micro="256" ;;
        [bB]) return ;;
    esac

    # Apply to X, Y, Z (not extruder - often different)
    if [[ -n "$step" && -n "$micro" ]]; then
        WIZARD_STATE[stepper_x_step_angle]="$step"
        WIZARD_STATE[stepper_x_microsteps]="$micro"
        WIZARD_STATE[stepper_y_step_angle]="$step"
        WIZARD_STATE[stepper_y_microsteps]="$micro"
        WIZARD_STATE[stepper_z_step_angle]="$step"
        WIZARD_STATE[stepper_z_microsteps]="$micro"
        save_state
        echo -e "\n${GREEN}✓${NC} Applied ${step}° / ${micro}µ to X, Y, Z axes"
        sleep 1
    fi
}

# ═══════════════════════════════════════════════════════════════════════════════
# MOTOR PORT ASSIGNMENT
# ═══════════════════════════════════════════════════════════════════════════════

menu_motor_ports() {
    # Save wizard state so Python script can read Z count, kinematics, etc.
    save_state

    # Call the Python hardware setup script for motor port assignment
    python3 "${SCRIPT_DIR}/setup-hardware.py" --motors

    # Reload hardware state
    load_hardware_state

    echo -e "${GREEN}Motor ports configured.${NC}"
    sleep 1
}

# ═══════════════════════════════════════════════════════════════════════════════
# EXTRUDER CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

menu_extruder() {
    clear_screen
    print_header "Extruder Configuration"
    
    print_box_line "${BWHITE}Select Extruder Type:${NC}"
    print_menu_item "1" "" "Direct Drive"
    print_menu_item "2" "" "Bowden"
    print_separator
    print_action_item "B" "Back"
    print_footer
    
    echo -en "${BYELLOW}Select type${NC}: "
    read -r choice
    
    case "$choice" in
        1) WIZARD_STATE[extruder_type]="direct-drive" ;;
        2) WIZARD_STATE[extruder_type]="bowden" ;;
        [bB]) return ;;
        *) return ;;
    esac
    
    # Thermistor selection
    menu_hotend_thermistor
}

menu_hotend_thermistor() {
    clear_screen
    print_header "Hotend Thermistor"
    
    print_box_line "${BWHITE}Common NTC Thermistors:${NC}"
    print_menu_item "1" "" "Generic 3950 (NTC 100K) - Most common"
    print_menu_item "2" "" "ATC Semitec 104GT-2 (E3D/Slice hotends)"
    print_menu_item "3" "" "ATC Semitec 104NT-4-R025H42G"
    print_menu_item "4" "" "Honeywell 100K 135-104LAG-J01"
    print_menu_item "5" "" "NTC 100K MGB18-104F39050L32"
    print_empty_line
    print_box_line "${BWHITE}High-Temp / RTD:${NC}"
    print_menu_item "6" "" "Slice Engineering 450C (high temp)"
    print_menu_item "7" "" "PT1000 (direct, no amplifier)"
    print_menu_item "8" "" "PT1000 with MAX31865 amplifier"
    print_menu_item "9" "" "PT100 with MAX31865 amplifier"
    print_empty_line
    print_menu_item "M" "" "Manual entry (custom sensor_type)"
    print_separator
    print_action_item "B" "Back"
    print_footer
    
    echo -en "${BYELLOW}Select thermistor${NC}: "
    read -r choice
    
    local needs_pullup=true
    case "$choice" in
        1) WIZARD_STATE[hotend_thermistor]="Generic 3950" ;;
        2) WIZARD_STATE[hotend_thermistor]="ATC Semitec 104GT-2" ;;
        3) WIZARD_STATE[hotend_thermistor]="ATC Semitec 104NT-4-R025H42G" ;;
        4) WIZARD_STATE[hotend_thermistor]="Honeywell 100K 135-104LAG-J01" ;;
        5) WIZARD_STATE[hotend_thermistor]="NTC 100K MGB18-104F39050L32" ;;
        6) WIZARD_STATE[hotend_thermistor]="SliceEngineering450" ;;
        7) WIZARD_STATE[hotend_thermistor]="PT1000" ;;
        8)
            WIZARD_STATE[hotend_thermistor]="PT1000_MAX31865"
            needs_pullup=false  # MAX31865 has its own amplifier
            ;;
        9)
            WIZARD_STATE[hotend_thermistor]="PT100_MAX31865"
            needs_pullup=false  # MAX31865 has its own amplifier
            ;;
        [mM])
            print_empty_line
            print_box_line "Enter exact Klipper sensor_type value:"
            print_box_line "(See: https://www.klipper3d.org/Config_Reference.html#thermistor)"
            echo -en "  "
            read -r custom_type
            if [[ -n "$custom_type" ]]; then
                WIZARD_STATE[hotend_thermistor]="$custom_type"
                # Check if MAX31865 type (no pullup needed)
                if [[ "$custom_type" == *MAX31865* ]]; then
                    needs_pullup=false
                fi
            fi
            ;;
        [bB]) return ;;
        *) needs_pullup=false ;;
    esac

    # Ask for pullup resistor for all analog thermistors (not MAX31865)
    if [[ "$needs_pullup" == "true" && -n "${WIZARD_STATE[hotend_thermistor]}" ]]; then
        menu_pullup_resistor
    fi
}

menu_pullup_resistor() {
    clear_screen
    print_header "Pullup Resistor Value"
    
    print_box_line "${BWHITE}Select the pullup resistor value for your board:${NC}"
    print_box_line "(Check your board documentation if unsure)"
    print_empty_line
    
    print_menu_item "1" "" "4700 ohms (4.7K) - Most common default"
    print_menu_item "2" "" "2200 ohms (2.2K) - Some BTT boards"
    print_menu_item "3" "" "1000 ohms (1K) - Rare"
    print_menu_item "4" "" "Custom value"
    print_menu_item "-" "" "Skip (use Klipper default)"
    print_separator
    print_action_item "B" "Back"
    print_footer

    echo -en "${BYELLOW}Select pullup resistor${NC}: "
    read -r choice

    case "$choice" in
        1) WIZARD_STATE[hotend_pullup_resistor]="4700" ;;
        2) WIZARD_STATE[hotend_pullup_resistor]="2200" ;;
        3) WIZARD_STATE[hotend_pullup_resistor]="1000" ;;
        4)
            echo -en "  Enter pullup resistor value (ohms): "
            read -r custom_value
            if [[ -n "$custom_value" ]]; then
                WIZARD_STATE[hotend_pullup_resistor]="$custom_value"
            fi
            ;;
        -) WIZARD_STATE[hotend_pullup_resistor]="" ;;
        [bB]) return ;;
        *) ;;
    esac
}

# ═══════════════════════════════════════════════════════════════════════════════
# EXTRUDER CONFIGURATION (motor, driver, port)
# ═══════════════════════════════════════════════════════════════════════════════

menu_extruder() {
    while true; do
        clear_screen
        print_header "Extruder Configuration"

        print_box_line "${BWHITE}Extruder Motor Settings:${NC}"
        print_empty_line

        # 1. Extruder Type (direct drive / bowden)
        local type_status=$([[ -n "${WIZARD_STATE[extruder_type]}" ]] && echo "done" || echo "")
        print_menu_item "1" "$type_status" "Extruder Type" "${WIZARD_STATE[extruder_type]:-not set}"

        # 2. Extruder Driver
        local driver_status=$([[ -n "${WIZARD_STATE[driver_E]}" ]] && echo "done" || echo "")
        print_menu_item "2" "$driver_status" "Driver Type" "${WIZARD_STATE[driver_E]:-not set}"

        # 3. Motor Port Assignment (depends on toolboard or mainboard)
        print_empty_line
        print_box_line "${BWHITE}Motor Port:${NC}"
        
        local has_toolboard="no"
        if [[ -n "${WIZARD_STATE[toolboard]}" && "${WIZARD_STATE[toolboard]}" != "none" ]]; then
            has_toolboard="yes"
        fi

        if [[ "$has_toolboard" == "yes" ]]; then
            # Extruder on toolboard
            local tb_motor_port="${HARDWARE_STATE[toolboard_extruder]:-not assigned}"
            local motor_status=$([[ -n "${HARDWARE_STATE[toolboard_extruder]}" ]] && echo "done" || echo "")
            print_menu_item "3" "$motor_status" "Motor Port (Toolboard)" "$tb_motor_port"
        else
            # Extruder on mainboard
            if [[ -n "${WIZARD_STATE[board]}" ]]; then
                local motor_port="${HARDWARE_STATE[extruder]:-not assigned}"
                local dir_invert="${HARDWARE_STATE[extruder_dir_invert]}"
                [[ "$dir_invert" == "true" || "$dir_invert" == "True" ]] && motor_port="${motor_port} [DIR INV]"
                local motor_status=$([[ -n "${HARDWARE_STATE[extruder]}" ]] && echo "done" || echo "")
                print_menu_item "3" "$motor_status" "Motor Port (Mainboard)" "$motor_port"
            else
                print_box_line "${YELLOW}3) Motor Port: select board first${NC}"
            fi
        fi

        # 4. Rotation Distance
        print_empty_line
        local e_status=$([[ -n "${WIZARD_STATE[stepper_e_rotation_distance]}" ]] && echo "done" || echo "")
        local e_info=""
        if [[ -n "${WIZARD_STATE[stepper_e_rotation_distance]}" ]]; then
            e_info="${WIZARD_STATE[stepper_e_rotation_distance]}mm"
        else
            e_info="not set"
        fi
        print_menu_item "4" "$e_status" "Rotation Distance" "$e_info"

        print_separator
        print_action_item "B" "Back"
        print_footer

        echo -en "${BYELLOW}Select option${NC}: "
        read -r choice

        case "$choice" in
            1) menu_extruder_type ;;
            2) menu_extruder_driver ;;
            3)
                if [[ "$has_toolboard" == "yes" ]]; then
                    # Assign on toolboard
                    save_state
                    python3 "${SCRIPT_DIR}/setup-hardware.py" --toolboard-motor
                    load_hardware_state
                elif [[ -n "${WIZARD_STATE[board]}" ]]; then
                    # Assign on mainboard - call motor port assignment for extruder only
                    save_state
                    python3 "${SCRIPT_DIR}/setup-hardware.py" --extruder-motor
                    load_hardware_state
                fi
                ;;
            4) menu_axis_config "e" "Extruder" "extruder" ;;
            [bB]) return ;;
            *) ;;
        esac
    done
}

menu_extruder_type() {
    clear_screen
    print_header "Extruder Type"

    print_box_line "${BWHITE}Select Extruder Type:${NC}"
    print_empty_line
    print_box_line "Direct Drive: Motor mounted on toolhead (Voron, Stealthburner)"
    print_box_line "Bowden: Motor separate, filament tube to hotend (Ender-style)"
    print_empty_line
    
    local dd_status=$([[ "${WIZARD_STATE[extruder_type]}" == "direct-drive" ]] && echo "done" || echo "")
    local bd_status=$([[ "${WIZARD_STATE[extruder_type]}" == "bowden" ]] && echo "done" || echo "")
    
    print_menu_item "1" "$dd_status" "Direct Drive"
    print_menu_item "2" "$bd_status" "Bowden"
    print_separator
    print_action_item "B" "Back"
    print_footer

    echo -en "${BYELLOW}Select type${NC}: "
    read -r choice

    case "$choice" in
        1) WIZARD_STATE[extruder_type]="direct-drive"; save_state ;;
        2) WIZARD_STATE[extruder_type]="bowden"; save_state ;;
        [bB]) return ;;
        *) ;;
    esac
}

menu_extruder_driver() {
    clear_screen
    print_header "Extruder Driver Type"

    print_box_line "${BWHITE}Select stepper driver for Extruder:${NC}"
    print_empty_line

    local current="${WIZARD_STATE[driver_E]}"
    local status_2209=$([[ "$current" == "TMC2209" ]] && echo "done" || echo "")
    local status_2240=$([[ "$current" == "TMC2240" ]] && echo "done" || echo "")
    local status_5160=$([[ "$current" == "TMC5160" ]] && echo "done" || echo "")
    local status_2208=$([[ "$current" == "TMC2208" ]] && echo "done" || echo "")
    local status_a4988=$([[ "$current" == "A4988" ]] && echo "done" || echo "")

    print_menu_item "1" "$status_2209" "TMC2209 (UART)" "Most common, StallGuard"
    print_menu_item "2" "$status_2240" "TMC2240 (SPI)" "High performance"
    print_menu_item "3" "$status_5160" "TMC5160 (SPI)" "High power"
    print_menu_item "4" "$status_2208" "TMC2208 (Standalone)" "No UART"
    print_menu_item "5" "$status_a4988" "A4988 (Basic)" "Legacy driver"
    print_separator
    print_action_item "B" "Back"
    print_footer

    echo -en "${BYELLOW}Select driver${NC}: "
    read -r choice

    case "$choice" in
        1) WIZARD_STATE[driver_E]="TMC2209" ;;
        2) WIZARD_STATE[driver_E]="TMC2240" ;;
        3) WIZARD_STATE[driver_E]="TMC5160" ;;
        4) WIZARD_STATE[driver_E]="TMC2208" ;;
        5) WIZARD_STATE[driver_E]="A4988" ;;
        [bB]) return ;;
        *) return ;;
    esac
    save_state
}

# ═══════════════════════════════════════════════════════════════════════════════
# HOTEND CONFIGURATION (thermistor, heater, ports)
# ═══════════════════════════════════════════════════════════════════════════════

menu_hotend() {
    while true; do
        clear_screen
        print_header "Hotend Configuration"

        print_box_line "${BWHITE}Hotend Settings (Thermistor + Heater):${NC}"
        print_empty_line

        # 1. Thermistor type
        local therm_status=$([[ -n "${WIZARD_STATE[hotend_thermistor]}" ]] && echo "done" || echo "")
        local therm_info="${WIZARD_STATE[hotend_thermistor]:-not set}"
        if [[ -n "${WIZARD_STATE[hotend_pullup_resistor]}" ]]; then
            therm_info="${therm_info} (pullup: ${WIZARD_STATE[hotend_pullup_resistor]}Ω)"
        fi
        print_menu_item "1" "$therm_status" "Thermistor Type" "${therm_info}"

        # 2-3. Port assignment (heater + thermistor)
        print_empty_line
        print_box_line "${BWHITE}Port Assignment:${NC}"

        if [[ -n "${WIZARD_STATE[board]}" ]]; then
            # Show heater port - check both mainboard and toolboard assignments
            local heater_status=""
            local heater_info="not assigned"
            if [[ -n "${HARDWARE_STATE[toolboard_heater_extruder]}" ]]; then
                heater_status="done"
                heater_info="toolboard:${HARDWARE_STATE[toolboard_heater_extruder]}"
            elif [[ -n "${HARDWARE_STATE[heater_extruder]}" ]]; then
                heater_status="done"
                heater_info="${HARDWARE_STATE[heater_extruder]}"
            fi
            print_menu_item "2" "$heater_status" "Heater Port" "$heater_info"

            # Show thermistor port - check both mainboard and toolboard assignments
            local therm_port_status=""
            local therm_port_info="not assigned"
            if [[ -n "${HARDWARE_STATE[toolboard_thermistor_extruder]}" ]]; then
                therm_port_status="done"
                therm_port_info="toolboard:${HARDWARE_STATE[toolboard_thermistor_extruder]}"
            elif [[ -n "${HARDWARE_STATE[thermistor_extruder]}" ]]; then
                therm_port_status="done"
                therm_port_info="${HARDWARE_STATE[thermistor_extruder]}"
            fi
            print_menu_item "3" "$therm_port_status" "Thermistor Port" "$therm_port_info"
        else
            print_box_line "${YELLOW}Select a main board first to assign ports${NC}"
        fi

        print_separator
        print_action_item "B" "Back"
        print_footer

        echo -en "${BYELLOW}Select option${NC}: "
        read -r choice

        case "$choice" in
            1) menu_hotend_thermistor ;;
            2)
                if [[ -n "${WIZARD_STATE[board]}" ]]; then
                    menu_hotend_heater_port
                fi
                ;;
            3)
                if [[ -n "${WIZARD_STATE[board]}" ]]; then
                    menu_hotend_thermistor_port
                fi
                ;;
            [bB]) return ;;
            *) ;;
        esac
    done
}

menu_hotend_heater_port() {
    # Save state and call Python script for heater port assignment
    save_state
    python3 "${SCRIPT_DIR}/setup-hardware.py" --heater-extruder
    load_hardware_state
}

menu_hotend_thermistor_port() {
    # Save state and call Python script for thermistor port assignment
    save_state
    python3 "${SCRIPT_DIR}/setup-hardware.py" --thermistor-extruder
    load_hardware_state
}

# ═══════════════════════════════════════════════════════════════════════════════
# BED CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

menu_bed() {
    while true; do
        clear_screen
        print_header "Heated Bed Configuration"

        print_box_line "${BWHITE}Bed Settings:${NC}"
        print_empty_line

        # 1. Bed dimensions
        local dim_info=""
        if [[ -n "${WIZARD_STATE[bed_size_x]}" ]]; then
            dim_info="${WIZARD_STATE[bed_size_x]}x${WIZARD_STATE[bed_size_y]}x${WIZARD_STATE[bed_size_z]}mm"
        else
            dim_info="not set"
        fi
        local dim_status=$([[ -n "${WIZARD_STATE[bed_size_x]}" ]] && echo "done" || echo "")
        print_menu_item "1" "$dim_status" "Bed Dimensions" "${dim_info}"

        # 2. Thermistor type
        local therm_status=$([[ -n "${WIZARD_STATE[bed_thermistor]}" ]] && echo "done" || echo "")
        local therm_info="${WIZARD_STATE[bed_thermistor]:-not set}"
        if [[ -n "${WIZARD_STATE[bed_pullup_resistor]}" ]]; then
            therm_info="${therm_info} (pullup: ${WIZARD_STATE[bed_pullup_resistor]}Ω)"
        fi
        print_menu_item "2" "$therm_status" "Thermistor Type" "${therm_info}"

        # 3. Port assignment
        print_empty_line
        print_box_line "${BWHITE}Port Assignment:${NC}"

        if [[ -n "${WIZARD_STATE[board]}" ]]; then
            local heater_status=$([[ -n "${HARDWARE_STATE[heater_bed]}" ]] && echo "done" || echo "")
            print_menu_item "3" "$heater_status" "Heater Port" "${HARDWARE_STATE[heater_bed]:-not assigned}"

            local therm_port_status=$([[ -n "${HARDWARE_STATE[thermistor_bed]}" ]] && echo "done" || echo "")
            print_menu_item "4" "$therm_port_status" "Thermistor Port" "${HARDWARE_STATE[thermistor_bed]:-not assigned}"
        else
            print_box_line "${YELLOW}Select a main board first to assign ports${NC}"
        fi

        print_separator
        print_action_item "B" "Back to Main Menu"
        print_footer

        echo -en "${BYELLOW}Select option${NC}: "
        read -r choice

        case "$choice" in
            1) menu_bed_dimensions ;;
            2) menu_bed_thermistor ;;
            3)
                if [[ -n "${WIZARD_STATE[board]}" ]]; then
                    menu_bed_heater_port
                fi
                ;;
            4)
                if [[ -n "${WIZARD_STATE[board]}" ]]; then
                    menu_bed_thermistor_port
                fi
                ;;
            [bB]) return ;;
            *) ;;
        esac
    done
}

menu_bed_dimensions() {
    clear_screen
    print_header "Bed Dimensions"

    print_box_line "${BWHITE}Enter bed dimensions:${NC}"
    print_empty_line

    echo -en "  " >&2
    WIZARD_STATE[bed_size_x]=$(prompt_input "Bed size X (mm)" "${WIZARD_STATE[bed_size_x]:-300}")
    echo -en "  " >&2
    WIZARD_STATE[bed_size_y]=$(prompt_input "Bed size Y (mm)" "${WIZARD_STATE[bed_size_y]:-300}")
    echo -en "  " >&2
    WIZARD_STATE[bed_size_z]=$(prompt_input "Max Z height (mm)" "${WIZARD_STATE[bed_size_z]:-350}")

    echo -e "\n${GREEN}Bed dimensions saved.${NC}"
    sleep 1
}

menu_bed_thermistor() {
    clear_screen
    print_header "Bed Thermistor"

    print_box_line "${BWHITE}Select Bed Thermistor:${NC}"
    print_menu_item "1" "" "Generic 3950 (NTC 100K - Keenovo, most common)"
    print_menu_item "2" "" "EPCOS 100K B57560G104F"
    print_menu_item "3" "" "PT1000 (direct)"
    print_menu_item "4" "" "NTC 100K MGB18-104F39050L32"
    print_menu_item "5" "" "Honeywell 100K 135-104LAG-J01"
    print_separator
    print_action_item "B" "Back"
    print_footer

    echo -en "${BYELLOW}Select thermistor${NC}: "
    read -r choice

    local needs_pullup=true
    case "$choice" in
        1) WIZARD_STATE[bed_thermistor]="Generic 3950" ;;
        2) WIZARD_STATE[bed_thermistor]="EPCOS 100K B57560G104F" ;;
        3) WIZARD_STATE[bed_thermistor]="PT1000" ;;
        4) WIZARD_STATE[bed_thermistor]="NTC 100K MGB18-104F39050L32" ;;
        5) WIZARD_STATE[bed_thermistor]="Honeywell 100K 135-104LAG-J01" ;;
        [bB]) return ;;
        *) needs_pullup=false ;;
    esac

    # Ask for pullup resistor for all analog thermistors
    if [[ "$needs_pullup" == "true" && -n "${WIZARD_STATE[bed_thermistor]}" ]]; then
        menu_bed_pullup_resistor
    fi
}

menu_bed_pullup_resistor() {
    clear_screen
    print_header "Bed Thermistor Pullup Resistor"

    print_box_line "${BWHITE}Select the pullup resistor value for bed thermistor:${NC}"
    print_box_line "(Check your board documentation if unsure)"
    print_empty_line

    print_menu_item "1" "" "4700 ohms (4.7K) - Most common default"
    print_menu_item "2" "" "2200 ohms (2.2K) - Some BTT boards"
    print_menu_item "3" "" "1000 ohms (1K) - Rare"
    print_menu_item "4" "" "Custom value"
    print_separator
    print_action_item "S" "Skip (use Klipper default)"
    print_footer

    echo -en "${BYELLOW}Select pullup resistor${NC}: "
    read -r choice

    case "$choice" in
        1) WIZARD_STATE[bed_pullup_resistor]="4700" ;;
        2) WIZARD_STATE[bed_pullup_resistor]="2200" ;;
        3) WIZARD_STATE[bed_pullup_resistor]="1000" ;;
        4)
            echo -en "  Enter pullup resistor value (ohms): "
            read -r custom_value
            if [[ -n "$custom_value" ]]; then
                WIZARD_STATE[bed_pullup_resistor]="$custom_value"
            fi
            ;;
        [sS]) WIZARD_STATE[bed_pullup_resistor]="" ;;
        *) ;;
    esac
}

menu_bed_heater_port() {
    save_state
    python3 "${SCRIPT_DIR}/setup-hardware.py" --heater-bed
    load_hardware_state
}

menu_bed_thermistor_port() {
    save_state
    python3 "${SCRIPT_DIR}/setup-hardware.py" --thermistor-bed
    load_hardware_state
}

# ═══════════════════════════════════════════════════════════════════════════════
# ENDSTOPS CONFIGURATION (includes probe as Z endstop)
# ═══════════════════════════════════════════════════════════════════════════════

menu_endstops() {
    while true; do
        clear_screen
        print_header "Endstops Configuration"

        print_box_line "${BWHITE}X/Y Endstops:${NC}"

        # X endstop
        local x_info=""
        if [[ -n "${WIZARD_STATE[home_x]}" ]]; then
            x_info="position: ${WIZARD_STATE[home_x]}"
            if [[ "${WIZARD_STATE[endstop_x_type]}" == "sensorless" ]]; then
                x_info="${x_info}, sensorless"
            elif [[ -n "${HARDWARE_STATE[endstop_x]}" ]]; then
                x_info="${x_info}, port: ${HARDWARE_STATE[endstop_x]}"
            fi
        else
            x_info="not configured"
        fi
        local x_status=$([[ -n "${WIZARD_STATE[home_x]}" ]] && echo "done" || echo "")
        print_menu_item "1" "$x_status" "X Endstop" "${x_info}"

        # Y endstop
        local y_info=""
        if [[ -n "${WIZARD_STATE[home_y]}" ]]; then
            y_info="position: ${WIZARD_STATE[home_y]}"
            if [[ "${WIZARD_STATE[endstop_y_type]}" == "sensorless" ]]; then
                y_info="${y_info}, sensorless"
            elif [[ -n "${HARDWARE_STATE[endstop_y]}" ]]; then
                y_info="${y_info}, port: ${HARDWARE_STATE[endstop_y]}"
            fi
        else
            y_info="not configured"
        fi
        local y_status=$([[ -n "${WIZARD_STATE[home_y]}" ]] && echo "done" || echo "")
        print_menu_item "2" "$y_status" "Y Endstop" "${y_info}"

        print_empty_line
        print_box_line "${BWHITE}Z Endstop / Probe:${NC}"

        # Z endstop / probe
        local z_info=""
        local probe_type="${WIZARD_STATE[probe_type]:-not set}"
        if [[ "$probe_type" == "endstop" ]]; then
            z_info="Physical switch"
            if [[ -n "${WIZARD_STATE[home_z]}" ]]; then
                z_info="${z_info} (${WIZARD_STATE[home_z]})"
            fi
            if [[ -n "${HARDWARE_STATE[endstop_z]}" ]]; then
                z_info="${z_info}, port: ${HARDWARE_STATE[endstop_z]}"
            fi
        elif [[ "$probe_type" != "not set" && -n "$probe_type" ]]; then
            z_info="${probe_type}"
            # Show mode and MCU info for eddy current probes
            if [[ "$probe_type" =~ ^(beacon|cartographer|btt-eddy)$ ]]; then
                # Add probe mode
                if [[ -n "${WIZARD_STATE[probe_mode]}" ]]; then
                    z_info="${z_info} [${WIZARD_STATE[probe_mode]}]"
                fi
                # Add MCU info
                if [[ -n "${WIZARD_STATE[probe_serial]}" ]]; then
                    z_info="${z_info} (serial configured)"
                elif [[ -n "${WIZARD_STATE[probe_canbus_uuid]}" ]]; then
                    z_info="${z_info} (CAN configured)"
                else
                    z_info="${z_info} (MCU not configured)"
                fi
            fi
        else
            z_info="not configured"
        fi
        local z_status=$([[ -n "${WIZARD_STATE[probe_type]}" ]] && echo "done" || echo "")
        print_menu_item "3" "$z_status" "Z Probe/Endstop" "${z_info}"

        print_separator
        print_action_item "B" "Back to Main Menu"
        print_footer

        echo -en "${BYELLOW}Select option${NC}: "
        read -r choice

        case "$choice" in
            1) menu_endstop_x ;;
            2) menu_endstop_y ;;
            3) menu_endstop_z ;;
            [bB]) return ;;
            *) ;;
        esac
    done
}

menu_endstop_x() {
    while true; do
        clear_screen
        print_header "X Endstop Configuration"

        print_box_line "${BWHITE}X Axis Endstop:${NC}"
        print_empty_line

        local pos_status=$([[ -n "${WIZARD_STATE[home_x]}" ]] && echo "done" || echo "")
        print_menu_item "1" "$pos_status" "Endstop Position" "${WIZARD_STATE[home_x]:-not set}"

        local type_status=$([[ -n "${WIZARD_STATE[endstop_x_type]}" ]] && echo "done" || echo "")
        print_menu_item "2" "$type_status" "Endstop Type" "${WIZARD_STATE[endstop_x_type]:-physical switch}"

        # Port assignment only for physical switches
        if [[ "${WIZARD_STATE[endstop_x_type]}" != "sensorless" ]]; then
            if [[ -n "${WIZARD_STATE[board]}" ]]; then
                local port_status=$([[ -n "${HARDWARE_STATE[endstop_x]}" ]] && echo "done" || echo "")
                print_menu_item "3" "$port_status" "Port Assignment" "${HARDWARE_STATE[endstop_x]:-not assigned}"
            else
                print_box_line "${YELLOW}3) Port Assignment: select board first${NC}"
            fi
        fi

        print_separator
        print_action_item "B" "Back"
        print_footer

        echo -en "${BYELLOW}Select option${NC}: "
        read -r choice

        case "$choice" in
            1) menu_endstop_x_position ;;
            2) menu_endstop_x_type ;;
            3)
                if [[ -n "${WIZARD_STATE[board]}" && "${WIZARD_STATE[endstop_x_type]}" != "sensorless" ]]; then
                    menu_endstop_x_port
                fi
                ;;
            [bB]) return ;;
            *) ;;
        esac
    done
}

menu_endstop_x_position() {
    clear_screen
    print_header "X Endstop Position"

    print_box_line "${BWHITE}Where is the X endstop located?${NC}"
    print_empty_line

    print_menu_item "1" "" "X MAX (right side) - Voron style"
    print_menu_item "2" "" "X MIN (left side) - Prusa/Ender style"
    print_separator
    print_action_item "B" "Back"
    print_footer

    echo -en "${BYELLOW}Select position${NC}: "
    read -r choice

    case "$choice" in
        1) WIZARD_STATE[home_x]="max" ;;
        2) WIZARD_STATE[home_x]="min" ;;
        [bB]) return ;;
        *) ;;
    esac
}

menu_endstop_x_type() {
    clear_screen
    print_header "X Endstop Type"

    print_box_line "${BWHITE}Select X endstop type:${NC}"
    print_empty_line

    print_menu_item "1" "" "Physical switch (microswitch)"
    print_menu_item "2" "" "Sensorless homing (TMC StallGuard)"
    print_separator
    print_action_item "B" "Back"
    print_footer

    echo -en "${BYELLOW}Select type${NC}: "
    read -r choice

    case "$choice" in
        1) WIZARD_STATE[endstop_x_type]="physical" ;;
        2) WIZARD_STATE[endstop_x_type]="sensorless" ;;
        [bB]) return ;;
        *) ;;
    esac
}

menu_endstop_x_port() {
    save_state
    python3 "${SCRIPT_DIR}/setup-hardware.py" --endstop-x
    load_hardware_state
}

menu_endstop_y() {
    while true; do
        clear_screen
        print_header "Y Endstop Configuration"

        print_box_line "${BWHITE}Y Axis Endstop:${NC}"
        print_empty_line

        local pos_status=$([[ -n "${WIZARD_STATE[home_y]}" ]] && echo "done" || echo "")
        print_menu_item "1" "$pos_status" "Endstop Position" "${WIZARD_STATE[home_y]:-not set}"

        local type_status=$([[ -n "${WIZARD_STATE[endstop_y_type]}" ]] && echo "done" || echo "")
        print_menu_item "2" "$type_status" "Endstop Type" "${WIZARD_STATE[endstop_y_type]:-physical switch}"

        # Port assignment only for physical switches
        if [[ "${WIZARD_STATE[endstop_y_type]}" != "sensorless" ]]; then
            if [[ -n "${WIZARD_STATE[board]}" ]]; then
                local port_status=$([[ -n "${HARDWARE_STATE[endstop_y]}" ]] && echo "done" || echo "")
                print_menu_item "3" "$port_status" "Port Assignment" "${HARDWARE_STATE[endstop_y]:-not assigned}"
            else
                print_box_line "${YELLOW}3) Port Assignment: select board first${NC}"
            fi
        fi

        print_separator
        print_action_item "B" "Back"
        print_footer

        echo -en "${BYELLOW}Select option${NC}: "
        read -r choice

        case "$choice" in
            1) menu_endstop_y_position ;;
            2) menu_endstop_y_type ;;
            3)
                if [[ -n "${WIZARD_STATE[board]}" && "${WIZARD_STATE[endstop_y_type]}" != "sensorless" ]]; then
                    menu_endstop_y_port
                fi
                ;;
            [bB]) return ;;
            *) ;;
        esac
    done
}

menu_endstop_y_position() {
    clear_screen
    print_header "Y Endstop Position"

    print_box_line "${BWHITE}Where is the Y endstop located?${NC}"
    print_empty_line

    print_menu_item "1" "" "Y MAX (back) - Voron style"
    print_menu_item "2" "" "Y MIN (front) - Prusa/Ender style"
    print_separator
    print_action_item "B" "Back"
    print_footer

    echo -en "${BYELLOW}Select position${NC}: "
    read -r choice

    case "$choice" in
        1) WIZARD_STATE[home_y]="max" ;;
        2) WIZARD_STATE[home_y]="min" ;;
        [bB]) return ;;
        *) ;;
    esac
}

menu_endstop_y_type() {
    clear_screen
    print_header "Y Endstop Type"

    print_box_line "${BWHITE}Select Y endstop type:${NC}"
    print_empty_line

    print_menu_item "1" "" "Physical switch (microswitch)"
    print_menu_item "2" "" "Sensorless homing (TMC StallGuard)"
    print_separator
    print_action_item "B" "Back"
    print_footer

    echo -en "${BYELLOW}Select type${NC}: "
    read -r choice

    case "$choice" in
        1) WIZARD_STATE[endstop_y_type]="physical" ;;
        2) WIZARD_STATE[endstop_y_type]="sensorless" ;;
        [bB]) return ;;
        *) ;;
    esac
}

menu_endstop_y_port() {
    save_state
    python3 "${SCRIPT_DIR}/setup-hardware.py" --endstop-y
    load_hardware_state
}

menu_endstop_z() {
    while true; do
        clear_screen
        print_header "Z Endstop / Probe Configuration"

        # Show installation status for probes that need modules
        local beacon_status="" carto_status="" eddy_status=""
        if is_probe_installed "beacon"; then
            beacon_status="${GREEN}[installed]${NC}"
        else
            beacon_status="${YELLOW}[not installed]${NC}"
        fi
        if is_probe_installed "cartographer"; then
            carto_status="${GREEN}[installed]${NC}"
        else
            carto_status="${YELLOW}[not installed]${NC}"
        fi
        if is_probe_installed "btt-eddy"; then
            eddy_status="${GREEN}[installed]${NC}"
        else
            eddy_status="${YELLOW}[not installed]${NC}"
        fi

        # Get current probe type for checkmark display
        local current_probe="${WIZARD_STATE[probe_type]}"
        local current_mode="${WIZARD_STATE[probe_mode]}"
        
        # Build current status display
        local current_display="${current_probe:-not set}"
        if [[ "$current_probe" =~ ^(beacon|cartographer|btt-eddy)$ && -n "$current_mode" ]]; then
            current_display="${current_probe} (${current_mode} mode)"
        fi

        print_box_line "${BWHITE}Current: ${current_display}${NC}"
        print_empty_line
        print_box_line "${BWHITE}Pin-based Probes:${NC}"
        local bltouch_sel=$([[ "$current_probe" == "bltouch" ]] && echo "done" || echo "")
        local klicky_sel=$([[ "$current_probe" == "klicky" ]] && echo "done" || echo "")
        local inductive_sel=$([[ "$current_probe" == "inductive" ]] && echo "done" || echo "")
        print_menu_item "1" "$bltouch_sel" "BLTouch / 3DTouch"
        print_menu_item "2" "$klicky_sel" "Klicky Probe"
        print_menu_item "3" "$inductive_sel" "Inductive Probe (PINDA/SuperPINDA)"

        print_empty_line
        print_box_line "${BWHITE}MCU-based Probes (USB/CAN):${NC}"
        local beacon_sel=$([[ "$current_probe" == "beacon" ]] && echo "done" || echo "")
        local carto_sel=$([[ "$current_probe" == "cartographer" ]] && echo "done" || echo "")
        local eddy_sel=$([[ "$current_probe" == "btt-eddy" ]] && echo "done" || echo "")
        print_menu_item "4" "$beacon_sel" "Beacon (Eddy Current)" "${beacon_status}"
        print_menu_item "5" "$carto_sel" "Cartographer" "${carto_status}"
        print_menu_item "6" "$eddy_sel" "BTT Eddy" "${eddy_status}"

        print_empty_line
        print_box_line "${BWHITE}Physical Endstop:${NC}"
        local endstop_sel=$([[ "$current_probe" == "endstop" ]] && echo "done" || echo "")
        print_menu_item "7" "$endstop_sel" "Physical Z Endstop (no probe)"

        # Show port/MCU assignment option if probe is selected
        if [[ -n "${WIZARD_STATE[probe_type]}" && "${WIZARD_STATE[probe_type]}" != "endstop" ]]; then
            print_empty_line
            if [[ "${WIZARD_STATE[probe_type]}" =~ ^(beacon|cartographer|btt-eddy)$ ]]; then
                local mcu_info=""
                if [[ -n "${WIZARD_STATE[probe_serial]}" ]]; then
                    mcu_info="USB: ${WIZARD_STATE[probe_serial]}"
                elif [[ -n "${WIZARD_STATE[probe_canbus_uuid]}" ]]; then
                    mcu_info="CAN: ${WIZARD_STATE[probe_canbus_uuid]}"
                else
                    mcu_info="not configured"
                fi
                print_menu_item "P" "" "Configure Probe MCU" "${mcu_info}"
                
                # Show operation mode option for eddy probes
                local mode_info="${WIZARD_STATE[probe_mode]:-not set}"
                local mode_status=$([[ -n "${WIZARD_STATE[probe_mode]}" ]] && echo "done" || echo "")
                print_menu_item "M" "$mode_status" "Operation Mode" "${mode_info}"
            else
                local pin_info="${HARDWARE_STATE[probe_pin]:-not assigned}"
                print_menu_item "P" "" "Configure Probe Pin" "${pin_info}"
            fi
        elif [[ "${WIZARD_STATE[probe_type]}" == "endstop" ]]; then
            print_empty_line
            local z_port="${HARDWARE_STATE[endstop_z]:-not assigned}"
            print_menu_item "P" "" "Configure Z Endstop Port" "${z_port}"
        fi

        print_separator
        print_action_item "B" "Back"
        print_footer

        echo -en "${BYELLOW}Select option${NC}: "
        read -r choice

        local selected_probe=""
        case "$choice" in
            1) WIZARD_STATE[probe_type]="bltouch" ;;
            2) WIZARD_STATE[probe_type]="klicky" ;;
            3) WIZARD_STATE[probe_type]="inductive" ;;
            4)
                WIZARD_STATE[probe_type]="beacon"
                selected_probe="beacon"
                ;;
            5)
                WIZARD_STATE[probe_type]="cartographer"
                selected_probe="cartographer"
                ;;
            6)
                WIZARD_STATE[probe_type]="btt-eddy"
                selected_probe="btt-eddy"
                ;;
            7)
                WIZARD_STATE[probe_type]="endstop"
                menu_endstop_z_position
                ;;
            [pP])
                if [[ -n "${WIZARD_STATE[probe_type]}" ]]; then
                    menu_probe_port_or_mcu
                fi
                ;;
            [mM])
                # Change operation mode for eddy probes
                if [[ "${WIZARD_STATE[probe_type]}" =~ ^(beacon|cartographer|btt-eddy)$ ]]; then
                    menu_probe_operation_mode
                fi
                ;;
            [bB]) return ;;
            *) ;;
        esac

        # If selected probe needs installation, offer to install it
        if [[ -n "$selected_probe" ]] && ! is_probe_installed "$selected_probe"; then
            echo ""
            echo -e "${YELLOW}The ${selected_probe} probe requires additional software.${NC}"
            if confirm "Install ${selected_probe} module now?"; then
                install_probe_module "$selected_probe"
                wait_for_key
            else
                echo -e "${YELLOW}Note: You'll need to install ${selected_probe} manually before using it.${NC}"
                wait_for_key
            fi
        fi
        
        # For eddy current probes, prompt for operation mode selection
        if [[ -n "$selected_probe" ]]; then
            menu_probe_operation_mode
        fi
    done
}

menu_endstop_z_position() {
    clear_screen
    print_header "Z Endstop Position"

    print_box_line "${BWHITE}Where is the Z endstop located?${NC}"
    print_empty_line

    print_menu_item "1" "" "Z MIN (bed level) - most common"
    print_menu_item "2" "" "Z MAX (top of travel)"
    print_separator
    print_action_item "B" "Back"
    print_footer

    echo -en "${BYELLOW}Select position${NC}: "
    read -r choice

    case "$choice" in
        1) WIZARD_STATE[home_z]="min" ;;
        2) WIZARD_STATE[home_z]="max" ;;
        [bB]) return ;;
        *) ;;
    esac
}

menu_probe_port_or_mcu() {
    local probe_type="${WIZARD_STATE[probe_type]}"

    if [[ "$probe_type" =~ ^(beacon|cartographer|btt-eddy)$ ]]; then
        # MCU-based probe - configure serial or CAN
        menu_probe_mcu
    elif [[ "$probe_type" == "endstop" ]]; then
        # Physical Z endstop
        if [[ -n "${WIZARD_STATE[board]}" ]]; then
            save_state
            python3 "${SCRIPT_DIR}/setup-hardware.py" --endstop-z
            load_hardware_state
        else
            echo -e "${RED}Please select a main board first!${NC}"
            wait_for_key
        fi
    else
        # Pin-based probe (BLTouch, Klicky, Inductive)
        if [[ -n "${WIZARD_STATE[board]}" ]]; then
            save_state
            python3 "${SCRIPT_DIR}/setup-hardware.py" --probe-pin
            load_hardware_state
        else
            echo -e "${RED}Please select a main board first!${NC}"
            wait_for_key
        fi
    fi
}

menu_probe_mcu() {
    clear_screen
    print_header "Probe MCU Configuration"

    local probe_type="${WIZARD_STATE[probe_type]}"
    print_box_line "${BWHITE}Configure ${probe_type} connection:${NC}"
    print_empty_line

    print_menu_item "1" "" "USB connection (serial by-id)"
    print_menu_item "2" "" "CAN bus (UUID)"
    print_separator
    print_action_item "B" "Back"
    print_footer

    echo -en "${BYELLOW}Select connection type${NC}: "
    read -r choice

    case "$choice" in
        1) menu_probe_usb ;;
        2) menu_probe_can ;;
        [bB]) return ;;
        *) ;;
    esac
}

menu_probe_usb() {
    clear_screen
    print_header "Probe USB Serial"

    print_box_line "${BWHITE}Scanning for USB devices...${NC}"
    print_empty_line

    # Scan for USB devices
    local devices=()
    local i=1
    while IFS= read -r device; do
        if [[ -n "$device" ]]; then
            devices+=("$device")
            local short_name=$(basename "$device")
            print_box_line "${BWHITE}${i})${NC} ${short_name}"
            i=$((i + 1))
        fi
    done < <(ls /dev/serial/by-id/ 2>/dev/null | grep -iE "beacon|cartographer|eddy|probe" || true)

    if [[ ${#devices[@]} -eq 0 ]]; then
        print_box_line "${YELLOW}No probe USB devices found.${NC}"
        print_box_line "${WHITE}Make sure your probe is connected via USB.${NC}"
    fi

    print_separator
    print_action_item "M" "Manual entry"
    print_action_item "B" "Back"
    print_footer

    echo -en "${BYELLOW}Select device or M for manual${NC}: "
    read -r choice

    case "$choice" in
        [1-9])
            local idx=$((choice - 1))
            if [[ $idx -lt ${#devices[@]} ]]; then
                WIZARD_STATE[probe_serial]="/dev/serial/by-id/${devices[$idx]}"
                WIZARD_STATE[probe_canbus_uuid]=""
                echo -e "${GREEN}✓${NC} Probe serial set to: ${WIZARD_STATE[probe_serial]}"
                sleep 1
            fi
            ;;
        [mM])
            echo -en "  Enter serial path: "
            read -r manual_serial
            if [[ -n "$manual_serial" ]]; then
                WIZARD_STATE[probe_serial]="$manual_serial"
                WIZARD_STATE[probe_canbus_uuid]=""
            fi
            ;;
        [bB]) return ;;
        *) ;;
    esac

    # Save state after probe serial selection
    save_state
}

menu_probe_can() {
    clear_screen
    print_header "Probe CAN UUID"

    print_box_line "${BWHITE}Scanning CAN bus for devices...${NC}"
    print_empty_line

    # Check if CAN interface is up
    if ! check_can_interface can0 2>/dev/null; then
        print_box_line "${RED}CAN interface not available.${NC}"
        print_box_line "${WHITE}Please configure CAN bus first.${NC}"
        print_footer
        wait_for_key
        return
    fi

    # Scan for CAN devices
    local uuids=()
    local i=1
    while IFS= read -r line; do
        if [[ "$line" =~ canbus_uuid=([a-f0-9]+) ]]; then
            local uuid="${BASH_REMATCH[1]}"
            uuids+=("$uuid")
            print_box_line "${BWHITE}${i})${NC} ${uuid}"
            i=$((i + 1))
        fi
    done < <(python3 ~/klipper/scripts/canbus_query.py can0 2>/dev/null || true)

    if [[ ${#uuids[@]} -eq 0 ]]; then
        print_box_line "${YELLOW}No CAN devices found.${NC}"
    fi

    print_separator
    print_action_item "M" "Manual entry"
    print_action_item "B" "Back"
    print_footer

    echo -en "${BYELLOW}Select device or M for manual${NC}: "
    read -r choice

    case "$choice" in
        [1-9])
            local idx=$((choice - 1))
            if [[ $idx -lt ${#uuids[@]} ]]; then
                WIZARD_STATE[probe_canbus_uuid]="${uuids[$idx]}"
                WIZARD_STATE[probe_serial]=""
                echo -e "${GREEN}✓${NC} Probe CAN UUID set to: ${WIZARD_STATE[probe_canbus_uuid]}"
                sleep 1
            fi
            ;;
        [mM])
            echo -en "  Enter CAN UUID: "
            read -r manual_uuid
            if [[ -n "$manual_uuid" ]]; then
                WIZARD_STATE[probe_canbus_uuid]="$manual_uuid"
                WIZARD_STATE[probe_serial]=""
            fi
            ;;
        [bB]) return ;;
        *) ;;
    esac

    # Save state after probe CAN UUID selection
    save_state
}

# ═══════════════════════════════════════════════════════════════════════════════
# PROBE OPERATION MODE SELECTION (for eddy current probes)
# ═══════════════════════════════════════════════════════════════════════════════

menu_probe_operation_mode() {
    local probe_type="${WIZARD_STATE[probe_type]}"
    
    # Only applicable for eddy current probes
    if [[ ! "$probe_type" =~ ^(beacon|cartographer|btt-eddy)$ ]]; then
        return
    fi
    
    clear_screen
    print_header "Probe Operation Mode"
    
    print_box_line "${BWHITE}Select operation mode for ${probe_type}:${NC}"
    print_empty_line
    
    # Show current mode
    local current_mode="${WIZARD_STATE[probe_mode]:-not set}"
    print_box_line "Current: ${BWHITE}${current_mode}${NC}"
    print_empty_line
    
    local prox_sel=$([[ "$current_mode" == "proximity" ]] && echo "done" || echo "")
    local touch_sel=$([[ "$current_mode" == "touch" ]] && echo "done" || echo "")
    
    # Proximity/Scan mode
    print_box_line "${BWHITE}Contactless Modes:${NC}"
    print_menu_item "1" "$prox_sel" "Proximity/Scan Mode" "Contactless sensing (standard)"
    print_box_line "    ${DIM}Uses eddy current induction to detect bed distance${NC}"
    print_box_line "    ${DIM}Good for rapid bed mesh scanning${NC}"
    print_empty_line
    
    # Touch/Tap mode
    print_box_line "${BWHITE}Contact Modes:${NC}"
    
    # Show different descriptions based on probe type
    case "$probe_type" in
        beacon)
            print_menu_item "2" "$touch_sel" "Contact Mode" "Physical contact homing (Rev H+ only)"
            print_box_line "    ${DIM}Probe physically touches bed for Z reference${NC}"
            print_box_line "    ${DIM}Higher precision, requires Beacon Rev H or later${NC}"
            ;;
        cartographer)
            print_menu_item "2" "$touch_sel" "Touch Mode" "Physical contact homing"
            print_box_line "    ${DIM}Uses touch sensing for Z reference${NC}"
            print_box_line "    ${DIM}Scan for mesh, touch for homing${NC}"
            ;;
        btt-eddy)
            print_menu_item "2" "$touch_sel" "Touch Mode" "Physical contact homing"
            print_box_line "    ${DIM}Uses tap detection for Z reference${NC}"
            print_box_line "    ${DIM}More precise than proximity for homing${NC}"
            ;;
    esac
    
    print_separator
    print_action_item "B" "Back (keep current)"
    print_footer
    
    echo -en "${BYELLOW}Select mode${NC}: "
    read -r choice
    
    case "$choice" in
        1)
            WIZARD_STATE[probe_mode]="proximity"
            echo -e "${GREEN}✓${NC} Operation mode set to: proximity"
            sleep 1
            ;;
        2)
            # For Beacon, check hardware revision
            if [[ "$probe_type" == "beacon" ]]; then
                menu_beacon_revision
            else
                WIZARD_STATE[probe_mode]="touch"
                echo -e "${GREEN}✓${NC} Operation mode set to: touch"
                sleep 1
            fi
            ;;
        [bB]) return ;;
        *) ;;
    esac
    
    save_state
}

menu_beacon_revision() {
    clear_screen
    print_header "Beacon Hardware Revision"
    
    print_box_line "${BWHITE}Select your Beacon hardware revision:${NC}"
    print_empty_line
    print_box_line "${YELLOW}Note: Contact mode requires Rev H or later hardware.${NC}"
    print_box_line "${YELLOW}Check your Beacon - revision is printed on the PCB.${NC}"
    print_empty_line
    
    local current_rev="${WIZARD_STATE[beacon_revision]:-not set}"
    print_box_line "Current: ${BWHITE}${current_rev}${NC}"
    print_empty_line
    
    local revd_sel=$([[ "$current_rev" == "revd" ]] && echo "done" || echo "")
    local revh_sel=$([[ "$current_rev" == "revh" ]] && echo "done" || echo "")
    
    print_menu_item "1" "$revd_sel" "Rev D or earlier" "Proximity mode only"
    print_menu_item "2" "$revh_sel" "Rev H or later" "Contact mode supported"
    
    print_separator
    print_action_item "B" "Back"
    print_footer
    
    echo -en "${BYELLOW}Select revision${NC}: "
    read -r choice
    
    case "$choice" in
        1)
            WIZARD_STATE[beacon_revision]="revd"
            WIZARD_STATE[probe_mode]="proximity"
            echo -e "${YELLOW}Rev D selected - using proximity mode (contact not supported)${NC}"
            sleep 2
            ;;
        2)
            WIZARD_STATE[beacon_revision]="revh"
            WIZARD_STATE[probe_mode]="touch"
            echo -e "${GREEN}✓${NC} Rev H selected - contact mode enabled"
            sleep 1
            ;;
        [bB]) return ;;
        *) ;;
    esac
    
    save_state
}

# Legacy probe menu - redirects to new endstops menu
menu_probe() {
    while true; do
        clear_screen
        print_header "Probe Configuration"

        print_box_line "${BWHITE}Configure your Z probe:${NC}"
        print_empty_line

        # Current probe type
        local probe_type="${WIZARD_STATE[probe_type]:-not selected}"
        local type_status=$([[ -n "${WIZARD_STATE[probe_type]}" ]] && echo "done" || echo "")
        print_menu_item "1" "$type_status" "Probe Type" "$probe_type"

        # Show module installation status for probes that need it
        local current_probe="${WIZARD_STATE[probe_type]}"
        if [[ "$current_probe" =~ ^(beacon|cartographer|btt-eddy)$ ]]; then
            print_empty_line
            local install_status=""
            local install_info=""
            if is_probe_installed "$current_probe"; then
                install_status="done"
                install_info="${GREEN}installed${NC}"
            else
                install_info="${YELLOW}not installed${NC}"
            fi
            print_menu_item "2" "$install_status" "Install ${current_probe} Module" "$install_info"
        fi

        # Port/MCU assignment (for probes that need it)
        if [[ -n "$current_probe" && "$current_probe" != "endstop" ]]; then
            print_empty_line
            local port_info=""
            if [[ -n "${WIZARD_STATE[probe_serial]}" ]]; then
                port_info="USB: ${WIZARD_STATE[probe_serial]}"
            elif [[ -n "${WIZARD_STATE[probe_canbus_uuid]}" ]]; then
                port_info="CAN: ${WIZARD_STATE[probe_canbus_uuid]}"
            elif [[ -n "${HARDWARE_STATE[probe_pin]}" ]]; then
                port_info="Pin: ${HARDWARE_STATE[probe_pin]}"
            else
                port_info="not configured"
            fi
            local port_status=$([[ "$port_info" != "not configured" ]] && echo "done" || echo "")
            print_menu_item "3" "$port_status" "Connection / Port" "$port_info"
        fi

        # Z endstop position (only for physical endstop)
        if [[ "$current_probe" == "endstop" ]]; then
            print_empty_line
            local endstop_pos="${WIZARD_STATE[z_endstop_position]:-not set}"
            local endstop_status=$([[ -n "${WIZARD_STATE[z_endstop_position]}" ]] && echo "done" || echo "")
            print_menu_item "3" "$endstop_status" "Z Endstop Position" "$endstop_pos"
        fi

        # Z homing position (for all probes except none)
        if [[ -n "$current_probe" && "$current_probe" != "none" ]]; then
            print_empty_line
            local bed_x="${WIZARD_STATE[bed_size_x]:-300}"
            local bed_y="${WIZARD_STATE[bed_size_y]:-300}"
            local z_home_x="${WIZARD_STATE[z_home_x]:-$((bed_x / 2))}"
            local z_home_y="${WIZARD_STATE[z_home_y]:-$((bed_y / 2))}"
            local z_home_info="X:${z_home_x}, Y:${z_home_y}"
            local z_home_status=$([[ -n "${WIZARD_STATE[z_home_x]}" ]] && echo "done" || echo "")
            print_menu_item "4" "$z_home_status" "Z Homing Position" "$z_home_info"
            
            # Mesh margin
            local mesh_margin="${WIZARD_STATE[mesh_margin]:-30}"
            local mesh_status=$([[ -n "${WIZARD_STATE[mesh_margin]}" ]] && echo "done" || echo "")
            print_menu_item "5" "$mesh_status" "Mesh Edge Margin" "${mesh_margin}mm from edges"
        fi

        print_separator
        print_action_item "B" "Back"
        print_footer

        echo -en "${BYELLOW}Select option${NC}: "
        read -r choice

        case "$choice" in
            1) menu_probe_type_select ;;
            2)
                if [[ "$current_probe" =~ ^(beacon|cartographer|btt-eddy)$ ]]; then
                    if is_probe_installed "$current_probe"; then
                        echo -e "${GREEN}${current_probe} module is already installed.${NC}"
                        sleep 1
                    else
                        if confirm "Install ${current_probe} module now?"; then
                            install_probe_module "$current_probe"
                            wait_for_key
                        fi
                    fi
                fi
                ;;
            3)
                if [[ "$current_probe" == "endstop" ]]; then
                    menu_z_endstop_position
                elif [[ -n "$current_probe" ]]; then
                    menu_probe_port_or_mcu
                fi
                ;;
            4)
                if [[ -n "$current_probe" && "$current_probe" != "none" ]]; then
                    menu_z_homing_position
                fi
                ;;
            5)
                if [[ -n "$current_probe" && "$current_probe" != "none" ]]; then
                    menu_mesh_margin
                fi
                ;;
            [bB]) return ;;
        esac
    done
}

menu_probe_type_select() {
    clear_screen
    print_header "Select Probe Type"

    # Get current probe type for checkmark display
    local current_probe="${WIZARD_STATE[probe_type]}"

    # Show installation status for probes that need modules
    local beacon_status="" carto_status="" eddy_status=""
    if is_probe_installed "beacon"; then
        beacon_status="${GREEN}[installed]${NC}"
    else
        beacon_status="${YELLOW}[not installed]${NC}"
    fi
    if is_probe_installed "cartographer"; then
        carto_status="${GREEN}[installed]${NC}"
    else
        carto_status="${YELLOW}[not installed]${NC}"
    fi
    if is_probe_installed "btt-eddy"; then
        eddy_status="${GREEN}[installed]${NC}"
    else
        eddy_status="${YELLOW}[not installed]${NC}"
    fi

    # Calculate selection status for each option
    local bltouch_sel=$([[ "$current_probe" == "bltouch" ]] && echo "done" || echo "")
    local klicky_sel=$([[ "$current_probe" == "klicky" ]] && echo "done" || echo "")
    local inductive_sel=$([[ "$current_probe" == "inductive" ]] && echo "done" || echo "")
    local endstop_sel=$([[ "$current_probe" == "endstop" ]] && echo "done" || echo "")
    local beacon_sel=$([[ "$current_probe" == "beacon" ]] && echo "done" || echo "")
    local carto_sel=$([[ "$current_probe" == "cartographer" ]] && echo "done" || echo "")
    local eddy_sel=$([[ "$current_probe" == "btt-eddy" ]] && echo "done" || echo "")

    print_box_line "${BWHITE}Standard Probes:${NC}"
    print_menu_item "1" "$bltouch_sel" "BLTouch / 3DTouch"
    print_menu_item "2" "$klicky_sel" "Klicky Probe"
    print_menu_item "3" "$inductive_sel" "Inductive Probe (PINDA/SuperPINDA)"
    print_menu_item "4" "$endstop_sel" "Physical Z Endstop (no probe)"
    print_empty_line
    print_box_line "${BWHITE}Eddy Current Probes (require module):${NC}"
    print_menu_item "5" "$beacon_sel" "Beacon" "${beacon_status}"
    print_menu_item "6" "$carto_sel" "Cartographer" "${carto_status}"
    print_menu_item "7" "$eddy_sel" "BTT Eddy" "${eddy_status}"
    print_separator
    print_action_item "B" "Back"
    print_footer

    echo -en "${BYELLOW}Select probe${NC}: "
    read -r choice

    case "$choice" in
        1)
            WIZARD_STATE[probe_type]="bltouch"
            echo -e "${GREEN}✓${NC} BLTouch selected"
            sleep 1
            ;;
        2)
            WIZARD_STATE[probe_type]="klicky"
            echo -e "${GREEN}✓${NC} Klicky Probe selected"
            sleep 1
            ;;
        3)
            WIZARD_STATE[probe_type]="inductive"
            echo -e "${GREEN}✓${NC} Inductive Probe selected"
            sleep 1
            ;;
        4)
            WIZARD_STATE[probe_type]="endstop"
            echo -e "${GREEN}✓${NC} Physical Z Endstop selected"
            sleep 1
            ;;
        5)
            WIZARD_STATE[probe_type]="beacon"
            echo -e "${GREEN}✓${NC} Beacon selected"
            if ! is_probe_installed "beacon"; then
                echo -e "${YELLOW}Note: Module not installed. Use option 2 to install when ready.${NC}"
            fi
            sleep 1
            ;;
        6)
            WIZARD_STATE[probe_type]="cartographer"
            echo -e "${GREEN}✓${NC} Cartographer selected"
            if ! is_probe_installed "cartographer"; then
                echo -e "${YELLOW}Note: Module not installed. Use option 2 to install when ready.${NC}"
            fi
            sleep 1
            ;;
        7)
            WIZARD_STATE[probe_type]="btt-eddy"
            echo -e "${GREEN}✓${NC} BTT Eddy selected"
            if ! is_probe_installed "btt-eddy"; then
                echo -e "${YELLOW}Note: Module not installed. Use option 2 to install when ready.${NC}"
            fi
            sleep 1
            ;;
        [bB]) return ;;
    esac

    # Save state after probe type selection
    save_state
}

menu_z_homing_position() {
    clear_screen
    print_header "Z Homing Position"
    
    print_box_line "${BWHITE}Configure where the toolhead moves before Z homing:${NC}"
    print_empty_line
    print_box_line "This is the XY position where the probe will home Z."
    print_box_line "For most setups, the center of the bed is a good choice."
    print_box_line "For Voron TAP or nozzle probes, this should be on the bed."
    print_empty_line
    
    # Get bed size for defaults
    local bed_x="${WIZARD_STATE[bed_size_x]:-300}"
    local bed_y="${WIZARD_STATE[bed_size_y]:-300}"
    local default_x=$((bed_x / 2))
    local default_y=$((bed_y / 2))
    
    # Current values
    local current_x="${WIZARD_STATE[z_home_x]:-$default_x}"
    local current_y="${WIZARD_STATE[z_home_y]:-$default_y}"
    
    print_box_line "Bed size: ${bed_x}mm x ${bed_y}mm"
    print_box_line "Current Z home position: X=${current_x}, Y=${current_y}"
    print_empty_line
    
    print_separator
    print_footer
    
    echo -en "  " >&2
    WIZARD_STATE[z_home_x]=$(prompt_input "Z homing X position (mm)" "$current_x")
    echo -en "  " >&2
    WIZARD_STATE[z_home_y]=$(prompt_input "Z homing Y position (mm)" "$current_y")
    
    echo -e "${GREEN}✓${NC} Z homing position set to: X=${WIZARD_STATE[z_home_x]}, Y=${WIZARD_STATE[z_home_y]}"
    sleep 1
    
    save_state
}

menu_mesh_margin() {
    clear_screen
    print_header "Bed Mesh Edge Margin"
    
    print_box_line "${BWHITE}Configure the margin from bed edges for mesh probing:${NC}"
    print_empty_line
    print_box_line "This is how far from each edge the bed mesh will start/end."
    print_box_line "A larger margin keeps the probe away from bed clips or edges."
    print_box_line "Klipper automatically compensates for probe offset."
    print_empty_line
    
    # Get bed size for context
    local bed_x="${WIZARD_STATE[bed_size_x]:-300}"
    local bed_y="${WIZARD_STATE[bed_size_y]:-300}"
    local current_margin="${WIZARD_STATE[mesh_margin]:-30}"
    
    print_box_line "Bed size: ${bed_x}mm x ${bed_y}mm"
    print_box_line "Current margin: ${current_margin}mm from all edges"
    print_box_line "Mesh area will be: (${current_margin}, ${current_margin}) to ($((bed_x - current_margin)), $((bed_y - current_margin)))"
    print_empty_line
    
    print_separator
    print_footer
    
    echo -en "  " >&2
    WIZARD_STATE[mesh_margin]=$(prompt_input "Edge margin (mm)" "$current_margin")
    
    local new_margin="${WIZARD_STATE[mesh_margin]}"
    echo -e "${GREEN}✓${NC} Mesh area: (${new_margin}, ${new_margin}) to ($((bed_x - new_margin)), $((bed_y - new_margin)))"
    sleep 1
    
    save_state
}

# ═══════════════════════════════════════════════════════════════════════════════
# FAN CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

menu_fans() {
    while true; do
        clear_screen
        print_header "Fan Configuration"
        
        print_box_line "${BWHITE}Configure your printer's fans:${NC}"
        print_empty_line
        
        # Helper function to get fan port info
        get_fan_port_info() {
            local fan_key="$1"
            local port=""
            if [[ -n "${HARDWARE_STATE[toolboard_${fan_key}]}" ]]; then
                port="toolboard:${HARDWARE_STATE[toolboard_${fan_key}]}"
            elif [[ -n "${HARDWARE_STATE[${fan_key}]}" ]]; then
                port="${HARDWARE_STATE[${fan_key}]}"
            fi
            # Check for multi-pin
            if [[ -n "${HARDWARE_STATE[${fan_key}_pin2]}" ]]; then
                port="${port} (multi-pin)"
            fi
            echo "${port:-not configured}"
        }

        # Helper function to get fan status
        get_fan_status() {
            local fan_key="$1"
            if [[ -n "${HARDWARE_STATE[toolboard_${fan_key}]}" ]] || [[ -n "${HARDWARE_STATE[${fan_key}]}" ]]; then
                echo "[✓]"
            else
                echo "[ ]"
            fi
        }

        # Display fan type descriptions
        print_box_line "${BWHITE}Essential Fans:${NC}"
        local pc_status=$(get_fan_status "fan_part_cooling")
        local pc_info=$(get_fan_port_info "fan_part_cooling")
        print_box_line "${GREEN}1)${NC} ${pc_status} Part Cooling Fan [fan] - ${CYAN}${pc_info}${NC}"

        local he_status=$(get_fan_status "fan_hotend")
        local he_info=$(get_fan_port_info "fan_hotend")
        print_box_line "${GREEN}2)${NC} ${he_status} Hotend Fan [heater_fan] - ${CYAN}${he_info}${NC}"

        local cf_status=$(get_fan_status "fan_controller")
        local cf_info=$(get_fan_port_info "fan_controller")
        print_box_line "${GREEN}3)${NC} ${cf_status} Controller Fan [controller_fan] - ${CYAN}${cf_info}${NC}"

        print_empty_line
        print_box_line "${BWHITE}Optional Fans:${NC}"

        local ex_status=$(get_fan_status "fan_exhaust")
        local ex_info=$(get_fan_port_info "fan_exhaust")
        print_box_line "${GREEN}4)${NC} ${ex_status} Exhaust Fan [fan_generic] - ${CYAN}${ex_info}${NC}"

        local ch_status=$(get_fan_status "fan_chamber")
        local ch_info=$(get_fan_port_info "fan_chamber")
        if [[ "${WIZARD_STATE[fan_chamber_type]}" == "temperature" ]]; then
            ch_info="${ch_info} (temp-controlled)"
        fi
        print_box_line "${GREEN}5)${NC} ${ch_status} Chamber Fan [fan_generic/temperature_fan] - ${CYAN}${ch_info}${NC}"

        local rs_status=$(get_fan_status "fan_rscs")
        local rs_info=$(get_fan_port_info "fan_rscs")
        print_box_line "${GREEN}6)${NC} ${rs_status} RSCS/Filter Fan [fan_generic] - ${CYAN}${rs_info}${NC}"

        local rd_status=$(get_fan_status "fan_radiator")
        local rd_info=$(get_fan_port_info "fan_radiator")
        print_box_line "${GREEN}7)${NC} ${rd_status} Radiator Fan [heater_fan] - ${CYAN}${rd_info}${NC}"
        
        print_separator
        print_action_item "A" "Advanced Fan Settings (PWM, max_power, etc.)"
        print_action_item "B" "Back"
        print_footer
        
        echo -en "${BYELLOW}Select fan to configure${NC}: "
        read -r choice
        
        case "$choice" in
            1) menu_fan_part_cooling ;;
            2) menu_fan_hotend ;;
            3) menu_fan_controller ;;
            4) menu_fan_exhaust ;;
            5) menu_fan_chamber ;;
            6) menu_fan_rscs ;;
            7) menu_fan_radiator ;;
            [aA]) menu_fan_advanced_select ;;
            [bB]) return ;;
            *) ;;
        esac
    done
}

menu_fan_part_cooling() {
    while true; do
        clear_screen
        print_header "Part Cooling Fan [fan]"

        print_box_line "${BWHITE}Part cooling fan controlled by M106/M107${NC}"
        print_box_line "This is the main print cooling fan."
        print_empty_line

        # Determine current port assignment (toolboard or mainboard)
        local primary_port=""
        local secondary_port=""
        if [[ -n "${HARDWARE_STATE[toolboard_fan_part_cooling]}" ]]; then
            primary_port="toolboard:${HARDWARE_STATE[toolboard_fan_part_cooling]}"
        elif [[ -n "${HARDWARE_STATE[fan_part_cooling]}" ]]; then
            primary_port="${HARDWARE_STATE[fan_part_cooling]}"
        fi
        [[ -n "${HARDWARE_STATE[fan_part_cooling_pin2]}" ]] && secondary_port="${HARDWARE_STATE[fan_part_cooling_pin2]}"

        # Display current status
        local primary_status=$([[ -n "$primary_port" ]] && echo "done" || echo "")
        local primary_info="${primary_port:-not assigned}"
        print_menu_item "1" "$primary_status" "Fan Port" "$primary_info"

        local secondary_status=$([[ -n "$secondary_port" ]] && echo "done" || echo "")
        local secondary_info="${secondary_port:-not set}"
        print_menu_item "2" "$secondary_status" "Multi-pin (2nd fan)" "$secondary_info"

        print_separator
        print_action_item "C" "Clear (disable fan)"
        print_action_item "B" "Back"
        print_footer

        echo -en "${BYELLOW}Select option${NC}: "
        read -r choice

        case "$choice" in
            1)
                if [[ -n "${WIZARD_STATE[board]}" ]]; then
                    save_state
                    python3 "${SCRIPT_DIR}/setup-hardware.py" --fan "fan_part_cooling"
                    load_hardware_state
                else
                    echo -e "${YELLOW}Select a main board first${NC}"
                    sleep 1
                fi
                ;;
            2)
                if [[ -n "${WIZARD_STATE[board]}" ]]; then
                    save_state
                    python3 "${SCRIPT_DIR}/setup-hardware.py" --fan-multipin "fan_part_cooling"
                    load_hardware_state
                else
                    echo -e "${YELLOW}Select a main board first${NC}"
                    sleep 1
                fi
                ;;
            [cC])
                # Clear fan assignment via Python script
                save_state
                python3 "${SCRIPT_DIR}/setup-hardware.py" --clear-port "fan_part_cooling"
                python3 "${SCRIPT_DIR}/setup-hardware.py" --clear-port "fan_part_cooling_2"
                load_hardware_state
                echo -e "${GREEN}✓${NC} Part cooling fan cleared"
                sleep 1
                ;;
            [bB]) return ;;
        esac
    done
}

# Generic fan port assignment helper
# Usage: menu_fan_port_assign <fan_key> <fan_display_name>
menu_fan_port_assign() {
    local fan_key="$1"
    local fan_name="$2"
    local is_multipin="${WIZARD_STATE[${fan_key}_multipin]}"

    save_state

    if [[ "$is_multipin" == "yes" ]]; then
        # Multi-pin assignment
        python3 "${SCRIPT_DIR}/setup-hardware.py" --fan-multipin "${fan_key}"
    else
        # Single pin assignment
        python3 "${SCRIPT_DIR}/setup-hardware.py" --fan "${fan_key}"
    fi

    load_hardware_state
}

menu_fan_hotend() {
    while true; do
        clear_screen

        # Determine fan type for header (default to heater for hotend cooling)
        local fan_type="${WIZARD_STATE[fan_hotend_type]:-heater}"
        local header_type="heater_fan"
        [[ "$fan_type" == "manual" ]] && header_type="fan_generic"
        [[ "$fan_type" == "temperature" ]] && header_type="temperature_fan"
        print_header "Hotend Fan [$header_type]"

        print_box_line "${BWHITE}Hotend cooling fan (heat sink / cold end)${NC}"
        print_box_line "Typically runs when extruder is hot to cool the heat break."
        print_empty_line

        # Determine current port assignment (toolboard or mainboard)
        local primary_port=""
        local secondary_port=""
        if [[ -n "${HARDWARE_STATE[toolboard_fan_hotend]}" ]]; then
            primary_port="toolboard:${HARDWARE_STATE[toolboard_fan_hotend]}"
        elif [[ -n "${HARDWARE_STATE[fan_hotend]}" ]]; then
            primary_port="${HARDWARE_STATE[fan_hotend]}"
        fi
        [[ -n "${HARDWARE_STATE[fan_hotend_pin2]}" ]] && secondary_port="${HARDWARE_STATE[fan_hotend_pin2]}"

        # Display current status
        local primary_status=$([[ -n "$primary_port" ]] && echo "done" || echo "")
        local primary_info="${primary_port:-not assigned}"
        print_menu_item "1" "$primary_status" "Fan Port" "$primary_info"

        local secondary_status=$([[ -n "$secondary_port" ]] && echo "done" || echo "")
        local secondary_info="${secondary_port:-not set}"
        print_menu_item "2" "$secondary_status" "Multi-pin (2nd fan)" "$secondary_info"

        # Control mode
        local control_status="done"
        local control_info="$fan_type"
        print_menu_item "3" "$control_status" "Control Mode" "$control_info"

        print_separator
        print_action_item "C" "Clear (disable fan)"
        print_action_item "B" "Back"
        print_footer

        echo -en "${BYELLOW}Select option${NC}: "
        read -r choice

        case "$choice" in
            1)
                if [[ -n "${WIZARD_STATE[board]}" ]]; then
                    save_state
                    python3 "${SCRIPT_DIR}/setup-hardware.py" --fan "fan_hotend"
                    load_hardware_state
                else
                    echo -e "${YELLOW}Select a main board first${NC}"
                    sleep 1
                fi
                ;;
            2)
                if [[ -n "${WIZARD_STATE[board]}" ]]; then
                    save_state
                    python3 "${SCRIPT_DIR}/setup-hardware.py" --fan-multipin "fan_hotend"
                    load_hardware_state
                else
                    echo -e "${YELLOW}Select a main board first${NC}"
                    sleep 1
                fi
                ;;
            3)
                menu_fan_control_mode "hotend" "Hotend Fan"
                save_state
                ;;
            [cC])
                save_state
                python3 "${SCRIPT_DIR}/setup-hardware.py" --clear-port "fan_hotend"
                python3 "${SCRIPT_DIR}/setup-hardware.py" --clear-port "fan_hotend_pin2"
                WIZARD_STATE[fan_hotend_type]=""
                WIZARD_STATE[fan_hotend_heater]=""
                WIZARD_STATE[fan_hotend_heater_temp]=""
                WIZARD_STATE[fan_hotend_sensor_type]=""
                WIZARD_STATE[fan_hotend_target_temp]=""
                load_hardware_state
                save_state
                echo -e "${GREEN}✓${NC} Hotend fan cleared"
                sleep 1
                ;;
            [bB]) return ;;
        esac
    done
}

menu_fan_controller() {
    while true; do
        clear_screen

        # Determine fan type for header (default to controller for electronics cooling)
        local fan_type="${WIZARD_STATE[fan_controller_type]:-controller}"
        local header_type="controller_fan"
        [[ "$fan_type" == "manual" ]] && header_type="fan_generic"
        [[ "$fan_type" == "heater" ]] && header_type="heater_fan"
        print_header "Controller Fan [$header_type]"

        print_box_line "${BWHITE}Electronics cooling fan${NC}"
        print_box_line "Cools MCU/drivers. Typically runs when steppers active."
        print_empty_line

        # Determine current port assignment
        local primary_port="${HARDWARE_STATE[fan_controller]}"
        local secondary_port="${HARDWARE_STATE[fan_controller_pin2]}"

        # Display current status
        local primary_status=$([[ -n "$primary_port" ]] && echo "done" || echo "")
        local primary_info="${primary_port:-not assigned}"
        print_menu_item "1" "$primary_status" "Fan Port" "$primary_info"

        local secondary_status=$([[ -n "$secondary_port" ]] && echo "done" || echo "")
        local secondary_info="${secondary_port:-not set}"
        print_menu_item "2" "$secondary_status" "Multi-pin (2nd fan)" "$secondary_info"

        # Control mode
        local control_status="done"
        local control_info="$fan_type"
        print_menu_item "3" "$control_status" "Control Mode" "$control_info"

        print_separator
        print_action_item "C" "Clear (disable fan)"
        print_action_item "B" "Back"
        print_footer

        echo -en "${BYELLOW}Select option${NC}: "
        read -r choice

        case "$choice" in
            1)
                if [[ -n "${WIZARD_STATE[board]}" ]]; then
                    save_state
                    python3 "${SCRIPT_DIR}/setup-hardware.py" --fan "fan_controller"
                    load_hardware_state
                else
                    echo -e "${YELLOW}Select a main board first${NC}"
                    sleep 1
                fi
                ;;
            2)
                if [[ -n "${WIZARD_STATE[board]}" ]]; then
                    save_state
                    python3 "${SCRIPT_DIR}/setup-hardware.py" --fan-multipin "fan_controller"
                    load_hardware_state
                else
                    echo -e "${YELLOW}Select a main board first${NC}"
                    sleep 1
                fi
                ;;
            3)
                menu_fan_controller_mode
                ;;
            [cC])
                save_state
                python3 "${SCRIPT_DIR}/setup-hardware.py" --clear-port "fan_controller"
                python3 "${SCRIPT_DIR}/setup-hardware.py" --clear-port "fan_controller_pin2"
                WIZARD_STATE[fan_controller_type]=""
                WIZARD_STATE[fan_controller_heater]=""
                WIZARD_STATE[fan_controller_heater_temp]=""
                load_hardware_state
                save_state
                echo -e "${GREEN}✓${NC} Controller fan cleared"
                sleep 1
                ;;
            [bB]) return ;;
        esac
    done
}

menu_fan_exhaust() {
    while true; do
        clear_screen

        # Determine fan type for header
        local fan_type="${WIZARD_STATE[fan_exhaust_type]:-manual}"
        local header_type="fan_generic"
        [[ "$fan_type" == "heater" ]] && header_type="heater_fan"
        [[ "$fan_type" == "temperature" ]] && header_type="temperature_fan"
        print_header "Exhaust Fan [$header_type]"

        print_box_line "${BWHITE}Enclosure exhaust fan${NC}"
        print_box_line "Removes hot air / controls chamber temperature."
        print_empty_line

        # Determine current port assignment
        local primary_port="${HARDWARE_STATE[fan_exhaust]}"
        local secondary_port="${HARDWARE_STATE[fan_exhaust_pin2]}"

        # Display current status
        local primary_status=$([[ -n "$primary_port" ]] && echo "done" || echo "")
        local primary_info="${primary_port:-not assigned}"
        print_menu_item "1" "$primary_status" "Fan Port" "$primary_info"

        local secondary_status=$([[ -n "$secondary_port" ]] && echo "done" || echo "")
        local secondary_info="${secondary_port:-not set}"
        print_menu_item "2" "$secondary_status" "Multi-pin (2nd fan)" "$secondary_info"

        print_empty_line

        # Control mode selection
        local type_status=$([[ -n "${WIZARD_STATE[fan_exhaust_type]}" ]] && echo "done" || echo "")
        local type_info="${WIZARD_STATE[fan_exhaust_type]:-manual}"
        case "$type_info" in
            heater)
                local heater="${WIZARD_STATE[fan_exhaust_heater]:-extruder}"
                local temp="${WIZARD_STATE[fan_exhaust_heater_temp]:-50}"
                type_info="heater-triggered ($heater @ ${temp}°C)"
                ;;
            temperature)
                local target="${WIZARD_STATE[fan_exhaust_target_temp]:-45}"
                type_info="temp-controlled (target ${target}°C)"
                ;;
        esac
        print_menu_item "3" "$type_status" "Control Mode" "$type_info"

        print_separator
        print_action_item "C" "Clear (disable fan)"
        print_action_item "B" "Back"
        print_footer

        echo -en "${BYELLOW}Select option${NC}: "
        read -r choice

        case "$choice" in
            1)
                if [[ -n "${WIZARD_STATE[board]}" ]]; then
                    save_state
                    python3 "${SCRIPT_DIR}/setup-hardware.py" --fan "fan_exhaust"
                    load_hardware_state
                else
                    echo -e "${YELLOW}Select a main board first${NC}"
                    sleep 1
                fi
                ;;
            2)
                if [[ -n "${WIZARD_STATE[board]}" ]]; then
                    save_state
                    python3 "${SCRIPT_DIR}/setup-hardware.py" --fan-multipin "fan_exhaust"
                    load_hardware_state
                else
                    echo -e "${YELLOW}Select a main board first${NC}"
                    sleep 1
                fi
                ;;
            3)
                menu_fan_control_mode "exhaust" "exhaust_fan"
                ;;
            [cC])
                save_state
                python3 "${SCRIPT_DIR}/setup-hardware.py" --clear-port "fan_exhaust"
                python3 "${SCRIPT_DIR}/setup-hardware.py" --clear-port "fan_exhaust_2"
                WIZARD_STATE[fan_exhaust_type]=""
                WIZARD_STATE[fan_exhaust_heater]=""
                WIZARD_STATE[fan_exhaust_heater_temp]=""
                WIZARD_STATE[fan_exhaust_sensor_type]=""
                WIZARD_STATE[fan_exhaust_target_temp]=""
                load_hardware_state
                echo -e "${GREEN}✓${NC} Exhaust fan cleared"
                sleep 1
                ;;
            [bB]) return ;;
        esac
    done
}

# Generic fan control mode selection menu
# Usage: menu_fan_control_mode <fan_key> <fan_display_name>
# fan_key: exhaust, chamber, radiator (used for state variable prefix)
# fan_display_name: exhaust_fan, chamber_fan, radiator_fan (for display)
menu_fan_control_mode() {
    local fan_key="$1"
    local fan_display="$2"

    clear_screen
    print_header "${fan_display} Control Mode"

    print_box_line "${BWHITE}Select control mode:${NC}"
    print_empty_line
    print_menu_item "1" "" "Manual [fan_generic]" "SET_FAN_SPEED control"
    print_menu_item "2" "" "Heater-triggered [heater_fan]" "ON when heater reaches temp"
    print_menu_item "3" "" "Temperature-controlled [temperature_fan]" "Maintain target temp"
    print_separator
    print_action_item "B" "Back"
    print_footer

    echo -en "${BYELLOW}Select mode${NC}: "
    read -r choice

    case "$choice" in
        1)
            WIZARD_STATE[fan_${fan_key}_type]="manual"
            # Clear heater/temp settings
            WIZARD_STATE[fan_${fan_key}_heater]=""
            WIZARD_STATE[fan_${fan_key}_heater_temp]=""
            WIZARD_STATE[fan_${fan_key}_sensor_type]=""
            WIZARD_STATE[fan_${fan_key}_target_temp]=""
            save_state
            echo -e "${GREEN}✓${NC} Set to manual control"
            sleep 1
            ;;
        2)
            WIZARD_STATE[fan_${fan_key}_type]="heater"
            # Clear temperature settings
            WIZARD_STATE[fan_${fan_key}_sensor_type]=""
            WIZARD_STATE[fan_${fan_key}_target_temp]=""
            menu_fan_heater_settings "$fan_key" "$fan_display"
            ;;
        3)
            WIZARD_STATE[fan_${fan_key}_type]="temperature"
            # Clear heater settings
            WIZARD_STATE[fan_${fan_key}_heater]=""
            WIZARD_STATE[fan_${fan_key}_heater_temp]=""
            menu_fan_temp_settings "$fan_key" "$fan_display"
            ;;
        [bB]) return ;;
    esac
}

# Heater-triggered fan settings
# Usage: menu_fan_heater_settings <fan_key> <fan_display_name>
menu_fan_heater_settings() {
    local fan_key="$1"
    local fan_display="$2"

    clear_screen
    print_header "${fan_display} Heater Settings"

    print_box_line "${BWHITE}Select which heater triggers this fan:${NC}"
    print_empty_line
    print_menu_item "1" "" "Extruder" "Fan runs when hotend is hot"
    print_menu_item "2" "" "Heated Bed" "Fan runs when bed is hot"
    print_menu_item "3" "" "Both (extruder + bed)" "Fan runs when either is hot"
    print_footer

    echo -en "${BYELLOW}Select heater${NC}: "
    read -r choice

    case "$choice" in
        1) WIZARD_STATE[fan_${fan_key}_heater]="extruder" ;;
        2) WIZARD_STATE[fan_${fan_key}_heater]="heater_bed" ;;
        3) WIZARD_STATE[fan_${fan_key}_heater]="extruder, heater_bed" ;;
        *) WIZARD_STATE[fan_${fan_key}_heater]="extruder" ;;
    esac

    # Temperature threshold
    echo ""
    echo -en "  Activation temperature (°C) [50]: "
    read -r heater_temp
    WIZARD_STATE[fan_${fan_key}_heater_temp]="${heater_temp:-50}"

    save_state
    echo -e "${GREEN}✓${NC} Heater fan configured: ${WIZARD_STATE[fan_${fan_key}_heater]} @ ${WIZARD_STATE[fan_${fan_key}_heater_temp]}°C"
    sleep 1
}

# Temperature-controlled fan settings
# Usage: menu_fan_temp_settings <fan_key> <fan_display_name>
menu_fan_temp_settings() {
    local fan_key="$1"
    local fan_display="$2"

    clear_screen
    print_header "${fan_display} Temperature Settings"

    print_box_line "${BWHITE}Configure temperature-controlled fan${NC}"
    print_box_line "Requires a temperature sensor to monitor."
    print_empty_line

    # Sensor type selection
    print_box_line "${BWHITE}Temperature Sensor Type:${NC}"
    print_menu_item "1" "" "Generic 3950 (NTC 100K)"
    print_menu_item "2" "" "NTC 100K MGB18-104F39050L32"
    print_menu_item "3" "" "ATC Semitec 104GT-2"
    print_menu_item "4" "" "Use chamber sensor" "If already configured"
    print_footer

    echo -en "${BYELLOW}Select sensor type${NC}: "
    read -r choice

    case "$choice" in
        1) WIZARD_STATE[fan_${fan_key}_sensor_type]="Generic 3950" ;;
        2) WIZARD_STATE[fan_${fan_key}_sensor_type]="NTC 100K MGB18-104F39050L32" ;;
        3) WIZARD_STATE[fan_${fan_key}_sensor_type]="ATC Semitec 104GT-2" ;;
        4)
            # Use existing chamber sensor
            WIZARD_STATE[fan_${fan_key}_sensor_type]="chamber"
            ;;
        *) WIZARD_STATE[fan_${fan_key}_sensor_type]="Generic 3950" ;;
    esac

    # Target temperature
    echo ""
    echo -en "  Target temperature (°C) [45]: "
    read -r target_temp
    WIZARD_STATE[fan_${fan_key}_target_temp]="${target_temp:-45}"

    save_state
    echo -e "${GREEN}✓${NC} Temperature fan configured: target ${WIZARD_STATE[fan_${fan_key}_target_temp]}°C"
    sleep 1
}

# Controller fan specific control mode (has unique 'controller' option)
menu_fan_controller_mode() {
    clear_screen
    print_header "Controller Fan Control Mode"

    print_box_line "${BWHITE}Select control mode:${NC}"
    print_empty_line
    print_menu_item "1" "" "Controller [controller_fan]" "ON when steppers/heaters active"
    print_menu_item "2" "" "Manual [fan_generic]" "SET_FAN_SPEED control"
    print_menu_item "3" "" "Heater-triggered [heater_fan]" "ON when heater reaches temp"
    print_separator
    print_action_item "B" "Back"
    print_footer

    echo -en "${BYELLOW}Select mode${NC}: "
    read -r choice

    case "$choice" in
        1)
            WIZARD_STATE[fan_controller_type]="controller"
            WIZARD_STATE[fan_controller_heater]=""
            WIZARD_STATE[fan_controller_heater_temp]=""
            ;;
        2)
            WIZARD_STATE[fan_controller_type]="manual"
            WIZARD_STATE[fan_controller_heater]=""
            WIZARD_STATE[fan_controller_heater_temp]=""
            ;;
        3)
            WIZARD_STATE[fan_controller_type]="heater"
            menu_fan_heater_settings "controller" "Controller Fan"
            ;;
        [bB]) return ;;
    esac

    save_state
}

menu_fan_chamber() {
    while true; do
        clear_screen

        # Determine fan type for header
        local fan_type="${WIZARD_STATE[fan_chamber_type]:-manual}"
        local header_type="fan_generic"
        [[ "$fan_type" == "heater" ]] && header_type="heater_fan"
        [[ "$fan_type" == "temperature" ]] && header_type="temperature_fan"
        print_header "Chamber Fan [$header_type]"

        print_box_line "${BWHITE}Chamber circulation/heating fan${NC}"
        print_box_line "Can be manual or temperature-controlled."
        print_empty_line

        # Determine current port assignment
        local primary_port="${HARDWARE_STATE[fan_chamber]}"
        local secondary_port="${HARDWARE_STATE[fan_chamber_pin2]}"

        # Display current status
        local primary_status=$([[ -n "$primary_port" ]] && echo "done" || echo "")
        local primary_info="${primary_port:-not assigned}"
        print_menu_item "1" "$primary_status" "Fan Port" "$primary_info"

        local secondary_status=$([[ -n "$secondary_port" ]] && echo "done" || echo "")
        local secondary_info="${secondary_port:-not set}"
        print_menu_item "2" "$secondary_status" "Multi-pin (2nd fan)" "$secondary_info"

        print_empty_line

        # Fan type/mode selection
        local type_status=$([[ -n "${WIZARD_STATE[fan_chamber_type]}" ]] && echo "done" || echo "")
        local type_info="${WIZARD_STATE[fan_chamber_type]:-manual}"
        case "$type_info" in
            heater)
                local heater="${WIZARD_STATE[fan_chamber_heater]:-extruder}"
                local temp="${WIZARD_STATE[fan_chamber_heater_temp]:-50}"
                type_info="heater-triggered ($heater @ ${temp}°C)"
                ;;
            temperature)
                local target="${WIZARD_STATE[fan_chamber_target_temp]:-45}"
                type_info="temp-controlled (target ${target}°C)"
                ;;
        esac
        print_menu_item "3" "$type_status" "Control Mode" "$type_info"

        print_separator
        print_action_item "C" "Clear (disable fan)"
        print_action_item "B" "Back"
        print_footer

        echo -en "${BYELLOW}Select option${NC}: "
        read -r choice

        case "$choice" in
            1)
                if [[ -n "${WIZARD_STATE[board]}" ]]; then
                    save_state
                    python3 "${SCRIPT_DIR}/setup-hardware.py" --fan "fan_chamber"
                    load_hardware_state
                else
                    echo -e "${YELLOW}Select a main board first${NC}"
                    sleep 1
                fi
                ;;
            2)
                if [[ -n "${WIZARD_STATE[board]}" ]]; then
                    save_state
                    python3 "${SCRIPT_DIR}/setup-hardware.py" --fan-multipin "fan_chamber"
                    load_hardware_state
                else
                    echo -e "${YELLOW}Select a main board first${NC}"
                    sleep 1
                fi
                ;;
            3)
                menu_fan_control_mode "chamber" "chamber_fan"
                ;;
            [cC])
                save_state
                python3 "${SCRIPT_DIR}/setup-hardware.py" --clear-port "fan_chamber"
                python3 "${SCRIPT_DIR}/setup-hardware.py" --clear-port "fan_chamber_2"
                WIZARD_STATE[fan_chamber_type]=""
                WIZARD_STATE[fan_chamber_heater]=""
                WIZARD_STATE[fan_chamber_heater_temp]=""
                WIZARD_STATE[fan_chamber_sensor_type]=""
                WIZARD_STATE[fan_chamber_target_temp]=""
                load_hardware_state
                echo -e "${GREEN}✓${NC} Chamber fan cleared"
                sleep 1
                ;;
            [bB]) return ;;
        esac
    done
}

menu_fan_rscs() {
    while true; do
        clear_screen

        # Determine fan type for header
        local fan_type="${WIZARD_STATE[fan_rscs_type]:-manual}"
        local header_type="fan_generic"
        [[ "$fan_type" == "heater" ]] && header_type="heater_fan"
        [[ "$fan_type" == "temperature" ]] && header_type="temperature_fan"
        print_header "RSCS/Filter Fan [$header_type]"

        print_box_line "${BWHITE}Recirculating active carbon/HEPA filter fan${NC}"
        print_box_line "Air filtration for VOCs and particles."
        print_empty_line

        # Determine current port assignment
        local primary_port="${HARDWARE_STATE[fan_rscs]}"
        local secondary_port="${HARDWARE_STATE[fan_rscs_pin2]}"

        # Display current status
        local primary_status=$([[ -n "$primary_port" ]] && echo "done" || echo "")
        local primary_info="${primary_port:-not assigned}"
        print_menu_item "1" "$primary_status" "Fan Port" "$primary_info"

        local secondary_status=$([[ -n "$secondary_port" ]] && echo "done" || echo "")
        local secondary_info="${secondary_port:-not set}"
        print_menu_item "2" "$secondary_status" "Multi-pin (2nd fan)" "$secondary_info"

        # Control mode
        local control_status="done"
        local control_info="$fan_type"
        print_menu_item "3" "$control_status" "Control Mode" "$control_info"

        print_separator
        print_action_item "C" "Clear (disable fan)"
        print_action_item "B" "Back"
        print_footer

        echo -en "${BYELLOW}Select option${NC}: "
        read -r choice

        case "$choice" in
            1)
                if [[ -n "${WIZARD_STATE[board]}" ]]; then
                    save_state
                    python3 "${SCRIPT_DIR}/setup-hardware.py" --fan "fan_rscs"
                    load_hardware_state
                else
                    echo -e "${YELLOW}Select a main board first${NC}"
                    sleep 1
                fi
                ;;
            2)
                if [[ -n "${WIZARD_STATE[board]}" ]]; then
                    save_state
                    python3 "${SCRIPT_DIR}/setup-hardware.py" --fan-multipin "fan_rscs"
                    load_hardware_state
                else
                    echo -e "${YELLOW}Select a main board first${NC}"
                    sleep 1
                fi
                ;;
            3)
                menu_fan_control_mode "rscs" "RSCS/Filter Fan"
                save_state
                ;;
            [cC])
                save_state
                python3 "${SCRIPT_DIR}/setup-hardware.py" --clear-port "fan_rscs"
                python3 "${SCRIPT_DIR}/setup-hardware.py" --clear-port "fan_rscs_pin2"
                WIZARD_STATE[fan_rscs_type]=""
                WIZARD_STATE[fan_rscs_heater]=""
                WIZARD_STATE[fan_rscs_heater_temp]=""
                WIZARD_STATE[fan_rscs_sensor_type]=""
                WIZARD_STATE[fan_rscs_target_temp]=""
                load_hardware_state
                save_state
                echo -e "${GREEN}✓${NC} RSCS/Filter fan cleared"
                sleep 1
                ;;
            [bB]) return ;;
        esac
    done
}

menu_fan_radiator() {
    while true; do
        clear_screen

        # Determine fan type for header (default to heater for radiator - water cooling)
        local fan_type="${WIZARD_STATE[fan_radiator_type]:-heater}"
        local header_type="heater_fan"
        [[ "$fan_type" == "manual" ]] && header_type="fan_generic"
        [[ "$fan_type" == "temperature" ]] && header_type="temperature_fan"
        print_header "Radiator Fan [$header_type]"

        print_box_line "${BWHITE}Water cooling radiator fan(s)${NC}"
        print_box_line "Typically runs when extruder is hot (like hotend fan)."
        print_box_line "Common for water-cooled hotends with external radiator."
        print_empty_line

        # Determine current port assignment
        local primary_port="${HARDWARE_STATE[fan_radiator]}"
        local secondary_port="${HARDWARE_STATE[fan_radiator_pin2]}"

        # Display current status
        local primary_status=$([[ -n "$primary_port" ]] && echo "done" || echo "")
        local primary_info="${primary_port:-not assigned}"
        print_menu_item "1" "$primary_status" "Fan Port" "$primary_info"

        local secondary_status=$([[ -n "$secondary_port" ]] && echo "done" || echo "")
        local secondary_info="${secondary_port:-not set}"
        print_menu_item "2" "$secondary_status" "Multi-pin (2nd fan)" "$secondary_info"

        print_empty_line

        # Control mode selection
        local type_status=$([[ -n "${WIZARD_STATE[fan_radiator_type]}" ]] && echo "done" || echo "")
        local type_info="${WIZARD_STATE[fan_radiator_type]:-heater}"
        case "$type_info" in
            manual)
                type_info="manual (SET_FAN_SPEED)"
                ;;
            heater)
                local heater="${WIZARD_STATE[fan_radiator_heater]:-extruder}"
                local temp="${WIZARD_STATE[fan_radiator_heater_temp]:-50}"
                type_info="heater-triggered ($heater @ ${temp}°C)"
                ;;
            temperature)
                local target="${WIZARD_STATE[fan_radiator_target_temp]:-45}"
                type_info="temp-controlled (target ${target}°C)"
                ;;
        esac
        print_menu_item "3" "$type_status" "Control Mode" "$type_info"

        print_separator
        print_action_item "C" "Clear (disable fan)"
        print_action_item "B" "Back"
        print_footer

        echo -en "${BYELLOW}Select option${NC}: "
        read -r choice

        case "$choice" in
            1)
                if [[ -n "${WIZARD_STATE[board]}" ]]; then
                    save_state
                    python3 "${SCRIPT_DIR}/setup-hardware.py" --fan "fan_radiator"
                    load_hardware_state
                else
                    echo -e "${YELLOW}Select a main board first${NC}"
                    sleep 1
                fi
                ;;
            2)
                if [[ -n "${WIZARD_STATE[board]}" ]]; then
                    save_state
                    python3 "${SCRIPT_DIR}/setup-hardware.py" --fan-multipin "fan_radiator"
                    load_hardware_state
                else
                    echo -e "${YELLOW}Select a main board first${NC}"
                    sleep 1
                fi
                ;;
            3)
                menu_fan_control_mode "radiator" "radiator_fan"
                ;;
            [cC])
                save_state
                python3 "${SCRIPT_DIR}/setup-hardware.py" --clear-port "fan_radiator"
                python3 "${SCRIPT_DIR}/setup-hardware.py" --clear-port "fan_radiator_2"
                WIZARD_STATE[fan_radiator_type]=""
                WIZARD_STATE[fan_radiator_heater]=""
                WIZARD_STATE[fan_radiator_heater_temp]=""
                WIZARD_STATE[fan_radiator_sensor_type]=""
                WIZARD_STATE[fan_radiator_target_temp]=""
                load_hardware_state
                echo -e "${GREEN}✓${NC} Radiator fan cleared"
                sleep 1
                ;;
            [bB]) return ;;
        esac
    done
}

menu_fan_advanced_select() {
    while true; do
        clear_screen
        print_header "Advanced Fan Settings"

        print_box_line "${BWHITE}Select fan to configure advanced settings:${NC}"
        print_empty_line

        print_menu_item "1" "" "Part Cooling Fan"
        print_menu_item "2" "" "Hotend Fan"
        print_menu_item "3" "" "Controller Fan"
        print_menu_item "4" "" "Exhaust Fan"
        print_menu_item "5" "" "Chamber Fan"
        print_menu_item "6" "" "RSCS/Filter Fan"
        print_menu_item "7" "" "Radiator Fan"
        print_separator
        print_action_item "B" "Back"
        print_footer

        echo -en "${BYELLOW}Select fan${NC}: "
        read -r choice

        case "$choice" in
            1) menu_fan_advanced "pc" "Part Cooling Fan" ;;
            2) menu_fan_advanced "hf" "Hotend Fan" ;;
            3) menu_fan_advanced "cf" "Controller Fan" ;;
            4) menu_fan_advanced "ex" "Exhaust Fan" ;;
            5) menu_fan_advanced "ch" "Chamber Fan" ;;
            6) menu_fan_advanced "rs" "RSCS/Filter Fan" ;;
            7) menu_fan_advanced "rd" "Radiator Fan" ;;
            [bB]) return ;;
        esac
    done
}

menu_fan_advanced() {
    # Usage: menu_fan_advanced <fan_prefix> <fan_name>
    # fan_prefix: pc, hf, cf, ex, ch, rs, rd
    # fan_name: display name for the fan
    local fan_prefix="${1:-pc}"
    local fan_name="${2:-Part Cooling Fan}"

    clear_screen
    print_header "Advanced Fan Settings"

    print_box_line "${BWHITE}${fan_name} Advanced Options:${NC}"
    print_empty_line

    # Current values or defaults (using dynamic keys)
    local max_power="${WIZARD_STATE[fan_${fan_prefix}_max_power]:-1.0}"
    local cycle_time="${WIZARD_STATE[fan_${fan_prefix}_cycle_time]:-0.010}"
    local hw_pwm="${WIZARD_STATE[fan_${fan_prefix}_hardware_pwm]:-false}"
    local shutdown="${WIZARD_STATE[fan_${fan_prefix}_shutdown_speed]:-0}"
    local kick="${WIZARD_STATE[fan_${fan_prefix}_kick_start]:-0.5}"

    print_box_line "Current settings:"
    print_box_line "• max_power: ${CYAN}${max_power}${NC} (0.0-1.0)"
    print_box_line "• cycle_time: ${CYAN}${cycle_time}${NC} (0.010 default, 0.002 for high-speed)"
    print_box_line "• hardware_pwm: ${CYAN}${hw_pwm}${NC}"
    print_box_line "• shutdown_speed: ${CYAN}${shutdown}${NC}"
    print_box_line "• kick_start_time: ${CYAN}${kick}${NC} seconds"
    print_empty_line

    print_menu_item "1" "" "Set max_power"
    print_menu_item "2" "" "Set cycle_time (PWM frequency)"
    print_menu_item "3" "" "Toggle hardware_pwm"
    print_menu_item "4" "" "Set shutdown_speed"
    print_menu_item "5" "" "Set kick_start_time"
    print_menu_item "D" "" "Reset to defaults"
    print_separator
    print_action_item "B" "Back"
    print_footer

    echo -en "${BYELLOW}Select option${NC}: "
    read -r choice

    case "$choice" in
        1)
            echo -en "  Enter max_power (0.0-1.0) [${max_power}]: "
            read -r value
            [[ -n "$value" ]] && WIZARD_STATE[fan_${fan_prefix}_max_power]="$value"
            ;;
        2)
            echo -en "  Enter cycle_time (0.010 default, 0.002 for high-speed) [${cycle_time}]: "
            read -r value
            [[ -n "$value" ]] && WIZARD_STATE[fan_${fan_prefix}_cycle_time]="$value"
            ;;
        3)
            if [[ "$hw_pwm" == "false" ]]; then
                WIZARD_STATE[fan_${fan_prefix}_hardware_pwm]="true"
                echo -e "${GREEN}✓${NC} hardware_pwm enabled"
            else
                WIZARD_STATE[fan_${fan_prefix}_hardware_pwm]="false"
                echo -e "${GREEN}✓${NC} hardware_pwm disabled"
            fi
            sleep 1
            ;;
        4)
            echo -en "  Enter shutdown_speed (0.0-1.0) [${shutdown}]: "
            read -r value
            [[ -n "$value" ]] && WIZARD_STATE[fan_${fan_prefix}_shutdown_speed]="$value"
            ;;
        5)
            echo -en "  Enter kick_start_time (seconds) [${kick}]: "
            read -r value
            [[ -n "$value" ]] && WIZARD_STATE[fan_${fan_prefix}_kick_start]="$value"
            ;;
        [dD])
            WIZARD_STATE[fan_${fan_prefix}_max_power]=""
            WIZARD_STATE[fan_${fan_prefix}_cycle_time]=""
            WIZARD_STATE[fan_${fan_prefix}_hardware_pwm]=""
            WIZARD_STATE[fan_${fan_prefix}_shutdown_speed]=""
            WIZARD_STATE[fan_${fan_prefix}_kick_start]=""
            echo -e "${GREEN}✓${NC} Reset to defaults"
            sleep 1
            ;;
        [bB]) return ;;
    esac

    save_state
}

# ═══════════════════════════════════════════════════════════════════════════════
# LIGHTING CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

menu_lighting() {
    while true; do
        clear_screen
        print_header "Lighting Configuration"

        print_box_line "${BWHITE}Configure printer lighting:${NC}"
        print_empty_line

        # Current status
        local light_type="${WIZARD_STATE[lighting_type]:-not configured}"
        print_box_line "Current: ${CYAN}${light_type}${NC}"
        print_empty_line

        # Show checkmark for currently selected type
        local neo_status=$([[ "$light_type" == "neopixel" ]] && echo "done" || echo "")
        local dot_status=$([[ "$light_type" == "dotstar" ]] && echo "done" || echo "")
        local pca_status=$([[ "$light_type" == "pca9533" ]] && echo "done" || echo "")
        local pwm_status=$([[ "$light_type" == "pwm" ]] && echo "done" || echo "")
        local none_status=$([[ "$light_type" == "none" ]] && echo "done" || echo "")

        print_menu_item "1" "$neo_status" "Neopixel (WS2812, SK6812)"
        print_menu_item "2" "$dot_status" "Dotstar (APA102)"
        print_menu_item "3" "$pca_status" "PCA9533 (I2C LED driver)"
        print_menu_item "4" "$pwm_status" "Simple PWM LED"
        print_menu_item "5" "$none_status" "None - no lighting"

        # Port/pin assignment option if type is selected
        if [[ -n "${WIZARD_STATE[lighting_type]}" && "${WIZARD_STATE[lighting_type]}" != "none" ]]; then
            print_empty_line
            # Check both mainboard and toolboard for lighting pin
            local pin_info=""
            if [[ -n "${HARDWARE_STATE[toolboard_lighting_pin]}" ]]; then
                pin_info="toolboard:${HARDWARE_STATE[toolboard_lighting_pin]}"
            elif [[ -n "${HARDWARE_STATE[lighting_pin]}" ]]; then
                pin_info="${HARDWARE_STATE[lighting_pin]}"
            else
                pin_info="not assigned"
            fi
            local led_count="${WIZARD_STATE[lighting_count]:-1}"
            if [[ "${WIZARD_STATE[lighting_type]}" =~ ^(neopixel|dotstar)$ ]]; then
                pin_info="${pin_info}, ${led_count} LEDs"
            fi
            local pin_status=$([[ -n "${HARDWARE_STATE[lighting_pin]}" || -n "${HARDWARE_STATE[toolboard_lighting_pin]}" ]] && echo "done" || echo "")
            print_menu_item "P" "$pin_status" "Configure Pin & Settings" "${pin_info}"
        fi

        print_separator
        print_action_item "B" "Back to Main Menu"
        print_footer

        echo -en "${BYELLOW}Select option${NC}: "
        read -r choice

        case "$choice" in
            1)
                WIZARD_STATE[lighting_type]="neopixel"
                echo -e "${GREEN}✓${NC} Neopixel lighting selected"
                sleep 1
                ;;
            2)
                WIZARD_STATE[lighting_type]="dotstar"
                echo -e "${GREEN}✓${NC} Dotstar lighting selected"
                sleep 1
                ;;
            3)
                WIZARD_STATE[lighting_type]="pca9533"
                echo -e "${GREEN}✓${NC} PCA9533 lighting selected"
                sleep 1
                ;;
            4)
                WIZARD_STATE[lighting_type]="pwm"
                echo -e "${GREEN}✓${NC} PWM LED lighting selected"
                sleep 1
                ;;
            5)
                WIZARD_STATE[lighting_type]="none"
                echo -e "${GREEN}✓${NC} Lighting disabled"
                sleep 1
                ;;
            [pP])
                if [[ -n "${WIZARD_STATE[lighting_type]}" && "${WIZARD_STATE[lighting_type]}" != "none" ]]; then
                    menu_lighting_settings
                fi
                ;;
            [bB]) return ;;
        esac

        # Save state after lighting type selection
        save_state
    done
}

menu_lighting_settings() {
    clear_screen
    print_header "Lighting Settings"

    local light_type="${WIZARD_STATE[lighting_type]}"
    print_box_line "${BWHITE}Configure ${light_type} settings:${NC}"
    print_empty_line

    # LED count for addressable LEDs
    if [[ "$light_type" =~ ^(neopixel|dotstar)$ ]]; then
        echo -en "  Number of LEDs [${WIZARD_STATE[lighting_count]:-1}]: "
        read -r led_count
        WIZARD_STATE[lighting_count]="${led_count:-${WIZARD_STATE[lighting_count]:-1}}"
    fi

    # Color order for Neopixels
    if [[ "$light_type" == "neopixel" ]]; then
        echo ""
        print_box_line "${BWHITE}Color order:${NC}"
        print_menu_item "1" "" "GRB (most common)"
        print_menu_item "2" "" "RGB"
        print_menu_item "3" "" "GRBW (RGBW strips)"
        print_menu_item "4" "" "RGBW"

        echo -en "${BYELLOW}Select color order${NC}: "
        read -r color_choice

        case "$color_choice" in
            1) WIZARD_STATE[lighting_color_order]="GRB" ;;
            2) WIZARD_STATE[lighting_color_order]="RGB" ;;
            3) WIZARD_STATE[lighting_color_order]="GRBW" ;;
            4) WIZARD_STATE[lighting_color_order]="RGBW" ;;
            *) WIZARD_STATE[lighting_color_order]="GRB" ;;
        esac
    fi

    # Pin assignment
    if [[ -n "${WIZARD_STATE[board]}" ]]; then
        save_state
        python3 "${SCRIPT_DIR}/setup-hardware.py" --lighting
        load_hardware_state
    else
        echo -e "${YELLOW}Select a board first to assign the pin.${NC}"
        wait_for_key
    fi

    echo -e "${GREEN}✓${NC} Lighting settings configured"
    sleep 1
}

# ═══════════════════════════════════════════════════════════════════════════════
# MISC MCUs (MMU, Expansion boards, CAN probes)
# ═══════════════════════════════════════════════════════════════════════════════

menu_misc_mcus() {
    while true; do
        clear_screen
        print_header "Misc MCUs Configuration"

        print_box_line "${BWHITE}Additional MCUs and expansion boards:${NC}"
        print_empty_line

        # MMU
        local mmu_info="${WIZARD_STATE[mmu_type]:-not configured}"
        if [[ -n "${WIZARD_STATE[mmu_serial]}" ]]; then
            mmu_info="${mmu_info} (USB configured)"
        elif [[ -n "${WIZARD_STATE[mmu_canbus_uuid]}" ]]; then
            mmu_info="${mmu_info} (CAN configured)"
        fi
        local mmu_status=$([[ -n "${WIZARD_STATE[mmu_type]}" && "${WIZARD_STATE[mmu_type]}" != "none" ]] && echo "done" || echo "")
        print_menu_item "1" "$mmu_status" "MMU / ERCF / Tradrack" "${mmu_info}"

        # Expansion board
        local exp_info="${WIZARD_STATE[expansion_board]:-not configured}"
        local exp_status=$([[ -n "${WIZARD_STATE[expansion_board]}" && "${WIZARD_STATE[expansion_board]}" != "none" ]] && echo "done" || echo "")
        print_menu_item "2" "$exp_status" "Expansion Board" "${exp_info}"

        # CAN probes (Beacon, Cartographer, Eddy) - shown if selected in endstops
        local probe_type="${WIZARD_STATE[probe_type]}"
        if [[ "$probe_type" =~ ^(beacon|cartographer|btt-eddy)$ ]]; then
            print_empty_line
            print_box_line "${BWHITE}Probe MCU (from Endstops):${NC}"
            local probe_mcu_info="${probe_type}"
            if [[ -n "${WIZARD_STATE[probe_serial]}" ]]; then
                probe_mcu_info="${probe_mcu_info} (USB: configured)"
            elif [[ -n "${WIZARD_STATE[probe_canbus_uuid]}" ]]; then
                probe_mcu_info="${probe_mcu_info} (CAN: configured)"
            else
                probe_mcu_info="${probe_mcu_info} (not configured)"
            fi
            local probe_mcu_status=$([[ -n "${WIZARD_STATE[probe_serial]}" || -n "${WIZARD_STATE[probe_canbus_uuid]}" ]] && echo "done" || echo "")
            print_menu_item "3" "$probe_mcu_status" "Probe MCU" "${probe_mcu_info}"
        fi

        print_separator
        print_action_item "B" "Back to Main Menu"
        print_footer

        echo -en "${BYELLOW}Select option${NC}: "
        read -r choice

        case "$choice" in
            1) menu_mmu ;;
            2) menu_expansion_board ;;
            3)
                if [[ "$probe_type" =~ ^(beacon|cartographer|btt-eddy)$ ]]; then
                    menu_probe_mcu
                fi
                ;;
            [bB]) return ;;
            *) ;;
        esac
    done
}

menu_mmu() {
    while true; do
        clear_screen
        print_header "MMU Configuration"

        print_box_line "${BWHITE}Multi-Material Unit:${NC}"
        print_empty_line

        # Current status
        local mmu_info="${WIZARD_STATE[mmu_type]:-not configured}"
        print_box_line "Current: ${CYAN}${mmu_info}${NC}"
        print_empty_line

        print_menu_item "1" "" "ERCF (Enraged Rabbit Carrot Feeder)"
        print_menu_item "2" "" "Tradrack"
        print_menu_item "3" "" "MMU2S"
        print_menu_item "4" "" "Other MMU (manual config)"
        print_menu_item "5" "" "None - no MMU"

        # Connection config if MMU selected
        if [[ -n "${WIZARD_STATE[mmu_type]}" && "${WIZARD_STATE[mmu_type]}" != "none" ]]; then
            print_empty_line
            local conn_info=""
            if [[ -n "${WIZARD_STATE[mmu_serial]}" ]]; then
                conn_info="USB: ${WIZARD_STATE[mmu_serial]}"
            elif [[ -n "${WIZARD_STATE[mmu_canbus_uuid]}" ]]; then
                conn_info="CAN: ${WIZARD_STATE[mmu_canbus_uuid]}"
            else
                conn_info="not configured"
            fi
            print_menu_item "C" "" "Configure Connection" "${conn_info}"
        fi

        print_separator
        print_action_item "B" "Back"
        print_footer

        echo -en "${BYELLOW}Select option${NC}: "
        read -r choice

        case "$choice" in
            1) WIZARD_STATE[mmu_type]="ercf" ;;
            2) WIZARD_STATE[mmu_type]="tradrack" ;;
            3) WIZARD_STATE[mmu_type]="mmu2s" ;;
            4) WIZARD_STATE[mmu_type]="other" ;;
            5)
                WIZARD_STATE[mmu_type]="none"
                WIZARD_STATE[mmu_serial]=""
                WIZARD_STATE[mmu_canbus_uuid]=""
                ;;
            [cC])
                if [[ -n "${WIZARD_STATE[mmu_type]}" && "${WIZARD_STATE[mmu_type]}" != "none" ]]; then
                    menu_mmu_connection
                fi
                ;;
            [bB]) return ;;
        esac
    done
}

menu_mmu_connection() {
    clear_screen
    print_header "MMU Connection"

    print_box_line "${BWHITE}Configure ${WIZARD_STATE[mmu_type]} connection:${NC}"
    print_empty_line

    print_menu_item "1" "" "USB connection (serial by-id)"
    print_menu_item "2" "" "CAN bus (UUID)"
    print_separator
    print_action_item "B" "Back"
    print_footer

    echo -en "${BYELLOW}Select connection type${NC}: "
    read -r choice

    case "$choice" in
        1)
            # USB serial selection
            clear_screen
            print_header "MMU USB Serial"

            print_box_line "${BWHITE}Scanning for USB devices...${NC}"
            print_empty_line

            local devices=()
            local i=1
            while IFS= read -r device; do
                if [[ -n "$device" ]]; then
                    devices+=("$device")
                    print_box_line "${BWHITE}${i})${NC} ${device}"
                    i=$((i + 1))
                fi
            done < <(ls /dev/serial/by-id/ 2>/dev/null || true)

            if [[ ${#devices[@]} -eq 0 ]]; then
                print_box_line "${YELLOW}No USB devices found.${NC}"
            fi

            print_separator
            print_action_item "M" "Manual entry"
            print_action_item "B" "Back"
            print_footer

            echo -en "${BYELLOW}Select device or M for manual${NC}: "
            read -r dev_choice

            case "$dev_choice" in
                [1-9])
                    local idx=$((dev_choice - 1))
                    if [[ $idx -lt ${#devices[@]} ]]; then
                        WIZARD_STATE[mmu_serial]="/dev/serial/by-id/${devices[$idx]}"
                        WIZARD_STATE[mmu_canbus_uuid]=""
                        echo -e "${GREEN}✓${NC} MMU serial configured"
                        sleep 1
                    fi
                    ;;
                [mM])
                    echo -en "  Enter serial path: "
                    read -r manual_serial
                    if [[ -n "$manual_serial" ]]; then
                        WIZARD_STATE[mmu_serial]="$manual_serial"
                        WIZARD_STATE[mmu_canbus_uuid]=""
                    fi
                    ;;
            esac
            ;;
        2)
            # CAN UUID selection
            clear_screen
            print_header "MMU CAN UUID"

            echo -en "  Enter CAN UUID: "
            read -r can_uuid
            if [[ -n "$can_uuid" ]]; then
                WIZARD_STATE[mmu_canbus_uuid]="$can_uuid"
                WIZARD_STATE[mmu_serial]=""
                echo -e "${GREEN}✓${NC} MMU CAN UUID configured"
                sleep 1
            fi
            ;;
        [bB]) return ;;
    esac
}

menu_expansion_board() {
    while true; do
        clear_screen
        print_header "Expansion Board"

        print_box_line "${BWHITE}Additional MCU expansion boards:${NC}"
        print_empty_line

        # Current status
        print_box_line "Current: ${CYAN}${WIZARD_STATE[expansion_board]:-not configured}${NC}"
        print_empty_line

        print_menu_item "1" "" "BTT EXP-MOT (motor expander)"
        print_menu_item "2" "" "Fly-SHT36/42 (as expansion, not toolhead)"
        print_menu_item "3" "" "Other expansion board"
        print_menu_item "4" "" "None - no expansion board"

        # Connection config if board selected
        if [[ -n "${WIZARD_STATE[expansion_board]}" && "${WIZARD_STATE[expansion_board]}" != "none" ]]; then
            print_empty_line
            local conn_info=""
            if [[ -n "${WIZARD_STATE[expansion_serial]}" ]]; then
                conn_info="USB: configured"
            elif [[ -n "${WIZARD_STATE[expansion_canbus_uuid]}" ]]; then
                conn_info="CAN: configured"
            else
                conn_info="not configured"
            fi
            print_menu_item "C" "" "Configure Connection" "${conn_info}"
        fi

        print_separator
        print_action_item "B" "Back"
        print_footer

        echo -en "${BYELLOW}Select option${NC}: "
        read -r choice

        case "$choice" in
            1) WIZARD_STATE[expansion_board]="btt-exp-mot" ;;
            2) WIZARD_STATE[expansion_board]="fly-sht" ;;
            3) WIZARD_STATE[expansion_board]="other" ;;
            4)
                WIZARD_STATE[expansion_board]="none"
                WIZARD_STATE[expansion_serial]=""
                WIZARD_STATE[expansion_canbus_uuid]=""
                ;;
            [cC])
                if [[ -n "${WIZARD_STATE[expansion_board]}" && "${WIZARD_STATE[expansion_board]}" != "none" ]]; then
                    menu_expansion_connection
                fi
                ;;
            [bB]) return ;;
        esac
    done
}

menu_expansion_connection() {
    clear_screen
    print_header "Expansion Board Connection"

    print_box_line "${BWHITE}Configure expansion board connection:${NC}"
    print_empty_line

    print_menu_item "1" "" "USB connection (serial by-id)"
    print_menu_item "2" "" "CAN bus (UUID)"
    print_separator
    print_action_item "B" "Back"
    print_footer

    echo -en "${BYELLOW}Select connection type${NC}: "
    read -r choice

    case "$choice" in
        1)
            echo -en "  Enter USB serial path: "
            read -r serial_path
            if [[ -n "$serial_path" ]]; then
                WIZARD_STATE[expansion_serial]="$serial_path"
                WIZARD_STATE[expansion_canbus_uuid]=""
                echo -e "${GREEN}✓${NC} Expansion board serial configured"
                sleep 1
            fi
            ;;
        2)
            echo -en "  Enter CAN UUID: "
            read -r can_uuid
            if [[ -n "$can_uuid" ]]; then
                WIZARD_STATE[expansion_canbus_uuid]="$can_uuid"
                WIZARD_STATE[expansion_serial]=""
                echo -e "${GREEN}✓${NC} Expansion board CAN UUID configured"
                sleep 1
            fi
            ;;
        [bB]) return ;;
    esac
}

# ═══════════════════════════════════════════════════════════════════════════════
# LED TYPE SELECTION
# ═══════════════════════════════════════════════════════════════════════════════

select_led_type() {
    local led_purpose="${1:-status}"  # "status" or "caselight"
    
    clear_screen
    print_header "Select LED Type"
    
    echo -e "${BCYAN}${BOX_V}${NC}  ${BWHITE}What type of LEDs are you using for ${led_purpose}?${NC}"
    echo -e "${BCYAN}${BOX_V}${NC}"
    
    print_menu_item "1" "" "NeoPixel (WS2812B)" "Addressable RGB LEDs"
    print_menu_item "2" "" "DotStar (APA102)" "Addressable RGB with clock line"
    print_menu_item "3" "" "Simple LED" "Single color, PWM controlled"
    
    print_separator
    print_action_item "B" "Back (cancel)"
    print_footer
    
    echo -en "${BYELLOW}Select LED type${NC}: "
    read -r choice
    
    case "$choice" in
        1)
            WIZARD_STATE[lighting_type]="neopixel"
            if [[ "$led_purpose" == "status" ]]; then
                WIZARD_STATE[led_type]="neopixel"
            else
                WIZARD_STATE[caselight_type]="neopixel"
            fi
            echo -e "${GREEN}✓${NC} Selected: NeoPixel"
            sleep 1
            ;;
        2)
            WIZARD_STATE[lighting_type]="dotstar"
            if [[ "$led_purpose" == "status" ]]; then
                WIZARD_STATE[led_type]="dotstar"
            else
                WIZARD_STATE[caselight_type]="dotstar"
            fi
            echo -e "${GREEN}✓${NC} Selected: DotStar"
            sleep 1
            ;;
        3)
            WIZARD_STATE[lighting_type]="simple"
            if [[ "$led_purpose" == "status" ]]; then
                WIZARD_STATE[led_type]="simple"
            else
                WIZARD_STATE[caselight_type]="simple"
            fi
            echo -e "${GREEN}✓${NC} Selected: Simple LED"
            sleep 1
            ;;
        [bB])
            # Cancel - revert the has_leds/has_caselight setting
            if [[ "$led_purpose" == "status" ]]; then
                WIZARD_STATE[has_leds]=""
            else
                WIZARD_STATE[has_caselight]=""
            fi
            return
            ;;
        *)
            # Default to neopixel
            WIZARD_STATE[lighting_type]="neopixel"
            if [[ "$led_purpose" == "status" ]]; then
                WIZARD_STATE[led_type]="neopixel"
            else
                WIZARD_STATE[caselight_type]="neopixel"
            fi
            ;;
    esac
    save_state
}

menu_extras() {
    clear_screen
    print_header "Extra Features"
    
    print_box_line "${BWHITE}Sensors:${NC}"

    local fs_status=$([[ "${WIZARD_STATE[has_filament_sensor]}" == "yes" ]] && echo "[x]" || echo "[ ]")
    local cs_status=$([[ "${WIZARD_STATE[has_chamber_sensor]}" == "yes" ]] && echo "[x]" || echo "[ ]")

    print_box_line "1) ${fs_status} Filament Sensor"
    # Show chamber sensor with type info and port assignment
    if [[ "${WIZARD_STATE[has_chamber_sensor]}" == "yes" ]]; then
        local cs_type="${WIZARD_STATE[chamber_sensor_type]:-Generic 3950}"
        local cs_port="${HARDWARE_STATE[thermistor_chamber]:-not assigned}"
        print_box_line "2) ${cs_status} Chamber Temperature Sensor ${WHITE}(${cs_type})${NC}"
        if [[ "$cs_port" == "not assigned" ]]; then
            print_box_line "   ${YELLOW}Port: not assigned - press P to assign${NC}"
        else
            print_box_line "   ${GREEN}Port: ${cs_port}${NC}"
        fi
    else
        print_box_line "2) ${cs_status} Chamber Temperature Sensor"
    fi
    
    print_empty_line
    print_box_line "${BWHITE}Displays:${NC}"
    
    local ks_status=$([[ "${WIZARD_STATE[has_klipperscreen]}" == "yes" ]] && echo "[x]" || echo "[ ]")
    local lcd_status=$([[ "${WIZARD_STATE[has_lcd_display]}" == "yes" ]] && echo "[x]" || echo "[ ]")
    
    # Build KlipperScreen info string
    local ks_info=""
    if [[ "${WIZARD_STATE[has_klipperscreen]}" == "yes" ]]; then
        local model="${WIZARD_STATE[touchscreen_model]:-}"
        local rotation="${WIZARD_STATE[touchscreen_rotation]:-0}"
        if [[ -n "$model" ]]; then
            # Format model name for display
            case "$model" in
                btt_hdmi5) ks_info=" - BTT HDMI5" ;;
                btt_hdmi7) ks_info=" - BTT HDMI7" ;;
                waveshare_hdmi_*) ks_info=" - Waveshare HDMI" ;;
                rpi_official_7) ks_info=" - RPi Official 7\"" ;;
                waveshare_dsi_*) ks_info=" - Waveshare DSI" ;;
                mellow_fly_tft_v2) ks_info=" - Mellow FLY-TFT" ;;
                waveshare_spi_*) ks_info=" - Waveshare SPI" ;;
                goodtft_3_5|generic_*) ks_info=" - Generic TFT" ;;
                *) ks_info=" - ${model}" ;;
            esac
            ks_info="${ks_info}, ${rotation}°"
        fi
    fi
    
    print_box_line "3) ${ks_status} KlipperScreen${ks_info}"
    print_box_line "4) ${lcd_status} LCD Display (Mini12864/ST7920)"
    
    print_empty_line
    print_box_line "${BWHITE}Lighting:${NC}"
    
    local led_status=$([[ "${WIZARD_STATE[has_leds]}" == "yes" ]] && echo "[x]" || echo "[ ]")
    local cl_status=$([[ "${WIZARD_STATE[has_caselight]}" == "yes" ]] && echo "[x]" || echo "[ ]")
    
    # Show LED type if set
    local led_type_info=""
    if [[ -n "${WIZARD_STATE[led_type]}" ]]; then
        led_type_info=" (${WIZARD_STATE[led_type]})"
    fi
    local cl_type_info=""
    if [[ -n "${WIZARD_STATE[caselight_type]}" ]]; then
        cl_type_info=" (${WIZARD_STATE[caselight_type]})"
    fi
    
    print_box_line "5) ${led_status} Status LEDs${led_type_info}"
    if [[ "${WIZARD_STATE[has_leds]}" == "yes" && -n "${HARDWARE_STATE[lighting_pin]}" ]]; then
        print_box_line "   ${GREEN}Pin: ${HARDWARE_STATE[lighting_pin]}${NC}"
    fi
    print_box_line "6) ${cl_status} Case Lighting${cl_type_info}"
    if [[ "${WIZARD_STATE[has_caselight]}" == "yes" && -n "${HARDWARE_STATE[caselight_pin]}" ]]; then
        print_box_line "   ${GREEN}Pin: ${HARDWARE_STATE[caselight_pin]}${NC}"
    fi

    # Show port assignment options
    print_empty_line
    print_box_line "${BWHITE}Port Assignment:${NC}"
    if [[ "${WIZARD_STATE[has_chamber_sensor]}" == "yes" ]]; then
        print_menu_item "P" "" "Assign Chamber Thermistor Port"
    fi
    if [[ "${WIZARD_STATE[has_leds]}" == "yes" || "${WIZARD_STATE[has_caselight]}" == "yes" ]]; then
        print_menu_item "L" "" "Assign Lighting Pin"
    fi
    
    # Show touch panel setup option if KlipperScreen is selected
    if [[ "${WIZARD_STATE[has_klipperscreen]}" == "yes" && -n "${WIZARD_STATE[touchscreen_model]:-}" ]]; then
        print_empty_line
        print_box_line "${BWHITE}Touch Panel:${NC}"
        print_menu_item "T" "" "Generate Touch Panel Setup Script"
    fi

    print_separator
    print_action_item "B" "Back"
    print_footer
    
    echo -en "${BYELLOW}Toggle option${NC}: "
    read -r choice
    
    case "$choice" in
        1) 
            if [[ "${WIZARD_STATE[has_filament_sensor]}" == "yes" ]]; then
                WIZARD_STATE[has_filament_sensor]=""
            else
                WIZARD_STATE[has_filament_sensor]="yes"
                # Ask for sensor type
                select_filament_sensor_type
            fi
            menu_extras  # Refresh
            ;;
        2)
            if [[ "${WIZARD_STATE[has_chamber_sensor]}" == "yes" ]]; then
                WIZARD_STATE[has_chamber_sensor]=""
                WIZARD_STATE[chamber_sensor_type]=""
            else
                WIZARD_STATE[has_chamber_sensor]="yes"
                select_chamber_sensor_type
                # Prompt to assign thermistor port if board is selected
                if [[ -n "${WIZARD_STATE[board]}" ]]; then
                    save_state
                    echo ""
                    echo -e "${CYAN}Now assign the thermistor port for the chamber sensor...${NC}"
                    sleep 1
                    python3 "${SCRIPT_DIR}/setup-hardware.py" --thermistor-chamber
                    load_hardware_state
                fi
            fi
            menu_extras  # Refresh
            ;;
        3)
            if [[ "${WIZARD_STATE[has_klipperscreen]}" == "yes" ]]; then
                WIZARD_STATE[has_klipperscreen]=""
                WIZARD_STATE[klipperscreen_type]=""
                WIZARD_STATE[touchscreen_model]=""
                WIZARD_STATE[touchscreen_rotation]=""
            else
                WIZARD_STATE[has_klipperscreen]="yes"
                select_klipperscreen_type
            fi
            menu_extras  # Refresh
            ;;
        4)
            if [[ "${WIZARD_STATE[has_lcd_display]}" == "yes" ]]; then
                WIZARD_STATE[has_lcd_display]=""
                WIZARD_STATE[lcd_display_type]=""
            else
                WIZARD_STATE[has_lcd_display]="yes"
                select_lcd_display_type
            fi
            menu_extras  # Refresh
            ;;
        5)
            if [[ "${WIZARD_STATE[has_leds]}" == "yes" ]]; then
                WIZARD_STATE[has_leds]=""
                WIZARD_STATE[led_type]=""
            else
                WIZARD_STATE[has_leds]="yes"
                # Ask for LED type
                select_led_type "status"
                # Assign pin if board selected
                if [[ -n "${WIZARD_STATE[board]}" ]]; then
                    save_state
                    python3 "${SCRIPT_DIR}/setup-hardware.py" --lighting
                    load_hardware_state
                fi
            fi
            menu_extras  # Refresh
            ;;
        6)
            if [[ "${WIZARD_STATE[has_caselight]}" == "yes" ]]; then
                WIZARD_STATE[has_caselight]=""
                WIZARD_STATE[caselight_type]=""
            else
                WIZARD_STATE[has_caselight]="yes"
                # Ask for caselight type
                select_led_type "caselight"
                # Assign pin if board selected
                if [[ -n "${WIZARD_STATE[board]}" ]]; then
                    save_state
                    python3 "${SCRIPT_DIR}/setup-hardware.py" --lighting
                    load_hardware_state
                fi
            fi
            menu_extras  # Refresh
            ;;
        7)
            if [[ "${WIZARD_STATE[has_camera]}" == "yes" ]]; then
                WIZARD_STATE[has_camera]=""
                WIZARD_STATE[camera_type]=""
            else
                WIZARD_STATE[has_camera]="yes"
                select_camera_type
            fi
            menu_extras  # Refresh
            ;;
        [pP])
            # Assign chamber thermistor port
            if [[ "${WIZARD_STATE[has_chamber_sensor]}" == "yes" && -n "${WIZARD_STATE[board]}" ]]; then
                save_state
                python3 "${SCRIPT_DIR}/setup-hardware.py" --thermistor-chamber
                load_hardware_state
            fi
            menu_extras  # Refresh
            ;;
        [lL])
            # Assign lighting pin
            if [[ ( "${WIZARD_STATE[has_leds]}" == "yes" || "${WIZARD_STATE[has_caselight]}" == "yes" ) && -n "${WIZARD_STATE[board]}" ]]; then
                save_state
                python3 "${SCRIPT_DIR}/setup-hardware.py" --lighting
                load_hardware_state
            fi
            menu_extras  # Refresh
            ;;
        [tT])
            # Generate touch panel setup script
            if [[ "${WIZARD_STATE[has_klipperscreen]}" == "yes" && -n "${WIZARD_STATE[touchscreen_model]:-}" ]]; then
                echo ""
                if generate_touch_panel_script; then
                    echo -e "${GREEN}Press Enter to continue...${NC}"
                    read -r
                else
                    echo -e "${RED}Failed to generate script. Press Enter to continue...${NC}"
                    read -r
                fi
            fi
            menu_extras  # Refresh
            ;;
        [bB]) return ;;
        *) ;;
    esac
}

select_filament_sensor_type() {
    clear_screen
    print_header "Filament Sensor Type"

    print_box_line "1) Simple Switch (runout only)"
    print_box_line "2) Motion Sensor (runout + jam detection)"
    print_footer

    echo -en "${BYELLOW}Select type${NC}: "
    read -r choice

    case "$choice" in
        1) WIZARD_STATE[filament_sensor_type]="switch" ;;
        2) WIZARD_STATE[filament_sensor_type]="motion" ;;
    esac
}

select_chamber_sensor_type() {
    clear_screen
    print_header "Chamber Thermistor Type"

    print_box_line "${BWHITE}Select your chamber thermistor type:${NC}"
    print_empty_line
    print_box_line "1) Generic 3950 (most common)"
    print_box_line "2) NTC 100K MGB18-104F39050L32"
    print_box_line "3) ATC Semitec 104GT-2"
    print_box_line "4) PT1000"
    print_footer

    echo -en "${BYELLOW}Select type${NC}: "
    read -r choice

    case "$choice" in
        1) WIZARD_STATE[chamber_sensor_type]="Generic 3950" ;;
        2) WIZARD_STATE[chamber_sensor_type]="NTC 100K MGB18-104F39050L32" ;;
        3) WIZARD_STATE[chamber_sensor_type]="ATC Semitec 104GT-2" ;;
        4) WIZARD_STATE[chamber_sensor_type]="PT1000" ;;
        *) WIZARD_STATE[chamber_sensor_type]="Generic 3950" ;;
    esac
}

select_camera_type() {
    clear_screen
    print_header "Camera Type"
    
    # Show Crowsnest installation status
    local crowsnest_status=""
    if is_crowsnest_installed; then
        crowsnest_status="${GREEN}[installed]${NC}"
    else
        crowsnest_status="${YELLOW}[not installed]${NC}"
    fi
    
    print_box_line "Crowsnest status: ${crowsnest_status}"
    print_empty_line
    print_box_line "${BWHITE}What type of camera?${NC}"
    print_empty_line
    print_box_line "1) USB Webcam (Logitech, generic)"
    print_box_line "2) Raspberry Pi Camera (CSI)"
    print_box_line "3) IP Camera (RTSP stream)"
    print_footer
    
    echo -en "${BYELLOW}Select camera type${NC}: "
    read -r choice
    
    case "$choice" in
        1) WIZARD_STATE[camera_type]="usb" ;;
        2) WIZARD_STATE[camera_type]="picam" ;;
        3) WIZARD_STATE[camera_type]="ipcam" ;;
        *) return ;;
    esac
    
    # Check if Crowsnest needs to be installed
    if ! is_crowsnest_installed; then
        echo ""
        echo -e "${YELLOW}Crowsnest is not installed.${NC}"
        if confirm "Install Crowsnest now?"; then
            install_crowsnest
            wait_for_key
        else
            echo -e "${YELLOW}Note: You'll need to install Crowsnest manually for webcam streaming.${NC}"
            echo -e "${CYAN}git clone https://github.com/mainsail-crew/crowsnest.git${NC}"
            echo -e "${CYAN}cd crowsnest && sudo tools/install.sh${NC}"
            wait_for_key
        fi
    else
        # Just add to update manager if not already there
        add_crowsnest_update_manager
        echo -e "\n${GREEN}Crowsnest is ready!${NC}"
        echo -e "${CYAN}Configure your camera in ~/printer_data/config/crowsnest.conf${NC}"
        sleep 2
    fi
}

select_klipperscreen_type() {
    clear_screen
    print_header "KlipperScreen Display Type"
    
    print_box_line "${WHITE}Select your touchscreen connection type:${NC}"
    print_empty_line
    print_box_line "1) HDMI Touchscreen (BTT HDMI5/7, Waveshare HDMI, etc.)"
    print_box_line "2) DSI Display (Raspberry Pi ribbon cable displays)"
    print_box_line "3) SPI TFT (small 3.5\" GPIO displays)"
    print_footer
    
    echo -en "${BYELLOW}Select type${NC}: "
    read -r choice
    
    case "$choice" in
        1) 
            WIZARD_STATE[klipperscreen_type]="hdmi"
            select_hdmi_model
            ;;
        2) 
            WIZARD_STATE[klipperscreen_type]="dsi"
            select_dsi_model
            ;;
        3) 
            WIZARD_STATE[klipperscreen_type]="spi_tft"
            select_spi_model
            ;;
    esac
    
    # If a model was selected, ask for rotation and offer setup script
    if [[ -n "${WIZARD_STATE[touchscreen_model]:-}" ]]; then
        select_display_rotation
        offer_touch_panel_setup
    fi
}

select_hdmi_model() {
    clear_screen
    print_header "HDMI Touchscreen Model"
    
    print_box_line "${WHITE}Select your HDMI display:${NC}"
    print_empty_line
    print_box_line "1) BTT HDMI5 (5\" 800x480)"
    print_box_line "2) BTT HDMI7 (7\" 1024x600)"
    print_box_line "3) Waveshare 5\" HDMI"
    print_box_line "4) Waveshare 7\" HDMI"
    print_box_line "5) Generic HDMI Touchscreen"
    print_footer
    
    echo -en "${BYELLOW}Select model${NC}: "
    read -r choice
    
    case "$choice" in
        1) WIZARD_STATE[touchscreen_model]="btt_hdmi5" ;;
        2) WIZARD_STATE[touchscreen_model]="btt_hdmi7" ;;
        3) WIZARD_STATE[touchscreen_model]="waveshare_hdmi_5" ;;
        4) WIZARD_STATE[touchscreen_model]="waveshare_hdmi_7" ;;
        5) WIZARD_STATE[touchscreen_model]="generic_hdmi" ;;
    esac
}

select_dsi_model() {
    clear_screen
    print_header "DSI Touchscreen Model"
    
    print_box_line "${WHITE}Select your DSI display:${NC}"
    print_empty_line
    print_box_line "1) Official Raspberry Pi 7\" Display"
    print_box_line "2) Waveshare 4.3\" DSI"
    print_box_line "3) Waveshare 5\" DSI"
    print_box_line "4) Waveshare 7\" DSI"
    print_box_line "5) Waveshare 7.9\" DSI"
    print_box_line "6) Waveshare 10.1\" DSI"
    print_footer
    
    echo -en "${BYELLOW}Select model${NC}: "
    read -r choice
    
    case "$choice" in
        1) WIZARD_STATE[touchscreen_model]="rpi_official_7" ;;
        2) WIZARD_STATE[touchscreen_model]="waveshare_dsi_4_3" ;;
        3) WIZARD_STATE[touchscreen_model]="waveshare_dsi_5" ;;
        4) WIZARD_STATE[touchscreen_model]="waveshare_dsi_7" ;;
        5) WIZARD_STATE[touchscreen_model]="waveshare_dsi_7_9" ;;
        6) WIZARD_STATE[touchscreen_model]="waveshare_dsi_10_1" ;;
    esac
}

select_spi_model() {
    clear_screen
    print_header "SPI TFT Display Model"
    
    print_box_line "${WHITE}Select your SPI TFT display:${NC}"
    print_empty_line
    print_box_line "1) Mellow FLY-TFT-V2 (recommended for Mellow boards)"
    print_box_line "2) Waveshare 3.5\" SPI"
    print_box_line "3) Waveshare 4\" SPI"
    print_box_line "4) Generic 3.5\" TFT (GoodTFT/clones)"
    print_box_line "5) Generic ILI9486 3.5\" TFT"
    print_footer
    
    echo -en "${BYELLOW}Select model${NC}: "
    read -r choice
    
    case "$choice" in
        1) WIZARD_STATE[touchscreen_model]="mellow_fly_tft_v2" ;;
        2) WIZARD_STATE[touchscreen_model]="waveshare_spi_3_5" ;;
        3) WIZARD_STATE[touchscreen_model]="waveshare_spi_4" ;;
        4) WIZARD_STATE[touchscreen_model]="goodtft_3_5" ;;
        5) WIZARD_STATE[touchscreen_model]="generic_ili9486" ;;
    esac
}

select_display_rotation() {
    clear_screen
    print_header "Display Rotation"
    
    print_box_line "${WHITE}Select your display orientation:${NC}"
    print_empty_line
    print_box_line "Rotation depends on how your display is mounted."
    print_box_line "You can change this later if the touch is inverted."
    print_empty_line
    print_box_line "1) 0°   - Normal (default landscape)"
    print_box_line "2) 90°  - Rotated clockwise"
    print_box_line "3) 180° - Upside down"
    print_box_line "4) 270° - Rotated counter-clockwise"
    print_footer
    
    echo -en "${BYELLOW}Select rotation [1]${NC}: "
    read -r choice
    
    case "$choice" in
        2) WIZARD_STATE[touchscreen_rotation]="90" ;;
        3) WIZARD_STATE[touchscreen_rotation]="180" ;;
        4) WIZARD_STATE[touchscreen_rotation]="270" ;;
        *) WIZARD_STATE[touchscreen_rotation]="0" ;;
    esac
}

# ═══════════════════════════════════════════════════════════════════════════════
# PLATFORM DETECTION FOR TOUCH PANEL SETUP
# ═══════════════════════════════════════════════════════════════════════════════

detect_host_platform() {
    # Detect the host platform for touch panel configuration
    # Sets: PLATFORM_TYPE, PLATFORM_MODEL, OS_VERSION, CONFIG_TXT_PATH
    
    local platform_type="unknown"
    local platform_model=""
    local os_version=""
    local config_txt_path=""
    
    # Check for Raspberry Pi
    if [[ -f /proc/device-tree/model ]]; then
        local model_string
        model_string=$(cat /proc/device-tree/model 2>/dev/null | tr -d '\0')
        
        if [[ "$model_string" == *"Raspberry Pi"* ]]; then
            platform_type="raspberry_pi"
            
            # Extract Pi model
            if [[ "$model_string" == *"Pi 5"* ]]; then
                platform_model="pi5"
            elif [[ "$model_string" == *"Pi 4"* ]]; then
                platform_model="pi4"
            elif [[ "$model_string" == *"Pi 3"* ]]; then
                platform_model="pi3"
            elif [[ "$model_string" == *"Pi Zero 2"* ]]; then
                platform_model="pizero2"
            elif [[ "$model_string" == *"Pi Zero"* ]]; then
                platform_model="pizero"
            else
                platform_model="other_pi"
            fi
        elif [[ "$model_string" == *"CB1"* ]] || [[ "$model_string" == *"Manta"* ]]; then
            # BTT CB1 or Manta with CB1
            platform_type="cb1"
            platform_model="cb1"
        fi
    fi
    
    # Check for CB1/Armbian if not detected via device-tree
    if [[ "$platform_type" == "unknown" ]]; then
        if [[ -f /etc/armbian-release ]]; then
            platform_type="armbian"
            # Could be CB1 or other Armbian SBC
            if grep -q "BOARD=cb1" /etc/armbian-release 2>/dev/null; then
                platform_model="cb1"
                platform_type="cb1"
            else
                platform_model="generic_armbian"
            fi
        fi
    fi
    
    # Detect OS version (Debian codename)
    if [[ -f /etc/os-release ]]; then
        # shellcheck source=/dev/null
        source /etc/os-release
        case "${VERSION_CODENAME:-}" in
            bullseye) os_version="bullseye" ;;
            bookworm) os_version="bookworm" ;;
            buster)   os_version="buster" ;;
            *)        os_version="${VERSION_CODENAME:-unknown}" ;;
        esac
    fi
    
    # Determine config.txt path based on platform and OS
    if [[ "$platform_type" == "raspberry_pi" ]]; then
        if [[ "$os_version" == "bookworm" ]]; then
            # Bookworm moved config.txt to /boot/firmware/
            config_txt_path="/boot/firmware/config.txt"
        else
            # Bullseye and earlier
            config_txt_path="/boot/config.txt"
        fi
    elif [[ "$platform_type" == "cb1" ]]; then
        # CB1 uses Armbian-style configuration
        config_txt_path="/boot/armbianEnv.txt"
    else
        # Default to common location
        if [[ -f /boot/firmware/config.txt ]]; then
            config_txt_path="/boot/firmware/config.txt"
        elif [[ -f /boot/config.txt ]]; then
            config_txt_path="/boot/config.txt"
        else
            config_txt_path="/boot/config.txt"
        fi
    fi
    
    # Store results
    WIZARD_STATE[platform_type]="$platform_type"
    WIZARD_STATE[platform_model]="$platform_model"
    WIZARD_STATE[os_version]="$os_version"
    WIZARD_STATE[config_txt_path]="$config_txt_path"
    
    # Return success if platform was detected
    [[ "$platform_type" != "unknown" ]]
}

get_platform_display_name() {
    # Returns a human-readable platform name
    local platform="${WIZARD_STATE[platform_type]:-unknown}"
    local model="${WIZARD_STATE[platform_model]:-}"
    
    case "$platform" in
        raspberry_pi)
            case "$model" in
                pi5) echo "Raspberry Pi 5" ;;
                pi4) echo "Raspberry Pi 4" ;;
                pi3) echo "Raspberry Pi 3" ;;
                pizero2) echo "Raspberry Pi Zero 2" ;;
                pizero) echo "Raspberry Pi Zero" ;;
                *) echo "Raspberry Pi" ;;
            esac
            ;;
        cb1) echo "BTT CB1" ;;
        armbian) echo "Armbian SBC" ;;
        *) echo "Unknown Platform" ;;
    esac
}

generate_touch_panel_script() {
    # Generate a customized touch panel setup script based on user selections
    # Reads from displays.json and substitutes into the template
    
    local model="${WIZARD_STATE[touchscreen_model]:-}"
    local conn_type="${WIZARD_STATE[klipperscreen_type]:-}"
    local rotation="${WIZARD_STATE[touchscreen_rotation]:-0}"
    
    if [[ -z "$model" ]]; then
        echo -e "${RED}No touchscreen model selected${NC}"
        return 1
    fi
    
    local displays_json="${SCRIPT_DIR}/../templates/hardware/displays.json"
    local template="${SCRIPT_DIR}/lib/touch-panel-setup.sh.template"
    local output_dir="${HOME}/printer_data/config/scripts"
    local output_file="${output_dir}/touch-panel-setup.sh"
    
    if [[ ! -f "$displays_json" ]]; then
        echo -e "${RED}displays.json not found${NC}"
        return 1
    fi
    
    if [[ ! -f "$template" ]]; then
        echo -e "${RED}Template not found: $template${NC}"
        return 1
    fi
    
    # Extract display info from JSON using python
    local display_info
    display_info=$(python3 << EOF
import json
import sys

try:
    with open("$displays_json", 'r') as f:
        data = json.load(f)
    
    model = "$model"
    conn_type = "$conn_type"
    
    # Find the display in the touchscreens section
    touchscreens = data.get('touchscreens', {})
    display = None
    
    # Search in the connection type category
    if conn_type in touchscreens:
        display = touchscreens[conn_type].get(model)
    
    # If not found, search all categories
    if not display:
        for category in ['hdmi', 'dsi', 'spi_tft']:
            if category in touchscreens and model in touchscreens[category]:
                display = touchscreens[category][model]
                break
    
    if not display:
        print("ERROR:Display not found in database", file=sys.stderr)
        sys.exit(1)
    
    # Output display properties
    print(f"DISPLAY_NAME={display.get('name', model)}")
    print(f"DRIVER_REQUIRED={str(display.get('driver_required', False)).lower()}")
    print(f"DRIVER_REPO={display.get('driver_repo', '')}")
    print(f"DRIVER_SCRIPT={display.get('driver_script', '')}")
    print(f"OVERLAY_FIX={display.get('overlay_fix', '')}")
    print(f"OVERLAY_NAME={display.get('overlay', '')}")
    print(f"TOUCH_DEVICE_NAME={display.get('touch_device_name', '')}")
    print(f"I2C_REQUIRED={str(display.get('i2c_required', False)).lower()}")
    
    # Handle HDMI config if present
    hdmi_config = display.get('hdmi_config', {})
    if hdmi_config:
        config_parts = []
        for key, value in hdmi_config.items():
            config_parts.append(f"{key}={value}")
        print(f"HDMI_CONFIG={','.join(config_parts)}")
    else:
        print("HDMI_CONFIG=")

except Exception as e:
    print(f"ERROR:{e}", file=sys.stderr)
    sys.exit(1)
EOF
    )
    
    if [[ $? -ne 0 ]]; then
        echo -e "${RED}Failed to parse display configuration${NC}"
        return 1
    fi
    
    # Parse the output into variables
    local display_name="" driver_required="" driver_repo="" driver_script=""
    local overlay_fix="" overlay_name="" touch_device_name="" i2c_required="" hdmi_config=""
    
    while IFS='=' read -r key value; do
        case "$key" in
            DISPLAY_NAME) display_name="$value" ;;
            DRIVER_REQUIRED) driver_required="$value" ;;
            DRIVER_REPO) driver_repo="$value" ;;
            DRIVER_SCRIPT) driver_script="$value" ;;
            OVERLAY_FIX) overlay_fix="$value" ;;
            OVERLAY_NAME) overlay_name="$value" ;;
            TOUCH_DEVICE_NAME) touch_device_name="$value" ;;
            I2C_REQUIRED) i2c_required="$value" ;;
            HDMI_CONFIG) hdmi_config="$value" ;;
        esac
    done <<< "$display_info"
    
    # Create output directory
    mkdir -p "$output_dir"
    
    # Generate the script from template with substitutions
    local generation_date
    generation_date=$(date '+%Y-%m-%d %H:%M:%S')
    
    sed -e "s|{{DISPLAY_MODEL}}|$model|g" \
        -e "s|{{DISPLAY_NAME}}|$display_name|g" \
        -e "s|{{CONNECTION_TYPE}}|$conn_type|g" \
        -e "s|{{ROTATION}}|$rotation|g" \
        -e "s|{{DRIVER_REQUIRED}}|$driver_required|g" \
        -e "s|{{DRIVER_REPO}}|$driver_repo|g" \
        -e "s|{{DRIVER_SCRIPT}}|$driver_script|g" \
        -e "s|{{OVERLAY_FIX}}|$overlay_fix|g" \
        -e "s|{{OVERLAY_NAME}}|$overlay_name|g" \
        -e "s|{{TOUCH_DEVICE_NAME}}|$touch_device_name|g" \
        -e "s|{{I2C_REQUIRED}}|$i2c_required|g" \
        -e "s|{{HDMI_CONFIG}}|$hdmi_config|g" \
        -e "s|{{GENERATION_DATE}}|$generation_date|g" \
        "$template" > "$output_file"
    
    chmod +x "$output_file"
    
    echo -e "${GREEN}Touch panel setup script generated!${NC}"
    echo -e "${CYAN}Location: ${output_file}${NC}"
    echo ""
    echo -e "${YELLOW}To configure your touch panel, run:${NC}"
    echo -e "  ${BWHITE}sudo bash ${output_file}${NC}"
    echo ""
    
    return 0
}

offer_touch_panel_setup() {
    # Called after KlipperScreen selection to offer generating the setup script
    
    if [[ "${WIZARD_STATE[has_klipperscreen]}" != "yes" ]]; then
        return 0
    fi
    
    if [[ -z "${WIZARD_STATE[touchscreen_model]:-}" ]]; then
        return 0
    fi
    
    clear_screen
    print_header "Touch Panel Setup Script"
    
    print_box_line "${WHITE}Generate a touch panel setup script?${NC}"
    print_empty_line
    print_box_line "This will create a script that configures:"
    print_box_line "  - Display overlays and drivers"
    print_box_line "  - Touch calibration"
    print_box_line "  - Rotation settings"
    print_empty_line
    print_box_line "${CYAN}Selected: ${WIZARD_STATE[touchscreen_model]} (${WIZARD_STATE[touchscreen_rotation]:-0}°)${NC}"
    print_empty_line
    print_box_line "1) Generate setup script"
    print_box_line "2) Skip for now"
    print_footer
    
    echo -en "${BYELLOW}Choice [1]${NC}: "
    read -r choice
    
    case "$choice" in
        2) 
            echo -e "${CYAN}Skipped. You can generate the script later from the Extras menu.${NC}"
            sleep 1
            ;;
        *)
            echo ""
            if generate_touch_panel_script; then
                echo -e "${GREEN}Press Enter to continue...${NC}"
                read -r
            else
                echo -e "${RED}Failed to generate script. Press Enter to continue...${NC}"
                read -r
            fi
            ;;
    esac
}

select_lcd_display_type() {
    clear_screen
    print_header "LCD Display Type"
    
    print_box_line "${WHITE}Select your display type:${NC}"
    print_empty_line
    print_box_line "1) Mini 12864 (BTT/FYSETC Mini12864 - Voron style)"
    print_box_line "2) Full Graphic 12864 (RepRap ST7920)"
    print_box_line "3) BTT TFT35/TFT50 (12864 emulation mode)"
    print_box_line "4) OLED 128x64 (SSD1306/SH1106)"
    print_footer
    
    echo -en "${BYELLOW}Select type${NC}: "
    read -r choice
    
    case "$choice" in
        1) WIZARD_STATE[lcd_display_type]="mini12864" ;;
        2) WIZARD_STATE[lcd_display_type]="st7920" ;;
        3) WIZARD_STATE[lcd_display_type]="emulated_st7920" ;;
        4) WIZARD_STATE[lcd_display_type]="oled" ;;
    esac
}

# ═══════════════════════════════════════════════════════════════════════════════
# MACRO CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

menu_macros() {
    while true; do
        clear_screen
        print_header "Macro Configuration"
        
        print_box_line "${BWHITE}START_PRINT Building Blocks${NC}"
        print_empty_line
        
        # Heat soak
        local soak_status=$([[ "${WIZARD_STATE[macro_heat_soak]}" == "yes" ]] && echo "done" || echo "")
        local soak_time="${WIZARD_STATE[macro_heat_soak_time]:-0}"
        print_menu_item "1" "$soak_status" "Heat Soak" "$([[ "${WIZARD_STATE[macro_heat_soak]}" == "yes" ]] && echo "${soak_time}min" || echo "disabled")"
        
        # Chamber heating
        local chamber_status=$([[ "${WIZARD_STATE[macro_chamber_wait]}" == "yes" ]] && echo "done" || echo "")
        print_menu_item "2" "$chamber_status" "Chamber Heating" "$([[ "${WIZARD_STATE[macro_chamber_wait]}" == "yes" ]] && echo "enabled" || echo "disabled")"
        
        # Bed leveling (auto-detected)
        local level_method=""
        local z_count="${WIZARD_STATE[z_stepper_count]:-1}"
        case "$z_count" in
            4) level_method="QGL (auto)" ;;
            3) level_method="Z_TILT (auto)" ;;
            2) level_method="Z_TILT (auto)" ;;
            *) level_method="none" ;;
        esac
        print_menu_item "3" "done" "Bed Leveling" "${level_method}"
        
        # Bed mesh mode
        local mesh_mode="${WIZARD_STATE[macro_bed_mesh_mode]:-adaptive}"
        print_menu_item "4" "done" "Bed Mesh" "${mesh_mode}"
        
        # Nozzle cleaning
        local brush_status=$([[ "${WIZARD_STATE[macro_brush_enabled]}" == "yes" ]] && echo "done" || echo "")
        print_menu_item "5" "$brush_status" "Nozzle Cleaning" "$([[ "${WIZARD_STATE[macro_brush_enabled]}" == "yes" ]] && echo "enabled" || echo "disabled")"
        
        # Purge style
        local purge_style="${WIZARD_STATE[macro_purge_style]:-line}"
        print_menu_item "6" "done" "Purge Style" "${purge_style}"
        
        # LED status
        local led_status=$([[ "${WIZARD_STATE[macro_led_enabled]}" == "yes" ]] && echo "done" || echo "")
        print_menu_item "7" "$led_status" "LED Status" "$([[ "${WIZARD_STATE[macro_led_enabled]}" == "yes" ]] && echo "enabled" || echo "disabled")"
        
        print_empty_line
        print_box_line "${BWHITE}END_PRINT Options${NC}"
        print_empty_line
        
        # Park position
        local park_pos="${WIZARD_STATE[macro_park_position]:-front}"
        print_menu_item "8" "done" "Park Position" "${park_pos}"
        
        # Cooldown behavior
        local cooldown="${WIZARD_STATE[macro_cooldown_bed]:-yes}"
        print_menu_item "9" "done" "Cooldown" "bed:${cooldown}"
        
        print_separator
        print_action_item "S" "Show Slicer Start G-code"
        print_action_item "B" "Back"
        print_footer
        
        echo -en "${BYELLOW}Select option${NC}: "
        read -r choice
        
        case "$choice" in
            1) menu_macro_heat_soak ;;
            2) menu_macro_chamber ;;
            3) echo -e "${CYAN}Leveling method is auto-selected based on Z motor count${NC}"; wait_for_key ;;
            4) menu_macro_bed_mesh ;;
            5) menu_macro_nozzle_clean ;;
            6) menu_macro_purge ;;
            7) menu_macro_led ;;
            8) menu_macro_park ;;
            9) menu_macro_cooldown ;;
            [sS]) show_slicer_gcode ;;
            [bB]|"") return ;;
            *) ;;
        esac
    done
}

menu_macro_heat_soak() {
    clear_screen
    print_header "Heat Soak Configuration"
    
    print_box_line "Heat soak waits for the bed temperature to stabilize"
    print_box_line "after reaching target. Useful for enclosed printers."
    print_empty_line
    
    if confirm "Enable heat soak?"; then
        WIZARD_STATE[macro_heat_soak]="yes"
        
        local soak_time=$(prompt_input "Soak time (minutes)" "${WIZARD_STATE[macro_heat_soak_time]:-5}")
        WIZARD_STATE[macro_heat_soak_time]="$soak_time"
        
        echo -e "${GREEN}Heat soak enabled: ${soak_time} minutes${NC}"
    else
        WIZARD_STATE[macro_heat_soak]="no"
        echo -e "${YELLOW}Heat soak disabled${NC}"
    fi
    
    wait_for_key
}

menu_macro_chamber() {
    clear_screen
    print_header "Chamber Heating Configuration"
    
    # Check if chamber sensor is configured
    if [[ "${WIZARD_STATE[has_chamber_sensor]}" != "yes" ]]; then
        print_box_line "${YELLOW}No chamber sensor configured.${NC}"
        print_box_line "Configure a chamber sensor in Components > Extras first."
        print_footer
        wait_for_key
        return
    fi
    
    print_box_line "Chamber heating waits for the enclosure to reach"
    print_box_line "the target temperature before printing."
    print_empty_line
    
    if confirm "Enable chamber temperature wait?"; then
        WIZARD_STATE[macro_chamber_wait]="yes"
        
        local default_temp="${WIZARD_STATE[macro_chamber_temp_default]:-45}"
        local temp=$(prompt_input "Default chamber temperature (°C)" "$default_temp")
        WIZARD_STATE[macro_chamber_temp_default]="$temp"
        
        echo -e "${GREEN}Chamber wait enabled: ${temp}°C default${NC}"
    else
        WIZARD_STATE[macro_chamber_wait]="no"
        echo -e "${YELLOW}Chamber wait disabled${NC}"
    fi
    
    wait_for_key
}

menu_macro_bed_mesh() {
    clear_screen
    print_header "Bed Mesh Mode"
    
    print_box_line "${BWHITE}Select default bed mesh behavior:${NC}"
    print_empty_line
    print_menu_item "1" "" "adaptive" "Mesh only print area (requires slicer setup)"
    print_menu_item "2" "" "full" "Full bed mesh every print"
    print_menu_item "3" "" "saved" "Load previously saved mesh"
    print_menu_item "4" "" "none" "Skip mesh (trust existing)"
    print_footer
    
    echo -en "${BYELLOW}Select mode${NC}: "
    read -r choice
    
    case "$choice" in
        1) WIZARD_STATE[macro_bed_mesh_mode]="adaptive" ;;
        2) WIZARD_STATE[macro_bed_mesh_mode]="full" ;;
        3) WIZARD_STATE[macro_bed_mesh_mode]="saved" ;;
        4) WIZARD_STATE[macro_bed_mesh_mode]="none" ;;
        *) return ;;
    esac
    
    echo -e "${GREEN}Bed mesh mode set to: ${WIZARD_STATE[macro_bed_mesh_mode]}${NC}"
    wait_for_key
}

menu_macro_nozzle_clean() {
    clear_screen
    print_header "Nozzle Cleaning Configuration"
    
    print_box_line "Configure a physical brush/wiper for nozzle cleaning."
    print_box_line "The nozzle will wipe across the brush before printing."
    print_empty_line
    
    if confirm "Enable nozzle cleaning?"; then
        WIZARD_STATE[macro_brush_enabled]="yes"
        
        # Get bed size for default position
        local bed_x="${WIZARD_STATE[bed_size_x]:-300}"
        local bed_y="${WIZARD_STATE[bed_size_y]:-300}"
        
        echo -e "\n${CYAN}Brush Position Configuration${NC}"
        echo -e "Enter the position where your brush is mounted."
        echo -e "(Usually at the back of the bed, past Y max)"
        
        local brush_x=$(prompt_input "Brush X position" "${WIZARD_STATE[macro_brush_x]:-50}")
        WIZARD_STATE[macro_brush_x]="$brush_x"
        
        local brush_y=$(prompt_input "Brush Y position" "${WIZARD_STATE[macro_brush_y]:-$((bed_y + 5))}")
        WIZARD_STATE[macro_brush_y]="$brush_y"
        
        local brush_z=$(prompt_input "Brush Z height" "${WIZARD_STATE[macro_brush_z]:-1}")
        WIZARD_STATE[macro_brush_z]="$brush_z"
        
        local brush_width=$(prompt_input "Brush width (mm)" "${WIZARD_STATE[macro_brush_width]:-30}")
        WIZARD_STATE[macro_brush_width]="$brush_width"
        
        local wipe_count=$(prompt_input "Wipe count" "${WIZARD_STATE[macro_wipe_count]:-3}")
        WIZARD_STATE[macro_wipe_count]="$wipe_count"
        
        echo -e "${GREEN}Nozzle cleaning enabled at X:${brush_x} Y:${brush_y}${NC}"
    else
        WIZARD_STATE[macro_brush_enabled]="no"
        echo -e "${YELLOW}Nozzle cleaning disabled${NC}"
    fi
    
    wait_for_key
}

menu_macro_purge() {
    clear_screen
    print_header "Purge Style"
    
    print_box_line "${BWHITE}Select purge method:${NC}"
    print_empty_line
    print_menu_item "1" "" "line" "Simple line along bed edge"
    print_menu_item "2" "" "blob" "Blob into bucket (requires bucket)"
    print_menu_item "3" "" "adaptive" "Purge near print area (KAMP-style)"
    print_menu_item "4" "" "voron" "VORON-style bucket + brush"
    print_menu_item "5" "" "none" "No purging (slicer handles it)"
    print_footer
    
    echo -en "${BYELLOW}Select style${NC}: "
    read -r choice
    
    case "$choice" in
        1) WIZARD_STATE[macro_purge_style]="line" ;;
        2) 
            WIZARD_STATE[macro_purge_style]="blob"
            menu_macro_purge_bucket
            ;;
        3) WIZARD_STATE[macro_purge_style]="adaptive" ;;
        4) 
            WIZARD_STATE[macro_purge_style]="voron"
            menu_macro_purge_bucket
            ;;
        5) WIZARD_STATE[macro_purge_style]="none" ;;
        *) return ;;
    esac
    
    # Configure purge amount
    if [[ "${WIZARD_STATE[macro_purge_style]}" != "none" ]]; then
        local purge_amount=$(prompt_input "Purge amount (mm of filament)" "${WIZARD_STATE[macro_purge_amount]:-30}")
        WIZARD_STATE[macro_purge_amount]="$purge_amount"
    fi
    
    echo -e "${GREEN}Purge style set to: ${WIZARD_STATE[macro_purge_style]}${NC}"
    wait_for_key
}

menu_macro_purge_bucket() {
    echo -e "\n${CYAN}Bucket/Purge Position Configuration${NC}"
    
    local bed_x="${WIZARD_STATE[bed_size_x]:-300}"
    local bed_y="${WIZARD_STATE[bed_size_y]:-300}"
    
    local bucket_x=$(prompt_input "Bucket X position" "${WIZARD_STATE[macro_bucket_x]:-$((bed_x / 2))}")
    WIZARD_STATE[macro_bucket_x]="$bucket_x"
    
    local bucket_y=$(prompt_input "Bucket Y position" "${WIZARD_STATE[macro_bucket_y]:-$((bed_y + 5))}")
    WIZARD_STATE[macro_bucket_y]="$bucket_y"
    
    local bucket_z=$(prompt_input "Bucket Z height" "${WIZARD_STATE[macro_bucket_z]:-5}")
    WIZARD_STATE[macro_bucket_z]="$bucket_z"
}

menu_macro_led() {
    clear_screen
    print_header "LED Status Configuration"
    
    # Check if LEDs are configured
    if [[ "${WIZARD_STATE[has_leds]}" != "yes" && "${WIZARD_STATE[lighting_type]}" != "neopixel" ]]; then
        print_box_line "${YELLOW}No NeoPixel LEDs configured.${NC}"
        print_box_line "Configure LEDs in Components > Lighting first."
        print_footer
        wait_for_key
        return
    fi
    
    print_box_line "LED status updates change LED colors during"
    print_box_line "different phases of the print start sequence."
    print_empty_line
    print_box_line "Colors: ${CYAN}heating${NC} → ${BLUE}homing${NC} → ${MAGENTA}leveling${NC} → ${CYAN}meshing${NC} → ${WHITE}printing${NC}"
    print_empty_line
    
    if confirm "Enable LED status updates?"; then
        WIZARD_STATE[macro_led_enabled]="yes"
        
        local led_name=$(prompt_input "LED section name" "${WIZARD_STATE[macro_led_name]:-status_led}")
        WIZARD_STATE[macro_led_name]="$led_name"
        
        echo -e "${GREEN}LED status enabled for: ${led_name}${NC}"
    else
        WIZARD_STATE[macro_led_enabled]="no"
        echo -e "${YELLOW}LED status disabled${NC}"
    fi
    
    wait_for_key
}

menu_macro_park() {
    clear_screen
    print_header "Park Position"
    
    print_box_line "${BWHITE}Where should the toolhead park after printing?${NC}"
    print_empty_line
    print_menu_item "1" "" "front" "Front center (easy part removal)"
    print_menu_item "2" "" "back" "Back center"
    print_menu_item "3" "" "center" "Bed center"
    print_menu_item "4" "" "front_left" "Front left corner"
    print_menu_item "5" "" "front_right" "Front right corner"
    print_menu_item "6" "" "back_left" "Back left corner"
    print_menu_item "7" "" "back_right" "Back right corner"
    print_footer
    
    echo -en "${BYELLOW}Select position${NC}: "
    read -r choice
    
    case "$choice" in
        1) WIZARD_STATE[macro_park_position]="front" ;;
        2) WIZARD_STATE[macro_park_position]="back" ;;
        3) WIZARD_STATE[macro_park_position]="center" ;;
        4) WIZARD_STATE[macro_park_position]="front_left" ;;
        5) WIZARD_STATE[macro_park_position]="front_right" ;;
        6) WIZARD_STATE[macro_park_position]="back_left" ;;
        7) WIZARD_STATE[macro_park_position]="back_right" ;;
        *) return ;;
    esac
    
    # Z settings
    local z_hop=$(prompt_input "Z hop height (mm)" "${WIZARD_STATE[macro_park_z_hop]:-10}")
    WIZARD_STATE[macro_park_z_hop]="$z_hop"
    
    local z_max=$(prompt_input "Max Z for parking" "${WIZARD_STATE[macro_park_z_max]:-50}")
    WIZARD_STATE[macro_park_z_max]="$z_max"
    
    echo -e "${GREEN}Park position: ${WIZARD_STATE[macro_park_position]}, Z hop: ${z_hop}mm${NC}"
    wait_for_key
}

menu_macro_cooldown() {
    clear_screen
    print_header "Cooldown Behavior"
    
    print_box_line "${BWHITE}Configure what turns off after printing:${NC}"
    print_empty_line
    
    if confirm "Turn off bed heater?"; then
        WIZARD_STATE[macro_cooldown_bed]="yes"
    else
        WIZARD_STATE[macro_cooldown_bed]="no"
    fi
    
    if confirm "Turn off extruder?"; then
        WIZARD_STATE[macro_cooldown_extruder]="yes"
    else
        WIZARD_STATE[macro_cooldown_extruder]="no"
    fi
    
    if confirm "Turn off part cooling fan?"; then
        WIZARD_STATE[macro_cooldown_fans]="yes"
        
        local delay=$(prompt_input "Fan off delay (seconds, 0=immediate)" "${WIZARD_STATE[macro_fan_off_delay]:-0}")
        WIZARD_STATE[macro_fan_off_delay]="$delay"
    else
        WIZARD_STATE[macro_cooldown_fans]="no"
    fi
    
    local motor_delay=$(prompt_input "Motor off delay (seconds, 0=immediate)" "${WIZARD_STATE[macro_motor_off_delay]:-300}")
    WIZARD_STATE[macro_motor_off_delay]="$motor_delay"
    
    echo -e "${GREEN}Cooldown configured${NC}"
    wait_for_key
}

show_slicer_gcode() {
    clear_screen
    print_header "Slicer Start G-code"
    
    print_box_line "${BWHITE}Copy this to your slicer's Start G-code:${NC}"
    print_empty_line
    
    print_box_line "${CYAN}PrusaSlicer / SuperSlicer / OrcaSlicer:${NC}"
    print_empty_line
    echo -e "${GREEN}START_PRINT BED=[first_layer_bed_temperature] EXTRUDER=[first_layer_temperature]${NC}"
    echo ""
    
    # Show with optional parameters based on configuration
    local full_cmd="START_PRINT BED=[first_layer_bed_temperature] EXTRUDER=[first_layer_temperature]"
    
    if [[ "${WIZARD_STATE[macro_chamber_wait]}" == "yes" ]]; then
        full_cmd="${full_cmd} CHAMBER=[chamber_temperature]"
    fi
    
    full_cmd="${full_cmd} MATERIAL=[filament_type]"
    
    if [[ "${WIZARD_STATE[macro_bed_mesh_mode]}" == "adaptive" || "${WIZARD_STATE[macro_purge_style]}" == "adaptive" ]]; then
        echo -e "${YELLOW}For adaptive mesh/purge, also add:${NC}"
        echo -e "${GREEN}PRINT_MIN={first_layer_print_min[0]},{first_layer_print_min[1]} PRINT_MAX={first_layer_print_max[0]},{first_layer_print_max[1]}${NC}"
    fi
    
    print_empty_line
    print_box_line "${CYAN}Cura:${NC}"
    print_empty_line
    echo -e "${GREEN}START_PRINT BED={material_bed_temperature_layer_0} EXTRUDER={material_print_temperature_layer_0}${NC}"
    
    print_empty_line
    print_box_line "${CYAN}End G-code (all slicers):${NC}"
    print_empty_line
    echo -e "${GREEN}END_PRINT${NC}"
    
    print_footer
    wait_for_key
}

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION GENERATOR
# ═══════════════════════════════════════════════════════════════════════════════

generate_config() {
    clear_screen
    print_header "Generate Configuration"
    
    # Validate required fields
    local missing=()
    [[ -z "${WIZARD_STATE[board]}" ]] && missing+=("Board")
    [[ -z "${WIZARD_STATE[kinematics]}" ]] && missing+=("Kinematics")
    [[ -z "${WIZARD_STATE[bed_size_x]}" ]] && missing+=("Bed Size")
    
    if [[ ${#missing[@]} -gt 0 ]]; then
        echo -e "${RED}Missing required configuration:${NC}"
        for item in "${missing[@]}"; do
            echo -e "  • ${item}"
        done
        wait_for_key
        return
    fi
    
    # ═══════════════════════════════════════════════════════════════════════════
    # SAFETY WARNINGS
    # ═══════════════════════════════════════════════════════════════════════════
    echo -e "${BYELLOW}╔═══════════════════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BYELLOW}║${NC}  ${BRED}⚠️  IMPORTANT SAFETY WARNINGS  ⚠️${NC}                                           ${BYELLOW}║${NC}"
    echo -e "${BYELLOW}╠═══════════════════════════════════════════════════════════════════════════════╣${NC}"
    echo -e "${BYELLOW}║${NC}                                                                               ${BYELLOW}║${NC}"
    echo -e "${BYELLOW}║${NC}  ${BWHITE}Before using this config on your printer:${NC}                                   ${BYELLOW}║${NC}"
    echo -e "${BYELLOW}║${NC}                                                                               ${BYELLOW}║${NC}"
    echo -e "${BYELLOW}║${NC}  ${CYAN}1.${NC} REVIEW generated files - verify pin assignments match your wiring        ${BYELLOW}║${NC}"
    echo -e "${BYELLOW}║${NC}  ${CYAN}2.${NC} BACKUP existing config - save your current printer.cfg first             ${BYELLOW}║${NC}"
    echo -e "${BYELLOW}║${NC}  ${CYAN}3.${NC} TEST with motors off - use STEPPER_BUZZ to verify directions             ${BYELLOW}║${NC}"
    echo -e "${BYELLOW}║${NC}  ${CYAN}4.${NC} START cold - don't heat bed/nozzle until movement is verified            ${BYELLOW}║${NC}"
    echo -e "${BYELLOW}║${NC}  ${CYAN}5.${NC} WATCH first home - keep hand on emergency stop                           ${BYELLOW}║${NC}"
    echo -e "${BYELLOW}║${NC}                                                                               ${BYELLOW}║${NC}"
    echo -e "${BYELLOW}║${NC}  ${DIM}See docs/USAGE.md for complete safety checklist.${NC}                            ${BYELLOW}║${NC}"
    echo -e "${BYELLOW}╚═══════════════════════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    
    print_box_line "${BWHITE}Configuration Summary:${NC}"
    print_box_line "• Board: ${WIZARD_STATE[board_name]}"
    print_box_line "• Kinematics: ${WIZARD_STATE[kinematics]}"
    print_box_line "• Bed: ${WIZARD_STATE[bed_size_x]}x${WIZARD_STATE[bed_size_y]}x${WIZARD_STATE[bed_size_z]}"
    print_box_line "• Probe: ${WIZARD_STATE[probe_type]:-none}"
    [[ -n "${WIZARD_STATE[probe_mode]}" ]] && print_box_line "• Probe Mode: ${WIZARD_STATE[probe_mode]}"
    print_empty_line
    print_box_line "Output directory: ${OUTPUT_DIR}"
    print_footer
    
    echo -e "${BYELLOW}I understand the risks and have read the safety warnings.${NC}"
    if ! confirm "Generate configuration?"; then
        return
    fi
    
    echo -e "\n${CYAN}Generating configuration...${NC}"
    
    # Save state to disk BEFORE generating (Python scripts read from file!)
    save_state
    
    # Create output directory
    mkdir -p "${OUTPUT_DIR}"
    
    # Generate files
    generate_hardware_cfg
    generate_macros_cfg
    generate_homing_cfg
    generate_printer_cfg
    
    echo -e "${GREEN}Configuration generated successfully!${NC}"
    echo -e "\nFiles created in: ${CYAN}${OUTPUT_DIR}${NC}"
    echo -e "Main config: ${CYAN}${PRINTER_CFG}${NC}"
    
    if confirm "Add Moonraker update manager entry?"; then
        add_moonraker_entry
    fi
    
    wait_for_key
}

generate_hardware_cfg() {
    # Use Python generator for hardware config (reads from hardware-state.json)
    if [[ -f "${HARDWARE_STATE_FILE}" ]]; then
        python3 "${SCRIPT_DIR}/generate-config.py" --output-dir "${OUTPUT_DIR}" --hardware-only
        if [[ $? -eq 0 ]]; then
            echo -e "  ${GREEN}✓${NC} hardware.cfg (from port assignments)"
            return 0
        fi
    fi
    
    # Fallback: generate placeholder config if no hardware state
    local output="${OUTPUT_DIR}/hardware.cfg"
    
    cat > "${output}" << EOF
# ═══════════════════════════════════════════════════════════════════════════════
# HARDWARE CONFIGURATION
# Generated by gschpoozi - $(date +%Y-%m-%d)
# Board: ${WIZARD_STATE[board_name]:-Not configured}
#
# NOTE: Pin assignments not configured!
# Run the Hardware Setup wizard to configure port assignments:
#   python3 ~/gschpoozi/scripts/setup-hardware.py
# ═══════════════════════════════════════════════════════════════════════════════

# ─────────────────────────────────────────────────────────────────────────────
# MCU
# ─────────────────────────────────────────────────────────────────────────────
[mcu]
serial: /dev/serial/by-id/REPLACE_WITH_YOUR_MCU_ID
# Run: ls /dev/serial/by-id/* to find your MCU

# ─────────────────────────────────────────────────────────────────────────────
# PRINTER
# ─────────────────────────────────────────────────────────────────────────────
[printer]
kinematics: ${WIZARD_STATE[kinematics]:-corexy}
max_velocity: 500
max_accel: 10000
max_z_velocity: 30
max_z_accel: 350

# ─────────────────────────────────────────────────────────────────────────────
# STEPPERS - CONFIGURE PORT ASSIGNMENTS FIRST!
# ─────────────────────────────────────────────────────────────────────────────
[stepper_x]
step_pin: REPLACE_PIN  # Run setup-hardware.py
dir_pin: REPLACE_PIN
enable_pin: !REPLACE_PIN
microsteps: 16
rotation_distance: 40
endstop_pin: REPLACE_PIN
position_min: ${WIZARD_STATE[position_min_x]:-0}
position_max: ${WIZARD_STATE[bed_size_x]:-300}
position_endstop: ${WIZARD_STATE[position_endstop_x]:-0}
homing_speed: 80

[stepper_y]
step_pin: REPLACE_PIN
dir_pin: REPLACE_PIN
enable_pin: !REPLACE_PIN
microsteps: 16
rotation_distance: 40
endstop_pin: REPLACE_PIN
position_min: ${WIZARD_STATE[position_min_y]:-0}
position_max: ${WIZARD_STATE[bed_size_y]:-300}
position_endstop: ${WIZARD_STATE[position_endstop_y]:-0}
homing_speed: 80

[stepper_z]
step_pin: REPLACE_PIN
dir_pin: REPLACE_PIN
enable_pin: !REPLACE_PIN
microsteps: 16
rotation_distance: 8
EOF

    # Add Z endstop configuration based on probe type
    if [[ "${WIZARD_STATE[probe_type]}" == "endstop" ]]; then
        cat >> "${output}" << EOF
endstop_pin: REPLACE_PIN  # Physical Z endstop
position_endstop: ${WIZARD_STATE[position_endstop_z]:-0}
position_min: -5
position_max: ${WIZARD_STATE[bed_size_z]:-350}
homing_speed: 15
EOF
    else
        cat >> "${output}" << EOF
endstop_pin: probe:z_virtual_endstop
homing_retract_dist: 0  # Required for probe-based Z homing
position_min: -5
position_max: ${WIZARD_STATE[bed_size_z]:-350}
homing_speed: 15
EOF
    fi

    cat >> "${output}" << EOF

[extruder]
step_pin: REPLACE_PIN
dir_pin: REPLACE_PIN
enable_pin: !REPLACE_PIN
heater_pin: REPLACE_PIN
sensor_pin: REPLACE_PIN

[heater_bed]
heater_pin: REPLACE_PIN
sensor_pin: REPLACE_PIN

[fan]
pin: REPLACE_PIN

# This is a placeholder config. Run setup-hardware.py to configure ports.
EOF

    echo -e "  ${YELLOW}⚠${NC} hardware.cfg (placeholder - run setup-hardware.py)"
}

generate_macros_cfg() {
    # Use Python generator for macros (reads from wizard state)
    python3 "${SCRIPT_DIR}/generate-config.py" --output-dir "${OUTPUT_DIR}" --macros-only
    if [[ $? -eq 0 ]]; then
        echo -e "  ${GREEN}✓${NC} macros.cfg (from wizard configuration)"
        echo -e "  ${GREEN}✓${NC} macros-config.cfg (user-editable variables)"
    else
        echo -e "  ${RED}✗${NC} Failed to generate macros"
    fi
}

generate_homing_cfg() {
    local output="${OUTPUT_DIR}/homing.cfg"
    
    # Get Z homing position from wizard state (for homing override example)
    local z_home_x="${WIZARD_STATE[z_home_x]:-$((${WIZARD_STATE[bed_size_x]:-300} / 2))}"
    local z_home_y="${WIZARD_STATE[z_home_y]:-$((${WIZARD_STATE[bed_size_y]:-300} / 2))}"
    
    cat > "${output}" << EOF
# ═══════════════════════════════════════════════════════════════════════════════
# HOMING
# Generated by gschpoozi
# ═══════════════════════════════════════════════════════════════════════════════
# NOTE: [safe_z_home] and [bed_mesh] are configured in hardware.cfg
# based on your probe type and wizard settings.

# ─────────────────────────────────────────────────────────────────────────────
# HOMING OVERRIDE (Optional - uncomment if needed)
# ─────────────────────────────────────────────────────────────────────────────
# Use this if you need custom homing behavior (e.g., sensorless homing cleanup)
#[homing_override]
#axes: xyz
#gcode:
#    {% set home_all = 'X' not in params and 'Y' not in params and 'Z' not in params %}
#    
#    {% if home_all or 'X' in params %}
#        G28 X
#    {% endif %}
#    
#    {% if home_all or 'Y' in params %}
#        G28 Y
#    {% endif %}
#    
#    {% if home_all or 'Z' in params %}
#        G1 X${z_home_x} Y${z_home_y} F6000
#        G28 Z
#        G1 Z10 F3000
#    {% endif %}
EOF

    echo -e "  ${GREEN}✓${NC} homing.cfg"
}

generate_printer_cfg() {
    # Only create printer.cfg if it doesn't exist
    if [[ -f "${PRINTER_CFG}" ]]; then
        echo -e "  ${YELLOW}!${NC} printer.cfg exists - not overwriting"
        echo -e "    Add these includes manually if needed:"
        echo -e "    ${CYAN}[include gschpoozi/hardware.cfg]${NC}"
        echo -e "    ${CYAN}[include gschpoozi/macros-config.cfg]${NC}"
        echo -e "    ${CYAN}[include gschpoozi/macros.cfg]${NC}"
        echo -e "    ${CYAN}[include gschpoozi/homing.cfg]${NC}"
        return
    fi
    
    cat > "${PRINTER_CFG}" << EOF
# ═══════════════════════════════════════════════════════════════════════════════
# PRINTER CONFIGURATION
# Generated by gschpoozi - $(date +%Y-%m-%d)
# https://github.com/gueee/gschpoozi
# ═══════════════════════════════════════════════════════════════════════════════

# ─────────────────────────────────────────────────────────────────────────────
# GSCHPOOZI INCLUDES
# NOTE: macros-config.cfg MUST be included before macros.cfg
# ─────────────────────────────────────────────────────────────────────────────
[include gschpoozi/hardware.cfg]
[include gschpoozi/macros-config.cfg]
[include gschpoozi/macros.cfg]
[include gschpoozi/homing.cfg]

# Optional: Uncomment if you have these features
#[include gschpoozi/calibration.cfg]

# ═══════════════════════════════════════════════════════════════════════════════
# YOUR OVERRIDES BELOW
# Add your customizations here - they won't be touched by updates
# ═══════════════════════════════════════════════════════════════════════════════

# Example: Override pressure advance
#[extruder]
#pressure_advance: 0.05

# Example: Add a custom macro
#[gcode_macro MY_MACRO]
#gcode:
#    G28



#*# <---------------------- SAVE_CONFIG ---------------------->
#*# DO NOT EDIT THIS BLOCK OR BELOW. The contents are auto-generated.
#*#
EOF

    echo -e "  ${GREEN}✓${NC} printer.cfg"
}

add_moonraker_entry() {
    local moonraker_conf="${DEFAULT_CONFIG_DIR}/moonraker.conf"
    local entry="
##### gschpoozi Configuration Update Manager ----------------
[update_manager gschpoozi]
type: git_repo
primary_branch: main
path: ~/gschpoozi
origin: https://github.com/gueee/gschpoozi.git
is_system_service: False
managed_services: klipper
info_tags:
    desc=gschpoozi Klipper Configuration Framework
"
    
    if [[ ! -f "${moonraker_conf}" ]]; then
        echo -e "${YELLOW}moonraker.conf not found at ${moonraker_conf}${NC}"
        echo -e "Add this to your moonraker.conf manually:"
        echo "$entry"
        return
    fi
    
    # Check if entry already exists
    if grep -q "\[update_manager gschpoozi\]" "${moonraker_conf}"; then
        echo -e "${GREEN}Update manager entry already exists in moonraker.conf${NC}"
        return
    fi
    
    # Add entry to moonraker.conf
    echo "$entry" >> "${moonraker_conf}"
    echo -e "${GREEN}✓ Added update manager entry to moonraker.conf${NC}"
    echo -e "${CYAN}Restart Moonraker to see gschpoozi in the update manager.${NC}"
}

# ═══════════════════════════════════════════════════════════════════════════════
# EXIT
# ═══════════════════════════════════════════════════════════════════════════════

exit_wizard() {
    if confirm "Save progress before exiting?"; then
        save_state
        echo -e "${GREEN}Progress saved!${NC}"
    fi
    echo -e "\n${CYAN}Thanks for using gschpoozi!${NC}"
    exit 0
}

# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

main() {
    # Initialize state
    init_state
    
    # Try to load previous state
    if load_state; then
        echo -e "${CYAN}Loaded previous configuration...${NC}"
        sleep 1
    fi
    
    # Check for MCU version issues (dirty flag usually means linux MCU needs update)
    if is_klipper_dirty; then
        check_mcu_versions
    fi
    
    # Main loop
    while true; do
        show_top_menu
    done
}

# Run main
main "$@"


