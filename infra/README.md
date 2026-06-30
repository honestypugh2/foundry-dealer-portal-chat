# Infrastructure

Azure Bicep templates for the Dealer Portal, aligned with the [Azure Well-Architected Framework (WAF)](https://learn.microsoft.com/azure/well-architected/).

## Architecture

```
main.bicep                    # Orchestrator — wires all modules together
├── modules/
│   ├── openai.bicep          # Azure OpenAI (GPT-5 + text-embedding-3-large)
│   ├── search.bicep          # Azure AI Search (hybrid: keyword + vector + semantic)
│   ├── storage.bicep         # Blob Storage (raw PDFs + document chunks)
│   ├── documentintelligence.bicep  # Azure Document Intelligence (PDF extraction)
│   ├── appservice.bicep      # App Service (Linux, Python 3.12, FastAPI)
│   ├── apim.bicep            # API Management (production gateway)
│   ├── keyvault.bicep        # Key Vault (RBAC-authorized, diagnostics)
│   ├── monitoring.bicep      # Log Analytics + Application Insights
│   ├── networking.bicep      # VNet, subnets, private endpoints, DNS zones
│   └── roles.bicep           # RBAC role assignments (managed identity + user)
└── parameters/
    ├── dev.bicepparam        # Development environment
    └── prod.bicepparam       # Production environment
```

## Environments

| Aspect | Dev | Prod |
|--------|-----|------|
| App Service | Not deployed (run locally) | P1v3 / PremiumV3 |
| APIM | Not deployed | Consumption tier (public) |
| AI Search | Basic, 1 replica | Standard, 2 replicas (HA) |
| Storage | Standard_LRS | Standard_GRS |
| Network | Public access enabled | Public (identity/policy isolation, no VNet) |
| Key Vault | No purge protection, 7d soft-delete | Purge protection, 90d soft-delete |
| OpenAI capacity | 30K TPM | 80K TPM |
| Log retention | 30 days | 90 days |
| Document Intelligence | F0 (free) | S0 (standard) |
| Simulated mode | true | false |

## Prerequisites

- Azure CLI with Bicep (`az bicep version`)
- An Azure subscription with sufficient quota for OpenAI models
- A resource group created in the target region

## Deployment

### Dev

```bash
az group create --name rg-mydealer-dev --location eastus2

az deployment group create \
  --resource-group rg-mydealer-dev \
  --template-file infra/main.bicep \
  --parameters infra/parameters/dev.bicepparam \
  --parameters principalId=$(az ad signed-in-user show --query id -o tsv)
```

### Prod

```bash
az group create --name rg-mydealer-prod --location eastus2

az deployment group create \
  --resource-group rg-mydealer-prod \
  --template-file infra/main.bicep \
  --parameters infra/parameters/prod.bicepparam \
  --parameters principalId=<SERVICE_PRINCIPAL_OBJECT_ID>
```

### Using Azure Developer CLI (azd)

```bash
# Authenticate
azd auth login

# Provision infrastructure and deploy the application in one step
azd up

# Or run steps individually:
azd provision   # Deploy infrastructure only
azd deploy      # Deploy application code only
```

To target a specific environment:

```bash
azd env new dev
azd env select dev
azd up
```

> **Note:** `azd up` will prompt for environment name, subscription, and location if not already configured.

## RBAC Roles Assigned

The `roles.bicep` module assigns least-privilege roles:

**App Service Managed Identity (prod only):**
| Role | Scope |
|------|-------|
| Cognitive Services OpenAI User | Azure OpenAI |
| Search Index Data Reader | AI Search |
| Search Index Data Contributor | AI Search |
| Storage Blob Data Reader | Storage Account |
| Key Vault Secrets User | Key Vault |
| Cognitive Services User | Document Intelligence |

**AI Search System Identity:**
| Role | Scope |
|------|-------|
| Storage Blob Data Reader | Storage (integrated vectorization) |
| Cognitive Services OpenAI User | Azure OpenAI (embeddings) |

**Deploying User/Service Principal:**
| Role | Scope |
|------|-------|
| Cognitive Services OpenAI User | Azure OpenAI |
| Search Index Data Contributor | AI Search |
| Search Service Contributor | AI Search |
| Storage Blob Data Contributor | Storage Account |
| Key Vault Secrets User | Key Vault |
| Cognitive Services User | Document Intelligence |

## Network Isolation (Prod)

When `useNetworkIsolation = true`:

- A VNet (`10.0.0.0/16`) is created with two subnets:
  - `snet-app` (`10.0.1.0/24`) — App Service VNet integration
  - `snet-pe` (`10.0.2.0/24`) — Private endpoints
- Private endpoints are provisioned for: OpenAI, AI Search, Blob Storage, Key Vault, Document Intelligence
- Private DNS zones link each service to the VNet
- All services set `publicNetworkAccess: Disabled`

## Validating Templates

```bash
# Build (lint) the main template
az bicep build --file infra/main.bicep

# Validate parameter files
az bicep build-params --file infra/parameters/dev.bicepparam
az bicep build-params --file infra/parameters/prod.bicepparam
```
