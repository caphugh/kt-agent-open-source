from fastapi import FastAPI

app = FastAPI(title="KT Agent API", description="API for the KT Agent application")

@app.get("/api/health")
def health_check():
    return {"status": "ok"}
