"""
Unified LLM Client — uses Google Gemini API (FREE tier).
Free tier: 15 requests/minute, 1,500 requests/day, 1M tokens/min.
"""

from typing import Optional
from loguru import logger

from config import settings


class LLMClient:
    """Google Gemini API client (100% free)."""

    def __init__(self):
        self._model = None
        self._init_client()

    def _init_client(self):
        """Initialize the Gemini API client."""
        if not settings.gemini_api_key:
            logger.warning(
                "No GEMINI_API_KEY set. AI features disabled. "
                "Get a FREE key at: https://aistudio.google.com/app/apikey"
            )
            return

        try:
            import google.generativeai as genai

            genai.configure(api_key=settings.gemini_api_key)
            # Use a verified model from the list: gemini-2.0-flash or gemini-flash-latest
            self._model = genai.GenerativeModel("gemini-2.0-flash")
            logger.info("✅ Gemini API initialized (FREE tier — gemini-2.0-flash)")
        except ImportError:
            logger.error("google-generativeai package not installed. Run: pip install google-generativeai")
        except Exception as e:
            logger.error(f"Gemini initialization failed: {e}")

    async def generate(self, prompt: str, system_prompt: str = None,
                       max_tokens: int = 2000, temperature: float = 0.7) -> str:
        """Generate text using Gemini (free)."""
        if not self._model:
            raise RuntimeError(
                "Gemini not initialized. Set GEMINI_API_KEY in .env. "
                "Get free key: https://aistudio.google.com/app/apikey"
            )

        # Combine system prompt and user prompt
        full_prompt = prompt
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n---\n\n{prompt}"

        try:
            import google.generativeai as genai

            generation_config = genai.GenerationConfig(
                max_output_tokens=max_tokens,
                temperature=temperature,
            )

            response = self._model.generate_content(
                full_prompt,
                generation_config=generation_config,
            )

            return response.text

        except Exception as e:
            # Handle rate limiting gracefully
            if "429" in str(e) or "quota" in str(e).lower():
                logger.warning("Gemini rate limit hit (15 req/min free tier). Waiting 60s...")
                import asyncio
                await asyncio.sleep(60)
                # Retry once
                try:
                    response = self._model.generate_content(
                        full_prompt,
                        generation_config=generation_config,
                    )
                    return response.text
                except Exception as retry_err:
                    logger.error(f"Gemini retry failed: {retry_err}")
                    raise

            logger.error(f"Gemini generation error: {e}")
            raise

    def generate_sync(self, prompt: str, system_prompt: str = None,
                      max_tokens: int = 2000, temperature: float = 0.7) -> str:
        """Synchronous version for non-async contexts."""
        if not self._model:
            raise RuntimeError("Gemini not initialized. Set GEMINI_API_KEY.")

        import google.generativeai as genai

        full_prompt = prompt
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n---\n\n{prompt}"

        generation_config = genai.GenerationConfig(
            max_output_tokens=max_tokens,
            temperature=temperature,
        )

        response = self._model.generate_content(
            full_prompt,
            generation_config=generation_config,
        )
        return response.text

    @property
    def is_available(self) -> bool:
        """Check if Gemini client is ready."""
        return self._model is not None
