#!/usr/bin/env bash
set -euo pipefail

ENVIRONMENT=${1:-prod}
AWS_REGION=${AWS_REGION:-us-east-1}
PROJECT_NAME="${PROJECT_NAME:-agentforge}"
STATE_BUCKET="${TF_STATE_BUCKET:-${PROJECT_NAME}-terraform-state}"

echo "🚀 Deploying AgentForge infrastructure..."
echo "   Environment: $ENVIRONMENT"
echo "   AWS Region:  $AWS_REGION"
echo "   State Bucket: $STATE_BUCKET"

# ─── Validate required variables ─────────────────────────────────────────────

: "${TF_VAR_db_password:?TF_VAR_db_password is required (min 16 chars)}"
: "${TF_VAR_secret_key:?TF_VAR_secret_key is required (min 32 chars)}"

if [ "${#TF_VAR_db_password}" -lt 16 ]; then
  echo "ERROR: TF_VAR_db_password must be at least 16 characters"
  exit 1
fi

if [ "${#TF_VAR_secret_key}" -lt 32 ]; then
  echo "ERROR: TF_VAR_secret_key must be at least 32 characters"
  exit 1
fi

# ─── Create Terraform state bucket if it doesn't exist ───────────────────────

echo "📦 Ensuring Terraform state bucket exists..."
if ! aws s3api head-bucket --bucket "$STATE_BUCKET" --region "$AWS_REGION" 2>/dev/null; then
  echo "Creating state bucket: $STATE_BUCKET"
  if [ "$AWS_REGION" = "us-east-1" ]; then
    aws s3api create-bucket \
      --bucket "$STATE_BUCKET" \
      --region "$AWS_REGION"
  else
    aws s3api create-bucket \
      --bucket "$STATE_BUCKET" \
      --region "$AWS_REGION" \
      --create-bucket-configuration LocationConstraint="$AWS_REGION"
  fi

  # Enable versioning on state bucket
  aws s3api put-bucket-versioning \
    --bucket "$STATE_BUCKET" \
    --versioning-configuration Status=Enabled

  # Enable encryption on state bucket
  aws s3api put-bucket-encryption \
    --bucket "$STATE_BUCKET" \
    --server-side-encryption-configuration '{
      "Rules": [{
        "ApplyServerSideEncryptionByDefault": {
          "SSEAlgorithm": "AES256"
        }
      }]
    }'

  echo "✅ State bucket created: $STATE_BUCKET"
fi

# ─── Terraform workflow ───────────────────────────────────────────────────────

cd infrastructure/terraform

echo "📦 Initialising Terraform..."
terraform init \
  -backend-config="bucket=${STATE_BUCKET}" \
  -backend-config="key=${PROJECT_NAME}/${ENVIRONMENT}/terraform.tfstate" \
  -backend-config="region=${AWS_REGION}" \
  -reconfigure

echo "✅ Validating configuration..."
terraform validate

echo "📋 Planning..."
terraform plan \
  -var="environment=${ENVIRONMENT}" \
  -var="aws_region=${AWS_REGION}" \
  -var="project_name=${PROJECT_NAME}" \
  -out=tfplan \
  -detailed-exitcode || PLAN_EXIT=$?

# Exit code 0 = no changes, 1 = error, 2 = changes
PLAN_EXIT=${PLAN_EXIT:-0}
if [ "$PLAN_EXIT" -eq 1 ]; then
  echo "ERROR: Terraform plan failed"
  exit 1
elif [ "$PLAN_EXIT" -eq 0 ]; then
  echo "No infrastructure changes required"
  rm -f tfplan
  exit 0
fi

echo ""
echo "The above changes will be applied to: $ENVIRONMENT"
if [ "${AUTO_APPROVE:-false}" != "true" ]; then
  read -rp "Apply these changes? [y/N] " CONFIRM
  if [[ "${CONFIRM}" != "y" && "${CONFIRM}" != "Y" ]]; then
    echo "Aborted"
    rm -f tfplan
    exit 0
  fi
fi

echo "⚡ Applying..."
terraform apply tfplan
rm -f tfplan

echo ""
echo "📊 Infrastructure Outputs:"
terraform output -json 2>/dev/null | python3 -c "
import json, sys
data = json.load(sys.stdin)
for k, v in data.items():
    if not v.get('sensitive', False):
        print(f'  {k} = {v["value"]}')
"

echo ""
echo "✅ Infrastructure deployment complete!"
echo ""
echo "Next steps:"
echo "  1. Build and push Docker images: make push ENVIRONMENT=$ENVIRONMENT"
echo "  2. Run database migrations (via ECS task in CI/CD)"
echo "  3. Update GitHub Actions secrets with the outputs above"
