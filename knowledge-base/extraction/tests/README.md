# Extraction Service Test Suite

This directory contains the automated test suite for the Clinical Trial Intelligence Platform Extraction Service.

The suite validates the service at five levels:

- Unit tests
- Component tests
- Local integration tests
- Performance tests
- Post-deployment AWS tests

Together, these tests cover document registration, deterministic identity, PDF extraction, OCR fallback, images and tables, canonical storage, SQS worker behavior, DynamoDB processing claims, heartbeat renewal, duplicate-event handling, failure recovery, observability safety, deployed AWS infrastructure, and the complete scale-from-zero lifecycle.

For service architecture, build, deployment, and runtime operations, see [`../README.md`](../README.md).

---

## Table of Contents

- [Test Structure](#test-structure)
- [Test Markers](#test-markers)
- [Testing Strategy](#testing-strategy)
- [Unit Tests](#unit-tests)
- [Component Tests](#component-tests)
- [Local Integration Tests](#local-integration-tests)
- [Performance Tests](#performance-tests)
- [AWS Tests](#aws-tests)
- [Test Fixtures](#test-fixtures)
- [Running Tests](#running-tests)
- [Coverage](#coverage)
- [AWS Test Requirements](#aws-test-requirements)
- [AWS Test Lifecycle](#aws-test-lifecycle)
- [Failure and Reliability Coverage](#failure-and-reliability-coverage)
- [Logging Safety](#logging-safety)
- [Troubleshooting](#troubleshooting)
- [Adding New Tests](#adding-new-tests)
- [Test Completion Checklist](#test-completion-checklist)

---

## Test Structure

```text
tests/
├── README.md
├── conftest.py
├── data/
│   ├── minimal_text.pdf
│   ├── scanned_page.pdf
│   └── table_document.pdf
├── aws/
│   ├── conftest.py
│   ├── test_document_extraction.py
│   ├── test_duplicate_processing.py
│   ├── test_infrastructure.py
│   ├── test_processing_registry.py
│   └── test_queue_and_autoscaling.py
├── component/
│   ├── test_document_extraction_service.py
│   ├── test_extraction_worker.py
│   ├── test_extraction_worker_run_loop.py
│   └── test_logging_safety.py
├── integration/
│   ├── test_local_pdf_extraction.py
│   └── test_pdf_failure_modes.py
├── performance/
│   └── test_large_pdf_processing.py
└── unit/
    ├── config/
    ├── events/
    ├── ocr/
    ├── processors/
    ├── repositories/
    ├── router/
    ├── services/
    ├── storage/
    └── test_main.py
```

The exact filenames under `tests/aws/` may evolve as scenarios are split or consolidated. All live-cloud tests must remain under the `aws` marker.

---

## Test Markers

Markers are registered in `pyproject.toml`:

```toml
markers = [
    "unit: fast isolated unit tests",
    "component: service and worker component tests",
    "integration: local integration tests using real files",
    "performance: slower resource and scalability tests",
    "aws: post-deployment tests using real AWS services",
]
```

Use the marker that represents the highest external dependency used by the test.

| Marker | External dependencies | Primary purpose |
|---|---|---|
| `unit` | None; dependencies mocked | Validate one class or function in isolation |
| `component` | AWS mocked; several application components collaborate | Validate orchestration and worker behavior |
| `integration` | Real local PDF files; no live AWS dependency | Validate the real PDF processing stack locally |
| `performance` | Generated local workload; no live AWS dependency | Validate consistency on larger documents |
| `aws` | Deployed AWS infrastructure and valid credentials | Validate real cloud resources and complete deployed behavior |

Local integration tests and AWS tests are intentionally separate. The `integration` marker does not mean live AWS access.

---

## Testing Strategy

The suite is organized around several core guarantees.

### Correctness

The extracted canonical document must accurately represent:

- Source identity
- Source version
- Processing schema version
- Native and OCR text
- Page offsets
- Page, image, and table counts
- Canonical object locations
- Processing status

### Idempotency

Repeated delivery of the same source version must not create conflicting canonical documents or repeat completed extraction unnecessarily.

### Ownership safety

Only the worker holding the active DynamoDB processing claim may renew, complete, or release that claim.

### Long-running processing safety

SQS visibility and DynamoDB processing ownership are renewed independently during active processing.

### Failure safety

Failures must not:

- Acknowledge an unsuccessful queue message
- Hide the original exception
- Leave known partial image and table assets without cleanup attempts
- Mark a registry record completed before canonical persistence and manifest creation
- Log extracted clinical text

### Deployment confidence

Live AWS tests verify that the infrastructure, IAM permissions, image deployment, event integration, extraction workflow, and autoscaling policies operate together after deployment.

---

## Unit Tests

Unit tests validate individual classes and functions with external dependencies mocked.

Run:

```bash
make test-unit
```

Equivalent pytest command:

```bash
PYTHONPATH="src:../../packages/aws_utils:../../packages/utils" \
uv run --locked --no-sync python -m pytest \
  tests/unit \
  -v
```

### Configuration

Configuration tests validate:

- Required runtime settings
- Reporting of all missing required settings
- `PAGES_TO_READ` values
- Minimum word threshold
- Text quality range
- SQS visibility extension limits
- SQS heartbeat timing
- Processing schema version
- Processing claim lease timing
- Processing claim heartbeat timing
- Configuration parse failures for invalid numeric values

The timing relationships tested include:

```text
SQS heartbeat < SQS visibility extension
Processing claim heartbeat < processing claim lease
Processing claim lease > SQS visibility extension
```

### Event consumers

Event-consumer tests validate:

- Base consumer interfaces
- SQS receive delegation
- Message deletion delegation
- Visibility-change delegation
- Zero-second visibility release
- AWS service failure propagation

### OCR

OCR tests validate:

- Textract receives the original image bytes
- Only `LINE` blocks are returned
- Line ordering is preserved
- Unicode is preserved
- Empty responses return an empty string
- Required response fields are enforced
- Textract failures propagate

### PDF processor

PDF processor unit tests cover:

- Text quality scoring
- OCR eligibility
- Page limits
- Native text extraction
- Page offsets
- OCR success
- OCR failure fallback
- Empty OCR result fallback
- Missing OCR processor warnings
- Page rendering as PNG
- Meaningful image filtering
- Image upload continuation after individual failures
- Table extraction and dimensions
- Table discovery and extraction failures
- Uploaded-asset tracking
- Rollback after fatal processing failures
- Warning generation
- Clean failed-document state

### Unsupported files and routing

Router and unsupported-processor tests validate:

- PDF processor selection
- Case-insensitive extensions
- Leading-period removal
- Unsupported extension routing
- Processor-factory failure propagation
- Configured PDF processor dependencies
- Failed status for unsupported files

### Document identity

Identity tests validate:

- Deterministic SHA-256 output
- Exact normalized identity payload
- Removal of leading and trailing spaces
- Required identity fields
- Different source versions produce different IDs
- Different schema versions produce different IDs
- Unicode source keys and version IDs

### Document registration

Registration tests validate:

- Study-document registration
- Shared-document registration
- Study ID normalization
- S3 metadata overrides
- Path metadata fallback
- File extension normalization
- Required source version ID
- Path component validation
- Root-folder validation
- Required file extension
- Supported study categories
- Supported shared categories
- Identity-service failure propagation

### Processing registry

Processing registry tests validate the full DynamoDB claim lifecycle:

```text
acquire → renew → mark completed
                ↘ release on failure
```

Covered behavior includes:

- Constructor validation
- DynamoDB key construction
- Conditional-failure recognition
- Claim acquisition attributes
- Owner-token generation
- Lease and TTL calculation
- Claim contention translation
- Lease renewal
- Claim-loss translation
- Completion update
- Removal of `lease_expires_at` after completion
- Conditional release
- Safe handling when ownership has already been lost
- Propagation of unexpected DynamoDB failures

### Heartbeats

Message-visibility heartbeat tests validate:

- Initial state
- Daemon-thread creation
- Idempotent start
- Visibility extension
- Failure recording
- Stop-event behavior
- Thread joining

Processing-claim heartbeat tests validate:

- Interval validation
- Daemon-thread creation
- Idempotent start and stop
- Claim renewal
- Updated claim storage
- Claim-loss recording
- Unexpected renewal failure recording
- Failure translation
- Thread shutdown
- Detection of a heartbeat thread that does not stop cleanly

### Storage

Storage tests validate:

- Canonical object-key construction
- Image-key construction
- Table-key construction
- Empty document-ID rejection
- S3 key independence from filenames
- Document-folder collision prevention
- S3 key-length safety
- Canonical serialization
- Exclusion of temporary local paths
- Unicode preservation
- Metadata, page, image, and table serialization
- Correct image content types
- Upload and deletion delegation
- Success-manifest creation
- Manifest loading and validation
- Identity mismatch detection
- Rejection of non-success manifests
- Upload failure propagation

### Application entry point

Main-module tests validate:

- Runtime configuration validation
- Worker construction
- Worker execution
- The `python -m` entry-point behavior

---

## Component Tests

Component tests validate collaboration among application services while AWS dependencies remain replaced with fakes or mocks.

Run:

```bash
make test-component
```

### Document extraction service

`DocumentExtractionService` component tests validate the orchestration sequence:

```text
register
  → check success manifest
  → acquire processing claim
  → start claim heartbeat
  → download exact source version
  → select processor
  → process document
  → persist canonical document
  → persist success manifest
  → stop heartbeat
  → mark registry completed
  → delete temporary file
```

Covered scenarios include:

- Successful full lifecycle
- Exact source-version download
- Processor returning `FAILED`
- Processor exception
- Source download failure
- Registration failure
- Claim contention
- Canonical save failure and asset cleanup
- Cleanup failure preserving the original save exception
- Manifest save failure
- Claim completion failure
- Claim heartbeat failure before persistence
- Existing success-manifest short circuit
- Registry reconciliation from a manifest
- Reconciliation under registry contention
- Manifest arriving after claim acquisition
- Manifest identity mismatch
- Reconciliation completion failure
- Processing-claim release failure
- Temporary-file deletion failure
- Processor-managed path cleanup
- Processor selection from the registered format
- Empty canonical object key during cleanup
- Heartbeat stop failure before claim completion

### Extraction worker

Worker component tests validate:

- Successful message acknowledgement
- Failed document remaining unacknowledged
- Extraction exception behavior
- Claim-contention deferral
- Malformed JSON rejection
- Non-object JSON rejection
- S3 test-event acknowledgement
- Multi-record S3 event processing
- No acknowledgement when a later record fails
- URL-decoded object keys
- Source version forwarding
- Rejection of missing version IDs
- Empty or malformed `Records`
- Missing bucket or object key
- Unsupported event sources
- Direct custom-message support
- Direct-message metadata validation
- Unsupported message formats
- Missing receipt-handle handling
- Duplicate-document acknowledgement
- Immediate release of unstarted messages during shutdown
- Safe visibility-release failure handling
- Default extraction-service creation
- SQS heartbeat degradation after successful processing
- Direct object processing version validation

### Worker run loop

Run-loop tests validate:

- SIGTERM and SIGINT shutdown flags
- Idempotent shutdown requests
- Signal-handler registration
- Exit after shutdown
- Batch processing
- No new processing after shutdown is requested
- Exponential receive backoff
- Backoff reset after a successful receive
- Sixty-second backoff cap

Expected receive backoff sequence:

```text
2, 4, 8, 16, 32, 60, 60, ... seconds
```

### Logging safety

Logging component tests validate that:

- Successful processing does not log `raw_text`.
- Failure logs do not include document content.
- Structured success records contain counts and identifiers, not extracted content.
- Failure logs do not include the complete queue message body.

---

## Local Integration Tests

Local integration tests use real PDF files and the real `PDFProcessor`, but do not call live AWS services.

Run:

```bash
make test-integration
```

These tests replace cloud-backed image, table, or OCR services with deterministic local implementations while retaining real PDF parsing and rendering.

### Native-text PDF

The minimal-text fixture validates:

- Real native text extraction
- Page count
- No unnecessary OCR
- No unexpected images or tables
- Page extraction method
- Page offsets into combined raw text

### Scanned PDF

The scanned fixture validates:

- Real PDF page rendering
- Fake deterministic OCR input and output
- PNG image bytes passed to OCR
- OCR page count
- OCR extraction method
- Embedded raster-image extraction

### Table PDF

The table fixture validates:

- Real vector-table discovery
- Extracted row values
- Row and column counts
- Table ID and page number
- Table-store interaction
- Page text and offsets

### PDF failure modes

Failure-mode integration tests validate:

- Corrupted PDF failure
- Truncated PDF consistency, whether PyMuPDF recovers or rejects the file
- Password-protected PDF failure without a password
- Defined behavior for a valid blank page
- Warning when OCR is required but no OCR processor is configured
- Clean failed-document state

---

## Performance Tests

Performance tests exercise larger local documents and validate consistency rather than enforcing a machine-dependent wall-clock threshold.

Run:

```bash
make test-performance
```

Current coverage generates and processes a 50-page native-text PDF.

The test validates:

- Successful processing
- Exactly 50 extracted pages
- Count and collection consistency
- No OCR for adequate native text
- Non-empty combined text
- Page extraction methods
- Page offsets
- Empty warning list

The test prints diagnostic duration and document-size information:

```text
pages=<count>
duration_seconds=<duration>
raw_text_chars=<characters>
```

The output is informational. The test does not currently fail on a fixed duration threshold because local and CI hardware can differ significantly.

---

## AWS Tests

AWS tests run against the deployed development environment and are marked:

```python
pytestmark = pytest.mark.aws
```

Run them only after successful deployment:

```bash
make test-aws \
  AWS_ACCOUNT_ID=123456789012
```

With an AWS profile:

```bash
make test-aws \
  AWS_PROFILE=clinical-dev \
  AWS_ACCOUNT_ID=123456789012
```

The Make target obtains all deployment identifiers from Terraform outputs before executing:

```bash
pytest tests/aws -m aws -v -s
```

### Infrastructure validation

The AWS suite validates deployed resource configuration, including:

- Raw and canonical S3 bucket availability
- S3 versioning
- S3 encryption
- Extraction queue attributes
- SQS long polling
- Queue visibility timeout
- Redrive policy
- DLQ ARN and retention
- SQS maximum receive count
- DynamoDB table availability
- DynamoDB TTL configuration
- ECS cluster and service
- ECS task-definition environment
- ECS runtime platform and image
- ECR repository image
- CloudWatch log group

### Native-text pipeline

The native PDF AWS test validates:

```text
fixture upload
  → S3 event
  → SQS delivery
  → ECS bootstrap
  → processing claim
  → PDF extraction
  → canonical document
  → success manifest
  → COMPLETED registry entry
  → queue drain
```

Assertions include:

- Successful processing status
- Exact source bucket, key, and version ID
- Expected processing schema version
- Deterministic document ID
- Expected canonical key
- Page content and counts
- Canonical document identity consistency
- Success-manifest consistency
- Registry completion
- Removal of `lease_expires_at` after completion

### Textract OCR pipeline

The scanned PDF AWS test validates:

- Real S3 event delivery
- Real ECS worker processing
- Real Textract OCR invocation
- OCR page count
- OCR extraction method
- Canonical output
- Success manifest
- Registry completion

### Table pipeline

The table-document AWS test validates:

- Native PDF text extraction
- Table discovery
- Canonical table metadata
- Stored table JSON
- Expected row and column counts
- Canonical document and manifest consistency

### Duplicate-event behavior

AWS duplicate-event tests validate that a repeated event for the same bucket, key, version ID, and processing schema:

- Resolves to the same deterministic document ID
- Uses the existing success manifest
- Avoids conflicting canonical output
- Leaves the registry in `COMPLETED`
- Can be safely acknowledged

### New source version

Versioning tests upload a new version of the same source key and verify:

- A new S3 version ID is generated.
- The deterministic document ID changes.
- A separate canonical document prefix is used.
- Source-version references remain consistent across registry, manifest, and canonical payload.

### Queue and autoscaling lifecycle

The autoscaling test validates the deployed lifecycle:

```text
queue drained and service at zero
        │
        ▼
upload versioned test document
        │
        ▼
visible SQS message
        │
        ▼
bootstrap ECS capacity to at least one
        │
        ▼
process document successfully
        │
        ▼
queue and DLQ drain
        │
        ▼
scale final worker back to zero
```

The test allows up to 15 minutes for bootstrap and processing and up to 30 minutes for final scale-to-zero, matching the delayed nature of CloudWatch alarms, ECS startup, and autoscaling evaluation windows.

Final assertions require:

```text
ECS service status: ACTIVE
desired tasks:       0
running tasks:       0
pending tasks:       0
DLQ visible:         0
DLQ in-flight:       0
```

---

## Test Fixtures

The shared PDF fixtures are stored under:

```text
tests/data/
```

### `minimal_text.pdf`

A searchable PDF used to validate native text extraction without OCR.

Expected characteristics:

- One page
- Native searchable text
- No OCR required
- No table
- No embedded image expected

### `scanned_page.pdf`

An image-based PDF used to validate OCR behavior.

Expected characteristics:

- One scanned page
- Native text insufficient
- OCR required
- Embedded raster image available

### `table_document.pdf`

A PDF containing a vector table used to validate table discovery and storage.

Expected characteristics:

- One page
- Native text available
- One table
- Four rows
- Three columns

When adding fixtures:

- Keep them small and deterministic.
- Do not include real patient, participant, sponsor-confidential, or regulated clinical data.
- Document the fixture's expected extraction behavior.
- Avoid files with unstable metadata that changes on every generation unless the tests ignore it.

---

## Running Tests

Run commands from:

```bash
cd knowledge-base/extraction
```

### Make targets

Run unit tests:

```bash
make test-unit
```

Run component tests:

```bash
make test-component
```

Run local integration tests:

```bash
make test-integration
```

Run performance tests:

```bash
make test-performance
```

Run all local tests with coverage:

```bash
make test-all
```

Run deployed AWS tests:

```bash
make test-aws AWS_ACCOUNT_ID=123456789012
```

### Direct pytest commands

Run by directory:

```bash
pytest tests/unit -v
pytest tests/component -v
pytest tests/integration -v
pytest tests/performance -m performance -v -s
pytest tests/aws -m aws -v -s
```

Run by marker:

```bash
pytest -m unit
pytest -m component
pytest -m integration
pytest -m performance
pytest -m aws
```

Run all tests except live AWS tests:

```bash
pytest -m "not aws"
```

Run a single file:

```bash
pytest tests/component/test_document_extraction_service.py -v
```

Run a single test:

```bash
pytest \
  tests/component/test_document_extraction_service.py::test_successful_document_completes_full_lifecycle \
  -v
```

Stop after the first failure:

```bash
pytest -x
```

Show local variables in tracebacks:

```bash
pytest -l
```

`make` targets should be preferred for normal development because they synchronize the locked environment and set the repository `PYTHONPATH` consistently.

---

## Coverage

Coverage configuration is defined in `pyproject.toml`:

```toml
[tool.coverage.run]
branch = true
source = ["src"]

[tool.coverage.report]
show_missing = true
fail_under = 100
```

Run the configured local coverage gate:

```bash
make test-all
```

The command includes:

```bash
--cov=src
--cov-branch
--cov-report=term-missing
```

The 100 percent requirement applies to measured source statement and branch coverage. It is a regression gate, not a substitute for behavioral test quality.

Live AWS tests are not included in this local coverage gate because they validate deployed infrastructure and behavior rather than increasing local source coverage.

---

## AWS Test Requirements

AWS tests require:

- Applied Terraform infrastructure
- A deployed ECS image
- Valid AWS credentials
- Access to the configured development account and region
- Confirmed SNS subscription if operational alarm email is being inspected
- Adequate time for ECS and CloudWatch autoscaling transitions

The Makefile target retrieves these values from Terraform:

```text
RAW_BUCKET
CANONICAL_BUCKET
EXTRACTION_QUEUE_URL
EXTRACTION_DLQ_ARN
PROCESSING_REGISTRY_TABLE
ECS_CLUSTER
ECS_SERVICE
CLOUDWATCH_LOG_GROUP
ECR_REPOSITORY_URL
```

It also supplies:

```text
AWS_DEFAULT_REGION
PROCESSING_SCHEMA_VERSION
IMAGE_TAG
AWS_TEST_TIMEOUT
```

Default development values include:

```text
Region:                    ap-south-1
Processing schema version: extraction-v1
Image tag:                 dev
AWS test timeout:          1200 seconds
```

Do not run the AWS suite against an unapproved account or environment.

---

## AWS Test Lifecycle

A safe deployed-test workflow is:

```bash
# 1. Deploy and wait for ECS stability
make deploy-dev AWS_ACCOUNT_ID=123456789012

# 2. Inspect deployed state
make deployment-status AWS_ACCOUNT_ID=123456789012

# 3. Run live AWS tests
make test-aws AWS_ACCOUNT_ID=123456789012

# 4. Inspect runtime state if needed
make monitor-aws-compact AWS_ACCOUNT_ID=123456789012

# 5. Follow worker logs during investigation
make logs-aws AWS_ACCOUNT_ID=123456789012 AWS_LOG_SINCE=30m

# 6. Review and destroy development resources when finished
make destroy-plan AWS_ACCOUNT_ID=123456789012
make destroy-dev AWS_ACCOUNT_ID=123456789012
```

### Isolation

AWS tests should use unique object keys and retain the returned source version ID. The exact version ID must be used when locating canonical outputs and registry records.

### Cleanup

The AWS test fixtures and helpers should clean up test-created resources where appropriate, including:

- Raw test object versions
- Canonical document objects
- Success manifests
- Extracted image and table assets
- Processing registry records

If a test is interrupted, inspect and clean residual test data before repeating destructive or count-sensitive scenarios.

### Cost

AWS tests can incur charges for:

- S3 requests and storage
- SQS requests
- DynamoDB requests
- Textract OCR
- ECS Fargate runtime
- CloudWatch logs, metrics, and alarms

The suite is intended for controlled post-deployment validation, not continuous unbounded polling.

---

## Failure and Reliability Coverage

The suite explicitly tests the following failure boundaries.

### Before claim acquisition

- Invalid path
- Missing source version
- Registration failure
- Existing success-manifest validation failure

Expected result:

```text
No source download
No canonical persistence
No processing claim created
No message acknowledgement
```

### During claim acquisition or renewal

- Active claim owned by another worker
- Conditional renewal failure
- Unexpected DynamoDB failure
- Heartbeat thread failure
- Heartbeat stop failure

Expected result:

```text
No unsafe completion
No acknowledgement on incomplete processing
Owned claim released where possible
Original failure remains visible
```

### During source download or processing

- S3 download failure
- Processor exception
- Processor returns FAILED
- Corrupted or encrypted PDF
- OCR failure
- Image extraction failure
- Table discovery or extraction failure

Expected behavior depends on severity:

- Recoverable page or asset failures produce warnings and continue.
- Fatal document failures clear extracted state and remain unacknowledged.

### During persistence

- Canonical document save failure
- Asset cleanup failure
- Success-manifest save failure
- Registry completion failure

The success ordering under test is:

```text
canonical document
    → success manifest
    → registry COMPLETED
    → SQS acknowledgement
```

### During shutdown and receive failures

- Repeated SIGTERM or SIGINT
- Shutdown after a batch is received
- Visibility release failure
- Repeated SQS receive failure
- Backoff cap

Expected result:

- The active message is allowed to finish.
- New messages are not started after shutdown.
- An unstarted received message is returned to SQS where possible.
- Receive errors back off exponentially without terminating the worker.

---

## Logging Safety

Clinical extraction systems must avoid accidental content exposure through operational logs.

The logging-safety tests use a sentinel value:

```text
SENSITIVE_CLINICAL_VALUE_12345
```

They verify that this value does not appear in logs during successful or failed processing.

Tests also verify that:

- `raw_text` is not attached to structured success records.
- Complete SQS message bodies are not logged on failure.
- Counts and identifiers are available for troubleshooting.
- Processing status and source version remain observable without document content.

When adding logs, prefer:

```text
document_id
message_id
source key
source version
processing status
counts
duration
error category
```

Do not log:

```text
raw extracted text
OCR output
table cell contents
complete message bodies
credentials or tokens
participant or patient data
```

Add or extend logging-safety tests whenever logging fields change.

---

## Troubleshooting

### Tests cannot import service modules

Run tests through the Makefile:

```bash
make test-unit
```

The Makefile sets:

```text
src:../../packages/aws_utils:../../packages/utils
```

as the required `PYTHONPATH`.

### Locked environment is out of date

Check and synchronize:

```bash
uv lock --check
make sync-dev
```

For an intentional upgrade:

```bash
make upgrade
```

Then rerun all tests and rebuild the image.

### AWS tests cannot find deployment values

Confirm Terraform initialization and state access:

```bash
make deployment-outputs AWS_ACCOUNT_ID=123456789012
```

Confirm the expected backend bucket and region in:

```text
infra/config/backend_config.tfvars
```

### ECS does not scale from zero quickly

Inspect:

```bash
make monitor-aws-compact AWS_ACCOUNT_ID=123456789012
```

Check:

- Visible queue message count
- Bootstrap alarm state
- Desired and pending ECS task counts
- Recent scaling activity
- ECS service events

CloudWatch metrics and autoscaling alarms are eventually consistent, so a delay of several minutes can be valid.

### Queue does not drain

Check:

- Visible messages
- In-flight messages
- DLQ messages
- Processing registry status
- Worker logs
- SQS visibility heartbeat logs
- Processing claim heartbeat logs

Use:

```bash
make monitor-aws AWS_ACCOUNT_ID=123456789012
make logs-aws AWS_ACCOUNT_ID=123456789012 AWS_LOG_SINCE=30m
```

### Service does not scale to zero

The final scale-to-zero policy requires:

```text
visible messages = 0
in-flight messages = 0
delayed messages = 0
running tasks <= 1
empty state sustained for the configured window
```

Development requires five consecutive one-minute periods before the final worker is set to zero. ECS stabilization adds additional time.

### AWS test leaves residual data

Use the test run ID, source key, document ID, or canonical prefix to locate residual objects and registry records. Remove only resources created by the test run.

### DLQ is not empty

Do not purge it without investigation.

1. Inspect the message and attributes.
2. Review worker logs for the message ID and source key.
3. Identify the persistent failure.
4. Fix the document, application, permissions, or infrastructure.
5. Redrive only after the cause is addressed.

---

## Adding New Tests

### Choose the correct layer

Use `unit` when one class or function can be tested with mocks.

Use `component` when validating collaboration among the worker, orchestration service, heartbeats, stores, or registry.

Use `integration` when exercising real local PDF behavior without live AWS access.

Use `performance` for larger or slower local workloads.

Use `aws` only when the behavior requires deployed AWS resources, IAM, service integration, or autoscaling.

### Naming

Test files:

```text
test_<subject>.py
```

Test functions:

```text
test_<behavior>_<expected_result>
```

Prefer behavior-focused names such as:

```python
def test_manifest_save_failure_prevents_completion():
    ...
```

rather than names tied only to internal method calls.

### Marker

Set one module-level marker:

```python
pytestmark = pytest.mark.unit
```

or the appropriate alternative.

### Assertions

For orchestration and reliability tests, assert both the positive result and prevented side effects.

Example concerns:

- Was the message deleted?
- Was the claim completed or released?
- Was the exact S3 version used?
- Were assets uploaded or cleaned?
- Was the manifest written?
- Was sensitive content excluded from logs?

### AWS tests

For live AWS tests:

- Use unique keys.
- Capture the exact source version ID.
- Poll with bounded timeouts.
- Include useful timeout diagnostics.
- Wait for eventual consistency where required.
- Keep the DLQ empty.
- Clean created resources.
- Avoid assumptions about immediate ECS or CloudWatch state changes.

### Fixtures

Never add real clinical or personal data to test fixtures. Use synthetic, minimal, deterministic documents.

---

## Test Completion Checklist

Before merging a source change:

```text
[ ] The correct test layer was selected.
[ ] Success behavior is covered.
[ ] Relevant failure behavior is covered.
[ ] Side effects and prevented side effects are asserted.
[ ] Logging remains free of extracted content.
[ ] make test-all passes.
[ ] Statement and branch coverage remain at the configured threshold.
[ ] The production image still builds and validates when dependencies change.
```

Before accepting an infrastructure or deployment change:

```text
[ ] make terraform-check passes.
[ ] The Terraform plan has been reviewed.
[ ] make deploy-dev succeeds in the expected AWS account.
[ ] make test-aws passes.
[ ] The main queue drains.
[ ] The DLQ remains empty.
[ ] The registry reaches the expected state.
[ ] Canonical objects and manifests are consistent.
[ ] ECS scales out from zero.
[ ] ECS returns to zero after the configured idle window.
[ ] CloudWatch alarms and dashboard behavior are reviewed.
```

---

## Quick Reference

```bash
# Enter the service directory
cd knowledge-base/extraction

# Run individual local layers
make test-unit
make test-component
make test-integration
make test-performance

# Run the complete local coverage gate
make test-all

# Deploy development before live AWS tests
make deploy-dev AWS_ACCOUNT_ID=123456789012

# Run real deployed AWS tests
make test-aws AWS_ACCOUNT_ID=123456789012

# Monitor a live test run
make monitor-aws-compact AWS_ACCOUNT_ID=123456789012

# Follow worker logs
make logs-aws AWS_ACCOUNT_ID=123456789012 AWS_LOG_SINCE=30m

# Clean generated local test artifacts
make clean
```
