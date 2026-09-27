############################################
# Extraction service commands
#
# Tests:
#   make test-unit
#   make test-component
#   make test-integration
#   make test-performance
#   make test-all
#
# Local image:
#   make build
#   make run
#
# Terraform:
#   make terraform-check
#   make terraform-plan
#   make terraform-apply
#
# Development deployment:
#   make deploy-dev \
#       AWS_ACCOUNT_ID=123456789012
#
# Deployed AWS smoke test:
#   make test-aws \
#       AWS_ACCOUNT_ID=123456789012
#
# Development destruction:
#   make destroy-plan \
#       AWS_ACCOUNT_ID=123456789012
#
#   make destroy-dev \
#       AWS_ACCOUNT_ID=123456789012
#
# Intentional dependency upgrade:
#   make upgrade
#   make build
############################################


############################################
# Application configuration
############################################

IMAGE_NAME ?= extraction
IMAGE_TAG ?= dev
IMAGE := $(IMAGE_NAME):$(IMAGE_TAG)

ENVIRONMENT ?= dev
REGION ?= ap-south-1

PYTHONPATH_VALUE := src:../../packages/aws_utils:../../packages/utils

UV_SYNC_FLAGS := --locked --link-mode=copy
UV_RUN := uv run --locked --no-sync


############################################
# AWS configuration
############################################

AWS_PROFILE ?=
AWS_ACCOUNT_ID ?= 721093132332
AWS_MONITOR_INTERVAL ?= 30

AWS_PROFILE_FLAG := $(if $(AWS_PROFILE),--profile $(AWS_PROFILE),)
AWS_PROFILE_MAKE_ARG := $(if $(AWS_PROFILE),AWS_PROFILE="$(AWS_PROFILE)",)
AWS_ENV := $(if $(AWS_PROFILE),AWS_PROFILE=$(AWS_PROFILE),)

############################################
# Terraform configuration
############################################

INFRA_DIR := infra

TF_BACKEND_CONFIG := config/backend_config.tfvars
TF_VARS_FILE := config/variables.tfvars

TF_PLAN_FILE := tfplan
TF_DESTROY_PLAN_FILE := tfplan-destroy

TF_STATE_BUCKET ?= tfstate-backend-config-dev

TF_LOCK_TIMEOUT ?= 5m

############################################
# AWS post-deployment test configuration
############################################
AWS_TEST_TIMEOUT ?= 1200
PROCESSING_SCHEMA_VERSION ?= extraction-v1

############################################
# Targets
############################################

.PHONY: \
	sync \
	sync-dev \
	upgrade \
	export-reqs \
	test-unit \
	test-component \
	test-integration \
	test-performance \
	test-all \
	docker-build \
	validate-image \
	build \
	run \
	check-tools \
	check-aws \
	check-aws-account \
	check-dev \
	check-state-bucket \
	terraform-init \
	terraform-fmt \
	terraform-validate \
	terraform-check \
	terraform-plan \
	terraform-apply \
	ecr-login \
	ecr-push \
	ecs-deploy \
	deployment-outputs \
	deployment-status \
	monitor-aws \
	monitor-aws-compact \
	logs-aws \
	deploy-dev \
	test-aws \
	destroy-plan \
	destroy-dev \
	clean


############################################
# Prevent deployment stages from running
# concurrently when make is called with -j.
############################################

.NOTPARALLEL: \
	deploy-dev \
	destroy-plan \
	destroy-dev


############################################
# Dependency management
############################################

sync:
	uv lock --check
	uv sync $(UV_SYNC_FLAGS) --no-dev
	@echo "✅ Locked production dependencies synchronized"


sync-dev:
	uv lock --check
	uv sync $(UV_SYNC_FLAGS) --extra dev
	@echo "✅ Locked development dependencies synchronized"


upgrade:
	uv lock --upgrade
	uv sync \
		--locked \
		--extra dev \
		--link-mode=copy
	@echo "✅ Dependencies upgraded and synchronized"


############################################
# Unit tests
############################################

test-unit: sync-dev
	PYTHONPATH="$(PYTHONPATH_VALUE)" \
	$(UV_RUN) python -m pytest \
		tests/unit \
		-v
	@echo "✅ Unit tests passed"


############################################
# Component tests
############################################

test-component: sync-dev
	PYTHONPATH="$(PYTHONPATH_VALUE)" \
	$(UV_RUN) python -m pytest \
		tests/component \
		-v
	@echo "✅ Component tests passed"


############################################
# Integration tests
############################################

test-integration: sync-dev
	PYTHONPATH="$(PYTHONPATH_VALUE)" \
	$(UV_RUN) python -m pytest \
		tests/integration \
		-v
	@echo "✅ Local integration tests passed"


############################################
# Performance tests
############################################

test-performance: sync-dev
	PYTHONPATH="$(PYTHONPATH_VALUE)" \
	$(UV_RUN) python -m pytest \
		tests/performance \
		-m performance \
		-v \
		-s
	@echo "✅ Local performance tests passed"


############################################
# All automated local tests
############################################

test-all: sync-dev
	PYTHONPATH="$(PYTHONPATH_VALUE)" \
	$(UV_RUN) python -m pytest \
		tests/unit \
		tests/component \
		tests/integration \
		tests/performance \
		--cov=src \
		--cov-branch \
		--cov-report=term-missing \
		-v
	@echo "✅ All automated local tests passed with required coverage"


############################################
# Production dependency export
############################################

export-reqs: sync
	uv export \
		--locked \
		--format requirements.txt \
		--no-dev \
		--no-emit-project \
		--no-emit-local \
		--output-file requirements.txt
	@echo "✅ Production requirements exported"


############################################
# Docker build
############################################

docker-build: test-all export-reqs
	docker build \
		--provenance=false \
		--platform linux/amd64 \
		-f Dockerfile \
		-t "$(IMAGE)" \
		../../

	@echo "✅ Docker image built: $(IMAGE)"


############################################
# Docker image validation
############################################

validate-image: docker-build
	docker run \
		--rm \
		--env AWS_DEFAULT_REGION="$(REGION)" \
		--entrypoint python \
		"$(IMAGE)" \
		-c "from workers.extraction_worker import ExtractionWorker; \
			from processors.pdf_processor import PDFProcessor; \
			from aws_utils.s3 import S3Service; \
			from utils.logger import get_logger; \
			print('✅ Image imports successful')"

	docker run \
		--rm \
		--entrypoint id \
		"$(IMAGE)" \
		| grep -q "uid=10001(appuser)"

	docker image inspect \
		"$(IMAGE)" \
		--format '{{.Architecture}} {{.Os}}' \
		| grep -q '^amd64 linux$$'

	@echo "✅ Docker image validation passed"


############################################
# Complete local production build
############################################

build: validate-image
	@echo "✅ Production image built and validated: $(IMAGE)"


############################################
# Run Docker image locally
############################################

run:
	docker run \
		--rm \
		--env AWS_DEFAULT_REGION="$(REGION)" \
		"$(IMAGE)"


############################################
# Deployment preflight
############################################

check-tools:
	@command -v aws >/dev/null 2>&1 \
		|| { echo "❌ AWS CLI is required"; exit 1; }

	@command -v docker >/dev/null 2>&1 \
		|| { echo "❌ Docker is required"; exit 1; }

	@command -v terraform >/dev/null 2>&1 \
		|| { echo "❌ Terraform is required"; exit 1; }

	@command -v uv >/dev/null 2>&1 \
		|| { echo "❌ uv is required"; exit 1; }

	@docker info >/dev/null 2>&1 \
		|| { echo "❌ Docker daemon is not available"; exit 1; }

	@echo "✅ Required deployment tools are available"


check-aws: check-tools
	@echo "AWS deployment identity:"

	@aws sts get-caller-identity \
		$(AWS_PROFILE_FLAG) \
		--region "$(REGION)" \
		--query '{Account:Account,Arn:Arn}' \
		--output table

	@echo "✅ AWS credentials are available"


check-aws-account: check-aws
	@if [ -z "$(AWS_ACCOUNT_ID)" ]; then \
		echo "❌ AWS_ACCOUNT_ID is required"; \
		echo "Run:"; \
		echo "make deploy-dev AWS_ACCOUNT_ID=123456789012"; \
		exit 1; \
	fi

	@ACTUAL_ACCOUNT_ID="$$( \
		aws sts get-caller-identity \
			$(AWS_PROFILE_FLAG) \
			--region "$(REGION)" \
			--query Account \
			--output text \
	)"; \
	if [ "$${ACTUAL_ACCOUNT_ID}" != "$(AWS_ACCOUNT_ID)" ]; then \
		echo "❌ AWS account mismatch"; \
		echo "Expected: $(AWS_ACCOUNT_ID)"; \
		echo "Actual:   $${ACTUAL_ACCOUNT_ID}"; \
		exit 1; \
	fi

	@echo "✅ AWS account verified: $(AWS_ACCOUNT_ID)"


check-dev: check-aws-account
	@if [ "$(ENVIRONMENT)" != "dev" ]; then \
		echo "❌ This target is restricted to ENVIRONMENT=dev"; \
		echo "Actual environment: $(ENVIRONMENT)"; \
		exit 1; \
	fi

	@if [ -z "$(IMAGE_TAG)" ]; then \
		echo "❌ IMAGE_TAG must not be empty"; \
		exit 1; \
	fi

	@if [ "$(IMAGE_TAG)" = "latest" ]; then \
		echo "❌ IMAGE_TAG cannot be latest"; \
		exit 1; \
	fi

	@echo "✅ Development deployment guard passed"


check-state-bucket: check-dev
	@aws s3api head-bucket \
		$(AWS_PROFILE_FLAG) \
		--bucket "$(TF_STATE_BUCKET)" \
		>/dev/null

	@echo "✅ Terraform state bucket exists: $(TF_STATE_BUCKET)"


############################################
# Terraform initialization
############################################

terraform-init: check-state-bucket
	$(AWS_ENV) terraform \
		-chdir="$(INFRA_DIR)" \
		init \
		-reconfigure \
		-backend-config="$(TF_BACKEND_CONFIG)"

	@echo "✅ Terraform initialized"


############################################
# Terraform formatting
############################################

terraform-fmt:
	terraform \
		-chdir="$(INFRA_DIR)" \
		fmt \
		-check \
		-recursive

	@echo "✅ Terraform formatting check passed"


############################################
# Terraform validation
############################################

terraform-validate: terraform-init
	$(AWS_ENV) terraform \
		-chdir="$(INFRA_DIR)" \
		validate

	@echo "✅ Terraform configuration validated"


############################################
# Complete Terraform checks
############################################

terraform-check: terraform-fmt terraform-validate
	@echo "✅ All Terraform checks passed"


############################################
# Terraform plan
############################################

terraform-plan: terraform-check
	$(AWS_ENV) terraform \
		-chdir="$(INFRA_DIR)" \
		plan \
		-lock-timeout="$(TF_LOCK_TIMEOUT)" \
		-var-file="$(TF_VARS_FILE)" \
		-var="image_tag=$(IMAGE_TAG)" \
		-out="$(TF_PLAN_FILE)"

	$(AWS_ENV) terraform \
		-chdir="$(INFRA_DIR)" \
		show \
		-no-color \
		"$(TF_PLAN_FILE)"

	@echo "✅ Terraform plan created: $(INFRA_DIR)/$(TF_PLAN_FILE)"


############################################
# Terraform apply
############################################

terraform-apply: build terraform-plan
	$(AWS_ENV) terraform \
		-chdir="$(INFRA_DIR)" \
		apply \
		-lock-timeout="$(TF_LOCK_TIMEOUT)" \
		"$(TF_PLAN_FILE)"

	rm -f \
		"$(INFRA_DIR)/$(TF_PLAN_FILE)"

	@echo "✅ Terraform infrastructure applied"


############################################
# ECR authentication
############################################

ecr-login: terraform-apply
	@ECR_URL="$$( \
		$(AWS_ENV) terraform \
			-chdir="$(INFRA_DIR)" \
			output \
			-raw \
			ecr_repository_url \
	)"; \
	ECR_REGISTRY="$${ECR_URL%%/*}"; \
	echo "Authenticating Docker to $${ECR_REGISTRY}"; \
	aws ecr get-login-password \
		$(AWS_PROFILE_FLAG) \
		--region "$(REGION)" \
		| docker login \
			--username AWS \
			--password-stdin \
			"$${ECR_REGISTRY}"

	@echo "✅ Docker authenticated to ECR"


############################################
# Publish image to ECR
############################################

ecr-push: ecr-login
	@ECR_URL="$$( \
		$(AWS_ENV) terraform \
			-chdir="$(INFRA_DIR)" \
			output \
			-raw \
			ecr_repository_url \
	)"; \
	REMOTE_IMAGE="$${ECR_URL}:$(IMAGE_TAG)"; \
	echo "Publishing image: $${REMOTE_IMAGE}"; \
	docker tag \
		"$(IMAGE)" \
		"$${REMOTE_IMAGE}"; \
	docker push \
		"$${REMOTE_IMAGE}"; \
	echo "✅ Image pushed: $${REMOTE_IMAGE}"


############################################
# Force ECS service deployment
############################################

ecs-deploy: ecr-push
	@CLUSTER="$$( \
		$(AWS_ENV) terraform \
			-chdir="$(INFRA_DIR)" \
			output \
			-raw \
			ecs_cluster \
	)"; \
	SERVICE="$$( \
		$(AWS_ENV) terraform \
			-chdir="$(INFRA_DIR)" \
			output \
			-raw \
			ecs_service_name \
	)"; \
	echo "Deploying ECS service: $${SERVICE}"; \
	aws ecs update-service \
		$(AWS_PROFILE_FLAG) \
		--region "$(REGION)" \
		--cluster "$${CLUSTER}" \
		--service "$${SERVICE}" \
		--force-new-deployment \
		--query \
			'service.{status:status,desired:desiredCount,running:runningCount,pending:pendingCount}' \
		--output table; \
	echo "Waiting for ECS service stability..."; \
	aws ecs wait services-stable \
		$(AWS_PROFILE_FLAG) \
		--region "$(REGION)" \
		--cluster "$${CLUSTER}" \
		--services "$${SERVICE}"

	@echo "✅ ECS deployment completed"


############################################
# Terraform deployment outputs
############################################

deployment-outputs: check-dev terraform-init
	@echo ""
	@echo "============================================"
	@echo "Deployment outputs"
	@echo "============================================"

	@$(AWS_ENV) terraform \
		-chdir="$(INFRA_DIR)" \
		output

	@echo "============================================"


############################################
# Runtime deployment status
############################################

deployment-status: check-dev terraform-init
	@CLUSTER="$$( \
		$(AWS_ENV) terraform \
			-chdir="$(INFRA_DIR)" \
			output \
			-raw \
			ecs_cluster \
	)"; \
	SERVICE="$$( \
		$(AWS_ENV) terraform \
			-chdir="$(INFRA_DIR)" \
			output \
			-raw \
			ecs_service_name \
	)"; \
	QUEUE_URL="$$( \
		$(AWS_ENV) terraform \
			-chdir="$(INFRA_DIR)" \
			output \
			-raw \
			extraction_queue_url \
	)"; \
	DLQ_ARN="$$( \
		$(AWS_ENV) terraform \
			-chdir="$(INFRA_DIR)" \
			output \
			-raw \
			extraction_dlq_arn \
	)"; \
	DLQ_NAME="$${DLQ_ARN##*:}"; \
	DLQ_URL="$$( \
		aws sqs get-queue-url \
			$(AWS_PROFILE_FLAG) \
			--region "$(REGION)" \
			--queue-name "$${DLQ_NAME}" \
			--query QueueUrl \
			--output text \
	)"; \
	echo ""; \
	echo "ECS service status:"; \
	aws ecs describe-services \
		$(AWS_PROFILE_FLAG) \
		--region "$(REGION)" \
		--cluster "$${CLUSTER}" \
		--services "$${SERVICE}" \
		--query \
			'services[0].{status:status,desired:desiredCount,running:runningCount,pending:pendingCount,taskDefinition:taskDefinition}' \
		--output table; \
	echo ""; \
	echo "Latest ECS service events:"; \
	aws ecs describe-services \
		$(AWS_PROFILE_FLAG) \
		--region "$(REGION)" \
		--cluster "$${CLUSTER}" \
		--services "$${SERVICE}" \
		--query \
			'services[0].events[0:5].[createdAt,message]' \
		--output table; \
	echo ""; \
	echo "Extraction queue status:"; \
	aws sqs get-queue-attributes \
		$(AWS_PROFILE_FLAG) \
		--region "$(REGION)" \
		--queue-url "$${QUEUE_URL}" \
		--attribute-names \
			ApproximateNumberOfMessages \
			ApproximateNumberOfMessagesNotVisible \
		--query Attributes \
		--output table; \
	echo ""; \
	echo "Dead-letter queue status:"; \
	aws sqs get-queue-attributes \
		$(AWS_PROFILE_FLAG) \
		--region "$(REGION)" \
		--queue-url "$${DLQ_URL}" \
		--attribute-names \
			ApproximateNumberOfMessages \
			ApproximateNumberOfMessagesNotVisible \
		--query Attributes \
		--output table

	@echo "✅ Deployment status retrieved"


############################################
# Complete development deployment
############################################

deploy-dev: ecs-deploy
	@echo ""
	@echo "============================================"
	@echo "Development deployment completed"
	@echo "============================================"
	@echo "Environment: $(ENVIRONMENT)"
	@echo "Region:      $(REGION)"
	@echo "Image:       $(IMAGE)"
	@echo "AWS account: $(AWS_ACCOUNT_ID)"
	@echo "============================================"

	@$(MAKE) deployment-outputs \
		ENVIRONMENT="$(ENVIRONMENT)" \
		REGION="$(REGION)" \
		IMAGE_TAG="$(IMAGE_TAG)" \
		AWS_ACCOUNT_ID="$(AWS_ACCOUNT_ID)" \
		$(AWS_PROFILE_MAKE_ARG)

	@$(MAKE) deployment-status \
		ENVIRONMENT="$(ENVIRONMENT)" \
		REGION="$(REGION)" \
		IMAGE_TAG="$(IMAGE_TAG)" \
		AWS_ACCOUNT_ID="$(AWS_ACCOUNT_ID)" \
		$(AWS_PROFILE_MAKE_ARG)

############################################
# Deployed AWS smoke test
############################################

test-aws: check-dev terraform-init sync-dev
	@RAW_BUCKET="$$( \
		$(AWS_ENV) terraform \
			-chdir="$(INFRA_DIR)" \
			output \
			-raw \
			raw_bucket \
	)"; \
	CANONICAL_BUCKET="$$( \
		$(AWS_ENV) terraform \
			-chdir="$(INFRA_DIR)" \
			output \
			-raw \
			canonical_bucket \
	)"; \
	QUEUE_URL="$$( \
		$(AWS_ENV) terraform \
			-chdir="$(INFRA_DIR)" \
			output \
			-raw \
			extraction_queue_url \
	)"; \
	DLQ_ARN="$$( \
		$(AWS_ENV) terraform \
			-chdir="$(INFRA_DIR)" \
			output \
			-raw \
			extraction_dlq_arn \
	)"; \
	PROCESSING_REGISTRY_TABLE="$$( \
		$(AWS_ENV) terraform \
			-chdir="$(INFRA_DIR)" \
			output \
			-raw \
			processing_registry_table \
	)"; \
	ECS_CLUSTER="$$( \
		$(AWS_ENV) terraform \
			-chdir="$(INFRA_DIR)" \
			output \
			-raw \
			ecs_cluster \
	)"; \
	ECS_SERVICE="$$( \
		$(AWS_ENV) terraform \
			-chdir="$(INFRA_DIR)" \
			output \
			-raw \
			ecs_service_name \
	)"; \
	CLOUDWATCH_LOG_GROUP="$$( \
		$(AWS_ENV) terraform \
			-chdir="$(INFRA_DIR)" \
			output \
			-raw \
			cloudwatch_log_group \
	)"; \
	ECR_REPOSITORY_URL="$$( \
		$(AWS_ENV) terraform \
			-chdir="$(INFRA_DIR)" \
			output \
			-raw \
			ecr_repository_url \
	)"; \
	echo ""; \
	echo "============================================"; \
	echo "AWS post-deployment test configuration"; \
	echo "============================================"; \
	echo "Region:                    $(REGION)"; \
	echo "Raw bucket:                $${RAW_BUCKET}"; \
	echo "Canonical bucket:          $${CANONICAL_BUCKET}"; \
	echo "Extraction queue:          $${QUEUE_URL}"; \
	echo "Processing registry table: $${PROCESSING_REGISTRY_TABLE}"; \
	echo "ECS cluster:               $${ECS_CLUSTER}"; \
	echo "ECS service:               $${ECS_SERVICE}"; \
	echo "Processing schema:         $(PROCESSING_SCHEMA_VERSION)"; \
	echo "Image tag:                 $(IMAGE_TAG)"; \
	echo "============================================"; \
	echo ""; \
	AWS_DEFAULT_REGION="$(REGION)" \
	RAW_BUCKET="$${RAW_BUCKET}" \
	CANONICAL_BUCKET="$${CANONICAL_BUCKET}" \
	EXTRACTION_QUEUE_URL="$${QUEUE_URL}" \
	EXTRACTION_DLQ_ARN="$${DLQ_ARN}" \
	PROCESSING_REGISTRY_TABLE="$${PROCESSING_REGISTRY_TABLE}" \
	PROCESSING_SCHEMA_VERSION="$(PROCESSING_SCHEMA_VERSION)" \
	ECS_CLUSTER="$${ECS_CLUSTER}" \
	ECS_SERVICE="$${ECS_SERVICE}" \
	CLOUDWATCH_LOG_GROUP="$${CLOUDWATCH_LOG_GROUP}" \
	ECR_REPOSITORY_URL="$${ECR_REPOSITORY_URL}" \
	IMAGE_TAG="$(IMAGE_TAG)" \
	AWS_TEST_TIMEOUT="$(AWS_TEST_TIMEOUT)" \
	PYTHONPATH="$(PYTHONPATH_VALUE)" \
	$(UV_RUN) python -m pytest \
		tests/aws \
		-m aws \
		-v \
		-s

	@echo "✅ AWS post-deployment tests passed"


############################################
# Terraform destroy plan
############################################

destroy-plan: terraform-init
	@if [ "$(ENVIRONMENT)" != "dev" ]; then \
		echo "❌ destroy-plan requires ENVIRONMENT=dev"; \
		exit 1; \
	fi

	$(AWS_ENV) terraform \
		-chdir="$(INFRA_DIR)" \
		plan \
		-destroy \
		-lock-timeout="$(TF_LOCK_TIMEOUT)" \
		-var-file="$(TF_VARS_FILE)" \
		-var="image_tag=$(IMAGE_TAG)" \
		-out="$(TF_DESTROY_PLAN_FILE)"

	$(AWS_ENV) terraform \
		-chdir="$(INFRA_DIR)" \
		show \
		-no-color \
		"$(TF_DESTROY_PLAN_FILE)"

	@echo ""
	@echo "⚠️  Review the destroy plan carefully."
	@echo "Run 'make destroy-dev' only after reviewing it."
	@echo "✅ Destroy plan created: $(INFRA_DIR)/$(TF_DESTROY_PLAN_FILE)"


############################################
# Apply reviewed destroy plan
############################################

destroy-dev: check-dev
	@if [ ! -f "$(INFRA_DIR)/$(TF_DESTROY_PLAN_FILE)" ]; then \
		echo "❌ Reviewed destroy plan not found"; \
		echo "Run 'make destroy-plan' first"; \
		exit 1; \
	fi

	@echo "⚠️  Destroying development infrastructure"
	@echo "AWS account: $(AWS_ACCOUNT_ID)"
	@echo "Region:      $(REGION)"
	@echo "Environment: $(ENVIRONMENT)"

	$(AWS_ENV) terraform \
		-chdir="$(INFRA_DIR)" \
		apply \
		-lock-timeout="$(TF_LOCK_TIMEOUT)" \
		"$(TF_DESTROY_PLAN_FILE)"

	rm -f \
		"$(INFRA_DIR)/$(TF_DESTROY_PLAN_FILE)"

	@echo "✅ Development infrastructure destroyed"


############################################
# Cleanup
############################################

clean:
	rm -rf .venv
	rm -rf .pytest_cache
	rm -rf htmlcov
	rm -rf src/extraction.egg-info

	find src tests scripts \
		-type d \
		-name "__pycache__" \
		-prune \
		-exec rm -rf {} +

	find src tests scripts \
		-type f \
		\( \
			-name "*.pyc" \
			-o -name "*.pyo" \
		\) \
		-delete

	rm -f .coverage
	rm -f coverage.xml
	rm -f requirements.txt
	rm -f test-results.txt

	rm -f "$(INFRA_DIR)/$(TF_PLAN_FILE)"
	rm -f "$(INFRA_DIR)/$(TF_DESTROY_PLAN_FILE)"

	@echo "✅ Cleaned generated files"


############################################
# Detailed AWS runtime dashboard
############################################

monitor-aws: check-dev terraform-init
	@CLUSTER="$$( \
		$(AWS_ENV) terraform \
			-chdir="$(INFRA_DIR)" \
			output \
			-raw \
			ecs_cluster \
	)"; \
	SERVICE="$$( \
		$(AWS_ENV) terraform \
			-chdir="$(INFRA_DIR)" \
			output \
			-raw \
			ecs_service_name \
	)"; \
	QUEUE_URL="$$( \
		$(AWS_ENV) terraform \
			-chdir="$(INFRA_DIR)" \
			output \
			-raw \
			extraction_queue_url \
	)"; \
	DLQ_ARN="$$( \
		$(AWS_ENV) terraform \
			-chdir="$(INFRA_DIR)" \
			output \
			-raw \
			extraction_dlq_arn \
	)"; \
	REGISTRY_TABLE="$$( \
		$(AWS_ENV) terraform \
			-chdir="$(INFRA_DIR)" \
			output \
			-raw \
			processing_registry_table \
	)"; \
	CANONICAL_BUCKET="$$( \
		$(AWS_ENV) terraform \
			-chdir="$(INFRA_DIR)" \
			output \
			-raw \
			canonical_bucket \
	)"; \
	DLQ_NAME="$${DLQ_ARN##*:}"; \
	DLQ_URL="$$( \
		aws sqs get-queue-url \
			$(AWS_PROFILE_FLAG) \
			--region "$(REGION)" \
			--queue-name "$${DLQ_NAME}" \
			--query QueueUrl \
			--output text \
	)"; \
	echo "Starting unified AWS monitor."; \
	echo "Refresh interval: $(AWS_MONITOR_INTERVAL) seconds"; \
	echo "Press Ctrl+C to stop."; \
	sleep 2; \
	while true; do \
		clear; \
		echo "============================================================"; \
		echo " Clinical KB Extraction AWS Monitor"; \
		echo "============================================================"; \
		echo "Region:      $(REGION)"; \
		echo "Environment: $(ENVIRONMENT)"; \
		echo "Time:        $$(date -u '+%Y-%m-%d %H:%M:%S UTC')"; \
		echo "Refresh:     $(AWS_MONITOR_INTERVAL) seconds"; \
		echo "============================================================"; \
		echo ""; \
		echo "=== ECS Service ==="; \
		aws ecs describe-services \
			$(AWS_PROFILE_FLAG) \
			--region "$(REGION)" \
			--cluster "$${CLUSTER}" \
			--services "$${SERVICE}" \
			--query \
				'services[0].{status:status,desired:desiredCount,running:runningCount,pending:pendingCount,taskDefinition:taskDefinition}' \
			--output table \
			|| true; \
		echo ""; \
		echo "=== Main Queue ==="; \
		aws sqs get-queue-attributes \
			$(AWS_PROFILE_FLAG) \
			--region "$(REGION)" \
			--queue-url "$${QUEUE_URL}" \
			--attribute-names \
				ApproximateNumberOfMessages \
				ApproximateNumberOfMessagesNotVisible \
			--query Attributes \
			--output table \
			|| true; \
		echo ""; \
		echo "=== Dead-Letter Queue ==="; \
		aws sqs get-queue-attributes \
			$(AWS_PROFILE_FLAG) \
			--region "$(REGION)" \
			--queue-url "$${DLQ_URL}" \
			--attribute-names \
				ApproximateNumberOfMessages \
				ApproximateNumberOfMessagesNotVisible \
			--query Attributes \
			--output table \
			|| true; \
		echo ""; \
		echo "=== CloudWatch Alarms ==="; \
        echo "Note: queue-depth-empty=ALARM is healthy when ECS is at zero."; \
        aws cloudwatch describe-alarms \
            $(AWS_PROFILE_FLAG) \
            --region "$(REGION)" \
            --alarm-name-prefix "clinical-kb-" \
            --query \
                'MetricAlarms[].{alarm:AlarmName,state:StateValue,updated:StateUpdatedTimestamp}' \
            --output table \
            || true; \
		echo ""; \
		echo "=== Recent Autoscaling Activities ==="; \
		aws application-autoscaling \
			describe-scaling-activities \
			$(AWS_PROFILE_FLAG) \
			--region "$(REGION)" \
			--service-namespace ecs \
			--resource-id \
				"service/$${CLUSTER}/$${SERVICE}" \
			--scalable-dimension \
				ecs:service:DesiredCount \
			--max-results 5 \
			--query \
				'ScalingActivities[].{time:StartTime,status:StatusCode}' \
			--output table \
			|| true; \
		echo ""; \
		echo "=== Processing Registry Counts ==="; \
		aws dynamodb scan \
			$(AWS_PROFILE_FLAG) \
			--region "$(REGION)" \
			--table-name "$${REGISTRY_TABLE}" \
			--projection-expression "#processing_status" \
			--expression-attribute-names \
				'{"#processing_status":"status"}' \
			--query \
				'{total:length(Items),processing:length(Items[?status.S==`PROCESSING`]),completed:length(Items[?status.S==`COMPLETED`])}' \
			--output table \
			|| true; \
		echo ""; \
		echo "=== Recent Processing Registry Records ==="; \
        REGISTRY_RECORDS="$$( \
            aws dynamodb scan \
                $(AWS_PROFILE_FLAG) \
                --region "$(REGION)" \
                --table-name "$${REGISTRY_TABLE}" \
                --projection-expression \
                    'document_id,#processing_status,source_version_id,lease_expires_at,completed_at' \
                --expression-attribute-names \
                    '{"#processing_status":"status"}' \
                --query \
                    'Items[].{document:document_id.S,status:status.S,version:source_version_id.S,lease:lease_expires_at.N,completed:completed_at.N}' \
                --output table \
            2>&1 \
        )"; \
        if [ -n "$${REGISTRY_RECORDS}" ]; then \
            printf '%s\n' "$${REGISTRY_RECORDS}"; \
        else \
            echo "No processing registry records."; \
        fi; \
		echo ""; \
		echo "=== Canonical Object Summary ==="; \
        CANONICAL_OBJECT_COUNT="$$( \
            aws s3api list-objects-v2 \
                $(AWS_PROFILE_FLAG) \
                --region "$(REGION)" \
                --bucket "$${CANONICAL_BUCKET}" \
                --prefix "canonical-documents/" \
                --query 'length(Contents || `[]`)' \
                --output text \
            2>/dev/null \
            || echo "unavailable" \
        )"; \
        echo "Canonical objects: $${CANONICAL_OBJECT_COUNT}"; \
		echo ""; \
		echo "=== Latest ECS Service Events ==="; \
		aws ecs describe-services \
			$(AWS_PROFILE_FLAG) \
			--region "$(REGION)" \
			--cluster "$${CLUSTER}" \
			--services "$${SERVICE}" \
			--query \
				'services[0].events[0:5].[createdAt,message]' \
			--output table \
			|| true; \
		echo ""; \
		echo "Press Ctrl+C to stop."; \
		sleep "$(AWS_MONITOR_INTERVAL)"; \
	done


############################################
# Follow deployed application logs
############################################

AWS_LOG_SINCE ?= 15m

logs-aws: check-dev terraform-init
	@LOG_GROUP="$$( \
		$(AWS_ENV) terraform \
			-chdir="$(INFRA_DIR)" \
			output \
			-raw \
			cloudwatch_log_group \
	)"; \
	echo "Following CloudWatch logs: $${LOG_GROUP}"; \
	echo "Showing logs since: $(AWS_LOG_SINCE)"; \
	echo "Press Ctrl+C to stop."; \
	aws logs tail \
		"$${LOG_GROUP}" \
		$(AWS_PROFILE_FLAG) \
		--region "$(REGION)" \
		--since "$(AWS_LOG_SINCE)" \
		--follow \
		--format short


############################################
# Compact AWS runtime dashboard
############################################

monitor-aws-compact: check-dev terraform-init
	@CLUSTER="$$( \
		$(AWS_ENV) terraform \
			-chdir="$(INFRA_DIR)" \
			output \
			-raw \
			ecs_cluster \
	)"; \
	SERVICE="$$( \
		$(AWS_ENV) terraform \
			-chdir="$(INFRA_DIR)" \
			output \
			-raw \
			ecs_service_name \
	)"; \
	QUEUE_URL="$$( \
		$(AWS_ENV) terraform \
			-chdir="$(INFRA_DIR)" \
			output \
			-raw \
			extraction_queue_url \
	)"; \
	DLQ_ARN="$$( \
		$(AWS_ENV) terraform \
			-chdir="$(INFRA_DIR)" \
			output \
			-raw \
			extraction_dlq_arn \
	)"; \
	REGISTRY_TABLE="$$( \
		$(AWS_ENV) terraform \
			-chdir="$(INFRA_DIR)" \
			output \
			-raw \
			processing_registry_table \
	)"; \
	CANONICAL_BUCKET="$$( \
		$(AWS_ENV) terraform \
			-chdir="$(INFRA_DIR)" \
			output \
			-raw \
			canonical_bucket \
	)"; \
	DLQ_NAME="$${DLQ_ARN##*:}"; \
	DLQ_URL="$$( \
		aws sqs get-queue-url \
			$(AWS_PROFILE_FLAG) \
			--region "$(REGION)" \
			--queue-name "$${DLQ_NAME}" \
			--query QueueUrl \
			--output text \
	)"; \
	echo "Starting AWS monitor."; \
	echo "Refresh interval: $(AWS_MONITOR_INTERVAL) seconds"; \
	echo "Press Ctrl+C to stop."; \
	sleep 2; \
	while true; do \
		ECS_VALUES="$$( \
			aws ecs describe-services \
				$(AWS_PROFILE_FLAG) \
				--region "$(REGION)" \
				--cluster "$${CLUSTER}" \
				--services "$${SERVICE}" \
				--query \
					'services[0].[status,desiredCount,runningCount,pendingCount]' \
				--output text \
			2>/dev/null \
			|| echo "UNKNOWN 0 0 0" \
		)"; \
		set -- $${ECS_VALUES}; \
		ECS_STATUS="$${1:-UNKNOWN}"; \
		ECS_DESIRED="$${2:-0}"; \
		ECS_RUNNING="$${3:-0}"; \
		ECS_PENDING="$${4:-0}"; \
		QUEUE_VALUES="$$( \
			aws sqs get-queue-attributes \
				$(AWS_PROFILE_FLAG) \
				--region "$(REGION)" \
				--queue-url "$${QUEUE_URL}" \
				--attribute-names \
					ApproximateNumberOfMessages \
					ApproximateNumberOfMessagesNotVisible \
				--query \
					'Attributes.[ApproximateNumberOfMessages,ApproximateNumberOfMessagesNotVisible]' \
				--output text \
			2>/dev/null \
			|| echo "0 0" \
		)"; \
		set -- $${QUEUE_VALUES}; \
		QUEUE_VISIBLE="$${1:-0}"; \
		QUEUE_IN_FLIGHT="$${2:-0}"; \
		DLQ_VALUES="$$( \
			aws sqs get-queue-attributes \
				$(AWS_PROFILE_FLAG) \
				--region "$(REGION)" \
				--queue-url "$${DLQ_URL}" \
				--attribute-names \
					ApproximateNumberOfMessages \
					ApproximateNumberOfMessagesNotVisible \
				--query \
					'Attributes.[ApproximateNumberOfMessages,ApproximateNumberOfMessagesNotVisible]' \
				--output text \
			2>/dev/null \
			|| echo "0 0" \
		)"; \
		set -- $${DLQ_VALUES}; \
		DLQ_VISIBLE="$${1:-0}"; \
		DLQ_IN_FLIGHT="$${2:-0}"; \
		REGISTRY_VALUES="$$( \
			aws dynamodb scan \
				$(AWS_PROFILE_FLAG) \
				--region "$(REGION)" \
				--table-name "$${REGISTRY_TABLE}" \
				--projection-expression "#processing_status" \
				--expression-attribute-names \
					'{"#processing_status":"status"}' \
				--query \
					'[length(Items[?status.S==`PROCESSING`]),length(Items[?status.S==`COMPLETED`])]' \
				--output text \
			2>/dev/null \
			|| echo "0 0" \
		)"; \
		set -- $${REGISTRY_VALUES}; \
		REGISTRY_PROCESSING="$${1:-0}"; \
		REGISTRY_COMPLETED="$${2:-0}"; \
		CANONICAL_OBJECTS="$$( \
			aws s3api list-objects-v2 \
				$(AWS_PROFILE_FLAG) \
				--region "$(REGION)" \
				--bucket "$${CANONICAL_BUCKET}" \
				--prefix "canonical-documents/" \
				--query 'length(Contents || `[]`)' \
				--output text \
			2>/dev/null \
			|| echo "unavailable" \
		)"; \
		FAILURE_ALARM="$$( \
			aws cloudwatch describe-alarms \
				$(AWS_PROFILE_FLAG) \
				--region "$(REGION)" \
				--alarm-names \
					"clinical-kb-extraction-processing-failures-$(ENVIRONMENT)" \
				--query 'MetricAlarms[0].StateValue' \
				--output text \
			2>/dev/null \
			|| echo "UNKNOWN" \
		)"; \
		OLDEST_ALARM="$$( \
			aws cloudwatch describe-alarms \
				$(AWS_PROFILE_FLAG) \
				--region "$(REGION)" \
				--alarm-names \
					"clinical-kb-extraction-oldest-message-$(ENVIRONMENT)" \
				--query 'MetricAlarms[0].StateValue' \
				--output text \
			2>/dev/null \
			|| echo "UNKNOWN" \
		)"; \
		DLQ_ALARM="$$( \
			aws cloudwatch describe-alarms \
				$(AWS_PROFILE_FLAG) \
				--region "$(REGION)" \
				--alarm-names \
					"clinical-kb-extraction-dlq-messages-$(ENVIRONMENT)" \
				--query 'MetricAlarms[0].StateValue' \
				--output text \
			2>/dev/null \
			|| echo "UNKNOWN" \
		)"; \
		LAST_SCALE="$$( \
			aws application-autoscaling \
				describe-scaling-activities \
				$(AWS_PROFILE_FLAG) \
				--region "$(REGION)" \
				--service-namespace ecs \
				--resource-id \
					"service/$${CLUSTER}/$${SERVICE}" \
				--scalable-dimension \
					ecs:service:DesiredCount \
				--max-results 1 \
				--query \
					'ScalingActivities[0].[StatusCode,StartTime]' \
				--output text \
			2>/dev/null \
			|| echo "Unavailable None" \
		)"; \
		set -- $${LAST_SCALE}; \
		LAST_SCALE_STATUS="$${1:-Unavailable}"; \
		LAST_SCALE_TIMESTAMP="$${2:-None}"; \
		if [ "$${LAST_SCALE_TIMESTAMP}" = "None" ]; then \
			LAST_SCALE_TIME="unavailable"; \
		else \
			LAST_SCALE_TIME="$$( \
				printf '%s' "$${LAST_SCALE_TIMESTAMP}" \
					| cut -dT -f2 \
					| cut -d. -f1 \
			) UTC"; \
		fi; \
		if [ "$${ECS_STATUS}" != "ACTIVE" ]; then \
			SYSTEM_STATE="ATTENTION REQUIRED"; \
		elif [ "$${DLQ_VISIBLE}" -gt 0 ] 2>/dev/null; then \
			SYSTEM_STATE="ATTENTION REQUIRED"; \
		elif [ "$${FAILURE_ALARM}" = "ALARM" ]; then \
			SYSTEM_STATE="ATTENTION REQUIRED"; \
		elif [ "$${OLDEST_ALARM}" = "ALARM" ]; then \
			SYSTEM_STATE="ATTENTION REQUIRED"; \
		elif [ "$${DLQ_ALARM}" = "ALARM" ]; then \
			SYSTEM_STATE="ATTENTION REQUIRED"; \
		elif [ "$${REGISTRY_PROCESSING}" -gt 0 ] 2>/dev/null; then \
			SYSTEM_STATE="PROCESSING DOCUMENT"; \
		elif [ "$${QUEUE_IN_FLIGHT}" -gt 0 ] 2>/dev/null; then \
			SYSTEM_STATE="PROCESSING DOCUMENT"; \
		elif [ "$${ECS_PENDING}" -gt 0 ] 2>/dev/null; then \
			SYSTEM_STATE="STARTING WORKER"; \
		elif [ "$${QUEUE_VISIBLE}" -gt 0 ] 2>/dev/null \
			&& [ "$${ECS_DESIRED}" -eq 0 ] 2>/dev/null; then \
			SYSTEM_STATE="WAITING FOR SCALE-OUT"; \
		elif [ "$${ECS_RUNNING}" -gt 0 ] 2>/dev/null \
			&& [ "$${QUEUE_VISIBLE}" -eq 0 ] 2>/dev/null \
			&& [ "$${QUEUE_IN_FLIGHT}" -eq 0 ] 2>/dev/null; then \
			SYSTEM_STATE="WAITING FOR SCALE-IN"; \
		elif [ "$${ECS_DESIRED}" -eq 0 ] 2>/dev/null \
			&& [ "$${ECS_RUNNING}" -eq 0 ] 2>/dev/null; then \
			SYSTEM_STATE="IDLE, SCALED TO ZERO"; \
		else \
			SYSTEM_STATE="HEALTHY"; \
		fi; \
		clear; \
		echo "Clinical KB Extraction"; \
		printf "%s | %s | %s | refresh %ss\n" \
			"$(ENVIRONMENT)" \
			"$(REGION)" \
			"$$(date -u '+%H:%M:%S UTC')" \
			"$(AWS_MONITOR_INTERVAL)"; \
		echo "------------------------------------------------------------"; \
		echo "WORKLOAD"; \
		printf "  %-12s %-10s %s desired   %s running   %s pending\n" \
			"ECS" \
			"$${ECS_STATUS}" \
			"$${ECS_DESIRED}" \
			"$${ECS_RUNNING}" \
			"$${ECS_PENDING}"; \
		printf "  %-23s %s visible   %s in-flight\n" \
			"Main queue" \
			"$${QUEUE_VISIBLE}" \
			"$${QUEUE_IN_FLIGHT}"; \
		printf "  %-23s %s visible   %s in-flight\n" \
			"DLQ" \
			"$${DLQ_VISIBLE}" \
			"$${DLQ_IN_FLIGHT}"; \
		echo "------------------------------------------------------------"; \
		echo "DATA"; \
		printf "  %-23s %s processing   %s completed\n" \
			"Registry" \
			"$${REGISTRY_PROCESSING}" \
			"$${REGISTRY_COMPLETED}"; \
		printf "  %-23s %s objects\n" \
			"Canonical" \
			"$${CANONICAL_OBJECTS}"; \
		echo "------------------------------------------------------------"; \
		echo "HEALTH"; \
		printf "  %-25s %s\n" \
			"Processing failures" \
			"$${FAILURE_ALARM}"; \
		printf "  %-25s %s\n" \
			"Oldest message" \
			"$${OLDEST_ALARM}"; \
		printf "  %-25s %s\n" \
			"DLQ alarm" \
			"$${DLQ_ALARM}"; \
		printf "  %-25s %s at %s\n" \
			"Last scaling" \
			"$${LAST_SCALE_STATUS}" \
			"$${LAST_SCALE_TIME}"; \
		echo "------------------------------------------------------------"; \
		echo "STATUS"; \
		printf "  %s\n" "$${SYSTEM_STATE}"; \
		echo "------------------------------------------------------------"; \
		if [ "$${SYSTEM_STATE}" = "ATTENTION REQUIRED" ]; then \
			echo "Run: make logs-aws AWS_LOG_SINCE=30m"; \
		fi; \
		echo "Ctrl+C to stop"; \
		sleep "$(AWS_MONITOR_INTERVAL)"; \
	done