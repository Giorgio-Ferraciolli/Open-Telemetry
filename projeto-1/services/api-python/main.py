import os
import time
import random
import logging

import httpx
from fastapi import FastAPI, HTTPException

from opentelemetry import trace, baggage, context as otel_context
from opentelemetry.trace import Status, StatusCode

# --- OpenTelemetry: setup explícito ---
from opentelemetry import trace, metrics
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry._logs import set_logger_provider

from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter

from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor

# 1. "Resource" = identidade do serviço (quem está produzindo a telemetria)
resource = Resource.create({
    "service.name": os.getenv("OTEL_SERVICE_NAME", "api-python"),
    "service.version": "0.1.0",
    "service.namespace": "demo",
})

# 2. Traces
tracer_provider = TracerProvider(resource=resource)
tracer_provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
trace.set_tracer_provider(tracer_provider)

# 3. Métricas (exportadas a cada 10s)
metric_reader = PeriodicExportingMetricReader(OTLPMetricExporter(), export_interval_millis=10000)
meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
metrics.set_meter_provider(meter_provider)

# 4. Logs — manda os logs do Python pro OTel
logger_provider = LoggerProvider(resource=resource)
logger_provider.add_log_record_processor(BatchLogRecordProcessor(OTLPLogExporter()))
set_logger_provider(logger_provider)

# 5. Instrumentação automática:
#    - LoggingInstrumentor injeta trace_id/span_id em cada log
#    - FastAPIInstrumentor cria spans de servidor pra cada requisição
LoggingInstrumentor().instrument(set_logging_format=True)
HTTPXClientInstrumentor().instrument()  # injeta traceparent em chamadas httpx

# --- aplicação ---
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("api-python")
# Adiciona um handler que envia os logs também pro OTel (em paralelo ao stdout)
log.addHandler(LoggingHandler(level=logging.INFO, logger_provider=logger_provider))

app = FastAPI(title="api-python")
FastAPIInstrumentor.instrument_app(app)

tracer = trace.get_tracer("api-python.checkout")

# --- Métricas de negócio ---
business_meter = metrics.get_meter("api-python.business")
checkouts_counter = business_meter.create_counter(
    "app.checkouts.total",
    description="Total de checkouts processados",
    unit="1",
)
checkout_duration = business_meter.create_histogram(
    "app.checkout.duration",
    description="Duração do checkout (ms)",
    unit="ms",
)

NODE_URL = os.getenv("NODE_URL", "http://api-node:8000")
CUSTOMERS = ["alice", "bob", "charlie", "diana"]

PRODUCTS = {
    1: {"id": 1, "name": "Café",   "price": 12.50},
    2: {"id": 2, "name": "Pão",    "price":  5.00},
    3: {"id": 3, "name": "Queijo", "price": 32.90},
}


@app.get("/")
def root():
    return {"service": "api-python", "ok": True}


@app.get("/products")
def list_products():
    log.info("listando %d produtos", len(PRODUCTS))
    return list(PRODUCTS.values())


@app.get("/products/{pid}")
def get_product(pid: int):
    p = PRODUCTS.get(pid)
    if not p:
        log.warning("produto %d não encontrado", pid)
        raise HTTPException(status_code=404, detail="not found")
    return p


@app.get("/slow")
def slow():
    delay = random.uniform(0.3, 1.2)
    time.sleep(delay)
    return {"slept_seconds": round(delay, 3)}


@app.get("/broken")
def broken():
    raise RuntimeError("erro intencional pra gerar span de erro")


@app.get("/checkout/{pid}")
def checkout(pid: int):
    """Olha o produto local e consulta o estoque no api-node."""
    customer = random.choice(CUSTOMERS)
    started = time.monotonic()
    status_label = "ok"

    token = otel_context.attach(baggage.set_baggage("customer.id", customer))
    try:
        try:
            with tracer.start_as_current_span("validate_product") as span:
                span.set_attribute("product.id", pid)
                span.set_attribute("customer.id", customer)
                product = PRODUCTS.get(pid)
                if not product:
                    span.add_event("produto inexistente", {"pid": pid})
                    span.set_status(Status(StatusCode.ERROR, "produto desconhecido"))
                    raise HTTPException(status_code=404, detail="produto não encontrado")
                span.set_attribute("product.name", product["name"])
                span.set_attribute("product.price", product["price"])

            with tracer.start_as_current_span("call_stock_service") as span:
                span.set_attribute("upstream.service", "api-node")
                log.info("consultando estoque do produto %d para customer=%s", pid, customer)
                with httpx.Client(timeout=5.0) as client:
                    r = client.get(f"{NODE_URL}/stock/{pid}")
                span.set_attribute("upstream.status_code", r.status_code)
                if r.status_code != 200:
                    span.add_event("api-node retornou erro", {"status": r.status_code})
                    span.set_status(Status(StatusCode.ERROR, "estoque indisponível"))
                    raise HTTPException(status_code=502, detail="estoque indisponível")
                stock = r.json()

            return {"product": product, "in_stock": stock["in_stock"], "customer": customer}
        except HTTPException as e:
            status_label = "client_error" if e.status_code < 500 else "server_error"
            raise
        except Exception:
            status_label = "server_error"
            raise
    finally:
        elapsed_ms = (time.monotonic() - started) * 1000
        labels = {"product.id": str(pid), "status": status_label}
        checkouts_counter.add(1, labels)
        checkout_duration.record(elapsed_ms, labels)
        otel_context.detach(token)
