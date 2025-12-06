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
                   [[ "$basename" == *Katapult* ]]; then
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
        print_action_item "B" "Back to main menu"
        
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
    
    echo -e "${BCYAN}${BOX_V}${NC}"
    print_action_item "C" "Cancel"
    
    print_footer
    
    read -r -p "Select adapter: " choice
    
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
    echo -e "${BCYAN}${BOX_V}${NC}"
    print_action_item "C" "Cancel"
    
    print_footer
    
    read -r -p "Select bitrate: " choice
    
    local bitrate
    case "$choice" in
        1) bitrate=1000000 ;;
        2) bitrate=500000 ;;
        3) bitrate=250000 ;;
        [Cc]) return ;;
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
    echo -e "${BCYAN}${BOX_V}${NC}"
    print_action_item "C" "Cancel"
    
    print_footer
    
    read -r -p "Select bitrate: " choice
    
    local bitrate
    case "$choice" in
        1) bitrate=1000000 ;;
        2) bitrate=500000 ;;
        [Cc]) return ;;
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

# Hardware state file (from Python script)
HARDWARE_STATE_FILE="${REPO_ROOT}/.hardware-state.json"

# Load hardware state from JSON (created by setup-hardware.py)
load_hardware_state() {
    if [[ -f "${HARDWARE_STATE_FILE}" ]]; then
        # Parse JSON using Python (guaranteed to be available)
        # Note: Use 'or' to handle None values properly
        eval "$(python3 -c "
import json
try:
    with open('${HARDWARE_STATE_FILE}') as f:
        data = json.load(f)
    board_id = data.get('board_id') or ''
    board_name = data.get('board_name') or ''
    toolboard_id = data.get('toolboard_id') or ''
    toolboard_name = data.get('toolboard_name') or ''
    print(f\"WIZARD_STATE[board]='{board_id}'\")
    print(f\"WIZARD_STATE[board_name]='{board_name}'\")
    print(f\"WIZARD_STATE[toolboard]='{toolboard_id}'\")
    print(f\"WIZARD_STATE[toolboard_name]='{toolboard_name}'\")
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
        [probe_type]=""
        [has_filament_sensor]=""
        [has_chamber_sensor]=""
        [position_endstop_x]=""
        [position_endstop_y]=""
        [position_endstop_z]=""
        [position_min_x]=""
        [position_min_y]=""
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
        bed)
            [[ -n "${WIZARD_STATE[bed_size_x]}" ]] && echo "done" || echo ""
            ;;
        probe)
            [[ -n "${WIZARD_STATE[probe_type]}" ]] && echo "done" || echo ""
            ;;
        extras)
            [[ -n "${WIZARD_STATE[has_filament_sensor]}" || -n "${WIZARD_STATE[has_chamber_sensor]}" ]] && echo "done" || echo ""
            ;;
        macros)
            echo "done"  # Default macros always included
            ;;
    esac
}

# ═══════════════════════════════════════════════════════════════════════════════
# MENU SCREENS
# ═══════════════════════════════════════════════════════════════════════════════

show_main_menu() {
    # Load hardware state from Python script's output
    load_hardware_state
    
    clear_screen
    print_header "gschpoozi Configuration Wizard"
    
    # Calculate required motor ports based on selections
    local motor_count=2  # X, Y minimum
    local z_count="${WIZARD_STATE[z_stepper_count]:-1}"
    motor_count=$((motor_count + z_count))
    
    # Extruder on main board only if no toolboard
    local extruder_on_mainboard="yes"
    if [[ -n "${WIZARD_STATE[toolboard]}" && "${WIZARD_STATE[toolboard]}" != "none" ]]; then
        extruder_on_mainboard="no"
    else
        motor_count=$((motor_count + 1))  # Add extruder
    fi
    
    echo -e "${BCYAN}${BOX_V}${NC}  ${BWHITE}Step 1: Define Your Setup${NC}"
    print_menu_item "1" "$(get_step_status toolboard)" "Toolhead Board" "${WIZARD_STATE[toolboard_name]:-none}"
    
    local kin_display="${WIZARD_STATE[kinematics]:-not set}"
    if [[ -n "${WIZARD_STATE[z_stepper_count]}" ]]; then
        kin_display="${kin_display}, ${WIZARD_STATE[z_stepper_count]}x Z"
        if [[ "${WIZARD_STATE[leveling_method]}" != "none" && -n "${WIZARD_STATE[leveling_method]}" ]]; then
            kin_display="${kin_display} (${WIZARD_STATE[leveling_method]})"
        fi
    fi
    print_menu_item "2" "$(get_step_status kinematics)" "Kinematics" "${kin_display}"
    print_menu_item "3" "$(get_step_status steppers)" "Stepper Drivers" "${WIZARD_STATE[driver_X]:-not set}"
    
    echo -e "${BCYAN}${BOX_V}${NC}"
    echo -e "${BCYAN}${BOX_V}${NC}  ${BWHITE}Step 2: Hardware Selection${NC}"
    local board_info="${WIZARD_STATE[board_name]:-not selected}"
    if [[ -n "${WIZARD_STATE[board]}" ]]; then
        board_info="${board_info} (need ${motor_count} motors)"
    fi
    print_menu_item "4" "$(get_step_status board)" "Main Board" "${board_info}"
    print_menu_item "5" "$(get_step_status ports)" "Port Assignment" "$(get_port_status)"
    
    # Show CAN status if toolboard uses CAN
    local can_status=""
    if [[ "${WIZARD_STATE[toolboard_connection]}" == "can" ]]; then
        if check_can_interface can0 2>/dev/null; then
            can_status="${GREEN}UP${NC}"
        else
            can_status="${RED}Not configured${NC}"
        fi
        print_menu_item "C" "" "CAN Bus Setup" "${can_status}"
    fi
    
    echo -e "${BCYAN}${BOX_V}${NC}"
    echo -e "${BCYAN}${BOX_V}${NC}  ${BWHITE}Step 3: Configuration${NC}"
    print_menu_item "6" "$(get_step_status extruder)" "Extruder" "${WIZARD_STATE[extruder_type]:-not set}"
    print_menu_item "7" "$(get_step_status bed)" "Heated Bed" "${WIZARD_STATE[bed_size_x]:+${WIZARD_STATE[bed_size_x]}x${WIZARD_STATE[bed_size_y]}mm}"
    print_menu_item "8" "$(get_step_status probe)" "Probe" "${WIZARD_STATE[probe_type]:-not set}"
    print_menu_item "9" "$(get_step_status extras)" "Extras" ""
    print_menu_item "0" "$(get_step_status macros)" "Macros" ""
    
    print_separator
    print_action_item "F" "MCU Firmware Update"
    print_action_item "G" "Generate Configuration"
    print_action_item "S" "Save Progress"
    print_action_item "Q" "Quit"
    print_footer
    
    echo -en "${BYELLOW}Select option${NC}: "
    read -r choice
    
    case "$choice" in
        1) menu_toolboard ;;
        2) menu_kinematics ;;
        3) menu_steppers ;;
        4) menu_board ;;
        5) menu_ports ;;
        6) menu_extruder ;;
        7) menu_bed ;;
        8) menu_probe ;;
        9) menu_extras ;;
        0) menu_macros ;;
        [cC]) menu_can_setup ;;
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
    clear_screen
    print_header "Select Kinematics"
    
    print_menu_item "1" "" "CoreXY"
    print_menu_item "2" "" "CoreXY AWD (4 XY motors)"
    print_menu_item "3" "" "Cartesian (bed slinger)"
    print_menu_item "4" "" "CoreXZ"
    print_separator
    print_action_item "B" "Back to Main Menu"
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
    
    # Now ask about Z configuration
    menu_z_config
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
        print_action_item "B" "Back to Main Menu"
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
# EXTRUDER CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

menu_extruder() {
    clear_screen
    print_header "Extruder Configuration"
    
    echo -e "${BCYAN}${BOX_V}${NC}  ${BWHITE}Select Extruder Type:${NC}"
    print_menu_item "1" "" "Direct Drive"
    print_menu_item "2" "" "Bowden"
    print_separator
    print_action_item "B" "Back to Main Menu"
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
    
    case "$choice" in
        1) WIZARD_STATE[hotend_thermistor]="Generic 3950" ;;
        2) WIZARD_STATE[hotend_thermistor]="ATC Semitec 104GT-2" ;;
        3) WIZARD_STATE[hotend_thermistor]="ATC Semitec 104NT-4-R025H42G" ;;
        4) WIZARD_STATE[hotend_thermistor]="Honeywell 100K 135-104LAG-J01" ;;
        5) WIZARD_STATE[hotend_thermistor]="NTC 100K MGB18-104F39050L32" ;;
        6) WIZARD_STATE[hotend_thermistor]="SliceEngineering450" ;;
        7) 
            WIZARD_STATE[hotend_thermistor]="PT1000"
            # PT1000 direct needs pullup resistor value
            menu_pullup_resistor
            ;;
        8) WIZARD_STATE[hotend_thermistor]="PT1000_MAX31865" ;;
        9) WIZARD_STATE[hotend_thermistor]="PT100_MAX31865" ;;
        [mM])
            echo -e "${BCYAN}${BOX_V}${NC}"
            echo -e "${BCYAN}${BOX_V}${NC}  Enter exact Klipper sensor_type value:"
            echo -e "${BCYAN}${BOX_V}${NC}  (See: https://www.klipper3d.org/Config_Reference.html#thermistor)"
            echo -en "  "
            read -r custom_type
            if [[ -n "$custom_type" ]]; then
                WIZARD_STATE[hotend_thermistor]="$custom_type"
            fi
            ;;
        [bB]) return ;;
        *) ;;
    esac
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
    print_separator
    print_action_item "S" "Skip (use Klipper default)"
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
        [sS]) WIZARD_STATE[hotend_pullup_resistor]="" ;;
        *) ;;
    esac
}

# ═══════════════════════════════════════════════════════════════════════════════
# BED CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

menu_bed() {
    clear_screen
    print_header "Heated Bed Configuration"
    
    echo -e "${BCYAN}${BOX_V}${NC}  ${BWHITE}Enter bed dimensions:${NC}"
    echo -e "${BCYAN}${BOX_V}${NC}"
    
    # Use a subshell-safe approach for prompts
    echo -en "  " >&2
    WIZARD_STATE[bed_size_x]=$(prompt_input "Bed size X (mm)" "${WIZARD_STATE[bed_size_x]:-300}")
    echo -en "  " >&2
    WIZARD_STATE[bed_size_y]=$(prompt_input "Bed size Y (mm)" "${WIZARD_STATE[bed_size_y]:-300}")
    echo -en "  " >&2
    WIZARD_STATE[bed_size_z]=$(prompt_input "Max Z height (mm)" "${WIZARD_STATE[bed_size_z]:-350}")
    
    echo ""
    echo -e "${BCYAN}${BOX_V}${NC}  ${BWHITE}Select Bed Thermistor:${NC}"
    print_menu_item "1" "" "Generic 3950 (NTC 100K)"
    print_menu_item "2" "" "Keenovo (NTC 100K)"
    print_menu_item "3" "" "PT1000"
    print_menu_item "4" "" "NTC 100K beta 3950 (Prusa)"
    print_separator
    print_action_item "B" "Back to Main Menu"
    print_footer
    
    echo -en "${BYELLOW}Select thermistor${NC}: "
    read -r choice
    
    case "$choice" in
        1) WIZARD_STATE[bed_thermistor]="Generic 3950" ;;
        2) WIZARD_STATE[bed_thermistor]="Keenovo" ;;
        3) WIZARD_STATE[bed_thermistor]="PT1000" ;;
        4) WIZARD_STATE[bed_thermistor]="NTC 100K beta 3950" ;;
        [bB]) return ;;
        *) ;;
    esac
}

# ═══════════════════════════════════════════════════════════════════════════════
# PROBE CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

menu_probe() {
    clear_screen
    print_header "Probe Configuration"
    
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
    
    print_menu_item "1" "" "BLTouch / 3DTouch"
    echo -e "${BCYAN}${BOX_V}${NC}  ${BWHITE}2)${NC} [ ] Beacon (Eddy Current) ${beacon_status}"
    echo -e "${BCYAN}${BOX_V}${NC}  ${BWHITE}3)${NC} [ ] Cartographer ${carto_status}"
    echo -e "${BCYAN}${BOX_V}${NC}  ${BWHITE}4)${NC} [ ] BTT Eddy ${eddy_status}"
    print_menu_item "5" "" "Klicky Probe"
    print_menu_item "6" "" "Inductive Probe (PINDA/SuperPINDA)"
    print_menu_item "7" "" "Physical Z Endstop (no probe)"
    print_separator
    print_action_item "B" "Back to Main Menu"
    print_footer
    
    echo -en "${BYELLOW}Select probe${NC}: "
    read -r choice
    
    local selected_probe=""
    case "$choice" in
        1) WIZARD_STATE[probe_type]="bltouch" ;;
        2) 
            WIZARD_STATE[probe_type]="beacon"
            selected_probe="beacon"
            ;;
        3) 
            WIZARD_STATE[probe_type]="cartographer"
            selected_probe="cartographer"
            ;;
        4) 
            WIZARD_STATE[probe_type]="btt-eddy"
            selected_probe="btt-eddy"
            ;;
        5) WIZARD_STATE[probe_type]="klicky" ;;
        6) WIZARD_STATE[probe_type]="inductive" ;;
        7) 
            WIZARD_STATE[probe_type]="endstop"
            # Prompt for Z endstop position since using physical endstop
            menu_z_endstop_position
            ;;
        [bB]) return ;;
        *) return ;;
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
}

# ═══════════════════════════════════════════════════════════════════════════════
# PLACEHOLDER MENUS (TODO)
# ═══════════════════════════════════════════════════════════════════════════════

menu_fans() {
    clear_screen
    print_header "Fan Configuration"
    echo -e "${BCYAN}${BOX_V}${NC}  ${YELLOW}Fan configuration coming soon...${NC}"
    echo -e "${BCYAN}${BOX_V}${NC}  Default fans will be configured based on board selection."
    print_footer
    wait_for_key
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
    
    echo -e "${BCYAN}${BOX_V}${NC}"
    echo -e "${BCYAN}${BOX_V}${NC}  ${BWHITE}Camera:${NC}"
    
    local cam_status=$([[ "${WIZARD_STATE[has_camera]}" == "yes" ]] && echo "[x]" || echo "[ ]")
    
    echo -e "${BCYAN}${BOX_V}${NC}  7) ${cam_status} Webcam (Crowsnest)"
    
    print_separator
    print_action_item "B" "Back to Main Menu"
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
        show_main_menu
    done
}

# Run main
main "$@"

