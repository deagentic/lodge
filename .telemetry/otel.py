"""
Optional OpenTelemetry / OpenLLMetry bridge.

Only active when `opentelemetry-sdk` is installed. When active, automatically
instruments Anthropic and Google GenAI SDK calls via OpenLLMetry, converting
spans to Cornerstone telemetry events.

To enable:
    pip install opentelemetry-sdk opentelemetry-exporter-otlp-proto-http
    pip install opentelemetry-instrumentation-anthropic  # for Claude
    pip install opentelemetry-instrumentation-google-genai  # for Gemini

Environment variables:
    AGENTIC_TELEMETRY_URL — used as fallback OTLP endpoint if OTEL_EXPORTER_OTLP_ENDPOINT is not set
    OTEL_EXPORTER_OTLP_ENDPOINT — standard OTEL variable, takes precedence
"""

from __future__ import annotations


def setup_otel_if_available(service_name: str = "cornerstone") -> bool:
    """
    Attempt to configure OpenTelemetry SDK with OTLP exporter.

    Returns True if OpenTelemetry was successfully configured, False if the
    SDK is not installed (graceful degradation).
    """
    try:
        from opentelemetry import trace  # noqa: F401
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError:
        return False

    import os

    otlp_endpoint = os.environ.get(
        "OTEL_EXPORTER_OTLP_ENDPOINT",
        os.environ.get("AGENTIC_TELEMETRY_URL", "").rstrip("/") + "/v1/traces",
    )
    if not otlp_endpoint or otlp_endpoint == "/v1/traces":
        return False

    try:
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

        resource = Resource.create({"service.name": service_name})
        provider = TracerProvider(resource=resource)
        exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
        provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(provider)

        _instrument_llm_providers()
        return True
    except Exception:  # noqa: BLE001
        return False


def _instrument_llm_providers() -> None:
    """Attempt to instrument known LLM SDKs via OpenLLMetry."""
    _try_instrument("opentelemetry.instrumentation.anthropic", "AnthropicInstrumentor")
    _try_instrument("opentelemetry.instrumentation.google_generativeai", "GoogleGenerativeAIInstrumentor")
    _try_instrument("opentelemetry.instrumentation.openai", "OpenAIInstrumentor")


def _try_instrument(module_path: str, class_name: str) -> None:
    try:
        import importlib
        module = importlib.import_module(module_path)
        instrumentor_cls = getattr(module, class_name)
        instrumentor_cls().instrument()
    except Exception:  # nosec B110  # best-effort: instrumentation optional  # noqa: BLE001
        pass
