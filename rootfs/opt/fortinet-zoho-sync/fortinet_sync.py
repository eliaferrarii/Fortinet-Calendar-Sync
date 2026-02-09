#!/usr/bin/env python3
"""
Fortinet Zoho Sync - Core synchronization logic
"""

import json
import logging
import os
from datetime import datetime, timedelta
from zoho_api import ZohoAPI
from fortinet_api import FortinetAPI

logger = logging.getLogger(__name__)

class FortinetZohoSync:
    """Main synchronization manager"""

    def __init__(self, config):
        """Initialize sync manager with configuration"""
        self.config = config
        self.zoho = ZohoAPI(config['zoho'])
        self.fortinet_api = FortinetAPI(config.get('fortinet_api', {}))
        self.fortinet_data_path = '/config/fortinet_devices.json'

    def load_fortinet_data(self):
        """Load Fortinet device data from JSON file"""
        if not os.path.exists(self.fortinet_data_path):
            logger.warning(f"Fortinet data file not found: {self.fortinet_data_path}")
            return []

        try:
            with open(self.fortinet_data_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            if isinstance(data, dict) and 'assets' in data:
                return data['assets']
            elif isinstance(data, list):
                return data
            else:
                logger.error("Unexpected data structure in JSON file")
                return []
        except Exception as e:
            logger.error(f"Error loading Fortinet data: {e}")
            return []

    def is_firewall(self, model):
        """Check if device is a FortiGate firewall"""
        return 'FortiGate' in model or model.startswith('FGT') or model.startswith('FG-')

    def calculate_days_until_expiration(self, end_date_str):
        """Calculate days until expiration from date string"""
        try:
            end_date = datetime.strptime(end_date_str.split('T')[0], '%Y-%m-%d')
            today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            days_remaining = (end_date - today).days
            return days_remaining
        except Exception:
            return None

    def get_event_date(self, expiration_date_str):
        """
        Calculate event date (one day before expiration).
        If it falls on Saturday or Sunday, move to Friday.
        """
        try:
            expiration_date = datetime.strptime(expiration_date_str.split('T')[0], '%Y-%m-%d')
            event_date = expiration_date - timedelta(days=1)

            weekday = event_date.weekday()
            if weekday == 5:  # Saturday
                event_date = event_date - timedelta(days=1)
            elif weekday == 6:  # Sunday
                event_date = event_date - timedelta(days=2)

            return event_date, event_date.strftime('%Y-%m-%d')
        except Exception as e:
            logger.error(f"Error calculating event date: {e}")
            return None, None

    def get_expiring_devices(self):
        """Get devices expiring within configured date range"""
        fortinet_data = self.load_fortinet_data()
        devices_dict = {}

        min_days = self.config['filter_days_min']
        max_days = self.config['filter_days_max']

        for asset in fortinet_data:
            serial = asset.get('serialNumber', 'N/A')
            model = asset.get('productModel', 'N/A')
            description = asset.get('description', serial)

            # Filter: Only FortiGate firewalls
            if not self.is_firewall(model):
                continue

            entitlements = asset.get('entitlements')
            if entitlements and isinstance(entitlements, list):
                for entitlement in entitlements:
                    end_date_str = entitlement.get('endDate')
                    if not end_date_str:
                        continue

                    days_remaining = self.calculate_days_until_expiration(end_date_str)

                    if days_remaining is not None and min_days <= days_remaining <= max_days:
                        event_date, event_date_str = self.get_event_date(end_date_str)

                        if event_date:
                            if serial not in devices_dict:
                                devices_dict[serial] = {
                                    'serial': serial,
                                    'model': model,
                                    'description': description,
                                    'services': [],
                                    'earliest_expiration': end_date_str,
                                    'earliest_days': days_remaining,
                                    'event_date': event_date,
                                    'event_date_str': event_date_str
                                }

                            service_info = {
                                'service': entitlement.get('typeDesc', 'N/A'),
                                'level': entitlement.get('levelDesc', 'N/A'),
                                'expiration_date': end_date_str.split('T')[0],
                                'days_remaining': days_remaining
                            }
                            devices_dict[serial]['services'].append(service_info)

                            if days_remaining < devices_dict[serial]['earliest_days']:
                                devices_dict[serial]['earliest_expiration'] = end_date_str
                                devices_dict[serial]['earliest_days'] = days_remaining
                                event_date, event_date_str = self.get_event_date(end_date_str)
                                devices_dict[serial]['event_date'] = event_date
                                devices_dict[serial]['event_date_str'] = event_date_str

        # Convert to list for JSON serialization
        devices_list = []
        for serial, device_data in devices_dict.items():
            device_data['event_date'] = device_data['event_date'].isoformat()
            devices_list.append(device_data)

        return devices_list

    def update_fortinet_data(self):
        """Update Fortinet data from API if configured"""
        if self.fortinet_api.enabled:
            logger.info("Updating Fortinet devices data from API...")
            success = self.fortinet_api.update_devices_file(self.fortinet_data_path)
            if success:
                logger.info("Fortinet data updated successfully")
            else:
                logger.warning("Failed to update Fortinet data, using existing file")
        else:
            logger.info("Fortinet API not configured, using existing data file")

    def sync_to_calendar(self):
        """Synchronize expiring devices to Zoho calendar"""
        # Update Fortinet data first (if API configured)
        self.update_fortinet_data()

        devices = self.get_expiring_devices()

        logger.info(f"Found {len(devices)} firewall(s) expiring in {self.config['filter_days_min']}-{self.config['filter_days_max']} days")

        created = 0
        skipped = 0
        failed = 0

        for device_data in devices:
            serial = device_data['serial']
            event_date_str = device_data['event_date_str']

            logger.info(f"Processing {serial} - {len(device_data['services'])} services expiring")

            # Check for each technician
            for technician in self.config['technicians']:
                # Check if event already exists
                if self.zoho.check_event_exists(serial, event_date_str, technician['id']):
                    logger.info(f"  Event already exists for {serial} on {event_date_str} - {technician['name']}")
                    skipped += 1
                else:
                    # Create event
                    if self.zoho.create_event(device_data, event_date_str, technician['id'], self.config['event']):
                        logger.info(f"  ✅ Event created for {serial} - {technician['name']}")
                        created += 1
                    else:
                        logger.error(f"  ❌ Failed to create event for {serial} - {technician['name']}")
                        failed += 1

        return {
            'devices_found': len(devices),
            'events_created': created,
            'events_skipped': skipped,
            'events_failed': failed
        }
