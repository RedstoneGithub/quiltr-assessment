import os
import re

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from openai import AsyncOpenAI

import dotenv
dotenv.load_dotenv()

EMAIL_RE = re.compile(
    r"(?<![A-Z0-9._%+-])[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b",
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

primary_server = os.getenv(
    "PRIMARY_LLM_URL"
)

app = FastAPI()
client = AsyncOpenAI(
    base_url=primary_server,
    api_key=os.environ.get("OPENAI_API_KEY")
)


class Redactor:
    bufferSize = 512
    safeSuffixSize = 254

    def __init__(self):
        self.buffer = ""
        self.bufferNumeric = False

    def redactBuffer(self):
        output = self.redactText(self.buffer)

        self.buffer = ""
        self.bufferNumeric = False
        return output

    def redactText(self, text: str):
        email = EMAIL_RE.sub("[REDACTED]", text)
        card = CARD_RE.sub("[REDACTED]", email)
        ssn = SSN_RE.sub("[REDACTED]", card)
        return ssn

    def drainBuffer(self):
        if len(self.buffer) <= self.bufferSize:
            return ""

        outputLength = len(self.buffer) - self.safeSuffixSize

        for pattern in (EMAIL_RE, CARD_RE, SSN_RE):
            for match in pattern.finditer(self.buffer):
                if match.start() < outputLength < match.end():
                    outputLength = match.start()

        if outputLength == 0:
            return self.redactBuffer()

        output = self.redactText(self.buffer[:outputLength])
        self.buffer = self.buffer[outputLength:]
        return output

    def redact(self, text: str):
        output = ""

        for char in text:
            if not self.buffer:
                self.bufferNumeric = char.isdecimal()

            if self.bufferNumeric:
                if char.isdecimal() or char == " " or char == "-":
                    self.buffer += char
                elif char.isalnum() or char in "._%+@":
                    if " " not in self.buffer:
                        self.buffer += char
                        self.bufferNumeric = False
                    else:
                        output += self.redactBuffer()
                        self.buffer = char
                        self.bufferNumeric = char.isdecimal()
                else:
                    output += self.redactBuffer()

                    if char.isalnum() or char in "._%+@-":
                        self.buffer = char
                        self.bufferNumeric = char.isdecimal()
                    else:
                        output += char
            else:
                if char.isalnum() or char in "._%+@-":
                    self.buffer += char
                else:
                    output += self.redactBuffer()
                    output += char

            output += self.drainBuffer()

        return output

    def finish(self):
        return self.redactBuffer()


@app.post("/generate")
async def generateResponse(request: str):
    async def generateStream():
        redactor = Redactor()

        stream = await client.responses.create(
            model="qwen/qwen3.8-flash",
            input=request,
            stream=True
        )

        async for event in stream:
            if event.type == "response.output_text.delta":
                output = redactor.redact(event.delta)
                if output:
                    yield output

        output = redactor.finish()
        if output:
            yield output

    return StreamingResponse(generateStream(), media_type="text/plain")
