from fastapi import FastAPI

app = FastAPI(title="bili-knowledge-pipeline")


@app.get("/healthz")
def healthz() -> dict:
    return {"ok": True}
