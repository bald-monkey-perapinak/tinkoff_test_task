import asyncio
import csv
import hashlib
import io
import logging
import shutil
import time
import uuid
from contextlib import asynccontextmanager

from circuit_breaker import groq_breaker, hh_breaker
from cli import build_criteria_text
from config import (
    ALLOWED_ORIGINS,
    ANALYSIS_MAX_VACANCIES,
    DB_PATH,
    GROQ_API_KEY,
    MAX_UPLOAD_SIZE,
    MAX_VACANCIES_PER_SESSION,
    NOTIFICATION_INTERVAL,
    RATE_LIMITS,
    validate_startup_config,
)
from database import (
    add_favorite,
    add_subscription,
    backup_database,
    batch_is_vacancy_seen,
    batch_mark_vacancies_seen,
    cleanup_expired_sessions,
    get_active_subscriptions,
    get_all_session_vacancies,
    get_favorites,
    get_session,
    init_db,
    remove_favorite,
    remove_subscription,
    save_session,
)
from fastapi import FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse, StreamingResponse
from logging_config import generate_request_id, request_id_var, setup_logging
from models import CriteriaInput, Favorite, Schedule, SearchParams, Subscription
from services.analyzer import analyze_with_llm
from services.hh_client import get_area_suggestions, get_role_suggestions, search_vacancies
from services.notifier import notify_new_vacancies
from services.parser import _csv_safe, parse_uploaded_file
from services.report import generate_report
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

setup_logging()
logger = logging.getLogger(__name__)

limiter = Limiter(key_func=get_remote_address)
_background_task: asyncio.Task | None = None


async def _check_subscriptions() -> int:
    subs = await get_active_subscriptions()
    if not subs:
        return 0

    total_notified = 0
    for sub in subs:
        try:
            schedule = None
            if sub.schedule:
                try:
                    schedule = Schedule(sub.schedule)
                except ValueError:
                    schedule = None

            params = SearchParams(
                query=sub.query or "",
                area=sub.area,
                salary_from=sub.min_salary,
                schedule=schedule,
                per_page=10,
            )
            vacancies, _ = await search_vacancies(params)

            seen = await batch_is_vacancy_seen(sub.chat_id, [v.id for v in vacancies])
            new_vacancies = [v for v in vacancies if v.id not in seen]

            if new_vacancies:
                sent = await notify_new_vacancies(sub.chat_id, new_vacancies)
                await batch_mark_vacancies_seen(sub.chat_id, [v.id for v in new_vacancies])
                total_notified += sent
                logger.info(f"Sent {sent} notifications to chat {sub.chat_id}")
        except Exception as e:
            logger.error(f"Notification check failed for subscription {sub.id}: {e}")
            continue

    return total_notified


async def _notification_loop():
    while True:
        try:
            count = await _check_subscriptions()
            if count:
                logger.info(f"Background check: {count} notifications sent")
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Background notification loop error: {e}")
        await asyncio.sleep(NOTIFICATION_INTERVAL)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _background_task
    validate_startup_config()
    await init_db()
    logger.info("Database initialized")
    await backup_database()
    _background_task = asyncio.create_task(_notification_loop())
    logger.info(f"Background notification task started (interval: {NOTIFICATION_INTERVAL}s)")
    yield
    if _background_task:
        _background_task.cancel()
        try:
            await _background_task
        except asyncio.CancelledError:
            pass
    from services.hh_client import close_clients as close_hh_clients
    from services.notifier import close_clients as close_notifier_clients
    await close_hh_clients()
    await close_notifier_clients()
    logger.info("HTTP clients closed, background notification task stopped")


app = FastAPI(title="Vacancy Agent API", lifespan=lifespan)
app.state.limiter = limiter


@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request_id = generate_request_id()
    token = request_id_var.set(request_id)
    request.state.request_id = request_id
    try:
        response = await call_next(request)
    finally:
        request_id_var.reset(token)
    response.headers["X-Request-ID"] = request_id
    return response


@app.middleware("http")
async def validate_telegram_auth(request: Request, call_next):
    from auth import validate_telegram_init_data
    from config import TELEGRAM_BOT_TOKEN

    if request.url.path.startswith("/api/") and not request.url.path.startswith("/api/health") and request.method != "OPTIONS":
        host = request.headers.get("host", "")
        is_local = "localhost" in host or "127.0.0.1" in host

        if not is_local:
            if not TELEGRAM_BOT_TOKEN:
                return JSONResponse(
                    status_code=503,
                    detail="Server misconfigured: TELEGRAM_BOT_TOKEN not set",
                )
            init_data = request.headers.get("Telegram-Init-Data", "")
            if not init_data:
                return JSONResponse(status_code=401, detail="Missing Telegram-Init-Data header")
            result = validate_telegram_init_data(init_data, TELEGRAM_BOT_TOKEN)
            if result is None:
                return JSONResponse(status_code=403, detail="Invalid Telegram initData")
            request.state.telegram_user = result

    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; connect-src 'self' https://api.hh.ru https://vacancy-agent.onrender.com; frame-ancestors 'none'"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"detail": "Too many requests. Please slow down."},
    )

app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type", "Telegram-Init-Data"],
)


@app.get("/api/search")
@limiter.limit(RATE_LIMITS["search"])
async def api_search(
    request: Request,
    query: str = Query(default="", max_length=200),
    area: str = Query(default=None, max_length=50),
    salary_from: int = Query(default=None, ge=0, le=10000000),
    salary_to: int = Query(default=None, ge=0, le=10000000),
    experience: str = Query(default=None, max_length=30),
    schedule: str = Query(default=None, max_length=30),
    professional_role: str = Query(default=None, max_length=50),
    page: int = Query(default=0, ge=0, le=100),
    per_page: int = Query(default=20, ge=1, le=100),
):
    try:
        params = SearchParams(
            query=query,
            area=area,
            salary_from=salary_from,
            salary_to=salary_to,
            experience=experience,
            schedule=schedule,
            professional_role=professional_role,
            page=page,
            per_page=per_page,
        )
        vacancies, total = await asyncio.wait_for(search_vacancies(params), timeout=60.0)
        logger.info(f"[{request.state.request_id}] Search: query='{query}', found={total}")
        return {
            "vacancies": [v.model_dump() for v in vacancies],
            "total": total,
            "page": page,
            "per_page": per_page,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[{getattr(request.state, 'request_id', '?')}] Search failed: {e}")
        raise HTTPException(status_code=500, detail="Search service temporarily unavailable")


@app.post("/api/upload")
@limiter.limit(RATE_LIMITS["upload"])
async def api_upload(request: Request, file: UploadFile = File(...)):
    try:
        import pathlib
        ext = pathlib.Path(file.filename or "").suffix.lower()
        if ext not in {".csv", ".json"}:
            raise HTTPException(status_code=400, detail=f"Unsupported file format: {ext}. Allowed: .csv, .json")

        content = await file.read()
        if len(content) > MAX_UPLOAD_SIZE:
            raise HTTPException(status_code=413, detail=f"File too large (max {MAX_UPLOAD_SIZE // 1024 // 1024}MB)")

        text = content.decode("utf-8", errors="replace").replace("\x00", "")
        vacancies = parse_uploaded_file(file.filename or "unknown", text)
        if not vacancies:
            raise HTTPException(status_code=400, detail="No valid vacancies found in file or invalid format")

        if len(vacancies) > MAX_VACANCIES_PER_SESSION:
            vacancies = vacancies[:MAX_VACANCIES_PER_SESSION]

        session_id = str(uuid.uuid4())
        await save_session(session_id, vacancies, time.time())
        await cleanup_expired_sessions()

        logger.info(f"[{request.state.request_id}] Upload: file={file.filename}, loaded={len(vacancies)}")
        return {
            "session_id": session_id,
            "loaded": len(vacancies),
            "vacancies": [v.model_dump() for v in vacancies[:5]],
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[{getattr(request.state, 'request_id', '?')}] Upload failed: {e}")
        raise HTTPException(status_code=500, detail="Upload processing failed")


@app.get("/api/vacancies")
@limiter.limit(RATE_LIMITS["default"])
async def api_vacancies(request: Request, session_id: str = Query(default=None)):
    session = await get_session(session_id) if session_id else None
    vacancies = session["vacancies"] if session else []
    return {
        "vacancies": [v.model_dump() for v in vacancies],
        "total": len(vacancies),
    }


@app.post("/api/analyze")
@limiter.limit(RATE_LIMITS["analyze"])
async def api_analyze(request: Request, criteria: CriteriaInput):
    try:
        vacancies_to_analyze = await get_all_session_vacancies()

        if not vacancies_to_analyze:
            params = SearchParams(
                query=criteria.direction or "стажировка junior",
                salary_from=criteria.min_salary,
            )
            vacancies_to_analyze, _ = await asyncio.wait_for(search_vacancies(params), timeout=20.0)

        if not vacancies_to_analyze:
            raise HTTPException(status_code=404, detail="No vacancies to analyze")

        results, metadata = await asyncio.wait_for(
            analyze_with_llm(vacancies_to_analyze[:ANALYSIS_MAX_VACANCIES], criteria),
            timeout=30.0,
        )
        criteria_text = build_criteria_text(criteria)

        report = generate_report(vacancies_to_analyze, results, criteria_text, analysis_type=metadata.analysis_type, overall_summary=metadata.overall_summary)

        valid_ids = {v.id for v in vacancies_to_analyze}
        enriched = []
        for r in results:
            if r.vacancy_id not in valid_ids:
                logger.warning(f"[{request.state.request_id}] LLM returned unknown vacancy_id: {r.vacancy_id}")
                continue
            v = next(x for x in vacancies_to_analyze if x.id == r.vacancy_id)
            enriched.append({
                **r.model_dump(),
                "vacancy": v.model_dump(),
            })

        logger.info(f"[{request.state.request_id}] Analyze: {len(enriched)} results, type={metadata.analysis_type}, iterations={metadata.iterations_used}")
        return {
            "results": enriched,
            "report": report,
            "analysis_type": metadata.analysis_type,
            "iterations_used": metadata.iterations_used,
            "total_vacancies_pool": metadata.total_vacancies_pool,
            "overall_summary": metadata.overall_summary,
            "plan_goal": metadata.plan_goal,
            "plan_steps_count": metadata.plan_steps_count,
            "reflections_count": metadata.reflections_count,
            "total_searches": metadata.total_searches,
            "total_new_vacancies": metadata.total_new_vacancies,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[{getattr(request.state, 'request_id', '?')}] Analyze failed: {e}")
        raise HTTPException(status_code=500, detail="AI analysis failed")


@app.get("/api/report")
@limiter.limit(RATE_LIMITS["default"])
async def api_report(request: Request):
    try:
        all_vacancies = await get_all_session_vacancies()

        if not all_vacancies:
            return PlainTextResponse("No data. Upload vacancies or run search first.", status_code=404)
        criteria = CriteriaInput()
        results, metadata = await analyze_with_llm(all_vacancies[:ANALYSIS_MAX_VACANCIES], criteria)
        report = generate_report(all_vacancies, results, analysis_type=metadata.analysis_type, overall_summary=metadata.overall_summary)
        logger.info(f"[{request.state.request_id}] Report generated: {len(all_vacancies)} vacancies, type={metadata.analysis_type}")
        return PlainTextResponse(report, media_type="text/markdown")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[{getattr(request.state, 'request_id', '?')}] Report failed: {e}")
        raise HTTPException(status_code=500, detail="Report generation failed")


def _get_chat_id(request: Request) -> int:
    user = getattr(request.state, "telegram_user", None)
    if user and "user" in user:
        try:
            return int(user["user"].split(",")[0]) if isinstance(user["user"], str) else int(user["id"])
        except (ValueError, KeyError, TypeError):
            pass
    client_host = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "unknown")
    dev_hash = hashlib.sha256(f"{client_host}:{user_agent}".encode()).hexdigest()[:8]
    return int(dev_hash, 16) % 1000000 + 9000000


@app.post("/api/favorites")
@limiter.limit(RATE_LIMITS["default"])
async def api_add_favorite(request: Request, fav: Favorite):
    try:
        chat_id = _get_chat_id(request)
        fav.chat_id = chat_id
        await add_favorite(fav)
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"[{getattr(request.state, 'request_id', '?')}] Add favorite failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to add favorite")


@app.delete("/api/favorites/{vacancy_id}")
@limiter.limit(RATE_LIMITS["default"])
async def api_remove_favorite(request: Request, vacancy_id: str):
    try:
        chat_id = _get_chat_id(request)
        await remove_favorite(chat_id, vacancy_id)
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"[{getattr(request.state, 'request_id', '?')}] Remove favorite failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to remove favorite")


@app.get("/api/favorites")
@limiter.limit(RATE_LIMITS["default"])
async def api_get_favorites(request: Request):
    try:
        chat_id = _get_chat_id(request)
        favs = await get_favorites(chat_id)
        return {"favorites": [f.model_dump() for f in favs]}
    except Exception as e:
        logger.error(f"[{getattr(request.state, 'request_id', '?')}] Get favorites failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to load favorites")


@app.post("/api/subscribe")
@limiter.limit(RATE_LIMITS["default"])
async def api_subscribe(request: Request, sub: Subscription):
    try:
        chat_id = _get_chat_id(request)
        if sub.chat_id and sub.chat_id != chat_id:
            raise HTTPException(status_code=403, detail="chat_id mismatch with authenticated user")
        sub.chat_id = chat_id
        sub_id = await add_subscription(sub)
        return {"id": sub_id, "status": "ok"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[{getattr(request.state, 'request_id', '?')}] Subscribe failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to create subscription")


@app.delete("/api/subscribe/{sub_id}")
@limiter.limit(RATE_LIMITS["default"])
async def api_unsubscribe(request: Request, sub_id: int):
    try:
        chat_id = _get_chat_id(request)
        await remove_subscription(chat_id, sub_id)
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"[{getattr(request.state, 'request_id', '?')}] Unsubscribe failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete subscription")


@app.get("/api/subscriptions")
@limiter.limit(RATE_LIMITS["default"])
async def api_get_subscriptions(request: Request):
    try:
        chat_id = _get_chat_id(request)
        subs = await get_active_subscriptions(chat_id)
        return {"subscriptions": [s.model_dump() for s in subs]}
    except Exception as e:
        logger.error(f"[{getattr(request.state, 'request_id', '?')}] Get subscriptions failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to load subscriptions")


@app.post("/api/check-notifications")
@limiter.limit(RATE_LIMITS["default"])
async def api_check_notifications(request: Request):
    try:
        count = await _check_subscriptions()
        return {"checked": count}
    except Exception as e:
        logger.error(f"[{getattr(request.state, 'request_id', '?')}] Check notifications failed: {e}")
        raise HTTPException(status_code=500, detail="Notification check failed")


@app.get("/api/areas")
@limiter.limit(RATE_LIMITS["default"])
async def api_areas(request: Request, q: str = Query(default="", max_length=100)):
    try:
        if not q:
            return {"areas": []}
        results = await get_area_suggestions(q)
        return {"areas": results}
    except Exception as e:
        logger.error(f"[{getattr(request.state, 'request_id', '?')}] Areas search failed: {e}")
        raise HTTPException(status_code=500, detail="Area search failed")


@app.get("/api/roles")
@limiter.limit(RATE_LIMITS["default"])
async def api_roles(request: Request, q: str = Query(default="", max_length=100)):
    try:
        if not q:
            return {"roles": []}
        results = await get_role_suggestions(q)
        return {"roles": results}
    except Exception as e:
        logger.error(f"[{getattr(request.state, 'request_id', '?')}] Roles search failed: {e}")
        raise HTTPException(status_code=500, detail="Role search failed")


@app.get("/api/health/live")
async def api_health_live():
    return {"status": "ok"}


@app.get("/api/health/ready")
async def api_health_ready():
    checks = {}
    status = "ok"

    try:
        import aiosqlite
        async with aiosqlite.connect(DB_PATH, timeout=2) as db:
            await asyncio.wait_for(db.execute("SELECT 1"), timeout=2)
        checks["database"] = "ok"
    except Exception:
        checks["database"] = "error: database unavailable"
        status = "degraded"

    checks["hh_circuit"] = hh_breaker.get_state()
    checks["groq_circuit"] = groq_breaker.get_state()

    if GROQ_API_KEY:
        checks["llm"] = groq_breaker.get_state()
    else:
        checks["llm"] = "skipped: no GROQ_API_KEY"

    try:
        free_gb = shutil.disk_usage(DB_PATH.parent).free / 1e9
        if free_gb < 0.5:
            status = "degraded"
    except Exception:
        pass

    return {"status": status, "checks": checks}


@app.get("/api/health")
async def api_health():
    return await api_health_ready()


@app.get("/api/export")
@limiter.limit(RATE_LIMITS["default"])
async def api_export(request: Request, format: str = Query(default="json")):
    try:
        all_vacancies = await get_all_session_vacancies()
        if not all_vacancies:
            raise HTTPException(status_code=404, detail="No data to export")

        criteria = CriteriaInput()
        results, _metadata = await analyze_with_llm(all_vacancies[:ANALYSIS_MAX_VACANCIES], criteria)

        if format == "csv":
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(["id", "title", "company", "city", "salary", "schedule", "experience", "fit_score", "why_fits", "concerns", "url"])
            for r in results:
                v = next((x for x in all_vacancies if x.id == r.vacancy_id), None)
                writer.writerow([
                    r.vacancy_id,
                    _csv_safe(v.title) if v else "",
                    _csv_safe(v.company) if v else "",
                    _csv_safe(v.city) if v else "",
                    _csv_safe(v.salary) if v else "",
                    _csv_safe(v.schedule) if v else "",
                    _csv_safe(v.experience) if v else "",
                    r.fit_score,
                    _csv_safe(r.why_fits),
                    _csv_safe(r.concerns),
                    v.url if v else "",
                ])
            return StreamingResponse(
                iter([output.getvalue()]),
                media_type="text/csv",
                headers={"Content-Disposition": "attachment; filename=vacancy-export.csv"},
            )

        data = {
            "vacancies": [v.model_dump() for v in all_vacancies],
            "results": [r.model_dump() for r in results],
            "exported_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        return JSONResponse(content=data)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Export failed: {e}")
        raise HTTPException(status_code=500, detail="Export failed")


@app.get("/api/agent/traces")
@limiter.limit(RATE_LIMITS["default"])
async def api_get_traces(request: Request, limit: int = Query(default=10, ge=1, le=50)):
    try:
        chat_id = _get_chat_id(request)
        user_key = str(chat_id)
        from database import get_agent_traces
        traces = await get_agent_traces(user_key, limit=limit)
        return {"traces": traces}
    except Exception as e:
        logger.error(f"Get traces failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to load traces")


@app.get("/api/agent/traces/{trace_id}")
@limiter.limit(RATE_LIMITS["default"])
async def api_get_trace(request: Request, trace_id: str):
    try:
        from database import get_agent_trace
        trace = await get_agent_trace(trace_id)
        if not trace:
            raise HTTPException(status_code=404, detail="Trace not found")
        return trace
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get trace failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to load trace")
