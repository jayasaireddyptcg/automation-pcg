from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import get_settings
from app.database import init_db, get_db
from app.routes import auth, workflows, runs, webhooks, integrations, gmail

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    
    # Start Gmail poller in background
    try:
        from app.services.gmail_poller import start_gmail_poller
        async for db in get_db():
            await start_gmail_poller(db)
            break
    except Exception as e:
        print(f"Failed to start Gmail poller: {e}")
    
    yield
    
    # Stop Gmail poller on shutdown
    try:
        from app.services.gmail_poller import stop_gmail_poller
        await stop_gmail_poller()
    except Exception as e:
        print(f"Failed to stop Gmail poller: {e}")


app = FastAPI(
    title="AgentKit API",
    description="OpenAI Agent Builder + n8n Hybrid with Custom Node Engine",
    version="1.0.0",
    lifespan=lifespan,
)

# Allow all origins in dev mode, specific origins in production
if settings.DEV_MODE:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
else:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(auth.router, prefix="/api")
app.include_router(workflows.router, prefix="/api")
app.include_router(runs.router, prefix="/api")
app.include_router(webhooks.router, prefix="/api")
app.include_router(integrations.router, prefix="/api")
app.include_router(gmail.router, prefix="/api")


@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "agentkit"}
