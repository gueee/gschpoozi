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

print_header() {
    local width=60
    local title="$1"
    local padding=$(( (width - ${#title} - 2) / 2 ))
    
    echo -e "${BCYAN}"
    echo -n "${BOX_TL}"
    printf "${BOX_H}%.0s" $(seq 1 $width)
    echo "${BOX_TR}"
    
    echo -n "${BOX_V}"
    printf " %.0s" $(seq 1 $padding)
    echo -n " ${title} "
    printf " %.0s" $(seq 1 $((width - padding - ${#title} - 2)))
    echo "${BOX_V}"
    
    echo -n "${BOX_LT}"
    printf "${BOX_H}%.0s" $(seq 1 $width)
    echo "${BOX_RT}"
    echo -e "${NC}"
}

print_footer() {
    local width=60
    echo -e "${BCYAN}"
    echo -n "${BOX_BL}"
    printf "${BOX_H}%.0s" $(seq 1 $width)
    echo "${BOX_BR}"
    echo -e "${NC}"
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
    
    if [[ -n "$value" ]]; then
        echo -e "${BCYAN}${BOX_V}${NC}  ${BWHITE}${num})${NC} ${status_icon} ${label}: ${CYAN}${value}${NC}"
    else
        echo -e "${BCYAN}${BOX_V}${NC}  ${BWHITE}${num})${NC} ${status_icon} ${label}"
    fi
}

print_separator() {
    local width=60
    echo -e "${BCYAN}${BOX_LT}$(printf "${BOX_H}%.0s" $(seq 1 $width))${BOX_RT}${NC}"
}

print_action_item() {
    local key="$1"
    local label="$2"
    echo -e "${BCYAN}${BOX_V}${NC}  ${BGREEN}${key})${NC} ${label}"
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
        
        echo -e "${BCYAN}${BOX_V}${NC}  ${YELLOW}Potential MCU issues detected!${NC}"
        echo -e "${BCYAN}${BOX_V}${NC}"
        echo -e "${BCYAN}${BOX_V}${NC}  Host Version: ${BWHITE}${host_version}${NC}"
        
        if $is_dirty; then
            echo -e "${BCYAN}${BOX_V}${NC}"
            echo -e "${BCYAN}${BOX_V}${NC}  ${YELLOW}⚠ Klipper marked as 'dirty'${NC}"
            echo -e "${BCYAN}${BOX_V}${NC}  ${WHITE}This usually means the Linux MCU needs updating.${NC}"
            echo -e "${BCYAN}${BOX_V}${NC}  ${WHITE}The Linux MCU runs on the Pi for GPIO/sensors.${NC}"
        fi
        
        print_separator
        echo -e "${BCYAN}${BOX_V}${NC}  ${BWHITE}Recommended: Update Linux Process MCU${NC}"
        echo -e "${BCYAN}${BOX_V}${NC}  This will rebuild and reinstall the host MCU service."
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

        echo -e "${BCYAN}${BOX_V}${NC}  ${BWHITE}Stepper Identification & Direction Calibration${NC}"
        echo -e "${BCYAN}${BOX_V}${NC}"
        echo -e "${BCYAN}${BOX_V}${NC}  This generates macros to help you:"
        echo -e "${BCYAN}${BOX_V}${NC}  - Identify which physical motor is on which driver"
        echo -e "${BCYAN}${BOX_V}${NC}  - Verify motor directions are correct"
        if [[ "$is_awd" == "yes" ]]; then
            echo -e "${BCYAN}${BOX_V}${NC}  - ${GREEN}Test AWD motor pairs safely (one pair at a time)${NC}"
        fi
        echo -e "${BCYAN}${BOX_V}${NC}"

        print_separator
        echo -e "${BCYAN}${BOX_V}${NC}  ${BWHITE}Your Configuration:${NC}"
        echo -e "${BCYAN}${BOX_V}${NC}  Kinematics: ${CYAN}${kinematics}${NC}"
        echo -e "${BCYAN}${BOX_V}${NC}  Z Motors: ${CYAN}${z_count}${NC}"
        echo -e "${BCYAN}${BOX_V}${NC}  Driver: ${CYAN}${driver}${NC}"
        if [[ "$is_tmc" == "yes" ]]; then
            echo -e "${BCYAN}${BOX_V}${NC}  TMC Status: ${GREEN}TMC query macros will be included${NC}"
        fi
        echo -e "${BCYAN}${BOX_V}${NC}"

        print_separator
        echo -e "${BCYAN}${BOX_V}${NC}  ${BWHITE}Available Macros (after generation):${NC}"
        echo -e "${BCYAN}${BOX_V}${NC}"
        echo -e "${BCYAN}${BOX_V}${NC}  ${CYAN}STEPPER_CALIBRATION_WIZARD${NC} - Display calibration instructions"
        echo -e "${BCYAN}${BOX_V}${NC}  ${CYAN}IDENTIFY_ALL_STEPPERS${NC} - Buzz each motor for identification"
        echo -e "${BCYAN}${BOX_V}${NC}  ${CYAN}IDENTIFY_STEPPER STEPPER=name${NC} - Buzz a single motor"
        if [[ "$is_tmc" == "yes" ]]; then
            echo -e "${BCYAN}${BOX_V}${NC}  ${CYAN}QUERY_TMC_STATUS${NC} - Query all TMC driver registers"
        fi
        if [[ "$is_awd" == "yes" ]]; then
            echo -e "${BCYAN}${BOX_V}${NC}"
            echo -e "${BCYAN}${BOX_V}${NC}  ${BWHITE}AWD-Specific (safe pair testing):${NC}"
            echo -e "${BCYAN}${BOX_V}${NC}  ${CYAN}AWD_FULL_TEST${NC} - Complete pair-by-pair calibration"
            echo -e "${BCYAN}${BOX_V}${NC}  ${CYAN}AWD_TEST_PAIR_A${NC} - Test X+Y only (X1+Y1 disabled)"
            echo -e "${BCYAN}${BOX_V}${NC}  ${CYAN}AWD_TEST_PAIR_B${NC} - Test X1+Y1 only (X+Y disabled)"
            echo -e "${BCYAN}${BOX_V}${NC}  ${CYAN}AWD_ENABLE_ALL${NC} - Re-enable all motors"
        else
            echo -e "${BCYAN}${BOX_V}${NC}  ${CYAN}COREXY_DIRECTION_CHECK${NC} - Test CoreXY directions"
        fi
        if [[ "$z_count" -gt 1 ]]; then
            echo -e "${BCYAN}${BOX_V}${NC}  ${CYAN}Z_DIRECTION_CHECK${NC} - Verify all Z motors match"
        fi
        echo -e "${BCYAN}${BOX_V}${NC}"

        print_separator
        print_action_item "G" "Generate calibration.cfg now"
        print_action_item "I" "Show calibration instructions"
        print_action_item "B" "Back"
        print_footer

        echo -en "${BYELLOW}Select option${NC}: "
        read -r choice

        case "$choice" in
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

show_calibration_instructions() {
    local is_awd="$1"
    local is_tmc="$2"
    local z_count="$3"

    clear_screen
    print_header "Stepper Calibration Instructions"

    echo -e "${BCYAN}${BOX_V}${NC}"
    echo -e "${BCYAN}${BOX_V}${NC}  ${BWHITE}STEP 1: Generate Configuration${NC}"
    echo -e "${BCYAN}${BOX_V}${NC}  Generate calibration.cfg and add to printer.cfg:"
    echo -e "${BCYAN}${BOX_V}${NC}  ${CYAN}[include gschpoozi/calibration.cfg]${NC}"
    echo -e "${BCYAN}${BOX_V}${NC}  Then restart Klipper."
    echo -e "${BCYAN}${BOX_V}${NC}"

    echo -e "${BCYAN}${BOX_V}${NC}  ${BWHITE}STEP 2: Identify Motors${NC}"
    echo -e "${BCYAN}${BOX_V}${NC}  Run from console: ${CYAN}IDENTIFY_ALL_STEPPERS${NC}"
    echo -e "${BCYAN}${BOX_V}${NC}  Watch each motor and note which one moves."
    echo -e "${BCYAN}${BOX_V}${NC}  This helps verify your wiring is correct."
    echo -e "${BCYAN}${BOX_V}${NC}"

    if [[ "$is_tmc" == "yes" ]]; then
        echo -e "${BCYAN}${BOX_V}${NC}  ${BWHITE}STEP 3: Check TMC Communication${NC}"
        echo -e "${BCYAN}${BOX_V}${NC}  Run: ${CYAN}QUERY_TMC_STATUS${NC}"
        echo -e "${BCYAN}${BOX_V}${NC}  Verify no 00000000 or ffffffff errors."
        echo -e "${BCYAN}${BOX_V}${NC}  Look for 'ola'/'olb' flags = motor disconnected."
        echo -e "${BCYAN}${BOX_V}${NC}"
    fi

    if [[ "$is_awd" == "yes" ]]; then
        echo -e "${BCYAN}${BOX_V}${NC}  ${BWHITE}STEP 4: AWD Safe Pair Testing${NC}"
        echo -e "${BCYAN}${BOX_V}${NC}  Run: ${CYAN}AWD_FULL_TEST${NC}"
        echo -e "${BCYAN}${BOX_V}${NC}"
        echo -e "${BCYAN}${BOX_V}${NC}  This tests motors in pairs to prevent fighting:"
        echo -e "${BCYAN}${BOX_V}${NC}  - First test: Only X+Y move (X1+Y1 disabled)"
        echo -e "${BCYAN}${BOX_V}${NC}  - Second test: Only X1+Y1 move (X+Y disabled)"
        echo -e "${BCYAN}${BOX_V}${NC}"
        echo -e "${BCYAN}${BOX_V}${NC}  Both pairs should move the toolhead identically."
        echo -e "${BCYAN}${BOX_V}${NC}  If they don't match, adjust dir_pins."
        echo -e "${BCYAN}${BOX_V}${NC}"
    else
        echo -e "${BCYAN}${BOX_V}${NC}  ${BWHITE}STEP 4: Direction Check${NC}"
        echo -e "${BCYAN}${BOX_V}${NC}  Run: ${CYAN}COREXY_DIRECTION_CHECK${NC}"
        echo -e "${BCYAN}${BOX_V}${NC}  Verify +X goes right, +Y goes back."
        echo -e "${BCYAN}${BOX_V}${NC}"
    fi

    if [[ "$z_count" -gt 1 ]]; then
        echo -e "${BCYAN}${BOX_V}${NC}  ${BWHITE}STEP 5: Z Axis Verification${NC}"
        echo -e "${BCYAN}${BOX_V}${NC}  Run: ${CYAN}Z_DIRECTION_CHECK${NC}"
        echo -e "${BCYAN}${BOX_V}${NC}  All ${z_count} Z motors should move the same direction."
        echo -e "${BCYAN}${BOX_V}${NC}"
    fi

    print_separator
    echo -e "${BCYAN}${BOX_V}${NC}  ${BWHITE}Resources:${NC}"
    echo -e "${BCYAN}${BOX_V}${NC}  ${CYAN}https://www.klipper3d.org/Config_checks.html${NC}"
    echo -e "${BCYAN}${BOX_V}${NC}  ${CYAN}https://mpx.wiki/Troubleshooting/corexy-direction${NC}"
    print_footer
}

# Interactive MCU firmware update menu
menu_mcu_firmware_update() {
    while true; do
        clear_screen
        print_header "MCU Firmware Update"
        
        local host_version=$(get_klipper_host_version)
        echo -e "${BCYAN}${BOX_V}${NC}  Klipper Host Version: ${BWHITE}${host_version}${NC}"
        echo -e "${BCYAN}${BOX_V}${NC}"
        echo -e "${BCYAN}${BOX_V}${NC}  ${YELLOW}Note: MCU firmware must match host version${NC}"
        echo -e "${BCYAN}${BOX_V}${NC}  ${YELLOW}for Klipper to communicate properly.${NC}"
        echo -e "${BCYAN}${BOX_V}${NC}"
        
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
        
        echo -e "${BCYAN}${BOX_V}${NC}"
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
    
    echo -e "${BCYAN}${BOX_V}${NC}  Scanning for USB MCUs..."
    echo -e "${BCYAN}${BOX_V}${NC}"
    
    local -a devices
    mapfile -t devices < <(detect_usb_mcus)
    
    if [[ ${#devices[@]} -eq 0 ]]; then
        echo -e "${BCYAN}${BOX_V}${NC}  ${YELLOW}No USB MCUs found.${NC}"
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
        echo -e "${BCYAN}${BOX_V}${NC}  ${BWHITE}${num})${NC} ${desc}: ${display_path}"
        ((num++))
    done
    
    echo -e "${BCYAN}${BOX_V}${NC}"
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
    
    echo -e "${BCYAN}${BOX_V}${NC}  Scanning CAN bus for devices..."
    echo -e "${BCYAN}${BOX_V}${NC}"
    
    local -a uuids
    mapfile -t uuids < <(detect_can_mcus)
    
    if [[ ${#uuids[@]} -eq 0 ]]; then
        echo -e "${BCYAN}${BOX_V}${NC}  ${YELLOW}No CAN devices found.${NC}"
        echo -e "${BCYAN}${BOX_V}${NC}  ${YELLOW}Make sure can0 is up and devices are powered.${NC}"
        print_footer
        wait_for_key
        return
    fi
    
    local num=1
    for uuid in "${uuids[@]}"; do
        echo -e "${BCYAN}${BOX_V}${NC}  ${BWHITE}${num})${NC} UUID: ${uuid}"
        ((num++))
    done
    
    echo -e "${BCYAN}${BOX_V}${NC}"
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
        
        echo -e "${BCYAN}${BOX_V}${NC}  CAN Interface Status: ${can_status}"
        if [[ "$bitrate" != "N/A" && "$bitrate" != "0" ]]; then
            echo -e "${BCYAN}${BOX_V}${NC}  Bitrate: ${BWHITE}${bitrate} bps${NC}"
        fi
        
        # Show selected CAN adapter
        local can_adapter="${WIZARD_STATE[can_adapter]:-not selected}"
        echo -e "${BCYAN}${BOX_V}${NC}  CAN Adapter: ${BWHITE}${can_adapter}${NC}"
        echo -e "${BCYAN}${BOX_V}${NC}"
        print_separator
        
        print_menu_item "1" "" "Select CAN adapter"
        print_menu_item "2" "" "Setup CAN interface (create config file)"
        print_menu_item "3" "" "Bring up CAN interface manually"
        print_menu_item "4" "" "Check CAN requirements"
        print_menu_item "5" "" "Diagnose CAN issues"
        print_menu_item "6" "" "Install Katapult (optional bootloader)"
        echo -e "${BCYAN}${BOX_V}${NC}"
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
    
    echo -e "${BCYAN}${BOX_V}${NC}  How is your CAN bus connected to the Pi?"
    echo -e "${BCYAN}${BOX_V}${NC}"
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
    
    echo -e "${BCYAN}${BOX_V}${NC}  This will create /etc/network/interfaces.d/can0"
    echo -e "${BCYAN}${BOX_V}${NC}  to automatically bring up the CAN interface on boot."
    echo -e "${BCYAN}${BOX_V}${NC}"
    print_separator
    
    echo -e "${BCYAN}${BOX_V}${NC}  Select CAN bitrate:"
    echo -e "${BCYAN}${BOX_V}${NC}"
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
    
    echo -e "${BCYAN}${BOX_V}${NC}  Select CAN bitrate:"
    echo -e "${BCYAN}${BOX_V}${NC}"
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
    
    echo -e "${BCYAN}${BOX_V}${NC}  Checking CAN bus requirements..."
    echo -e "${BCYAN}${BOX_V}${NC}"
    
    local issues
    issues=$(check_can_requirements "can0")
    
    if [[ -z "$issues" ]]; then
        echo -e "${BCYAN}${BOX_V}${NC}  ${GREEN}✓ All CAN requirements met!${NC}"
        echo -e "${BCYAN}${BOX_V}${NC}"
        echo -e "${BCYAN}${BOX_V}${NC}  Interface: can0"
        echo -e "${BCYAN}${BOX_V}${NC}  Bitrate: $(get_can_bitrate can0) bps"
        echo -e "${BCYAN}${BOX_V}${NC}  Status: UP"
    else
        echo -e "${BCYAN}${BOX_V}${NC}  ${RED}Issues found:${NC}"
        while IFS= read -r issue; do
            echo -e "${BCYAN}${BOX_V}${NC}  ${YELLOW}• ${issue}${NC}"
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
    
    echo -e "${BCYAN}${BOX_V}${NC}  Katapult (formerly CanBoot) is a bootloader that allows"
    echo -e "${BCYAN}${BOX_V}${NC}  updating Klipper firmware over the CAN bus without"
    echo -e "${BCYAN}${BOX_V}${NC}  physically connecting USB cables."
    echo -e "${BCYAN}${BOX_V}${NC}"
    echo -e "${BCYAN}${BOX_V}${NC}  ${YELLOW}Note: Katapult is optional but highly recommended${NC}"
    echo -e "${BCYAN}${BOX_V}${NC}  ${YELLOW}for CAN-based toolhead boards.${NC}"
    echo -e "${BCYAN}${BOX_V}${NC}"
    
    if is_katapult_installed; then
        echo -e "${BCYAN}${BOX_V}${NC}  Status: ${GREEN}Installed${NC}"
    else
        echo -e "${BCYAN}${BOX_V}${NC}  Status: ${RED}Not installed${NC}"
    fi
    
    print_separator
    
    if is_katapult_installed; then
        print_menu_item "1" "" "Update Katapult (git pull)"
        print_menu_item "2" "" "Add to Moonraker update manager"
    else
        print_menu_item "1" "" "Install Katapult"
    fi
    echo -e "${BCYAN}${BOX_V}${NC}"
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
    
    echo -e "${BCYAN}${BOX_V}${NC}  Running diagnostics..."
    echo -e "${BCYAN}${BOX_V}${NC}"
    
    local has_issues=0
    
    # Check 1: CAN interface exists
    echo -e "${BCYAN}${BOX_V}${NC}  ${BWHITE}1. CAN Interface (can0):${NC}"
    if ip link show can0 &>/dev/null; then
        echo -e "${BCYAN}${BOX_V}${NC}     ${GREEN}✓ Interface exists${NC}"
        
        # Check if UP
        if ip link show can0 2>/dev/null | grep -q "state UP"; then
            echo -e "${BCYAN}${BOX_V}${NC}     ${GREEN}✓ Interface is UP${NC}"
            local bitrate
            bitrate=$(get_can_bitrate can0)
            echo -e "${BCYAN}${BOX_V}${NC}     ${GREEN}✓ Bitrate: ${bitrate} bps${NC}"
        else
            echo -e "${BCYAN}${BOX_V}${NC}     ${RED}✗ Interface is DOWN${NC}"
            echo -e "${BCYAN}${BOX_V}${NC}     ${YELLOW}  Fix: sudo ip link set can0 up type can bitrate 1000000${NC}"
            has_issues=1
        fi
    else
        echo -e "${BCYAN}${BOX_V}${NC}     ${RED}✗ Interface does not exist${NC}"
        echo -e "${BCYAN}${BOX_V}${NC}     ${YELLOW}  Check: Is your CAN adapter connected?${NC}"
        echo -e "${BCYAN}${BOX_V}${NC}     ${YELLOW}  Fix: Create /etc/network/interfaces.d/can0${NC}"
        has_issues=1
    fi
    
    echo -e "${BCYAN}${BOX_V}${NC}"
    
    # Check 2: CAN adapter
    echo -e "${BCYAN}${BOX_V}${NC}  ${BWHITE}2. CAN Adapter Detection:${NC}"
    local usb_can_devices
    usb_can_devices=$(lsusb 2>/dev/null | grep -iE "can|1d50:606f|gs_usb" || true)
    if [[ -n "$usb_can_devices" ]]; then
        echo -e "${BCYAN}${BOX_V}${NC}     ${GREEN}✓ USB CAN device found:${NC}"
        while IFS= read -r device; do
            echo -e "${BCYAN}${BOX_V}${NC}       $device"
        done <<< "$usb_can_devices"
    else
        echo -e "${BCYAN}${BOX_V}${NC}     ${YELLOW}? No obvious USB CAN adapter detected${NC}"
        echo -e "${BCYAN}${BOX_V}${NC}     ${YELLOW}  (May be using USB-CAN bridge mode on mainboard)${NC}"
    fi
    
    echo -e "${BCYAN}${BOX_V}${NC}"
    
    # Check 3: Klipper query script
    echo -e "${BCYAN}${BOX_V}${NC}  ${BWHITE}3. Klipper CAN Query Script:${NC}"
    if [[ -f "${HOME}/klipper/scripts/canbus_query.py" ]]; then
        echo -e "${BCYAN}${BOX_V}${NC}     ${GREEN}✓ canbus_query.py found${NC}"
    else
        echo -e "${BCYAN}${BOX_V}${NC}     ${RED}✗ canbus_query.py not found${NC}"
        echo -e "${BCYAN}${BOX_V}${NC}     ${YELLOW}  Check: Is Klipper installed?${NC}"
        has_issues=1
    fi
    
    echo -e "${BCYAN}${BOX_V}${NC}"
    
    # Check 4: Try to find CAN devices
    echo -e "${BCYAN}${BOX_V}${NC}  ${BWHITE}4. CAN Device Discovery:${NC}"
    if check_can_interface can0; then
        local uuids
        uuids=$(detect_can_mcus)
        if [[ -n "$uuids" ]]; then
            echo -e "${BCYAN}${BOX_V}${NC}     ${GREEN}✓ CAN devices found:${NC}"
            while IFS= read -r uuid; do
                echo -e "${BCYAN}${BOX_V}${NC}       ${BWHITE}${uuid}${NC}"
            done <<< "$uuids"
        else
            echo -e "${BCYAN}${BOX_V}${NC}     ${YELLOW}? No CAN devices responding${NC}"
            echo -e "${BCYAN}${BOX_V}${NC}     ${YELLOW}  Check:${NC}"
            echo -e "${BCYAN}${BOX_V}${NC}     ${YELLOW}  - Is the toolboard powered?${NC}"
            echo -e "${BCYAN}${BOX_V}${NC}     ${YELLOW}  - Is Klipper/Katapult flashed on it?${NC}"
            echo -e "${BCYAN}${BOX_V}${NC}     ${YELLOW}  - Are CAN H/L wires connected correctly?${NC}"
            echo -e "${BCYAN}${BOX_V}${NC}     ${YELLOW}  - Is there a 120Ω termination resistor?${NC}"
            has_issues=1
        fi
    else
        echo -e "${BCYAN}${BOX_V}${NC}     ${YELLOW}? Cannot query - can0 not ready${NC}"
        has_issues=1
    fi
    
    echo -e "${BCYAN}${BOX_V}${NC}"
    
    # Check 5: Klipper service
    echo -e "${BCYAN}${BOX_V}${NC}  ${BWHITE}5. Klipper Service:${NC}"
    if systemctl is-active --quiet klipper 2>/dev/null; then
        echo -e "${BCYAN}${BOX_V}${NC}     ${GREEN}✓ Klipper service is running${NC}"
        echo -e "${BCYAN}${BOX_V}${NC}     ${YELLOW}  Note: Stop Klipper to flash firmware over CAN${NC}"
    else
        echo -e "${BCYAN}${BOX_V}${NC}     ${YELLOW}? Klipper service is not running${NC}"
        echo -e "${BCYAN}${BOX_V}${NC}     ${YELLOW}  (OK for flashing, needed for operation)${NC}"
    fi
    
    print_separator
    
    if [[ $has_issues -eq 0 ]]; then
        echo -e "${BCYAN}${BOX_V}${NC}  ${GREEN}All checks passed!${NC}"
    else
        echo -e "${BCYAN}${BOX_V}${NC}  ${YELLOW}Some issues found. See suggestions above.${NC}"
        echo -e "${BCYAN}${BOX_V}${NC}"
        echo -e "${BCYAN}${BOX_V}${NC}  ${BWHITE}Helpful resources:${NC}"
        echo -e "${BCYAN}${BOX_V}${NC}  • https://canbus.esoterical.online/"
        echo -e "${BCYAN}${BOX_V}${NC}  • Voron Discord #can-and-usb_toolhead_boards"
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
        echo -e "${BCYAN}${BOX_V}${NC}  Scanning CAN bus for devices..."
        echo -e "${BCYAN}${BOX_V}${NC}"
        
        local -a uuids
        mapfile -t uuids < <(detect_can_mcus)
        
        if [[ ${#uuids[@]} -eq 0 ]]; then
            echo -e "${BCYAN}${BOX_V}${NC}  ${YELLOW}No CAN devices found.${NC}"
            echo -e "${BCYAN}${BOX_V}${NC}  Make sure:"
            echo -e "${BCYAN}${BOX_V}${NC}  - CAN interface is up (can0)"
            echo -e "${BCYAN}${BOX_V}${NC}  - Device is powered and connected"
            echo -e "${BCYAN}${BOX_V}${NC}  - Device has Klipper/Katapult firmware"
            print_footer
            wait_for_key
            return 1
        fi
        
        local num=1
        for uuid in "${uuids[@]}"; do
            echo -e "${BCYAN}${BOX_V}${NC}  ${BWHITE}${num})${NC} ${uuid}"
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
        echo -e "${BCYAN}${BOX_V}${NC}  Scanning USB for Klipper MCUs..."
        echo -e "${BCYAN}${BOX_V}${NC}"
        
        local -a devices
        mapfile -t devices < <(detect_usb_mcus)
        
        if [[ ${#devices[@]} -eq 0 ]]; then
            echo -e "${BCYAN}${BOX_V}${NC}  ${YELLOW}No Klipper USB devices found.${NC}"
            echo -e "${BCYAN}${BOX_V}${NC}  Make sure:"
            echo -e "${BCYAN}${BOX_V}${NC}  - MCU is connected via USB"
            echo -e "${BCYAN}${BOX_V}${NC}  - MCU has Klipper firmware flashed"
            print_footer
            wait_for_key
            return 1
        fi
        
        local num=1
        for device in "${devices[@]}"; do
            local desc=$(get_mcu_description "$device")
            local basename=$(basename "$device")
            echo -e "${BCYAN}${BOX_V}${NC}  ${BWHITE}${num})${NC} ${CYAN}${desc}${NC}"
            echo -e "${BCYAN}${BOX_V}${NC}      ${WHITE}${basename}${NC}"
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
        echo -e "${BCYAN}${BOX_V}${NC}"
        echo -e "${BCYAN}${BOX_V}${NC}  ${RED}Installation library not found!${NC}"
        echo -e "${BCYAN}${BOX_V}${NC}  Please ensure scripts/lib/klipper-install.sh exists."
        echo -e "${BCYAN}${BOX_V}${NC}"
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
        echo -e "${BCYAN}${BOX_V}${NC}"
        echo -e "${BCYAN}${BOX_V}${NC}  ${RED}Installation library not found!${NC}"
        echo -e "${BCYAN}${BOX_V}${NC}  Please ensure scripts/lib/klipper-install.sh exists."
        echo -e "${BCYAN}${BOX_V}${NC}"
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
        echo -e "${BCYAN}${BOX_V}${NC}"
        echo -e "${BCYAN}${BOX_V}${NC}  ${RED}Installation library not found!${NC}"
        echo -e "${BCYAN}${BOX_V}${NC}  Please ensure scripts/lib/klipper-install.sh exists."
        echo -e "${BCYAN}${BOX_V}${NC}"
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
        echo -e "${BCYAN}${BOX_V}${NC}"
        echo -e "${BCYAN}${BOX_V}${NC}  ${RED}Installation library not found!${NC}"
        echo -e "${BCYAN}${BOX_V}${NC}  Please ensure scripts/lib/klipper-install.sh exists."
        echo -e "${BCYAN}${BOX_V}${NC}"
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
        echo -e "${BCYAN}${BOX_V}${NC}"
        echo -e "${BCYAN}${BOX_V}${NC}  ${RED}Installation library not found!${NC}"
        echo -e "${BCYAN}${BOX_V}${NC}  Please ensure scripts/lib/klipper-install.sh exists."
        echo -e "${BCYAN}${BOX_V}${NC}"
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
        echo -e "${BCYAN}${BOX_V}${NC}"
        echo -e "${BCYAN}${BOX_V}${NC}  ${RED}Installation library not found!${NC}"
        echo -e "${BCYAN}${BOX_V}${NC}  Please ensure scripts/lib/klipper-install.sh exists."
        echo -e "${BCYAN}${BOX_V}${NC}"
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
        echo -e "${BCYAN}${BOX_V}${NC}"
        echo -e "${BCYAN}${BOX_V}${NC}  ${RED}Installation library not found!${NC}"
        echo -e "${BCYAN}${BOX_V}${NC}  Please ensure scripts/lib/klipper-install.sh exists."
        echo -e "${BCYAN}${BOX_V}${NC}"
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
    
    echo -e "${BCYAN}${BOX_V}${NC}  ${WHITE}Klipper Configuration Generator${NC}"
    echo -e "${BCYAN}${BOX_V}${NC}"
    
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
        
        echo -e "${BCYAN}${BOX_V}${NC}  ${BWHITE}CORE COMPONENTS${NC}"
        
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
        
        echo -e "${BCYAN}${BOX_V}${NC}"
        echo -e "${BCYAN}${BOX_V}${NC}  ${BWHITE}WEB INTERFACE${NC} ${WHITE}(choose one)${NC}"
        
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
        
        echo -e "${BCYAN}${BOX_V}${NC}"
        echo -e "${BCYAN}${BOX_V}${NC}  ${BWHITE}OPTIONAL${NC}"
        
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
    echo -e "${BCYAN}${BOX_V}${NC}  ${BWHITE}BOARDS${NC}"

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
        echo -e "${BCYAN}${BOX_V}${NC}  ${BWHITE}C)${NC} [ ] CAN Bus Setup: ${CYAN}${can_status}${NC}"
    fi

    # ─────────────────────────────────────────────────────────────────────────
    # MOTION
    # ─────────────────────────────────────────────────────────────────────────
    echo -e "${BCYAN}${BOX_V}${NC}"
    echo -e "${BCYAN}${BOX_V}${NC}  ${BWHITE}MOTION${NC}"

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
    echo -e "${BCYAN}${BOX_V}${NC}"
    echo -e "${BCYAN}${BOX_V}${NC}  ${BWHITE}COMPONENTS${NC}"

    # Hotend
    local hotend_info=""
    if [[ -n "${WIZARD_STATE[hotend_thermistor]}" ]]; then
        hotend_info="${WIZARD_STATE[hotend_thermistor]}"
    else
        hotend_info="not configured"
    fi
    print_menu_item "5" "$(get_step_status hotend)" "Hotend" "${hotend_info}"

    # Heated Bed
    local bed_info=""
    if [[ -n "${WIZARD_STATE[bed_size_x]}" ]]; then
        bed_info="${WIZARD_STATE[bed_size_x]}x${WIZARD_STATE[bed_size_y]}mm"
        [[ -n "${WIZARD_STATE[bed_thermistor]}" ]] && bed_info="${bed_info}, ${WIZARD_STATE[bed_thermistor]}"
    else
        bed_info="not configured"
    fi
    print_menu_item "6" "$(get_step_status bed)" "Heated Bed" "${bed_info}"

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
    print_menu_item "7" "$(get_step_status endstops)" "Endstops" "${endstop_info}"

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
    print_menu_item "8" "$fan_status" "Fans" "${fan_info}"

    # Lighting
    local light_info="${WIZARD_STATE[lighting_type]:-not configured}"
    local light_status=$([[ -n "${WIZARD_STATE[lighting_type]}" && "${WIZARD_STATE[lighting_type]}" != "none" ]] && echo "done" || echo "")
    print_menu_item "9" "$light_status" "Lighting" "${light_info}"

    # ─────────────────────────────────────────────────────────────────────────
    # EXTRAS
    # ─────────────────────────────────────────────────────────────────────────
    echo -e "${BCYAN}${BOX_V}${NC}"
    echo -e "${BCYAN}${BOX_V}${NC}  ${BWHITE}EXTRAS${NC}"
    print_menu_item "E" "$(get_step_status extras)" "Extras" ""
    print_menu_item "M" "$(get_step_status macros)" "Macros" ""

    print_separator
    print_action_item "T" "Stepper Calibration"
    print_action_item "F" "MCU Firmware Update"
    print_action_item "G" "Generate Configuration"
    print_action_item "S" "Save Progress"
    print_action_item "Q" "Quit"
    print_footer

    echo -en "${BYELLOW}Select option${NC}: "
    read -r choice

    case "$choice" in
        1) menu_board ;;
        2) menu_toolboard ;;
        3) menu_misc_mcus ;;
        4) menu_kinematics ;;
        5) menu_hotend ;;
        6) menu_bed ;;
        7) menu_endstops ;;
        8) menu_fans ;;
        9) menu_lighting ;;
        [eE]) menu_extras ;;
        [mM]) menu_macros ;;
        [cC]) menu_can_setup ;;
        [tT]) menu_stepper_calibration ;;
        [fF]) menu_mcu_firmware_update ;;
        [gG]) generate_config ;;
        [sS]) save_state; echo -e "${GREEN}Progress saved!${NC}"; wait_for_key ;;
        [qQ]) exit_wizard ;;
        *) ;;
    esac
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
        echo -e "${BCYAN}${BOX_V}${NC}  ${RED}Please select a board first!${NC}"
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
        echo -e "${BCYAN}${BOX_V}${NC}  ${BWHITE}Current Configuration:${NC}"
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
            echo -e "${BCYAN}${BOX_V}${NC}  ${BWHITE}4)${NC} ${YELLOW}[ ]${NC} Motor Port Assignment: ${YELLOW}select board first${NC}"
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
    
    echo -e "${BCYAN}${BOX_V}${NC}  ${BWHITE}How many Z stepper motors?${NC}"
    echo -e "${BCYAN}${BOX_V}${NC}"
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
    
    echo -e "${BCYAN}${BOX_V}${NC}  ${BWHITE}Where are your X/Y endstops located?${NC}"
    echo -e "${BCYAN}${BOX_V}${NC}  (This determines homing direction)"
    echo -e "${BCYAN}${BOX_V}${NC}"
    
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
    
    echo -e "${BCYAN}${BOX_V}${NC}  ${BWHITE}Enter the physical endstop trigger positions:${NC}"
    echo -e "${BCYAN}${BOX_V}${NC}  (Where the nozzle is when each endstop triggers)"
    echo -e "${BCYAN}${BOX_V}${NC}"
    
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
    
    echo -e "${BCYAN}${BOX_V}${NC}  ${YELLOW}X axis (homing to ${WIZARD_STATE[home_x]:-max}):${NC}"
    echo -en "  " >&2
    WIZARD_STATE[position_endstop_x]=$(prompt_input "X position_endstop (mm)" "${WIZARD_STATE[position_endstop_x]:-$default_x}")
    echo -en "  " >&2
    WIZARD_STATE[position_min_x]=$(prompt_input "X position_min (mm, can be negative)" "${WIZARD_STATE[position_min_x]:-$default_min_x}")
    
    echo ""
    echo -e "${BCYAN}${BOX_V}${NC}  ${YELLOW}Y axis (homing to ${WIZARD_STATE[home_y]:-max}):${NC}"
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
    
    echo -e "${BCYAN}${BOX_V}${NC}  ${BWHITE}Enter the Z endstop trigger position:${NC}"
    echo -e "${BCYAN}${BOX_V}${NC}  (Where the nozzle is when the Z endstop triggers)"
    echo -e "${BCYAN}${BOX_V}${NC}"
    echo -e "${BCYAN}${BOX_V}${NC}  ${YELLOW}Typical values:${NC}"
    echo -e "${BCYAN}${BOX_V}${NC}  • 0 for bed-mounted endstop at bed level"
    echo -e "${BCYAN}${BOX_V}${NC}  • Positive value if endstop triggers above bed"
    echo -e "${BCYAN}${BOX_V}${NC}"
    
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
            echo -e "${BCYAN}${BOX_V}${NC}  ${RED}Please select a board first!${NC}"
            print_footer
            wait_for_key
            return
        fi
        
        local axes
        axes=$(get_required_axes)
        
        echo -e "${BCYAN}${BOX_V}${NC}  ${BWHITE}Configure driver for each axis:${NC}"
        echo -e "${BCYAN}${BOX_V}${NC}  ${WHITE}(Based on: ${WIZARD_STATE[kinematics]:-not set})${NC}"
        echo -e "${BCYAN}${BOX_V}${NC}"
        
        local num=1
        for axis in $axes; do
            local driver="${WIZARD_STATE[driver_${axis}]}"
            local status=$([[ -n "$driver" ]] && echo "done" || echo "")
            print_menu_item "$num" "$status" "${axis} Axis" "$driver"
            num=$((num + 1))
        done
        
        print_separator
        print_action_item "A" "Set ALL axes to same driver"
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

        echo -e "${BCYAN}${BOX_V}${NC}  ${BWHITE}Configure each axis individually:${NC}"
        echo -e "${BCYAN}${BOX_V}${NC}"
        echo -e "${BCYAN}${BOX_V}${NC}  Each axis can have different step angle, microsteps,"
        echo -e "${BCYAN}${BOX_V}${NC}  and rotation_distance settings."
        echo -e "${BCYAN}${BOX_V}${NC}"

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
        echo -e "${BCYAN}${BOX_V}${NC}  ${BWHITE}Quick Setup:${NC}"
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

        echo -e "${BCYAN}${BOX_V}${NC}  ${BWHITE}Current settings:${NC}"
        echo -e "${BCYAN}${BOX_V}${NC}  Step angle: ${CYAN}${step}°${NC} ($([ "$step" == "1.8" ] && echo "200" || echo "400") steps/rev)"
        echo -e "${BCYAN}${BOX_V}${NC}  Microsteps: ${CYAN}${micro}${NC}"
        echo -e "${BCYAN}${BOX_V}${NC}  Rotation distance: ${CYAN}${rot:-not set}${NC}${rot:+mm}"
        echo -e "${BCYAN}${BOX_V}${NC}"

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

    echo -e "${BCYAN}${BOX_V}${NC}  ${BWHITE}Select stepper motor step angle:${NC}"
    echo -e "${BCYAN}${BOX_V}${NC}"

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

    echo -e "${BCYAN}${BOX_V}${NC}  ${BWHITE}Select microstep resolution:${NC}"
    echo -e "${BCYAN}${BOX_V}${NC}"

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

    echo -e "${BCYAN}${BOX_V}${NC}  ${BWHITE}Configure belt drive rotation distance:${NC}"
    echo -e "${BCYAN}${BOX_V}${NC}"
    echo -e "${BCYAN}${BOX_V}${NC}  rotation_distance = pulley_teeth × belt_pitch"
    echo -e "${BCYAN}${BOX_V}${NC}"

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

    echo -e "${BCYAN}${BOX_V}${NC}  ${BWHITE}Configure lead screw rotation distance:${NC}"
    echo -e "${BCYAN}${BOX_V}${NC}"
    echo -e "${BCYAN}${BOX_V}${NC}  rotation_distance = lead (pitch × starts)"
    echo -e "${BCYAN}${BOX_V}${NC}  Example: 2mm pitch × 4 starts = 8mm lead"
    echo -e "${BCYAN}${BOX_V}${NC}"

    print_menu_item "1" "" "8mm lead" "T8×8 4-start (most common, fast)"
    print_menu_item "2" "" "4mm lead" "T8×4 2-start"
    print_menu_item "3" "" "2mm lead" "T8×2 single-start (slow, precise)"
    print_menu_item "4" "" "1mm lead" "Fine pitch"
    print_separator
    echo -e "${BCYAN}${BOX_V}${NC}  ${BWHITE}Or belt-driven Z:${NC}"
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

    echo -e "${BCYAN}${BOX_V}${NC}  ${BWHITE}Configure extruder rotation distance:${NC}"
    echo -e "${BCYAN}${BOX_V}${NC}"
    echo -e "${BCYAN}${BOX_V}${NC}  ${YELLOW}This is a starting value - calibrate after setup!${NC}"
    echo -e "${BCYAN}${BOX_V}${NC}"

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

    echo -e "${BCYAN}${BOX_V}${NC}  ${BWHITE}Apply same step angle to X, Y, Z:${NC}"
    echo -e "${BCYAN}${BOX_V}${NC}"

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

    echo -e "${BCYAN}${BOX_V}${NC}  ${BWHITE}Apply same microsteps to X, Y, Z:${NC}"
    echo -e "${BCYAN}${BOX_V}${NC}"

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
    
    echo -e "${BCYAN}${BOX_V}${NC}  ${BWHITE}Select Extruder Type:${NC}"
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
    
    echo -e "${BCYAN}${BOX_V}${NC}  ${BWHITE}Common NTC Thermistors:${NC}"
    print_menu_item "1" "" "Generic 3950 (NTC 100K) - Most common"
    print_menu_item "2" "" "ATC Semitec 104GT-2 (E3D/Slice hotends)"
    print_menu_item "3" "" "ATC Semitec 104NT-4-R025H42G"
    print_menu_item "4" "" "Honeywell 100K 135-104LAG-J01"
    print_menu_item "5" "" "NTC 100K MGB18-104F39050L32"
    echo -e "${BCYAN}${BOX_V}${NC}"
    echo -e "${BCYAN}${BOX_V}${NC}  ${BWHITE}High-Temp / RTD:${NC}"
    print_menu_item "6" "" "Slice Engineering 450C (high temp)"
    print_menu_item "7" "" "PT1000 (direct, no amplifier)"
    print_menu_item "8" "" "PT1000 with MAX31865 amplifier"
    print_menu_item "9" "" "PT100 with MAX31865 amplifier"
    echo -e "${BCYAN}${BOX_V}${NC}"
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
            echo -e "${BCYAN}${BOX_V}${NC}"
            echo -e "${BCYAN}${BOX_V}${NC}  Enter exact Klipper sensor_type value:"
            echo -e "${BCYAN}${BOX_V}${NC}  (See: https://www.klipper3d.org/Config_Reference.html#thermistor)"
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
    
    echo -e "${BCYAN}${BOX_V}${NC}  ${BWHITE}Select the pullup resistor value for your board:${NC}"
    echo -e "${BCYAN}${BOX_V}${NC}  (Check your board documentation if unsure)"
    echo -e "${BCYAN}${BOX_V}${NC}"
    
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
# HOTEND CONFIGURATION (thermistor, heater, ports)
# ═══════════════════════════════════════════════════════════════════════════════

menu_hotend() {
    while true; do
        clear_screen
        print_header "Hotend Configuration"

        echo -e "${BCYAN}${BOX_V}${NC}  ${BWHITE}Hotend Settings:${NC}"
        echo -e "${BCYAN}${BOX_V}${NC}"

        # 1. Extruder type (direct drive / bowden)
        local ext_status=$([[ -n "${WIZARD_STATE[extruder_type]}" ]] && echo "done" || echo "")
        print_menu_item "1" "$ext_status" "Extruder Type" "${WIZARD_STATE[extruder_type]:-not set}"

        # 2. Thermistor type
        local therm_status=$([[ -n "${WIZARD_STATE[hotend_thermistor]}" ]] && echo "done" || echo "")
        local therm_info="${WIZARD_STATE[hotend_thermistor]:-not set}"
        if [[ -n "${WIZARD_STATE[hotend_pullup_resistor]}" ]]; then
            therm_info="${therm_info} (pullup: ${WIZARD_STATE[hotend_pullup_resistor]}Ω)"
        fi
        print_menu_item "2" "$therm_status" "Thermistor Type" "${therm_info}"

        # 3. Port assignment (heater + thermistor)
        echo -e "${BCYAN}${BOX_V}${NC}"
        echo -e "${BCYAN}${BOX_V}${NC}  ${BWHITE}Port Assignment:${NC}"

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
            print_menu_item "3" "$heater_status" "Heater Port" "$heater_info"

            # Show thermistor port - check both mainboard and toolboard assignments
            local therm_status=""
            local therm_info="not assigned"
            if [[ -n "${HARDWARE_STATE[toolboard_thermistor_extruder]}" ]]; then
                therm_status="done"
                therm_info="toolboard:${HARDWARE_STATE[toolboard_thermistor_extruder]}"
            elif [[ -n "${HARDWARE_STATE[thermistor_extruder]}" ]]; then
                therm_status="done"
                therm_info="${HARDWARE_STATE[thermistor_extruder]}"
            fi
            print_menu_item "4" "$therm_status" "Thermistor Port" "$therm_info"
        else
            echo -e "${BCYAN}${BOX_V}${NC}  ${YELLOW}Select a main board first to assign ports${NC}"
        fi

        print_separator
        print_action_item "B" "Back to Main Menu"
        print_footer

        echo -en "${BYELLOW}Select option${NC}: "
        read -r choice

        case "$choice" in
            1) menu_extruder_type ;;
            2) menu_hotend_thermistor ;;
            3)
                if [[ -n "${WIZARD_STATE[board]}" ]]; then
                    menu_hotend_heater_port
                fi
                ;;
            4)
                if [[ -n "${WIZARD_STATE[board]}" ]]; then
                    menu_hotend_thermistor_port
                fi
                ;;
            [bB]) return ;;
            *) ;;
        esac
    done
}

menu_extruder_type() {
    clear_screen
    print_header "Extruder Type"

    echo -e "${BCYAN}${BOX_V}${NC}  ${BWHITE}Select Extruder Type:${NC}"
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
        *) ;;
    esac
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

        echo -e "${BCYAN}${BOX_V}${NC}  ${BWHITE}Bed Settings:${NC}"
        echo -e "${BCYAN}${BOX_V}${NC}"

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
        echo -e "${BCYAN}${BOX_V}${NC}"
        echo -e "${BCYAN}${BOX_V}${NC}  ${BWHITE}Port Assignment:${NC}"

        if [[ -n "${WIZARD_STATE[board]}" ]]; then
            local heater_status=$([[ -n "${HARDWARE_STATE[heater_bed]}" ]] && echo "done" || echo "")
            print_menu_item "3" "$heater_status" "Heater Port" "${HARDWARE_STATE[heater_bed]:-not assigned}"

            local therm_port_status=$([[ -n "${HARDWARE_STATE[thermistor_bed]}" ]] && echo "done" || echo "")
            print_menu_item "4" "$therm_port_status" "Thermistor Port" "${HARDWARE_STATE[thermistor_bed]:-not assigned}"
        else
            echo -e "${BCYAN}${BOX_V}${NC}  ${YELLOW}Select a main board first to assign ports${NC}"
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

    echo -e "${BCYAN}${BOX_V}${NC}  ${BWHITE}Enter bed dimensions:${NC}"
    echo -e "${BCYAN}${BOX_V}${NC}"

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

    echo -e "${BCYAN}${BOX_V}${NC}  ${BWHITE}Select Bed Thermistor:${NC}"
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

    echo -e "${BCYAN}${BOX_V}${NC}  ${BWHITE}Select the pullup resistor value for bed thermistor:${NC}"
    echo -e "${BCYAN}${BOX_V}${NC}  (Check your board documentation if unsure)"
    echo -e "${BCYAN}${BOX_V}${NC}"

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

        echo -e "${BCYAN}${BOX_V}${NC}  ${BWHITE}X/Y Endstops:${NC}"

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

        echo -e "${BCYAN}${BOX_V}${NC}"
        echo -e "${BCYAN}${BOX_V}${NC}  ${BWHITE}Z Endstop / Probe:${NC}"

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
            # Show MCU info for probes with their own MCU
            if [[ "$probe_type" =~ ^(beacon|cartographer|btt-eddy)$ ]]; then
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

        echo -e "${BCYAN}${BOX_V}${NC}  ${BWHITE}X Axis Endstop:${NC}"
        echo -e "${BCYAN}${BOX_V}${NC}"

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
                echo -e "${BCYAN}${BOX_V}${NC}  ${YELLOW}3) Port Assignment: select board first${NC}"
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

    echo -e "${BCYAN}${BOX_V}${NC}  ${BWHITE}Where is the X endstop located?${NC}"
    echo -e "${BCYAN}${BOX_V}${NC}"

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

    echo -e "${BCYAN}${BOX_V}${NC}  ${BWHITE}Select X endstop type:${NC}"
    echo -e "${BCYAN}${BOX_V}${NC}"

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

        echo -e "${BCYAN}${BOX_V}${NC}  ${BWHITE}Y Axis Endstop:${NC}"
        echo -e "${BCYAN}${BOX_V}${NC}"

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
                echo -e "${BCYAN}${BOX_V}${NC}  ${YELLOW}3) Port Assignment: select board first${NC}"
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

    echo -e "${BCYAN}${BOX_V}${NC}  ${BWHITE}Where is the Y endstop located?${NC}"
    echo -e "${BCYAN}${BOX_V}${NC}"

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

    echo -e "${BCYAN}${BOX_V}${NC}  ${BWHITE}Select Y endstop type:${NC}"
    echo -e "${BCYAN}${BOX_V}${NC}"

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

        echo -e "${BCYAN}${BOX_V}${NC}  ${BWHITE}Current: ${current_probe:-not set}${NC}"
        echo -e "${BCYAN}${BOX_V}${NC}"
        echo -e "${BCYAN}${BOX_V}${NC}  ${BWHITE}Pin-based Probes:${NC}"
        local bltouch_sel=$([[ "$current_probe" == "bltouch" ]] && echo "done" || echo "")
        local klicky_sel=$([[ "$current_probe" == "klicky" ]] && echo "done" || echo "")
        local inductive_sel=$([[ "$current_probe" == "inductive" ]] && echo "done" || echo "")
        print_menu_item "1" "$bltouch_sel" "BLTouch / 3DTouch"
        print_menu_item "2" "$klicky_sel" "Klicky Probe"
        print_menu_item "3" "$inductive_sel" "Inductive Probe (PINDA/SuperPINDA)"

        echo -e "${BCYAN}${BOX_V}${NC}"
        echo -e "${BCYAN}${BOX_V}${NC}  ${BWHITE}MCU-based Probes (USB/CAN):${NC}"
        local beacon_sel=$([[ "$current_probe" == "beacon" ]] && echo "done" || echo "")
        local carto_sel=$([[ "$current_probe" == "cartographer" ]] && echo "done" || echo "")
        local eddy_sel=$([[ "$current_probe" == "btt-eddy" ]] && echo "done" || echo "")
        print_menu_item "4" "$beacon_sel" "Beacon (Eddy Current)" "${beacon_status}"
        print_menu_item "5" "$carto_sel" "Cartographer" "${carto_status}"
        print_menu_item "6" "$eddy_sel" "BTT Eddy" "${eddy_status}"

        echo -e "${BCYAN}${BOX_V}${NC}"
        echo -e "${BCYAN}${BOX_V}${NC}  ${BWHITE}Physical Endstop:${NC}"
        local endstop_sel=$([[ "$current_probe" == "endstop" ]] && echo "done" || echo "")
        print_menu_item "7" "$endstop_sel" "Physical Z Endstop (no probe)"

        # Show port/MCU assignment option if probe is selected
        if [[ -n "${WIZARD_STATE[probe_type]}" && "${WIZARD_STATE[probe_type]}" != "endstop" ]]; then
            echo -e "${BCYAN}${BOX_V}${NC}"
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
            else
                local pin_info="${HARDWARE_STATE[probe_pin]:-not assigned}"
                print_menu_item "P" "" "Configure Probe Pin" "${pin_info}"
            fi
        elif [[ "${WIZARD_STATE[probe_type]}" == "endstop" ]]; then
            echo -e "${BCYAN}${BOX_V}${NC}"
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
    done
}

menu_endstop_z_position() {
    clear_screen
    print_header "Z Endstop Position"

    echo -e "${BCYAN}${BOX_V}${NC}  ${BWHITE}Where is the Z endstop located?${NC}"
    echo -e "${BCYAN}${BOX_V}${NC}"

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
    echo -e "${BCYAN}${BOX_V}${NC}  ${BWHITE}Configure ${probe_type} connection:${NC}"
    echo -e "${BCYAN}${BOX_V}${NC}"

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

    echo -e "${BCYAN}${BOX_V}${NC}  ${BWHITE}Scanning for USB devices...${NC}"
    echo -e "${BCYAN}${BOX_V}${NC}"

    # Scan for USB devices
    local devices=()
    local i=1
    while IFS= read -r device; do
        if [[ -n "$device" ]]; then
            devices+=("$device")
            local short_name=$(basename "$device")
            echo -e "${BCYAN}${BOX_V}${NC}  ${BWHITE}${i})${NC} ${short_name}"
            i=$((i + 1))
        fi
    done < <(ls /dev/serial/by-id/ 2>/dev/null | grep -iE "beacon|cartographer|eddy|probe" || true)

    if [[ ${#devices[@]} -eq 0 ]]; then
        echo -e "${BCYAN}${BOX_V}${NC}  ${YELLOW}No probe USB devices found.${NC}"
        echo -e "${BCYAN}${BOX_V}${NC}  ${WHITE}Make sure your probe is connected via USB.${NC}"
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
}

menu_probe_can() {
    clear_screen
    print_header "Probe CAN UUID"

    echo -e "${BCYAN}${BOX_V}${NC}  ${BWHITE}Scanning CAN bus for devices...${NC}"
    echo -e "${BCYAN}${BOX_V}${NC}"

    # Check if CAN interface is up
    if ! check_can_interface can0 2>/dev/null; then
        echo -e "${BCYAN}${BOX_V}${NC}  ${RED}CAN interface not available.${NC}"
        echo -e "${BCYAN}${BOX_V}${NC}  ${WHITE}Please configure CAN bus first.${NC}"
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
            echo -e "${BCYAN}${BOX_V}${NC}  ${BWHITE}${i})${NC} ${uuid}"
            i=$((i + 1))
        fi
    done < <(python3 ~/klipper/scripts/canbus_query.py can0 2>/dev/null || true)

    if [[ ${#uuids[@]} -eq 0 ]]; then
        echo -e "${BCYAN}${BOX_V}${NC}  ${YELLOW}No CAN devices found.${NC}"
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
}

# Legacy probe menu - redirects to new endstops menu
menu_probe() {
    while true; do
        clear_screen
        print_header "Probe Configuration"

        echo -e "${BCYAN}${BOX_V}${NC}  ${BWHITE}Configure your Z probe:${NC}"
        echo -e "${BCYAN}${BOX_V}${NC}"

        # Current probe type
        local probe_type="${WIZARD_STATE[probe_type]:-not selected}"
        local type_status=$([[ -n "${WIZARD_STATE[probe_type]}" ]] && echo "done" || echo "")
        print_menu_item "1" "$type_status" "Probe Type" "$probe_type"

        # Show module installation status for probes that need it
        local current_probe="${WIZARD_STATE[probe_type]}"
        if [[ "$current_probe" =~ ^(beacon|cartographer|btt-eddy)$ ]]; then
            echo -e "${BCYAN}${BOX_V}${NC}"
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
            echo -e "${BCYAN}${BOX_V}${NC}"
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
            echo -e "${BCYAN}${BOX_V}${NC}"
            local endstop_pos="${WIZARD_STATE[z_endstop_position]:-not set}"
            local endstop_status=$([[ -n "${WIZARD_STATE[z_endstop_position]}" ]] && echo "done" || echo "")
            print_menu_item "3" "$endstop_status" "Z Endstop Position" "$endstop_pos"
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

    echo -e "${BCYAN}${BOX_V}${NC}  ${BWHITE}Standard Probes:${NC}"
    print_menu_item "1" "$bltouch_sel" "BLTouch / 3DTouch"
    print_menu_item "2" "$klicky_sel" "Klicky Probe"
    print_menu_item "3" "$inductive_sel" "Inductive Probe (PINDA/SuperPINDA)"
    print_menu_item "4" "$endstop_sel" "Physical Z Endstop (no probe)"
    echo -e "${BCYAN}${BOX_V}${NC}"
    echo -e "${BCYAN}${BOX_V}${NC}  ${BWHITE}Eddy Current Probes (require module):${NC}"
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

# ═══════════════════════════════════════════════════════════════════════════════
# FAN CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

menu_fans() {
    while true; do
        clear_screen
        print_header "Fan Configuration"
        
        echo -e "${BCYAN}${BOX_V}${NC}  ${BWHITE}Configure your printer's fans:${NC}"
        echo -e "${BCYAN}${BOX_V}${NC}"
        
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
            if [[ -n "${HARDWARE_STATE[${fan_key}_2]}" ]]; then
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
        echo -e "${BCYAN}${BOX_V}${NC}  ${BWHITE}Essential Fans:${NC}"
        local pc_status=$(get_fan_status "fan_part_cooling")
        local pc_info=$(get_fan_port_info "fan_part_cooling")
        echo -e "${BCYAN}${BOX_V}${NC}  ${GREEN}1)${NC} ${pc_status} Part Cooling Fan [fan] - ${CYAN}${pc_info}${NC}"

        local he_status=$(get_fan_status "fan_hotend")
        local he_info=$(get_fan_port_info "fan_hotend")
        echo -e "${BCYAN}${BOX_V}${NC}  ${GREEN}2)${NC} ${he_status} Hotend Fan [heater_fan] - ${CYAN}${he_info}${NC}"

        local cf_status=$(get_fan_status "fan_controller")
        local cf_info=$(get_fan_port_info "fan_controller")
        echo -e "${BCYAN}${BOX_V}${NC}  ${GREEN}3)${NC} ${cf_status} Controller Fan [controller_fan] - ${CYAN}${cf_info}${NC}"

        echo -e "${BCYAN}${BOX_V}${NC}"
        echo -e "${BCYAN}${BOX_V}${NC}  ${BWHITE}Optional Fans:${NC}"

        local ex_status=$(get_fan_status "fan_exhaust")
        local ex_info=$(get_fan_port_info "fan_exhaust")
        echo -e "${BCYAN}${BOX_V}${NC}  ${GREEN}4)${NC} ${ex_status} Exhaust Fan [fan_generic] - ${CYAN}${ex_info}${NC}"

        local ch_status=$(get_fan_status "fan_chamber")
        local ch_info=$(get_fan_port_info "fan_chamber")
        if [[ "${WIZARD_STATE[fan_chamber_type]}" == "temperature" ]]; then
            ch_info="${ch_info} (temp-controlled)"
        fi
        echo -e "${BCYAN}${BOX_V}${NC}  ${GREEN}5)${NC} ${ch_status} Chamber Fan [fan_generic/temperature_fan] - ${CYAN}${ch_info}${NC}"

        local rs_status=$(get_fan_status "fan_rscs")
        local rs_info=$(get_fan_port_info "fan_rscs")
        echo -e "${BCYAN}${BOX_V}${NC}  ${GREEN}6)${NC} ${rs_status} RSCS/Filter Fan [fan_generic] - ${CYAN}${rs_info}${NC}"

        local rd_status=$(get_fan_status "fan_radiator")
        local rd_info=$(get_fan_port_info "fan_radiator")
        echo -e "${BCYAN}${BOX_V}${NC}  ${GREEN}7)${NC} ${rd_status} Radiator Fan [heater_fan] - ${CYAN}${rd_info}${NC}"
        
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

        echo -e "${BCYAN}${BOX_V}${NC}  ${BWHITE}Part cooling fan controlled by M106/M107${NC}"
        echo -e "${BCYAN}${BOX_V}${NC}  This is the main print cooling fan."
        echo -e "${BCYAN}${BOX_V}${NC}"

        # Determine current port assignment (toolboard or mainboard)
        local primary_port=""
        local secondary_port=""
        if [[ -n "${HARDWARE_STATE[toolboard_fan_part_cooling]}" ]]; then
            primary_port="toolboard:${HARDWARE_STATE[toolboard_fan_part_cooling]}"
        elif [[ -n "${HARDWARE_STATE[fan_part_cooling]}" ]]; then
            primary_port="${HARDWARE_STATE[fan_part_cooling]}"
        fi
        [[ -n "${HARDWARE_STATE[fan_part_cooling_2]}" ]] && secondary_port="${HARDWARE_STATE[fan_part_cooling_2]}"

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
        print_header "Hotend Fan [heater_fan]"

        echo -e "${BCYAN}${BOX_V}${NC}  ${BWHITE}Hotend cooling fan that runs when extruder is hot${NC}"
        echo -e "${BCYAN}${BOX_V}${NC}  Automatically turns on above heater_temp threshold."
        echo -e "${BCYAN}${BOX_V}${NC}"

        # Determine current port assignment (toolboard or mainboard)
        local primary_port=""
        local secondary_port=""
        if [[ -n "${HARDWARE_STATE[toolboard_fan_hotend]}" ]]; then
            primary_port="toolboard:${HARDWARE_STATE[toolboard_fan_hotend]}"
        elif [[ -n "${HARDWARE_STATE[fan_hotend]}" ]]; then
            primary_port="${HARDWARE_STATE[fan_hotend]}"
        fi
        [[ -n "${HARDWARE_STATE[fan_hotend_2]}" ]] && secondary_port="${HARDWARE_STATE[fan_hotend_2]}"

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
            [cC])
                save_state
                python3 "${SCRIPT_DIR}/setup-hardware.py" --clear-port "fan_hotend"
                python3 "${SCRIPT_DIR}/setup-hardware.py" --clear-port "fan_hotend_2"
                load_hardware_state
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
        print_header "Controller Fan [controller_fan]"

        echo -e "${BCYAN}${BOX_V}${NC}  ${BWHITE}Electronics cooling fan${NC}"
        echo -e "${BCYAN}${BOX_V}${NC}  Runs when steppers or heaters are active."
        echo -e "${BCYAN}${BOX_V}${NC}"

        # Determine current port assignment
        local primary_port="${HARDWARE_STATE[fan_controller]}"
        local secondary_port="${HARDWARE_STATE[fan_controller_2]}"

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
            [cC])
                save_state
                python3 "${SCRIPT_DIR}/setup-hardware.py" --clear-port "fan_controller"
                python3 "${SCRIPT_DIR}/setup-hardware.py" --clear-port "fan_controller_2"
                load_hardware_state
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
        print_header "Exhaust Fan [fan_generic]"

        echo -e "${BCYAN}${BOX_V}${NC}  ${BWHITE}Enclosure exhaust fan${NC}"
        echo -e "${BCYAN}${BOX_V}${NC}  Manually controlled via SET_FAN_SPEED FAN=exhaust_fan SPEED=x"
        echo -e "${BCYAN}${BOX_V}${NC}"

        # Determine current port assignment
        local primary_port="${HARDWARE_STATE[fan_exhaust]}"
        local secondary_port="${HARDWARE_STATE[fan_exhaust_2]}"

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
            [cC])
                save_state
                python3 "${SCRIPT_DIR}/setup-hardware.py" --clear-port "fan_exhaust"
                python3 "${SCRIPT_DIR}/setup-hardware.py" --clear-port "fan_exhaust_2"
                load_hardware_state
                echo -e "${GREEN}✓${NC} Exhaust fan cleared"
                sleep 1
                ;;
            [bB]) return ;;
        esac
    done
}

menu_fan_chamber() {
    while true; do
        clear_screen
        print_header "Chamber Fan"

        echo -e "${BCYAN}${BOX_V}${NC}  ${BWHITE}Chamber circulation/heating fan${NC}"
        echo -e "${BCYAN}${BOX_V}${NC}  Can be manual or temperature-controlled."
        echo -e "${BCYAN}${BOX_V}${NC}"

        # Determine current port assignment
        local primary_port="${HARDWARE_STATE[fan_chamber]}"
        local secondary_port="${HARDWARE_STATE[fan_chamber_2]}"

        # Display current status
        local primary_status=$([[ -n "$primary_port" ]] && echo "done" || echo "")
        local primary_info="${primary_port:-not assigned}"
        print_menu_item "1" "$primary_status" "Fan Port" "$primary_info"

        local secondary_status=$([[ -n "$secondary_port" ]] && echo "done" || echo "")
        local secondary_info="${secondary_port:-not set}"
        print_menu_item "2" "$secondary_status" "Multi-pin (2nd fan)" "$secondary_info"

        echo -e "${BCYAN}${BOX_V}${NC}"

        # Fan type/mode selection (only relevant if port is assigned)
        local type_status=$([[ -n "${WIZARD_STATE[fan_chamber_type]}" ]] && echo "done" || echo "")
        local type_info="${WIZARD_STATE[fan_chamber_type]:-manual}"
        [[ "$type_info" == "temperature" ]] && type_info="temp-controlled (${WIZARD_STATE[fan_chamber_target_temp]:-45}°C)"
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
                menu_fan_chamber_mode
                ;;
            [cC])
                save_state
                python3 "${SCRIPT_DIR}/setup-hardware.py" --clear-port "fan_chamber"
                python3 "${SCRIPT_DIR}/setup-hardware.py" --clear-port "fan_chamber_2"
                WIZARD_STATE[fan_chamber_type]=""
                WIZARD_STATE[fan_chamber_target_temp]=""
                WIZARD_STATE[fan_chamber_sensor_type]=""
                load_hardware_state
                echo -e "${GREEN}✓${NC} Chamber fan cleared"
                sleep 1
                ;;
            [bB]) return ;;
        esac
    done
}

menu_fan_chamber_mode() {
    clear_screen
    print_header "Chamber Fan Control Mode"

    echo -e "${BCYAN}${BOX_V}${NC}  ${BWHITE}Select control mode:${NC}"
    echo -e "${BCYAN}${BOX_V}${NC}"
    print_menu_item "1" "" "Manual [fan_generic]" "SET_FAN_SPEED control"
    print_menu_item "2" "" "Temperature [temperature_fan]" "Auto control to target temp"
    print_separator
    print_action_item "B" "Back"
    print_footer

    echo -en "${BYELLOW}Select mode${NC}: "
    read -r choice

    case "$choice" in
        1)
            WIZARD_STATE[fan_chamber_type]="manual"
            WIZARD_STATE[fan_chamber_target_temp]=""
            WIZARD_STATE[fan_chamber_sensor_type]=""
            echo -e "${GREEN}✓${NC} Set to manual control"
            sleep 1
            ;;
        2)
            WIZARD_STATE[fan_chamber_type]="temperature"
            menu_fan_chamber_temp_settings
            ;;
        [bB]) return ;;
    esac
}

menu_fan_chamber_temp_settings() {
    clear_screen
    print_header "Chamber Temperature Fan Settings"
    
    echo -e "${BCYAN}${BOX_V}${NC}  ${BWHITE}Configure temperature-controlled chamber fan${NC}"
    echo -e "${BCYAN}${BOX_V}${NC}"
    
    # Sensor type
    echo -e "${BCYAN}${BOX_V}${NC}  ${BWHITE}Chamber Temperature Sensor:${NC}"
    print_menu_item "1" "" "Generic 3950 (NTC 100K)"
    print_menu_item "2" "" "NTC 100K MGB18-104F39050L32"
    print_menu_item "3" "" "ATC Semitec 104GT-2"
    print_footer
    
    echo -en "${BYELLOW}Select sensor type${NC}: "
    read -r choice
    
    case "$choice" in
        1) WIZARD_STATE[fan_chamber_sensor_type]="Generic 3950" ;;
        2) WIZARD_STATE[fan_chamber_sensor_type]="NTC 100K MGB18-104F39050L32" ;;
        3) WIZARD_STATE[fan_chamber_sensor_type]="ATC Semitec 104GT-2" ;;
        *) WIZARD_STATE[fan_chamber_sensor_type]="Generic 3950" ;;
    esac
    
    # Target temperature
    echo ""
    echo -en "  Enter target chamber temperature (°C) [45]: "
    read -r target_temp
    WIZARD_STATE[fan_chamber_target_temp]="${target_temp:-45}"
    
    echo -e "${GREEN}✓${NC} Temperature fan configured: ${WIZARD_STATE[fan_chamber_sensor_type]} @ ${WIZARD_STATE[fan_chamber_target_temp]}°C"
    sleep 1
}

menu_fan_rscs() {
    while true; do
        clear_screen
        print_header "RSCS/Filter Fan [fan_generic]"

        echo -e "${BCYAN}${BOX_V}${NC}  ${BWHITE}Recirculating active carbon/HEPA filter fan${NC}"
        echo -e "${BCYAN}${BOX_V}${NC}  Controlled via SET_FAN_SPEED FAN=rscs_fan SPEED=x"
        echo -e "${BCYAN}${BOX_V}${NC}"

        # Determine current port assignment
        local primary_port="${HARDWARE_STATE[fan_rscs]}"
        local secondary_port="${HARDWARE_STATE[fan_rscs_2]}"

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
            [cC])
                save_state
                python3 "${SCRIPT_DIR}/setup-hardware.py" --clear-port "fan_rscs"
                python3 "${SCRIPT_DIR}/setup-hardware.py" --clear-port "fan_rscs_2"
                load_hardware_state
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
        print_header "Radiator Fan [heater_fan]"

        echo -e "${BCYAN}${BOX_V}${NC}  ${BWHITE}Water cooling radiator fan(s)${NC}"
        echo -e "${BCYAN}${BOX_V}${NC}  Runs when extruder is hot (like hotend fan)."
        echo -e "${BCYAN}${BOX_V}${NC}  Common for water-cooled hotends with external radiator."
        echo -e "${BCYAN}${BOX_V}${NC}"

        # Determine current port assignment
        local primary_port="${HARDWARE_STATE[fan_radiator]}"
        local secondary_port="${HARDWARE_STATE[fan_radiator_2]}"

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
            [cC])
                save_state
                python3 "${SCRIPT_DIR}/setup-hardware.py" --clear-port "fan_radiator"
                python3 "${SCRIPT_DIR}/setup-hardware.py" --clear-port "fan_radiator_2"
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

        echo -e "${BCYAN}${BOX_V}${NC}  ${BWHITE}Select fan to configure advanced settings:${NC}"
        echo -e "${BCYAN}${BOX_V}${NC}"

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

    echo -e "${BCYAN}${BOX_V}${NC}  ${BWHITE}${fan_name} Advanced Options:${NC}"
    echo -e "${BCYAN}${BOX_V}${NC}"

    # Current values or defaults (using dynamic keys)
    local max_power="${WIZARD_STATE[fan_${fan_prefix}_max_power]:-1.0}"
    local cycle_time="${WIZARD_STATE[fan_${fan_prefix}_cycle_time]:-0.010}"
    local hw_pwm="${WIZARD_STATE[fan_${fan_prefix}_hardware_pwm]:-false}"
    local shutdown="${WIZARD_STATE[fan_${fan_prefix}_shutdown_speed]:-0}"
    local kick="${WIZARD_STATE[fan_${fan_prefix}_kick_start]:-0.5}"

    echo -e "${BCYAN}${BOX_V}${NC}  Current settings:"
    echo -e "${BCYAN}${BOX_V}${NC}  • max_power: ${CYAN}${max_power}${NC} (0.0-1.0)"
    echo -e "${BCYAN}${BOX_V}${NC}  • cycle_time: ${CYAN}${cycle_time}${NC} (0.010 default, 0.002 for high-speed)"
    echo -e "${BCYAN}${BOX_V}${NC}  • hardware_pwm: ${CYAN}${hw_pwm}${NC}"
    echo -e "${BCYAN}${BOX_V}${NC}  • shutdown_speed: ${CYAN}${shutdown}${NC}"
    echo -e "${BCYAN}${BOX_V}${NC}  • kick_start_time: ${CYAN}${kick}${NC} seconds"
    echo -e "${BCYAN}${BOX_V}${NC}"

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

        echo -e "${BCYAN}${BOX_V}${NC}  ${BWHITE}Configure printer lighting:${NC}"
        echo -e "${BCYAN}${BOX_V}${NC}"

        # Current status
        local light_type="${WIZARD_STATE[lighting_type]:-not configured}"
        echo -e "${BCYAN}${BOX_V}${NC}  Current: ${CYAN}${light_type}${NC}"
        echo -e "${BCYAN}${BOX_V}${NC}"

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
            echo -e "${BCYAN}${BOX_V}${NC}"
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
    echo -e "${BCYAN}${BOX_V}${NC}  ${BWHITE}Configure ${light_type} settings:${NC}"
    echo -e "${BCYAN}${BOX_V}${NC}"

    # LED count for addressable LEDs
    if [[ "$light_type" =~ ^(neopixel|dotstar)$ ]]; then
        echo -en "  Number of LEDs [${WIZARD_STATE[lighting_count]:-1}]: "
        read -r led_count
        WIZARD_STATE[lighting_count]="${led_count:-${WIZARD_STATE[lighting_count]:-1}}"
    fi

    # Color order for Neopixels
    if [[ "$light_type" == "neopixel" ]]; then
        echo ""
        echo -e "${BCYAN}${BOX_V}${NC}  ${BWHITE}Color order:${NC}"
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

        echo -e "${BCYAN}${BOX_V}${NC}  ${BWHITE}Additional MCUs and expansion boards:${NC}"
        echo -e "${BCYAN}${BOX_V}${NC}"

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
            echo -e "${BCYAN}${BOX_V}${NC}"
            echo -e "${BCYAN}${BOX_V}${NC}  ${BWHITE}Probe MCU (from Endstops):${NC}"
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

        echo -e "${BCYAN}${BOX_V}${NC}  ${BWHITE}Multi-Material Unit:${NC}"
        echo -e "${BCYAN}${BOX_V}${NC}"

        # Current status
        local mmu_info="${WIZARD_STATE[mmu_type]:-not configured}"
        echo -e "${BCYAN}${BOX_V}${NC}  Current: ${CYAN}${mmu_info}${NC}"
        echo -e "${BCYAN}${BOX_V}${NC}"

        print_menu_item "1" "" "ERCF (Enraged Rabbit Carrot Feeder)"
        print_menu_item "2" "" "Tradrack"
        print_menu_item "3" "" "MMU2S"
        print_menu_item "4" "" "Other MMU (manual config)"
        print_menu_item "5" "" "None - no MMU"

        # Connection config if MMU selected
        if [[ -n "${WIZARD_STATE[mmu_type]}" && "${WIZARD_STATE[mmu_type]}" != "none" ]]; then
            echo -e "${BCYAN}${BOX_V}${NC}"
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

    echo -e "${BCYAN}${BOX_V}${NC}  ${BWHITE}Configure ${WIZARD_STATE[mmu_type]} connection:${NC}"
    echo -e "${BCYAN}${BOX_V}${NC}"

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

            echo -e "${BCYAN}${BOX_V}${NC}  ${BWHITE}Scanning for USB devices...${NC}"
            echo -e "${BCYAN}${BOX_V}${NC}"

            local devices=()
            local i=1
            while IFS= read -r device; do
                if [[ -n "$device" ]]; then
                    devices+=("$device")
                    echo -e "${BCYAN}${BOX_V}${NC}  ${BWHITE}${i})${NC} ${device}"
                    i=$((i + 1))
                fi
            done < <(ls /dev/serial/by-id/ 2>/dev/null || true)

            if [[ ${#devices[@]} -eq 0 ]]; then
                echo -e "${BCYAN}${BOX_V}${NC}  ${YELLOW}No USB devices found.${NC}"
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

        echo -e "${BCYAN}${BOX_V}${NC}  ${BWHITE}Additional MCU expansion boards:${NC}"
        echo -e "${BCYAN}${BOX_V}${NC}"

        # Current status
        echo -e "${BCYAN}${BOX_V}${NC}  Current: ${CYAN}${WIZARD_STATE[expansion_board]:-not configured}${NC}"
        echo -e "${BCYAN}${BOX_V}${NC}"

        print_menu_item "1" "" "BTT EXP-MOT (motor expander)"
        print_menu_item "2" "" "Fly-SHT36/42 (as expansion, not toolhead)"
        print_menu_item "3" "" "Other expansion board"
        print_menu_item "4" "" "None - no expansion board"

        # Connection config if board selected
        if [[ -n "${WIZARD_STATE[expansion_board]}" && "${WIZARD_STATE[expansion_board]}" != "none" ]]; then
            echo -e "${BCYAN}${BOX_V}${NC}"
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

    echo -e "${BCYAN}${BOX_V}${NC}  ${BWHITE}Configure expansion board connection:${NC}"
    echo -e "${BCYAN}${BOX_V}${NC}"

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

menu_extras() {
    clear_screen
    print_header "Extra Features"
    
    echo -e "${BCYAN}${BOX_V}${NC}  ${BWHITE}Sensors:${NC}"
    
    local fs_status=$([[ "${WIZARD_STATE[has_filament_sensor]}" == "yes" ]] && echo "[x]" || echo "[ ]")
    local cs_status=$([[ "${WIZARD_STATE[has_chamber_sensor]}" == "yes" ]] && echo "[x]" || echo "[ ]")
    
    echo -e "${BCYAN}${BOX_V}${NC}  1) ${fs_status} Filament Sensor"
    echo -e "${BCYAN}${BOX_V}${NC}  2) ${cs_status} Chamber Temperature Sensor"
    
    echo -e "${BCYAN}${BOX_V}${NC}"
    echo -e "${BCYAN}${BOX_V}${NC}  ${BWHITE}Displays:${NC}"
    
    local ks_status=$([[ "${WIZARD_STATE[has_klipperscreen]}" == "yes" ]] && echo "[x]" || echo "[ ]")
    local lcd_status=$([[ "${WIZARD_STATE[has_lcd_display]}" == "yes" ]] && echo "[x]" || echo "[ ]")
    
    echo -e "${BCYAN}${BOX_V}${NC}  3) ${ks_status} KlipperScreen (HDMI/DSI touchscreen)"
    echo -e "${BCYAN}${BOX_V}${NC}  4) ${lcd_status} LCD Display (Mini12864/ST7920)"
    
    echo -e "${BCYAN}${BOX_V}${NC}"
    echo -e "${BCYAN}${BOX_V}${NC}  ${BWHITE}Lighting:${NC}"
    
    local led_status=$([[ "${WIZARD_STATE[has_leds]}" == "yes" ]] && echo "[x]" || echo "[ ]")
    local cl_status=$([[ "${WIZARD_STATE[has_caselight]}" == "yes" ]] && echo "[x]" || echo "[ ]")
    
    echo -e "${BCYAN}${BOX_V}${NC}  5) ${led_status} Status LEDs (NeoPixel on toolhead)"
    echo -e "${BCYAN}${BOX_V}${NC}  6) ${cl_status} Case Lighting"

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
            else
                WIZARD_STATE[has_chamber_sensor]="yes"
            fi
            menu_extras  # Refresh
            ;;
        3)
            if [[ "${WIZARD_STATE[has_klipperscreen]}" == "yes" ]]; then
                WIZARD_STATE[has_klipperscreen]=""
                WIZARD_STATE[klipperscreen_type]=""
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
            else
                WIZARD_STATE[has_leds]="yes"
            fi
            menu_extras  # Refresh
            ;;
        6)
            if [[ "${WIZARD_STATE[has_caselight]}" == "yes" ]]; then
                WIZARD_STATE[has_caselight]=""
            else
                WIZARD_STATE[has_caselight]="yes"
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
        [bB]) return ;;
        *) ;;
    esac
}

select_filament_sensor_type() {
    clear_screen
    print_header "Filament Sensor Type"
    
    echo -e "${BCYAN}${BOX_V}${NC}  1) Simple Switch (runout only)"
    echo -e "${BCYAN}${BOX_V}${NC}  2) Motion Sensor (runout + jam detection)"
    print_footer
    
    echo -en "${BYELLOW}Select type${NC}: "
    read -r choice
    
    case "$choice" in
        1) WIZARD_STATE[filament_sensor_type]="switch" ;;
        2) WIZARD_STATE[filament_sensor_type]="motion" ;;
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
    
    echo -e "${BCYAN}${BOX_V}${NC}  Crowsnest status: ${crowsnest_status}"
    echo -e "${BCYAN}${BOX_V}${NC}"
    echo -e "${BCYAN}${BOX_V}${NC}  ${BWHITE}What type of camera?${NC}"
    echo -e "${BCYAN}${BOX_V}${NC}"
    echo -e "${BCYAN}${BOX_V}${NC}  1) USB Webcam (Logitech, generic)"
    echo -e "${BCYAN}${BOX_V}${NC}  2) Raspberry Pi Camera (CSI)"
    echo -e "${BCYAN}${BOX_V}${NC}  3) IP Camera (RTSP stream)"
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
    
    echo -e "${BCYAN}${BOX_V}${NC}  ${WHITE}Select your touchscreen connection:${NC}"
    echo -e "${BCYAN}${BOX_V}${NC}"
    echo -e "${BCYAN}${BOX_V}${NC}  1) HDMI Touchscreen (BTT HDMI5/7, Waveshare, etc.)"
    echo -e "${BCYAN}${BOX_V}${NC}  2) DSI Display (Raspberry Pi official display)"
    echo -e "${BCYAN}${BOX_V}${NC}  3) SPI TFT (small 3.5\" displays)"
    print_footer
    
    echo -en "${BYELLOW}Select type${NC}: "
    read -r choice
    
    case "$choice" in
        1) WIZARD_STATE[klipperscreen_type]="hdmi" ;;
        2) WIZARD_STATE[klipperscreen_type]="dsi" ;;
        3) WIZARD_STATE[klipperscreen_type]="spi_tft" ;;
    esac
}

select_lcd_display_type() {
    clear_screen
    print_header "LCD Display Type"
    
    echo -e "${BCYAN}${BOX_V}${NC}  ${WHITE}Select your display type:${NC}"
    echo -e "${BCYAN}${BOX_V}${NC}"
    echo -e "${BCYAN}${BOX_V}${NC}  1) Mini 12864 (BTT/FYSETC Mini12864 - Voron style)"
    echo -e "${BCYAN}${BOX_V}${NC}  2) Full Graphic 12864 (RepRap ST7920)"
    echo -e "${BCYAN}${BOX_V}${NC}  3) BTT TFT35/TFT50 (12864 emulation mode)"
    echo -e "${BCYAN}${BOX_V}${NC}  4) OLED 128x64 (SSD1306/SH1106)"
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

menu_macros() {
    clear_screen
    print_header "Macro Configuration"
    echo -e "${BCYAN}${BOX_V}${NC}  ${GREEN}Default macros will be included:${NC}"
    echo -e "${BCYAN}${BOX_V}${NC}  • PRINT_START / PRINT_END"
    echo -e "${BCYAN}${BOX_V}${NC}  • Homing routines"
    echo -e "${BCYAN}${BOX_V}${NC}  • Filament load/unload"
    echo -e "${BCYAN}${BOX_V}${NC}  • Pause/Resume/Cancel"
    echo -e "${BCYAN}${BOX_V}${NC}  • Bed mesh helpers"
    echo -e "${BCYAN}${BOX_V}${NC}"
    echo -e "${BCYAN}${BOX_V}${NC}  ${YELLOW}Custom macro selection coming soon...${NC}"
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
    
    echo -e "${BCYAN}${BOX_V}${NC}  Configuration Summary:"
    echo -e "${BCYAN}${BOX_V}${NC}  • Board: ${WIZARD_STATE[board_name]}"
    echo -e "${BCYAN}${BOX_V}${NC}  • Kinematics: ${WIZARD_STATE[kinematics]}"
    echo -e "${BCYAN}${BOX_V}${NC}  • Bed: ${WIZARD_STATE[bed_size_x]}x${WIZARD_STATE[bed_size_y]}x${WIZARD_STATE[bed_size_z]}"
    echo -e "${BCYAN}${BOX_V}${NC}  • Probe: ${WIZARD_STATE[probe_type]:-none}"
    echo -e "${BCYAN}${BOX_V}${NC}"
    echo -e "${BCYAN}${BOX_V}${NC}  Output directory: ${OUTPUT_DIR}"
    print_footer
    
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
    local output="${OUTPUT_DIR}/macros.cfg"
    
    cat > "${output}" << 'EOF'
# ═══════════════════════════════════════════════════════════════════════════════
# MACROS & MAINSAIL ESSENTIALS
# Generated by gschpoozi
# ═══════════════════════════════════════════════════════════════════════════════

# ─────────────────────────────────────────────────────────────────────────────
# MAINSAIL / FLUIDD REQUIRED SECTIONS
# ─────────────────────────────────────────────────────────────────────────────
[virtual_sdcard]
path: ~/printer_data/gcodes
on_error_gcode: CANCEL_PRINT

[display_status]
# Required for M117 messages and print status

[pause_resume]
# Required for PAUSE/RESUME functionality

[exclude_object]
# Required for object cancellation in Mainsail/Fluidd

[respond]
# Required for M118 messages

# ─────────────────────────────────────────────────────────────────────────────
# PRINT START
# Usage: PRINT_START BED_TEMP=60 EXTRUDER_TEMP=200
# ─────────────────────────────────────────────────────────────────────────────
[gcode_macro PRINT_START]
description: Start print routine - heat, home, level, purge
gcode:
    {% set BED_TEMP = params.BED_TEMP|default(60)|float %}
    {% set EXTRUDER_TEMP = params.EXTRUDER_TEMP|default(200)|float %}
    
    M117 Heating bed...
    M140 S{BED_TEMP}                    ; Start bed heating
    M104 S150                           ; Preheat nozzle (no ooze)
    
    M117 Homing...
    G28                                 ; Home all axes
    
    M117 Waiting for bed...
    M190 S{BED_TEMP}                    ; Wait for bed temp
    
    M117 Bed mesh...
    BED_MESH_CALIBRATE                  ; Adaptive bed mesh
    
    M117 Heating nozzle...
    G1 X5 Y5 Z10 F3000                  ; Move to front corner
    M109 S{EXTRUDER_TEMP}               ; Wait for nozzle temp
    
    M117 Purging...
    PURGE_LINE                          ; Draw purge line
    
    M117 Printing...

# ─────────────────────────────────────────────────────────────────────────────
# PRINT END
# ─────────────────────────────────────────────────────────────────────────────
[gcode_macro PRINT_END]
description: End print routine - retract, park, cool down
gcode:
    {% set max_y = printer.toolhead.axis_maximum.y|float %}
    {% set max_x = printer.toolhead.axis_maximum.x|float %}
    
    M400                                ; Wait for buffer to clear
    G92 E0                              ; Reset extruder
    G1 E-5.0 F3600                      ; Retract filament
    
    G91                                 ; Relative positioning
    G1 Z10 F3000                        ; Raise Z
    G90                                 ; Absolute positioning
    
    G1 X{max_x - 10} Y{max_y - 10} F6000  ; Park at rear
    
    M104 S0                             ; Turn off hotend
    M140 S0                             ; Turn off bed
    M106 S0                             ; Turn off part cooling fan
    M84                                 ; Disable steppers
    
    M117 Print complete!

# ─────────────────────────────────────────────────────────────────────────────
# PURGE LINE
# ─────────────────────────────────────────────────────────────────────────────
[gcode_macro PURGE_LINE]
description: Draw a purge line at the front of the bed
gcode:
    G92 E0                              ; Reset extruder
    G1 X5 Y5 Z0.3 F3000                 ; Move to start
    G1 X100 Y5 Z0.3 E15 F1500           ; Draw line
    G1 X100 Y5.4 Z0.3 F3000             ; Move over
    G1 X5 Y5.4 Z0.3 E30 F1500           ; Draw second line
    G92 E0                              ; Reset extruder
    G1 Z2 F3000                         ; Lift nozzle

# ─────────────────────────────────────────────────────────────────────────────
# PAUSE / RESUME / CANCEL
# ─────────────────────────────────────────────────────────────────────────────
[gcode_macro PAUSE]
description: Pause the print
rename_existing: BASE_PAUSE
gcode:
    {% set X = params.X|default(10)|float %}
    {% set Y = params.Y|default(10)|float %}
    {% set Z = params.Z|default(10)|float %}
    {% set E = params.E|default(5)|float %}
    
    SAVE_GCODE_STATE NAME=PAUSE_state
    BASE_PAUSE
    G91
    G1 E-{E} F2100
    G1 Z{Z} F3000
    G90
    G1 X{X} Y{Y} F6000

[gcode_macro RESUME]
description: Resume the print
rename_existing: BASE_RESUME
gcode:
    {% set E = params.E|default(5)|float %}
    
    G91
    G1 E{E} F2100
    G90
    RESTORE_GCODE_STATE NAME=PAUSE_state MOVE=1 MOVE_SPEED=60
    BASE_RESUME

[gcode_macro CANCEL_PRINT]
description: Cancel the print
rename_existing: BASE_CANCEL_PRINT
gcode:
    PRINT_END
    BASE_CANCEL_PRINT

# ─────────────────────────────────────────────────────────────────────────────
# FILAMENT
# ─────────────────────────────────────────────────────────────────────────────
[gcode_macro LOAD_FILAMENT]
description: Load filament into the extruder
gcode:
    {% set TEMP = params.TEMP|default(220)|float %}
    {% set LENGTH = params.LENGTH|default(100)|float %}
    
    M109 S{TEMP}                        ; Heat nozzle
    M83                                 ; Relative extrusion
    G1 E{LENGTH} F300                   ; Extrude
    M82                                 ; Absolute extrusion
    M104 S0                             ; Cool down

[gcode_macro UNLOAD_FILAMENT]
description: Unload filament from the extruder
gcode:
    {% set TEMP = params.TEMP|default(220)|float %}
    {% set LENGTH = params.LENGTH|default(100)|float %}
    
    M109 S{TEMP}                        ; Heat nozzle
    M83                                 ; Relative extrusion
    G1 E10 F300                         ; Purge a little
    G1 E-{LENGTH} F1800                 ; Retract
    M82                                 ; Absolute extrusion
    M104 S0                             ; Cool down
EOF

    echo -e "  ${GREEN}✓${NC} macros.cfg"
}

generate_homing_cfg() {
    local output="${OUTPUT_DIR}/homing.cfg"
    
    cat > "${output}" << 'EOF'
# ═══════════════════════════════════════════════════════════════════════════════
# HOMING
# Generated by gschpoozi
# ═══════════════════════════════════════════════════════════════════════════════

# ─────────────────────────────────────────────────────────────────────────────
# SAFE Z HOME
# ─────────────────────────────────────────────────────────────────────────────
[safe_z_home]
home_xy_position: 150, 150  # Center of bed - adjust for your printer
speed: 100
z_hop: 10
z_hop_speed: 15

# ─────────────────────────────────────────────────────────────────────────────
# BED MESH
# ─────────────────────────────────────────────────────────────────────────────
[bed_mesh]
speed: 300
horizontal_move_z: 5
mesh_min: 30, 30
mesh_max: 270, 270        # Adjust for your bed size
probe_count: 5, 5
algorithm: bicubic
fade_start: 0.6
fade_end: 10
fade_target: 0

# ─────────────────────────────────────────────────────────────────────────────
# HOMING OVERRIDE (Optional - uncomment if needed)
# ─────────────────────────────────────────────────────────────────────────────
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
#        G1 X150 Y150 F6000
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
# ─────────────────────────────────────────────────────────────────────────────
[include gschpoozi/hardware.cfg]
[include gschpoozi/macros.cfg]
[include gschpoozi/homing.cfg]

# Optional: Uncomment if you have these features
#[include gschpoozi/probe.cfg]
#[include gschpoozi/sensors.cfg]

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


