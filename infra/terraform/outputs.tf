# ============================================================
# DataNexus v2.0.0 — Terraform Outputs
# ============================================================

output "aws_region" {
  description = "Target deployment AWS region"
  value       = var.aws_region
}

output "vpc_id" {
  description = "ID of the DataNexus VPC"
  value       = aws_vpc.main.id
}

output "s3_bucket_name" {
  description = "Name of the cold document binary storage S3 bucket"
  value       = aws_s3_bucket.documents.id
}

output "s3_bucket_arn" {
  description = "ARN of the S3 storage bucket"
  value       = aws_s3_bucket.documents.arn
}

output "rds_endpoint" {
  description = "Connection endpoint for PostgreSQL RDS"
  value       = aws_db_instance.postgres.endpoint
}

output "rds_address" {
  description = "Host address for PostgreSQL RDS"
  value       = aws_db_instance.postgres.address
}

output "ecr_backend_repository_url" {
  description = "Amazon ECR repository URI for backend Docker images"
  value       = aws_ecr_repository.backend.repository_url
}

output "alb_dns_name" {
  description = "Public DNS name of the Application Load Balancer"
  value       = aws_lb.main.dns_name
}

output "ecs_cluster_name" {
  description = "Name of the ECS Fargate Cluster"
  value       = aws_ecs_cluster.main.name
}
