from __future__ import annotations

import os

from pydantic import BaseModel


class GenaiModelClient:
    """Real structured-generation client backed by the google-genai SDK (Gemini).

    Lazily imports google-genai so Tier-0 installs need not pull the GCP stack. Works against
    either Vertex AI (the user's own project) or the AI Studio Gemini API, chosen by config/env:
      - Vertex:    project (+ location) set, or GOOGLE_GENAI_USE_VERTEXAI=true
      - AI Studio: GEMINI_API_KEY / GOOGLE_API_KEY
    """

    def __init__(
        self,
        *,
        vertexai: bool | None = None,
        project: str | None = None,
        location: str | None = None,
        api_key: str | None = None,
    ) -> None:
        from google import genai  # requires the [gcp] extra

        use_vertex = vertexai
        if use_vertex is None:
            env = os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "").lower() in ("1", "true", "yes")
            use_vertex = bool(project) or env
        if use_vertex:
            self._client = genai.Client(
                vertexai=True,
                project=project or os.getenv("GOOGLE_CLOUD_PROJECT"),
                location=location or os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1"),
            )
        else:
            self._client = genai.Client(
                api_key=api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
            )

    def generate_structured(
        self, *, prompt: str, schema: type[BaseModel], model: str
    ) -> BaseModel:
        resp = self._client.models.generate_content(
            model=model,
            contents=prompt,
            config={
                "response_mime_type": "application/json",
                "response_schema": schema,
            },
        )
        parsed = getattr(resp, "parsed", None)
        if parsed is not None:
            return parsed
        return schema.model_validate_json(resp.text)
