# NetBox Population Tool

A Python script to populate a NetBox instance with pre-extracted network infrastructure data.

## Overview

This tool imports a complete network infrastructure dataset into NetBox, including:
- Sites, regions, and locations
- Racks and power infrastructure
- Device types, manufacturers, and platforms
- Devices and virtual machines
- Network interfaces and IP addressing
- Cables and physical connections
- VLANs, prefixes, and aggregates
- Services and circuits

## Features

- ✅ **Idempotent**: Safe to run multiple times without creating duplicates
- ✅ **Dependency-aware**: Creates objects in the correct order (8 tiers)
- ✅ **Manufacturer filtering**: Automatically filters out Arista and Juniper devices
- ✅ **Error handling**: Continues on errors and provides detailed summary
- ✅ **Progress tracking**: Shows real-time status for each object created

## Prerequisites

- Python 3.8 or higher
- Access to a NetBox instance (v4.0+)
- NetBox API token with write permissions

## Installation

1. Clone or download this repository:
   ```bash
   git clone <repository-url>
   cd netbox-population-tool
   ```

2. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

### Basic Usage

Run the script with your NetBox API token:

```bash
python scripts/populate_netbox.py --token YOUR_API_TOKEN
```

### Command-Line Options

```bash
python scripts/populate_netbox.py --help

Options:
  --url URL           NetBox URL (default: http://localhost:8001)
  --token TOKEN       NetBox API token (required)
  --data-dir DIR      Data directory path (default: extracted_data)
  --dry-run          Preview what would be created without making changes
```

### Examples

**Populate a remote NetBox instance:**
```bash
python scripts/populate_netbox.py \
  --url https://netbox.example.com \
  --token YOUR_API_TOKEN
```

**Dry run to preview changes:**
```bash
python scripts/populate_netbox.py \
  --token YOUR_API_TOKEN \
  --dry-run
```

**Use custom data directory:**
```bash
python scripts/populate_netbox.py \
  --token YOUR_API_TOKEN \
  --data-dir /path/to/data
```

## Getting a NetBox API Token

1. Log in to your NetBox instance
2. Navigate to your user profile (top right menu)
3. Click on "API Tokens"
4. Click "Add a token"
5. Give it a name (e.g., "Population Script")
6. Set write permissions: **Yes**
7. Copy the generated token

## What Gets Created

The script creates objects in 8 dependency tiers:

### Tier 0: Foundation (35 objects)
- Tags, manufacturers, platforms
- RIRs, tenants, tenant groups
- Contact roles, contact groups, contacts
- Circuit providers

### Tier 1: Organization (40 objects)
- Regions, site groups, sites
- Locations, rack roles, device roles

### Tier 2: Templates (11 objects)
- Device types, module types
- IPAM roles, VLAN groups
- Circuit types, cluster types, wireless LAN groups

### Tier 3: Infrastructure (23 objects)
- Racks, power panels, power feeds
- Clusters, VLANs, wireless LANs, circuits

### Tier 4: Devices & VMs (13 objects)
- Network devices (routers, switches, access points)
- Virtual machines

### Tier 5: Components (113 objects)
- Network interfaces (51)
- Console ports, power ports, power outlets
- VM interfaces, modules, device bays

### Tier 6: Connectivity (29 objects)
- IP aggregates (3)
- Prefixes (9)
- IP addresses (14) with interface assignments
- Cables (7)

### Tier 7: Services (8 objects)
- Network services (SSH, PostgreSQL, etc.)
- Contact assignments

**Total: 272+ objects**

## Filtered Objects

The script automatically filters out devices and components from these manufacturers:
- **Arista** (e.g., Arista switches)
- **Juniper** (e.g., Juniper EX, SRX devices)

This results in approximately 437 objects being intentionally skipped.

## Data Structure

The `extracted_data/` directory contains JSON files, one per NetBox object type:

```
extracted_data/
├── dcim_site.json              # Sites
├── dcim_device.json            # Devices
├── dcim_interface.json         # Network interfaces
├── ipam_ipaddress.json         # IP addresses
├── ipam_prefix.json            # IP prefixes
├── dcim_cable.json             # Physical cables
└── ... (40+ more files)
```

Each JSON file contains an array of objects with their attributes.

## Expected Output

Successful run example:

```
======================================================================
NetBox Population Script
======================================================================
Target: http://localhost:8001
Source: extracted_data
Mode: LIVE
======================================================================

======================================================================
TIER 0: Foundation
======================================================================

Creating tags... (3 total)
  ⊙ Exists tag: consulting
  ⊙ Exists tag: europe
  ✓ Created tag: Foxtrot

...

======================================================================
SUMMARY
======================================================================
✓ Created:  272
⊙ Skipped:  33 (already exist)
✗ Failed:   437 (filtered devices/components)
======================================================================
```

### Status Symbols

- `✓` **Created** - Object was successfully created
- `⊙` **Exists** - Object already exists (idempotency check)
- `⊘` **Filtered** - Object intentionally skipped (Arista/Juniper)
- `✗` **Failed** - Object creation failed (usually due to missing parent)
- `⚠` **Skipping** - Object type not supported yet

## Idempotency

The script is fully idempotent - you can run it multiple times safely:

- **First run**: Creates all objects
- **Subsequent runs**: Detects existing objects and skips them

This makes it safe to:
- Re-run after failures
- Update the dataset and re-import
- Use in CI/CD pipelines

## Troubleshooting

### "Related object not found"
This usually means a parent object (like a device) was filtered out. This is expected for Arista/Juniper components.

### "Connection refused"
Check that your NetBox instance is running and accessible at the specified URL.

### "Authentication failed"
Verify your API token is correct and has write permissions.

### "Rate limited"
NetBox may be rate-limiting API requests. The script handles this automatically with retries.

## Data Customization

To use your own data:

1. Replace the JSON files in `extracted_data/` with your own
2. Ensure each file follows the same structure as the examples
3. Run the script as normal

## Sites in This Dataset

The included data represents a multi-site network:

- **Amsterdam, Netherlands** (NLAMS01) - Main office with router, switches, APs, and servers
- **Sydney, Australia** (AUSYD01) - Branch office
- **Chicago, USA** (USCHG) - Data center
- **Lisbon, Portugal** (POLIS01) - Branch office
- **London, UK** (GBLON) - Branch office
- **Los Angeles, USA** (USLAX01) - Branch office

## IP Addressing

The dataset includes:
- **Public**: 37.251.64.0/29 (ISP-assigned)
- **Private**: 192.168.0.0/22 (internal networks)
  - Data VLAN: 192.168.0.0/25
  - Voice VLAN: 192.168.0.128/25
  - Branch WiFi: 192.168.1.0/25
  - Guest WiFi: 192.168.1.128/25
  - Network Management: 192.168.2.0/26
  - Point-to-Point: 192.168.2.64/30

## License

This tool is provided as-is for use with NetBox.

## Support

For issues or questions about:
- **NetBox**: See [NetBox documentation](https://docs.netbox.dev/)
- **This script**: Open an issue in the repository

## Version Information

- **NetBox Compatibility**: v4.0+
- **Python Version**: 3.8+
- **Last Updated**: 2026-02-09
