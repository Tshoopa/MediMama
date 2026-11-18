"""Answer generation adapter for local MedGemma and OpenAI API modes."""

from __future__ import annotations

import logging
import threading
from typing import Any

from backend.config import settings
from backend.openai_client import get_openai_client

log = logging.getLogger("medimama.llm")
_model_lock = threading.Lock()
_local_model = None
_local_tokenizer = None
_local_load_error: str | None = None

SYSTEM_PROMPT = """You are MediMama, a cautious, warm pediatric health information assistant.
Answer the parent's question briefly, using only the supplied medical evidence.
Do not invent diagnoses, doses, or facts. Do not change the urgency level supplied
by the deterministic triage engine. If evidence is insufficient, say so and advise
appropriate professional care. Use plain language and no more than four sentences.
You are not a substitute for a qualified clinician or emergency services."""



def _load_local_model() -> tuple[Any, Any]:
    global _local_model, _local_tokenizer, _local_load_error

    if _local_model is not None and _local_tokenizer is not None:
        return _local_model, _local_tokenizer

    if _local_load_error:
        raise RuntimeError(_local_load_error)

    with _model_lock:
        if _local_model is not None and _local_tokenizer is not None:
            return _local_model, _local_tokenizer

        try:
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer

            model_id = settings.local_model_id
            token = settings.hf_token.strip() or None
            cache_dir = settings.local_model_cache_dir

            if torch.cuda.is_available():
                if settings.local_model_dtype == "float32":
                    dtype = torch.float32
                elif settings.local_model_dtype == "bfloat16":
                    dtype = torch.bfloat16
                else:
                    dtype = torch.float16
            else:
                dtype = torch.float32

            log.info("Loading local model: %s", model_id)

            tokenizer = AutoTokenizer.from_pretrained(
                model_id,
                token=token,
                cache_dir=cache_dir,
            )

            if tokenizer.pad_token_id is None:
                tokenizer.pad_token = tokenizer.eos_token

            model = AutoModelForCausalLM.from_pretrained(
                model_id,
                token=token,
                cache_dir=cache_dir,
                torch_dtype=dtype,
                device_map=settings.local_device_map,
                low_cpu_mem_usage=True,
            )

            model.eval()

            _local_model = model
            _local_tokenizer = tokenizer

            log.info("Local model loaded successfully: %s", model_id)

            return _local_model, _local_tokenizer

        except Exception as exc:
            _local_load_error = (
                f"Could not load local model {settings.local_model_id}: "
                f"{type(exc).__name__}: {exc}. "
                "Check internet access, available disk/RAM/VRAM, "
                "Transformers version >= 4.51, and Hugging Face connectivity."
            )

            log.exception("Local model loading failed")

            raise RuntimeError(_local_load_error) from exc


def initialize_generation_backend() -> None:
    """Eagerly load local weights at startup, but never load them in API mode."""
    if settings.inference_mode == "local":
        _load_local_model()
    else:
        log.info("Answer generation mode: OpenAI API (%s)", settings.openai_model)


def generation_backend_ready() -> bool:
    if settings.inference_mode == "api":
        return bool(settings.openai_api_key.strip())
    return _local_model is not None


def generation_backend_status() -> dict[str, Any]:
    if settings.inference_mode == "api":
        return {
            "mode": "api",
            "provider": "OpenAI",
            "model": settings.openai_model,
            "ready": bool(settings.openai_api_key.strip()),
            "local_model_loaded": False,
        }
    return {
        "mode": "local",
        "provider": "Hugging Face Transformers",
        "model": settings.local_model_id,
        "ready": _local_model is not None,
        "local_model_loaded": _local_model is not None,
        "load_error": _local_load_error,
    }


def _build_user_prompt(question: str, evidence_context: str) -> str:
    return (
        "Medical evidence (use only this evidence):\n"
        f"{evidence_context}\n\n"
        "Parent's question (translated to English):\n"
        f"{question}\n\n"
        "Give a concise, empathetic answer in plain English. Do not repeat the triage level."
    )


def _generate_openai(question: str, evidence_context: str) -> str:
    client = get_openai_client()
    response = client.responses.create(
        model=settings.openai_model,
        instructions=SYSTEM_PROMPT,
        input=_build_user_prompt(question, evidence_context),
        max_output_tokens=settings.local_max_new_tokens,
        temperature=0.1,
    )
    return (getattr(response, "output_text", "") or "").strip()



def generate_local_completion(
    instructions: str,
    input_text: str,
    max_new_tokens: int | None = None,
    temperature: float = 0.0,
) -> str:
    """
    Shared local completion function.

    Qwen3 is used for both:
    - Clinical translation
    - Grounded answer generation

    No OpenAI API is required in local mode.
    """

    model, tokenizer = _load_local_model()

    messages = [
        {
            "role": "system",
            "content": instructions,
        },
        {
            "role": "user",
            "content": input_text,
        },
    ]

    inputs = tokenizer.apply_chat_template(
        messages,
        add_generation_prompt=True,
        tokenize=True,
        return_dict=True,
        return_tensors="pt",
    )

    inputs = inputs.to(model.device)

    import torch

    generation_kwargs = {
        "max_new_tokens": int(
            max_new_tokens or settings.local_max_new_tokens
        ),
        "do_sample": float(temperature) > 0,
        "repetition_penalty": settings.local_repetition_penalty,
        "pad_token_id": tokenizer.eos_token_id,
    }

    if float(temperature) > 0:
        generation_kwargs["temperature"] = float(temperature)

    with _model_lock, torch.inference_mode():
        output_ids = model.generate(
            **inputs,
            **generation_kwargs,
        )

    input_length = inputs["input_ids"].shape[-1]

    new_tokens = output_ids[0][input_length:]

    return tokenizer.decode(
        new_tokens,
        skip_special_tokens=True,
    ).strip()

def _generate_local_model(question, evidence_context):
    return generate_local_completion(
        SYSTEM_PROMPT,
        _build_user_prompt(question, evidence_context),
        max_new_tokens=settings.local_max_new_tokens,
        temperature=settings.local_temperature,
    )


def generate_answer(question: str, evidence_context: str) -> str:
    if settings.inference_mode == "api":
        return _generate_openai(question, evidence_context)

    return _generate_local_model(question, evidence_context)
