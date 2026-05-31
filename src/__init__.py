import os

from dotenv import load_dotenv
load_dotenv()
from .users.UserRoutes import user_router
from .messages.MessageRoutes import message_router
# from .conversations.ConversationRoutes import conversation_router
from .posts.PostRoutes import post_router
from .story.StoryRoutes import story_router
from .notifications.NotificationRoutes import notification_router
#from .groups.GroupRoutes import group_router
from contextlib import asynccontextmanager
from fastapi import FastAPI
from .db.main import initdb
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from slowapi.errors import RateLimitExceeded

from .middleware.logging import logging_middleware
from .middleware.profiling import profiling_middleware, get_stats
from .middleware.rate_limit import limiter, rate_limit_exceeded_handler

@asynccontextmanager
async def lifespan(app: FastAPI):
    await initdb()
    yield
    print("server is stopping")

version = 'v1'

app = FastAPI(
    title="Instagramm",
    description="A REST API for a Instagram clone",
    version= version,
    lifespan=lifespan
)
from fastapi.responses import HTMLResponse

@app.get("/api/v1/stats", response_class=HTMLResponse, tags=["monitoring"])
async def request_stats():
    
    stats = get_stats()

    grouped = {"GET": [], "POST": [], "PATCH": [], "DELETE": [], "OTHER": []}
    for endpoint, data in stats.items():
        m = data["method"]
        row = {"endpoint": endpoint, **data}
        grouped.get(m, grouped["OTHER"]).append(row)

    for m in grouped:
        grouped[m].sort(key=lambda x: x["avg_ms"], reverse=True)

    def make_table(rows, color):
        if not rows:
            return "<p style='color:#888'>No data</p>"
        html = f"<table><thead><tr><th>Endpoint</th><th>Calls</th><th>Avg ms</th><th>Min ms</th><th>Max ms</th><th>Errors</th><th>Error Rate</th></tr></thead><tbody>"
        for r in rows:
            slow = "slow" if r["avg_ms"] > 500 else ""
            html += f"<tr class='{slow}'><td>{r['endpoint']}</td><td>{r['count']}</td><td>{r['avg_ms']}</td><td>{r['min_ms']}</td><td>{r['max_ms']}</td><td>{r['errors']}</td><td>{r['error_rate']}</td></tr>"
        html += "</tbody></table>"
        return html

    method_colors = {"GET": "#4CAF50", "POST": "#2196F3", "PATCH": "#FF9800", "DELETE": "#f44336", "OTHER": "#9C27B0"}

    sections = ""
    for method, rows in grouped.items():
        if rows:
            sections += f"""
            <div class="section">
                <h2 style="color:{method_colors[method]}">{method} <span class="badge">{len(rows)} endpoints</span></h2>
                {make_table(rows, method_colors[method])}
            </div>"""

    return f"""
    <!DOCTYPE html><html><head>
    <title>API Stats</title>
    <meta http-equiv="refresh" content="5">
    <style>
        body {{ font-family: monospace; background: #0d1117; color: #c9d1d9; padding: 2rem; }}
        h1 {{ color: #58a6ff; }}
        h2 {{ margin-top: 2rem; }}
        .badge {{ background: #21262d; padding: 2px 8px; border-radius: 12px; font-size: 0.8rem; color:#8b949e; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 0.5rem; }}
        th {{ background: #161b22; padding: 8px 12px; text-align: left; color: #8b949e; font-size: 0.85rem; }}
        td {{ padding: 8px 12px; border-bottom: 1px solid #21262d; }}
        tr:hover td {{ background: #161b22; }}
        tr.slow td {{ color: #f0883e; }}
        tr.slow td:first-child::after {{ content: ' '; }}
        .section {{ margin-bottom: 2rem; }}
        .note {{ color: #8b949e; font-size: 0.8rem; margin-top: 0.5rem; }}
    </style>
    </head><body>
    <h1>API Request Statistics</h1>
    <p class="note">Rows in orange = avg response time &gt; 500ms | Auto-refreshes every 5s</p>
    {sections}
    </body></html>
    """
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],      
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["*"] 
)

app.add_middleware(BaseHTTPMiddleware, dispatch=logging_middleware)

app.add_middleware(BaseHTTPMiddleware, dispatch=profiling_middleware)

app.state.limiter = limiter

app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

app.include_router(user_router, prefix=f"/api/{version}", tags=["users"])
app.include_router(post_router, prefix=f"/api/{version}", tags=["posts"])
app.include_router(message_router, prefix=f"/api/{version}", tags=["messages"])
app.include_router(story_router, prefix=f"/api/{version}", tags=["stories"])
app.include_router(notification_router, prefix=f"/api/{version}", tags=["notifications"])
