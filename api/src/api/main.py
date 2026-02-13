import os

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from api.controller.chat import router as chat_router

app = FastAPI(title="y-agent API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat_router)

# Serve Vite build output at root
_web_dist = os.path.join(os.path.dirname(__file__), "..", "..", "..", "web", "dist")
_web_dist = os.path.normpath(_web_dist)
if os.path.isdir(_web_dist):
    app.mount("/", StaticFiles(directory=_web_dist, html=True), name="web")


def main():
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)


if __name__ == "__main__":
    main()
