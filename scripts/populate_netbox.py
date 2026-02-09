#!/usr/bin/env python3
"""
NetBox Population Script
Populates a target NetBox instance from extracted JSON data.
Filters out Arista and Juniper related objects.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Set
import pynetbox
from pynetbox.core.api import Api
from pynetbox.core.response import Record


class NetBoxPopulator:
    """Populates NetBox from JSON data with filtering and error handling."""

    # Manufacturers to filter out
    EXCLUDED_MANUFACTURERS = {'Arista', 'Juniper'}

    # Platforms to filter out
    EXCLUDED_PLATFORMS = {'juniper junos', 'eos', 'nxos'}

    def __init__(self, netbox_url: str, token: str, data_dir: Path, dry_run: bool = False):
        self.netbox_url = netbox_url
        self.token = token
        self.data_dir = data_dir
        self.dry_run = dry_run

        # Initialize NetBox API
        self.nb = pynetbox.api(netbox_url, token=token)
        self.nb.http_session.verify = False

        # Load mappings
        self.id_cache = self._load_json('id_mappings.json')
        self.m2m_data = self._load_json('m2m_mappings.json')

        # Track filtered IDs
        self.filtered_manufacturer_ids: Set[int] = set()
        self.filtered_devicetype_ids: Set[int] = set()
        self.filtered_platform_ids: Set[int] = set()

        # Track created objects
        self.created_count = 0
        self.skipped_count = 0
        self.failed_count = 0
        self.errors: List[Dict] = []

    def _load_json(self, filename: str) -> Dict:
        """Load JSON file from data directory."""
        path = self.data_dir / filename
        if not path.exists():
            return {}
        with open(path, 'r') as f:
            return json.load(f)

    def _load_table_data(self, table_name: str) -> List[Dict]:
        """Load table data from JSON file."""
        path = self.data_dir / f"{table_name}.json"
        if not path.exists():
            return []
        with open(path, 'r') as f:
            return json.load(f)

    def _resolve_fk(self, table: str, fk_id: Optional[int]) -> Optional[str]:
        """Resolve foreign key ID to name using id_cache."""
        if fk_id is None:
            return None
        if table not in self.id_cache:
            return None
        return self.id_cache[table].get(str(fk_id))

    def _should_filter_manufacturer(self, obj: Dict) -> bool:
        """Check if object should be filtered based on manufacturer."""
        if 'name' in obj and obj['name'] in self.EXCLUDED_MANUFACTURERS:
            return True
        if 'manufacturer' in obj:
            mfr_name = self._resolve_fk('dcim_manufacturer', obj['manufacturer'])
            if mfr_name and mfr_name in self.EXCLUDED_MANUFACTURERS:
                return True
        return False

    def _should_filter_platform(self, obj: Dict) -> bool:
        """Check if object should be filtered based on platform."""
        if 'name' in obj and obj['name'].lower() in self.EXCLUDED_PLATFORMS:
            return True
        if 'slug' in obj and obj['slug'].lower() in self.EXCLUDED_PLATFORMS:
            return True
        return False

    def _should_filter_device(self, obj: Dict) -> bool:
        """Check if device should be filtered."""
        # Check device type
        if 'device_type' in obj and obj['device_type'] in self.filtered_devicetype_ids:
            return True
        # Check platform
        if 'platform' in obj and obj['platform'] in self.filtered_platform_ids:
            return True
        return False

    def populate(self):
        """Main population routine - executes all tiers in order."""
        print("=" * 70)
        print("NetBox Population Script")
        print("=" * 70)
        print(f"Target: {self.netbox_url}")
        print(f"Source: {self.data_dir}")
        print(f"Mode: {'DRY RUN' if self.dry_run else 'LIVE'}")
        print("=" * 70)

        # Execute tiers in dependency order
        self._tier_0_foundation()
        self._tier_1_organization()
        self._tier_2_templates()
        self._tier_3_infrastructure()
        self._tier_4_devices()
        self._tier_5_components()
        self._tier_6_connectivity()
        self._tier_7_services()

        # Summary
        self._print_summary()

    def _tier_0_foundation(self):
        """Tier 0: Foundation objects (tags, manufacturers, platforms, etc.)"""
        print("\n" + "=" * 70)
        print("TIER 0: Foundation")
        print("=" * 70)

        # Tags
        self._create_tags()

        # Manufacturers (with filtering)
        self._create_manufacturers()

        # Platforms (with filtering)
        self._create_platforms()

        # RIRs
        self._create_objects('ipam_rir', self.nb.ipam.rirs, ['name', 'slug'])

        # Tenant Groups
        self._create_objects('tenancy_tenantgroup', self.nb.tenancy.tenant_groups, ['name', 'slug'])

        # Tenants
        self._create_objects('tenancy_tenant', self.nb.tenancy.tenants, ['name', 'slug'])

        # Contact Roles
        self._create_objects('tenancy_contactrole', self.nb.tenancy.contact_roles, ['name', 'slug'])

        # Contact Groups
        self._create_contact_groups()

        # Contacts
        self._create_contacts()

        # Circuit Providers
        self._create_objects('circuits_provider', self.nb.circuits.providers, ['name', 'slug'])

    def _tier_1_organization(self):
        """Tier 1: Organizational structure"""
        print("\n" + "=" * 70)
        print("TIER 1: Organization")
        print("=" * 70)

        # Regions
        self._create_objects('dcim_region', self.nb.dcim.regions, ['name', 'slug'])

        # Site Groups
        self._create_objects('dcim_sitegroup', self.nb.dcim.site_groups, ['name', 'slug'])

        # Sites
        self._create_sites()

        # Locations
        self._create_locations()

        # Rack Roles
        self._create_objects('dcim_rackrole', self.nb.dcim.rack_roles, ['name', 'slug'])

        # Device Roles
        self._create_objects('dcim_devicerole', self.nb.dcim.device_roles, ['name', 'slug'])

    def _tier_2_templates(self):
        """Tier 2: Templates and reference data"""
        print("\n" + "=" * 70)
        print("TIER 2: Templates")
        print("=" * 70)

        # Device Types (with filtering)
        self._create_device_types()

        # Module Types (with filtering)
        self._create_module_types()

        # IPAM Roles
        self._create_objects('ipam_role', self.nb.ipam.roles, ['name', 'slug'])

        # VLAN Groups
        self._create_vlan_groups()

        # Circuit Types
        self._create_objects('circuits_circuittype', self.nb.circuits.circuit_types, ['name', 'slug'])

        # Cluster Types
        self._create_objects('virtualization_clustertype', self.nb.virtualization.cluster_types, ['name', 'slug'])

        # Wireless LAN Groups
        self._create_objects('wireless_wirelesslangroup', self.nb.wireless.wireless_lan_groups, ['name', 'slug'])

    def _tier_3_infrastructure(self):
        """Tier 3: Physical infrastructure"""
        print("\n" + "=" * 70)
        print("TIER 3: Infrastructure")
        print("=" * 70)

        # Racks (without location due to ambiguous names)
        self._create_racks()

        # Power Panels
        self._create_power_panels()

        # Power Feeds
        self._create_power_feeds()

        # Clusters
        self._create_clusters()

        # VLANs
        self._create_vlans()

        # Wireless LANs
        self._create_wireless_lans()

        # Circuits
        self._create_circuits()

    def _tier_4_devices(self):
        """Tier 4: Devices and VMs (without primary IPs)"""
        print("\n" + "=" * 70)
        print("TIER 4: Devices and VMs")
        print("=" * 70)

        # Devices (with filtering)
        self._create_devices()

        # Virtual Machines
        self._create_vms()

    def _tier_5_components(self):
        """Tier 5: Device components"""
        print("\n" + "=" * 70)
        print("TIER 5: Components")
        print("=" * 70)

        # Interfaces
        self._create_interfaces()

        # Console Ports
        self._create_console_ports()

        # Console Server Ports
        self._create_console_server_ports()

        # Power Ports
        self._create_power_ports()

        # Power Outlets
        self._create_power_outlets()

        # Front Ports
        self._create_objects('dcim_frontport', self.nb.dcim.front_ports, ['name'])

        # Rear Ports
        self._create_objects('dcim_rearport', self.nb.dcim.rear_ports, ['name'])

        # Module Bays
        self._create_objects('dcim_modulebay', self.nb.dcim.module_bays, ['name'])

        # VM Interfaces
        self._create_vm_interfaces()

    def _tier_6_connectivity(self):
        """Tier 6: Connectivity and IP addressing"""
        print("\n" + "=" * 70)
        print("TIER 6: Connectivity")
        print("=" * 70)

        # Aggregates
        self._create_aggregates()

        # Prefixes
        self._create_prefixes()

        # IP Addresses
        self._create_ip_addresses()

        # Cables
        self._create_cables()

        # Circuit Terminations
        self._create_circuit_terminations()

    def _tier_7_services(self):
        """Tier 7: Services"""
        print("\n" + "=" * 70)
        print("TIER 7: Services")
        print("=" * 70)

        # Services
        self._create_services()

    def _create_tags(self):
        """Create tags."""
        data = self._load_table_data('extras_tag')
        print(f"\nCreating tags... ({len(data)} total)")

        for obj in data:
            self._create_object(
                name='tag',
                endpoint=self.nb.extras.tags,
                data={
                    'name': obj['name'],
                    'slug': obj['slug'],
                    'color': obj.get('color', '9e9e9e'),
                    'description': obj.get('description', ''),
                }
            )

    def _create_manufacturers(self):
        """Create manufacturers (with filtering)."""
        data = self._load_table_data('dcim_manufacturer')
        print(f"\nCreating manufacturers... ({len(data)} total)")

        for obj in data:
            # Filter Arista and Juniper
            if self._should_filter_manufacturer(obj):
                self.filtered_manufacturer_ids.add(obj['id'])
                print(f"  ⊘ Filtered manufacturer: {obj['name']}")
                continue

            self._create_object(
                name='manufacturer',
                endpoint=self.nb.dcim.manufacturers,
                data={
                    'name': obj['name'],
                    'slug': obj['slug'],
                    'description': obj.get('description', ''),
                }
            )

    def _create_platforms(self):
        """Create platforms (with filtering)."""
        data = self._load_table_data('dcim_platform')
        print(f"\nCreating platforms... ({len(data)} total)")

        for obj in data:
            # Filter Juniper and Arista platforms
            if self._should_filter_platform(obj):
                self.filtered_platform_ids.add(obj['id'])
                print(f"  ⊘ Filtered platform: {obj['name']}")
                continue

            # Skip if manufacturer is filtered
            if obj.get('manufacturer') in self.filtered_manufacturer_ids:
                self.filtered_platform_ids.add(obj['id'])
                print(f"  ⊘ Filtered platform (manufacturer): {obj['name']}")
                continue

            data_dict = {
                'name': obj['name'],
                'slug': obj['slug'],
                'description': obj.get('description', ''),
            }

            # Add manufacturer if present
            if obj.get('manufacturer'):
                mfr_name = self._resolve_fk('dcim_manufacturer', obj['manufacturer'])
                if mfr_name:
                    data_dict['manufacturer'] = {'name': mfr_name}

            self._create_object(
                name='platform',
                endpoint=self.nb.dcim.platforms,
                data=data_dict
            )

    def _create_contact_groups(self):
        """Create contact groups with existence check."""
        data = self._load_table_data('tenancy_contactgroup')
        print(f"\nCreating tenancy_contactgroup... ({len(data)} total)")

        for obj in data:
            # Check if already exists (no unique constraint, must check manually)
            existing = self.nb.tenancy.contact_groups.get(name=obj['name'])
            if existing:
                print(f"  ⊙ Exists tenancy_contactgroup: {obj['name']}")
                self.skipped_count += 1
                continue

            data_dict = {
                'name': obj['name'],
                'slug': obj['slug'],
            }
            if obj.get('description'):
                data_dict['description'] = obj['description']

            self._create_object(
                name='tenancy_contactgroup',
                endpoint=self.nb.tenancy.contact_groups,
                data=data_dict
            )

    def _create_contacts(self):
        """Create contacts with existence check."""
        data = self._load_table_data('tenancy_contact')
        print(f"\nCreating tenancy_contact... ({len(data)} total)")

        for obj in data:
            # Check if already exists (no unique constraint, must check manually)
            existing = self.nb.tenancy.contacts.get(name=obj['name'])
            if existing:
                print(f"  ⊙ Exists tenancy_contact: {obj['name']}")
                self.skipped_count += 1
                continue

            data_dict = {
                'name': obj['name'],
            }
            if obj.get('email'):
                data_dict['email'] = obj['email']
            if obj.get('phone'):
                data_dict['phone'] = obj['phone']
            if obj.get('address'):
                data_dict['address'] = obj['address']

            self._create_object(
                name='tenancy_contact',
                endpoint=self.nb.tenancy.contacts,
                data=data_dict
            )

    def _create_sites(self):
        """Create sites."""
        data = self._load_table_data('dcim_site')
        print(f"\nCreating sites... ({len(data)} total)")

        for obj in data:
            data_dict = {
                'name': obj['name'],
                'slug': obj['slug'],
                'status': obj.get('status', 'active'),
                'description': obj.get('description', ''),
            }

            # Add optional FKs
            if obj.get('region'):
                region_name = self._resolve_fk('dcim_region', obj['region'])
                if region_name:
                    data_dict['region'] = {'name': region_name}

            if obj.get('group'):
                group_name = self._resolve_fk('dcim_sitegroup', obj['group'])
                if group_name:
                    data_dict['group'] = {'name': group_name}

            if obj.get('tenant'):
                tenant_name = self._resolve_fk('tenancy_tenant', obj['tenant'])
                if tenant_name:
                    data_dict['tenant'] = {'name': tenant_name}

            self._create_object(
                name='site',
                endpoint=self.nb.dcim.sites,
                data=data_dict
            )

    def _create_locations(self):
        """Create locations."""
        data = self._load_table_data('dcim_location')
        print(f"\nCreating locations... ({len(data)} total)")

        for obj in data:
            site_name = self._resolve_fk('dcim_site', obj['site'])
            if not site_name:
                continue

            data_dict = {
                'name': obj['name'],
                'slug': obj['slug'],
                'site': {'name': site_name},
                'status': obj.get('status', 'active'),
                'description': obj.get('description', ''),
            }

            self._create_object(
                name='location',
                endpoint=self.nb.dcim.locations,
                data=data_dict
            )

    def _create_device_types(self):
        """Create device types (with filtering)."""
        data = self._load_table_data('dcim_devicetype')
        print(f"\nCreating device types... ({len(data)} total)")

        for obj in data:
            # Filter if manufacturer is filtered
            if obj.get('manufacturer') in self.filtered_manufacturer_ids:
                self.filtered_devicetype_ids.add(obj['id'])
                print(f"  ⊘ Filtered device type: {obj['model']}")
                continue

            mfr_name = self._resolve_fk('dcim_manufacturer', obj['manufacturer'])
            if not mfr_name:
                continue

            data_dict = {


                'model': obj['model'],


                'slug': obj['slug'],


                'manufacturer': {'name': mfr_name},
                'u_height': obj.get('u_height', 1),
                'is_full_depth': obj.get('is_full_depth', False),
            }

            # Optional fields
            if obj.get('part_number'):
                data_dict['part_number'] = obj['part_number']
            if obj.get('airflow'):
                data_dict['airflow'] = obj['airflow']

            self._create_object(
                name='device_type',
                endpoint=self.nb.dcim.device_types,
                data=data_dict
            )

    def _create_module_types(self):
        """Create module types (with filtering)."""
        data = self._load_table_data('dcim_moduletype')
        print(f"\nCreating module types... ({len(data)} total)")

        for obj in data:
            # Filter if manufacturer is filtered
            if obj.get('manufacturer') in self.filtered_manufacturer_ids:
                print(f"  ⊘ Filtered module type: {obj['model']}")
                continue

            mfr_name = self._resolve_fk('dcim_manufacturer', obj['manufacturer'])
            if not mfr_name:
                continue

            data_dict = {


                'model': obj['model'],


                'manufacturer': {'name': mfr_name},
            }

            if obj.get('part_number'):
                data_dict['part_number'] = obj['part_number']

            self._create_object(
                name='module_type',
                endpoint=self.nb.dcim.module_types,
                data=data_dict
            )

    def _create_vlan_groups(self):
        """Create VLAN groups."""
        data = self._load_table_data('ipam_vlangroup')
        print(f"\nCreating VLAN groups... ({len(data)} total)")

        for obj in data:
            # Check if VLAN group already exists to avoid duplicates
            try:
                existing = list(self.nb.ipam.vlan_groups.filter(name=obj['name']))
                if existing:
                    print(f"  ⊙ Exists vlan_group: {obj['name']}")
                    self.skipped_count += 1
                    continue
            except Exception as e:
                # If filter fails, continue with creation attempt
                pass

            data_dict = {
                'name': obj['name'],
                'slug': obj['slug'],
            }

            # Add site if present
            if obj.get('site'):
                site_name = self._resolve_fk('dcim_site', obj['site'])
                if site_name:
                    data_dict['scope_type'] = 'dcim.site'
                    data_dict['scope_id'] = self.nb.dcim.sites.get(name=site_name).id

            self._create_object(
                name='vlan_group',
                endpoint=self.nb.ipam.vlan_groups,
                data=data_dict
            )

    def _create_racks(self):
        """Create racks (without location due to ambiguous names)."""
        data = self._load_table_data('dcim_rack')
        print(f"\nCreating racks... ({len(data)} total)")

        for obj in data:
            site_name = self._resolve_fk('dcim_site', obj['site'])
            if not site_name:
                continue

            # Check if rack already exists to avoid duplicates
            try:
                existing = list(self.nb.dcim.racks.filter(name=obj['name']))
                # Filter by site name in the results
                existing = [r for r in existing if r.site.name == site_name]
                if existing:
                    print(f"  ⊙ Exists rack: {obj['name']}")
                    self.skipped_count += 1
                    continue
            except Exception as e:
                # If filter fails, continue with creation attempt
                pass

            data_dict = {
                'name': obj['name'],
                'site': {'name': site_name},
                'status': obj.get('status', 'active'),
            }

            # Add optional fields
            if obj.get('role'):
                role_name = self._resolve_fk('dcim_rackrole', obj['role'])
                if role_name:
                    data_dict['role'] = {'name': role_name}

            if obj.get('tenant'):
                tenant_name = self._resolve_fk('tenancy_tenant', obj['tenant'])
                if tenant_name:
                    data_dict['tenant'] = {'name': tenant_name}

            if obj.get('u_height'):
                data_dict['u_height'] = obj['u_height']

            # Note: Omitting location due to ambiguous names

            self._create_object(
                name='rack',
                endpoint=self.nb.dcim.racks,
                data=data_dict
            )

    def _create_power_panels(self):
        """Create power panels."""
        data = self._load_table_data('dcim_powerpanel')
        print(f"\nCreating power panels... ({len(data)} total)")

        for obj in data:
            site_name = self._resolve_fk('dcim_site', obj['site'])
            if not site_name:
                continue

            data_dict = {
                'name': obj['name'],
                'site': {'name': site_name},
            }

            self._create_object(
                name='power_panel',
                endpoint=self.nb.dcim.power_panels,
                data=data_dict
            )

    def _create_power_feeds(self):
        """Create power feeds."""
        data = self._load_table_data('dcim_powerfeed')
        print(f"\nCreating power feeds... ({len(data)} total)")

        for obj in data:
            power_panel_name = self._resolve_fk('dcim_powerpanel', obj['power_panel'])
            if not power_panel_name:
                continue

            data_dict = {
                'name': obj['name'],
                'power_panel': {'name': power_panel_name},
                'status': obj.get('status', 'active'),
            }

            # Note: Omitting rack due to lookup complexity

            self._create_object(
                name='power_feed',
                endpoint=self.nb.dcim.power_feeds,
                data=data_dict
            )

    def _create_clusters(self):
        """Create clusters."""
        data = self._load_table_data('virtualization_cluster')
        print(f"\nCreating clusters... ({len(data)} total)")

        for obj in data:
            cluster_type_name = self._resolve_fk('virtualization_clustertype', obj['type'])
            if not cluster_type_name:
                continue

            # Check if cluster already exists to avoid duplicates
            try:
                existing = list(self.nb.virtualization.clusters.filter(name=obj['name']))
                if existing:
                    print(f"  ⊙ Exists cluster: {obj['name']}")
                    self.skipped_count += 1
                    continue
            except Exception as e:
                # If filter fails, continue with creation attempt
                pass

            data_dict = {
                'name': obj['name'],
                'type': {'name': cluster_type_name},
            }

            # Add site if present
            if obj.get('site'):
                site_name = self._resolve_fk('dcim_site', obj['site'])
                if site_name:
                    data_dict['site'] = {'name': site_name}

            self._create_object(
                name='cluster',
                endpoint=self.nb.virtualization.clusters,
                data=data_dict
            )

    def _create_vlans(self):
        """Create VLANs."""
        data = self._load_table_data('ipam_vlan')
        print(f"\nCreating VLANs... ({len(data)} total)")

        for obj in data:
            data_dict = {
                'name': obj['name'],
                'vid': obj['vid'],
                'status': obj.get('status', 'active'),
            }

            # Add site if present
            if obj.get('site'):
                site_name = self._resolve_fk('dcim_site', obj['site'])
                if site_name:
                    data_dict['site'] = {'name': site_name}

            # Add group if present
            if obj.get('group'):
                group_name = self._resolve_fk('ipam_vlangroup', obj['group'])
                if group_name:
                    data_dict['group'] = {'name': group_name}

            # Add role if present
            if obj.get('role'):
                role_name = self._resolve_fk('ipam_role', obj['role'])
                if role_name:
                    data_dict['role'] = {'name': role_name}

            self._create_object(
                name='vlan',
                endpoint=self.nb.ipam.vlans,
                data=data_dict
            )

    def _create_circuits(self):
        """Create circuits."""
        data = self._load_table_data('circuits_circuit')
        print(f"\nCreating circuits... ({len(data)} total)")

        for obj in data:
            provider_name = self._resolve_fk('circuits_provider', obj['provider'])
            circuit_type_name = self._resolve_fk('circuits_circuittype', obj['type'])

            if not provider_name or not circuit_type_name:
                continue

            data_dict = {
                'cid': obj['cid'],
                'provider': {'name': provider_name},
                'type': {'name': circuit_type_name},
                'status': obj.get('status', 'active'),
            }

            self._create_object(
                name='circuit',
                endpoint=self.nb.circuits.circuits,
                data=data_dict
            )

    def _create_wireless_lans(self):
        """Create wireless LANs."""
        data = self._load_table_data('wireless_wirelesslan')
        print(f"\nCreating wireless LANs... ({len(data)} total)")

        for obj in data:
            # Check if wireless LAN already exists (by SSID and group)
            group_name = self._resolve_fk('wireless_wirelesslangroup', obj.get('group'))

            try:
                # Check if already exists by SSID only (simplest approach)
                existing = list(self.nb.wireless.wireless_lans.filter(ssid=obj['ssid']))

                if existing:
                    print(f"  ⊙ Exists wireless_lan: {obj['ssid']}")
                    self.skipped_count += 1
                    continue
            except Exception:
                pass

            data_dict = {
                'ssid': obj['ssid'],
                'status': obj.get('status', 'active'),
            }

            # Add optional fields
            if group_name:
                data_dict['group'] = {'name': group_name}

            if obj.get('description'):
                data_dict['description'] = obj['description']

            if obj.get('tenant'):
                tenant_name = self._resolve_fk('tenancy_tenant', obj['tenant'])
                if tenant_name:
                    data_dict['tenant'] = {'name': tenant_name}

            if obj.get('vlan'):
                # Resolve VLAN by ID, then look it up in NetBox by VID
                vlan_vid = None
                vlan_site = None
                vlan_data = self._load_table_data('ipam_vlan')
                for vlan in vlan_data:
                    if vlan['id'] == obj['vlan']:
                        vlan_vid = vlan['vid']
                        if vlan.get('site'):
                            vlan_site = self._resolve_fk('dcim_site', vlan['site'])
                        break

                if vlan_vid:
                    # Look up VLAN in NetBox by vid and optionally site
                    try:
                        if vlan_site:
                            vlan_obj = self.nb.ipam.vlans.get(vid=vlan_vid, site=vlan_site)
                        else:
                            vlan_obj = self.nb.ipam.vlans.get(vid=vlan_vid)

                        if vlan_obj:
                            data_dict['vlan'] = vlan_obj.id
                    except Exception:
                        pass

            if obj.get('auth_type'):
                data_dict['auth_type'] = obj['auth_type']

            if obj.get('auth_cipher'):
                data_dict['auth_cipher'] = obj['auth_cipher']

            if obj.get('auth_psk'):
                data_dict['auth_psk'] = obj['auth_psk']

            self._create_object(
                name='wireless_lan',
                endpoint=self.nb.wireless.wireless_lans,
                data=data_dict
            )

    def _create_circuit_terminations(self):
        """Create circuit terminations."""
        data = self._load_table_data('circuits_circuittermination')
        print(f"\nCreating circuit terminations... ({len(data)} total)")

        # Circuit terminations require a terminating object (interface, device, etc.)
        # Since we don't have cables and can't map interface IDs from source system,
        # we skip these for now
        print(f"  ⚠ Skipping circuit terminations (require terminating objects/cables)")
        self.skipped_count += len(data)

    def _create_devices(self):
        """Create devices (with filtering for Arista/Juniper)."""
        data = self._load_table_data('dcim_device')
        print(f"\nCreating devices... ({len(data)} total)")

        for obj in data:
            # Filter devices with filtered device types or platforms
            if self._should_filter_device(obj):
                device_type_name = self._resolve_fk('dcim_devicetype', obj.get('device_type'))
                print(f"  ⊘ Filtered device: {obj['name']} (type: {device_type_name})")
                continue

            device_type_name = self._resolve_fk('dcim_devicetype', obj['device_type'])
            device_role_name = self._resolve_fk('dcim_devicerole', obj['role'])
            site_name = self._resolve_fk('dcim_site', obj['site'])

            if not all([device_type_name, device_role_name, site_name]):
                continue

            data_dict = {
                'name': obj['name'],
                'device_type': {'slug': device_type_name},  # Use slug as-is from source
                'role': {'name': device_role_name},  # API uses 'role' not 'device_role'
                'site': {'name': site_name},
                'status': obj.get('status', 'active'),
            }

            # Add optional fields
            if obj.get('rack'):
                rack_name = self._resolve_fk('dcim_rack', obj['rack'])
                if rack_name:
                    data_dict['rack'] = {'name': rack_name, 'site': {'name': site_name}}

            if obj.get('position'):
                data_dict['position'] = obj['position']

            if obj.get('face'):
                data_dict['face'] = obj['face']

            if obj.get('platform') and obj['platform'] not in self.filtered_platform_ids:
                platform_name = self._resolve_fk('dcim_platform', obj['platform'])
                if platform_name:
                    data_dict['platform'] = {'name': platform_name}

            if obj.get('tenant'):
                tenant_name = self._resolve_fk('tenancy_tenant', obj['tenant'])
                if tenant_name:
                    data_dict['tenant'] = {'name': tenant_name}

            if obj.get('serial'):
                data_dict['serial'] = obj['serial']

            if obj.get('asset_tag'):
                data_dict['asset_tag'] = obj['asset_tag']

            if obj.get('airflow'):
                data_dict['airflow'] = obj['airflow']

            # Note: Omitting location due to ambiguous names

            self._create_object(
                name='device',
                endpoint=self.nb.dcim.devices,
                data=data_dict
            )

    def _create_vms(self):
        """Create virtual machines."""
        data = self._load_table_data('virtualization_virtualmachine')
        print(f"\nCreating VMs... ({len(data)} total)")

        for obj in data:
            cluster_name = self._resolve_fk('virtualization_cluster', obj['cluster'])
            if not cluster_name:
                continue

            data_dict = {
                'name': obj['name'],
                'cluster': {'name': cluster_name},
                'status': obj.get('status', 'active'),
            }

            # Add optional fields
            if obj.get('vcpus'):
                data_dict['vcpus'] = obj['vcpus']

            if obj.get('memory'):
                data_dict['memory'] = obj['memory']

            if obj.get('disk'):
                data_dict['disk'] = obj['disk']

            self._create_object(
                name='vm',
                endpoint=self.nb.virtualization.virtual_machines,
                data=data_dict
            )

    def _create_interfaces(self):
        """Create device interfaces (skip for filtered devices)."""
        data = self._load_table_data('dcim_interface')
        print(f"\nCreating interfaces... ({len(data)} total)")

        for obj in data:
            # Skip if device is filtered
            device_name = self._resolve_fk('dcim_device', obj['device'])
            if not device_name:
                continue

            data_dict = {
                'device': {'name': device_name},
                'name': obj['name'],
                'type': obj.get('type', '1000base-t'),
            }

            # Add optional fields
            if obj.get('enabled') is not None:
                data_dict['enabled'] = obj['enabled']

            if obj.get('mtu'):
                data_dict['mtu'] = obj['mtu']

            if obj.get('mode'):
                data_dict['mode'] = obj['mode']

            if obj.get('description'):
                data_dict['description'] = obj['description']

            self._create_object(
                name='interface',
                endpoint=self.nb.dcim.interfaces,
                data=data_dict
            )

    def _create_console_ports(self):
        """Create console ports."""
        data = self._load_table_data('dcim_consoleport')
        print(f"\nCreating console ports... ({len(data)} total)")

        for obj in data:
            device_name = self._resolve_fk('dcim_device', obj['device'])
            if not device_name:
                continue

            data_dict = {
                'device': {'name': device_name},
                'name': obj['name'],
                'type': obj.get('type', 'rj-45'),
            }

            self._create_object(
                name='console_port',
                endpoint=self.nb.dcim.console_ports,
                data=data_dict
            )

    def _create_console_server_ports(self):
        """Create console server ports."""
        data = self._load_table_data('dcim_consoleserverport')
        print(f"\nCreating console server ports... ({len(data)} total)")

        for obj in data:
            device_name = self._resolve_fk('dcim_device', obj['device'])
            if not device_name:
                continue

            data_dict = {
                'device': {'name': device_name},
                'name': obj['name'],
                'type': obj.get('type', 'rj-45'),
            }

            self._create_object(
                name='console_server_port',
                endpoint=self.nb.dcim.console_server_ports,
                data=data_dict
            )

    def _create_power_ports(self):
        """Create power ports."""
        data = self._load_table_data('dcim_powerport')
        print(f"\nCreating power ports... ({len(data)} total)")

        for obj in data:
            device_name = self._resolve_fk('dcim_device', obj['device'])
            if not device_name:
                continue

            data_dict = {
                'device': {'name': device_name},
                'name': obj['name'],
            }

            self._create_object(
                name='power_port',
                endpoint=self.nb.dcim.power_ports,
                data=data_dict
            )

    def _create_power_outlets(self):
        """Create power outlets."""
        data = self._load_table_data('dcim_poweroutlet')
        print(f"\nCreating power outlets... ({len(data)} total)")

        for obj in data:
            device_name = self._resolve_fk('dcim_device', obj['device'])
            if not device_name:
                continue

            data_dict = {
                'device': {'name': device_name},
                'name': obj['name'],
            }

            self._create_object(
                name='power_outlet',
                endpoint=self.nb.dcim.power_outlets,
                data=data_dict
            )

    def _create_prefixes(self):
        """Create prefixes."""
        data = self._load_table_data('ipam_prefix')
        print(f"\nCreating prefixes... ({len(data)} total)")

        for obj in data:
            data_dict = {
                'prefix': obj['prefix'],
                'status': obj.get('status', 'active'),
            }

            # Add optional fields
            if obj.get('site'):
                site_name = self._resolve_fk('dcim_site', obj['site'])
                if site_name:
                    data_dict['site'] = {'name': site_name}

            # VLAN needs special handling - needs name AND site to be unique
            if obj.get('vlan'):
                vlan_name = self._resolve_fk('ipam_vlan', obj['vlan'])
                site_name = data_dict.get('site', {}).get('name') if 'site' in data_dict else None
                if vlan_name and site_name:
                    # Look up VLAN by name and site
                    data_dict['vlan'] = {'name': vlan_name, 'site': {'name': site_name}}
                elif vlan_name:
                    # Try just by name (may fail if ambiguous)
                    data_dict['vlan'] = {'name': vlan_name}

            if obj.get('role'):
                role_name = self._resolve_fk('ipam_role', obj['role'])
                if role_name:
                    data_dict['role'] = {'name': role_name}

            if obj.get('tenant'):
                tenant_name = self._resolve_fk('tenancy_tenant', obj['tenant'])
                if tenant_name:
                    data_dict['tenant'] = {'name': tenant_name}

            if obj.get('description'):
                data_dict['description'] = obj['description']

            self._create_object(
                name='prefix',
                endpoint=self.nb.ipam.prefixes,
                data=data_dict
            )

    def _create_aggregates(self):
        """Create IP aggregates."""
        data = self._load_table_data('ipam_aggregate')
        print(f"\nCreating ipam_aggregate... ({len(data)} total)")

        for obj in data:
            rir_name = self._resolve_fk('ipam_rir', obj['rir'])

            if not rir_name:
                continue

            data_dict = {
                'prefix': obj['prefix'],
                'rir': {'name': rir_name},
            }

            # Add optional fields
            if obj.get('tenant'):
                tenant_name = self._resolve_fk('tenancy_tenant', obj['tenant'])
                if tenant_name:
                    data_dict['tenant'] = {'name': tenant_name}

            if obj.get('description'):
                data_dict['description'] = obj['description']

            if obj.get('date_added'):
                data_dict['date_added'] = obj['date_added']

            self._create_object(
                name='ipam_aggregate',
                endpoint=self.nb.ipam.aggregates,
                data=data_dict
            )

    def _create_ip_addresses(self):
        """Create IP addresses."""
        data = self._load_table_data('ipam_ipaddress')
        print(f"\nCreating IP addresses... ({len(data)} total)")

        for obj in data:
            data_dict = {
                'address': obj['address'],
                'status': obj.get('status', 'active'),
            }

            # Add optional fields
            if obj.get('tenant'):
                tenant_name = self._resolve_fk('tenancy_tenant', obj['tenant'])
                if tenant_name:
                    data_dict['tenant'] = {'name': tenant_name}

            if obj.get('description'):
                data_dict['description'] = obj['description']

            # Handle interface/VM interface assignments
            if obj.get('assigned_object_type') and obj.get('assigned_object_id'):
                assigned_type = obj['assigned_object_type']
                assigned_id = obj['assigned_object_id']

                if assigned_type == 'dcim.interface':
                    # Resolve interface from source data
                    interface_data = self._load_table_data('dcim_interface')
                    for intf in interface_data:
                        if intf['id'] == assigned_id:
                            # Get interface name and device
                            intf_name = intf['name']
                            device_name = self._resolve_fk('dcim_device', intf['device'])

                            if device_name:
                                # Look up interface in target NetBox
                                try:
                                    target_intf = self.nb.dcim.interfaces.get(
                                        name=intf_name,
                                        device=device_name
                                    )
                                    if target_intf:
                                        data_dict['assigned_object_type'] = 'dcim.interface'
                                        data_dict['assigned_object_id'] = target_intf.id
                                except Exception:
                                    pass
                            break

                elif assigned_type == 'virtualization.vminterface':
                    # Resolve VM interface from source data
                    vmintf_data = self._load_table_data('virtualization_vminterface')
                    for vmintf in vmintf_data:
                        if vmintf['id'] == assigned_id:
                            # Get VM interface name and VM
                            vmintf_name = vmintf['name']
                            vm_name = self._resolve_fk('virtualization_virtualmachine', vmintf['virtual_machine'])

                            if vm_name:
                                # Look up VM interface in target NetBox
                                try:
                                    target_vmintf = self.nb.virtualization.interfaces.get(
                                        name=vmintf_name,
                                        virtual_machine=vm_name
                                    )
                                    if target_vmintf:
                                        data_dict['assigned_object_type'] = 'virtualization.vminterface'
                                        data_dict['assigned_object_id'] = target_vmintf.id
                                except Exception:
                                    pass
                            break

            self._create_object(
                name='ip_address',
                endpoint=self.nb.ipam.ip_addresses,
                data=data_dict
            )

    def _create_cables(self):
        """Create cables."""
        data = self._load_table_data('dcim_cable')
        print(f"\nCreating cables... ({len(data)} total)")

        for obj in data:
            # Resolve terminations
            a_terminations = []
            b_terminations = []

            # Process A-side terminations
            for term in obj.get('a_terminations', []):
                target_obj = self._resolve_termination(term['object_type'], term['object_id'])
                if target_obj:
                    a_terminations.append({
                        'object_type': term['object_type'],
                        'object_id': target_obj.id
                    })

            # Process B-side terminations
            for term in obj.get('b_terminations', []):
                target_obj = self._resolve_termination(term['object_type'], term['object_id'])
                if target_obj:
                    b_terminations.append({
                        'object_type': term['object_type'],
                        'object_id': target_obj.id
                    })

            # Only create cable if both sides have terminations
            if not a_terminations or not b_terminations:
                self.skipped_count += 1
                continue

            data_dict = {
                'a_terminations': a_terminations,
                'b_terminations': b_terminations,
                'type': obj.get('type', ''),
                'status': obj.get('status', 'connected'),
            }

            # Add optional fields
            if obj.get('tenant'):
                tenant_name = self._resolve_fk('tenancy_tenant', obj['tenant'])
                if tenant_name:
                    data_dict['tenant'] = {'name': tenant_name}

            if obj.get('label'):
                data_dict['label'] = obj['label']

            if obj.get('color'):
                data_dict['color'] = obj['color']

            if obj.get('length'):
                data_dict['length'] = obj['length']

            if obj.get('length_unit'):
                data_dict['length_unit'] = obj['length_unit']

            if obj.get('description'):
                data_dict['description'] = obj['description']

            self._create_object(
                name='cable',
                endpoint=self.nb.dcim.cables,
                data=data_dict
            )

    def _resolve_termination(self, object_type, source_object_id):
        """Resolve a cable termination object from source ID to target NetBox object."""
        # Map of object types to their source data and lookup methods
        type_map = {
            'dcim.interface': ('dcim_interface', 'interfaces', 'device'),
            'dcim.consoleport': ('dcim_consoleport', 'console_ports', 'device'),
            'dcim.consoleserverport': ('dcim_consoleserverport', 'console_server_ports', 'device'),
            'dcim.powerport': ('dcim_powerport', 'power_ports', 'device'),
            'dcim.poweroutlet': ('dcim_poweroutlet', 'power_outlets', 'device'),
            'dcim.frontport': ('dcim_frontport', 'front_ports', 'device'),
            'dcim.rearport': ('dcim_rearport', 'rear_ports', 'device'),
        }

        if object_type not in type_map:
            return None

        source_table, endpoint_name, parent_field = type_map[object_type]

        # Load source data
        source_data = self._load_table_data(source_table)

        # Find the object in source data
        source_obj = next((obj for obj in source_data if obj['id'] == source_object_id), None)
        if not source_obj:
            return None

        # Get the object name and parent device
        obj_name = source_obj.get('name')
        parent_id = source_obj.get(parent_field)

        if not obj_name or not parent_id:
            return None

        # Resolve parent device
        parent_name = self._resolve_fk(f'dcim_device', parent_id)
        if not parent_name:
            return None

        # Look up the object in target NetBox
        try:
            endpoint = getattr(self.nb.dcim, endpoint_name)
            target_obj = endpoint.get(name=obj_name, device=parent_name)
            return target_obj
        except Exception:
            return None

    def _create_vm_interfaces(self):
        """Create VM interfaces."""
        data = self._load_table_data('virtualization_vminterface')
        print(f"\nCreating virtualization_vminterface... ({len(data)} total)")

        for obj in data:
            vm_name = self._resolve_fk('virtualization_virtualmachine', obj['virtual_machine'])

            if not vm_name:
                continue

            data_dict = {
                'virtual_machine': {'name': vm_name},
                'name': obj['name'],
                'enabled': obj.get('enabled', True),
            }

            # Add optional fields
            if obj.get('description'):
                data_dict['description'] = obj['description']

            if obj.get('mode'):
                data_dict['mode'] = obj['mode']

            if obj.get('mtu'):
                data_dict['mtu'] = obj['mtu']

            if obj.get('mac_address'):
                data_dict['mac_address'] = obj['mac_address']

            self._create_object(
                name='virtualization_vminterface',
                endpoint=self.nb.virtualization.interfaces,
                data=data_dict
            )

    def _create_services(self):
        """Create services."""
        data = self._load_table_data('ipam_service')
        print(f"\nCreating services... ({len(data)} total)")

        for obj in data:
            # Services can be assigned to either a device OR a virtual machine
            device_name = self._resolve_fk('dcim_device', obj.get('device'))
            vm_name = self._resolve_fk('virtualization_virtualmachine', obj.get('virtual_machine'))

            if not device_name and not vm_name:
                continue

            # Services use generic FK - need to look up parent object ID
            parent_obj = None
            parent_type = None

            if device_name:
                try:
                    parent_obj = self.nb.dcim.devices.get(name=device_name)
                    parent_type = 'dcim.device'
                except Exception:
                    continue
            elif vm_name:
                try:
                    parent_obj = self.nb.virtualization.virtual_machines.get(name=vm_name)
                    parent_type = 'virtualization.virtualmachine'
                except Exception:
                    continue

            if not parent_obj:
                continue

            # Check if service already exists on this parent
            try:
                existing = list(self.nb.ipam.services.filter(
                    name=obj['name'],
                    parent_object_id=parent_obj.id
                ))
                if existing:
                    print(f"  ⊙ Exists service: {obj['name']} on {parent_obj.name}")
                    self.skipped_count += 1
                    continue
            except Exception:
                pass

            data_dict = {
                'name': obj['name'],
                'protocol': obj.get('protocol', 'tcp'),
                'ports': obj['ports'],
                'parent_object_type': parent_type,
                'parent_object_id': parent_obj.id,
            }

            # Add optional fields
            if obj.get('description'):
                data_dict['description'] = obj['description']

            self._create_object(
                name='service',
                endpoint=self.nb.ipam.services,
                data=data_dict
            )

    def _create_objects(self, table_name: str, endpoint, required_fields: List[str]):
        """Generic object creation helper."""
        data = self._load_table_data(table_name)
        if not data:
            return

        print(f"\nCreating {table_name}... ({len(data)} total)")

        for obj in data:
            # Build data dict with required fields
            data_dict = {}
            for field in required_fields:
                if field in obj:
                    data_dict[field] = obj[field]

            self._create_object(
                name=table_name,
                endpoint=endpoint,
                data=data_dict
            )

    def _create_object(self, name: str, endpoint, data: Dict) -> Optional[Record]:
        """Create a single object with error handling."""
        if self.dry_run:
            print(f"  [DRY RUN] Would create {name}: {data.get('name', data)}")
            self.created_count += 1
            return None

        try:
            obj = endpoint.create(data)
            print(f"  ✓ Created {name}: {data.get('name', data)}")
            self.created_count += 1
            return obj
        except pynetbox.RequestError as e:
            error_msg = str(e)
            # Check for various duplicate/uniqueness error patterns
            duplicate_indicators = [
                'already exists',
                'duplicate',
                'must be unique',
                'is violated',
                'constraint',
            ]
            if any(indicator in error_msg.lower() for indicator in duplicate_indicators):
                print(f"  ⊙ Exists {name}: {data.get('name', data)}")
                self.skipped_count += 1
            else:
                print(f"  ✗ Failed {name}: {data.get('name', data)} - {error_msg}")
                self.failed_count += 1
                self.errors.append({
                    'type': name,
                    'data': data,
                    'error': error_msg
                })
            return None
        except Exception as e:
            print(f"  ✗ Error {name}: {data.get('name', data)} - {e}")
            self.failed_count += 1
            self.errors.append({
                'type': name,
                'data': data,
                'error': str(e)
            })
            return None

    def _print_summary(self):
        """Print final summary."""
        print("\n" + "=" * 70)
        print("SUMMARY")
        print("=" * 70)
        print(f"✓ Created:  {self.created_count}")
        print(f"⊙ Skipped:  {self.skipped_count} (already exist)")
        print(f"✗ Failed:   {self.failed_count}")
        print("=" * 70)

        if self.errors:
            print("\nErrors:")
            for error in self.errors[:10]:  # Show first 10
                print(f"  {error['type']}: {error['data'].get('name', error['data'])} - {error['error']}")
            if len(self.errors) > 10:
                print(f"  ... and {len(self.errors) - 10} more errors")


def main():
    parser = argparse.ArgumentParser(description='Populate NetBox from extracted JSON data')
    parser.add_argument('--url', default='http://localhost:8001',
                        help='NetBox URL (default: http://localhost:8001)')
    parser.add_argument('--token', required=True,
                        help='NetBox API token')
    parser.add_argument('--data-dir', type=Path, default='extracted_data',
                        help='Directory containing JSON data files (default: extracted_data)')
    parser.add_argument('--dry-run', action='store_true',
                        help='Preview what would be created without making changes')

    args = parser.parse_args()

    # Validate data directory
    if not args.data_dir.exists():
        print(f"Error: Data directory not found: {args.data_dir}")
        sys.exit(1)

    # Create populator and run
    populator = NetBoxPopulator(
        netbox_url=args.url,
        token=args.token,
        data_dir=args.data_dir,
        dry_run=args.dry_run
    )

    try:
        populator.populate()
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        populator._print_summary()
        sys.exit(1)
    except Exception as e:
        print(f"\n\nFatal error: {e}")
        import traceback
        traceback.print_exc()
        populator._print_summary()
        sys.exit(1)


if __name__ == '__main__':
    main()
