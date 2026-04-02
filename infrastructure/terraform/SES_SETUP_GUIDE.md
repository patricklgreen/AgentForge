# AWS SES Setup Guide for AgentForge

This guide explains how to configure AWS Simple Email Service (SES) for sending transactional emails in your AgentForge deployment.

## Overview

The AgentForge infrastructure includes comprehensive SES configuration for:

- **Email verification** during user registration
- **Password reset** functionality  
- **Notification emails** (future extensibility)
- **Email templates** with HTML and text versions
- **Bounce and complaint monitoring** via CloudWatch
- **Security and deliverability** best practices

## Prerequisites

### 1. AWS Account Setup
- Ensure you have appropriate AWS permissions for SES, CloudWatch, and Secrets Manager
- Request production access for SES (initially limited to sandbox mode)

### 2. Choose Email Setup Method

You have two options for configuring email sending:

#### Option A: Domain Identity (Recommended for Production)
- **Benefits**: Professional appearance, higher deliverability, no sandbox limitations
- **Requirements**: Own a domain with DNS management access
- **Best for**: Production environments

#### Option B: Individual Email Identity  
- **Benefits**: Quick setup, good for testing
- **Limitations**: Sandbox restrictions, less professional appearance
- **Best for**: Development and testing

## Setup Instructions

### Option A: Domain Identity Setup

#### 1. Configure Terraform Variables

In your `terraform.tfvars` file:

```hcl
# Use your domain
ses_domain            = "yourdomain.com"
ses_mail_from_domain  = "mail.yourdomain.com"  # Optional but recommended
ses_from_name         = "AgentForge"

# Leave this empty when using domain identity
ses_from_email = ""
```

#### 2. Deploy Infrastructure

```bash
cd infrastructure/terraform
terraform plan
terraform apply
```

#### 3. Complete Domain Verification

After Terraform deployment:

1. **Get DNS Records**: Check AWS SES Console → Domains → your domain
2. **Add DNS Records**: Add the following to your domain's DNS:
   
   ```
   # Domain verification (TXT record)
   _amazonses.yourdomain.com -> "verification-token-from-ses"
   
   # DKIM records (3 CNAME records) 
   token1._domainkey.yourdomain.com -> token1.dkim.amazonses.com
   token2._domainkey.yourdomain.com -> token2.dkim.amazonses.com  
   token3._domainkey.yourdomain.com -> token3.dkim.amazonses.com
   
   # SPF record (optional but recommended)
   yourdomain.com -> "v=spf1 include:amazonses.com ~all"
   
   # MAIL FROM domain (if using ses_mail_from_domain)
   mail.yourdomain.com -> MX 10 feedback-smtp.region.amazonses.com
   mail.yourdomain.com -> TXT "v=spf1 include:amazonses.com ~all"
   ```

3. **Wait for Verification**: DNS propagation typically takes 15 minutes to 24 hours

4. **Request Production Access**: Submit a request in AWS SES Console to move out of sandbox mode

### Option B: Individual Email Setup

#### 1. Configure Terraform Variables

In your `terraform.tfvars` file:

```hcl
# Use your email address
ses_from_email = "noreply@youremail.com" 
ses_from_name  = "AgentForge"

# Leave these empty when using individual email
ses_domain           = ""
ses_mail_from_domain = ""
```

#### 2. Deploy Infrastructure

```bash
cd infrastructure/terraform
terraform plan  
terraform apply
```

#### 3. Verify Email Address

1. **Check AWS SES Console** → Email Addresses → your email
2. **Verify the email** by clicking the verification link sent to your inbox
3. **Note**: You'll be in sandbox mode (can only send to verified addresses)

## Configuration Reference

### Required Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `ses_domain` | Domain for email sending | `"yourdomain.com"` |
| `ses_from_email` | Individual email address | `"noreply@gmail.com"` |
| `ses_from_name` | Display name for sender | `"AgentForge"` |

### Optional Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ses_mail_from_domain` | `""` | Custom MAIL FROM domain |
| `enable_ses_monitoring` | `true` | CloudWatch monitoring |
| `ses_alarm_topic_arn` | `""` | SNS topic for alerts |

## Email Templates

The infrastructure creates two pre-configured email templates:

### 1. Email Verification Template
- **Name**: `{project}-{environment}-email-verification`
- **Subject**: "Verify your AgentForge email address"
- **Variables**: `{{verification_url}}`, `{{email_address}}`

### 2. Password Reset Template  
- **Name**: `{project}-{environment}-password-reset`
- **Subject**: "Reset your AgentForge password"
- **Variables**: `{{reset_url}}`, `{{email_address}}`

Templates include both HTML and text versions for maximum compatibility.

## Backend Integration

### Environment Variables

After deployment, your backend will have access to SES configuration via Secrets Manager:

```python
import boto3
import json

# Get SES configuration from Secrets Manager
secrets_client = boto3.client('secretsmanager', region_name='us-east-1')
ses_config = json.loads(
    secrets_client.get_secret_value(
        SecretId='agentforge-prod-ses-config'
    )['SecretString']
)

# Configuration values available:
# - ses_config['aws_region'] 
# - ses_config['ses_from_email']
# - ses_config['ses_from_name']
# - ses_config['ses_configuration_set']
# - ses_config['templates']['email_verification']
# - ses_config['templates']['password_reset']
```

### Sending Emails

Example Python code for sending templated emails:

```python
import boto3

ses_client = boto3.client('ses', region_name=ses_config['aws_region'])

# Send verification email
response = ses_client.send_templated_email(
    Source=ses_config['ses_from_email'],
    Destination={'ToAddresses': [user_email]},
    Template=ses_config['templates']['email_verification'],
    TemplateData=json.dumps({
        'verification_url': f'https://yourapp.com/verify-email?token={verification_token}',
        'email_address': user_email
    }),
    ConfigurationSetName=ses_config['ses_configuration_set']
)
```

## Monitoring and Troubleshooting

### CloudWatch Metrics

The infrastructure automatically sets up monitoring for:

- **Send rates**: Emails sent per time period
- **Bounce rates**: Hard and soft bounces  
- **Complaint rates**: Spam complaints
- **Delivery rates**: Successful deliveries
- **Reject rates**: Rejected before sending

### CloudWatch Alarms

Automatic alarms trigger when:
- Bounce rate exceeds 5%
- Complaint rate exceeds 0.1%

### Logs

SES events are logged to CloudWatch Logs:
- Log group: `/aws/ses/{project}-{environment}`
- Includes delivery status, bounces, and complaints

### Common Issues

#### 1. "Email address not verified" (Sandbox Mode)
- **Cause**: Individual email not verified or domain not verified
- **Solution**: Complete verification process in SES Console

#### 2. "Daily sending quota exceeded"
- **Cause**: Hit SES sending limits (200 emails/day in sandbox)
- **Solution**: Request production access to increase limits

#### 3. "Failed to send email" 
- **Cause**: Missing IAM permissions
- **Solution**: Verify ECS task role has SES permissions (automatically configured)

#### 4. DNS verification taking too long
- **Cause**: DNS propagation delays
- **Solution**: Wait up to 72 hours, check DNS records with `dig` or `nslookup`

## Security Best Practices

### 1. Use HTTPS
Always use HTTPS URLs in email links to protect user verification tokens.

### 2. Token Expiration
The infrastructure templates include 24-hour expiration for verification tokens and 1-hour for password resets.

### 3. Rate Limiting
Consider implementing rate limiting for email sending to prevent abuse.

### 4. Bounce Handling
Monitor bounce and complaint rates to maintain sender reputation.

### 5. Secrets Management
SES configuration is stored securely in AWS Secrets Manager with automatic rotation support.

## Production Checklist

Before going live with email functionality:

- [ ] Domain verification completed
- [ ] DNS records properly configured  
- [ ] SES moved out of sandbox mode
- [ ] Bounce and complaint handling configured
- [ ] Email templates tested with real addresses
- [ ] CloudWatch alarms configured
- [ ] HTTPS endpoints used in email links
- [ ] Rate limiting implemented in backend
- [ ] Backup email sending method (optional)

## Cost Optimization

### SES Pricing (US East 1)
- First 62,000 emails/month: **Free** (AWS Free Tier)
- Additional emails: **$0.10 per 1,000 emails**
- Data transfer: **$0.12 per GB** (outbound)

### CloudWatch Costs
- Log ingestion: **$0.50 per GB**
- Metric storage: **$0.30 per metric per month**
- Alarms: **$0.10 per alarm per month**

### Cost Monitoring
- Set up billing alerts for SES usage
- Monitor CloudWatch costs for log retention
- Adjust log retention periods based on compliance needs

## Support

For issues with this SES configuration:

1. **Check CloudWatch logs** for detailed error messages
2. **Verify DNS records** are correctly configured  
3. **Review SES Console** for verification status
4. **Test with CLI**: Use AWS CLI to test email sending
5. **Contact AWS Support** for SES-specific issues (production accounts)

Example CLI test:
```bash
aws ses send-email \
  --source noreply@yourdomain.com \
  --destination ToAddresses=test@yourdomain.com \
  --message Subject={Data="Test"},Body={Text={Data="Test email"}}
```