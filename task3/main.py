import os

import re
from fastapi import FastAPI
from openai import AsyncOpenAI
from openai.types.responses import ResponseTextDeltaEvent

import dotenv
dotenv.load_dotenv()

EMAIL_RE = re.compile(
    r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b",
    re.IGNORECASE,
)

SSN_RE = re.compile(
    r"(?<!\d)"
    r"(?!000|666|9\d{2})\d{3}[- ]?"
    r"(?!00)\d{2}[- ]?"
    r"(?!0000)\d{4}"
    r"(?!\d)"
)

CARD_RE = re.compile(
    r"(?<!\d)(?:\d[ -]?){12,18}\d(?!\d)"
)

app = FastAPI()
client = AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key = os.environ.get("OPENAI_API_KEY")
)

bufferSize = 20

def redact(buffer):
    buffer = EMAIL_RE.sub("[REDACTED]", buffer)
    buffer = CARD_RE.sub("[REDACTED]", buffer)
    buffer = SSN_RE.sub("[REDACTED]", buffer)
    return buffer



@app.post("/generate")
async def generateResponse(request: str):

    stream = await client.responses.create(
        model="qwen3.8-flash",
        input=request,
        stream=True
    )

    buffer = ""
    final = ""
    async for event in stream:

        if event.type == "response.output_text.delta":
            delta = event.delta
            buffer += delta
            if len(buffer) > bufferSize:
                final += redact(buffer)
                print(final)
                buffer = ""
    print()

    return final