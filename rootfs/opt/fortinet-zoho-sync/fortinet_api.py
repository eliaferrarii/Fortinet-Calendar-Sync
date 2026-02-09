#!/usr/bin/env python3
"""
Fortinet API Client - Download device data from FortiCare API
Uses OAuth 2.0 authentication
"""

import requests
import logging
import json
import os
from datetime import datetime

logger = logging.getLogger(__name__)

class FortinetAPI:
    """Fortinet FortiCare API client with OAuth 2.0"""

    def __init__(self, api_config):
        """Initialize Fortinet API client"""
        self.api_id = api_config.get('api_id', '')
        self.password = api_config.get('password', '')
        self.account_id = api_config.get('account_id', '')
        self.client_id = api_config.get('client_id') or 'REPLACE_ME'
        self.auth_endpoint = api_config.get('auth_endpoint') or \
            'https://customerapiauth.fortinet.com/api/v1/oauth/token/'
        self.products_endpoint = api_config.get('products_endpoint') or \
            'https://support.fortinet.com/ES/api/registration/v3/products/list'

        self.enabled = bool(self.api_id and self.password and self.account_id)
        self.access_token = None

    def get_access_token(self):
        """Get OAuth 2.0 access token"""
        if not self.enabled:
            logger.warning("Fortinet API credentials not configured")
            return None

        payload = {
            "username": self.api_id,
            "password": self.password,
            "client_id": self.client_id,
            "grant_type": "password"
        }

        try:
            logger.info("Authenticating with Fortinet API...")

            response = requests.post(
                self.auth_endpoint,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            response.raise_for_status()

            token_data = response.json()
            self.access_token = token_data.get('access_token')

            expires_in = token_data.get('expires_in', 0)
            logger.info(f"Authentication successful! Token valid for {expires_in / 3600:.1f} hours")

            return self.access_token

        except requests.exceptions.RequestException as e:
            logger.error(f"Authentication error: {e}")
            return None

    def download_devices(self):
        """Download devices from Fortinet API"""
        if not self.enabled:
            logger.warning("Fortinet API not configured. Using local file.")
            return None

        # Get access token first
        token = self.get_access_token()
        if not token:
            logger.error("Failed to get access token")
            return None

        try:
            logger.info(f"Downloading devices from Fortinet API (Account: {self.account_id})...")

            headers = {
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json'
            }

            payload = {
                "accountId": int(self.account_id),
                "expireBefore": "2099-12-31"
            }

            response = requests.post(
                self.products_endpoint,
                json=payload,
                headers=headers,
                timeout=60
            )
            response.raise_for_status()

            data = response.json()

            # Validate response structure
            if 'assets' not in data:
                logger.error("Invalid response structure from Fortinet API (missing 'assets')")
                return None

            assets_count = len(data.get('assets', []))
            logger.info(f"Downloaded {assets_count} devices from Fortinet API")

            return data

        except requests.exceptions.RequestException as e:
            logger.error(f"Error downloading from Fortinet API: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Response status: {e.response.status_code}")
                logger.error(f"Response body: {e.response.text[:200]}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error downloading from Fortinet API: {e}")
            return None

    def save_to_file(self, data, file_path):
        """Save devices data to JSON file"""
        try:
            # Create backup of existing file
            if os.path.exists(file_path):
                backup_path = f"{file_path}.backup"
                try:
                    os.rename(file_path, backup_path)
                    logger.info(f"Created backup: {backup_path}")
                except Exception as e:
                    logger.warning(f"Could not create backup: {e}")

            # Save new data
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            # Get file size
            size_mb = os.path.getsize(file_path) / (1024 * 1024)
            logger.info(f"Saved {len(data.get('assets', []))} devices to {file_path} ({size_mb:.2f} MB)")

            return True

        except Exception as e:
            logger.error(f"Error saving devices to file: {e}")

            # Restore backup if save failed
            backup_path = f"{file_path}.backup"
            if os.path.exists(backup_path):
                try:
                    os.rename(backup_path, file_path)
                    logger.info("Restored from backup after save failure")
                except:
                    pass

            return False

    def update_devices_file(self, file_path):
        """Download and update devices file"""
        if not self.enabled:
            logger.info("Fortinet API not configured. Skipping update.")
            return False

        logger.info("Updating Fortinet devices data...")

        # Download data
        data = self.download_devices()
        if not data:
            logger.error("Failed to download devices from Fortinet API")
            return False

        # Save to file
        success = self.save_to_file(data, file_path)
        if success:
            logger.info("Successfully updated Fortinet devices data")
        else:
            logger.error("Failed to save Fortinet devices data")

        return success
