# DataNexus v2.0.0 — Production Deployment Runbook

This guide covers the four standardized deployment and operational paths for DataNexus v2.0.0:
1. **Local Multi-Container Production Bring-up** (Docker Compose)
2. **Infrastructure as Code Provisioning** (AWS Terraform)
3. **Continuous Integration & CD Configuration** (GitHub Actions / Secrets)
4. **Post-Deployment Verification & Smoke Testing**

---

## 1. Local Multi-Container Production Stack

The local production stack runs all five services using the unified production configuration:
- **FastAPI Backend (v2.0.0)** with FlashRank reranker, OTel tracing, and hybrid storage
- **React 18 / Vite Frontend** served via Nginx with SSE reverse proxying
- **PostgreSQL 16** with Star-Schema analytical models and OLAP views
- **Elasticsearch 8.11.3** for hybrid BM25 + 384-d dense vector search
- **Redis 7** for query result and SHA-256 deduplication caching

### Step 1: Environment Preparation
```bash
cp .env.example .env
# Ensure GROQ_API_KEY is populated if live LLM RAG inference is desired
```

### Step 2: Validate Docker Compose Configuration
```bash
docker compose -f docker-compose.prod.yml config
```

### Step 3: Launch Stack
```bash
docker compose -f docker-compose.prod.yml up -d --build
```

### Step 4: Verify Container Health
```bash
docker compose -f docker-compose.prod.yml ps
```
All services (`datanexus_postgres`, `datanexus_elasticsearch`, `datanexus_redis`, `datanexus_backend`, `datanexus_frontend`) should report `healthy` or `running`.

---

## 2. Cloud Provisioning with Terraform (AWS)

DataNexus provisions modular cloud infrastructure via Terraform in `infra/terraform/`:
- **Private S3 Bucket**: Server-side encrypted (`AES256`), versioned, public access blocked.
- **RDS PostgreSQL 16**: Multi-AZ capable, hosted in private subnets, encrypted at rest.
- **Amazon ECR Repositories**: Automated vulnerability scanning on image push.
- **ECS Fargate & ALB**: Containerized backend behind an Application Load Balancer with health checks.
- **IAM Policies**: Scoped least-privilege policies for S3 (`s3:GetObject`, `s3:PutObject`) and RDS.

### Prerequisites
- AWS CLI configured (`aws configure` with appropriate credentials)
- Terraform CLI (`>= 1.5.0`)

### Step 1: Initialize Terraform
```bash
cd infra/terraform
terraform init
```

### Step 2: Inspect Execution Plan
```bash
terraform plan -var="environment=production" -var="aws_region=us-east-1"
```

### Step 3: Apply Infrastructure
```bash
terraform apply -var="environment=production" -var="aws_region=us-east-1" -auto-approve
```

### Step 4: Retrieve Infrastructure Outputs
```bash
terraform output
```
Note the values for:
- `s3_bucket_name`
- `rds_endpoint`
- `ecr_backend_repository_url`
- `alb_dns_name`

---

## 3. GitHub Actions CI/CD Secrets Setup

To enable automated testing, Docker validation, and automated ECR pushing, configure the following secrets in **GitHub Repository Settings > Secrets and variables > Actions**:

| Secret Name | Description | Example / Note |
|---|---|---|
| `AWS_ACCESS_KEY_ID` | IAM deployment user access key | `AKIAIOSFODNN7EXAMPLE` |
| `AWS_SECRET_ACCESS_KEY` | IAM deployment user secret key | `wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY` |
| `AWS_REGION` | Target deployment AWS region | `us-east-1` |
| `GROQ_API_KEY` | GroqCloud API key for live RAG | `gsk_...` |

> **Note on Safety:** The CD workflow contains an `if: env.AWS_ACCESS_KEY_ID != ''` safety gate. If AWS secrets are not yet configured in GitHub, the CI pipeline will run all tests, lints, and Docker checks without failing the build.

---

## 4. Post-Deployment Verification & Smoke Testing

### Liveness & Readiness Probes
```bash
# Check backend liveness
curl -f http://localhost:8008/api/health/liveness

# Check backend readiness (verifies DB & system components)
curl -f http://localhost:8008/api/health/readiness

# Check search provider cluster status
curl -s http://localhost:8008/api/search/status | jq .
```

### Run Smoke Test Suite
```bash
python scripts/smoke_test.py
```

### Automated Benchmark Dry-Run
```bash
python scripts/run_benchmarks.py --sample 20
```
This runs a 20-sample validation across ingestion, deduplication, 11-rule DQ engine, and A/B/C retrieval ablation without external dependencies.
