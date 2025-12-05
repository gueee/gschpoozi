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
        local board_id board_name toolboard_id toolboard_name
        
        eval "$(python3 -c "
import json
try:
    with open('${HARDWARE_STATE_FILE}') as f:
        data = json.load(f)
    print(f\"WIZARD_STATE[board]='{data.get('board_id', '')}'\")
    print(f\"WIZARD_STATE[board_name]='{data.get('board_name', '')}'\")
    print(f\"WIZARD_STATE[toolboard]='{data.get('toolboard_id', '')}'\")
    print(f\"WIZARD_STATE[toolboard_name]='{data.get('toolboard_name', '')}'\")
except:
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
        [bed_thermistor]=""
        [probe_type]=""
        [has_filament_sensor]=""
        [has_chamber_sensor]=""
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
    
    echo -e "${BCYAN}${BOX_V}${NC}"
    echo -e "${BCYAN}${BOX_V}${NC}  ${BWHITE}Step 3: Configuration${NC}"
    print_menu_item "6" "$(get_step_status extruder)" "Extruder" "${WIZARD_STATE[extruder_type]:-not set}"
    print_menu_item "7" "$(get_step_status bed)" "Heated Bed" "${WIZARD_STATE[bed_size_x]:+${WIZARD_STATE[bed_size_x]}x${WIZARD_STATE[bed_size_y]}mm}"
    print_menu_item "8" "$(get_step_status probe)" "Probe" "${WIZARD_STATE[probe_type]:-not set}"
    print_menu_item "9" "$(get_step_status extras)" "Extras" ""
    print_menu_item "0" "$(get_step_status macros)" "Macros" ""
    
    print_separator
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
    clear_screen
    print_header "Hotend Thermistor"
    
    print_menu_item "1" "" "Generic 3950 (NTC 100K)"
    print_menu_item "2" "" "ATC Semitec 104NT-4-R025H42G"
    print_menu_item "3" "" "Slice Engineering 450C"
    print_menu_item "4" "" "PT1000"
    print_separator
    print_action_item "B" "Back"
    print_footer
    
    echo -en "${BYELLOW}Select thermistor${NC}: "
    read -r choice
    
    case "$choice" in
        1) WIZARD_STATE[hotend_thermistor]="Generic 3950" ;;
        2) WIZARD_STATE[hotend_thermistor]="ATC Semitec 104NT-4-R025H42G" ;;
        3) WIZARD_STATE[hotend_thermistor]="SliceEngineering450" ;;
        4) WIZARD_STATE[hotend_thermistor]="PT1000" ;;
        [bB]) return ;;
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
    
    print_menu_item "1" "" "BLTouch / 3DTouch"
    print_menu_item "2" "" "Beacon (Eddy Current)"
    print_menu_item "3" "" "Klicky Probe"
    print_menu_item "4" "" "Inductive Probe"
    print_menu_item "5" "" "Microswitch (Z endstop)"
    print_menu_item "6" "" "None"
    print_separator
    print_action_item "B" "Back to Main Menu"
    print_footer
    
    echo -en "${BYELLOW}Select probe${NC}: "
    read -r choice
    
    case "$choice" in
        1) WIZARD_STATE[probe_type]="bltouch" ;;
        2) WIZARD_STATE[probe_type]="beacon" ;;
        3) WIZARD_STATE[probe_type]="klicky" ;;
        4) WIZARD_STATE[probe_type]="inductive" ;;
        5) WIZARD_STATE[probe_type]="endstop" ;;
        6) WIZARD_STATE[probe_type]="none" ;;
        [bB]) return ;;
        *) ;;
    esac
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
position_min: 0
position_max: ${WIZARD_STATE[bed_size_x]:-300}
position_endstop: ${WIZARD_STATE[bed_size_x]:-300}
homing_speed: 80

[stepper_y]
step_pin: REPLACE_PIN
dir_pin: REPLACE_PIN
enable_pin: !REPLACE_PIN
microsteps: 16
rotation_distance: 40
endstop_pin: REPLACE_PIN
position_min: 0
position_max: ${WIZARD_STATE[bed_size_y]:-300}
position_endstop: ${WIZARD_STATE[bed_size_y]:-300}
homing_speed: 80

[stepper_z]
step_pin: REPLACE_PIN
dir_pin: REPLACE_PIN
enable_pin: !REPLACE_PIN
microsteps: 16
rotation_distance: 8
endstop_pin: probe:z_virtual_endstop
position_min: -5
position_max: ${WIZARD_STATE[bed_size_z]:-350}
homing_speed: 15

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
# MACROS
# Generated by gschpoozi
# ═══════════════════════════════════════════════════════════════════════════════

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
    
    if [[ ! -f "${moonraker_conf}" ]]; then
        echo -e "${YELLOW}moonraker.conf not found at ${moonraker_conf}${NC}"
        echo -e "Add this to your moonraker.conf manually:"
    else
        echo -e "Add this to your moonraker.conf:"
    fi
    
    cat << 'EOF'

##### gschpoozi Configuration Update Manager ----------------
[update_manager gschpoozi]
type: git_repo
primary_branch: main
path: ~/gschpoozi
origin: https://github.com/gueee/gschpoozi.git
install_script: scripts/update-manager/moonraker-update.sh
is_system_service: False
managed_services: klipper
info_tags:
    desc=gschpoozi Klipper Configuration Framework

EOF
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
    
    # Main loop
    while true; do
        show_main_menu
    done
}

# Run main
main "$@"

