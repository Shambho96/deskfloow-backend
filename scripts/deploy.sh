#!/bin/bash
set -e

echo "========== Starting DeskFlow Backend Deployment =========="

# ----------------------------------------
# Auto-detect AWS Region and Account ID via IMDSv2
# ----------------------------------------
TOKEN=$(curl -X PUT "http://169.254.169.254/latest/api/token" \
    -H "X-aws-ec2-metadata-token-ttl-seconds: 21600" -s || true)

AWS_REGION=$(curl \
    -H "X-aws-ec2-metadata-token: $TOKEN" \
    -s http://169.254.169.254/latest/meta-data/placement/region || echo "ap-southeast-2")

AWS_ACCOUNT_ID=$(curl \
    -H "X-aws-ec2-metadata-token: $TOKEN" \
    -s http://169.254.169.254/latest/meta-data/identity-credentials/ec2/info \
    | grep -oP '"AccountId" : "\K[^"]+' || echo "245370795178")

# ----------------------------------------
# Project Directory
# ----------------------------------------
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

echo "Project Directory: $PROJECT_DIR"

# ----------------------------------------
# Load Deployment Variables from deploy.env
# ----------------------------------------
if [ -f "$PROJECT_DIR/deploy.env" ]; then
    echo "Loading deploy.env..."
    set -a
    source "$PROJECT_DIR/deploy.env"
    set +a
else
    echo "ERROR: deploy.env not found!"
    exit 1
fi

# ----------------------------------------
# Configuration & Environment Detection
# ----------------------------------------
ENVIRONMENT="${ENVIRONMENT:-prod}"
export ENVIRONMENT
export REPO_NAME="${REPO_NAME:-deskfloow/backend}"
export ECR_REGISTRY="${ECR_REGISTRY:-${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com}"
export IMAGE_TAG="${IMAGE_TAG:-latest}"

if [ "$ENVIRONMENT" = "dev" ]; then
    echo "[ENVIRONMENT] Development mode selected"
    COMPOSE_FILE="$PROJECT_DIR/docker-compose.dev.yml"
    PROJECT_NAME="deskflow-backend-dev"
    ENV_FILE="/home/ubuntu/.deskflow-dev-env"
elif [ "$ENVIRONMENT" = "staging" ]; then
    echo "[ENVIRONMENT] Staging mode selected"
    COMPOSE_FILE="$PROJECT_DIR/docker-compose.staging.yml"
    PROJECT_NAME="deskflow-backend-staging"
    ENV_FILE="/home/ubuntu/.deskflow-staging-env"
else
    echo "[ENVIRONMENT] Production mode selected"
    COMPOSE_FILE="$PROJECT_DIR/docker-compose.prod.yml"
    PROJECT_NAME="deskflow-backend-prod"
    ENV_FILE="/home/ubuntu/.deskflow-env"
fi

# ----------------------------------------
# Verify Persistent Environment File
# ----------------------------------------
if [ ! -f "$ENV_FILE" ]; then
    echo "ERROR: Persistent env file not found: $ENV_FILE"
    echo "Please create it on the server: sudo nano $ENV_FILE"
    exit 1
fi

echo "Loading persistent environment variables from $ENV_FILE..."
set -a
source "$ENV_FILE"
set +a

# Clear AWS_PROFILE if present so AWS CLI uses EC2 IAM Instance Profile
unset AWS_PROFILE

# ----------------------------------------
# Deployment Info Output
# ----------------------------------------
echo ""
echo "========== Deployment Configuration =========="
echo "AWS Region      : $AWS_REGION"
echo "AWS Account     : $AWS_ACCOUNT_ID"
echo "ECR Registry    : $ECR_REGISTRY"
echo "Repository      : $REPO_NAME"
echo "Image Tag       : $IMAGE_TAG"
echo "Environment     : $ENVIRONMENT"
echo "Compose File    : $COMPOSE_FILE"
echo "Project Name    : $PROJECT_NAME"
echo "=============================================="
echo ""

# ----------------------------------------
# Login to Amazon ECR
# ----------------------------------------
echo "Logging into Amazon ECR..."
aws ecr get-login-password --region "$AWS_REGION" \
    | docker login --username AWS --password-stdin "$ECR_REGISTRY"

# ----------------------------------------
# Pull Latest Image
# ----------------------------------------
echo "Pulling latest image: ${ECR_REGISTRY}/${REPO_NAME}:${IMAGE_TAG}..."
docker compose \
    -f "$COMPOSE_FILE" \
    --env-file "$PROJECT_DIR/deploy.env" \
    -p "$PROJECT_NAME" \
    pull

# ----------------------------------------
# Run Alembic Database Migrations (if applicable)
# ----------------------------------------
echo "Running database migrations..."
docker compose \
    -f "$COMPOSE_FILE" \
    --env-file "$PROJECT_DIR/deploy.env" \
    -p "$PROJECT_NAME" \
    run --rm app alembic upgrade head || echo "Database migration step completed or bypassed."

# ----------------------------------------
# Start / Restart Containers
# ----------------------------------------
echo "Starting containers for $PROJECT_NAME..."
docker compose \
    -f "$COMPOSE_FILE" \
    --env-file "$PROJECT_DIR/deploy.env" \
    -p "$PROJECT_NAME" \
    up -d --remove-orphans

# ----------------------------------------
# Cleanup old unused Docker images
# ----------------------------------------
echo "Cleaning up dangling Docker images..."
docker image prune -f

echo ""
echo "========== Deployment for $PROJECT_NAME Completed Successfully! =========="
