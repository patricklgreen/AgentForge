# AgentForge Infrastructure

This directory contains Terraform configuration for deploying AgentForge on AWS using a modern, scalable architecture.

## Architecture Overview

- **Compute**: Amazon ECS Fargate for containerized services
- **Database**: Amazon RDS PostgreSQL with automatic backups
- **Cache**: Amazon ElastiCache Redis for session storage
- **Storage**: Amazon S3 for project artifacts and files
- **Load Balancer**: Application Load Balancer with HTTPS support
- **Email**: Amazon SES for transactional emails (verification, password reset)
- **Monitoring**: CloudWatch logs, metrics, and alarms
- **Security**: VPC with private/public subnets, security groups, IAM roles
- **CI/CD**: GitHub Actions OIDC for secure deployments

## Quick Start

### Prerequisites

1. **AWS Account** with appropriate permissions
2. **Terraform** >= 1.6.0 installed
3. **AWS CLI** configured with credentials
4. **Domain name** (optional, for HTTPS and professional email setup)

### Basic Deployment

```bash
# 1. Clone and navigate to infrastructure
git clone <your-repo>
cd agentforge/infrastructure/terraform

# 2. Create configuration file  
cp terraform.tfvars.example terraform.tfvars

# 3. Edit terraform.tfvars with your values
nano terraform.tfvars

# 4. Initialize Terraform
terraform init \
  -backend-config="bucket=your-terraform-state-bucket" \
  -backend-config="key=agentforge/prod/terraform.tfstate" \
  -backend-config="region=us-east-1"

# 5. Plan and apply
terraform plan
terraform apply
```

### Email Setup (Important)

AgentForge requires email functionality for user verification. Choose one setup method:

#### Quick Setup: Individual Email
1. Set `ses_from_email = "your-email@gmail.com"` in `terraform.tfvars`
2. After deployment, verify the email address in AWS SES Console
3. **Note**: Limited to sandbox mode (200 emails/day, verified recipients only)

#### Production Setup: Domain Email  
1. Set `ses_domain = "yourdomain.com"` in `terraform.tfvars`
2. After deployment, complete DNS verification (see [SES Setup Guide](./SES_SETUP_GUIDE.md))
3. Request production access in AWS SES Console

**📋 See [SES_SETUP_GUIDE.md](./SES_SETUP_GUIDE.md) for detailed email configuration instructions.**

## Configuration

### Core Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `aws_region` | AWS region | `"us-east-1"` |
| `environment` | Environment name | `"prod"` |
| `project_name` | Project identifier | `"agentforge"` |
| `secret_key` | JWT signing key (32+ chars) | `"your-secret-key..."` |
| `db_password` | Database password (16+ chars) | `"your-db-password..."` |

### Email Configuration

| Variable | Description | Required |
|----------|-------------|----------|
| `ses_domain` | Domain for email sending | One of domain |
| `ses_from_email` | Individual email address | or email required |
| `ses_from_name` | Display name for emails | Optional |

### Optional Features

| Variable | Default | Description |
|----------|---------|-------------|
| `domain_name` | `""` | Custom domain for HTTPS |
| `certificate_arn` | `""` | ACM certificate for HTTPS |
| `enable_ses_monitoring` | `true` | Email monitoring/alarms |

## Resources Created

### Networking
- VPC with public/private subnets across 3 AZs
- Internet Gateway and NAT Gateways
- Route tables and security groups

### Compute & Storage  
- ECS Fargate cluster with auto-scaling
- Application Load Balancer with health checks
- S3 bucket for project artifacts
- ECR repositories for Docker images

### Database & Cache
- RDS PostgreSQL with encryption
- ElastiCache Redis cluster
- Automated backups and maintenance windows

### Email Service
- SES domain/email identity configuration
- Email templates (verification, password reset)
- CloudWatch monitoring and alarms
- Bounce and complaint handling

### Security
- IAM roles with least-privilege permissions
- Secrets Manager for sensitive configuration
- VPC security groups with minimal access
- GitHub OIDC for keyless deployments

### Monitoring
- CloudWatch log groups for all services  
- Custom metrics and alarms
- SES reputation monitoring
- Cost allocation tags

## Outputs

After successful deployment, Terraform outputs important values:

```bash
# View all outputs
terraform output

# Specific outputs
terraform output app_url              # Application URL
terraform output ecr_backend_url      # Backend container registry
terraform output github_actions_role_arn  # CI/CD role
terraform output ses_config_secret_arn     # Email configuration
```

## Post-Deployment Steps

### 1. Configure GitHub Actions

Add these secrets to your GitHub repository:

```bash
# Get the role ARN
terraform output github_actions_role_arn

# Add to GitHub Secrets:
AWS_REGION=us-east-1
AWS_ROLE_TO_ASSUME=<role-arn-from-output>
ECR_BACKEND_URI=<backend-uri-from-output>  
ECR_FRONTEND_URI=<frontend-uri-from-output>
ECS_CLUSTER_NAME=<cluster-name-from-output>
```

### 2. Complete Email Setup

- **Individual Email**: Verify email address in AWS SES Console
- **Domain Email**: Add DNS records and request production access
- **See**: [SES_SETUP_GUIDE.md](./SES_SETUP_GUIDE.md) for detailed steps

### 3. Deploy Application

```bash
# Push images and deploy via GitHub Actions
git push origin main

# Or deploy manually
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <ecr-url>
docker build -t backend ./backend
docker tag backend:latest <backend-ecr-url>:latest  
docker push <backend-ecr-url>:latest
```

### 4. Database Migration

```bash
# Run database migrations (one-time setup)
aws ecs run-task \
  --cluster <cluster-name> \
  --task-definition <backend-task-def> \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[<private-subnet>],securityGroups=[<backend-sg>],assignPublicIp=DISABLED}" \
  --overrides '{"containerOverrides":[{"name":"backend","command":["alembic","upgrade","head"]}]}'
```

## Cost Estimation

### Monthly costs for typical production deployment:

| Service | Configuration | Estimated Cost |
|---------|---------------|----------------|
| **ECS Fargate** | 2 backend + 2 frontend tasks | ~$30-50 |
| **RDS PostgreSQL** | db.t3.small, 20GB | ~$25-30 |
| **ElastiCache Redis** | cache.t3.micro | ~$15 |
| **Application Load Balancer** | Standard ALB | ~$20 |
| **S3 + Data Transfer** | Low usage | ~$5-10 |
| **SES Email** | <62k emails/month | Free |
| **CloudWatch** | Logs + metrics | ~$10-15 |
| **NAT Gateway** | 2 AZs | ~$60 |
| **Total** | | **~$165-205/month** |

**Note**: Actual costs depend on traffic, storage, and email volume. Use AWS Cost Calculator for precise estimates.

## Scaling & Performance

### Auto-scaling Configuration

```hcl
# Backend scaling (in terraform.tfvars)
backend_min_capacity = 2    # Minimum tasks
backend_max_capacity = 10   # Maximum tasks
backend_desired_count = 2   # Starting count

# Scaling triggers
# - CPU > 70% for 2 minutes → scale out
# - CPU < 30% for 5 minutes → scale in
```

### Performance Tuning

- **Database**: Upgrade to `db.t3.medium` or larger for production
- **Cache**: Use `cache.t3.small` or larger for better performance  
- **ECS**: Increase CPU/memory allocations for demanding workloads
- **Load Balancer**: Enable sticky sessions if needed

## Security Best Practices

### Network Security
- Private subnets for database and application tiers
- Security groups with minimal required ports
- VPC Flow Logs enabled (optional, additional cost)

### Data Protection  
- Encryption at rest for RDS and S3
- Encryption in transit via HTTPS/TLS
- Secrets stored in AWS Secrets Manager
- Regular automated backups

### Access Control
- IAM roles with least-privilege permissions
- GitHub OIDC instead of long-lived access keys
- Multi-factor authentication on AWS accounts
- Regular security group and IAM policy reviews

### Email Security
- SPF, DKIM, and DMARC records configured
- Bounce and complaint monitoring
- Rate limiting to prevent abuse
- HTTPS-only verification links

## Troubleshooting

### Common Issues

#### 1. Terraform State Lock
```bash
# If state is locked, identify the lock
terraform force-unlock <lock-id>

# Or use different state bucket/key
terraform init -reconfigure -backend-config="key=new-path"
```

#### 2. ECS Deployment Failures
```bash
# Check service events
aws ecs describe-services --cluster <cluster> --services <service>

# Check task logs  
aws logs get-log-events --log-group-name /ecs/<cluster>/<task>
```

#### 3. Email Not Sending
```bash
# Check SES sending statistics
aws ses get-send-statistics

# Verify email/domain status
aws ses get-identity-verification-attributes --identities <email-or-domain>

# Test email sending
aws ses send-email --source <from> --destination ToAddresses=<to> --message Subject={Data="Test"},Body={Text={Data="Test"}}
```

#### 4. Database Connection Issues
```bash
# Check security group rules
aws ec2 describe-security-groups --group-ids <db-security-group-id>

# Test connectivity from ECS task
aws ecs run-task --task-definition <backend> --overrides '{"containerOverrides":[{"name":"backend","command":["nc","-zv","<db-endpoint>","5432"]}]}'
```

### Debugging Commands

```bash
# View Terraform state
terraform show
terraform state list

# Check AWS resources
aws ecs list-clusters
aws rds describe-db-instances  
aws ses list-identities
aws secretsmanager list-secrets

# View logs
aws logs describe-log-groups --log-group-name-prefix /ecs/
aws logs get-log-events --log-group-name <log-group> --log-stream-name <stream>
```

## Disaster Recovery

### Backup Strategy
- **Database**: Automated daily backups with 7-day retention
- **Configuration**: Terraform state in versioned S3 bucket  
- **Code**: Git repository with tagged releases
- **Secrets**: Stored in AWS Secrets Manager with cross-region replication option

### Recovery Procedures
1. **Database restore**: Use RDS automated backups or point-in-time recovery
2. **Infrastructure**: Re-deploy from Terraform with same state
3. **Application**: Deploy from last known good Docker image tags
4. **DNS**: Update Route 53 records if changing regions

## Maintenance

### Regular Tasks
- [ ] Monitor CloudWatch alarms and metrics
- [ ] Review security group rules quarterly  
- [ ] Update Terraform and AWS provider versions
- [ ] Rotate secrets (database passwords, API keys)
- [ ] Review and optimize costs monthly
- [ ] Test backup and recovery procedures

### Updates
- **Terraform**: Test updates in non-production environment first
- **AWS Services**: Most updates happen automatically (RDS patches, etc.)
- **Container Images**: Use CI/CD pipeline for application updates

## Support

### AWS Resources
- [AWS Well-Architected Framework](https://aws.amazon.com/architecture/well-architected/)
- [ECS Best Practices](https://docs.aws.amazon.com/AmazonECS/latest/bestpracticesguide/)
- [RDS Best Practices](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/CHAP_BestPractices.html)
- [SES Developer Guide](https://docs.aws.amazon.com/ses/latest/DeveloperGuide/)

### Documentation
- [SES Setup Guide](./SES_SETUP_GUIDE.md) - Detailed email configuration
- [Integration Examples](./examples/) - Backend integration code samples
- [Terraform Variables](./terraform.tfvars.example) - Complete configuration reference

For infrastructure issues, check CloudWatch logs first, then AWS documentation. For application-specific problems, refer to the main AgentForge documentation.