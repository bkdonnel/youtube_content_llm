#!/bin/bash

# Music Production Pipeline - Phase 1 Setup
# Run this script to set up everything automatically

set -e  # Exit on any error

echo "Music Production Pipeline - Phase 1 Setup"
echo "=============================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python 3 is not installed${NC}"
    echo "Please install Python 3.8 or newer first"
    exit 1
fi

echo -e "${GREEN}✓ Python 3 found${NC}"
python3 --version

# Check if we're in the right directory
if [ ! -f "requirements.txt" ]; then
    echo -e "${RED}❌ requirements.txt not found${NC}"
    echo "Make sure you're in the music-production-pipeline directory"
    exit 1
fi

echo -e "${GREEN}✓ requirements.txt found${NC}"

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo ""
    echo " Creating virtual environment..."
    python3 -m venv venv
    echo -e "${GREEN}✓ Virtual environment created${NC}"
else
    echo -e "${YELLOW}⚠ Virtual environment already exists${NC}"
fi

# Activate virtual environment
echo ""
echo "🔌 Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo ""
echo "Upgrading pip..."
pip install --upgrade pip --quiet

# Install requirements
echo ""
echo "Installing packages from requirements.txt..."
echo "   (This may take 2-3 minutes)"
pip install -r requirements.txt --quiet

echo ""
echo -e "${GREEN}✓ All packages installed successfully!${NC}"

# Verify key packages
echo ""
echo " Verifying installation..."
python3 << 'EOF'
import sys
packages = {
    'yt_dlp': 'yt-dlp',
    'openai': 'openai',
    'snowflake.connector': 'snowflake-connector-python',
    'streamlit': 'streamlit',
    'pandas': 'pandas',
    'dotenv': 'python-dotenv'
}

missing = []
for module, name in packages.items():
    try:
        __import__(module)
        print(f'  ✓ {name}')
    except ImportError:
        print(f'  ✗ {name} - MISSING')
        missing.append(name)

if missing:
    print(f'\n Missing packages: {", ".join(missing)}')
    sys.exit(1)
else:
    print('\n All required packages are installed!')
EOF

# Check for .env file
echo ""
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}⚠  .env file not found${NC}"
    if [ -f ".env.template" ]; then
        echo "   Creating .env from template..."
        cp .env.template .env
        echo -e "${YELLOW}   Please edit .env and add your credentials!${NC}"
    else
        echo -e "${RED}   Please create a .env file with your credentials${NC}"
    fi
else
    echo -e "${GREEN}✓ .env file exists${NC}"
fi

# Check if Snowflake tables are created
echo ""
echo " Checking Snowflake setup..."
echo "   Have you created the tables in Snowflake? (y/n)"
read -r snowflake_ready

if [ "$snowflake_ready" = "y" ] || [ "$snowflake_ready" = "Y" ]; then
    echo -e "${GREEN}✓ Snowflake ready${NC}"
else
    echo ""
    echo -e "${YELLOW}⚠  You need to run the Snowflake schema first:${NC}"
    echo "   1. Open Snowflake web UI"
    echo "   2. Run: database/snowflake_schema_single_schema.sql"
    echo "   3. Then come back and run the test script"
    echo ""
fi

# Summary
echo ""
echo "=============================================="
echo "Setup Complete"
echo "=============================================="
echo ""
echo "Next steps:"
echo ""
echo "1. Make sure .env has your credentials:"
echo "   - SNOWFLAKE_ACCOUNT, USER, PASSWORD, etc."
echo "   - OPENAI_API_KEY"
echo ""
echo "2. If not done yet, create Snowflake tables:"
echo "   - Run: database/snowflake_schema_single_schema.sql"
echo ""
echo "3. Run the test pipeline:"
echo "   ${GREEN}source venv/bin/activate${NC}  # Activate venv"
echo "   ${GREEN}python scripts/test_pipeline.py${NC}"
echo ""
echo "4. After test passes, launch Streamlit:"
echo "   ${GREEN}streamlit run streamlit_app_simple.py${NC}"
echo ""
echo "=============================================="
echo ""

# Keep venv activated
echo " Virtual environment is now activated"
echo "  (You should see (venv) in your prompt)"
echo ""