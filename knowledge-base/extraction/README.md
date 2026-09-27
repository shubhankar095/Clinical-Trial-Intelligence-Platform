# Extraction Service

The Extraction Service is the event-driven document ingestion pipeline for the Clinical Trial Intelligence Platform.

It receives versioned clinical documents from Amazon S3, processes them with horizontally scalable Amazon ECS Fargate workers, applies Amazon Textract OCR when native PDF text is insufficient, and writes deterministic canonical outputs to Amazon S3. Processing ownership, retries, duplicate-event safety, observability, and scale-to-zero behavior are built into the service.

This README describes the service architecture, processing lifecycle, reliability model, local development workflow, deployment process, monitoring commands, and operational procedures.

For detailed test documentation, see [`tests/README.md`](tests/README.md).

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Processing Lifecycle](#processing-lifecycle)
- [Document Paths and Metadata](#document-paths-and-metadata)
- [Document Identity and Idempotency](#document-identity-and-idempotency)
- [Processing Claims and Heartbeats](#processing-claims-and-heartbeats)
- [PDF Extraction](#pdf-extraction)
- [Canonical Storage](#canonical-storage)
- [Failure Handling and DLQ](#failure-handling-and-dlq)
- [Autoscaling](#autoscaling)
- [Observability](#observability)
- [Security](#security)
- [Repository Structure](#repository-structure)
- [Prerequisites](#prerequisites)
- [Dependency Management](#dependency-management)
- [Local Tests](#local-tests)
- [Build the Docker Image](#build-the-docker-image)
- [Terraform](#terraform)
- [Deploy to Development](#deploy-to-development)
- [Post-Deployment AWS Tests](#post-deployment-aws-tests)
- [Monitoring and Logs](#monitoring-and-logs)
- [Destroy the Development Environment](#destroy-the-development-environment)
- [Runtime Configuration](#runtime-configuration)
- [Current Limitations](#current-limitations)
- [Most-Used Commands](#most-used-commands)

---

## Overview

The Extraction Service provides:

- S3 event-driven ingestion through SQS
- Exact S3 object-version processing
- Deterministic document identities
- Duplicate-event protection
- DynamoDB-backed processing ownership
- SQS visibility and DynamoDB claim heartbeats
- Native PDF text extraction
- Textract OCR fallback
- Embedded image extraction
- Table extraction
- Canonical JSON output
- Authoritative success manifests
- Partial-output rollback
- SQS retry and dead-letter handling
- ECS scale from zero and back to zero
- Structured logs, custom metrics, alarms, and dashboards
- Unit, component, local integration, performance, and deployed AWS tests

The service currently routes PDF files to the production processor. Other file types are returned as unsupported.

---

## Architecture

```text
Source client
     │
     │ Upload versioned document
     ▼
Raw S3 bucket
     │
     │ ObjectCreated event
     ▼
Extraction SQS queue ───────────────► Extraction DLQ
     │                                  │
     │                                  ├── CloudWatch alarm
     │                                  └── SNS email notification
     ▼
ECS Fargate extraction worker
     │
     ├── DynamoDB processing registry
     │     ├── claim acquisition
     │     ├── lease renewal
     │     └── completion record
     │
     ├── Amazon Textract
     │     └── OCR for weak or scanned pages
     │
     └── Canonical S3 bucket
           ├── extracted-document.json
           ├── _SUCCESS.json
           ├── images/
           └── tables/
```

### AWS components

The Terraform configuration creates four logical infrastructure components:

- **Foundation:** VPC, public subnets, S3 buckets, SQS queue, DLQ, DynamoDB registry, security group, and SNS topic
- **Worker:** ECR repository, ECS cluster, task definition, service, IAM roles, and CloudWatch log group
- **Autoscaling:** bootstrap, backlog target tracking, queue-drained scale-in, and final scale-to-zero
- **Observability:** log-derived metrics, alarms, and CloudWatch dashboard

---

## Processing Lifecycle

```text
1. A document is uploaded under the raw bucket's documents/ prefix.
2. S3 publishes an ObjectCreated event to the extraction queue.
3. Bootstrap autoscaling starts one ECS worker if capacity is zero.
4. The worker receives the SQS message.
5. The worker starts the SQS visibility heartbeat.
6. The S3 event, source path, and version ID are validated.
7. A deterministic document ID is generated.
8. The service checks for an existing _SUCCESS manifest.
9. The worker acquires an exclusive DynamoDB processing claim.
10. The claim heartbeat renews ownership during processing.
11. The exact S3 object version is downloaded.
12. The document router selects the PDF processor.
13. Text, OCR, images, tables, pages, and offsets are extracted.
14. The canonical document is written to S3.
15. The _SUCCESS manifest is written to S3.
16. The DynamoDB claim is marked COMPLETED.
17. The SQS message is deleted.
18. The temporary local file is removed.
19. ECS capacity scales in after the queue drains.
```

A message is acknowledged only after successful canonical persistence, success-manifest creation, and processing-registry completion.

---

## Document Paths and Metadata

### Study documents

Study-specific documents must use:

```text
documents/<study-id>/<category>/<file>
```

Example:

```text
documents/STUDY001/protocols/protocol-v1.pdf
```

Supported study categories:

| Path category | Canonical type |
|---|---|
| `protocols` | `PROTOCOL` |
| `monitoring` | `MONITORING` |
| `csr` | `CSR` |
| `sap` | `SAP` |
| `ib` | `IB` |
| `tmf` | `TMF` |

### Shared documents

Shared documents must use:

```text
documents/shared/<category>/<file>
```

Supported shared categories:

| Path category | Canonical type |
|---|---|
| `sop` | `SOP` |
| `regulations` | `REGULATION` |
| `guidances` | `GUIDANCE` |
| `templates` | `TEMPLATE` |

Path-derived metadata can be supplemented or overridden by supported message metadata fields:

- `study_id`
- `document_type`
- `version`
- `sponsor`
- `phase`

---

## Document Identity and Idempotency

The document ID is a SHA-256 hash of this normalized identity payload:

```json
{
  "processing_schema_version": "extraction-v1",
  "source_bucket": "raw-bucket",
  "source_key": "documents/STUDY001/protocols/protocol.pdf",
  "source_version_id": "s3-version-id"
}
```

This provides the following guarantees:

- The same source version and schema produce the same document ID.
- A new S3 object version produces a new document ID.
- A new processing schema version produces a new document ID.
- Duplicate S3 events resolve to the same canonical location.
- Intentional reprocessing can be triggered by changing the schema version.

Idempotency is enforced through three layers:

1. Deterministic document identity
2. DynamoDB conditional processing claims
3. S3 `_SUCCESS.json` manifests

If a success manifest already exists, the service validates its identity and skips duplicate extraction. If the manifest exists but the DynamoDB completion record is missing, the service attempts to reconcile the registry from the authoritative manifest.

---

## Processing Claims and Heartbeats

### DynamoDB processing claim

Before downloading and processing a document, a worker acquires an exclusive claim containing:

```text
document_id
owner_token
status
source_bucket
source_key
source_version_id
processing_schema_version
claimed_at
updated_at
lease_expires_at
ttl
```

The conditional write succeeds only when no record exists or the previous lease has expired.

A worker can renew, complete, or release only the claim associated with its owner token.

### SQS visibility heartbeat

The worker periodically extends SQS message visibility while the message is being processed. This prevents redelivery during long-running PDF extraction or OCR.

Development configuration:

```text
Visibility extension: 600 seconds
Heartbeat interval:    180 seconds
```

### Processing-claim heartbeat

The service independently renews the DynamoDB processing lease throughout extraction.

Development configuration:

```text
Claim lease:              900 seconds
Claim heartbeat interval: 5 seconds
```

The service checks claim-heartbeat health before important persistence boundaries. If ownership is lost, normal completion does not continue.

Together, the two heartbeats protect different guarantees:

```text
SQS visibility heartbeat  → prevents message redelivery
DynamoDB claim heartbeat  → prevents document ownership expiration
```

---

## PDF Extraction

The PDF processor performs:

- Native text extraction
- Unicode NFKC normalization
- Page-level quality scoring
- OCR eligibility detection
- Textract OCR fallback
- Embedded image extraction
- Table discovery and extraction
- Page offset calculation
- Document-level count aggregation

### OCR decision

A page requires OCR when either condition is true:

```text
word_count <= MIN_WORDS_PER_PAGE
quality_score < MIN_QUALITY_SCORE
```

The quality score is the ratio of alphanumeric characters to total text length.

When OCR is required, the page is rendered as PNG and sent to Textract. If OCR fails or returns blank text, the native text is retained and a warning is recorded.

### Image extraction

Embedded images with width or height below 50 pixels are skipped. Accepted images are stored beneath the document's canonical prefix.

### Table extraction

Tables discovered by PyMuPDF are saved as JSON arrays. Canonical metadata records the table ID, source page, row count, column count, and S3 key.

### Page offsets

Each page records `start_offset` and `end_offset` into the combined document `raw_text`. This supports downstream chunking, retrieval, page citations, and traceability.

---

## Canonical Storage

Canonical outputs use the deterministic document ID:

```text
canonical-documents/
└── <document-id>/
    ├── extracted-document.json
    ├── _SUCCESS.json
    ├── images/
    │   └── image-<page>-<index>.<extension>
    └── tables/
        └── table-<page>-<index>.json
```

### Canonical document

`extracted-document.json` contains:

- Document identity and source version
- Processing schema version
- Canonical S3 location
- Clinical metadata
- Combined raw text
- Page text and offsets
- OCR decisions and counts
- Image metadata
- Table metadata
- Warnings
- Processing status

The temporary local file path is excluded from serialization.

### Success manifest

`_SUCCESS.json` is written only after the canonical document is stored successfully. It records:

- Document ID
- Source bucket, key, and version ID
- Processing schema version
- Canonical bucket and key
- Completion timestamp
- Success status

The success manifest is authoritative proof that canonical persistence completed.

---

## Failure Handling and DLQ

### Retry behavior

When processing fails, the worker does not delete the SQS message. After visibility expires, SQS makes the message available for retry.

The main extraction queue uses:

```text
Maximum receive count: 5
Message retention:      7 days
Long polling:           20 seconds
```

After the maximum receive count is reached, SQS moves the message to the extraction DLQ.

### Dead-letter queue

The DLQ uses:

```text
Retention: 14 days
Alarm:     visible DLQ messages > 0
Action:    SNS email notification
```

Typical persistent failures include:

- Corrupted or password-protected PDFs
- Invalid source paths
- Missing S3 version IDs
- Invalid queue payloads
- Persistent S3, DynamoDB, or Textract failures
- Canonical persistence failures
- Unexpected worker failures

### Rollback behavior

If PDF processing fails after assets were uploaded:

- Uploaded images are deleted where possible.
- Uploaded tables are deleted where possible.
- Extracted content and counts are reset.
- The document is marked `FAILED`.

If canonical document persistence fails after assets were created, the orchestration service also removes known image and table assets.

If manifest creation fails after the canonical document is written, the message remains unacknowledged. A retry can repair the incomplete state using deterministic keys and manifest reconciliation.

### DLQ recovery guideline

Before redriving a message:

1. Inspect the DLQ message and attributes.
2. Identify the source bucket, key, version ID, message ID, and receive count.
3. Review the corresponding ECS worker logs.
4. Determine whether the failure is document-specific or operational.
5. Correct the document, code, permissions, or infrastructure.
6. Check whether `_SUCCESS.json` already exists.
7. Redrive the message to the main extraction queue.
8. Monitor the queue, registry, canonical output, logs, and DLQ.
9. Confirm successful acknowledgement.

Idempotency checks protect replay when processing has already completed.

---

## Autoscaling

The ECS service implements this lifecycle:

```text
0 → 1 → N → 1 → 0
```

### Zero to one

When visible queue messages exist and no ECS task is running, bootstrap step scaling sets capacity to exactly one worker.

### One to maximum

Target tracking scales according to visible SQS backlog per running task.

Development values:

```text
Target backlog per worker: 5 messages
Minimum workers:           0
Maximum workers:           5
Scale-out cooldown:        60 seconds
Scale-in cooldown:         300 seconds
```

### Multiple workers to one

When visible, in-flight, and delayed messages remain zero while more than one worker is running, step scaling reduces capacity directly to one.

Development drain window:

```text
2 consecutive one-minute periods
```

### One to zero

The final worker scales to zero only when visible, in-flight, and delayed message counts remain zero and no more than one worker remains.

Development idle window:

```text
5 consecutive one-minute periods
```

Including in-flight messages in scale-in decisions prevents termination while a worker is processing a document.

---

## Observability

The service writes structured JSON logs to CloudWatch Logs and avoids intentionally logging extracted clinical text.

### Custom metrics

CloudWatch log metric filters publish:

- `ProcessingSuccesses`
- `ProcessingFailures`
- `ProcessingDurationSeconds`

### Alarms

The Terraform configuration creates alarms for:

- Visible messages in the DLQ
- Oldest extraction message age
- Worker processing failures
- Bootstrap scale-out
- Queue-drained scale-in
- Final scale-to-zero

### Dashboard

The CloudWatch dashboard includes:

- Visible, in-flight, and delayed queue messages
- Oldest message age
- DLQ depth
- Successful document count
- Processing failure count
- Average and maximum processing duration
- Backlog per running task
- ECS CPU utilization
- ECS memory utilization
- Alarm and scaling status

### Structured log fields

Operational logs include identifiers and aggregate data such as:

```text
event
document_id
message_id
source_bucket
source_key
source_version_id
processing_schema_version
processing_status
page_count
ocr_page_count
image_count
table_count
warning_count
duration_seconds
receive_count
```

---

## Security

Implemented controls include:

- S3 public-access blocking
- S3 default server-side encryption
- S3 versioning
- Source-account and source-bucket restrictions on S3-to-SQS delivery
- DynamoDB server-side encryption
- DynamoDB point-in-time recovery
- Separate ECS task and execution roles
- Scoped task permissions for S3, SQS, DynamoDB, and Textract
- No inbound ECS security-group rules
- ECR image scanning on push
- Immutable ECR tags outside development
- `latest` image tag prohibition
- Non-root container runtime
- Hashed dependency installation
- AWS account verification before deployment and destruction
- Saved Terraform deployment and destruction plans

The development environment uses public subnets and public task IPs as a cost-conscious design. Private subnets and VPC endpoints can be introduced for stricter production isolation.

---

## Repository Structure

```text
extraction/
├── Dockerfile
├── Makefile
├── README.md
├── pyproject.toml
├── requirements.txt
├── uv.lock
├── infra/
│   ├── components/
│   │   ├── autoscaling/
│   │   ├── foundation/
│   │   ├── observability/
│   │   └── worker/
│   └── config/
├── src/
│   ├── config/
│   ├── events/
│   ├── exceptions/
│   ├── models/
│   ├── ocr/
│   ├── processors/
│   ├── repositories/
│   ├── router/
│   ├── services/
│   ├── storage/
│   ├── workers/
│   └── main.py
└── tests/
    ├── aws/
    ├── component/
    ├── data/
    ├── integration/
    ├── performance/
    ├── unit/
    └── README.md
```

---

## Prerequisites

Run all commands from:

```bash
cd knowledge-base/extraction
```

Install and configure:

```text
Python 3.12 or later
AWS CLI
Docker
Terraform 1.10 or later
uv
GNU Make
```

Before the first deployment, create the Terraform state bucket configured in:

```text
infra/config/backend_config.tfvars
```

The current development backend expects:

```text
Bucket: tfstate-backend-config-dev
Region: ap-south-1
```

Recommended state-bucket controls:

```text
Versioning enabled
Default encryption enabled
Public access blocked
```

Get the active AWS account ID:

```bash
aws sts get-caller-identity \
  --query Account \
  --output text
```

The deployment targets verify that this account matches `AWS_ACCOUNT_ID`.

---

## Dependency Management

The service uses `uv` for dependency resolution and synchronization.

- `pyproject.toml` defines direct and development dependencies.
- `uv.lock` records the complete locked dependency graph.
- `requirements.txt` contains hashed production dependencies used by Docker.

Synchronize production dependencies:

```bash
make sync
```

Synchronize development dependencies:

```bash
make sync-dev
```

Intentionally upgrade dependencies:

```bash
make upgrade
```

After an upgrade, run:

```bash
make test-all
make build
```

Export production requirements:

```bash
make export-reqs
```

---

## Local Tests

Run one test category:

```bash
make test-unit
make test-component
make test-integration
make test-performance
```

Run all local tests:

```bash
make test-all
```

`make test-all` runs unit, component, local integration, and performance tests with statement and branch coverage.

The configured source-coverage requirement is:

```text
100 percent
```

The test markers defined in `pyproject.toml` are:

```text
unit
component
integration
performance
aws
```

Deployed AWS tests are intentionally run separately because they require live infrastructure.

See [`tests/README.md`](tests/README.md) for the full test strategy and AWS-test behavior.

---

## Build the Docker Image

Build and validate the production image:

```bash
make build
```

This performs:

```text
Locked dependency synchronization
Local tests with branch coverage
Hashed requirements export
Linux AMD64 image build
Application import validation
Non-root user validation
Image architecture validation
```

Default local image:

```text
extraction:dev
```

### Container characteristics

The image:

- Uses `python:3.12-slim`
- Installs hashed production dependencies with `pip --require-hashes`
- Copies only required service and shared-package source
- Runs as `appuser` with UID `10001`
- Uses Linux AMD64 for the current ECS task definition
- Starts with `python src/main.py`

Build only the image:

```bash
make docker-build
```

Validate an image:

```bash
make validate-image
```

Run the image locally:

```bash
make run
```

A normal worker run requires valid AWS credentials and the required runtime environment variables.

---

## Terraform

### Format and validate

```bash
make terraform-check
```

`terraform-check` runs formatting, backend initialization, and Terraform validation.

### Review the deployment plan

```bash
make terraform-plan \
  AWS_ACCOUNT_ID=123456789012
```

The saved plan is written to:

```text
infra/tfplan
```

### Important configuration files

```text
infra/config/backend_config.tfvars
infra/config/variables.tfvars
```

Review environment-specific bucket names, alert email, capacity, image tag, heartbeat timing, and alarm thresholds before deployment.

---

## Deploy to Development

Deploy the complete development environment and application:

```bash
make deploy-dev \
  AWS_ACCOUNT_ID=123456789012
```

With a named AWS profile:

```bash
make deploy-dev \
  AWS_PROFILE=clinical-dev \
  AWS_ACCOUNT_ID=123456789012
```

The deployment target:

```text
Verifies required tools and Docker daemon
Verifies AWS credentials and account
Restricts deployment to ENVIRONMENT=dev
Runs all local tests
Builds and validates the Docker image
Initializes and validates Terraform
Creates and applies a saved Terraform plan
Authenticates Docker with ECR
Pushes the image to ECR
Forces a new ECS deployment
Waits for ECS service stability
Displays Terraform outputs
Displays ECS, SQS, and DLQ status
```

Development uses the mutable `dev` image tag. Non-development ECR repositories are configured as immutable.

### Check deployment status

```bash
make deployment-status \
  AWS_ACCOUNT_ID=123456789012
```

This shows:

- ECS service status and capacity
- Active task definition
- Recent ECS events
- Main queue visible and in-flight counts
- DLQ visible and in-flight counts

### Show Terraform outputs

```bash
make deployment-outputs \
  AWS_ACCOUNT_ID=123456789012
```

---

## Post-Deployment AWS Tests

After deployment, run the real AWS test suite:

```bash
make test-aws \
  AWS_ACCOUNT_ID=123456789012
```

With a named profile:

```bash
make test-aws \
  AWS_PROFILE=clinical-dev \
  AWS_ACCOUNT_ID=123456789012
```

The target reads deployed values directly from Terraform outputs and runs:

```bash
pytest tests/aws -m aws
```

The AWS tests validate:

- S3 bucket accessibility, versioning, and encryption
- SQS queue, long polling, visibility, and redrive policy
- DLQ configuration and retention
- DynamoDB table, TTL, and completion records
- ECS service and task-definition configuration
- ECR image deployment
- CloudWatch log-group configuration
- Native-text PDF extraction
- Textract OCR extraction
- Table-asset extraction
- Canonical document creation
- Success-manifest creation
- Duplicate-event idempotency
- New source-version identities
- Queue drainage
- Bootstrap scale-out from zero
- Final scale-to-zero

The tests use fixtures from:

```text
tests/data/minimal_text.pdf
tests/data/scanned_page.pdf
tests/data/table_document.pdf
```

Test uploads use unique keys beneath the AWS test study prefix and are cleaned up after the test session.

The default AWS test timeout is:

```text
1200 seconds
```

No separate `scripts/aws_smoke_test.py` is required. The deployed AWS verification is implemented under `tests/aws/`.

---

## Monitoring and Logs

### Compact runtime monitor

```bash
make monitor-aws-compact \
  AWS_ACCOUNT_ID=123456789012
```

The compact monitor displays:

- ECS desired, running, and pending capacity
- Main queue visible and in-flight messages
- DLQ visible and in-flight messages
- Processing and completed registry counts
- Canonical object count
- Alarm states
- Latest scaling activity
- Derived system status

Possible statuses include:

```text
HEALTHY
IDLE, SCALED TO ZERO
WAITING FOR SCALE-OUT
STARTING WORKER
PROCESSING DOCUMENT
WAITING FOR SCALE-IN
ATTENTION REQUIRED
```

### Detailed runtime monitor

```bash
make monitor-aws \
  AWS_ACCOUNT_ID=123456789012
```

Change the refresh interval:

```bash
make monitor-aws \
  AWS_ACCOUNT_ID=123456789012 \
  AWS_MONITOR_INTERVAL=10
```

### Follow CloudWatch logs

```bash
make logs-aws \
  AWS_ACCOUNT_ID=123456789012
```

Change the log window:

```bash
make logs-aws \
  AWS_ACCOUNT_ID=123456789012 \
  AWS_LOG_SINCE=30m
```

---

## Destroy the Development Environment

First create and review the destroy plan:

```bash
make destroy-plan \
  AWS_ACCOUNT_ID=123456789012
```

The reviewed plan is saved as:

```text
infra/tfplan-destroy
```

Apply the reviewed plan:

```bash
make destroy-dev \
  AWS_ACCOUNT_ID=123456789012
```

`destroy-dev` will not run unless the saved destroy plan already exists.

The destruction workflow also verifies the AWS account and restricts the operation to `ENVIRONMENT=dev`.

Development resources are configured for easy cleanup:

- Raw and canonical S3 buckets use `force_destroy` in development.
- The development ECR repository uses `force_delete`.
- Non-development environments do not enable those destructive settings.

Only resources managed by this Terraform state are affected.

---

## Clean Local Generated Files

```bash
make clean
```

This removes local generated artifacts such as:

- `.venv`
- pytest cache
- coverage files
- Python bytecode and cache directories
- generated package metadata
- generated `requirements.txt`
- Terraform plan files

It does not delete AWS resources.

---

## Runtime Configuration

The worker validates required configuration before entering the SQS receive loop.

### Required application variables

```text
CANONICAL_DOCUMENT_BUCKET
DOCUMENT_UPLOADED_QUEUE_URL
PROCESSING_REGISTRY_TABLE
```

### Extraction variables

| Variable | Source default | Development infrastructure value | Purpose |
|---|---:|---:|---|
| `PAGES_TO_READ` | `all` | `all` unless overridden | Number of PDF pages to process |
| `MIN_WORDS_PER_PAGE` | `20` | `20` unless overridden | Native text density threshold |
| `MIN_QUALITY_SCORE` | `0.6` | `0.6` unless overridden | Native text quality threshold |
| `PROCESSING_SCHEMA_VERSION` | `extraction-v1` | `extraction-v1` | Output schema and identity version |

### SQS heartbeat variables

| Variable | Source default | Development value | Purpose |
|---|---:|---:|---|
| `SQS_VISIBILITY_EXTENSION_SECONDS` | `600` | `600` | Renewed message visibility |
| `SQS_VISIBILITY_HEARTBEAT_SECONDS` | `180` | `180` | Visibility-renewal interval |

Constraint:

```text
0 < heartbeat < extension <= 43200
```

### Processing-claim variables

| Variable | Source default | Development value | Purpose |
|---|---:|---:|---|
| `PROCESSING_CLAIM_LEASE_SECONDS` | `1800` | `900` | Exclusive document lease |
| `PROCESSING_CLAIM_HEARTBEAT_SECONDS` | `300` | `5` | Lease-renewal interval |

Constraints:

```text
claim heartbeat > 0
claim heartbeat < claim lease
claim lease > SQS visibility extension
```

The ECS task definition supplies the deployed values, so infrastructure configuration overrides source defaults at runtime.

---

## Current Limitations

### Supported formats

PDF is the only production-routed document format.

`DOCXProcessor` currently contains placeholder logic and is not registered in the document router. DOCX must therefore be considered unsupported until a real implementation and corresponding tests are added.

### Textract mode

The current OCR integration uses synchronous `DetectDocumentText` against rendered page images. Specialized form, table, or very large asynchronous Textract workflows may require a separate processor design.

### Worker concurrency

Each worker processes messages sequentially. Horizontal concurrency is provided by ECS autoscaling rather than multiple concurrent document jobs inside one task.

This simplifies:

- Memory control
- Claim ownership
- Graceful shutdown
- Message-heartbeat lifecycle
- Operational troubleshooting

### Development network model

Development Fargate tasks run in public subnets with public IP addresses to avoid NAT gateway costs. Production can adopt private subnets and VPC endpoints when stricter isolation is required.

---

## Most-Used Commands

```bash
# Enter the service directory
cd knowledge-base/extraction

# Run all local tests with branch coverage
make test-all

# Build and validate the production image
make build

# Validate Terraform
make terraform-check

# Review the Terraform deployment plan
make terraform-plan AWS_ACCOUNT_ID=123456789012

# Deploy development infrastructure and application
make deploy-dev AWS_ACCOUNT_ID=123456789012

# Check deployed infrastructure and application status
make deployment-status AWS_ACCOUNT_ID=123456789012

# Run real deployed AWS tests
make test-aws AWS_ACCOUNT_ID=123456789012

# Open compact runtime monitoring
make monitor-aws-compact AWS_ACCOUNT_ID=123456789012

# Follow application logs
make logs-aws AWS_ACCOUNT_ID=123456789012 AWS_LOG_SINCE=30m

# Review and destroy development infrastructure
make destroy-plan AWS_ACCOUNT_ID=123456789012
make destroy-dev AWS_ACCOUNT_ID=123456789012

# Remove local generated files
make clean
```

---

## Production Readiness Summary

The Extraction Service currently implements:

- Event-driven, version-aware S3 ingestion
- SQS long polling and retry delivery
- Dedicated DLQ with alarm and SNS notification
- ECS Fargate workers with scale-to-zero
- Zero-to-one bootstrap scaling
- Backlog-per-worker target tracking
- Queue-drained direct scale-in
- Safe final scale-to-zero
- Deterministic document identities
- DynamoDB processing claims
- Claim renewal heartbeat
- SQS visibility heartbeat
- Duplicate-event idempotency
- Success-manifest reconciliation
- OCR fallback
- Image and table extraction
- Partial-output cleanup
- Graceful shutdown
- Exponential receive backoff
- Structured operational logging
- Sensitive-content logging tests
- Custom CloudWatch metrics
- Operational alarms and dashboard
- Non-root, reproducible container builds
- Hashed dependencies
- ECR scanning
- Guarded deployment and destruction workflows
- Complete local and deployed AWS test layers

The remaining production hardening opportunities are primarily environment-specific controls such as private networking, customer-managed KMS keys, image signing, SBOM publication, digest-based deployments, automated CI/CD policy enforcement, and deployment rollback automation.
