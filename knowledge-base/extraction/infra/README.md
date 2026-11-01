# Extraction Infrastructure

Terraform root module for the Clinical Knowledge Base Extraction service.

## Structure

- `main.tf`: queue, registry, repository, security group, notifications
- `runtime.tf`: IAM, logs, ECS task definition and service
- `operations.tf`: autoscaling and monitoring
- `integrations.tf`: Platform remote state and S3-to-SQS routing
- `locals.tf`: names, standard tags, labels, descriptions, derived values
- `providers.tf`: backend and AWS provider
- `variables.tf`: root input contract
- `outputs.tf`: service outputs
- `config/`: backend and environment values
- `templates/`: Extraction-specific IAM, ECS, and SQS policies

## Safety

This package is intended for a new deployment with an empty Extraction state.
No `moved.tf`, import, or state-migration declarations are required. Before the
first apply, confirm that `terraform state list` returns no managed resources.
Deploy the shared Platform root first because this root consumes Platform outputs
through Terraform remote state.

## Validate

```bash
terraform -chdir=knowledge-base/extraction/infra fmt -recursive
terraform -chdir=knowledge-base/extraction/infra init -backend=false
terraform -chdir=knowledge-base/extraction/infra validate
```
