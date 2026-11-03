import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import DateTime, Integer, String, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column
from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from datetime import datetime, timezone

DATABASE_URL = os.getenv("DATABASE_URL", "mysql+pymysql://lab:lab@mysql:3306/lab")
OTEL_ENDPOINT = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-collector:4317")

engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_recycle=280)

class Base(DeclarativeBase):
    pass

class Item(Base):
    __tablename__ = "items"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

class ItemCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)

class ItemResponse(BaseModel):
    id: int
    name: str
    created_at: datetime


def configure_tracing() -> None:
    resource = Resource.create({
        "service.name": os.getenv("OTEL_SERVICE_NAME", "fastapi-lab"),
        "service.version": "1.0.0",
        "deployment.environment": "lab",
    })
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter(endpoint=OTEL_ENDPOINT, insecure=True))
    )
    trace.set_tracer_provider(provider)
    SQLAlchemyInstrumentor().instrument(engine=engine)

@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_tracing()
    for _ in range(30):
        try:
            Base.metadata.create_all(engine)
            break
        except Exception:
            import time
            time.sleep(2)
    else:
        raise RuntimeError("MySQL não ficou disponível a tempo")
    yield

app = FastAPI(title="OTel Lab API", version="1.0.0", lifespan=lifespan)
FastAPIInstrumentor.instrument_app(app)
app.mount("/static", StaticFiles(directory="frontend"), name="static")

@app.get("/", include_in_schema=False)
def index():
    return FileResponse("frontend/index.html")

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/api/items", response_model=ItemResponse, status_code=201)
def create_item(payload: ItemCreate):
    with Session(engine) as session:
        item = Item(name=payload.name.strip())
        if not item.name:
            raise HTTPException(status_code=422, detail="O nome não pode ficar vazio")
        session.add(item)
        session.commit()
        session.refresh(item)
        return item

@app.get("/api/items", response_model=list[ItemResponse])
def list_items():
    with Session(engine) as session:
        return list(session.scalars(select(Item).order_by(Item.id.desc())).all())
