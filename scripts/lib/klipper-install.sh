#!/bin/bash
#
# gschpoozi Klipper Installation Library
# KIAUH-style installation routines for Klipper ecosystem
#
# This file is sourced by configure.sh
#

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

# Repository URLs
# Check for KLIPPER_VARIANT environment variable (set by component manager)
# Defaults to "standard" if not set
KLIPPER_VARIANT="${KLIPPER_VARIANT:-standard}"
if [[ "${KLIPPER_VARIANT}" == "kalico" ]]; then
    KLIPPER_REPO="https://github.com/KalicoCrew/kalico.git"
else
    KLIPPER_REPO="https://github.com/Klipper3d/klipper.git"
fi
MOONRAKER_REPO="https://github.com/Arksine/moonraker.git"
MAINSAIL_REPO="https://github.com/mainsail-crew/mainsail"
FLUIDD_REPO="https://github.com/fluidd-core/fluidd"
CROWSNEST_REPO="https://github.com/mainsail-crew/crowsnest.git"
SONAR_REPO="https://github.com/mainsail-crew/sonar.git"
TIMELAPSE_REPO="https://github.com/mainsail-crew/moonraker-timelapse.git"

# Installation paths
KLIPPER_DIR="${HOME}/klipper"
MOONRAKER_DIR="${HOME}/moonraker"
MAINSAIL_DIR="${HOME}/mainsail"
FLUIDD_DIR="${HOME}/fluidd"
CROWSNEST_DIR="${HOME}/crowsnest"
SONAR_DIR="${HOME}/sonar"
TIMELAPSE_DIR="${HOME}/moonraker-timelapse"

KLIPPY_ENV="${HOME}/klippy-env"
MOONRAKER_ENV="${HOME}/moonraker-env"

PRINTER_DATA="${HOME}/printer_data"
SYSTEMD_DIR="/etc/systemd/system"

# Template paths (set by configure.sh)
INSTALL_LIB_DIR="${INSTALL_LIB_DIR:-$(dirname "${BASH_SOURCE[0]}")}"
SERVICE_TEMPLATES="${INSTALL_LIB_DIR}/service-templates"
NGINX_TEMPLATES="${INSTALL_LIB_DIR}/nginx-templates"

# ═══════════════════════════════════════════════════════════════════════════════
# DEPENDENCY DEFINITIONS
# ═══════════════════════════════════════════════════════════════════════════════

# Klipper dependencies
KLIPPER_DEPS=(
    git
    virtualenv
    python3-dev
    python3-venv
    libffi-dev
    build-essential
    libncurses-dev
    libusb-dev
    stm32flash
    libnewlib-arm-none-eabi
    gcc-arm-none-eabi
    binutils-arm-none-eabi
    libusb-1.0-0
    libusb-1.0-0-dev
    pkg-config
    dfu-util
)

# Moonraker dependencies
MOONRAKER_DEPS=(
    python3-virtualenv
    python3-dev
    libopenjp2-7
    python3-libgpiod
    curl
    libcurl4-openssl-dev
    libssl-dev
    liblmdb-dev
    libsodium-dev
    zlib1g-dev
    libjpeg-dev
    packagekit
    wireless-tools
    iw
)

# Web interface dependencies
WEBUI_DEPS=(
    nginx
)

# ═══════════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

# Print status message
status_msg() {
    echo -e "${CYAN}###### $1${NC}"
}

# Print success message
ok_msg() {
    echo -e "${GREEN}[OK] $1${NC}"
}

# Print error message
error_msg() {
    echo -e "${RED}[ERROR] $1${NC}"
}

# Print warning message
warn_msg() {
    echo -e "${YELLOW}[WARN] $1${NC}"
}

# ------------------------------------------------------------------------------
# INSTALL STATUS HELPERS (KIAUH-style)
#
# The component manager + update/remove routines use these predicates. They must
# be available whenever this file is sourced (e.g. via scripts/tools/* wrapper).
# ------------------------------------------------------------------------------

is_klipper_installed() {
    [[ -d "${KLIPPER_DIR}" && -f "${KLIPPER_DIR}/klippy/klippy.py" ]]
}

is_moonraker_installed() {
    [[ -d "${MOONRAKER_DIR}" && -f "${MOONRAKER_DIR}/moonraker/moonraker.py" ]]
}

is_mainsail_installed() {
    [[ -d "${MAINSAIL_DIR}" ]]
}

is_fluidd_installed() {
    [[ -d "${FLUIDD_DIR}" ]]
}

is_crowsnest_installed() {
    [[ -d "${CROWSNEST_DIR}" ]]
}

is_sonar_installed() {
    [[ -d "${SONAR_DIR}" ]]
}

is_timelapse_installed() {
    [[ -d "${TIMELAPSE_DIR}" ]]
}

# Check if running as root (we don't want that)
check_not_root() {
    if [[ $(id -u) -eq 0 ]]; then
        error_msg "This script should NOT be run as root!"
        error_msg "Please run as your normal user (the script will use sudo when needed)."
        return 1
    fi
    return 0
}

# Check if user has sudo access
check_sudo_access() {
    if ! sudo -v 2>/dev/null; then
        error_msg "This script requires sudo access."
        error_msg "Please ensure your user has sudo privileges."
        return 1
    fi
    return 0
}

# Install apt packages
install_packages() {
    local packages=("$@")

    status_msg "Updating package lists..."
    sudo apt-get update

    status_msg "Installing packages: ${packages[*]}"
    sudo apt-get install -y "${packages[@]}"

    if [[ $? -eq 0 ]]; then
        ok_msg "Packages installed successfully"
        return 0
    else
        error_msg "Failed to install some packages"
        return 1
    fi
}

# Clone a git repository
clone_repo() {
    local repo_url="$1"
    local target_dir="$2"
    local branch="${3:-}"

    if [[ -d "$target_dir" ]]; then
        warn_msg "Directory $target_dir already exists"
        if [[ -d "$target_dir/.git" ]]; then
            status_msg "Updating existing repository..."
            cd "$target_dir" && git pull
            return $?
        else
            error_msg "Directory exists but is not a git repository"
            return 1
        fi
    fi

    status_msg "Cloning $repo_url to $target_dir..."
    if [[ -n "$branch" ]]; then
        git clone -b "$branch" "$repo_url" "$target_dir"
    else
        git clone "$repo_url" "$target_dir"
    fi

    return $?
}

# Create Python virtual environment
create_virtualenv() {
    local venv_path="$1"
    local python_version="${2:-python3}"

    if [[ -d "$venv_path" ]]; then
        warn_msg "Virtual environment already exists at $venv_path"
        return 0
    fi

    status_msg "Creating virtual environment at $venv_path..."
    "$python_version" -m venv "$venv_path"

    if [[ $? -eq 0 ]]; then
        ok_msg "Virtual environment created"
        return 0
    else
        error_msg "Failed to create virtual environment"
        return 1
    fi
}

# Install pip requirements
install_pip_requirements() {
    local venv_path="$1"
    local requirements_file="$2"

    if [[ ! -f "$requirements_file" ]]; then
        error_msg "Requirements file not found: $requirements_file"
        return 1
    fi

    status_msg "Installing Python requirements from $requirements_file..."
    "${venv_path}/bin/pip" install --upgrade pip
    "${venv_path}/bin/pip" install -r "$requirements_file"

    return $?
}

# Create systemd service from template
create_systemd_service() {
    local service_name="$1"
    local template_file="$2"

    if [[ ! -f "$template_file" ]]; then
        error_msg "Service template not found: $template_file"
        return 1
    fi

    local service_file="${SYSTEMD_DIR}/${service_name}.service"

    status_msg "Creating systemd service: $service_name"

    # Replace placeholders in template
    local temp_file=$(mktemp)
    sed -e "s|%USER%|${USER}|g" \
        -e "s|%HOME%|${HOME}|g" \
        "$template_file" > "$temp_file"

    sudo cp "$temp_file" "$service_file"
    rm "$temp_file"

    sudo systemctl daemon-reload

    ok_msg "Service file created: $service_file"
    return 0
}

# Enable and start a systemd service
enable_service() {
    local service_name="$1"

    status_msg "Enabling and starting $service_name..."
    sudo systemctl enable "$service_name"
    sudo systemctl start "$service_name"

    # Check if service started successfully
    sleep 2
    if systemctl is-active --quiet "$service_name"; then
        ok_msg "$service_name is running"
        return 0
    else
        error_msg "$service_name failed to start"
        return 1
    fi
}

# Create printer_data directory structure
create_printer_data_dirs() {
    status_msg "Creating printer_data directory structure..."

    mkdir -p "${PRINTER_DATA}/config"
    mkdir -p "${PRINTER_DATA}/gcodes"
    mkdir -p "${PRINTER_DATA}/logs"
    mkdir -p "${PRINTER_DATA}/systemd"
    mkdir -p "${PRINTER_DATA}/comms"

    ok_msg "Directory structure created at ${PRINTER_DATA}"
    return 0
}

# Create Klipper environment file
create_klipper_env() {
    local env_file="${PRINTER_DATA}/systemd/klipper.env"

    if [[ -f "$env_file" ]]; then
        warn_msg "Klipper env file already exists"
        return 0
    fi

    status_msg "Creating Klipper environment file..."
    cat > "$env_file" << EOF
KLIPPER_ARGS=${PRINTER_DATA}/config/printer.cfg -l ${PRINTER_DATA}/logs/klippy.log -I ${PRINTER_DATA}/comms/klippy.serial -a ${PRINTER_DATA}/comms/klippy.sock
EOF

    ok_msg "Created $env_file"
    return 0
}

# Create Moonraker environment file (matches official Moonraker installer format)
create_moonraker_env() {
    local env_file="${PRINTER_DATA}/systemd/moonraker.env"

    if [[ -f "$env_file" ]]; then
        warn_msg "Moonraker env file already exists"
        return 0
    fi

    status_msg "Creating Moonraker environment file..."
    cat > "$env_file" << EOF
MOONRAKER_DATA_PATH="${PRINTER_DATA}"
MOONRAKER_ARGS="-m moonraker"
EOF

    ok_msg "Created $env_file"
    return 0
}

# Create moonraker-admin group for polkit permissions
create_moonraker_group() {
    if getent group moonraker-admin > /dev/null 2>&1; then
        status_msg "moonraker-admin group already exists"
    else
        status_msg "Creating moonraker-admin group..."
        sudo groupadd -f moonraker-admin
        ok_msg "Created moonraker-admin group"
    fi
}

# Create basic moonraker.conf
create_moonraker_conf() {
    local conf_file="${PRINTER_DATA}/config/moonraker.conf"

    if [[ -f "$conf_file" ]]; then
        warn_msg "moonraker.conf already exists"
        return 0
    fi

    status_msg "Creating moonraker.conf..."
    cat > "$conf_file" << 'EOF'
# Moonraker Configuration
# Generated by gschpoozi

[server]
host: 0.0.0.0
port: 7125
klippy_uds_address: ~/printer_data/comms/klippy.sock

[authorization]
trusted_clients:
    10.0.0.0/8
    127.0.0.0/8
    169.254.0.0/16
    172.16.0.0/12
    192.168.0.0/16
    FE80::/10
    ::1/128
cors_domains:
    *.lan
    *.local
    *://localhost
    *://localhost:*
    *://my.mainsail.xyz
    *://app.fluidd.xyz

[octoprint_compat]

[history]

[file_manager]
enable_object_processing: True

[machine]
provider: systemd_dbus

# Update manager configuration
# Klipper and Moonraker are auto-detected
[update_manager]
refresh_interval: 168
enable_auto_refresh: True
EOF

    ok_msg "Created $conf_file"
    return 0
}

# Create basic printer.cfg if it doesn't exist
create_basic_printer_cfg() {
    local conf_file="${PRINTER_DATA}/config/printer.cfg"

    if [[ -f "$conf_file" ]]; then
        warn_msg "printer.cfg already exists"
        return 0
    fi

    status_msg "Creating basic printer.cfg..."
    cat > "$conf_file" << 'EOF'
# Klipper Configuration
# Generated by gschpoozi
#
# This is a placeholder configuration.
# Use the gschpoozi wizard to generate your full configuration.

[virtual_sdcard]
path: ~/printer_data/gcodes

[display_status]

[pause_resume]

# Add your MCU configuration below
# [mcu]
# serial: /dev/serial/by-id/usb-xxx
EOF

    ok_msg "Created basic $conf_file"
    return 0
}

# Add user to required groups
add_user_to_groups() {
    status_msg "Adding user to required groups..."

    local groups=("tty" "dialout")
    local needs_relogin=false

    for group in "${groups[@]}"; do
        if ! groups "$USER" | grep -q "\b${group}\b"; then
            sudo usermod -a -G "$group" "$USER"
            ok_msg "Added $USER to group: $group"
            needs_relogin=true
        else
            ok_msg "User already in group: $group"
        fi
    done

    if [[ "$needs_relogin" == "true" ]]; then
        warn_msg "You may need to log out and back in for group changes to take effect"
    fi

    return 0
}

# Get latest GitHub release download URL
get_latest_release_url() {
    local repo="$1"  # e.g., "mainsail-crew/mainsail"
    local asset_name="${2:-}"  # e.g., "mainsail.zip"

    local api_url="https://api.github.com/repos/${repo}/releases/latest"

    if [[ -n "$asset_name" ]]; then
        curl -s "$api_url" | grep "browser_download_url.*${asset_name}" | head -1 | cut -d '"' -f 4
    else
        curl -s "$api_url" | grep "browser_download_url.*\.zip" | head -1 | cut -d '"' -f 4
    fi
}

# Download and extract a release
download_and_extract() {
    local url="$1"
    local target_dir="$2"

    if [[ -z "$url" ]]; then
        error_msg "No download URL provided"
        return 1
    fi

    status_msg "Downloading from $url..."

    local temp_file=$(mktemp)
    curl -L -o "$temp_file" "$url"

    if [[ $? -ne 0 ]]; then
        error_msg "Download failed"
        rm -f "$temp_file"
        return 1
    fi

    # Create target directory
    mkdir -p "$target_dir"

    status_msg "Extracting to $target_dir..."
    unzip -o "$temp_file" -d "$target_dir"

    local result=$?
    rm -f "$temp_file"

    return $result
}

# Get the next available port for web UI
# Returns: port number (80 if nothing else is on 80, 81 otherwise)
get_webui_port() {
    local ui_name="$1"  # mainsail or fluidd
    local other_ui=""

    # Determine the other UI
    if [[ "$ui_name" == "mainsail" ]]; then
        other_ui="fluidd"
    else
        other_ui="mainsail"
    fi

    # Check if other UI is already configured
    if [[ -f "/etc/nginx/sites-enabled/${other_ui}" ]]; then
        # Check what port the other UI is using
        local other_port=$(grep -oP 'listen \K[0-9]+' "/etc/nginx/sites-available/${other_ui}" 2>/dev/null | head -1)
        if [[ "$other_port" == "80" ]]; then
            echo "81"
            return
        fi
    fi

    # Default to port 80
    echo "80"
}

# Check if a port is already in use by nginx
is_port_in_use() {
    local port="$1"
    grep -rq "listen ${port}" /etc/nginx/sites-enabled/ 2>/dev/null
}

# Setup nginx for web UI
# Now supports running Mainsail and Fluidd side by side on different ports
setup_nginx() {
    local ui_name="$1"  # mainsail or fluidd
    local port="${2:-}"  # optional port, auto-detect if not specified
    local template_file="${NGINX_TEMPLATES}/${ui_name}.conf"
    local common_vars="${NGINX_TEMPLATES}/common_vars.conf"

    if [[ ! -f "$template_file" ]]; then
        error_msg "Nginx template not found: $template_file"
        return 1
    fi

    # Auto-detect port if not specified
    if [[ -z "$port" ]]; then
        port=$(get_webui_port "$ui_name")
    fi

    # Determine if this should be default_server
    local default_server=""
    if [[ "$port" == "80" ]]; then
        default_server="default_server"
    fi

    status_msg "Configuring nginx for $ui_name on port $port..."

    # Install common_vars if not present
    if [[ ! -f "/etc/nginx/conf.d/common_vars.conf" ]]; then
        sudo cp "$common_vars" /etc/nginx/conf.d/
    fi

    # Create site config with placeholders replaced
    local temp_file=$(mktemp)
    sed -e "s|%HOME%|${HOME}|g" \
        -e "s|%PORT%|${port}|g" \
        -e "s|%DEFAULT_SERVER%|${default_server}|g" \
        "$template_file" > "$temp_file"

    # Remove default nginx site if exists
    if [[ -f "/etc/nginx/sites-enabled/default" ]]; then
        sudo rm /etc/nginx/sites-enabled/default
    fi

    # Install new site config
    sudo cp "$temp_file" "/etc/nginx/sites-available/${ui_name}"
    rm "$temp_file"

    # Enable site
    if [[ ! -L "/etc/nginx/sites-enabled/${ui_name}" ]]; then
        sudo ln -s "/etc/nginx/sites-available/${ui_name}" "/etc/nginx/sites-enabled/${ui_name}"
    fi

    # Test and restart nginx
    if sudo nginx -t; then
        sudo systemctl restart nginx
        ok_msg "Nginx configured for $ui_name on port $port"
        # Store the port for display purposes
        WEBUI_PORT="$port"
        return 0
    else
        error_msg "Nginx configuration test failed"
        return 1
    fi
}

# Add update manager entry to moonraker.conf
add_update_manager_entry() {
    local name="$1"
    local type="$2"
    local path="$3"
    local extra="${4:-}"

    local conf_file="${PRINTER_DATA}/config/moonraker.conf"

    if ! grep -q "\[update_manager ${name}\]" "$conf_file" 2>/dev/null; then
        status_msg "Adding update_manager entry for $name..."

        cat >> "$conf_file" << EOF

[update_manager ${name}]
type: ${type}
path: ${path}
${extra}
EOF
        ok_msg "Added update_manager entry for $name"
    else
        warn_msg "Update manager entry for $name already exists"
    fi
}

# ═══════════════════════════════════════════════════════════════════════════════
# MAIN INSTALLATION FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

# Install Klipper
do_install_klipper() {
    clear_screen
    print_header "Installing Klipper"

    echo -e "${BCYAN}${BOX_V}${NC}"
    echo -e "${BCYAN}${BOX_V}${NC}  This will install:"
    echo -e "${BCYAN}${BOX_V}${NC}  - Klipper 3D printer firmware"
    echo -e "${BCYAN}${BOX_V}${NC}  - Python virtual environment (klippy-env)"
    echo -e "${BCYAN}${BOX_V}${NC}  - Systemd service"
    echo -e "${BCYAN}${BOX_V}${NC}"
    print_footer

    if ! confirm "Proceed with Klipper installation?"; then
        return 1
    fi

    echo ""

    # Preflight checks
    check_not_root || return 1
    check_sudo_access || return 1

    # Install dependencies
    install_packages "${KLIPPER_DEPS[@]}" || return 1

    # Clone repository
    clone_repo "$KLIPPER_REPO" "$KLIPPER_DIR" || return 1

    # Create virtual environment
    create_virtualenv "$KLIPPY_ENV" || return 1

    # Install Python requirements
    install_pip_requirements "$KLIPPY_ENV" "${KLIPPER_DIR}/scripts/klippy-requirements.txt" || return 1

    # Create printer_data directories
    create_printer_data_dirs

    # Create environment file
    create_klipper_env

    # Create basic printer.cfg
    create_basic_printer_cfg

    # Create and enable service
    create_systemd_service "klipper" "${SERVICE_TEMPLATES}/klipper.service" || return 1
    enable_service "klipper"

    # Add user to groups
    add_user_to_groups

    echo ""
    echo -e "${GREEN}════════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}  Klipper installation complete!${NC}"
    echo -e "${GREEN}════════════════════════════════════════════════════════════${NC}"
    echo ""
    echo -e "  Config directory: ${CYAN}${PRINTER_DATA}/config${NC}"
    echo -e "  Log file: ${CYAN}${PRINTER_DATA}/logs/klippy.log${NC}"
    echo ""

    wait_for_key
    return 0
}

# Install Moonraker
do_install_moonraker() {
    clear_screen
    print_header "Installing Moonraker"

    echo -e "${BCYAN}${BOX_V}${NC}"
    echo -e "${BCYAN}${BOX_V}${NC}  This will install:"
    echo -e "${BCYAN}${BOX_V}${NC}  - Moonraker API server"
    echo -e "${BCYAN}${BOX_V}${NC}  - Python virtual environment (moonraker-env)"
    echo -e "${BCYAN}${BOX_V}${NC}  - Systemd service"
    echo -e "${BCYAN}${BOX_V}${NC}"

    if ! is_klipper_installed; then
        echo -e "${BCYAN}${BOX_V}${NC}  ${YELLOW}Warning: Klipper is not installed.${NC}"
        echo -e "${BCYAN}${BOX_V}${NC}  ${YELLOW}Moonraker requires Klipper to function.${NC}"
    fi
    echo -e "${BCYAN}${BOX_V}${NC}"
    print_footer

    if ! confirm "Proceed with Moonraker installation?"; then
        return 1
    fi

    echo ""

    # Preflight checks
    check_not_root || return 1
    check_sudo_access || return 1

    # Install dependencies
    install_packages "${MOONRAKER_DEPS[@]}" || return 1

    # Clone repository
    clone_repo "$MOONRAKER_REPO" "$MOONRAKER_DIR" || return 1

    # Create virtual environment
    create_virtualenv "$MOONRAKER_ENV" || return 1

    # Install Python requirements
    install_pip_requirements "$MOONRAKER_ENV" "${MOONRAKER_DIR}/scripts/moonraker-requirements.txt" || return 1

    # Ensure printer_data directories exist
    create_printer_data_dirs

    # Create moonraker-admin group (required for polkit permissions)
    create_moonraker_group

    # Create environment file
    create_moonraker_env

    # Create moonraker.conf
    create_moonraker_conf

    # Create and enable service
    create_systemd_service "moonraker" "${SERVICE_TEMPLATES}/moonraker.service" || return 1
    enable_service "moonraker"

    echo ""
    echo -e "${GREEN}════════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}  Moonraker installation complete!${NC}"
    echo -e "${GREEN}════════════════════════════════════════════════════════════${NC}"
    echo ""
    echo -e "  API available at: ${CYAN}http://$(hostname -I | awk '{print $1}'):7125${NC}"
    echo -e "  Config file: ${CYAN}${PRINTER_DATA}/config/moonraker.conf${NC}"
    echo ""

    wait_for_key
    return 0
}

# Install Mainsail
do_install_mainsail() {
    clear_screen
    print_header "Installing Mainsail"

    # Determine which port will be used
    local port=$(get_webui_port "mainsail")

    echo -e "${BCYAN}${BOX_V}${NC}"
    echo -e "${BCYAN}${BOX_V}${NC}  This will install:"
    echo -e "${BCYAN}${BOX_V}${NC}  - Mainsail web interface"
    echo -e "${BCYAN}${BOX_V}${NC}  - Nginx web server"
    echo -e "${BCYAN}${BOX_V}${NC}"

    if ! is_moonraker_installed; then
        echo -e "${BCYAN}${BOX_V}${NC}  ${YELLOW}Warning: Moonraker is not installed.${NC}"
        echo -e "${BCYAN}${BOX_V}${NC}  ${YELLOW}Mainsail requires Moonraker to function.${NC}"
    fi

    if is_fluidd_installed; then
        echo -e "${BCYAN}${BOX_V}${NC}  ${GREEN}Note: Fluidd is already installed on port 80.${NC}"
        echo -e "${BCYAN}${BOX_V}${NC}  ${GREEN}Mainsail will be installed on port ${port} (side-by-side).${NC}"
    else
        echo -e "${BCYAN}${BOX_V}${NC}  Will be available on port ${CYAN}${port}${NC}"
    fi
    echo -e "${BCYAN}${BOX_V}${NC}"
    print_footer

    if ! confirm "Proceed with Mainsail installation?"; then
        return 1
    fi

    echo ""

    # Preflight checks
    check_not_root || return 1
    check_sudo_access || return 1

    # Install nginx
    install_packages "${WEBUI_DEPS[@]}" || return 1

    # Also need unzip for extraction
    install_packages "unzip" || return 1

    # Get latest release URL
    status_msg "Fetching latest Mainsail release..."
    local download_url=$(get_latest_release_url "mainsail-crew/mainsail" "mainsail.zip")

    if [[ -z "$download_url" ]]; then
        error_msg "Could not find Mainsail release"
        wait_for_key
        return 1
    fi

    # Download and extract
    download_and_extract "$download_url" "$MAINSAIL_DIR" || return 1

    # Setup nginx with auto-detected port
    setup_nginx "mainsail" "$port" || return 1

    # Add update manager entry
    if is_moonraker_installed; then
        add_update_manager_entry "mainsail" "web" "${MAINSAIL_DIR}" "repo: mainsail-crew/mainsail"
    fi

    # Build access URL
    local ip_addr=$(hostname -I | awk '{print $1}')
    local access_url="http://${ip_addr}"
    if [[ "$port" != "80" ]]; then
        access_url="${access_url}:${port}"
    fi

    echo ""
    echo -e "${GREEN}════════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}  Mainsail installation complete!${NC}"
    echo -e "${GREEN}════════════════════════════════════════════════════════════${NC}"
    echo ""
    echo -e "  Access at: ${CYAN}${access_url}${NC}"
    if is_fluidd_installed; then
        echo -e "  (Fluidd is on port 80, Mainsail is on port ${port})"
    fi
    echo ""

    wait_for_key
    return 0
}

# Install Fluidd
do_install_fluidd() {
    clear_screen
    print_header "Installing Fluidd"

    # Determine which port will be used
    local port=$(get_webui_port "fluidd")

    echo -e "${BCYAN}${BOX_V}${NC}"
    echo -e "${BCYAN}${BOX_V}${NC}  This will install:"
    echo -e "${BCYAN}${BOX_V}${NC}  - Fluidd web interface"
    echo -e "${BCYAN}${BOX_V}${NC}  - Nginx web server"
    echo -e "${BCYAN}${BOX_V}${NC}"

    if ! is_moonraker_installed; then
        echo -e "${BCYAN}${BOX_V}${NC}  ${YELLOW}Warning: Moonraker is not installed.${NC}"
        echo -e "${BCYAN}${BOX_V}${NC}  ${YELLOW}Fluidd requires Moonraker to function.${NC}"
    fi

    if is_mainsail_installed; then
        echo -e "${BCYAN}${BOX_V}${NC}  ${GREEN}Note: Mainsail is already installed on port 80.${NC}"
        echo -e "${BCYAN}${BOX_V}${NC}  ${GREEN}Fluidd will be installed on port ${port} (side-by-side).${NC}"
    else
        echo -e "${BCYAN}${BOX_V}${NC}  Will be available on port ${CYAN}${port}${NC}"
    fi
    echo -e "${BCYAN}${BOX_V}${NC}"
    print_footer

    if ! confirm "Proceed with Fluidd installation?"; then
        return 1
    fi

    echo ""

    # Preflight checks
    check_not_root || return 1
    check_sudo_access || return 1

    # Install nginx
    install_packages "${WEBUI_DEPS[@]}" || return 1

    # Also need unzip for extraction
    install_packages "unzip" || return 1

    # Get latest release URL
    status_msg "Fetching latest Fluidd release..."
    local download_url=$(get_latest_release_url "fluidd-core/fluidd" "fluidd.zip")

    if [[ -z "$download_url" ]]; then
        error_msg "Could not find Fluidd release"
        wait_for_key
        return 1
    fi

    # Download and extract
    download_and_extract "$download_url" "$FLUIDD_DIR" || return 1

    # Setup nginx with auto-detected port
    setup_nginx "fluidd" "$port" || return 1

    # Add update manager entry
    if is_moonraker_installed; then
        add_update_manager_entry "fluidd" "web" "${FLUIDD_DIR}" "repo: fluidd-core/fluidd"
    fi

    # Build access URL
    local ip_addr=$(hostname -I | awk '{print $1}')
    local access_url="http://${ip_addr}"
    if [[ "$port" != "80" ]]; then
        access_url="${access_url}:${port}"
    fi

    echo ""
    echo -e "${GREEN}════════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}  Fluidd installation complete!${NC}"
    echo -e "${GREEN}════════════════════════════════════════════════════════════${NC}"
    echo ""
    echo -e "  Access at: ${CYAN}${access_url}${NC}"
    if is_mainsail_installed; then
        echo -e "  (Mainsail is on port 80, Fluidd is on port ${port})"
    fi
    echo ""

    wait_for_key
    return 0
}

# Install Crowsnest
do_install_crowsnest() {
    clear_screen
    print_header "Installing Crowsnest"

    echo -e "${BCYAN}${BOX_V}${NC}"
    echo -e "${BCYAN}${BOX_V}${NC}  This will install:"
    echo -e "${BCYAN}${BOX_V}${NC}  - Crowsnest webcam streamer"
    echo -e "${BCYAN}${BOX_V}${NC}  - Camera streaming support for Mainsail/Fluidd"
    echo -e "${BCYAN}${BOX_V}${NC}"
    print_footer

    if ! confirm "Proceed with Crowsnest installation?"; then
        return 1
    fi

    echo ""

    # Preflight checks
    check_not_root || return 1
    check_sudo_access || return 1

    # Clone repository
    clone_repo "$CROWSNEST_REPO" "$CROWSNEST_DIR" || return 1

    # Run Crowsnest's own installer
    status_msg "Running Crowsnest installer..."
    cd "$CROWSNEST_DIR"

    if [[ -f "tools/install.sh" ]]; then
        # Run in non-interactive mode
        sudo make install
    else
        error_msg "Crowsnest installer not found"
        wait_for_key
        return 1
    fi

    # Add update manager entry
    if is_moonraker_installed; then
        add_update_manager_entry "crowsnest" "git_repo" "${CROWSNEST_DIR}" "origin: https://github.com/mainsail-crew/crowsnest.git
managed_services: crowsnest"
    fi

    echo ""
    echo -e "${GREEN}════════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}  Crowsnest installation complete!${NC}"
    echo -e "${GREEN}════════════════════════════════════════════════════════════${NC}"
    echo ""
    echo -e "  Config file: ${CYAN}${PRINTER_DATA}/config/crowsnest.conf${NC}"
    echo -e "  Edit this file to configure your webcam(s)"
    echo ""

    wait_for_key
    return 0
}

# Install Sonar
do_install_sonar() {
    clear_screen
    print_header "Installing Sonar"

    echo -e "${BCYAN}${BOX_V}${NC}"
    echo -e "${BCYAN}${BOX_V}${NC}  This will install:"
    echo -e "${BCYAN}${BOX_V}${NC}  - Sonar network keepalive service"
    echo -e "${BCYAN}${BOX_V}${NC}  - Prevents WiFi from sleeping during prints"
    echo -e "${BCYAN}${BOX_V}${NC}"
    print_footer

    if ! confirm "Proceed with Sonar installation?"; then
        return 1
    fi

    echo ""

    # Preflight checks
    check_not_root || return 1
    check_sudo_access || return 1

    # Clone repository
    clone_repo "$SONAR_REPO" "$SONAR_DIR" || return 1

    # Run Sonar's own installer
    status_msg "Running Sonar installer..."
    cd "$SONAR_DIR"

    if [[ -f "tools/install.sh" ]]; then
        # Run installer
        bash tools/install.sh
    else
        error_msg "Sonar installer not found"
        wait_for_key
        return 1
    fi

    # Add update manager entry
    if is_moonraker_installed; then
        add_update_manager_entry "sonar" "git_repo" "${SONAR_DIR}" "origin: https://github.com/mainsail-crew/sonar.git
managed_services: sonar"
    fi

    echo ""
    echo -e "${GREEN}════════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}  Sonar installation complete!${NC}"
    echo -e "${GREEN}════════════════════════════════════════════════════════════${NC}"
    echo ""
    echo -e "  Config file: ${CYAN}${PRINTER_DATA}/config/sonar.conf${NC}"
    echo ""

    wait_for_key
    return 0
}

# Install Moonraker Timelapse
do_install_timelapse() {
    clear_screen
    print_header "Installing Moonraker Timelapse"

    echo -e "${BCYAN}${BOX_V}${NC}"
    echo -e "${BCYAN}${BOX_V}${NC}  This will install:"
    echo -e "${BCYAN}${BOX_V}${NC}  - Moonraker Timelapse for print recordings"
    echo -e "${BCYAN}${BOX_V}${NC}  - Proper symlink-based installation"
    echo -e "${BCYAN}${BOX_V}${NC}"

    if ! is_moonraker_installed; then
        echo -e "${BCYAN}${BOX_V}${NC}  ${RED}Error: Moonraker is not installed!${NC}"
        echo -e "${BCYAN}${BOX_V}${NC}  ${RED}Timelapse requires Moonraker.${NC}"
        print_footer
        wait_for_key
        return 1
    fi

    # Check for incorrectly installed timelapse
    if [[ -f "${MOONRAKER_DIR}/moonraker/components/timelapse.py" ]] && [[ ! -L "${MOONRAKER_DIR}/moonraker/components/timelapse.py" ]]; then
        echo -e "${BCYAN}${BOX_V}${NC}  ${YELLOW}Warning: Found incorrectly installed timelapse.py${NC}"
        echo -e "${BCYAN}${BOX_V}${NC}  ${YELLOW}This will be removed and replaced with proper symlink.${NC}"
    fi
    echo -e "${BCYAN}${BOX_V}${NC}"
    print_footer

    if ! confirm "Proceed with Timelapse installation?"; then
        return 1
    fi

    echo ""

    # Preflight checks
    check_not_root || return 1
    check_sudo_access || return 1

    # Install ffmpeg dependency
    install_packages "ffmpeg" || return 1

    # Remove incorrectly installed timelapse if present
    if [[ -f "${MOONRAKER_DIR}/moonraker/components/timelapse.py" ]] && [[ ! -L "${MOONRAKER_DIR}/moonraker/components/timelapse.py" ]]; then
        status_msg "Removing incorrectly installed timelapse.py..."
        rm -f "${MOONRAKER_DIR}/moonraker/components/timelapse.py"
    fi

    # Clone repository
    clone_repo "$TIMELAPSE_REPO" "$TIMELAPSE_DIR" || return 1

    # Create symlink for the component
    status_msg "Creating symlink for timelapse component..."
    ln -sf "${TIMELAPSE_DIR}/component/timelapse.py" "${MOONRAKER_DIR}/moonraker/components/timelapse.py"

    # Create timelapse macro file if it doesn't exist
    local macro_file="${PRINTER_DATA}/config/timelapse.cfg"
    if [[ ! -f "$macro_file" ]]; then
        status_msg "Creating timelapse.cfg..."
        cp "${TIMELAPSE_DIR}/klipper_macro/timelapse.cfg" "$macro_file"
    fi

    # Add update manager entry
    add_update_manager_entry "timelapse" "git_repo" "${TIMELAPSE_DIR}" "origin: https://github.com/mainsail-crew/moonraker-timelapse.git
primary_branch: main"

    # Add timelapse config to moonraker.conf if not present
    local moonraker_conf="${PRINTER_DATA}/config/moonraker.conf"
    if ! grep -q "\[timelapse\]" "$moonraker_conf" 2>/dev/null; then
        status_msg "Adding timelapse config to moonraker.conf..."
        cat >> "$moonraker_conf" << 'EOF'

[timelapse]
output_path: ~/printer_data/timelapse/
frame_path: ~/printer_data/timelapse/frames/
EOF
    fi

    # Create timelapse directories
    mkdir -p "${PRINTER_DATA}/timelapse/frames"

    # Restart Moonraker to load the component
    status_msg "Restarting Moonraker..."
    sudo systemctl restart moonraker

    echo ""
    echo -e "${GREEN}════════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}  Moonraker Timelapse installation complete!${NC}"
    echo -e "${GREEN}════════════════════════════════════════════════════════════${NC}"
    echo ""
    echo -e "  ${WHITE}Add to your printer.cfg:${NC}"
    echo -e "  ${CYAN}[include timelapse.cfg]${NC}"
    echo ""
    echo -e "  Output directory: ${CYAN}${PRINTER_DATA}/timelapse/${NC}"
    echo ""

    wait_for_key
    return 0
}

# ═══════════════════════════════════════════════════════════════════════════════
# UPDATE FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

# Update Klipper
do_update_klipper() {
    clear_screen
    print_header "Update Klipper"

    if ! is_klipper_installed; then
        echo -e "${BCYAN}${BOX_V}${NC}  ${RED}Klipper is not installed!${NC}"
        print_footer
        wait_for_key
        return 1
    fi

    echo -e "${BCYAN}${BOX_V}${NC}"
    echo -e "${BCYAN}${BOX_V}${NC}  This will update Klipper to the latest version."
    echo -e "${BCYAN}${BOX_V}${NC}"
    print_footer

    if ! confirm "Proceed with Klipper update?"; then
        return 1
    fi

    echo ""

    # Stop service
    status_msg "Stopping Klipper service..."
    sudo systemctl stop klipper

    # Update repository
    status_msg "Pulling latest changes..."
    cd "$KLIPPER_DIR"
    git pull

    # Update Python requirements
    status_msg "Updating Python dependencies..."
    "${KLIPPY_ENV}/bin/pip" install -r "${KLIPPER_DIR}/scripts/klippy-requirements.txt"

    # Restart service
    status_msg "Starting Klipper service..."
    sudo systemctl start klipper

    echo ""
    ok_msg "Klipper updated successfully!"
    echo -e "  New version: ${CYAN}$(get_klipper_version)${NC}"
    echo ""

    wait_for_key
    return 0
}

# Update Moonraker
do_update_moonraker() {
    clear_screen
    print_header "Update Moonraker"

    if ! is_moonraker_installed; then
        echo -e "${BCYAN}${BOX_V}${NC}  ${RED}Moonraker is not installed!${NC}"
        print_footer
        wait_for_key
        return 1
    fi

    echo -e "${BCYAN}${BOX_V}${NC}"
    echo -e "${BCYAN}${BOX_V}${NC}  This will update Moonraker to the latest version."
    echo -e "${BCYAN}${BOX_V}${NC}"
    print_footer

    if ! confirm "Proceed with Moonraker update?"; then
        return 1
    fi

    echo ""

    # Stop service
    status_msg "Stopping Moonraker service..."
    sudo systemctl stop moonraker

    # Update repository
    status_msg "Pulling latest changes..."
    cd "$MOONRAKER_DIR"
    git pull

    # Update Python requirements
    status_msg "Updating Python dependencies..."
    "${MOONRAKER_ENV}/bin/pip" install -r "${MOONRAKER_DIR}/scripts/moonraker-requirements.txt"

    # Restart service
    status_msg "Starting Moonraker service..."
    sudo systemctl start moonraker

    echo ""
    ok_msg "Moonraker updated successfully!"
    echo -e "  New version: ${CYAN}$(get_moonraker_version)${NC}"
    echo ""

    wait_for_key
    return 0
}

# Update Mainsail
do_update_mainsail() {
    clear_screen
    print_header "Update Mainsail"

    if ! is_mainsail_installed; then
        echo -e "${BCYAN}${BOX_V}${NC}  ${RED}Mainsail is not installed!${NC}"
        print_footer
        wait_for_key
        return 1
    fi

    echo -e "${BCYAN}${BOX_V}${NC}"
    echo -e "${BCYAN}${BOX_V}${NC}  This will update Mainsail to the latest version."
    echo -e "${BCYAN}${BOX_V}${NC}"
    print_footer

    if ! confirm "Proceed with Mainsail update?"; then
        return 1
    fi

    echo ""

    # Get latest release URL
    status_msg "Fetching latest Mainsail release..."
    local download_url=$(get_latest_release_url "mainsail-crew/mainsail" "mainsail.zip")

    if [[ -z "$download_url" ]]; then
        error_msg "Could not find Mainsail release"
        wait_for_key
        return 1
    fi

    # Backup current version
    status_msg "Backing up current version..."
    rm -rf "${MAINSAIL_DIR}.bak"
    mv "$MAINSAIL_DIR" "${MAINSAIL_DIR}.bak"

    # Download and extract new version
    download_and_extract "$download_url" "$MAINSAIL_DIR"

    if [[ $? -eq 0 ]]; then
        rm -rf "${MAINSAIL_DIR}.bak"
        ok_msg "Mainsail updated successfully!"
    else
        error_msg "Update failed, restoring backup..."
        rm -rf "$MAINSAIL_DIR"
        mv "${MAINSAIL_DIR}.bak" "$MAINSAIL_DIR"
    fi

    echo ""
    wait_for_key
    return 0
}

# Update Fluidd
do_update_fluidd() {
    clear_screen
    print_header "Update Fluidd"

    if ! is_fluidd_installed; then
        echo -e "${BCYAN}${BOX_V}${NC}  ${RED}Fluidd is not installed!${NC}"
        print_footer
        wait_for_key
        return 1
    fi

    echo -e "${BCYAN}${BOX_V}${NC}"
    echo -e "${BCYAN}${BOX_V}${NC}  This will update Fluidd to the latest version."
    echo -e "${BCYAN}${BOX_V}${NC}"
    print_footer

    if ! confirm "Proceed with Fluidd update?"; then
        return 1
    fi

    echo ""

    # Get latest release URL
    status_msg "Fetching latest Fluidd release..."
    local download_url=$(get_latest_release_url "fluidd-core/fluidd" "fluidd.zip")

    if [[ -z "$download_url" ]]; then
        error_msg "Could not find Fluidd release"
        wait_for_key
        return 1
    fi

    # Backup current version
    status_msg "Backing up current version..."
    rm -rf "${FLUIDD_DIR}.bak"
    mv "$FLUIDD_DIR" "${FLUIDD_DIR}.bak"

    # Download and extract new version
    download_and_extract "$download_url" "$FLUIDD_DIR"

    if [[ $? -eq 0 ]]; then
        rm -rf "${FLUIDD_DIR}.bak"
        ok_msg "Fluidd updated successfully!"
    else
        error_msg "Update failed, restoring backup..."
        rm -rf "$FLUIDD_DIR"
        mv "${FLUIDD_DIR}.bak" "$FLUIDD_DIR"
    fi

    echo ""
    wait_for_key
    return 0
}

# Update Crowsnest
do_update_crowsnest() {
    clear_screen
    print_header "Update Crowsnest"

    if ! is_crowsnest_installed; then
        echo -e "${BCYAN}${BOX_V}${NC}  ${RED}Crowsnest is not installed!${NC}"
        print_footer
        wait_for_key
        return 1
    fi

    echo -e "${BCYAN}${BOX_V}${NC}"
    echo -e "${BCYAN}${BOX_V}${NC}  This will update Crowsnest to the latest version."
    echo -e "${BCYAN}${BOX_V}${NC}"
    print_footer

    if ! confirm "Proceed with Crowsnest update?"; then
        return 1
    fi

    echo ""

    # Stop service
    status_msg "Stopping Crowsnest service..."
    sudo systemctl stop crowsnest 2>/dev/null || true

    # Update repository
    status_msg "Pulling latest changes..."
    cd "$CROWSNEST_DIR"
    git pull

    # Run update if available
    if [[ -f "tools/update.sh" ]]; then
        bash tools/update.sh
    fi

    # Restart service
    status_msg "Starting Crowsnest service..."
    sudo systemctl start crowsnest 2>/dev/null || true

    echo ""
    ok_msg "Crowsnest updated successfully!"
    echo ""

    wait_for_key
    return 0
}

# Update Sonar
do_update_sonar() {
    clear_screen
    print_header "Update Sonar"

    if ! is_sonar_installed; then
        echo -e "${BCYAN}${BOX_V}${NC}  ${RED}Sonar is not installed!${NC}"
        print_footer
        wait_for_key
        return 1
    fi

    echo -e "${BCYAN}${BOX_V}${NC}"
    echo -e "${BCYAN}${BOX_V}${NC}  This will update Sonar to the latest version."
    echo -e "${BCYAN}${BOX_V}${NC}"
    print_footer

    if ! confirm "Proceed with Sonar update?"; then
        return 1
    fi

    echo ""

    # Stop service
    status_msg "Stopping Sonar service..."
    sudo systemctl stop sonar 2>/dev/null || true

    # Update repository
    status_msg "Pulling latest changes..."
    cd "$SONAR_DIR"
    git pull

    # Restart service
    status_msg "Starting Sonar service..."
    sudo systemctl start sonar 2>/dev/null || true

    echo ""
    ok_msg "Sonar updated successfully!"
    echo ""

    wait_for_key
    return 0
}

# Update Timelapse
do_update_timelapse() {
    clear_screen
    print_header "Update Moonraker Timelapse"

    if ! is_timelapse_installed; then
        echo -e "${BCYAN}${BOX_V}${NC}  ${RED}Timelapse is not installed!${NC}"
        print_footer
        wait_for_key
        return 1
    fi

    echo -e "${BCYAN}${BOX_V}${NC}"
    echo -e "${BCYAN}${BOX_V}${NC}  This will update Timelapse to the latest version."
    echo -e "${BCYAN}${BOX_V}${NC}"
    print_footer

    if ! confirm "Proceed with Timelapse update?"; then
        return 1
    fi

    echo ""

    # Update repository
    status_msg "Pulling latest changes..."
    cd "$TIMELAPSE_DIR"
    git pull

    # Restart Moonraker to reload the component
    status_msg "Restarting Moonraker..."
    sudo systemctl restart moonraker

    echo ""
    ok_msg "Timelapse updated successfully!"
    echo ""

    wait_for_key
    return 0
}

# Update all components
do_update_all() {
    clear_screen
    print_header "Update All Components"

    echo -e "${BCYAN}${BOX_V}${NC}"
    echo -e "${BCYAN}${BOX_V}${NC}  This will update all installed components:"
    is_klipper_installed && echo -e "${BCYAN}${BOX_V}${NC}  - Klipper"
    is_moonraker_installed && echo -e "${BCYAN}${BOX_V}${NC}  - Moonraker"
    is_mainsail_installed && echo -e "${BCYAN}${BOX_V}${NC}  - Mainsail"
    is_fluidd_installed && echo -e "${BCYAN}${BOX_V}${NC}  - Fluidd"
    is_crowsnest_installed && echo -e "${BCYAN}${BOX_V}${NC}  - Crowsnest"
    is_sonar_installed && echo -e "${BCYAN}${BOX_V}${NC}  - Sonar"
    is_timelapse_installed && echo -e "${BCYAN}${BOX_V}${NC}  - Timelapse"
    echo -e "${BCYAN}${BOX_V}${NC}"
    print_footer

    if ! confirm "Proceed with updating all components?"; then
        return 1
    fi

    echo ""

    local errors=0

    if is_klipper_installed; then
        echo -e "\n${BWHITE}=== Updating Klipper ===${NC}"
        sudo systemctl stop klipper
        cd "$KLIPPER_DIR" && git pull
        "${KLIPPY_ENV}/bin/pip" install -r "${KLIPPER_DIR}/scripts/klippy-requirements.txt"
        sudo systemctl start klipper
        ok_msg "Klipper updated"
    fi

    if is_moonraker_installed; then
        echo -e "\n${BWHITE}=== Updating Moonraker ===${NC}"
        sudo systemctl stop moonraker
        cd "$MOONRAKER_DIR" && git pull
        "${MOONRAKER_ENV}/bin/pip" install -r "${MOONRAKER_DIR}/scripts/moonraker-requirements.txt"
        sudo systemctl start moonraker
        ok_msg "Moonraker updated"
    fi

    if is_mainsail_installed; then
        echo -e "\n${BWHITE}=== Updating Mainsail ===${NC}"
        local url=$(get_latest_release_url "mainsail-crew/mainsail" "mainsail.zip")
        if [[ -n "$url" ]]; then
            rm -rf "${MAINSAIL_DIR}.bak"
            mv "$MAINSAIL_DIR" "${MAINSAIL_DIR}.bak"
            download_and_extract "$url" "$MAINSAIL_DIR" && rm -rf "${MAINSAIL_DIR}.bak"
            ok_msg "Mainsail updated"
        fi
    fi

    if is_fluidd_installed; then
        echo -e "\n${BWHITE}=== Updating Fluidd ===${NC}"
        local url=$(get_latest_release_url "fluidd-core/fluidd" "fluidd.zip")
        if [[ -n "$url" ]]; then
            rm -rf "${FLUIDD_DIR}.bak"
            mv "$FLUIDD_DIR" "${FLUIDD_DIR}.bak"
            download_and_extract "$url" "$FLUIDD_DIR" && rm -rf "${FLUIDD_DIR}.bak"
            ok_msg "Fluidd updated"
        fi
    fi

    if is_crowsnest_installed; then
        echo -e "\n${BWHITE}=== Updating Crowsnest ===${NC}"
        sudo systemctl stop crowsnest 2>/dev/null || true
        cd "$CROWSNEST_DIR" && git pull
        sudo systemctl start crowsnest 2>/dev/null || true
        ok_msg "Crowsnest updated"
    fi

    if is_sonar_installed; then
        echo -e "\n${BWHITE}=== Updating Sonar ===${NC}"
        sudo systemctl stop sonar 2>/dev/null || true
        cd "$SONAR_DIR" && git pull
        sudo systemctl start sonar 2>/dev/null || true
        ok_msg "Sonar updated"
    fi

    if is_timelapse_installed; then
        echo -e "\n${BWHITE}=== Updating Timelapse ===${NC}"
        cd "$TIMELAPSE_DIR" && git pull
        sudo systemctl restart moonraker
        ok_msg "Timelapse updated"
    fi

    echo ""
    echo -e "${GREEN}════════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}  All components updated!${NC}"
    echo -e "${GREEN}════════════════════════════════════════════════════════════${NC}"
    echo ""

    wait_for_key
    return 0
}

# ═══════════════════════════════════════════════════════════════════════════════
# REMOVE FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

# Remove Klipper
do_remove_klipper() {
    clear_screen
    print_header "Remove Klipper"

    if ! is_klipper_installed; then
        echo -e "${BCYAN}${BOX_V}${NC}  ${YELLOW}Klipper is not installed.${NC}"
        print_footer
        wait_for_key
        return 1
    fi

    echo -e "${BCYAN}${BOX_V}${NC}"
    echo -e "${BCYAN}${BOX_V}${NC}  ${RED}WARNING: This will remove:${NC}"
    echo -e "${BCYAN}${BOX_V}${NC}  - Klipper installation (~/klipper)"
    echo -e "${BCYAN}${BOX_V}${NC}  - Python environment (~/klippy-env)"
    echo -e "${BCYAN}${BOX_V}${NC}  - Systemd service"
    echo -e "${BCYAN}${BOX_V}${NC}"
    echo -e "${BCYAN}${BOX_V}${NC}  ${WHITE}Your config files in ~/printer_data will be preserved.${NC}"
    echo -e "${BCYAN}${BOX_V}${NC}"
    print_footer

    if ! confirm "Are you sure you want to remove Klipper?"; then
        return 1
    fi

    # Double confirm for destructive action
    echo -e "\n${RED}This action cannot be undone!${NC}"
    if ! confirm "Type 'yes' to confirm removal"; then
        return 1
    fi

    echo ""

    # Stop and disable service
    status_msg "Stopping and disabling Klipper service..."
    sudo systemctl stop klipper 2>/dev/null || true
    sudo systemctl disable klipper 2>/dev/null || true
    sudo rm -f "${SYSTEMD_DIR}/klipper.service"
    sudo systemctl daemon-reload

    # Remove directories
    status_msg "Removing Klipper files..."
    rm -rf "$KLIPPER_DIR"
    rm -rf "$KLIPPY_ENV"

    # Remove environment file (but keep printer_data structure)
    rm -f "${PRINTER_DATA}/systemd/klipper.env"

    echo ""
    ok_msg "Klipper has been removed."
    echo -e "  ${WHITE}Your config files in ~/printer_data have been preserved.${NC}"
    echo ""

    wait_for_key
    return 0
}

# Remove Moonraker
do_remove_moonraker() {
    clear_screen
    print_header "Remove Moonraker"

    if ! is_moonraker_installed; then
        echo -e "${BCYAN}${BOX_V}${NC}  ${YELLOW}Moonraker is not installed.${NC}"
        print_footer
        wait_for_key
        return 1
    fi

    echo -e "${BCYAN}${BOX_V}${NC}"
    echo -e "${BCYAN}${BOX_V}${NC}  ${RED}WARNING: This will remove:${NC}"
    echo -e "${BCYAN}${BOX_V}${NC}  - Moonraker installation (~/moonraker)"
    echo -e "${BCYAN}${BOX_V}${NC}  - Python environment (~/moonraker-env)"
    echo -e "${BCYAN}${BOX_V}${NC}  - Systemd service"
    echo -e "${BCYAN}${BOX_V}${NC}"
    echo -e "${BCYAN}${BOX_V}${NC}  ${YELLOW}Web interfaces (Mainsail/Fluidd) will stop working!${NC}"
    echo -e "${BCYAN}${BOX_V}${NC}"
    print_footer

    if ! confirm "Are you sure you want to remove Moonraker?"; then
        return 1
    fi

    echo ""

    # Stop and disable service
    status_msg "Stopping and disabling Moonraker service..."
    sudo systemctl stop moonraker 2>/dev/null || true
    sudo systemctl disable moonraker 2>/dev/null || true
    sudo rm -f "${SYSTEMD_DIR}/moonraker.service"
    sudo systemctl daemon-reload

    # Remove directories
    status_msg "Removing Moonraker files..."
    rm -rf "$MOONRAKER_DIR"
    rm -rf "$MOONRAKER_ENV"

    # Remove environment file
    rm -f "${PRINTER_DATA}/systemd/moonraker.env"

    echo ""
    ok_msg "Moonraker has been removed."
    echo ""

    wait_for_key
    return 0
}

# Remove Mainsail
do_remove_mainsail() {
    clear_screen
    print_header "Remove Mainsail"

    if ! is_mainsail_installed; then
        echo -e "${BCYAN}${BOX_V}${NC}  ${YELLOW}Mainsail is not installed.${NC}"
        print_footer
        wait_for_key
        return 1
    fi

    echo -e "${BCYAN}${BOX_V}${NC}"
    echo -e "${BCYAN}${BOX_V}${NC}  This will remove:"
    echo -e "${BCYAN}${BOX_V}${NC}  - Mainsail web interface (~/mainsail)"
    echo -e "${BCYAN}${BOX_V}${NC}  - Nginx configuration"
    echo -e "${BCYAN}${BOX_V}${NC}"
    print_footer

    if ! confirm "Are you sure you want to remove Mainsail?"; then
        return 1
    fi

    echo ""

    # Remove nginx config
    status_msg "Removing nginx configuration..."
    sudo rm -f "/etc/nginx/sites-enabled/mainsail"
    sudo rm -f "/etc/nginx/sites-available/mainsail"
    sudo systemctl restart nginx 2>/dev/null || true

    # Remove directory
    status_msg "Removing Mainsail files..."
    rm -rf "$MAINSAIL_DIR"

    # Remove update manager entry from moonraker.conf if present
    if [[ -f "${PRINTER_DATA}/config/moonraker.conf" ]]; then
        sed -i '/\[update_manager mainsail\]/,/^$/d' "${PRINTER_DATA}/config/moonraker.conf" 2>/dev/null || true
    fi

    echo ""
    ok_msg "Mainsail has been removed."
    echo ""

    wait_for_key
    return 0
}

# Remove Fluidd
do_remove_fluidd() {
    clear_screen
    print_header "Remove Fluidd"

    if ! is_fluidd_installed; then
        echo -e "${BCYAN}${BOX_V}${NC}  ${YELLOW}Fluidd is not installed.${NC}"
        print_footer
        wait_for_key
        return 1
    fi

    echo -e "${BCYAN}${BOX_V}${NC}"
    echo -e "${BCYAN}${BOX_V}${NC}  This will remove:"
    echo -e "${BCYAN}${BOX_V}${NC}  - Fluidd web interface (~/fluidd)"
    echo -e "${BCYAN}${BOX_V}${NC}  - Nginx configuration"
    echo -e "${BCYAN}${BOX_V}${NC}"
    print_footer

    if ! confirm "Are you sure you want to remove Fluidd?"; then
        return 1
    fi

    echo ""

    # Remove nginx config
    status_msg "Removing nginx configuration..."
    sudo rm -f "/etc/nginx/sites-enabled/fluidd"
    sudo rm -f "/etc/nginx/sites-available/fluidd"
    sudo systemctl restart nginx 2>/dev/null || true

    # Remove directory
    status_msg "Removing Fluidd files..."
    rm -rf "$FLUIDD_DIR"

    # Remove update manager entry from moonraker.conf if present
    if [[ -f "${PRINTER_DATA}/config/moonraker.conf" ]]; then
        sed -i '/\[update_manager fluidd\]/,/^$/d' "${PRINTER_DATA}/config/moonraker.conf" 2>/dev/null || true
    fi

    echo ""
    ok_msg "Fluidd has been removed."
    echo ""

    wait_for_key
    return 0
}

# Remove Crowsnest
do_remove_crowsnest() {
    clear_screen
    print_header "Remove Crowsnest"

    if ! is_crowsnest_installed; then
        echo -e "${BCYAN}${BOX_V}${NC}  ${YELLOW}Crowsnest is not installed.${NC}"
        print_footer
        wait_for_key
        return 1
    fi

    echo -e "${BCYAN}${BOX_V}${NC}"
    echo -e "${BCYAN}${BOX_V}${NC}  This will remove:"
    echo -e "${BCYAN}${BOX_V}${NC}  - Crowsnest webcam streamer (~/crowsnest)"
    echo -e "${BCYAN}${BOX_V}${NC}  - Systemd service"
    echo -e "${BCYAN}${BOX_V}${NC}"
    print_footer

    if ! confirm "Are you sure you want to remove Crowsnest?"; then
        return 1
    fi

    echo ""

    # Use Crowsnest's uninstaller if available
    if [[ -f "${CROWSNEST_DIR}/tools/uninstall.sh" ]]; then
        status_msg "Running Crowsnest uninstaller..."
        cd "$CROWSNEST_DIR"
        bash tools/uninstall.sh
    else
        # Manual removal
        status_msg "Stopping and disabling Crowsnest service..."
        sudo systemctl stop crowsnest 2>/dev/null || true
        sudo systemctl disable crowsnest 2>/dev/null || true
        sudo rm -f "${SYSTEMD_DIR}/crowsnest.service"
        sudo systemctl daemon-reload

        status_msg "Removing Crowsnest files..."
        rm -rf "$CROWSNEST_DIR"
    fi

    # Remove update manager entry
    if [[ -f "${PRINTER_DATA}/config/moonraker.conf" ]]; then
        sed -i '/\[update_manager crowsnest\]/,/^$/d' "${PRINTER_DATA}/config/moonraker.conf" 2>/dev/null || true
    fi

    echo ""
    ok_msg "Crowsnest has been removed."
    echo ""

    wait_for_key
    return 0
}

# Remove Sonar
do_remove_sonar() {
    clear_screen
    print_header "Remove Sonar"

    if ! is_sonar_installed; then
        echo -e "${BCYAN}${BOX_V}${NC}  ${YELLOW}Sonar is not installed.${NC}"
        print_footer
        wait_for_key
        return 1
    fi

    echo -e "${BCYAN}${BOX_V}${NC}"
    echo -e "${BCYAN}${BOX_V}${NC}  This will remove:"
    echo -e "${BCYAN}${BOX_V}${NC}  - Sonar keepalive service (~/sonar)"
    echo -e "${BCYAN}${BOX_V}${NC}  - Systemd service"
    echo -e "${BCYAN}${BOX_V}${NC}"
    print_footer

    if ! confirm "Are you sure you want to remove Sonar?"; then
        return 1
    fi

    echo ""

    # Use Sonar's uninstaller if available
    if [[ -f "${SONAR_DIR}/tools/uninstall.sh" ]]; then
        status_msg "Running Sonar uninstaller..."
        cd "$SONAR_DIR"
        bash tools/uninstall.sh
    else
        # Manual removal
        status_msg "Stopping and disabling Sonar service..."
        sudo systemctl stop sonar 2>/dev/null || true
        sudo systemctl disable sonar 2>/dev/null || true
        sudo rm -f "${SYSTEMD_DIR}/sonar.service"
        sudo systemctl daemon-reload

        status_msg "Removing Sonar files..."
        rm -rf "$SONAR_DIR"
    fi

    # Remove update manager entry
    if [[ -f "${PRINTER_DATA}/config/moonraker.conf" ]]; then
        sed -i '/\[update_manager sonar\]/,/^$/d' "${PRINTER_DATA}/config/moonraker.conf" 2>/dev/null || true
    fi

    echo ""
    ok_msg "Sonar has been removed."
    echo ""

    wait_for_key
    return 0
}

# Remove Timelapse
do_remove_timelapse() {
    clear_screen
    print_header "Remove Moonraker Timelapse"

    if ! is_timelapse_installed; then
        echo -e "${BCYAN}${BOX_V}${NC}  ${YELLOW}Timelapse is not installed.${NC}"
        print_footer
        wait_for_key
        return 1
    fi

    echo -e "${BCYAN}${BOX_V}${NC}"
    echo -e "${BCYAN}${BOX_V}${NC}  This will remove:"
    echo -e "${BCYAN}${BOX_V}${NC}  - Moonraker Timelapse (~/moonraker-timelapse)"
    echo -e "${BCYAN}${BOX_V}${NC}  - Component symlink from Moonraker"
    echo -e "${BCYAN}${BOX_V}${NC}"
    echo -e "${BCYAN}${BOX_V}${NC}  ${WHITE}timelapse.cfg and recordings will be preserved.${NC}"
    echo -e "${BCYAN}${BOX_V}${NC}"
    print_footer

    if ! confirm "Are you sure you want to remove Timelapse?"; then
        return 1
    fi

    echo ""

    # Remove symlink from Moonraker
    status_msg "Removing timelapse component symlink..."
    rm -f "${MOONRAKER_DIR}/moonraker/components/timelapse.py"

    # Remove repository
    status_msg "Removing Timelapse repository..."
    rm -rf "$TIMELAPSE_DIR"

    # Remove update manager entry
    if [[ -f "${PRINTER_DATA}/config/moonraker.conf" ]]; then
        sed -i '/\[update_manager timelapse\]/,/^$/d' "${PRINTER_DATA}/config/moonraker.conf" 2>/dev/null || true
        # Also remove the [timelapse] section
        sed -i '/\[timelapse\]/,/^$/d' "${PRINTER_DATA}/config/moonraker.conf" 2>/dev/null || true
    fi

    # Restart Moonraker
    status_msg "Restarting Moonraker..."
    sudo systemctl restart moonraker

    echo ""
    ok_msg "Timelapse has been removed."
    echo -e "  ${WHITE}timelapse.cfg and recordings have been preserved.${NC}"
    echo ""

    wait_for_key
    return 0
}

# Remove component menu
show_remove_menu() {
    while true; do
        clear_screen
        print_header "Remove Component"

        echo -e "${BCYAN}${BOX_V}${NC}  ${RED}WARNING: Removal is permanent!${NC}"
        echo -e "${BCYAN}${BOX_V}${NC}"
        echo -e "${BCYAN}${BOX_V}${NC}  Select component to remove:"
        echo -e "${BCYAN}${BOX_V}${NC}"

        # Show installed components
        local num=1
        local options=()

        if is_klipper_installed; then
            echo -e "${BCYAN}${BOX_V}${NC}  ${BWHITE}${num})${NC} Klipper"
            options+=("klipper")
            num=$((num + 1))
        fi

        if is_moonraker_installed; then
            echo -e "${BCYAN}${BOX_V}${NC}  ${BWHITE}${num})${NC} Moonraker"
            options+=("moonraker")
            num=$((num + 1))
        fi

        if is_mainsail_installed; then
            echo -e "${BCYAN}${BOX_V}${NC}  ${BWHITE}${num})${NC} Mainsail"
            options+=("mainsail")
            num=$((num + 1))
        fi

        if is_fluidd_installed; then
            echo -e "${BCYAN}${BOX_V}${NC}  ${BWHITE}${num})${NC} Fluidd"
            options+=("fluidd")
            num=$((num + 1))
        fi

        if is_crowsnest_installed; then
            echo -e "${BCYAN}${BOX_V}${NC}  ${BWHITE}${num})${NC} Crowsnest"
            options+=("crowsnest")
            num=$((num + 1))
        fi

        if is_sonar_installed; then
            echo -e "${BCYAN}${BOX_V}${NC}  ${BWHITE}${num})${NC} Sonar"
            options+=("sonar")
            num=$((num + 1))
        fi

        if is_timelapse_installed; then
            echo -e "${BCYAN}${BOX_V}${NC}  ${BWHITE}${num})${NC} Timelapse"
            options+=("timelapse")
            num=$((num + 1))
        fi

        if [[ ${#options[@]} -eq 0 ]]; then
            echo -e "${BCYAN}${BOX_V}${NC}  ${YELLOW}No components installed to remove.${NC}"
        fi

        echo -e "${BCYAN}${BOX_V}${NC}"
        print_separator
        print_action_item "B" "Back"
        print_footer

        echo -en "${BYELLOW}Select option${NC}: "
        read -r choice

        case "$choice" in
            [bB]) return ;;
            [0-9]*)
                local idx=$((choice - 1))
                if [[ $idx -ge 0 && $idx -lt ${#options[@]} ]]; then
                    case "${options[$idx]}" in
                        klipper) do_remove_klipper ;;
                        moonraker) do_remove_moonraker ;;
                        mainsail) do_remove_mainsail ;;
                        fluidd) do_remove_fluidd ;;
                        crowsnest) do_remove_crowsnest ;;
                        sonar) do_remove_sonar ;;
                        timelapse) do_remove_timelapse ;;
                    esac
                fi
                ;;
        esac
    done
}

