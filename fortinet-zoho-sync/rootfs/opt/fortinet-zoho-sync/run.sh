#!/bin/bash
set -e

echo "Starting Fortinet Zoho Sync Add-on..."

# Read configuration from Home Assistant options file
CONFIG_PATH="/data/options.json"

if [ -f "$CONFIG_PATH" ]; then
    echo "Configuration loaded from $CONFIG_PATH"

    # Export configuration as environment variables using jq
    export FILTER_DAYS_MIN=$(jq -r '.filter_days_min // 1' $CONFIG_PATH)
    export FILTER_DAYS_MAX=$(jq -r '.filter_days_max // 15' $CONFIG_PATH)
    export ZOHO_DC=$(jq -r '.zoho_dc // "eu"' $CONFIG_PATH)
    export ZOHO_CLIENT_ID=$(jq -r '.zoho_client_id' $CONFIG_PATH)
    export ZOHO_CLIENT_SECRET=$(jq -r '.zoho_client_secret' $CONFIG_PATH)
    export ZOHO_OWNER=$(jq -r '.zoho_owner // "REPLACE_ME"' $CONFIG_PATH)
    export ZOHO_APP=$(jq -r '.zoho_app // "REPLACE_ME"' $CONFIG_PATH)
    export ZOHO_FORM=$(jq -r '.zoho_form // "Pianificazione"' $CONFIG_PATH)
    export ZOHO_REPORT=$(jq -r '.zoho_report // "CalendarioPianificazione"' $CONFIG_PATH)
    export ATTIVITA_INTERNA_ID=$(jq -r '.attivita_interna_id // 0' $CONFIG_PATH)
    export REPARTO=$(jq -r '.reparto // "REPLACE_ME"' $CONFIG_PATH)
    export TIPOLOGIA=$(jq -r '.tipologia // "Altre attività"' $CONFIG_PATH)
    export EVENT_START_TIME=$(jq -r '.event_start_time // "08:00"' $CONFIG_PATH)
    export EVENT_END_TIME=$(jq -r '.event_end_time // "09:00"' $CONFIG_PATH)
    export ORE_PIANIFICATE=$(jq -r '.ore_pianificate // 1.0' $CONFIG_PATH)
    export FORTINET_API_ID=$(jq -r '.fortinet_api_id // ""' $CONFIG_PATH)
    export FORTINET_PASSWORD=$(jq -r '.fortinet_password // ""' $CONFIG_PATH)
    export FORTINET_ACCOUNT_ID=$(jq -r '.fortinet_account_id // ""' $CONFIG_PATH)
    export FORTINET_CLIENT_ID=$(jq -r '.fortinet_client_id // "REPLACE_ME"' $CONFIG_PATH)
    export FORTINET_AUTH_ENDPOINT=$(jq -r '.fortinet_auth_endpoint // ""' $CONFIG_PATH)
    export FORTINET_PRODUCTS_ENDPOINT=$(jq -r '.fortinet_products_endpoint // ""' $CONFIG_PATH)

    # Export technicians as JSON
    jq -r '.technicians' $CONFIG_PATH > /tmp/technicians.json

    echo "Configuration loaded successfully"
    echo "Filter: ${FILTER_DAYS_MIN}-${FILTER_DAYS_MAX} days"
    echo "Zoho DC: ${ZOHO_DC}"
else
    echo "WARNING: Configuration file not found at $CONFIG_PATH"
    echo "Using default values"
    export FILTER_DAYS_MIN=1
    export FILTER_DAYS_MAX=15
    export ZOHO_DC="eu"
fi

# Start Flask application
echo "Starting web server on port 8099..."
cd /opt/fortinet-zoho-sync
exec python3 app.py
