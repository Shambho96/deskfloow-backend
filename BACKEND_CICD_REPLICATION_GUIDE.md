# Complete CI/CD Pipeline Replication Guide (AWS CodeDeploy + ECR + Docker Compose)

This guide documents the exact production CI/CD architecture used by `business-backend`. You can use this document as a standalone blueprint to replicate the identical pipeline in any new project, replacing only your project names, ports, and AWS credentials.

---

## 1. High-Level Architecture Flow

```mermaid
flowchart TD
    subgraph GitHub ["GitHub Repository"]
        DevPush["git push to main"] --> WfDev["deploy-dev.yml"]
        TagPush["git tag v*"] --> WfProd["deploy-production.yml"]
    end

    subgraph GitHubActions ["GitHub Actions Runner"]
        WfDev & WfProd --> Build["1. Build Multi-stage Docker Image"]
        Build --> PushECR["2. Push Image to Amazon ECR"]
        PushECR --> Package["3. Package Artifact (appspec.yml + scripts/ + docker-compose.yml + deploy.env)"]
        Package --> UploadS3["4. Upload deployment.zip to S3"]
        UploadS3 --> TriggerCD["5. Trigger AWS CodeDeploy (create-deployment)"]
    end

    subgraph AWSInfra ["AWS Cloud Infrastructure"]
        ECR[("Amazon ECR Repository")]
        S3Bucket[("Amazon S3 Deployment Bucket")]
        CodeDeploy["AWS CodeDeploy Service"]
    end

    PushECR -.-> ECR
    UploadS3 -.-> S3Bucket
    TriggerCD -.-> CodeDeploy

    subgraph EC2Server ["EC2 Target Host (Instance Profile IAM)"]
        CDAgent["CodeDeploy Agent"]
        CDAgent <-- "Polls & Downloads Bundle" --> CodeDeploy
        CDAgent --> Extract["Extracts to /app/<project-name>"]
        Extract --> DeploySh["Executes scripts/deploy.sh as root"]
        DeploySh --> IMDS["Auto-detects AWS Region & Account via IMDSv2"]
        DeploySh --> LoadEnv["Sources persistent /home/ubuntu/.<project>-env"]
        DeploySh --> ECRLogin["Logs into Amazon ECR via Instance IAM"]
        DeploySh --> DockerCompose["docker compose pull & up -d"]
        DockerCompose --> AppContainer["Running Docker Container"]
        DeploySh --> Prune["docker image prune -f"]
    end
```

---

## 2. Directory & File Structure Blueprint

Replicate the following structure in your new project root:

```text
your-project/
├── .github/
│   └── workflows/
│       ├── deploy-dev.yml              # Trigger on main push
│       ├── deploy-staging.yml          # Optional: Trigger on staging branch
│       └── deploy-production.yml       # Trigger on tag (v*) or manual dispatch
├── scripts/
│   └── deploy.sh                       # Server-side deployment hook (executed by CodeDeploy)
├── .dockerignore                       # Exclude secrets, tests, node_modules/pycache
├── Dockerfile                          # Multi-stage production container build
├── docker-compose.dev.yml              # Dev environment container spec
├── docker-compose.prod.yml             # Production container spec
├── appspec.dev.yml                     # CodeDeploy spec for dev environment
├── appspec.prod.yml                    # CodeDeploy spec for production
└── README.md
```

---

## 3. AWS Infrastructure Prerequisites

Before running the pipeline, set up these 5 AWS resources:

### A. Amazon ECR (Elastic Container Registry)
1. Go to **AWS Console > ECR > Repositories**.
2. Click **Create repository**:
   - Visibility: **Private**
   - Repository name: `<your-org>/<your-repo-name>` (e.g., `restaverse/my-backend`)
   - Tag immutability: **Disabled** (or Enabled if strict tagging is desired)
   - Scan on push: **Enabled**

### B. Amazon S3 Bucket
1. Create a private S3 bucket to store deployment zip bundles:
   - Name: `<your-company>-deployments` (e.g., `my-company-deployments`)
   - Block all public access: **Enabled**
   - Default encryption: **Amazon S3-managed keys (SSE-S3)**

### C. EC2 Instance IAM Role (Instance Profile)
The EC2 server needs permissions to pull images and download artifacts **without hardcoding AWS access keys on the server**.
1. Go to **IAM > Roles > Create Role**.
2. Trusted entity type: **AWS service** > Use case: **EC2**.
3. Attach policies:
   - `AmazonEC2ContainerRegistryReadOnly` (to pull images from ECR)
   - `AmazonS3ReadOnlyAccess` (or custom policy restricted to your S3 deployment bucket)
   - `AWSCodeDeployRole` (or `AmazonSSMManagedInstanceCore`)
4. Attach this role to your EC2 instance:
   - **EC2 Console > Instances > Select Instance > Actions > Security > Modify IAM role**.

### D. AWS CodeDeploy Setup
1. **Create CodeDeploy Service Role**:
   - IAM > Roles > Create Role > AWS Service: **CodeDeploy**.
   - Attach policy: `AWSCodeDeployRole`.
2. **Create CodeDeploy Application**:
   - Go to **CodeDeploy > Applications > Create application**.
   - Application name: `<your-app-name>` (e.g., `my-backend`)
   - Compute platform: **EC2/On-premises**.
3. **Create Deployment Groups**:
   - Create one group for each environment (e.g., `my-backend-dev-dg`, `my-backend-production-dg`).
   - Service role: The CodeDeploy role created above.
   - Deployment type: **In-place**.
   - Environment configuration: **Amazon EC2 instances**. Add Tag (e.g., `Environment = production` or `Name = my-backend-prod`).
   - Deployment settings: `CodeDeployDefault.AllAtOnce`.
   - Load Balancer: Disable (unless using an Application Load Balancer).

### E. GitHub Actions IAM User (CI/CD User)
Create an IAM user with programmatic access for GitHub Actions:
- Attach policy allowing:
  - `ecr:GetAuthorizationToken`, `ecr:BatchCheckLayerAvailability`, `ecr:GetDownloadUrlForLayer`, `ecr:PutImage`, `ecr:InitiateLayerUpload`, `ecr:UploadLayerPart`, `ecr:CompleteLayerUpload`
  - `s3:PutObject`, `s3:GetObject` on `arn:aws:s3:::<your-deployment-bucket>/*`
  - `codedeploy:CreateDeployment`, `codedeploy:GetDeployment`, `codedeploy:GetDeploymentConfig`, `codedeploy:RegisterApplicationRevision`
- Generate Access Key ID & Secret Access Key for GitHub repository secrets.

---

## 4. EC2 Server Preparation

SSH into your target EC2 instance and run these once:

### 1. Install Docker & Docker Compose
```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg lsb-release
sudo mkdir -p /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# Allow ubuntu user to run docker
sudo usermod -aG docker ubuntu
```

### 2. Install AWS CLI v2
```bash
curl "https://awscli.amazonaws.com/awscli-exe-linux-$(uname -m).zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install
rm -rf aws awscliv2.zip
```

### 3. Install AWS CodeDeploy Agent
```bash
sudo apt-get update
sudo apt-get install -y ruby-full wget
cd /home/ubuntu
wget https://aws-codedeploy-ap-south-1.s3.ap-south-1.amazonaws.com/latest/install
chmod +x ./install
sudo ./install auto

# Verify agent status
sudo systemctl enable codedeploy-agent
sudo systemctl status codedeploy-agent
```
*(Replace `ap-south-1` with your AWS region if different).*

### 4. Create Persistent Server Environment File
Sensitive database credentials, third-party API keys, and secret tokens should live safely on the server, **never committed to Git**:

```bash
# For Production:
sudo nano /home/ubuntu/.my-backend-env

# For Dev:
sudo nano /home/ubuntu/.my-backend-dev-env
```

Add your environment variables:
```dotenv
DATABASE_URL=mysql+pymysql://user:pass@host:3306/dbname
REDIS_URL=redis://localhost:6379/0
SECRET_KEY=supersecretjwtkey
LOG_LEVEL=20
```

Lock down permissions:
```bash
chmod 600 /home/ubuntu/.my-backend-env
```

---

## 5. Ready-to-Use File Templates

Copy and customize each file in your project:

### File 1: `appspec.prod.yml`
```yaml
version: 0.0
os: linux
files:
  - source: /
    destination: /app/my-backend
hooks:
  AfterInstall:
    - location: scripts/deploy.sh
      timeout: 300
      runas: root
```

### File 2: `appspec.dev.yml`
```yaml
version: 0.0
os: linux
files:
  - source: /
    destination: /app/my-backend-dev
hooks:
  AfterInstall:
    - location: scripts/deploy.sh
      timeout: 300
      runas: root
```

---

### File 3: `scripts/deploy.sh`
*(Make sure to run `chmod +x scripts/deploy.sh` in Git)*

```bash
#!/bin/bash
set -e

echo "========== Starting Deployment =========="

# ----------------------------------------
# Auto-detect AWS Region and Account ID via IMDSv2
# ----------------------------------------
TOKEN=$(curl -X PUT "http://169.254.169.254/latest/api/token" \
    -H "X-aws-ec2-metadata-token-ttl-seconds: 21600" -s || true)

AWS_REGION=$(curl \
    -H "X-aws-ec2-metadata-token: $TOKEN" \
    -s http://169.254.169.254/latest/meta-data/placement/region || echo "ap-south-1")

AWS_ACCOUNT_ID=$(curl \
    -H "X-aws-ec2-metadata-token: $TOKEN" \
    -s http://169.254.169.254/latest/meta-data/identity-credentials/ec2/info \
    | grep -oP '"AccountId" : "\K[^"]+' || echo "")

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
if [ -n "$ENVIRONMENT" ]; then
    echo "Environment '$ENVIRONMENT' specified in deploy.env."
elif [ -f "$PROJECT_DIR/docker-compose.staging.yml" ] && [ ! -f "$PROJECT_DIR/docker-compose.prod.yml" ]; then
    ENVIRONMENT="staging"
elif [ -f "$PROJECT_DIR/docker-compose.dev.yml" ] && [ ! -f "$PROJECT_DIR/docker-compose.staging.yml" ]; then
    ENVIRONMENT="dev"
else
    ENVIRONMENT="prod"
fi

export ENVIRONMENT
export REPO_NAME="${REPO_NAME:-my-org/my-backend}"
export ECR_REGISTRY="${ECR_REGISTRY:-${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com}"
export IMAGE_TAG="${IMAGE_TAG:-latest}"

# Configure compose file and persistent env file per environment
if [ "$ENVIRONMENT" = "staging" ]; then
    echo "Staging environment detected."
    COMPOSE_FILE="$PROJECT_DIR/docker-compose.staging.yml"
    PROJECT_NAME="my-backend-staging"
    ENV_FILE="/home/ubuntu/.my-backend-staging-env"
elif [ "$ENVIRONMENT" = "dev" ]; then
    echo "Dev environment detected."
    COMPOSE_FILE="$PROJECT_DIR/docker-compose.dev.yml"
    PROJECT_NAME="my-backend-dev"
    ENV_FILE="/home/ubuntu/.my-backend-dev-env"
else
    echo "Production environment detected."
    COMPOSE_FILE="$PROJECT_DIR/docker-compose.prod.yml"
    PROJECT_NAME="my-backend"
    ENV_FILE="/home/ubuntu/.my-backend-env"
fi

# ----------------------------------------
# Verify Persistent Environment File
# ----------------------------------------
if [ ! -f "$ENV_FILE" ]; then
    echo "ERROR: Persistent env file not found in $ENV_FILE!"
    echo "Please create it once on the server: sudo nano $ENV_FILE"
    exit 1
fi

echo "Loading persistent environment variables from $ENV_FILE..."
set -a
source "$ENV_FILE"
set +a

# Clear AWS_PROFILE if present so AWS CLI uses EC2 IAM Instance Profile
unset AWS_PROFILE

# ----------------------------------------
# Debug Information
# ----------------------------------------
echo ""
echo "========== Deployment Info =========="
echo "AWS Region      : $AWS_REGION"
echo "AWS Account     : $AWS_ACCOUNT_ID"
echo "ECR Registry    : $ECR_REGISTRY"
echo "Repository      : $REPO_NAME"
echo "Image Tag       : $IMAGE_TAG"
echo "Compose File    : $COMPOSE_FILE"
echo "====================================="
echo ""

# ----------------------------------------
# Login to Amazon ECR
# ----------------------------------------
echo "Logging into Amazon ECR..."
aws ecr get-login-password --region "$AWS_REGION" \
    | docker login --username AWS --password-stdin "$ECR_REGISTRY"

# ----------------------------------------
# Pull Latest Image & Restart Containers
# ----------------------------------------
echo "Pulling latest image..."
docker compose \
    -f "$COMPOSE_FILE" \
    --env-file "$PROJECT_DIR/deploy.env" \
    -p "$PROJECT_NAME" \
    pull

echo "Starting containers..."
docker compose \
    -f "$COMPOSE_FILE" \
    --env-file "$PROJECT_DIR/deploy.env" \
    -p "$PROJECT_NAME" \
    up -d --remove-orphans

# ----------------------------------------
# Cleanup old Docker images
# ----------------------------------------
echo "Cleaning up old Docker images..."
docker image prune -f

echo ""
echo "========== Deployment Completed Successfully =========="
```

---

### File 4: `docker-compose.prod.yml`
```yaml
services:
  app:
    image: ${ECR_REGISTRY}/${REPO_NAME}:${IMAGE_TAG:-latest}
    container_name: my-backend
    labels:
      service: "my-backend"
      environment: "production"
    restart: unless-stopped
    ports:
      - "8000:8000"
    extra_hosts:
      - "host.docker.internal:host-gateway"
    env_file:
      - /home/ubuntu/.my-backend-env
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
    deploy:
      resources:
        limits:
          cpus: '1.5'
          memory: 1G
```

### File 5: `docker-compose.dev.yml`
```yaml
services:
  app:
    image: ${ECR_REGISTRY}/${REPO_NAME}:${IMAGE_TAG:-dev}
    container_name: my-backend-dev
    labels:
      service: "my-backend"
      environment: "development"
    restart: unless-stopped
    ports:
      - "8001:8000"
    extra_hosts:
      - "host.docker.internal:host-gateway"
    env_file:
      - /home/ubuntu/.my-backend-dev-env
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
    deploy:
      resources:
        limits:
          cpus: '1'
          memory: 512M
```

---

### File 6: `Dockerfile` (Multi-stage Python Example)
```dockerfile
# ---------- Stage 1: Build Dependencies ----------
FROM python:3.12-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    pkg-config \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ---------- Stage 2: Final Minimal Runtime ----------
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app

WORKDIR /app

# Copy installed libraries from builder
COPY --from=builder /usr/local /usr/local

# Copy application source code
COPY . .

EXPOSE 8000

# Start server using uvicorn / gunicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### File 7: `.dockerignore`
```text
__pycache__/
*.pyc
.git
.github
.env
tests/
node_modules/
```

---

### File 8: `.github/workflows/deploy-production.yml`
```yaml
name: Production Deployment

on:
  push:
    tags: [ 'v*' ]
  workflow_dispatch:

permissions:
  id-token: write
  contents: read

jobs:
  build-and-push:
    runs-on: ubuntu-latest
    outputs:
      image_tag: ${{ steps.slug.outputs.sha }}
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Get Short SHA
        id: slug
        run: echo "sha=$(git rev-parse --short HEAD)" >> $GITHUB_OUTPUT

      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: ${{ secrets.AWS_REGION }}

      - name: Login to Amazon ECR
        id: login-ecr
        uses: aws-actions/amazon-ecr-login@v2

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Build and Push Image
        env:
          ECR_REGISTRY: ${{ steps.login-ecr.outputs.registry }}
          ECR_REPOSITORY: ${{ secrets.ECR_REPOSITORY }}
          IMAGE_TAG: ${{ steps.slug.outputs.sha }}
        run: |
          docker buildx build \
            --platform linux/amd64 \
            --cache-from type=gha \
            --cache-to type=gha,mode=max \
            -t $ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG \
            -t $ECR_REGISTRY/$ECR_REPOSITORY:latest \
            --push .

      - name: Create Deployment Package
        env:
          IMAGE_TAG: ${{ steps.slug.outputs.sha }}
        run: |
          cp appspec.prod.yml appspec.yml
          echo "IMAGE_TAG=$IMAGE_TAG" > deploy.env
          echo "REPO_NAME=${{ secrets.ECR_REPOSITORY }}" >> deploy.env
          echo "ENVIRONMENT=prod" >> deploy.env
          zip -r deployment.zip appspec.yml scripts/ docker-compose.prod.yml deploy.env

      - name: Upload Deployment Package
        uses: actions/upload-artifact@v4
        with:
          name: deployment-package-prod
          path: deployment.zip
          retention-days: 1

  deploy-production:
    needs: build-and-push
    runs-on: ubuntu-latest
    environment: production
    steps:
      - name: Download Deployment Package
        uses: actions/download-artifact@v4
        with:
          name: deployment-package-prod

      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: ${{ secrets.AWS_REGION }}

      - name: Upload to S3
        run: aws s3 cp deployment.zip s3://${{ secrets.S3_BUCKET }}/my-backend-deployment-production.zip

      - name: Trigger CodeDeploy
        run: |
          aws deploy create-deployment \
            --application-name ${{ secrets.CODEDEPLOY_APPLICATION }} \
            --deployment-group-name my-backend-production-dg \
            --s3-location bucket=${{ secrets.S3_BUCKET }},key=my-backend-deployment-production.zip,bundleType=zip
```

---

### File 9: `.github/workflows/deploy-dev.yml`
```yaml
name: Development Deployment

on:
  push:
    branches: [ main ]
  workflow_dispatch:

permissions:
  id-token: write
  contents: read

jobs:
  build-and-push:
    runs-on: ubuntu-latest
    outputs:
      image_tag: ${{ steps.slug.outputs.sha }}
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Get Short SHA
        id: slug
        run: echo "sha=$(git rev-parse --short HEAD)" >> $GITHUB_OUTPUT

      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: ${{ secrets.AWS_REGION }}

      - name: Login to Amazon ECR
        id: login-ecr
        uses: aws-actions/amazon-ecr-login@v2

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Build and Push Image
        env:
          ECR_REGISTRY: ${{ steps.login-ecr.outputs.registry }}
          ECR_REPOSITORY: ${{ secrets.ECR_REPOSITORY }}
          IMAGE_TAG: ${{ steps.slug.outputs.sha }}
        run: |
          docker buildx build \
            --platform linux/amd64 \
            --cache-from type=gha \
            --cache-to type=gha,mode=max \
            -t $ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG \
            -t $ECR_REGISTRY/$ECR_REPOSITORY:dev \
            --push .

      - name: Create Deployment Package
        env:
          IMAGE_TAG: ${{ steps.slug.outputs.sha }}
        run: |
          cp appspec.dev.yml appspec.yml
          echo "IMAGE_TAG=$IMAGE_TAG" > deploy.env
          echo "REPO_NAME=${{ secrets.ECR_REPOSITORY }}" >> deploy.env
          echo "ENVIRONMENT=dev" >> deploy.env
          zip -r deployment.zip appspec.yml scripts/ docker-compose.dev.yml deploy.env

      - name: Upload Deployment Package
        uses: actions/upload-artifact@v4
        with:
          name: deployment-package-dev
          path: deployment.zip
          retention-days: 1

  deploy-development:
    needs: build-and-push
    runs-on: ubuntu-latest
    environment: dev
    steps:
      - name: Download Deployment Package
        uses: actions/download-artifact@v4
        with:
          name: deployment-package-dev

      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: ${{ secrets.AWS_REGION }}

      - name: Upload to S3
        run: aws s3 cp deployment.zip s3://${{ secrets.S3_BUCKET }}/my-backend-deployment-dev.zip

      - name: Trigger CodeDeploy
        run: |
          aws deploy create-deployment \
            --application-name ${{ secrets.CODEDEPLOY_APPLICATION }} \
            --deployment-group-name my-backend-dev-dg \
            --s3-location bucket=${{ secrets.S3_BUCKET }},key=my-backend-deployment-dev.zip,bundleType=zip
```

---

## 6. GitHub Repository Secrets Checklist

In your new repository under **Settings > Secrets and variables > Actions > Repository secrets**, add:

| Secret Name | Example Value | Description |
| :--- | :--- | :--- |
| `AWS_ACCESS_KEY_ID` | `AKIAIOSFODNN7EXAMPLE` | IAM CI/CD User access key |
| `AWS_SECRET_ACCESS_KEY` | `wJalrXUtnFEMI/K7MDENG/...` | IAM CI/CD User secret |
| `AWS_REGION` | `ap-south-1` | Target AWS Region |
| `ECR_REPOSITORY` | `my-org/my-backend` | ECR repository name |
| `S3_BUCKET` | `my-company-deployments` | S3 bucket storing deployment zips |
| `CODEDEPLOY_APPLICATION` | `my-backend` | AWS CodeDeploy Application name |

---

## 7. Troubleshooting & Verification Runbook

### How to Monitor the Deployment on EC2:
```bash
# 1. View CodeDeploy agent logs:
sudo tail -f /var/log/aws/codedeploy-agent/codedeploy-agent.log

# 2. View deploy.sh script execution logs:
sudo tail -f /opt/codedeploy-agent/deployment-root/deployment-logs/codedeploy-agent-deployments.log

# 3. View running Docker container status:
docker ps

# 4. View container live logs:
docker logs -f my-backend
```

### Common Issues & Quick Fixes:

1. **`scripts/deploy.sh: Permission denied` (Exit code 126)**:
   - Ensure `scripts/deploy.sh` is committed with executable bits:
     ```bash
     git update-index --chmod=+x scripts/deploy.sh
     git commit -m "chmod +x deploy.sh" && git push
     ```
2. **ECR Login fails on EC2**:
   - Ensure the EC2 instance has an IAM Role attached with `AmazonEC2ContainerRegistryReadOnly`.
   - Verify `unset AWS_PROFILE` is in `scripts/deploy.sh`.
3. **Container fails on startup due to missing environment variables**:
   - Verify `/home/ubuntu/.my-backend-env` exists on the server and is readable (`chmod 600`).
4. **Architecture mismatch (`exec format error`)**:
   - If using `ubuntu-24.04-arm` in GitHub Actions, your EC2 instance must be ARM64 (e.g. `t4g`, `c6g`). If your EC2 instance is x86 (e.g. `t3`, `c5`), use `ubuntu-latest` with `--platform linux/amd64` in `docker buildx build`.
