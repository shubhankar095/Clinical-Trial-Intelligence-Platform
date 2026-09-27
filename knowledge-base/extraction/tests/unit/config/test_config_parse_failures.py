import importlib

import pytest

import config.config as config_module


pytestmark = pytest.mark.unit


def reload_config(
    monkeypatch,
    **environment,
):
    for key, value in environment.items():
        monkeypatch.setenv(
            key,
            value,
        )

    return importlib.reload(
        config_module
    )


def test_non_integer_word_threshold_fails_configuration_load(
    monkeypatch,
):
    with pytest.raises(
        ValueError,
    ):
        reload_config(
            monkeypatch,
            MIN_WORDS_PER_PAGE="abc",
        )


def test_non_numeric_quality_threshold_fails_configuration_load(
    monkeypatch,
):
    with pytest.raises(
        ValueError,
    ):
        reload_config(
            monkeypatch,
            MIN_QUALITY_SCORE="abc",
        )