# ============================================================
# DataNexus v2.0.0 — Terraform Providers & Backend Configuration
# ============================================================

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.30"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.5"
    }
  }

  # Production state storage (uncomment for production remote S3 backend)
  # backend "s3" {
  #   bucket         = "datanexus-terraform-state"
  #   key            = "prod/terraform.tfstate"
  #   region         = "us-east-1"
  #   dynamodb_table = "datanexus-terraform-locks"
  #   encrypt        = true
  # }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "DataNexus"
      Environment = var.environment
      ManagedBy   = "Terraform"
      Version     = "2.0.0"
    }
  }
}
