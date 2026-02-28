#!/bin/bash

# LuminaLearn Mainnet Deployment Script
# This script deploys Soroban contracts to Stellar mainnet
#
# IMPORTANT: This script is for production deployment using REAL XLM
# Make sure you have:
# 1. Thoroughly tested on testnet
# 2. Completed security audit
# 3. Sufficient XLM for deployment (typically 10-50 XLM)
# 4. Backed up all secret keys securely

set -e  # Exit on error

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}========================================${NC}"
echo -e "${YELLOW}  LuminaLearn Mainnet Deployment${NC}"
echo -e "${YELLOW}========================================${NC}"
echo ""

# Safety check
echo -e "${RED}⚠️  WARNING: This will deploy to MAINNET using REAL XLM${NC}"
echo -e "${RED}⚠️  All transactions are IRREVERSIBLE${NC}"
echo ""
read -p "Are you sure you want to continue? (yes/no): " confirm

if [ "$confirm" != "yes" ]; then
    echo "Deployment cancelled."
    exit 0
fi

# Check if stellar CLI is installed
if ! command -v stellar &> /dev/null; then
    echo -e "${RED}Error: stellar CLI not found${NC}"
    echo "Install it with: cargo install --locked stellar-cli"
    exit 1
fi

# Navigate to contract directory
cd "$(dirname "$0")/../LuminaLearnContract" || exit 1

echo -e "${GREEN}Step 1: Building contracts...${NC}"
stellar contract build

if [ $? -ne 0 ]; then
    echo -e "${RED}Build failed!${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Build successful${NC}"
echo ""

# Check for mainnet identity
echo -e "${GREEN}Step 2: Checking mainnet identity...${NC}"

read -p "Enter your mainnet deployer identity name (e.g., 'mainnet-deployer'): " IDENTITY_NAME

if ! stellar keys address "$IDENTITY_NAME" &> /dev/null; then
    echo -e "${YELLOW}Identity not found. Creating new identity...${NC}"
    stellar keys generate "$IDENTITY_NAME" --network mainnet

    PUBKEY=$(stellar keys address "$IDENTITY_NAME")
    echo -e "${YELLOW}New identity created: $PUBKEY${NC}"
    echo -e "${RED}⚠️  IMPORTANT: Fund this account with XLM before continuing${NC}"
    echo -e "${YELLOW}Minimum required: 10 XLM (recommended: 50 XLM for safety)${NC}"
    echo ""
    read -p "Press enter once account is funded..."
else
    PUBKEY=$(stellar keys address "$IDENTITY_NAME")
    echo -e "${GREEN}Using existing identity: $PUBKEY${NC}"
fi

echo ""

# Deploy attendance contract
echo -e "${GREEN}Step 3: Deploying attendance contract to mainnet...${NC}"

ATTENDANCE_WASM="target/wasm32v1-none/release/attendance.wasm"

if [ ! -f "$ATTENDANCE_WASM" ]; then
    echo -e "${RED}Error: Attendance WASM not found at $ATTENDANCE_WASM${NC}"
    exit 1
fi

echo "Deploying attendance contract..."
ATTENDANCE_CONTRACT_ID=$(stellar contract deploy \
    --wasm "$ATTENDANCE_WASM" \
    --source "$IDENTITY_NAME" \
    --network mainnet 2>&1 | tee /dev/tty | tail -1)

if [ -z "$ATTENDANCE_CONTRACT_ID" ]; then
    echo -e "${RED}Failed to deploy attendance contract${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Attendance contract deployed${NC}"
echo -e "${YELLOW}Contract ID: $ATTENDANCE_CONTRACT_ID${NC}"
echo -e "${YELLOW}Explorer: https://stellar.expert/explorer/public/contract/$ATTENDANCE_CONTRACT_ID${NC}"
echo ""

# Deploy course factory contract
echo -e "${GREEN}Step 4: Deploying course factory contract to mainnet...${NC}"

FACTORY_WASM="target/wasm32v1-none/release/course_factory.wasm"

if [ ! -f "$FACTORY_WASM" ]; then
    echo -e "${YELLOW}Warning: Course factory WASM not found, skipping...${NC}"
    FACTORY_CONTRACT_ID=""
else
    echo "Deploying course factory contract..."
    FACTORY_CONTRACT_ID=$(stellar contract deploy \
        --wasm "$FACTORY_WASM" \
        --source "$IDENTITY_NAME" \
        --network mainnet 2>&1 | tee /dev/tty | tail -1)

    if [ -z "$FACTORY_CONTRACT_ID" ]; then
        echo -e "${RED}Failed to deploy course factory contract${NC}"
    else
        echo -e "${GREEN}✓ Course factory contract deployed${NC}"
        echo -e "${YELLOW}Contract ID: $FACTORY_CONTRACT_ID${NC}"
        echo -e "${YELLOW}Explorer: https://stellar.expert/explorer/public/contract/$FACTORY_CONTRACT_ID${NC}"
    fi
fi

echo ""

# Generate .env configuration
echo -e "${GREEN}Step 5: Generating mainnet configuration...${NC}"

cat > ../mainnet.env << EOF
# LuminaLearn Mainnet Configuration
# Generated: $(date)

# Django Settings
SECRET_KEY=CHANGE_ME_TO_SECURE_RANDOM_KEY
DEBUG=False
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com

# Stellar Mainnet Configuration
STELLAR_NETWORK=mainnet
STELLAR_HORIZON_URL=https://horizon.stellar.org
STELLAR_RPC_URL=https://soroban.stellar.org
STELLAR_CONTRACT_ID=$ATTENDANCE_CONTRACT_ID
STELLAR_FACTORY_CONTRACT_ID=$FACTORY_CONTRACT_ID
STELLAR_ADMIN_SECRET=YOUR_ADMIN_SECRET_HERE

# Database (use production database)
DATABASE_URL=postgresql://user:password@localhost:5432/luminallearn_prod

# Redis
REDIS_URL=redis://localhost:6379/0
EOF

echo -e "${GREEN}✓ Configuration saved to mainnet.env${NC}"
echo ""

# Summary
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  Deployment Summary${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "Deployer: ${YELLOW}$PUBKEY${NC}"
echo -e "Attendance Contract: ${YELLOW}$ATTENDANCE_CONTRACT_ID${NC}"
if [ -n "$FACTORY_CONTRACT_ID" ]; then
    echo -e "Factory Contract: ${YELLOW}$FACTORY_CONTRACT_ID${NC}"
fi
echo ""
echo -e "${YELLOW}Next Steps:${NC}"
echo "1. Update mainnet.env with your actual values"
echo "2. Copy mainnet.env to .env in production"
echo "3. Initialize contracts with admin account"
echo "4. Run migrations: python manage.py migrate"
echo "5. Test thoroughly before going live"
echo ""
echo -e "${GREEN}✓ Deployment complete!${NC}"
