# Ingestion Test Guide

The Ingestion test suite verifies deterministic processing, provider behavior, infrastructure contracts, distributed ownership, retry handling, OpenSearch visibility, AWS deployment behavior, and scale-to-zero operation.

Run commands from:

```text
knowledge-base/ingestion
```

## Test Principles

The suite is intentionally layered:

```text
unit
  -> contract
  -> component
  -> local resilience
  -> local performance
  -> Docker integration
  -> AWS smoke
  -> AWS end-to-end
  -> AWS resilience
  -> AWS performance
```

A lower-level test failure should be fixed before progressing to deployed tests. AWS tests operate on real development resources and should run only against an isolated `dev` environment.

## Test Layout

```text
tests/
├── unit/                    # Isolated source behavior and branch coverage
├── contract/                # Cross-module and artifact contracts
├── component/               # In-memory pipeline composition
├── integration/             # Docker-backed AWS/OpenSearch integration
├── resilience/              # Local retry and duplicate scenarios
├── performance/             # Local parsing and chunking budgets
├── aws/
│   ├── smoke/               # Deployment access and small real ingestion
│   ├── e2e/                 # Success, duplicate, and DLQ failure lifecycle
│   ├── resilience/          # Claims, DLQ, ECS termination, redelivery
│   ├── performance/         # Queue drain, scale-out, scale-to-zero
│   └── support/             # Deployment, polling, fixtures, cleanup
└── data/                    # Canonical test artifacts
```

## Local Suites

### Unit tests

```bash
make test-unit
```

Covers isolated application behavior without AWS.

### Coverage gate

```bash
make test-coverage
```

Runs unit tests with statement and branch coverage over `src`. The configured gate requires 100% coverage.

### Contract tests

```bash
make test-contract
```

Verifies contracts such as:

- canonical artifact references
- committed fixture consistency
- deterministic mapping assumptions
- infrastructure/application configuration wiring
- OpenSearch Serverless DAVV configuration propagation

### Component tests

```bash
make test-component
```

Exercises composed ingestion pipelines using test doubles at external provider boundaries.

### Local resilience tests

```bash
make test-resilience-local
```

Covers duplicate claims and provider-failure classification without deployed AWS resources.

### Local performance tests

```bash
make test-performance-local
```

Checks local parsing and chunking budgets. These tests are regression guards, not production throughput SLOs.

### Docker integration tests

```bash
make test-integration
```

Starts the integration Docker Compose stack, runs local integration tests, and always tears the stack down.

## Combined Local Workflows

### Fast developer feedback

```bash
make test-fast
```

Runs:

```text
coverage
contract
component
local resilience
```

It excludes Docker, AWS, and local performance tests.

### Complete pre-deployment gate

```bash
make test-pre-deploy
```

Runs:

```text
coverage
contract
component
local resilience
local performance
Docker integration
```

The unit suite runs once through the coverage target.

### Production-image build gate

```bash
make test-build-gate
```

Runs deterministic tests required before building the production image:

```text
coverage
contract
component
local resilience
```

## AWS Test Prerequisites

Before running AWS tests:

1. Deploy Platform infrastructure.
2. Deploy Ingestion infrastructure and image.
3. Confirm AWS credentials point to the expected account.
4. Confirm `ENVIRONMENT=dev`.
5. Confirm the main queue and DLQ are empty.
6. Confirm no registry item is `PROCESSING`.
7. Prefer starting with ECS scaled to zero.

A clean baseline is:

```text
ECS:        ACTIVE, 0 desired, 0 running, 0 pending
Main queue: 0 visible, 0 in-flight
DLQ:        0 visible, 0 in-flight
Registry:   0 processing
```

Check it with:

```bash
make deployment-status \
  AWS_ACCOUNT_ID=721093132332 \
  IMAGE_TAG=dev
```

Monitor while tests run:

```bash
make monitor-aws-compact \
  AWS_ACCOUNT_ID=721093132332 \
  IMAGE_TAG=dev \
  AWS_MONITOR_INTERVAL=15
```

Follow logs in another terminal:

```bash
make logs-aws \
  AWS_ACCOUNT_ID=721093132332 \
  IMAGE_TAG=dev \
  AWS_LOG_SINCE=30m
```

## AWS Smoke Tests

```bash
make test-smoke \
  AWS_ACCOUNT_ID=721093132332 \
  IMAGE_TAG=dev
```

The suite verifies:

- deployed resources are accessible;
- a small real canonical document completes ingestion;
- OpenSearch record count equals chunk count;
- DAVV completes without a Serverless refresh call;
- the queue and DLQ are clean after processing.

Expected test count:

```text
2 passed
```

## AWS End-to-End Tests

```bash
make test-e2e \
  AWS_ACCOUNT_ID=721093132332 \
  IMAGE_TAG=dev \
  RUN_DESTRUCTIVE_AWS_TESTS=1
```

The suite verifies:

- duplicate trigger idempotency;
- malformed pre-claim canonical input redrives to the DLQ;
- a full canonical fixture completes successfully.

Expected test count:

```text
3 passed
```

The permanent-failure test temporarily suspends dynamic scaling, stops the ECS worker, publishes a test-owned malformed fixture, advances that message through the real SQS redrive policy, verifies it reaches the DLQ, deletes only its own DLQ message, and restores the original scaling state.

## AWS Resilience Tests

```bash
make test-resilience-aws \
  AWS_ACCOUNT_ID=721093132332 \
  IMAGE_TAG=dev \
  RUN_DESTRUCTIVE_AWS_TESTS=1
```

The explicit destructive opt-in is mandatory.

The suite verifies:

- repeated triggers produce one registry generation;
- a test-owned DLQ message can be selectively received and deleted;
- ECS task termination recovers and processing completes;
- an SQS message can be released and redelivered.

Expected test count:

```text
4 passed
```

## AWS Performance Tests

```bash
make test-performance-aws \
  AWS_ACCOUNT_ID=721093132332 \
  IMAGE_TAG=dev
```

The suite verifies:

- queue work drains within the configured budget;
- visible work bootstraps at least one ECS worker;
- an idle service returns to zero workers.

Expected test count:

```text
3 passed
```

These tests verify operational behavior under the configured development workload. They are not a substitute for production load testing with representative document sizes and provider quotas.

## Complete Post-Deployment Verification

```bash
make test-post-deploy \
  AWS_ACCOUNT_ID=721093132332 \
  IMAGE_TAG=dev \
  RUN_DESTRUCTIVE_AWS_TESTS=1
```

Execution order:

```text
AWS smoke
  -> AWS end-to-end
  -> AWS resilience
  -> AWS performance
```

Expected deployed total:

```text
12 passed
```

A successful run ends with:

```text
Complete post-deployment verification passed
```

## Complete Release Verification

```bash
make test-release \
  AWS_ACCOUNT_ID=721093132332 \
  IMAGE_TAG=dev \
  RUN_DESTRUCTIVE_AWS_TESTS=1
```

This combines local pre-deployment verification and deployed AWS verification. Run it only against an isolated development environment.

## Important AWS Test Safety Rules

- Never run destructive tests against production.
- Do not run two destructive suites concurrently against the same stack.
- Do not manually change ECS desired count while a suite is running.
- Do not purge queues while tests are running.
- Start from empty main and dead-letter queues.
- Keep test-owned fixture cleanup in `finally` blocks.
- Correlate queue messages using unique test-owned document IDs.
- Do not rely on global queue emptiness in a shared environment.

For GitHub Actions, serialize deployed tests:

```yaml
concurrency:
  group: ingestion-dev-aws-tests
  cancel-in-progress: false
```

## DAVV Test Expectations

For OpenSearch Serverless, successful ingestion should show:

```text
bulk write succeeds
  -> explicit refresh is skipped
  -> count is polled by ingestion_id
  -> actual record count equals expected record count
  -> registry becomes COMPLETED
  -> message is acknowledged
```

These failures should not appear:

```text
NotFoundError from indices.refresh
Document ID is not supported in create/index operation request
DAVV visibility timeout during a healthy ingestion
```

Useful success log events include:

```text
ingestion_processing_claim_acquired
ingestion_processing_claim_completed
ingestion_completed
ingestion_message_acknowledged
```

## Understanding Queue Metrics

Amazon SQS queue counts are approximate. Two monitors can briefly report different visible and in-flight counts.

Use the combined evidence from:

- test result;
- DynamoDB registry status;
- structured worker logs;
- queue trend;
- ECS service events.

A brief transition such as `0 visible / 1 in-flight` is expected while a worker owns a message.

## Expected Alarm Behavior

The queue-depth-empty alarm is expected to be in `ALARM` while the service is at zero. It drives the final scale-in action.

During destructive tests, temporary changes to DLQ, ECS, or queue alarms may be intentional. Judge the scenario by the test result and cleanup state.

After the suite, wait for alarms and approximate queue metrics to settle.

## Troubleshooting

### Smoke succeeds, but DLQ assertion fails

A stale message existed before the test. Start future runs with an empty DLQ. Inspect and delete only known test-owned messages; do not blindly purge shared environments.

### Invalid canonical test waits for a registry `FAILED` record

That is the wrong contract for a pre-claim failure. Malformed pre-claim input creates no normal registry claim and should retry to the DLQ.

### ECS remains at one worker after tests

The service is usually waiting for the configured idle scale-in window. Expected sequence:

```text
queue drains
  -> one idle worker remains
  -> empty period completes
  -> desired count changes from 1 to 0
```

### Queue has one message but ECS is zero

Wait for the bootstrap alarm evaluation. Expected sequence:

```text
visible message
  -> bootstrap alarm ALARM
  -> desired count 1
  -> task starts
```

### Worker returns retryable provider failures

Check:

- provider HTTP status and retry classification;
- API token availability;
- network connectivity;
- provider quota or throttling;
- OpenSearch endpoint and access policy;
- DAVV timeout and observed counts.

### Terraform test initialization repeats

AWS test targets depend on `terraform-init` so deployment outputs are available. Reinitialization is intentional and safe.

## Adding Tests

When adding a new scenario:

1. Mark it with the correct pytest category.
2. Use deterministic test-owned document IDs.
3. Isolate external-provider boundaries in unit tests.
4. Put real AWS lifecycle checks under `tests/aws`.
5. Use bounded polling via shared helpers.
6. Always clean test-owned S3 objects, queue messages, DLQ messages, and registry records.
7. Preserve and restore ECS/autoscaling state in destructive tests.
8. Avoid fixed sleeps when a bounded state poll is available.
9. Avoid asserting exact timing for eventually consistent AWS metrics.
10. Keep destructive scenarios gated by `RUN_DESTRUCTIVE_AWS_TESTS=1`.

## Final Verification Record

The current development deployment has demonstrated:

```text
Unit statement and branch coverage: 100%
AWS smoke:                           2 passed
AWS end-to-end:                      3 passed
AWS resilience:                      4 passed
AWS performance:                     3 passed
Final ECS desired/running/pending:   0 / 0 / 0
Final main queue visible/in-flight:  0 / 0
Final DLQ visible/in-flight:         0 / 0
```
