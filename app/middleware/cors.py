from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI

from app.config import get_settings

settings = get_settings()


def setup_cors(app: FastAPI):
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
