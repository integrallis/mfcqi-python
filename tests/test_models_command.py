"""Tests for the models CLI command (list / pull / benchmark / test)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
import requests
from click.testing import CliRunner

from mfcqi.cli.commands.models import (
    _measure_completion_latency,
    _stream_pull_status,
    models,
)


def test_models_list_command() -> None:
    """`models list` returns 0 even when Ollama is unreachable."""
    runner = CliRunner()
    result = runner.invoke(models, ["list"])
    assert result.exit_code == 0
    assert "models" in result.output.lower() or "ollama" in result.output.lower()


def test_models_list_with_endpoint() -> None:
    """Custom --endpoint must not change the exit code."""
    runner = CliRunner()
    result = runner.invoke(models, ["list", "--endpoint", "http://localhost:11434"])
    assert result.exit_code == 0


def test_stream_pull_status_prints_each_unique_status(capsys) -> None:
    """Status transitions are emitted once each."""
    lines = [
        json.dumps({"status": "pulling manifest"}),
        json.dumps({"status": "downloading", "completed": 1024 * 1024, "total": 1024 * 1024 * 4}),
        json.dumps(
            {"status": "downloading", "completed": 1024 * 1024 * 2, "total": 1024 * 1024 * 4}
        ),
        json.dumps({"status": "verifying sha256 digest"}),
        json.dumps({"status": "success"}),
    ]

    exit_code = _stream_pull_status(iter(lines))
    out = capsys.readouterr().out

    assert exit_code == 0
    assert "pulling manifest" in out
    assert "downloading" in out
    assert "verifying sha256 digest" in out
    assert "success" in out
    # Per-line progress shows up when status repeats with completed/total fields.
    assert "MB" in out and "%" in out


def test_stream_pull_status_returns_two_on_error(capsys) -> None:
    """Error payloads exit 2 with the message on stderr."""
    lines = [json.dumps({"error": "manifest not found"})]
    exit_code = _stream_pull_status(iter(lines))
    captured = capsys.readouterr()
    assert exit_code == 2
    assert "manifest not found" in captured.err


def test_stream_pull_status_returns_two_on_garbage_line(capsys) -> None:
    """A non-JSON line in the stream is reported and exits 2."""
    exit_code = _stream_pull_status(iter(["not-json"]))
    captured = capsys.readouterr()
    assert exit_code == 2
    assert "Failed to parse pull response line" in captured.err


def test_models_pull_command_exits_two_when_ollama_unreachable() -> None:
    """End-to-end: a failing requests.post yields exit 2 and an informative message."""
    runner = CliRunner()
    with patch(
        "mfcqi.cli.commands.models.requests.post",
        side_effect=requests.ConnectionError("connection refused"),
    ):
        result = runner.invoke(models, ["pull", "codellama:7b"])
    assert result.exit_code == 2
    assert "Failed to reach Ollama" in result.output or "Failed to reach Ollama" in (
        result.stderr_bytes or b""
    ).decode("utf-8", "ignore")


def test_models_pull_command_streams_status_to_stdout() -> None:
    """End-to-end: a stubbed streaming response prints status transitions."""
    response = MagicMock()
    response.ok = True
    response.iter_lines.return_value = iter(
        [
            json.dumps({"status": "pulling manifest"}),
            json.dumps({"status": "success"}),
        ]
    )

    runner = CliRunner()
    with patch("mfcqi.cli.commands.models.requests.post", return_value=response) as post:
        result = runner.invoke(models, ["pull", "codellama:7b"])

    assert result.exit_code == 0
    assert "pulling manifest" in result.output
    assert "success" in result.output
    # Verify the right URL/payload were sent.
    args, kwargs = post.call_args
    assert args[0].endswith("/api/pull")
    assert kwargs["json"] == {"name": "codellama:7b", "stream": True}
    assert kwargs["stream"] is True


def test_models_pull_command_reports_non_2xx() -> None:
    """A non-2xx status code surfaces the HTTP code and exits 2."""
    response = MagicMock()
    response.ok = False
    response.status_code = 500
    runner = CliRunner()
    with patch("mfcqi.cli.commands.models.requests.post", return_value=response):
        result = runner.invoke(models, ["pull", "codellama:7b"])
    assert result.exit_code == 2
    assert "HTTP 500" in result.output


def _stub_litellm_response(content: str = "ok") -> MagicMock:
    """Build a MagicMock that quacks like a litellm.completion ModelResponse."""
    response = MagicMock()
    response.choices = [MagicMock()]
    response.choices[0].message = MagicMock()
    response.choices[0].message.content = content
    return response


def test_measure_completion_latency_routes_through_litellm() -> None:
    """Latency comes from time.monotonic deltas around a litellm.completion call."""
    times = iter([100.0, 100.42])  # +0.42s wall-clock
    with (
        patch(
            "mfcqi.cli.commands.models.litellm.completion",
            return_value=_stub_litellm_response(),
        ) as completion,
        patch("mfcqi.cli.commands.models.time.monotonic", side_effect=lambda: next(times)),
    ):
        latency = _measure_completion_latency("http://localhost:11434", "codellama:7b", "hi")

    assert latency == pytest.approx(0.42, abs=1e-6)
    kwargs = completion.call_args.kwargs
    # LiteLLM Ollama routing: "ollama/<name>" with api_base set to the endpoint.
    assert kwargs["model"] == "ollama/codellama:7b"
    assert kwargs["api_base"] == "http://localhost:11434"
    assert kwargs["stream"] is False
    assert kwargs["messages"] == [{"role": "user", "content": "hi"}]


def test_measure_completion_latency_normalizes_existing_prefix() -> None:
    """A model already namespaced as ``ollama:`` is rewritten to ``ollama/``."""
    times = iter([0.0, 0.1])
    with (
        patch(
            "mfcqi.cli.commands.models.litellm.completion",
            return_value=_stub_litellm_response(),
        ) as completion,
        patch("mfcqi.cli.commands.models.time.monotonic", side_effect=lambda: next(times)),
    ):
        _measure_completion_latency("http://x", "ollama:llama3:8b", "hi")
    assert completion.call_args.kwargs["model"] == "ollama/llama3:8b"


def test_models_benchmark_command_runs_completions_for_named_model() -> None:
    """End-to-end: benchmark issues completions through LiteLLM and prints latencies."""
    handler = MagicMock()
    handler.check_ollama_connection.return_value = {"available": True, "models": ["codellama:7b"]}

    # 1 cold + 3 warm = 4 measurement pairs of monotonic() calls.
    times = iter(
        [
            0.0,
            0.5,  # cold
            1.0,
            1.2,  # warm 1
            2.0,
            2.1,  # warm 2
            3.0,
            3.05,  # warm 3
        ]
    )

    runner = CliRunner()
    with (
        patch("mfcqi.cli.commands.models.LLMHandler", return_value=handler),
        patch(
            "mfcqi.cli.commands.models.litellm.completion",
            return_value=_stub_litellm_response(),
        ) as completion,
        patch("mfcqi.cli.commands.models.time.monotonic", side_effect=lambda: next(times)),
    ):
        result = runner.invoke(models, ["benchmark", "codellama:7b"])

    assert result.exit_code == 0
    assert "Cold start" in result.output
    assert "0.50s" in result.output  # cold latency
    assert "Warm" in result.output
    # Confirm we actually went through LiteLLM and not direct HTTP.
    assert completion.call_count == 4
    assert all(call.kwargs["model"] == "ollama/codellama:7b" for call in completion.call_args_list)


def test_models_benchmark_command_exits_two_when_ollama_unavailable() -> None:
    """When the connection check reports unavailable, exit 2."""
    handler = MagicMock()
    handler.check_ollama_connection.return_value = {"available": False, "models": []}
    runner = CliRunner()
    with patch("mfcqi.cli.commands.models.LLMHandler", return_value=handler):
        result = runner.invoke(models, ["benchmark"])
    assert result.exit_code == 2
    assert "Ollama not available" in result.output


def test_models_test_command() -> None:
    """`models test` smoke test — output should not be empty even when Ollama is down."""
    runner = CliRunner()
    result = runner.invoke(models, ["test", "codellama:7b"])
    assert result.exit_code in (0, 1)
    assert len(result.output) > 0
