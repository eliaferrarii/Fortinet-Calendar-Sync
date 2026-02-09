#!/usr/bin/env python3
"""
Zoho API - Handle all Zoho Calendar/Creator interactions
"""

import requests
import logging
import json
import os
from datetime import datetime

logger = logging.getLogger(__name__)

class ZohoAPI:
    """Zoho API client"""

    def __init__(self, zoho_config):
        """Initialize Zoho API client"""
        self.config = zoho_config
        self.dc = zoho_config['dc']
        self.api_base = f"https://creator.zoho.{self.dc}/api/v2.1"
        self.token_path = '/config/zoho_tokens.json'
        self.access_token = None

    def get_access_token(self):
        """Get or refresh Zoho access token"""
        # Check if cached token exists and is valid
        if os.path.exists(self.token_path):
            try:
                with open(self.token_path, 'r') as f:
                    token_data = json.load(f)
                    expires_at = token_data.get('expires_at', 0)
                    if datetime.now().timestamp() < expires_at:
                        self.access_token = token_data['access_token']
                        return self.access_token
            except Exception as e:
                logger.warning(f"Error reading cached token: {e}")

        # Need to refresh token
        logger.info("Refreshing Zoho access token...")

        # Check if refresh token exists
        if not os.path.exists('/config/zoho_refresh_token.txt'):
            raise Exception("Zoho refresh token not found. Please configure authentication first.")

        with open('/config/zoho_refresh_token.txt', 'r') as f:
            refresh_token = f.read().strip()

        token_url = f"https://accounts.zoho.{self.dc}/oauth/v2/token"
        data = {
            'grant_type': 'refresh_token',
            'client_id': self.config['client_id'],
            'client_secret': self.config['client_secret'],
            'refresh_token': refresh_token
        }

        response = requests.post(token_url, data=data, timeout=30)
        response.raise_for_status()

        token_response = response.json()

        if 'error' in token_response:
            raise Exception(f"Zoho token error: {token_response['error']} - {token_response.get('error_description', '')}")

        if 'access_token' not in token_response:
            raise Exception(f"Zoho response missing access_token: {json.dumps(token_response)}")

        access_token = token_response['access_token']
        expires_in = token_response.get('expires_in', 3600)

        # Save token to cache
        expires_at = int(datetime.now().timestamp()) + expires_in - 60
        with open(self.token_path, 'w') as f:
            json.dump({
                'access_token': access_token,
                'expires_at': expires_at
            }, f, indent=2)

        self.access_token = access_token
        logger.info("Access token refreshed successfully")
        return access_token

    def check_event_exists(self, serial, event_date_str, technician_id):
        """Check if event already exists in Zoho Calendar"""
        try:
            access_token = self.get_access_token()

            # Convert date to DD/MM/YYYY format
            date_obj = datetime.strptime(event_date_str, '%Y-%m-%d')
            zoho_date = date_obj.strftime('%d/%m/%Y')

            url = f"{self.api_base}/{self.config['owner']}/{self.config['app']}/report/{self.config['report']}"

            headers = {
                'Authorization': f'Zoho-oauthtoken {access_token}',
                'Content-Type': 'application/json'
            }

            # Search for existing event
            criteria = f"Data = '{zoho_date}' && Titolo.contains(\"Scadenza\") && Titolo.contains(\"{serial}\")"

            params = {'criteria': criteria}

            response = requests.get(url, headers=headers, params=params, timeout=30)

            if response.status_code == 200:
                result = response.json()
                if result.get('code') == 3000:
                    data = result.get('data', [])

                    # Verify it matches our criteria
                    for event in data:
                        tecnico = event.get('LkpTecnico', {})
                        if isinstance(tecnico, dict):
                            event_tecnico_id = tecnico.get('ID', '')
                        else:
                            event_tecnico_id = event.get('LkpTecnico_calfield', '')

                        start_time = event.get('DataInizio', '')
                        end_time = event.get('DataFine', '')

                        if (str(event_tecnico_id) == str(technician_id) and
                            start_time == '08:00' and
                            end_time == '09:00'):
                            return True

                    return False

            return False

        except Exception as e:
            logger.warning(f"Error checking event existence: {e}")
            return False

    def create_event(self, device_data, event_date_str, technician_id, event_config):
        """Create event in Zoho Calendar"""
        try:
            access_token = self.get_access_token()

            # Build services list
            services_text = "\n".join([
                f"- {svc['service']} ({svc['level']}) - Scade il {svc['expiration_date']} ({svc['days_remaining']} giorni)"
                for svc in device_data['services']
            ])

            # Prepare event data
            title = f"Scadenza {device_data['model']} - {device_data['serial']}"
            description = f"""Dispositivo in scadenza:

Modello: {device_data['model']}
Seriale: {device_data['serial']}
Descrizione: {device_data['description']}

Servizi in scadenza ({len(device_data['services'])}):
{services_text}

ATTENZIONE: Verificare rinnovo contratto!"""

            date_obj = datetime.strptime(event_date_str, '%Y-%m-%d')
            zoho_date = date_obj.strftime('%d/%m/%Y')
            start_datetime = f"{zoho_date} {event_config['start_time']}"
            end_datetime = f"{zoho_date} {event_config['end_time']}"

            url = f"{self.api_base}/{self.config['owner']}/{self.config['app']}/form/{self.config['form']}"

            headers = {
                'Authorization': f'Zoho-oauthtoken {access_token}',
                'Content-Type': 'application/json'
            }

            event_data = {
                "data": {
                    "Data": zoho_date,
                    "DataInizio": start_datetime,
                    "DataFine": end_datetime,
                    "Titolo": title,
                    "DescrizioneAttivita": description,
                    "Tipologia": event_config['tipologia'],
                    "OrePianificate": event_config['ore_pianificate'],
                    "LkpTecnico": technician_id,
                    "LkpAttivitaInterna": event_config['attivita_interna_id'],
                    "Reparto": event_config['reparto']
                }
            }

            response = requests.post(url, headers=headers, json=event_data, timeout=30)

            if response.status_code == 200:
                result = response.json()
                if result.get('code') == 3000:
                    return True
                else:
                    logger.error(f"Zoho API error: {result.get('message')}")
                    return False
            else:
                logger.error(f"HTTP error {response.status_code}: {response.text}")
                return False

        except Exception as e:
            logger.error(f"Error creating event: {e}")
            return False
