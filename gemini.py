import asyncio
import google.generativeai as genai
from config import GEMINI_API_KEY

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash-latest')

# Резервные слова и фразы, если API упадет
FALLBACK_WORDS = ["alpha", "beta", "gamma", "delta", "omega", "zeta", "sigma", "theta"]
FALLBACK_GREETING = "Привет! Для доступа к функционалу бота необходимо оформить подписку на наши каналы. Нажми кнопку ниже, чтобы перейти к каналам."

async def generate_greeting() -> str:
    try:
        prompt = (
            "Напиши короткое, дружелюбное приветствие для пользователя Telegram-бота. "
            "Пользователь только что нажал /start. "
            "Скажи ему, что перед началом использования нужно обязательно подписаться на спонсорские каналы. "
            "ВАЖНО: Никаких упоминаний, что ты ИИ, нейросеть, языковая модель. Пиши как живой человек. "
            "Только текст приветствия, без лишних символов."
        )
        response = await asyncio.to_thread(model.generate_content, prompt)
        return response.text.strip()
    except Exception as e:
        print(f"Gemini API Error (greeting): {e}")
        return FALLBACK_GREETING

async def generate_random_word() -> str:
    try:
        prompt = "Сгенерируй одно случайное короткое английское слово (существительное). Напиши только это слово, без знаков препинания и лишнего текста."
        response = await asyncio.to_thread(model.generate_content, prompt)
        word = response.text.strip().lower()
        # На всякий случай берем только первое слово, если ИИ добавил лишнее
        return word.split()[0] if word else "access"
    except Exception as e:
        print(f"Gemini API Error (word): {e}")
        import random
        return random.choice(FALLBACK_WORDS)