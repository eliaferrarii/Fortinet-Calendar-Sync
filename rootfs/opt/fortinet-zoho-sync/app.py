#!/usr/bin/env python3
"""
Fortinet Zoho Sync - Home Assistant Add-on
Main Flask application
"""

import os
import json
import logging
from datetime import datetime
from flask import Flask, render_template, jsonify, request
from fortinet_sync import FortinetZohoSync

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False

# Initialize sync manager
sync_manager = None
OPTIONS_PATH = '/data/options.json'
USER_CONFIG_PATH = '/data/user_config.json'
REFRESH_TOKEN_PATH = '/config/zoho_refresh_token.txt'

def _load_json(path):
    try:
        if os.path.exists(path):
            with open(path, 'r') as f:
                return json.load(f)
    except Exception as e:
        logger.warning(f"Error reading JSON from {path}: {e}")
    return None

def _deep_merge(base, updates):
    if not isinstance(updates, dict):
        return base
    for key, value in updates.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value
    return base

def get_config():
    """Load configuration from environment variables"""
    try:
        with open('/tmp/technicians.json', 'r') as f:
            technicians = json.load(f)
    except:
        technicians = [{'id': 0, 'name': 'Tecnico Esempio'}]

    defaults = {
        'filter_days_min': int(os.getenv('FILTER_DAYS_MIN', '1')),
        'filter_days_max': int(os.getenv('FILTER_DAYS_MAX', '15')),
        'technicians': technicians,
        'zoho': {
            'dc': os.getenv('ZOHO_DC', 'eu'),
            'client_id': os.getenv('ZOHO_CLIENT_ID'),
            'client_secret': os.getenv('ZOHO_CLIENT_SECRET'),
            'owner': os.getenv('ZOHO_OWNER', 'REPLACE_ME'),
            'app': os.getenv('ZOHO_APP', 'REPLACE_ME'),
            'form': os.getenv('ZOHO_FORM', 'REPLACE_ME'),
            'report': os.getenv('ZOHO_REPORT', 'CalendarioPianificazione'),
        },
        'fortinet_api': {
            'api_id': os.getenv('FORTINET_API_ID', ''),
            'password': os.getenv('FORTINET_PASSWORD', ''),
            'account_id': os.getenv('FORTINET_ACCOUNT_ID', ''),
            'client_id': os.getenv('FORTINET_CLIENT_ID', 'REPLACE_ME'),
            'auth_endpoint': os.getenv('FORTINET_AUTH_ENDPOINT', ''),
            'products_endpoint': os.getenv('FORTINET_PRODUCTS_ENDPOINT', '')
        },
        'event': {
            'attivita_interna_id': int(os.getenv('ATTIVITA_INTERNA_ID', '0')),
            'reparto': os.getenv('REPARTO', 'REPLACE_ME'),
            'tipologia': os.getenv('TIPOLOGIA', 'REPLACE_ME'),
            'start_time': os.getenv('EVENT_START_TIME', '08:00'),
            'end_time': os.getenv('EVENT_END_TIME', '09:00'),
            'ore_pianificate': float(os.getenv('ORE_PIANIFICATE', '1.0'))
        }
    }

    options_cfg = _load_json(OPTIONS_PATH) or {}
    user_cfg = _load_json(USER_CONFIG_PATH) or {}

    config = _deep_merge(defaults, options_cfg)
    config = _deep_merge(config, user_cfg)

    return config

def _is_configured(config):
    zoho_cfg = config.get('zoho', {})
    required = [
        zoho_cfg.get('client_id'),
        zoho_cfg.get('client_secret'),
        zoho_cfg.get('owner'),
        zoho_cfg.get('app'),
        zoho_cfg.get('form'),
        zoho_cfg.get('report'),
    ]
    if not all(required):
        return False
    if not os.path.exists(REFRESH_TOKEN_PATH):
        return False
    try:
        with open(REFRESH_TOKEN_PATH, 'r') as f:
            if not f.read().strip():
                return False
    except Exception:
        return False
    return True

@app.route('/')
def index():
    """Dashboard home page"""
    return render_template('index.html')

@app.route('/setup')
def setup():
    """Setup wizard page"""
    return render_template('setup.html')

@app.route('/api/config')
def api_config():
    """Get current configuration"""
    config = get_config()
    # Remove sensitive data
    config['zoho']['client_secret'] = '***'
    return jsonify(config)

@app.route('/api/status')
def api_status():
    """Return configuration status"""
    config = get_config()
    return jsonify({
        'configured': _is_configured(config)
    })

@app.route('/api/setup', methods=['POST'])
def api_setup():
    """Save setup configuration"""
    try:
        payload = request.get_json(force=True)
        if not payload:
            return jsonify({'success': False, 'error': 'Dati mancanti'}), 400

        zoho = payload.get('zoho', {})
        fortinet_api = payload.get('fortinet_api', {})
        event_cfg = payload.get('event', {})
        technicians = payload.get('technicians', [])
        refresh_token = payload.get('refresh_token', '').strip()

        required = [
            zoho.get('dc'),
            zoho.get('client_id'),
            zoho.get('client_secret'),
            zoho.get('owner'),
            zoho.get('app'),
            zoho.get('form'),
            zoho.get('report'),
            refresh_token
        ]
        if not all(required):
            return jsonify({'success': False, 'error': 'Compila tutti i campi richiesti'}), 400

        user_cfg = {
            'filter_days_min': int(payload.get('filter_days_min', 1)),
            'filter_days_max': int(payload.get('filter_days_max', 15)),
            'technicians': technicians,
            'zoho': {
                'dc': zoho.get('dc'),
                'client_id': zoho.get('client_id'),
                'client_secret': zoho.get('client_secret'),
                'owner': zoho.get('owner'),
                'app': zoho.get('app'),
                'form': zoho.get('form'),
                'report': zoho.get('report')
            },
            'fortinet_api': {
                'api_id': fortinet_api.get('api_id', ''),
                'password': fortinet_api.get('password', ''),
                'account_id': fortinet_api.get('account_id', ''),
                'client_id': fortinet_api.get('client_id', ''),
                'auth_endpoint': fortinet_api.get('auth_endpoint', ''),
                'products_endpoint': fortinet_api.get('products_endpoint', '')
            },
            'event': {
                'attivita_interna_id': int(event_cfg.get('attivita_interna_id', 0)),
                'reparto': event_cfg.get('reparto', ''),
                'tipologia': event_cfg.get('tipologia', ''),
                'start_time': event_cfg.get('start_time', '08:00'),
                'end_time': event_cfg.get('end_time', '09:00'),
                'ore_pianificate': float(event_cfg.get('ore_pianificate', 1.0))
            }
        }

        os.makedirs(os.path.dirname(USER_CONFIG_PATH), exist_ok=True)
        with open(USER_CONFIG_PATH, 'w') as f:
            json.dump(user_cfg, f, indent=2)

        os.makedirs(os.path.dirname(REFRESH_TOKEN_PATH), exist_ok=True)
        with open(REFRESH_TOKEN_PATH, 'w') as f:
            f.write(refresh_token)

        with open('/tmp/technicians.json', 'w') as f:
            json.dump(technicians, f)

        global sync_manager
        sync_manager = None

        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error saving setup: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/devices')
def api_devices():
    """Get devices expiring soon"""
    try:
        global sync_manager
        if not sync_manager:
            sync_manager = FortinetZohoSync(get_config())

        devices = sync_manager.get_expiring_devices()
        return jsonify({
            'success': True,
            'count': len(devices),
            'devices': devices
        })
    except Exception as e:
        logger.error(f"Error getting devices: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/sync', methods=['POST'])
def api_sync():
    """Run synchronization manually"""
    try:
        global sync_manager
        if not sync_manager:
            sync_manager = FortinetZohoSync(get_config())

        result = sync_manager.sync_to_calendar()
        return jsonify({
            'success': True,
            'result': result
        })
    except Exception as e:
        logger.error(f"Error during sync: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/health')
def api_health():
    """Health check endpoint"""
    return jsonify({
        'status': 'ok',
        'timestamp': datetime.now().isoformat()
    })

if __name__ == '__main__':
    logger.info("Starting Fortinet Zoho Sync Add-on")
    logger.info(f"Configuration: {get_config()}")

    # Initialize sync manager
    try:
        sync_manager = FortinetZohoSync(get_config())
        logger.info("Sync manager initialized successfully")
    except Exception as e:
        logger.error(f"Error initializing sync manager: {e}")

    # Start Flask app
    app.run(host='0.0.0.0', port=8099, debug=False)
