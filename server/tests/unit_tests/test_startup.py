"""Pure unit tests for core.startup — secret validation logic.

Covers:
  _check_jwt_secret  — pure function, no external dependencies, no mocks needed.
  validate_secrets   — environment-aware dispatcher; sys.exit and logging are
                       mocked so tests never abort the process or pollute output.

Design notes:
  - Config is stubbed with SimpleNamespace — no real ServerConfig instantiated,
    no pydantic validation, no .env file reads.
  - sys.exit is patched at its call site (core.startup.sys.exit) so the test
    process never terminates.
  - The logger is patched at core.startup.log to assert the correct log level
    is chosen per environment without capturing the real log stream.
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import call, patch

import pytest
from pydantic import SecretStr

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from core.startup import (
    _DEFAULT_JWT_SECRET,
    _JWT_SECRET_MIN_LEN,
    _REDIS_URL_ENV_VAR,
    _check_jwt_secret,
    _check_llm_config,
    _check_multi_worker,
    validate_secrets,
)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _cfg(
    secret: str,
    environment: str,
    *,
    workers: int = 1,
    redis_url: str = "",
    llm_provider: str = "ollama",
    llm_api_key: str = "",
) -> SimpleNamespace:
    """Minimal config stub accepted by validate_secrets."""
    return SimpleNamespace(
        auth=SimpleNamespace(jwt_secret=secret),
        network=SimpleNamespace(workers=workers),
        redis=SimpleNamespace(url=redis_url),
        llm=SimpleNamespace(provider=llm_provider, api_key=SecretStr(llm_api_key)),
        environment=environment,
    )


# A secret that satisfies both checks: not the default, meets min-length.
_VALID_SECRET = "x" * _JWT_SECRET_MIN_LEN


# =============================================================================
# _check_jwt_secret  — pure function, no mocks
# =============================================================================


@pytest.mark.unit
class TestCheckJwtSecret:
    """_check_jwt_secret must return violations only for insecure inputs and
    return an empty list when the secret is acceptable."""

    # --- known-default branch ---

    def test_known_default_returns_one_violation(self):
        assert len(_check_jwt_secret(_DEFAULT_JWT_SECRET)) == 1

    def test_known_default_violation_names_the_bad_value(self):
        (msg,) = _check_jwt_secret(_DEFAULT_JWT_SECRET)
        assert _DEFAULT_JWT_SECRET in msg

    def test_short_secret_violation_does_not_name_the_default_value(self):
        """A too-short-but-not-default secret must produce a length message,
        not the known-default message.  Verifies the two branches are distinct
        so operators receive targeted, actionable error text."""
        short_custom = "a" * (_JWT_SECRET_MIN_LEN - 1)
        (msg,) = _check_jwt_secret(short_custom)
        assert _DEFAULT_JWT_SECRET not in msg

    # --- too-short branch ---

    def test_one_char_below_floor_returns_one_violation(self):
        short = "a" * (_JWT_SECRET_MIN_LEN - 1)
        assert len(_check_jwt_secret(short)) == 1

    def test_short_violation_mentions_minimum_length(self):
        (msg,) = _check_jwt_secret("a" * (_JWT_SECRET_MIN_LEN - 1))
        assert str(_JWT_SECRET_MIN_LEN) in msg

    def test_empty_string_returns_violation(self):
        assert len(_check_jwt_secret("")) == 1

    # --- valid branch ---

    def test_secret_at_exactly_min_length_passes(self):
        assert _check_jwt_secret("a" * _JWT_SECRET_MIN_LEN) == []

    def test_secret_well_above_min_length_passes(self):
        assert _check_jwt_secret("a" * (_JWT_SECRET_MIN_LEN * 2)) == []

    # --- return-type contract ---

    def test_violations_are_strings(self):
        violations = _check_jwt_secret(_DEFAULT_JWT_SECRET)
        assert all(isinstance(v, str) for v in violations)

    def test_returns_list(self):
        assert isinstance(_check_jwt_secret(_VALID_SECRET), list)


# =============================================================================
# validate_secrets — development: warn and continue
# =============================================================================


@pytest.mark.unit
class TestValidateSecretsDevelopment:
    """In 'development' violations must surface as warnings; the process must
    never be terminated regardless of how bad the secret is."""

    def test_default_secret_logs_warning(self):
        with patch("core.startup.log") as mock_log:
            validate_secrets(_cfg(_DEFAULT_JWT_SECRET, "development"))
        assert mock_log.warning.called

    def test_default_secret_does_not_exit(self):
        with patch("core.startup.log"), patch("sys.exit") as mock_exit:
            validate_secrets(_cfg(_DEFAULT_JWT_SECRET, "development"))
        mock_exit.assert_not_called()

    def test_short_secret_logs_warning(self):
        with patch("core.startup.log") as mock_log:
            validate_secrets(_cfg("short", "development"))
        assert mock_log.warning.called

    def test_short_secret_does_not_exit(self):
        with patch("core.startup.log"), patch("sys.exit") as mock_exit:
            validate_secrets(_cfg("short", "development"))
        mock_exit.assert_not_called()

    def test_valid_secret_emits_no_warning(self):
        with patch("core.startup.log") as mock_log:
            validate_secrets(_cfg(_VALID_SECRET, "development"))
        mock_log.warning.assert_not_called()

    def test_valid_secret_does_not_exit(self):
        with patch("sys.exit") as mock_exit:
            validate_secrets(_cfg(_VALID_SECRET, "development"))
        mock_exit.assert_not_called()

    def test_violations_never_escalate_to_critical_in_development(self):
        with patch("core.startup.log") as mock_log:
            validate_secrets(_cfg(_DEFAULT_JWT_SECRET, "development"))
        mock_log.critical.assert_not_called()

    def test_valid_secret_emits_no_log_at_any_level(self):
        with patch("core.startup.log") as mock_log:
            validate_secrets(_cfg(_VALID_SECRET, "development"))
        mock_log.warning.assert_not_called()
        mock_log.critical.assert_not_called()
        mock_log.error.assert_not_called()

    def test_multi_worker_no_redis_logs_warning(self):
        """Multi-worker violation must surface through validate_secrets in development."""
        with patch("core.startup.log") as mock_log:
            validate_secrets(_cfg(_VALID_SECRET, "development", workers=2))
        assert mock_log.warning.called
        mock_log.critical.assert_not_called()

    def test_multi_worker_no_redis_does_not_exit(self):
        with patch("core.startup.log"), patch("sys.exit") as mock_exit:
            validate_secrets(_cfg(_VALID_SECRET, "development", workers=2))
        mock_exit.assert_not_called()

    def test_multi_worker_with_redis_is_clean(self):
        with patch("core.startup.log") as mock_log, patch("sys.exit") as mock_exit:
            validate_secrets(
                _cfg(_VALID_SECRET, "development", workers=4, redis_url="redis://localhost:6379")
            )
        mock_log.warning.assert_not_called()
        mock_exit.assert_not_called()


# =============================================================================
# validate_secrets — production / staging: fatal
# =============================================================================


@pytest.mark.unit
class TestValidateSecretsProduction:
    """In 'production' and 'staging' any violation must terminate the process
    with exit code 1.  A valid secret must never trigger an exit."""

    @pytest.mark.parametrize("env", ["production", "staging"])
    def test_default_secret_exits_1(self, env):
        with patch("core.startup.log"), patch("sys.exit") as mock_exit:
            validate_secrets(_cfg(_DEFAULT_JWT_SECRET, env))
        mock_exit.assert_called_once_with(1)

    @pytest.mark.parametrize("env", ["production", "staging"])
    def test_short_secret_exits_1(self, env):
        with patch("core.startup.log"), patch("sys.exit") as mock_exit:
            validate_secrets(_cfg("short", env))
        mock_exit.assert_called_once_with(1)

    @pytest.mark.parametrize("env", ["production", "staging"])
    def test_valid_secret_does_not_exit(self, env):
        with patch("sys.exit") as mock_exit:
            validate_secrets(_cfg(_VALID_SECRET, env))
        mock_exit.assert_not_called()

    @pytest.mark.parametrize("env", ["production", "staging"])
    def test_violations_logged_at_critical_not_warning(self, env):
        with patch("core.startup.log") as mock_log, patch("sys.exit"):
            validate_secrets(_cfg(_DEFAULT_JWT_SECRET, env))
        assert mock_log.critical.called
        mock_log.warning.assert_not_called()

    @pytest.mark.parametrize("env", ["production", "staging"])
    def test_valid_secret_emits_no_log_at_any_level(self, env):
        with patch("core.startup.log") as mock_log:
            validate_secrets(_cfg(_VALID_SECRET, env))
        mock_log.warning.assert_not_called()
        mock_log.critical.assert_not_called()
        mock_log.error.assert_not_called()

    def test_exit_called_exactly_once_not_multiple_times(self):
        """Guard against a regression where each violation triggers its own exit."""
        with patch("core.startup.log"), patch("sys.exit") as mock_exit:
            validate_secrets(_cfg(_DEFAULT_JWT_SECRET, "production"))
        assert mock_exit.call_count == 1

    def test_exit_code_is_1_not_0_or_other(self):
        with patch("core.startup.log"), patch("sys.exit") as mock_exit:
            validate_secrets(_cfg(_DEFAULT_JWT_SECRET, "production"))
        mock_exit.assert_called_with(1)
        assert mock_exit.call_args != call(0)

    @pytest.mark.parametrize("env", ["production", "staging"])
    def test_multi_worker_no_redis_exits_1(self, env):
        """Multi-worker violation must surface through validate_secrets in production/staging."""
        with patch("core.startup.log"), patch("sys.exit") as mock_exit:
            validate_secrets(_cfg(_VALID_SECRET, env, workers=2))
        mock_exit.assert_called_once_with(1)

    @pytest.mark.parametrize("env", ["production", "staging"])
    def test_multi_worker_with_redis_does_not_exit(self, env):
        with patch("sys.exit") as mock_exit:
            validate_secrets(
                _cfg(_VALID_SECRET, env, workers=4, redis_url="redis://localhost:6379")
            )
        mock_exit.assert_not_called()

    def test_two_violations_exit_called_exactly_once(self):
        """JWT violation + multi-worker violation must still exit exactly once, not twice."""
        with patch("core.startup.log"), patch("sys.exit") as mock_exit:
            validate_secrets(_cfg(_DEFAULT_JWT_SECRET, "production", workers=2))
        assert mock_exit.call_count == 1


# =============================================================================
# _check_multi_worker — pure function, no mocks
# =============================================================================

def _mw_cfg(workers: int, redis_url: str = "") -> SimpleNamespace:
    """Minimal stub for _check_multi_worker."""
    return SimpleNamespace(
        network=SimpleNamespace(workers=workers),
        redis=SimpleNamespace(url=redis_url),
    )


@pytest.mark.unit
class TestCheckMultiWorker:
    """_check_multi_worker must return a violation only when workers > 1
    and no Redis URL is configured."""

    # --- safe configurations (no violation) ---

    def test_single_worker_no_redis_returns_no_violations(self):
        assert _check_multi_worker(_mw_cfg(workers=1)) == []

    def test_single_worker_with_redis_returns_no_violations(self):
        assert _check_multi_worker(_mw_cfg(workers=1, redis_url="redis://localhost:6379")) == []

    def test_multi_worker_with_redis_returns_no_violations(self):
        assert _check_multi_worker(_mw_cfg(workers=4, redis_url="redis://localhost:6379")) == []

    def test_two_workers_with_redis_returns_no_violations(self):
        assert _check_multi_worker(_mw_cfg(workers=2, redis_url="redis://localhost:6379")) == []

    # --- violation cases ---

    def test_two_workers_without_redis_returns_one_violation(self):
        assert len(_check_multi_worker(_mw_cfg(workers=2))) == 1

    def test_many_workers_without_redis_returns_one_violation(self):
        assert len(_check_multi_worker(_mw_cfg(workers=8))) == 1

    def test_violation_names_the_worker_count(self):
        (msg,) = _check_multi_worker(_mw_cfg(workers=4))
        assert "4" in msg


# =============================================================================
# _check_llm_config — pure function, no mocks
# =============================================================================


def _llm_cfg(provider: str, api_key: str = "") -> SimpleNamespace:
    """Minimal stub for _check_llm_config."""
    return SimpleNamespace(llm=SimpleNamespace(provider=provider, api_key=SecretStr(api_key)))


@pytest.mark.unit
class TestCheckLlmConfig:
    """_check_llm_config must require an api_key for cloud providers and
    pass local providers regardless of api_key."""

    # --- no violation ---

    def test_ollama_without_api_key_passes(self):
        assert _check_llm_config(_llm_cfg("ollama")) == []

    def test_ollama_with_api_key_passes(self):
        assert _check_llm_config(_llm_cfg("ollama", api_key="ignored")) == []

    def test_nvidia_with_api_key_passes(self):
        assert _check_llm_config(_llm_cfg("nvidia", api_key="nvapi-abc123")) == []

    # --- violation ---

    def test_nvidia_without_api_key_returns_one_violation(self):
        assert len(_check_llm_config(_llm_cfg("nvidia"))) == 1

    def test_nvidia_with_spaces_only_key_returns_one_violation(self):
        assert len(_check_llm_config(_llm_cfg("nvidia", api_key="   "))) == 1

    def test_nvidia_with_tab_only_key_returns_one_violation(self):
        assert len(_check_llm_config(_llm_cfg("nvidia", api_key="\t"))) == 1

    def test_nvidia_with_newline_only_key_returns_one_violation(self):
        assert len(_check_llm_config(_llm_cfg("nvidia", api_key="\n"))) == 1

    def test_violation_mentions_provider_name(self):
        (msg,) = _check_llm_config(_llm_cfg("nvidia"))
        assert "nvidia" in msg

    def test_violation_mentions_env_var(self):
        (msg,) = _check_llm_config(_llm_cfg("nvidia"))
        assert "HOPMAP_SERVER__LLM__API_KEY" in msg

    def test_violations_are_strings(self):
        violations = _check_llm_config(_llm_cfg("nvidia"))
        assert all(isinstance(v, str) for v in violations)

    def test_returns_list(self):
        assert isinstance(_check_llm_config(_llm_cfg("nvidia")), list)

    def test_violation_names_the_redis_env_var(self):
        (msg,) = _check_multi_worker(_mw_cfg(workers=2))
        assert _REDIS_URL_ENV_VAR in msg

    def test_violation_mentions_single_worker_alternative(self):
        (msg,) = _check_multi_worker(_mw_cfg(workers=2))
        assert "workers=1" in msg
