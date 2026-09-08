# Complete Beginner's Guide to FastAPI: End-to-End API Flow in a Real-World Project

Welcome to FastAPI! If you already know basic Python (variables, functions, classes, dictionaries, and imports), this guide will take you step-by-step through how a modern, production-grade FastAPI application works.

We will use the **EffortlessInsight AI Service** codebase you have right here in this repository as our practical case study.

---

## Table of Contents
1. [Why FastAPI? The Core Philosophy](#1-why-fastapi-the-core-philosophy)
2. [Project Architecture Overview](#2-project-architecture-overview)
3. [The Case Study API: `POST /api/v1/process/notice`](#3-the-case-study-api-post-apiv1processnotice)
4. [The 10 Stages of an API Request Lifecycle](#4-the-10-stages-of-an-api-request-lifecycle)
   - [Stage 1: Server Startup & Application Lifespan (`app/main.py`)](#stage-1-server-startup--application-lifespan-appmainpy)
   - [Stage 2: The Middleware "Onion" Layer](#stage-2-the-middleware-onion-layer)
   - [Stage 3: Hierarchical Routing (`main.py` ➔ `app/api/__init__.py` ➔ `process.py`)](#stage-3-hierarchical-routing)
   - [Stage 4: Request Validation with Pydantic (`app/schemas/requests.py`)](#stage-4-request-validation-with-pydantic)
   - [Stage 5: Dependency Injection (`Depends(get_db)`)](#stage-5-dependency-injection-dependsget_db)
   - [Stage 6: Concurrency & Async/Await (`async def`)](#stage-6-concurrency--asyncawait-async-def)
   - [Stage 7: Background Tasks Support (`BackgroundTasks`)](#stage-7-background-tasks-support)
   - [Stage 8: Service Layer & Business Logic (`app/services/...`)](#stage-8-service-layer--business-logic)
   - [Stage 9: Response Serialization & Type Validation (`response_model`)](#stage-9-response-serialization--type-validation)
   - [Stage 10: Automatic OpenAPI & Swagger Documentation (`/docs`)](#stage-10-automatic-openapi--swagger-documentation-docs)
5. [Visual End-to-End Sequence Diagram](#5-visual-end-to-end-sequence-diagram)
6. [FastAPI Concepts Cheat Sheet for Python Developers](#6-fastapi-concepts-cheat-sheet-for-python-developers)
7. [How to Run and Test This Project Locally](#7-how-to-run-and-test-this-project-locally)

---

## 1. Why FastAPI? The Core Philosophy

In traditional Python web frameworks (like Flask or Django), you often had to:
- Manually extract data from `request.json`
- Manually check if fields were missing or had the wrong type (e.g. `if not isinstance(age, int): return error`)
- Manually write Swagger/OpenAPI documentation
- Handle asynchronous I/O with extra complexity

**FastAPI solves this using Python 3 type hints + Pydantic + Starlette**:
1. **Type Hints as Code Contracts**: You declare the types of inputs and outputs using standard Python types (`int`, `str`, `UUID`, custom classes).
2. **Automatic Data Parsing & Validation**: FastAPI automatically converts JSON into Python objects, validating data types before your function even runs. If the client sends bad data, FastAPI returns a clear `422 Unprocessable Entity` error automatically.
3. **High Performance Async**: Built from the ground up on `asyncio` and `uvicorn`, giving performance comparable to NodeJS or Go.
4. **Dependency Injection**: A built-in way to share database connections, authentication, and configuration cleanly.
5. **Automatic Interactive Documentation**: It automatically produces interactive Swagger documentation at `/docs`.

---

## 2. Project Architecture Overview

Look at how the codebase in this repository is structured:

```text
effortless-insight-ai-service/
├── app/
│   ├── main.py              # 🚀 Application Entry Point (App creation, Lifespan, Middlewares)
│   ├── core/                # ⚙️ Global configurations, settings, database connections
│   │   ├── config.py        # Settings loaded from .env (Pydantic BaseSettings)
│   │   └── database.py      # SQLAlchemy async database engine & get_db dependency
│   ├── api/                 # 🌐 HTTP Routing & Endpoints
│   │   ├── __init__.py      # Root API router (groups sub-routers with /api/v1)
│   │   ├── middleware/      # Auth, Error handling, Logging, Metrics
│   │   └── endpoints/       # Route controllers
│   │       ├── process.py   # 📌 Process notice & response generation endpoints
│   │       ├── health.py    # Health check endpoints
│   │       ├── embeddings.py# Vector search & embedding endpoints
│   │       └── admin.py     # Administrative routes
│   ├── schemas/             # 📋 Pydantic Models (Data shapes for Requests & Responses)
│   │   ├── requests.py      # Input models (e.g. ProcessNoticeRequest)
│   │   └── responses.py     # Output models (e.g. AiProcessingResult)
│   ├── models/              # 🗄️ Database ORM Models (SQLAlchemy)
│   └── services/            # 🧠 Business Logic / AI Pipeline / OCR / LLMs
│       └── pipeline/        # Multi-stage notice processing orchestrator
```

### Clean Layering Principle:
- **Router / Endpoint Layer (`app/api/endpoints/`)**: Thin controllers. They accept HTTP requests, validate input, call the service layer, and return HTTP responses.
- **Schema Layer (`app/schemas/`)**: Defines the *contract* (data shapes) between the outside world and Python.
- **Service Layer (`app/services/`)**: Pure business logic (e.g. OCR, calling OpenAI, calculating risk scores). It knows nothing about HTTP request objects.
- **Core Layer (`app/core/`)**: Cross-cutting concerns like database connection pools and environment configuration.

---

## 3. The Case Study API: `POST /api/v1/process/notice`

To understand FastAPI end-to-end, let's trace the central API endpoint in this project:

- **HTTP Method**: `POST`
- **URL**: `/api/v1/process/notice`
- **Purpose**: Accepts a GST tax notice file URL and its ID, runs it through an 8-stage AI analysis pipeline (OCR -> entity extraction -> classification -> RAG -> LLM analysis -> verification -> report generation), and returns a detailed AI report.

### Incoming JSON Request Example:
```json
{
  "noticeId": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
  "fileUrl": "https://s3.amazonaws.com/notices/sample-notice.pdf",
  "organizationId": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "priority": "high"
}
```

### Outgoing JSON Response Example:
```json
{
  "success": true,
  "error": null,
  "report": {
    "riskScore": 85,
    "riskLevel": "high",
    "summaryEn": "Demand notice under section 73 for ITC mismatch.",
    "summaryHi": "धारा 73 के तहत आईटीसी बेमेल के लिए मांग नोटिस।",
    "plainEnglish": "The tax department claims you claimed excess Input Tax Credit in FY 2021-22.",
    "metadata": {
      "noticeType": "DRC-01",
      "noticeNumber": "DRC01/2023/001",
      "gstin": "27AABCU9603R1ZM",
      "taxAmount": 150000.0,
      "penaltyAmount": 15000.0
    },
    "actionItems": [
      {
        "priority": 1,
        "action": "Reconcile GSTR-2B with GSTR-3B",
        "description": "Verify the supplier invoice details in the portal.",
        "dueInDays": 15
      }
    ]
  }
}
```

---

## 4. The 10 Stages of an API Request Lifecycle

Let's follow what happens from the moment the server boots up until the client receives the HTTP response.

```
       [Client HTTP Request]
                 │
                 ▼
     ┌───────────────────────┐
     │   Uvicorn ASGI Server │
     └───────────┬───────────┘
                 │
                 ▼
     ┌───────────────────────┐
     │   Middleware Stack    │  (Error -> Metrics -> Logging -> Auth -> CORS)
     └───────────┬───────────┘
                 │
                 ▼
     ┌───────────────────────┐
     │   APIRouter Matching  │  (/api/v1 -> /process -> /notice)
     └───────────┬───────────┘
                 │
                 ▼
     ┌───────────────────────┐
     │ Pydantic Validation   │  (Parses JSON body into ProcessNoticeRequest)
     └───────────┬───────────┘
                 │
                 ▼
     ┌───────────────────────┐
     │ Dependency Injection  │  (Executes Depends(get_db) -> yields AsyncSession)
     └───────────┬───────────┘
                 │
                 ▼
     ┌───────────────────────┐
     │  Endpoint Controller  │  (process_notice in process.py)
     └───────────┬───────────┘
                 │
                 ▼
     ┌───────────────────────┐
     │     Service Layer     │  (PipelineOrchestrator, OCR, OpenAI LLM)
     └───────────┬───────────┘
                 │
                 ▼
     ┌───────────────────────┐
     │ Response Serialization│  (Validates against AiProcessingResult & serializes to camelCase JSON)
     └───────────┬───────────┘
                 │
                 ▼
        [Client HTTP Response]
```

---

### Stage 1: Server Startup & Application Lifespan (`app/main.py`)

When you run FastAPI with `uvicorn app.main:app`, the first thing that happens is FastAPI initializes the app instance and runs its **Lifespan** context manager.

Look at `app/main.py`:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management"""
    logger.info("Starting EffortlessInsight AI Service")

    # Initialize database connection pool & tables before accepting any requests
    await init_db()

    yield  # ⏸️ The application runs and serves requests here

    logger.info("Shutting down EffortlessInsight AI Service")
```

#### Why this matters:
- The code **before** `yield` runs once when the server starts (e.g., establishing database pools, checking API keys).
- The code **after** `yield` runs once when the server gracefully shuts down (e.g., closing connections, freeing resources).
- This replaces the older `@app.on_event("startup")` and `@app.on_event("shutdown")` patterns.

Then, the FastAPI instance is instantiated:
```python
app = FastAPI(
    title="EffortlessInsight AI Service",
    description="AI-powered GST notice processing service",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.environment == "development" else None,
    redoc_url="/redoc" if settings.environment == "development" else None,
)
```

---

### Stage 2: The Middleware "Onion" Layer

Before a request hits your router function, it passes through a stack of **Middlewares**. Think of middlewares like layers of an onion: the request travels inwards through each layer, reaches the endpoint, and the response travels back outwards.

Look at how middlewares are registered in `app/main.py`:

```python
# 1. Error handling (outermost - catches unhandled exceptions from all inner layers)
app.add_middleware(ErrorHandlerMiddleware)

# 2. Metrics (tracks request duration, active counts)
app.add_middleware(MetricsMiddleware)

# 3. Request Logging (logs path, method, client IP)
app.add_middleware(RequestLoggingMiddleware)

# 4. Authentication (validates X-API-Key header)
app.add_middleware(APIKeyMiddleware)

# 5. CORS (Cross-Origin Resource Sharing for browser clients)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

#### Example: How `APIKeyMiddleware` Works (`app/api/middleware/auth.py`):
```python
class APIKeyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # 1. Skip auth for health check and /docs
        if request.url.path in ["/health", "/docs", "/openapi.json"]:
            return await call_next(request)

        # 2. Check X-API-Key header
        provided_key = request.headers.get("X-API-Key")
        if not provided_key or provided_key != self.api_key:
            # ⛔ Block the request immediately!
            return JSONResponse(status_code=401, content={"detail": "Invalid or missing API key"})

        # ✅ Pass request to the next middleware/endpoint
        response = await call_next(request)
        return response
```

---

### Stage 3: Hierarchical Routing

In large applications, putting every route in one file creates a messy, thousands-of-lines file. FastAPI solves this cleanly with `APIRouter`.

Let's see how routers are composed hierarchically:

#### 1. In `app/main.py`:
```python
from app.api import router as api_router

# Mount all API endpoints under the "/api/v1" prefix
app.include_router(api_router, prefix="/api/v1")
```

#### 2. In `app/api/__init__.py`:
```python
from fastapi import APIRouter
from app.api.endpoints import health, process, embeddings, admin

router = APIRouter()

# Group endpoints with sub-prefixes and Swagger tags
router.include_router(process.router, prefix="/process", tags=["Processing"])
router.include_router(health.router, prefix="/health", tags=["Health"])
router.include_router(embeddings.router, prefix="/embeddings", tags=["Embeddings"])
router.include_router(admin.router, prefix="/admin", tags=["Admin"])
```

#### 3. In `app/api/endpoints/process.py`:
```python
router = APIRouter()

@router.post("/notice", response_model=AiProcessingResult)
async def process_notice(...):
    ...
```

#### Resulting Full URL:
`[Base Domain]` + `/api/v1` + `/process` + `/notice` = **`http://localhost:8000/api/v1/process/notice`**

---

### Stage 4: Request Validation with Pydantic

Here is where FastAPI shines compared to other frameworks. Look at the function signature in `app/api/endpoints/process.py`:

```python
@router.post("/notice", response_model=AiProcessingResult)
async def process_notice(
    request: ProcessNoticeRequest,               # 👈 Pydantic Model (Body)
    background_tasks: BackgroundTasks,           # 👈 FastAPI Background Task utility
    db: AsyncSession = Depends(get_db)           # 👈 Dependency Injection (Database)
):
```

Look at the definition of `ProcessNoticeRequest` in `app/schemas/requests.py`:

```python
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field

class ProcessNoticeRequest(BaseModel):
    """Request model for notice processing"""
    notice_id: UUID = Field(..., alias="noticeId", description="UUID of the notice to process")
    file_url: str = Field(..., alias="fileUrl", description="Presigned S3 URL for the notice file")
    organization_id: Optional[UUID] = Field(None, alias="organizationId", description="Organization ID")
    priority: Optional[str] = Field("normal", description="Processing priority: low, normal, high")
    callback_url: Optional[str] = Field(None, alias="callbackUrl", description="URL for webhook notification")

    class Config:
        populate_by_name = True
```

#### What FastAPI and Pydantic do automatically:
1. **JSON Body Extraction**: Because `request` is typed as a Pydantic model (`ProcessNoticeRequest`), FastAPI automatically parses the incoming JSON request body.
2. **Type Enforcement**: If a user sends `"noticeId": "123"` (not a valid UUID) or omits `"fileUrl"`, FastAPI will **abort immediately** and return:
   ```json
   {
     "detail": [
       {
         "loc": ["body", "noticeId"],
         "msg": "value is not a valid uuid",
         "type": "type_error.uuid"
       }
     ]
   }
   ```
   **You never have to write manual validation code!**
3. **Alias Mapping (`alias="noticeId"`)**: In .NET or frontend JavaScript, naming conventions use `camelCase` (`noticeId`, `fileUrl`), while Python standard is `snake_case` (`notice_id`, `file_url`). The `alias` parameter bridges this seamlessly without breaking Python conventions.
4. **Default Values**: If `priority` is not sent, it automatically defaults to `"normal"`.

---

### Stage 5: Dependency Injection (`Depends(get_db)`)

**Dependency Injection (DI)** sounds complicated, but in FastAPI it is simple and elegant: it is a way to say **"Before running this function, run another helper function and pass its result into my parameter."**

Notice this parameter in our route:
```python
db: AsyncSession = Depends(get_db)
```

Let's look at `get_db` in `app/core/database.py`:

```python
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency to get database session"""
    session_maker = get_session_maker()
    async with session_maker() as session:
        try:
            yield session          # 1. Provide the open DB session to the endpoint
            await session.commit() # 2. If endpoint succeeds, commit the transaction
        except Exception:
            await session.rollback() # 3. If an error occurs, roll back changes
            raise
        finally:
            await session.close()  # 4. Always close the session to prevent connection leaks!
```

#### How the magic works:
1. When a request arrives, FastAPI calls `get_db()`.
2. It executes up to the `yield session` line.
3. The yielded `session` is injected into `process_notice(db=session)`.
4. Your endpoint runs and does its work.
5. After your endpoint finishes (or raises an error), FastAPI resumes `get_db()` after the `yield` statement to commit or rollback and close the connection.

This guarantees you **never leak database connections**, even if an unexpected error occurs!

---

### Stage 6: Concurrency & Async/Await (`async def`)

Notice that `process_notice` is declared with `async def`:

```python
@router.post("/notice", response_model=AiProcessingResult)
async def process_notice(...):
    ...
    # Calling an async service method:
    result = await pipeline.process(...)
    ...
    return result
```

#### `async def` vs regular `def` in FastAPI:
- **`def` (Synchronous)**: FastAPI runs synchronous endpoints in a separate threadpool (`anyio`). Good for CPU-heavy tasks.
- **`async def` (Asynchronous)**: FastAPI runs asynchronous endpoints directly on the event loop. When code does `await`, the event loop pauses this specific request and handles other incoming requests while waiting for network I/O (like database queries, S3 file downloads, or OpenAI API calls).

This allows FastAPI to handle **thousands of concurrent requests** on a single server process with low memory usage.

---

### Stage 7: Background Tasks Support

Notice this parameter in the route signature:
```python
background_tasks: BackgroundTasks
```

If you have work that takes time (like sending an email, writing audit logs, or notifying a webhook) and you don't want the client to wait for it, you can add it to `background_tasks`:

```python
# Example:
background_tasks.add_task(send_slack_notification, notice_id=request.notice_id)
```
FastAPI will return the HTTP response to the client first, and then execute `send_slack_notification` in the background.

---

### Stage 8: Service Layer & Business Logic

FastAPI best practices recommend keeping route handlers small and delegating heavy logic to separate Service classes.

In `app/api/endpoints/process.py`, look how clean the handler is:

```python
@router.post("/notice", response_model=AiProcessingResult)
async def process_notice(
    request: ProcessNoticeRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    logger.info("Processing notice request", notice_id=str(request.notice_id))
    increment_active_jobs()

    try:
        # 1. Instantiate the business logic pipeline orchestrator
        pipeline = PipelineOrchestrator()

        # 2. Run the 8-stage AI processing
        result = await pipeline.process(
            notice_id=request.notice_id,
            file_url=request.file_url,
            organization_id=request.organization_id,
            priority=request.priority or "normal",
        )

        # 3. Record metrics
        record_processing_complete(result.success)
        return result

    except Exception as e:
        logger.error("Notice processing failed", error=str(e))
        record_processing_complete(False)
        return AiProcessingResult(success=False, error=str(e))
    finally:
        decrement_active_jobs()
```

The orchestrator (`app/services/pipeline/orchestrator.py`) handles downloading the PDF, performing OCR, querying vector embeddings via pgvector, and calling OpenAI's GPT-4o model.

---

### Stage 9: Response Serialization & Type Validation (`response_model`)

In the endpoint decorator:
```python
@router.post("/notice", response_model=AiProcessingResult)
```

The `response_model=AiProcessingResult` tells FastAPI:
1. **Response Filtering**: Only fields defined in `AiProcessingResult` will be sent to the client. Any internal private fields or sensitive passwords on internal objects are automatically stripped out.
2. **Data Formatting**: Look at `CamelCaseModel` in `app/schemas/responses.py`:
   ```python
   def to_camel(string: str) -> str:
       components = string.split('_')
       return components[0] + ''.join(x.title() for x in components[1:])

   class CamelCaseModel(BaseModel):
       class Config:
           populate_by_name = True
           alias_generator = to_camel
   ```
   FastAPI automatically converts Python snake_case attributes (`risk_score`, `action_items`, `due_in_days`) into JSON camelCase properties (`riskScore`, `actionItems`, `dueInDays`) in the final HTTP response!
3. **Data Type Validation with `@field_validator`**:
   LLMs (like OpenAI GPT) sometimes output numbers as strings like `"5"` or nulls as `"null"`. Notice how `app/schemas/responses.py` uses Pydantic validators to protect data integrity:
   ```python
   @field_validator('priority', mode='before')
   @classmethod
   def parse_priority(cls, v):
       if isinstance(v, str):
           try:
               return int(v)
           except ValueError:
               return 5  # Fallback to default
       return v
   ```

---

### Stage 10: Automatic OpenAPI & Swagger Documentation (`/docs`)

FastAPI automatically reads:
- Your route path (`/notice`) and HTTP method (`POST`)
- Docstring under your function (`"""Process a GST notice through the AI pipeline..."""`)
- Request schema (`ProcessNoticeRequest`) with field descriptions and types
- Response schema (`AiProcessingResult`)
- Sub-router tags (`tags=["Processing"]`)

And generates:
1. A standard JSON OpenAPI specification schema at `/openapi.json`.
2. An interactive, beautiful web interface at **`http://localhost:8000/docs`** (Swagger UI) where anyone can test endpoints directly from the browser!
3. An alternative clean documentation UI at **`http://localhost:8000/redoc`** (ReDoc).

---

## 5. Visual End-to-End Sequence Diagram

Here is the exact message sequence when a client calls this API:

```text
Client                  FastAPI Server               Middleware Stack             Process Endpoint              PipelineOrchestrator            PostgreSQL DB
  │                            │                             │                            │                               │                           │
  │── 1. POST /api/v1/process/notice ───────────────────────>│                            │                               │                           │
  │   (Headers: X-API-Key,     │                             │                            │                               │                           │
  │    Body: JSON notice info) │                             │                            │                               │                           │
  │                            │                             │── 2. Check X-API-Key ─────>│                               │                           │
  │                            │                             │── 3. Start Timer (Metrics) │                               │                           │
  │                            │                             │── 4. Log Request ─────────>│                               │                           │
  │                            │                             │                            │                               │                           │
  │                            │                             │                            │── 5. Parse & Validate JSON ──>│                           │
  │                            │                             │                            │   (ProcessNoticeRequest)      │                           │
  │                            │                             │                            │                               │                           │
  │                            │                             │                            │── 6. Execute Depends(get_db) ────────────────────────────>│
  │                            │                             │                            │<── 7. Return AsyncSession ────────────────────────────────│
  │                            │                             │                            │                               │                           │
  │                            │                             │                            │── 8. Call pipeline.process() ─>│                          │
  │                            │                             │                            │                               │── 9. OCR & AI Analysis ───│
  │                            │                             │                            │                               │── 10. Query/Save Data ───>│
  │                            │                             │                            │                               │<── 11. DB Result ─────────│
  │                            │                             │                            │<── 12. Return AI Report ──────│                           │
  │                            │                             │                            │                               │                           │
  │                            │                             │                            │── 13. Serialize to JSON ──────│                           │
  │                            │                             │                            │   (AiProcessingResult)        │                           │
  │                            │                             │                            │                               │                           │
  │                            │                             │<── 14. Commit & Close DB ─────────────────────────────────────────────────────────────│
  │                            │<── 15. Record Metrics ──────│                            │                               │                           │
  │<── 16. HTTP 200 OK Response ─────────────────────────────│                            │                               │                           │
  │   (Structured JSON Report) │                             │                            │                               │                           │
```

---

## 6. FastAPI Concepts Cheat Sheet for Python Developers

| Concept | What It Is in Python | Where in This Project It Is Used |
| :--- | :--- | :--- |
| **`FastAPI()`** | The core application object managing routes, middlewares, and startup events | `app/main.py` |
| **`APIRouter`** | A mini-app to organize endpoints into modular files | `app/api/endpoints/*.py`, `app/api/__init__.py` |
| **`BaseModel` (Pydantic)** | A class defining expected data types, fields, and validations for JSON | `app/schemas/requests.py`, `app/schemas/responses.py` |
| **`Field(...)`** | Adds metadata, validation constraints (min/max), aliases, and descriptions to model fields | `app/schemas/requests.py` |
| **`Depends(...)`** | Dependency injection for DB connections, authentication, and reusable services | `app/api/endpoints/process.py`, `app/core/database.py` |
| **`async def` / `await`** | Asynchronous execution permitting non-blocking I/O during network calls | Used in all endpoints and service calls |
| **`BackgroundTasks`** | Schedules background jobs to execute after returning the HTTP response | `app/api/endpoints/process.py` |
| **`HTTPException`** | Standard way to return HTTP error status codes (e.g. 400, 404, 500) | `app/api/endpoints/process.py` |
| **`BaseSettings`** | Automatically reads configuration and secrets from `.env` file | `app/core/config.py` |
| **`lifespan`** | Asynchronous context manager for startup and shutdown actions | `app/main.py` |

---

## 7. How to Run and Test This Project Locally

If you want to run this FastAPI application locally on your machine, follow these simple steps:

### 1. Create and activate a Python virtual environment
```powershell
# In PowerShell (Windows)
python -m venv venv
.\venv\Scripts\Activate.ps1
```

### 2. Install dependencies
```powershell
pip install -r requirements.txt
```

### 3. Setup your `.env` file
Copy the `.env.example` file to `.env`:
```powershell
cp .env.example .env
```

### 4. Start the FastAPI development server
```powershell
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
- `--reload`: Automatically restarts the server whenever you edit and save any Python file!

### 5. Explore interactive documentation
Open your web browser and navigate to:
- **Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc UI**: [http://localhost:8000/redoc](http://localhost:8000/redoc)
- **Health Check**: [http://localhost:8000/health](http://localhost:8000/health)

You can click on the `POST /api/v1/process/notice` endpoint in Swagger UI, click **"Try it out"**, paste a test JSON payload, and click **"Execute"** to see FastAPI in action!

---

*Document prepared for EffortlessInsight AI Service developers.*
