import asyncio
import json

import numpy as np
from agents import Agent, Runner
from agents.voice import AudioInput
from agents.voice.pipeline_config import VoicePipelineConfig
from pydub import AudioSegment

from runner.tools import TOOLS, reset_state

AGENT_INSTRUCTIONS = """You are a customer support voice agent for a food delivery app in Singapore.
Help users with orders, cancellations, and refunds.

Rules:
- Keep responses SHORT — this is a voice interface, 1-2 sentences max.
- If the user refers to an order ambiguously (e.g. "my order" when they have multiple), call list_orders first and ask which one. Never guess an order ID.
- If the user changes their mind mid-sentence ("wait no", "actually", "never mind"), act on the FINAL intent only. Do not execute the abandoned action.
- If the request is outside food delivery (weather, ride-hailing, other apps), politely say it's out of scope.
- If the user seems very frustrated or the issue needs human help (payment disputes, lost delivery), escalate.
"""


def build_agent() -> Agent:
    return Agent(
        name="SG Customer Support",
        instructions=AGENT_INSTRUCTIONS,
        tools=TOOLS,
        model="gpt-4o",
    )


async def run_case(audio_path: str) -> dict:
    reset_state()  # fresh seed for each case

    # --- 1. Load & normalise audio ---
    seg = (AudioSegment.from_file(audio_path)
           .set_frame_rate(24000)
           .set_channels(1))
    samples = np.array(seg.get_array_of_samples(), dtype=np.int16)
    audio_input = AudioInput(buffer=samples)

    # --- 2. STT: transcribe audio to text ---
    config = VoicePipelineConfig()
    stt_model = config.model_provider.get_stt_model(None)
    transcript = await stt_model.transcribe(
        audio_input,
        config.stt_settings,
        trace_include_sensitive_data=True,
        trace_include_sensitive_audio_data=False,   # avoids base64 tracing errors
    )

    # --- 3. Run agent with transcript, collecting tool calls & response text ---
    agent = build_agent()
    stream = Runner.run_streamed(agent, transcript)

    # call_id -> {name, args} for pairing tool_called with tool_output
    pending: dict[str, dict] = {}
    tool_calls: list[dict] = []
    response_text = ""
    raw_events: list[str] = []

    async for event in stream.stream_events():
        raw_events.append(event.type)

        if event.type == "run_item_stream_event":
            item = event.item

            if event.name == "tool_called":
                raw = item.raw_item
                name = item.tool_name
                args_str = (
                    raw.get("arguments") if isinstance(raw, dict)
                    else getattr(raw, "arguments", "{}")
                ) or "{}"
                try:
                    args = json.loads(args_str)
                except Exception:
                    args = {"raw": args_str}
                call_id = item.call_id
                if call_id:
                    pending[call_id] = {"name": name, "args": args}

            elif event.name == "tool_output":
                call_id = item.call_id
                if call_id and call_id in pending:
                    entry = pending.pop(call_id)
                    tool_calls.append({
                        "name": entry["name"],
                        "args": entry["args"],
                        "result": item.output,
                    })

        elif event.type == "raw_response_event":
            if getattr(event.data, "type", None) == "response.output_text.delta":
                response_text += event.data.delta

    return {
        "transcript": transcript,
        "tool_calls": tool_calls,
        "response_text": response_text,
        "audio_output_bytes": 0,   # no TTS in benchmark mode
        "raw_events": raw_events,
    }
