#!/bin/bash
# ============================================================================
# JAYCO Dealer Portal - Azure Deployment Script
# ============================================================================
set -e

# Configuration
RESOURCE_GROUP="${RESOURCE_GROUP:-rg-company-dealer-dev}"
LOCATION="${LOCATION:-eastus2}"
ENVIRONMENT="${ENVIRONMENT:-dev}"
DEPLOY_APIM="${DEPLOY_APIM:-false}"

echo "🚀 Deploying JAYCO Dealer Portal"
echo "   Resource Group: $RESOURCE_GROUP"
echo "   Location: $LOCATION"
echo "   Environment: $ENVIRONMENT"
echo "   Deploy APIM: $DEPLOY_APIM"
echo ""

# Login check
az account show > /dev/null 2>&1 || { echo "Please login with 'az login' first."; exit 1; }

# Create resource group
echo "📦 Creating resource group..."
az group create --name "$RESOURCE_GROUP" --location "$LOCATION" --output none

# Deploy infrastructure
echo "🏗️  Deploying infrastructure (Bicep)..."
az deployment group create \
    --resource-group "$RESOURCE_GROUP" \
    --template-file infra/main.bicep \
    --parameters environment="$ENVIRONMENT" \
    --parameters location="$LOCATION" \
    --parameters deployApim="$DEPLOY_APIM" \
    --output json

# Get outputs
APP_URL=$(az deployment group show \
    --resource-group "$RESOURCE_GROUP" \
    --name "main" \
    --query "properties.outputs.appServiceUrl.value" \
    --output tsv 2>/dev/null || echo "")

echo ""
echo "✅ Deployment complete!"
if [ -n "$APP_URL" ]; then
    echo "   App Service URL: $APP_URL"
fi
echo ""
echo "Next steps:"
echo "  1. Deploy the FastAPI app: az webapp up --name app-company-dealer-$ENVIRONMENT --src-path src/api"
echo "  2. Index documents: python src/indexer/index_documents.py ./data/portal_docs"
echo "  3. Build & deploy frontend: cd src/frontend && npm run build"
