#!/usr/bin/env python3
"""Small local FastAPI wrapper around one loaded Dot Reflex controller."""

from __future__ import annotations

import os
import threading
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Request

from inference import DEFAULT_ADAPTER, DotReflex


@asynccontextmanager
async def lifespan(app: FastAPI):
    adapter = os.environ.get("DOT_REFLEX_ADAPTER", DEFAULT_ADAPTER)
    app.state.controller = DotReflex(adapter)
    app.state.generation_lock = threading.Lock()
    yield


app = FastAPI(
    title="Dot Reflex 14B",
    version="1.0.0",
    description="Local agent execution-recovery controller.",
    lifespan=lifespan,
)


@app.get("/healthz")
def health(request: Request) -> dict[str, Any]:
    return {"status": "ok", **request.app.state.controller.identity}


@app.post("/v1/decision")
def decision(trajectory: dict[str, Any], request: Request) -> dict[str, Any]:
    try:
        with request.app.state.generation_lock:
            result = request.app.state.controller.predict(trajectory)
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if not result["parse_valid"]:
        raise HTTPException(status_code=502, detail=result)
    return result

