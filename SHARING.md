# Sharing This Repository

## Quick Start for Recipients

Your colleagues can use this tool in a few simple steps:

### 1. Clone the Repository

```bash
git clone <repository-url>
cd netbox-population-tool
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Get NetBox API Token

- Log in to NetBox
- Go to User Profile → API Tokens
- Create a new token with **write permissions**
- Copy the token

### 4. Run the Script

```bash
python scripts/populate_netbox.py --url https://your-netbox.com --token YOUR_TOKEN
```

## Sharing Options

### Option 1: GitHub/GitLab (Recommended)

Create a repository on GitHub or GitLab:

```bash
# Create a new repository on GitHub/GitLab first, then:
git remote add origin https://github.com/yourusername/netbox-population-tool.git
git push -u origin master
```

Share the repository URL with your colleagues.

### Option 2: Zip File

```bash
# Create a zip file excluding .git directory
cd ..
zip -r netbox-population-tool.zip netbox-population-tool -x "*.git*"
```

Send the `netbox-population-tool.zip` file to your colleagues.

### Option 3: Internal Git Server

```bash
# Push to your organization's Git server
git remote add origin https://git.yourcompany.com/netbox-population-tool.git
git push -u origin master
```

## What's Included

- ✅ `scripts/populate_netbox.py` - The main population script
- ✅ `extracted_data/` - 50+ JSON files with network data
- ✅ `README.md` - Complete usage documentation
- ✅ `requirements.txt` - Python dependencies
- ✅ `.gitignore` - Excludes unnecessary files

## Repository Size

- **Total size**: ~1.2 MB
- **54 files** including all data and documentation
- **29,485+ lines** of code and data

## Security Note

⚠️ **Important**: This repository contains network infrastructure data including:
- IP addresses and network topology
- Device names and locations
- VLAN configurations

Consider using a **private repository** if this data is sensitive.

## Support

Recipients can refer to the main `README.md` for:
- Detailed usage instructions
- Troubleshooting tips
- Command-line options
- Expected output and behavior
