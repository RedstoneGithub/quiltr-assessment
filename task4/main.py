import asyncio
import hashlib
import json
import os
import sqlite3
import sys
import time
import uuid
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, Header
from fastapi.responses import JSONResponse
import httpx

import dotenv
dotenv.load_dotenv()

API_KEY = os.getenv("OPENAI_API_KEY", "")
PRIMARY_API_KEY = os.getenv("PRIMARY_API_KEY", API_KEY)
BACKUP_API_KEY = os.getenv("BACKUP_API_KEY", API_KEY)

primary_server = os.getenv(
    "PRIMARY_LLM_URL",
    "https://openrouter.ai/api/v1/chat/completions"
) or "https://openrouter.ai/api/v1/chat/completions"
backup_server = os.getenv(
    "BACKUP_LLM_URL",
    "https://openrouter.ai/api/v1/chat/completions"
) or "https://openrouter.ai/api/v1/chat/completions"

primary_model = os.getenv("PRIMARY_MODEL", "qwen3.7-flash")
backup_model = os.getenv("BACKUP_MODEL", "qwen3.8-flash")

RATE_LIMIT = 1500 #50_000
WINDOW_SECONDS = 60
PRIMARY_TIMEOUT = 3.0
BACKUP_TIMEOUT = 10.0
DATABASE_PATH = os.getenv(
    "RATE_LIMIT_DATABASE",
    str(Path(__file__).with_name("db.sqlite3"))
)

app = FastAPI()
client = httpx.AsyncClient()


class RateLimiter:
    def __init__(self, databasePath: str, tokenLimit: int = RATE_LIMIT):
        self.databasePath = databasePath
        self.tokenLimit = tokenLimit
        self.initialized = False
        self.initializeLock = asyncio.Lock()

    def setupDatabase(self):
        with sqlite3.connect(self.databasePath) as database:
            database.execute("PRAGMA journal_mode=WAL")
            database.execute(
                """
                CREATE TABLE IF NOT EXISTS usage_events (
                    request_id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    tokens INTEGER NOT NULL
                )
                """
            )
            database.execute(
                """
                CREATE INDEX IF NOT EXISTS usage_events_tenant_time
                ON usage_events (tenant_id, created_at)
                """
            )

    async def initialize(self):
        if self.initialized:
            return

        async with self.initializeLock:
            if not self.initialized:
                await asyncio.to_thread(self.setupDatabase)
                self.initialized = True

    def reserveTokens(self, tenantId: str, requestId: str, tokens: int):
        now = time.time()
        windowStart = now - WINDOW_SECONDS
        database = sqlite3.connect(
            self.databasePath,
            timeout=5,
            isolation_level=None
        )

        try:
            database.execute("BEGIN IMMEDIATE")
            database.execute(
                "DELETE FROM usage_events WHERE created_at < ?",
                (windowStart,)
            )

            row = database.execute(
                """
                SELECT COALESCE(SUM(tokens), 0)
                FROM usage_events
                WHERE tenant_id = ? AND created_at >= ?
                """,
                (tenantId, windowStart)
            ).fetchone()
            usedTokens = row[0]

            #print("Used", usedTokens, "tokens +", tokens)

            if usedTokens + tokens > self.tokenLimit:
                database.rollback()
                return False

            database.execute(
                """
                INSERT INTO usage_events
                    (request_id, tenant_id, created_at, tokens)
                VALUES (?, ?, ?, ?)
                """,
                (requestId, tenantId, now, tokens)
            )
            database.commit()
            return True
        except Exception:
            database.rollback()
            raise
        finally:
            database.close()

    async def reserve(self, tenantId: str, requestId: str, tokens: int):
        await self.initialize()
        return await asyncio.to_thread(
            self.reserveTokens,
            tenantId,
            requestId,
            tokens
        )

    def updateTokens(self, requestId: str, tokens: int):
        with sqlite3.connect(self.databasePath) as database:
            database.execute(
                "UPDATE usage_events SET tokens = ? WHERE request_id = ?",
                (tokens, requestId)
            )

    async def update(self, requestId: str, tokens: int):
        await asyncio.to_thread(self.updateTokens, requestId, tokens)


rateLimiter = RateLimiter(DATABASE_PATH)


def countTokens(text: str):
    return max(1, (len(text.encode("utf-8")) + 3) // 4)


def getTenantId(apiKey: str):
    return hashlib.sha256(apiKey.encode("utf-8")).hexdigest()


def createGatewayError(statusCode: int, code: str, message: str, requestId: str):
    return JSONResponse(
        status_code=statusCode,
        content={
            "error": {
                "code": code,
                "message": message,
                "request_id": requestId
            }
        }
    )


async def callModel(server: str, apiKey: str, model: str, msg: str,
                    maxTokens: int, timeout: float):
    return await client.post(
        url=server,
        headers={
            "Authorization": "Bearer " + apiKey,
            "Content-Type": "application/json"
        },
        json={
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": msg
                }
            ],
            "max_tokens": maxTokens
        },
        timeout=timeout
    )


def getActualTokens(responseData: dict, msg: str):
    usage = responseData.get("usage")
    if isinstance(usage, dict):
        totalTokens = usage.get("total_tokens")
        if isinstance(totalTokens, int):
            return totalTokens

    try:
        output = responseData["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        output = ""

    return countTokens(msg) + countTokens(output)


@app.on_event("shutdown")
async def shutdown():
    await client.aclose()


@app.post("/generate")
async def generate(
    msg: str,
    max_tokens: int = 1000,
    x_api_key: Annotated[str | None, Header()] = None
):
    requestId = str(uuid.uuid4())

    if not x_api_key:
        return createGatewayError(
            401,
            "UNAUTHORIZED",
            "A tenant API key is required",
            requestId
        )

    if max_tokens < 1:
        return createGatewayError(
            400,
            "INVALID_REQUEST",
            "max_tokens must be greater than zero",
            requestId
        )

    tenantId = getTenantId(x_api_key)
    reservedTokens = countTokens(msg) + max_tokens

    try:
        allowed = await rateLimiter.reserve(
            tenantId,
            requestId,
            reservedTokens
        )
    except sqlite3.Error as error:
        print(f"Rate limiter database error: {error}", file=sys.stderr)
        return createGatewayError(
            503,
            "GATEWAY_UNAVAILABLE",
            "The gateway is temporarily unavailable",
            requestId
        )

    if not allowed:
        return createGatewayError(
            429,
            "RATE_LIMIT_EXCEEDED",
            "The tenant token limit has been exceeded",
            requestId
        )

    response = None
    useBackup = False

    try:
        response = await asyncio.wait_for(
            callModel(
                primary_server,
                PRIMARY_API_KEY,
                primary_model,
                msg,
                max_tokens,
                PRIMARY_TIMEOUT
            ),
            timeout=PRIMARY_TIMEOUT
        )
        useBackup = response.status_code == 429
    except (TimeoutError, httpx.TimeoutException) as error:
        print(f"Primary provider timed out: {error}", file=sys.stderr)
        useBackup = True
    except httpx.HTTPError as error:
        print(f"Primary provider HTTP error: {error}", file=sys.stderr)
        return createGatewayError(
            502,
            "UPSTREAM_UNAVAILABLE",
            "The generation service is temporarily unavailable",
            requestId
        )

    if useBackup:
        try:
            response = await callModel(
                backup_server,
                BACKUP_API_KEY,
                backup_model,
                msg,
                max_tokens,
                BACKUP_TIMEOUT
            )
        except (TimeoutError, httpx.HTTPError) as error:
            print(f"Backup provider HTTP error: {error}", file=sys.stderr)
            return createGatewayError(
                502,
                "UPSTREAM_UNAVAILABLE",
                "The generation service is temporarily unavailable",
                requestId
            )
    if not response.is_success:
        provider = "backup" if useBackup else "primary"
        print(
            f"{provider.capitalize()} provider returned HTTP "
            f"{response.status_code}",
            file=sys.stderr
        )
        return createGatewayError(
            502,
            "UPSTREAM_UNAVAILABLE",
            "The generation service is temporarily unavailable",
            requestId
        )

    try:
        responseData = response.json()
    except (json.JSONDecodeError, ValueError) as error:
        print(f"Invalid upstream JSON response: {error}", file=sys.stderr)
        return createGatewayError(
            502,
            "INVALID_UPSTREAM_RESPONSE",
            "The generation service returned an invalid response",
            requestId
        )

    actualTokens = getActualTokens(responseData, msg)
    try:
        await rateLimiter.update(requestId, actualTokens)
    except sqlite3.Error as error:
        print(f"Rate limiter database error: {error}", file=sys.stderr)
        return createGatewayError(
            503,
            "GATEWAY_UNAVAILABLE",
            "The gateway is temporarily unavailable",
            requestId
        )

    return JSONResponse(content=responseData)
