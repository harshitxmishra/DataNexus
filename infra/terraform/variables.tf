# ============================================================
# DataNexus v2.0.0 — Terraform Variables
# ============================================================

variable "aws_region" {
  type        = string
  description = "AWS region for DataNexus infrastructure deployment"
  default     = "us-east-1"
}

variable "environment" {
  type        = string
  description = "Deployment environment (e.g. dev, staging, production)"
  default     = "production"
}

variable "project_name" {
  type        = string
  description = "Base name for provisioned cloud resources"
  default     = "datanexus"
}

variable "vpc_cidr" {
  type        = string
  description = "CIDR block for the dedicated DataNexus VPC"
  default     = "10.0.0.0/16"
}

variable "public_subnet_cidrs" {
  type        = list(string)
  description = "CIDR blocks for public subnets (ALB / Ingress)"
  default     = ["10.0.1.0/24", "10.0.2.0/24"]
}

variable "private_subnet_cidrs" {
  type        = list(string)
  description = "CIDR blocks for private subnets (ECS / RDS)"
  default     = ["10.0.10.0/24", "10.0.11.0/24"]
}

variable "db_instance_class" {
  type        = string
  description = "RDS PostgreSQL compute instance class"
  default     = "db.t4g.micro"
}

variable "db_name" {
  type        = string
  description = "PostgreSQL canonical database name"
  default     = "datanexus"
}

variable "db_username" {
  type        = string
  description = "PostgreSQL root/master username"
  default     = "datanexus_admin"
}

variable "s3_bucket_prefix" {
  type        = string
  description = "Prefix for immutable PDF cold storage S3 bucket"
  default     = "datanexus-documents"
}

variable "backend_cpu" {
  type        = number
  description = "Fargate vCPU allocation for FastAPI backend (1024 = 1 vCPU)"
  default     = 1024
}

variable "backend_memory" {
  type        = number
  description = "Fargate memory allocation in MB (2048 = 2GB)"
  default     = 2048
}

variable "backend_desired_count" {
  type        = number
  description = "Number of active backend Fargate task replicas"
  default     = 2
}
