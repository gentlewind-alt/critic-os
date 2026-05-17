# app/services/hf_client.py

import os
import logging
import requests
import time
from typing import Generator

logger = logging.getLogger(__name__)

# ==========================
# HF SPACE SETUP (Qwen 7B T4)
# ==========================
# Using the OpenAI-compatible endpoint of the new Space
HF_SPACE_URL = os.getenv("HF_SPACE_URL", "https://mikeee-qwen-7b-chat.hf.space/v1/chat/completions")

def call_hf_space(prompt: str, max_tokens: int = 150, retries: int = 2) -> str:
    """Helper to call the Hugging Face Space API with retries (OpenAI compatible)."""
    
    for attempt in range(retries + 1):
        start_time = time.time()
        try:
            response = requests.post(
                HF_SPACE_URL,
                json={
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": max_tokens,
                    "temperature": 0.7,
                    "top_p": 0.9,
                    "stream": False # We can potentially switch to True later for real streaming
                },
                timeout=180 # 3 minutes (T4 is faster, so 3 mins is plenty)
            )
            response.raise_for_status()
            data = response.json()
            
            # OpenAI format: choices[0].message.content
            message = data.get("choices", [{}])[0].get("message", {})
            content = message.get("content", "").strip()
            reasoning = message.get("reasoning_content", "").strip()
            
            # If content is empty but reasoning has content, use reasoning as a fallback
            # (Some models put everything in reasoning if they are interrupted or misconfigured)
            generated = content if content else reasoning
            
            duration = time.time() - start_time
            if generated:
                logger.info(f"Qwen Space Inference successful (Attempt {attempt+1}) in {duration:.2f}s. Content length: {len(generated)}")
            else:
                logger.warning(f"Qwen Space returned empty content and reasoning. Full message: {message}")

            return generated.strip()

        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            duration = time.time() - start_time
            logger.warning(f"Qwen Space Attempt {attempt+1} failed ({duration:.2f}s): {e}")
            if attempt < retries:
                wait_time = (attempt + 1) * 2
                logger.info(f"Retrying in {wait_time}s...")
                time.sleep(wait_time)
            else:
                logger.error("All Qwen Space retries exhausted.")
        except Exception as e:
            logger.error(f"Unexpected Qwen Space Error: {e}")
            break
            
    return ""

def fake_stream(text: str) -> Generator[str, None, None]:
    """Helper to simulate streaming for non-streaming APIs."""
    if not text:
        return
    words = text.split(" ")
    for i, word in enumerate(words):
        yield word + (" " if i < len(words) - 1 else "")
        time.sleep(0.01)
