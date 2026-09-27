import pytest

from app.services.observability import (
    ObservabilityCollector,
    run_observed_call,
)


def test_successful_llm_call_is_recorded():

    collector = ObservabilityCollector(
        pipeline_version="test-v1"
    )

    result = run_observed_call(
        collector,

        stage="requirement_extraction",

        prompt_version="req-v1",

        model="test-model",

        is_fallback=False,

        call=lambda: "success",
    )

    observability = collector.build(
        total_latency_ms=100.0
    )

    assert result == "success"

    assert (
        observability.llm_call_count
        == 1
    )

    assert (
        observability.fallback_used
        is False
    )

    assert observability.models_used == [
        "test-model"
    ]

    assert (
        observability.calls[0].status
        == "success"
    )


def test_failed_call_is_recorded():

    collector = ObservabilityCollector(
        pipeline_version="test-v1"
    )

    def failing_call():
        raise RuntimeError(
            "Test failure"
        )

    with pytest.raises(RuntimeError):

        run_observed_call(
            collector,

            stage="evidence_matching",

            prompt_version="match-v1",

            model="primary-model",

            is_fallback=False,

            call=failing_call,
        )

    observability = collector.build(
        total_latency_ms=50.0
    )

    assert (
        observability.llm_call_count
        == 1
    )

    assert (
        observability.calls[0].status
        == "error"
    )

    assert (
        observability.calls[0].error_type
        == "RuntimeError"
    )


def test_fallback_usage_is_recorded():

    collector = ObservabilityCollector(
        pipeline_version="test-v1"
    )

    def failing_primary():
        raise RuntimeError(
            "Primary failed"
        )

    try:
        run_observed_call(
            collector,

            stage="requirement_extraction",

            prompt_version="req-v1",

            model="primary-model",

            is_fallback=False,

            call=failing_primary,
        )

    except RuntimeError:
        pass

    result = run_observed_call(
        collector,

        stage="requirement_extraction",

        prompt_version="req-v1",

        model="fallback-model",

        is_fallback=True,

        call=lambda: "fallback success",
    )

    observability = collector.build(
        total_latency_ms=200.0
    )

    assert result == "fallback success"

    assert (
        observability.llm_call_count
        == 2
    )

    assert (
        observability.fallback_used
        is True
    )

    assert observability.models_used == [
        "primary-model",
        "fallback-model",
    ]