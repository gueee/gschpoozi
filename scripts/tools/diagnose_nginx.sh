#!/bin/bash
# Nginx diagnostic script for troubleshooting post-pull issues

set -e

echo "════════════════════════════════════════════════════════════"
echo "  Nginx Diagnostic Tool"
echo "════════════════════════════════════════════════════════════"
echo ""

# 1. Check nginx service status
echo "1. Checking nginx service status..."
if systemctl is-active --quiet nginx; then
    echo "   ✓ nginx is running"
else
    echo "   ✗ nginx is NOT running"
    echo "   Status: $(systemctl is-active nginx || echo 'inactive')"
fi
echo ""

# 2. Test nginx configuration syntax
echo "2. Testing nginx configuration syntax..."
if sudo nginx -t 2>&1; then
    echo "   ✓ Configuration syntax is valid"
else
    echo "   ✗ Configuration syntax has errors (see above)"
fi
echo ""

# 3. Check nginx error log for recent errors
echo "3. Recent nginx errors (last 20 lines)..."
if [[ -f /var/log/nginx/error.log ]]; then
    sudo tail -20 /var/log/nginx/error.log | sed 's/^/   /'
else
    echo "   No error log found at /var/log/nginx/error.log"
fi
echo ""

# 4. Check line endings in template files
echo "4. Checking line endings in nginx template files..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEMPLATE_DIR="${SCRIPT_DIR}/lib/nginx-templates"

if [[ -d "$TEMPLATE_DIR" ]]; then
    for template in "${TEMPLATE_DIR}"/*.conf; do
        if [[ -f "$template" ]]; then
            filename=$(basename "$template")
            # Check for CRLF (Windows line endings)
            if file "$template" | grep -q "CRLF"; then
                echo "   ✗ $filename has CRLF line endings (Windows)"
            elif grep -q $'\r' "$template" 2>/dev/null; then
                echo "   ✗ $filename contains CR characters"
            else
                echo "   ✓ $filename has LF line endings (Unix)"
            fi
        fi
    done
else
    echo "   ✗ Template directory not found: $TEMPLATE_DIR"
fi
echo ""

# 5. Check line endings in generated nginx configs
echo "5. Checking line endings in generated nginx configs..."
for site in /etc/nginx/sites-enabled/*; do
    if [[ -f "$site" ]]; then
        sitename=$(basename "$site")
        if grep -q $'\r' "$site" 2>/dev/null; then
            echo "   ✗ $sitename contains CR characters"
        else
            echo "   ✓ $sitename has LF line endings"
        fi
    fi
done
echo ""

# 6. Check if web UIs are installed
echo "6. Checking installed web UIs..."
if [[ -d ~/mainsail ]]; then
    echo "   ✓ Mainsail installed at ~/mainsail"
    if [[ -f ~/mainsail/index.html ]]; then
        echo "     - index.html exists"
    else
        echo "     ✗ index.html missing!"
    fi
else
    echo "   - Mainsail not installed"
fi

if [[ -d ~/fluidd ]]; then
    echo "   ✓ Fluidd installed at ~/fluidd"
    if [[ -f ~/fluidd/index.html ]]; then
        echo "     - index.html exists"
    else
        echo "     ✗ index.html missing!"
    fi
else
    echo "   - Fluidd not installed"
fi
echo ""

# 7. Check nginx site configs exist
echo "7. Checking nginx site configurations..."
if [[ -f /etc/nginx/sites-enabled/mainsail ]]; then
    echo "   ✓ Mainsail site config exists"
    echo "     Port: $(grep -E '^\s*listen\s+' /etc/nginx/sites-enabled/mainsail | head -1 | sed 's/.*listen[^0-9]*\([0-9]*\).*/\1/' || echo 'unknown')"
else
    echo "   - Mainsail site config not found"
fi

if [[ -f /etc/nginx/sites-enabled/fluidd ]]; then
    echo "   ✓ Fluidd site config exists"
    echo "     Port: $(grep -E '^\s*listen\s+' /etc/nginx/sites-enabled/fluidd | head -1 | sed 's/.*listen[^0-9]*\([0-9]*\).*/\1/' || echo 'unknown')"
else
    echo "   - Fluidd site config not found"
fi
echo ""

# 8. Check file permissions for web UIs
echo "8. Checking file permissions..."
if [[ -d ~/mainsail ]]; then
    if sudo -u www-data test -r ~/mainsail/index.html 2>/dev/null; then
        echo "   ✓ nginx (www-data) can read ~/mainsail/index.html"
    else
        echo "   ✗ nginx (www-data) CANNOT read ~/mainsail/index.html"
        echo "     Permissions: $(ls -ld ~/mainsail | awk '{print $1, $3, $4}')"
    fi
fi

if [[ -d ~/fluidd ]]; then
    if sudo -u www-data test -r ~/fluidd/index.html 2>/dev/null; then
        echo "   ✓ nginx (www-data) can read ~/fluidd/index.html"
    else
        echo "   ✗ nginx (www-data) CANNOT read ~/fluidd/index.html"
        echo "     Permissions: $(ls -ld ~/fluidd | awk '{print $1, $3, $4}')"
    fi
fi
echo ""

# 9. Check for duplicate default_server directives
echo "9. Checking for duplicate default_server directives..."
default_count=$(grep -r "default_server" /etc/nginx/sites-enabled/ 2>/dev/null | wc -l || echo "0")
if [[ "$default_count" -gt 1 ]]; then
    echo "   ✗ Found $default_count default_server directives (should be 0 or 1)"
    echo "     Files with default_server:"
    grep -l "default_server" /etc/nginx/sites-enabled/* 2>/dev/null | sed 's/^/     - /' || true
else
    echo "   ✓ No duplicate default_server directives"
fi
echo ""

# 10. Summary and recommendations
echo "════════════════════════════════════════════════════════════"
echo "  Summary & Recommendations"
echo "════════════════════════════════════════════════════════════"
echo ""

if ! sudo nginx -t >/dev/null 2>&1; then
    echo "⚠ Nginx configuration has syntax errors!"
    echo "  Run: sudo nginx -t (to see details)"
    echo "  Fix: Regenerate configs from templates"
    echo ""
fi

if systemctl is-active --quiet nginx; then
    echo "✓ Nginx service is running"
else
    echo "⚠ Nginx service is NOT running"
    echo "  Try: sudo systemctl restart nginx"
    echo ""
fi

echo "To fix nginx after git pull:"
echo "  source ~/gschpoozi/scripts/lib/klipper-install.sh"
echo "  fix_nginx_after_pull"
echo ""
echo "Or manually regenerate:"
echo "  cd ~/gschpoozi"
echo "  source scripts/lib/klipper-install.sh"
if [[ -d ~/mainsail ]]; then
    echo "  setup_nginx mainsail"
fi
if [[ -d ~/fluidd ]]; then
    echo "  setup_nginx fluidd"
fi
echo ""
