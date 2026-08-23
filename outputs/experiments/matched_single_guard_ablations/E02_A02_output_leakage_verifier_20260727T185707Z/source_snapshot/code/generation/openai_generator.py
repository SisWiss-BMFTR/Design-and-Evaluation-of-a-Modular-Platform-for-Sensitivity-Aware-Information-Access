import os
import time
from typing import Dict, List, Optional

from openai import APIConnectionError, APITimeoutError, InternalServerError, OpenAI, RateLimitError

from generation.base import BaseGenerator


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


class OpenAIGenerator(BaseGenerator):
    def __init__(
        self,
        model_name: str,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        endpoint = base_url or os.getenv("OPENAI_BASE_URL")
        key = api_key or os.getenv("OPENAI_API_KEY") or ("EMPTY" if endpoint else None)
        if not key:
            raise ValueError(
                "Missing OpenAI API key. Set OPENAI_API_KEY in your environment "
                "or set OPENAI_BASE_URL for a local OpenAI-compatible endpoint."
            )
        self.client = OpenAI(api_key=key, base_url=endpoint) if endpoint else OpenAI(api_key=key)
        self.model = model_name
        self.temperature = float(os.getenv("GENERATION_TEMPERATURE", "0.0"))
        self.extra_body = self._build_extra_body(model_name, bool(endpoint))
        self.last_messages: List[Dict[str, str]] = []
        self.last_request_settings: Dict = {}

    def _build_extra_body(self, model_name: str, has_custom_endpoint: bool) -> Optional[Dict]:
        is_qwen = "qwen" in model_name.casefold()
        has_qwen_override = os.getenv("QWEN_ENABLE_THINKING") is not None
        if not is_qwen or not (has_custom_endpoint or has_qwen_override):
            return None

        return {
            "chat_template_kwargs": {
                "enable_thinking": _env_bool("QWEN_ENABLE_THINKING", False),
            }
        }

    def _create_chat_completion(self, messages: List[Dict[str, str]]):
        request = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
        }
        if self.extra_body:
            request["extra_body"] = self.extra_body
        self.last_messages = [dict(message) for message in messages]
        self.last_request_settings = {
            key: value for key, value in request.items() if key != "messages"
        }
        max_retries = int(os.getenv("OPENAI_MAX_RETRIES", "8"))
        base_delay = float(os.getenv("OPENAI_RETRY_BASE_SECONDS", "1.0"))
        max_delay = float(os.getenv("OPENAI_RETRY_MAX_SECONDS", "30.0"))

        for attempt in range(max_retries + 1):
            try:
                return self.client.chat.completions.create(**request)
            except (APIConnectionError, APITimeoutError, InternalServerError, RateLimitError):
                if attempt >= max_retries:
                    raise
                delay = min(max_delay, base_delay * (2 ** attempt))
                time.sleep(delay)

    def _build_prompt_sections(
        self,
        query: str,
        context_chunks: List[str],
        memory_summary: str,
        memory_snippets: Optional[List[str]],
    ) -> str:
        context = "\n\n".join(context_chunks) if context_chunks else "(no retrieved context)"

        snippets_block = ""
        if memory_snippets:
            snippets_block = "\n\nRelevant past conversation memories:\n" + "\n".join(
                f"- {snippet}" for snippet in memory_snippets
            )

        summary_block = ""
        if memory_summary.strip():
            summary_block = f"\n\nConversation summary so far:\n{memory_summary.strip()}"

        return (
            "Use retrieved context as your primary factual source. "
            "Use conversation memory only for continuity (references, preferences, previously discussed entities). "
            "Answer only for IDs/entities explicitly asked by the user or already active in this thread; do not add unrelated products. "
            "If context is missing, say so clearly instead of inventing facts. "
            "When retrieved context contains SENSITIVITY EVALUATION MODE, follow its access, availability, and disclosure rules: "
            "fields marked visibility=allowed are available for answering, while fields marked restricted_for_role must not be disclosed. "
            "If an authorized role has a retrieved linked formulation entity, use that formulation entity instead of saying formulation details are unavailable. "
            f"\n\nRetrieved context:\n{context}"
            f"{summary_block}"
            f"{snippets_block}"
            f"\n\nCurrent user question:\n{query}"
        )

    def generate(
        self,
        query: str,
        context_chunks: List[str],
        conversation_messages: Optional[List[Dict[str, str]]] = None,
        memory_summary: str = "",
        memory_snippets: Optional[List[str]] = None,
    ) -> str:
        messages: List[Dict[str, str]] = [
            {
                "role": "system",
                "content": (
                    "You are a helpful assistant in a retrieval-augmented chat system. "
                    "Maintain coherent multi-turn conversation while staying grounded in provided context."
                ),
            }
        ]

        if conversation_messages:
            messages.extend(conversation_messages)

        messages.append(
            {
                "role": "user",
                "content": self._build_prompt_sections(
                    query=query,
                    context_chunks=context_chunks,
                    memory_summary=memory_summary,
                    memory_snippets=memory_snippets,
                ),
            }
        )

        response = self._create_chat_completion(messages)
        return response.choices[0].message.content or ""

    def summarize_conversation(
        self,
        existing_summary: str,
        turns: List[Dict[str, str]],
    ) -> str:
        if not turns:
            return existing_summary

        turns_text = "\n".join(
            f"User: {turn.get('user', '')}\nAssistant: {turn.get('assistant', '')}" for turn in turns
        )

        response = self._create_chat_completion(
            [
                {
                    "role": "system",
                    "content": (
                        "You maintain a compact conversation memory for a RAG chatbot. "
                        "Keep stable facts, user goals, constraints, decisions, and unresolved questions. "
                        "Return concise plain text."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Existing summary:\n{existing_summary or '(empty)'}\n\n"
                        f"New turns:\n{turns_text}\n\n"
                        "Update the summary so future turns stay coherent."
                    ),
                },
            ]
        )
        return (response.choices[0].message.content or "").strip()
