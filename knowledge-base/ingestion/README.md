# Clinical Knowledge Base Ingestion

The Ingestion service transforms canonical clinical-trial documents published by the Extraction service into deterministic, searchable vector records in Amazon OpenSearch Serverless.

The service is event-driven, idempotent, and designed to scale from zero. Amazon S3 success manifests trigger Amazon SQS messages, Amazon ECS workers process one message at a time, Amazon DynamoDB provides generation ownership, and OpenSearch stores profile-specific vector indexes.

## Status

The development deployment has passed the complete local and deployed verification workflows:

- 100% unit statement and branch coverage
- contract, component, resilience, performance, and Docker integration tests
- AWS smoke, end-to-end, resilience, and performance tests
- duplicate-ingestion and DLQ-redrive scenarios
- ECS termination recovery
- queue bootstrap, drain, and scale-to-zero behavior
- Deployment-Aware Visibility Verification for OpenSearch Serverless

The current Terraform root supports **OpenSearch Serverless only**. The application retains an OpenSearch domain code path for reuse and isolated testing.

## Processing Flow

```text
Extraction writes canonical artifacts
  -> Extraction writes _SUCCESS.json last
  -> Amazon S3 sends an event to Amazon SQS
  -> queue depth bootstraps the ECS service from 0 to 1
  -> worker validates the manifest and canonical document
  -> worker creates a deterministic ingestion identity
  -> worker acquires a DynamoDB processing claim
  -> document is chunked deterministically
  -> chunks are embedded
  -> deterministic OpenSearch records are bulk indexed
  -> DAVV verifies exact record visibility
  -> result manifest is written
  -> registry is marked COMPLETED
  -> SQS message is acknowledged
  -> idle service scales back to zero
```

## Key Design Properties

### Deterministic identities

The service creates deterministic identifiers for ingestion profiles, ingestion generations, chunks, and OpenSearch records. Replaying the same logical generation therefore targets the same records instead of creating duplicates.

### At-least-once delivery safety

Amazon S3 and Amazon SQS can deliver events more than once. The service combines deterministic IDs, DynamoDB conditional claims, and idempotent OpenSearch writes so duplicate delivery does not create duplicate generations.

### Distributed ownership

Two ownership mechanisms are used:

- SQS visibility heartbeat protects message-processing time.
- DynamoDB claim heartbeat protects logical ownership of an ingestion generation.

Expired processing claims can be recovered by another worker after interruption.

### Deployment-Aware Visibility Verification

OpenSearch Serverless does not use the explicit index refresh path used by an OpenSearch domain. DAVV applies the correct verification strategy for each deployment type.

For Serverless:

```text
bulk write
  -> skip explicit refresh
  -> count records for ingestion_id
  -> poll until actual count equals expected count
  -> return retryable failure on timeout
```

The exact-count requirement detects both missing and unexpected records.

## Failure Model

### Pre-claim invalid input

Examples include malformed events, invalid manifests, or malformed canonical documents that fail before a trusted processing claim exists.

```text
message is not acknowledged
  -> SQS retries it
  -> message eventually reaches the DLQ
```

### Retryable technical failure

Examples include network errors, throttling, temporary provider failures, OpenSearch transient errors, ECS interruption, and DAVV timeout.

```text
message is retained
  -> processing retries
  -> persistent failure eventually reaches the DLQ
```

### Permanent post-claim failure

When an identified generation fails permanently after claim acquisition:

```text
failure manifest is written
  -> registry becomes FAILED
  -> message is acknowledged
```

### Success

```text
success manifest is written
  -> registry becomes COMPLETED
  -> message is acknowledged
```

## Repository Structure

```text
knowledge-base/ingestion/
├── src/
│   ├── chunkers/             # Deterministic document chunking
│   ├── config/               # Environment configuration and validation
│   ├── embedders/            # Hugging Face and Amazon Bedrock adapters
│   ├── exceptions/           # Processing and provider error taxonomy
│   ├── indexers/             # OpenSearch indexing and DAVV
│   ├── ingestion_events/     # S3/SQS event parsing and consumption
│   ├── models/               # Canonical, profile, chunk, and manifest models
│   ├── repositories/         # DynamoDB processing registry
│   ├── services/             # Pipeline orchestration services
│   ├── storage/              # S3 text and manifest stores
│   └── workers/              # Long-running ingestion worker
├── tests/                    # Local and deployed test suites
├── infra/                    # Ingestion Terraform root
├── Dockerfile                # Production worker image
├── Makefile                  # Build, test, deploy, monitor, and destroy workflows
├── pyproject.toml            # Python project and pytest configuration
└── uv.lock                   # Locked dependency graph
```

## Prerequisites

Install and configure:

- Python 3.12
- `uv`
- Docker with a running daemon
- Terraform
- AWS CLI
- AWS credentials for the target development account

The shared Platform infrastructure must be deployed first because the Ingestion Terraform root consumes its outputs through remote state.

## Local Setup

From `knowledge-base/ingestion`:

```bash
make sync-dev
```

Run the fast deterministic gate:

```bash
make test-fast
```

Run every pre-deployment suite, including Docker-backed integration:

```bash
make test-pre-deploy
```

Build and validate the production image:

```bash
make build
```

## Configuration

Application configuration is supplied through environment variables. Terraform renders these values into the ECS task definition.

Important configuration groups include:

- AWS region and environment
- canonical S3 bucket and prefixes
- SQS queue and visibility heartbeat
- DynamoDB claim lease and heartbeat
- chunk size and overlap
- embedding provider, model, dimensions, and provider options
- OpenSearch endpoint, index prefix, bulk limits, and DAVV settings
- processing-record retention

Supported application environments are:

```text
dev
uat
stage
prod
```

The current Terraform root requires:

```text
OPENSEARCH_DEPLOYMENT_TYPE=serverless
```

## Embedding Providers

### Hugging Face API

The development deployment uses the Hugging Face API and requires `HUGGINGFACE_API_TOKEN`.

Do not commit the token to Terraform variable files. Supply it through a GitHub Actions secret or a local `TF_VAR_huggingface_api_token` value. For formal production use, prefer AWS Secrets Manager and ECS secret injection.

Example local shell setup:

```bash
export TF_VAR_huggingface_api_token="$HUGGINGFACE_API_TOKEN"
```

### Amazon Bedrock

Amazon Bedrock support is implemented and unit tested. It has not been deployed end to end in the current AWS account because Bedrock access is unavailable there.

## Terraform

The Ingestion root consumes Platform outputs and creates Ingestion-owned resources such as:

- SQS queue and DLQ
- DynamoDB processing registry
- ECR repository
- ECS task definition and service
- IAM roles and policies
- OpenSearch Serverless data-access policy
- S3 notification integration
- autoscaling policies and alarms
- CloudWatch logs, alarms, and dashboard
- SNS alerting resources

Validate Terraform:

```bash
make terraform-check \
  AWS_ACCOUNT_ID=721093132332 \
  IMAGE_TAG=dev
```

Create and review a plan:

```bash
make terraform-plan \
  AWS_ACCOUNT_ID=721093132332 \
  IMAGE_TAG=dev
```

## Development Deployment

Deploy the complete development stack and image:

```bash
make deploy-dev \
  AWS_ACCOUNT_ID=721093132332 \
  IMAGE_TAG=dev
```

The deployment target runs the test/build gate, exports production dependencies, builds and validates the image, plans and applies Terraform, pushes to ECR, forces an ECS deployment, and prints outputs and runtime status.

Development intentionally uses a mutable `dev` image tag. Non-development ECR repositories use immutable tags, `latest` is prohibited, and production tags may use version or Git SHA formats.

## Runtime Operations

Show current ECS, queue, and DLQ state:

```bash
make deployment-status \
  AWS_ACCOUNT_ID=721093132332 \
  IMAGE_TAG=dev
```

Follow application logs:

```bash
make logs-aws \
  AWS_ACCOUNT_ID=721093132332 \
  IMAGE_TAG=dev \
  AWS_LOG_SINCE=30m
```

Run the compact monitor:

```bash
make monitor-aws-compact \
  AWS_ACCOUNT_ID=721093132332 \
  IMAGE_TAG=dev \
  AWS_MONITOR_INTERVAL=15
```

Run the detailed monitor:

```bash
make monitor-aws \
  AWS_ACCOUNT_ID=721093132332 \
  IMAGE_TAG=dev \
  AWS_MONITOR_INTERVAL=30
```

A healthy idle baseline is:

```text
ECS:        ACTIVE, 0 desired, 0 running, 0 pending
Main queue: 0 visible, 0 in-flight
DLQ:        0 visible, 0 in-flight
Registry:   0 processing
Status:     IDLE, SCALED TO ZERO
```

The queue-depth-empty CloudWatch alarm is expected to be in `ALARM` while the service is scaled to zero because it drives the final `1 -> 0` scaling action.

## Deployed Verification

Run every deployed AWS suite:

```bash
make test-post-deploy \
  AWS_ACCOUNT_ID=721093132332 \
  IMAGE_TAG=dev \
  RUN_DESTRUCTIVE_AWS_TESTS=1
```

The destructive flag is intentionally required because resilience tests can terminate ECS tasks and manipulate queue visibility and DLQ state.

See [`tests/README.md`](tests/README.md) for suite definitions, commands, expected baselines, and troubleshooting.

## Destruction

Create and review the development destroy plan:

```bash
make destroy-plan \
  AWS_ACCOUNT_ID=721093132332 \
  IMAGE_TAG=dev
```

Apply only the reviewed destroy plan:

```bash
make destroy-dev \
  AWS_ACCOUNT_ID=721093132332 \
  IMAGE_TAG=dev
```

## Security Notes

- Never commit provider tokens or AWS credentials.
- Prefer GitHub OIDC for AWS authentication in CI/CD.
- Store sensitive GitHub values as Actions secrets, not ordinary variables.
- Do not upload Terraform plans containing sensitive values as public artifacts.
- Development currently uses public networking for Hugging Face API access.
- Production networking should use private subnets and controlled egress.
- Destructive AWS tests must never target production.

## Known Follow-up Work

The current implementation is fully verified in development. Production-hardening items include:

- AWS Secrets Manager integration for runtime provider secrets
- canonical-object checksum verification
- required S3 object-version lineage in stage/prod
- explicit S3 bucket-notification ownership
- excess-record repair for DAVV mismatch
- complete OpenSearch mapping fingerprint validation
- profile/index lifecycle governance
- private production networking
- destructive-test concurrency locking
- deployed Amazon Bedrock verification when account access is available

## Additional Documentation

- [`tests/README.md`](tests/README.md): test architecture and commands
- [`infra/README.md`](infra/README.md): Terraform root structure and safety notes
