# Terraform Infrastructure as Code

## Quick Start

### Prerequisites
- Google Cloud SDK installed and authenticated: `gcloud auth login && gcloud auth application-default login`
- Terraform installed (>= 1.0)
- GCP Project with billing enabled
- `.env` file in project root with `GCP_PROJECT_ID`, `GCP_REGION`, and API keys

### Deployment Steps

1. **Generate terraform.tfvars from .env:**
   ```bash
   cd deploy/terraform
   chmod +x generate-tfvars.sh
   ./generate-tfvars.sh
   ```

2. **Initialize secrets in Secret Manager:**
   ```bash
   chmod +x init-secrets.sh
   ./init-secrets.sh  # Reads GCP_PROJECT_ID from .env automatically
   ```

3. **Initialize and deploy:**
   ```bash
   terraform init
   terraform plan    # Review changes
   terraform apply   # Deploy
   ```

4. **View outputs:**
   ```bash
   terraform output  # Get function URL
   ```

### Common Operations

**Update secrets:**
```bash
echo -n "new-value" | gcloud secrets versions add SECRET_NAME \
  --project=YOUR_PROJECT_ID --data-file=-
```

**Update function code:**
```bash
# Make code changes, then:
terraform apply
```

**Destroy infrastructure:**
```bash
terraform destroy
```

---

## Configuration

**Secret Manager (Recommended):** Set `use_secret_manager = true` in `terraform.tfvars`. Secrets are encrypted, versioned, and not stored in Terraform state.

**Direct Environment Variables (Not Recommended):** Set `use_secret_manager = false` and provide secrets in `terraform.tfvars`. Only for development.

**Outputs:** Run `terraform output` to get `function_url`, `function_name`, and `source_bucket`.

## Troubleshooting

**Authentication:** `gcloud auth application-default login`

**Permission Denied:** Ensure `roles/owner` or `roles/editor` + `roles/secretmanager.admin` + `roles/iam.serviceAccountUser`

**Deployment Fails:** Check `gcloud builds list --project=YOUR_PROJECT_ID`

### Secret Access Issues
Verify IAM bindings:
```bash
gcloud projects get-iam-policy YOUR_PROJECT_ID
```

## Comparison with deploy.sh

| Feature | deploy.sh | Terraform |
|---------|-----------|-----------|
| Infrastructure as Code | ❌ | ✅ |
| Version Control | ❌ | ✅ |
| State Management | ❌ | ✅ |
| Secret Management | Environment vars | Secret Manager |
| Multi-environment | Manual | Easy |
| Rollback | Manual | Built-in |
| Dependency Management | Manual | Automatic |

## Best Practices

1. **Use Secret Manager** for all sensitive values
2. **Version control** only `*.tf` files and `terraform.tfvars.example`
3. **Never commit** `terraform.tfvars` or `.tfstate` files
4. **Use workspaces** for multiple environments (dev/staging/prod)
5. **Review plans** before applying changes
6. **Backup state files** if using remote state

## Remote State (Optional)

For team collaboration, consider using remote state:

```hcl
# In versions.tf
terraform {
  backend "gcs" {
    bucket = "your-terraform-state-bucket"
    prefix = "chatbot-milesguo"
  }
}
```

## Notes

- Terraform references existing secrets (created by `init-secrets.sh`), doesn't create them
- Never commit `terraform.tfvars` or `.tfstate` files
- Use Secret Manager for production (secrets not in state)
- Review `terraform plan` before applying
