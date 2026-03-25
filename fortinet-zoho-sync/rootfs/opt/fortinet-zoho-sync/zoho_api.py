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
        self.registry_path = '/config/fortinet_zoho_event_registry.json'
        self.access_token = None

    def _load_registry(self):
        """Load local event registry used to prevent duplicate creations."""
        if not os.path.exists(self.registry_path):
            return {}
        try:
            with open(self.registry_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except Exception as e:
            logger.warning(f"Error reading event registry: {e}")
            return {}

    def _save_registry(self, registry):
        """Persist local event registry."""
        try:
            os.makedirs(os.path.dirname(self.registry_path), exist_ok=True)
            with open(self.registry_path, 'w', encoding='utf-8') as f:
                json.dump(registry, f, indent=2)
        except Exception as e:
            logger.warning(f"Error saving event registry: {e}")

    def _event_key(self, serial, event_date_str, technician_id):
        """Build stable registry key for a calendar event."""
        return f"{serial}|{event_date_str}|{technician_id}"

    def _is_registered(self, serial, event_date_str, technician_id):
        """Check local registry before relying on Zoho lookup."""
        registry = self._load_registry()
        return self._event_key(serial, event_date_str, technician_id) in registry

    def _register_event(self, serial, event_date_str, technician_id, source, zoho_id=None):
        """Record an event in the local registry."""
        registry = self._load_registry()
        key = self._event_key(serial, event_date_str, technician_id)
        registry[key] = {
            'serial': serial,
            'event_date': event_date_str,
            'technician_id': str(technician_id),
            'source': source,
            'zoho_id': str(zoho_id) if zoho_id not in (None, '') else '',
            'updated_at': datetime.now().isoformat()
        }
        self._save_registry(registry)

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

    def _extract_lookup_id(self, value):
        """Extract Zoho lookup ID from different response formats."""
        if isinstance(value, dict):
            for key in ('ID', 'id', 'zc_display_value'):
                candidate = value.get(key)
                if candidate not in (None, ''):
                    return str(candidate)
            return ''
        if value in (None, ''):
            return ''
        return str(value)

    def _extract_date_and_time(self, value):
        """Normalize Zoho date/datetime fields to comparable values."""
        if value in (None, ''):
            return '', ''

        text = str(value).strip()
        for fmt in ('%d/%m/%Y %H:%M', '%d/%m/%Y', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%Y-%m-%d'):
            try:
                parsed = datetime.strptime(text, fmt)
                date_value = parsed.strftime('%d/%m/%Y')
                time_value = parsed.strftime('%H:%M') if 'H:%M' in fmt else ''
                return date_value, time_value
            except ValueError:
                continue

        parts = text.split()
        if len(parts) >= 2:
            return parts[0], parts[1][:5]
        return text, ''

    def _fetch_events(self, headers, criteria):
        """Fetch candidate events from the configured Zoho report."""
        url = f"{self.api_base}/{self.config['owner']}/{self.config['app']}/report/{self.config['report']}"
        response = requests.get(url, headers=headers, params={'criteria': criteria}, timeout=30)

        if response.status_code != 200:
            logger.warning(f"Zoho event lookup failed (HTTP {response.status_code}) for criteria: {criteria}")
            return []

        result = response.json()
        if result.get('code') != 3000:
            logger.warning(f"Zoho event lookup returned code {result.get('code')} for criteria: {criteria}")
            return []

        return result.get('data', [])

    def check_event_exists(self, serial, event_date_str, technician_id, event_config,
                           allow_technician_fallback=False, expected_candidate_count=None):
        """Check if event already exists in Zoho Calendar."""
        try:
            if self._is_registered(serial, event_date_str, technician_id):
                logger.info(
                    f"Existing event found in local registry for {serial} on {event_date_str} "
                    f"(technician={technician_id})"
                )
                return True

            access_token = self.get_access_token()

            # Convert date to DD/MM/YYYY format
            date_obj = datetime.strptime(event_date_str, '%Y-%m-%d')
            zoho_date = date_obj.strftime('%d/%m/%Y')
            expected_start = event_config['start_time'][:5]
            expected_end = event_config['end_time'][:5]

            headers = {
                'Authorization': f'Zoho-oauthtoken {access_token}',
                'Content-Type': 'application/json'
            }

            criteria_list = [
                f"Data = '{zoho_date}' && Titolo.contains(\"Scadenza\") && Titolo.contains(\"{serial}\")",
                f"Titolo.contains(\"Scadenza\") && Titolo.contains(\"{serial}\")"
            ]

            candidates = []
            for criteria in criteria_list:
                fetched = self._fetch_events(headers, criteria)
                if fetched:
                    candidates = fetched
                    logger.info(f"Zoho duplicate lookup found {len(candidates)} candidate(s) with criteria: {criteria}")
                    break

            for event in candidates:
                event_tecnico_id = (
                    self._extract_lookup_id(event.get('LkpTecnico')) or
                    self._extract_lookup_id(event.get('LkpTecnico.ID')) or
                    self._extract_lookup_id(event.get('LkpTecnico_calfield')) or
                    self._extract_lookup_id(event.get('LkpTecnico_ID'))
                )

                start_date, start_time = self._extract_date_and_time(event.get('DataInizio'))
                end_date, end_time = self._extract_date_and_time(event.get('DataFine'))
                data_date, _ = self._extract_date_and_time(event.get('Data'))

                same_date = zoho_date in {start_date, end_date, data_date}
                same_slot = start_time == expected_start and end_time == expected_end
                same_technician = str(event_tecnico_id) == str(technician_id)
                fallback_match = allow_technician_fallback and not event_tecnico_id

                if same_date:
                    self._register_event(serial, event_date_str, technician_id, 'zoho_lookup')
                    logger.info(
                        f"Existing event found for {serial} on {zoho_date}; "
                        f"skipping creation conservatively to avoid duplicates"
                    )
                    return True

                if same_date and same_slot and (same_technician or fallback_match):
                    self._register_event(serial, event_date_str, technician_id, 'zoho_lookup')
                    logger.info(
                        f"Existing event matched for {serial} on {zoho_date} "
                        f"(technician={technician_id}, found={event_tecnico_id or 'missing'}, "
                        f"slot={expected_start}-{expected_end})"
                    )
                    return True

            if expected_candidate_count and len(candidates) >= expected_candidate_count:
                self._register_event(serial, event_date_str, technician_id, 'zoho_lookup')
                logger.info(
                    f"Existing events already cover all configured technicians for {serial} on {zoho_date} "
                    f"(candidates={len(candidates)}, expected={expected_candidate_count})"
                )
                return True

            logger.info(
                f"No existing event matched for {serial} on {zoho_date} "
                f"(technician={technician_id}, candidates={len(candidates)})"
            )
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

            payload = {
                "Data": zoho_date,
                "DataInizio": start_datetime,
                "DataFine": end_datetime,
                "Titolo": title,
                "DescrizioneAttivita": description,
                "Tipologia": event_config['tipologia'],
                "OrePianificate": event_config['ore_pianificate'],
                "LkpTecnico": technician_id,
                "Reparto": event_config['reparto']
            }

            attivita_interna_id = event_config.get('attivita_interna_id')
            if attivita_interna_id not in (None, '', 0, '0'):
                payload["LkpAttivitaInterna"] = attivita_interna_id

            event_data = {"data": payload}

            logger.info(f"Creating event: {title} on {zoho_date} for technician {technician_id}")
            logger.debug(f"Event payload: {json.dumps(event_data)}")

            response = requests.post(url, headers=headers, json=event_data, timeout=30)

            result = response.json()
            logger.info(f"Zoho create response (HTTP {response.status_code}): {json.dumps(result)}")

            if response.status_code == 200 and result.get('code') == 3000:
                self._register_event(
                    device_data['serial'],
                    event_date_str,
                    technician_id,
                    'zoho_create',
                    result.get('data', {}).get('ID')
                )
                return True

            error_text = json.dumps(result)
            if payload.get("LkpAttivitaInterna") and "Invalid column value" in error_text:
                retry_payload = dict(payload)
                invalid_value = retry_payload.pop("LkpAttivitaInterna", None)
                logger.warning(
                    f"Zoho rejected LkpAttivitaInterna={invalid_value}; retrying create without that field"
                )

                retry_event_data = {"data": retry_payload}
                retry_response = requests.post(url, headers=headers, json=retry_event_data, timeout=30)
                retry_result = retry_response.json()
                logger.info(
                    f"Zoho create retry response (HTTP {retry_response.status_code}): {json.dumps(retry_result)}"
                )

                if retry_response.status_code == 200 and retry_result.get('code') == 3000:
                    self._register_event(
                        device_data['serial'],
                        event_date_str,
                        technician_id,
                        'zoho_create_retry',
                        retry_result.get('data', {}).get('ID')
                    )
                    return True

                result = retry_result

            logger.error(
                f"Zoho create event failed - code: {result.get('code')}, "
                f"message: {result.get('message')}, result: {json.dumps(result)}"
            )
            return False

        except Exception as e:
            logger.error(f"Error creating event: {e}")
            return False
