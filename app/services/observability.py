import logging
from time import perf_counter
from typing import Callable, Literal, Optional, TypeVar

from pydantic import BaseModel


T = TypeVar("T")


logger = logging.getLogger(__name__)


class LLMCallMetric(BaseModel):
    stage: str
    prompt_version: str
    model: str

    is_fallback: bool

    latency_ms: float

    status: Literal[
        "success",
        "error",
    ]

    error_type: Optional[str] = None


class AnalysisObservability(BaseModel):
    pipeline_version: str

    total_latency_ms: float

    llm_call_count: int

    fallback_used: bool

    models_used: list[str]

    prompt_versions: dict[str, str]

    calls: list[LLMCallMetric]


class ObservabilityCollector:

    def __init__(
        self,
        pipeline_version: str,
    ):
        self.pipeline_version = pipeline_version

        self.calls: list[
            LLMCallMetric
        ] = []

    def run_llm_call(
        self,
        *,
        stage: str,
        prompt_version: str,
        model: str,
        is_fallback: bool,
        call: Callable[[], T],
    ) -> T:

        start_time = perf_counter()

        try:
            result = call()

        except Exception as error:

            latency_ms = (
                perf_counter() - start_time
            ) * 1000

            self.calls.append(
                LLMCallMetric(
                    stage=stage,
                    prompt_version=prompt_version,
                    model=model,
                    is_fallback=is_fallback,
                    latency_ms=round(
                        latency_ms,
                        2,
                    ),
                    status="error",
                    error_type=type(error).__name__,
                )
            )

            logger.warning(
                (
                    "LLM call failed | "
                    "stage=%s model=%s "
                    "fallback=%s latency_ms=%.2f "
                    "error=%s"
                ),
                stage,
                model,
                is_fallback,
                latency_ms,
                type(error).__name__,
            )

            raise

        latency_ms = (
            perf_counter() - start_time
        ) * 1000

        self.calls.append(
            LLMCallMetric(
                stage=stage,
                prompt_version=prompt_version,
                model=model,
                is_fallback=is_fallback,
                latency_ms=round(
                    latency_ms,
                    2,
                ),
                status="success",
            )
        )

        logger.info(
            (
                "LLM call completed | "
                "stage=%s model=%s "
                "fallback=%s latency_ms=%.2f"
            ),
            stage,
            model,
            is_fallback,
            latency_ms,
        )

        return result

    def build(
        self,
        total_latency_ms: float,
    ) -> AnalysisObservability:

        prompt_versions = {}

        for call in self.calls:
            prompt_versions[
                call.stage
            ] = call.prompt_version

        models_used = list(
            dict.fromkeys(
                call.model
                for call in self.calls
            )
        )

        return AnalysisObservability(
            pipeline_version=(
                self.pipeline_version
            ),

            total_latency_ms=round(
                total_latency_ms,
                2,
            ),

            llm_call_count=len(
                self.calls
            ),

            fallback_used=any(
                call.is_fallback
                for call in self.calls
            ),

            models_used=models_used,

            prompt_versions=(
                prompt_versions
            ),

            calls=self.calls,
        )


def run_observed_call(
    collector: Optional[
        ObservabilityCollector
    ],
    *,
    stage: str,
    prompt_version: str,
    model: str,
    is_fallback: bool,
    call: Callable[[], T],
) -> T:

    if collector is None:
        return call()

    return collector.run_llm_call(
        stage=stage,
        prompt_version=prompt_version,
        model=model,
        is_fallback=is_fallback,
        call=call,
    )