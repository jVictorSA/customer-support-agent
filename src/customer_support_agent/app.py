from fastapi import FastAPI

app = FastAPI(
    title="Customer Support Agent API",
    description=(
        "API de agente de atendimento ao cliente para uma loja de instrumentos "
        "musicais."
    ),
    version="0.1.0",
)


@app.get("/", tags=["Root"])
def read_root() -> dict[str, str]:
    return {
        "name": "Customer Support Agent API",
        "version": "0.1.0",
        "status": "ok",
    }


@app.get("/health", tags=["Health"])
def health_check() -> dict[str, str]:
    return {"status": "ok"}
