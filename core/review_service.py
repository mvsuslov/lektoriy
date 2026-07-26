"""Вызов DeepSeek API для методического анализа. Отдельный файл —
легко выпилить/заменить, не трогая views."""
import hashlib
import json
import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

CRITERIA = {
    "ooo": """Критерии ФГОС ООО (5–9 классы):
- наличие целей: предметные, метапредметные, личностные;
- универсальные учебные действия (УУД): познавательные, коммуникативные, регулятивные;
- планируемые результаты;
- системно-деятельностный подход (ученик действует, а не только слушает);
- этапы урока: организационный, актуализация, изучение нового, закрепление, рефлексия;
- воспитательный аспект.""",
    "soo": """Критерии ФГОС СОО (10–11 классы):
- цели: предметные, метапредметные, личностные;
- учёт профильности / углублённого уровня;
- проектная и исследовательская деятельность;
- конкретные планируемые результаты по предмету;
- этапы урока и рефлексия.""",
    "spo": """Критерии ФГОС СПО:
- общие (ОК) и профессиональные (ПК) компетенции;
- связь с профессиональным стандартом / трудовыми функциями;
- структура: цели, задачи, оснащение, ход занятия;
- практико-ориентированность;
- методы и формы контроля.""",
}

SYSTEM_PROMPT = """Ты — опытный методист-предметник. Проанализируй конспект/методическую разработку.
Ответь СТРОГО в формате JSON (без markdown, без пояснений вне JSON):
{
  "score": <целое 1-10>,
  "summary": "<рецензия 2-4 предложения>",
  "strengths": ["<сильная сторона>", ...],
  "weaknesses": ["<недочёт>", ...],
  "suggestions": ["<конкретное предложение с примером формулировки>", ...]
}
Правила:
- score: 9-10 отлично, 7-8 хорошо, 5-6 требует доработки, 1-4 серьёзные проблемы.
- suggestions — самое ценное: давай конкретные правки, а не общие слова.
- НЕ ссылайся на конкретные номера приказов и пунктов стандартов — можешь ошибиться.
- Отвечай по-русски."""


def make_hash(text: str) -> str:
    return hashlib.sha256(text.strip().lower().encode()).hexdigest()


def run_analysis(level: str, text: str) -> dict:
    """Синхронный вызов API. Возвращает dict с результатом.
    При ошибке бросает исключение — ловит вызывающий код (поток)."""
    if not settings.DEEPSEEK_API_KEY:
        raise RuntimeError("API-ключ DeepSeek не настроен")

    user_prompt = f"{CRITERIA[level]}\n\n=== ТЕКСТ ДЛЯ АНАЛИЗА ===\n{text}"

    api_url = f"{settings.DEEPSEEK_BASE_URL.rstrip('/')}/chat/completions"

    resp = requests.post(
        api_url,
        headers={"Authorization": f"Bearer {settings.DEEPSEEK_API_KEY}"},
        json={
            "model": settings.DEEPSEEK_MODEL,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.3,
            "max_tokens": 1500,
        },
        timeout=120,
    )

    # ==== Диагностика: HTTP-ошибки с текстом ответа ====
    if resp.status_code != 200:
        raise RuntimeError(
            f"API вернул {resp.status_code}: {resp.text[:200]}"
        )

    # ==== Диагностика: пустое или кривое тело ====
    try:
        payload = resp.json()
    except ValueError:
        raise RuntimeError(f"Невалидный JSON в ответе API: {resp.text[:200]}")

    content = (payload.get("choices") or [{}])[0].get("message", {}).get("content") or ""
    if not content.strip():
        raise RuntimeError(f"Пустой ответ модели: {str(payload)[:200]}")

    # ==== Модель может обернуть JSON в ```json ... ``` — чистим ====
    cleaned = content.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[-1]          # убрать первую строку ```json
        cleaned = cleaned.rsplit("```", 1)[0].strip() # убрать закрывающий ```

    try:
        data = json.loads(cleaned)
    except ValueError:
        raise RuntimeError(f"Модель вернула не-JSON: {cleaned[:200]}")

    return {
        "score": max(1, min(10, int(data.get("score", 5)))),
        "summary": str(data.get("summary", ""))[:2000],
        "strengths": [str(s)[:500] for s in data.get("strengths", [])][:7],
        "weaknesses": [str(s)[:500] for s in data.get("weaknesses", [])][:7],
        "suggestions": [str(s)[:500] for s in data.get("suggestions", [])][:10],
    }