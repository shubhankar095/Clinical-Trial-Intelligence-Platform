from pathlib import Path
import re

import pytest


pytestmark = [
    pytest.mark.contract,
    pytest.mark.local,
]


INGESTION_ROOT = Path(__file__).resolve().parents[2]
INFRA_DIR = INGESTION_ROOT / "infra"

VARIABLES_FILE = INFRA_DIR / "variables.tf"
TFVARS_FILE = INFRA_DIR / "config" / "variables.tfvars"
RUNTIME_FILE = INFRA_DIR / "runtime.tf"
TASK_TEMPLATE_FILE = (
    INFRA_DIR
    / "templates"
    / "ecs-task-definition.json.tpl"
)

TIMEOUT_VARIABLE = (
    "opensearch_visibility_timeout_seconds"
)
POLL_VARIABLE = (
    "opensearch_visibility_poll_seconds"
)

TIMEOUT_ENVIRONMENT = (
    "OPENSEARCH_VISIBILITY_TIMEOUT_SECONDS"
)
POLL_ENVIRONMENT = (
    "OPENSEARCH_VISIBILITY_POLL_SECONDS"
)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def variable_block(
    content: str,
    variable_name: str,
) -> str:
    marker = f'variable "{variable_name}" {{'
    start = content.find(marker)

    if start < 0:
        raise AssertionError(
            f"Missing Terraform variable {variable_name!r}."
        )

    depth = 0
    block_started = False

    for index in range(start, len(content)):
        character = content[index]

        if character == "{":
            depth += 1
            block_started = True
        elif character == "}":
            depth -= 1

            if block_started and depth == 0:
                return content[start : index + 1]

    raise AssertionError(
        f"Terraform variable {variable_name!r} "
        "has an unbalanced block."
    )


def assignment_value(
    content: str,
    variable_name: str,
) -> str:
    pattern = re.compile(
        rf"(?m)^\s*{re.escape(variable_name)}"
        rf"\s*=\s*([^\s#]+)"
    )
    match = pattern.search(content)

    if match is None:
        raise AssertionError(
            f"Missing assignment for {variable_name!r}."
        )

    return match.group(1)


def template_environment_value(
    content: str,
    environment_name: str,
) -> str:
    pattern = re.compile(
        r"\{\s*"
        rf'"name"\s*:\s*"{re.escape(environment_name)}"'
        r"\s*,\s*"
        r'"value"\s*:\s*"([^"]+)"'
        r"\s*\}",
        re.DOTALL,
    )
    match = pattern.search(content)

    if match is None:
        raise AssertionError(
            "Missing ECS environment entry for "
            f"{environment_name!r}."
        )

    return match.group(1)


def test_davv_terraform_variables_define_safe_defaults():
    content = read(VARIABLES_FILE)

    timeout = variable_block(
        content,
        TIMEOUT_VARIABLE,
    )
    poll = variable_block(
        content,
        POLL_VARIABLE,
    )

    assert re.search(
        r"(?m)^\s*type\s*=\s*number\s*$",
        timeout,
    )
    assert re.search(
        r"(?m)^\s*default\s*=\s*60\s*$",
        timeout,
    )
    assert (
        "var.opensearch_visibility_"
        "timeout_seconds > 0"
        in timeout
    )
    assert (
        "var.opensearch_visibility_"
        "timeout_seconds <= 600"
        in timeout
    )

    assert re.search(
        r"(?m)^\s*type\s*=\s*number\s*$",
        poll,
    )
    assert re.search(
        r"(?m)^\s*default\s*=\s*1\s*$",
        poll,
    )
    assert (
        "var.opensearch_visibility_"
        "poll_seconds > 0"
        in poll
    )
    assert (
        "var.opensearch_visibility_"
        "poll_seconds"
        in poll
    )
    assert (
        "var.opensearch_visibility_"
        "timeout_seconds"
        in poll
    )


def test_dev_tfvars_select_davv_operating_values():
    content = read(TFVARS_FILE)

    timeout = assignment_value(
        content,
        TIMEOUT_VARIABLE,
    )
    poll = assignment_value(
        content,
        POLL_VARIABLE,
    )

    assert timeout == "60"
    assert poll == "1"

    assert float(timeout) > 0
    assert float(poll) > 0
    assert float(poll) <= float(timeout)


def test_runtime_passes_davv_values_to_task_template():
    content = read(RUNTIME_FILE)

    assert re.search(
        rf"(?s)\b{TIMEOUT_VARIABLE}\s*=\s*"
        rf"tostring\s*\(\s*"
        rf"var\.{TIMEOUT_VARIABLE}\s*\)",
        content,
    )

    assert re.search(
        rf"(?s)\b{POLL_VARIABLE}\s*=\s*"
        rf"tostring\s*\(\s*"
        rf"var\.{POLL_VARIABLE}\s*\)",
        content,
    )


def test_task_template_exposes_davv_environment():
    content = read(TASK_TEMPLATE_FILE)

    timeout_value = template_environment_value(
        content,
        TIMEOUT_ENVIRONMENT,
    )
    poll_value = template_environment_value(
        content,
        POLL_ENVIRONMENT,
    )

    assert timeout_value == (
        "${opensearch_visibility_timeout_seconds}"
    )
    assert poll_value == (
        "${opensearch_visibility_poll_seconds}"
    )


def test_each_davv_environment_variable_occurs_once():
    content = read(TASK_TEMPLATE_FILE)

    assert content.count(TIMEOUT_ENVIRONMENT) == 1
    assert content.count(POLL_ENVIRONMENT) == 1

    assert (
        content.count(
            "${opensearch_visibility_timeout_seconds}"
        )
        == 1
    )
    assert (
        content.count(
            "${opensearch_visibility_poll_seconds}"
        )
        == 1
    )