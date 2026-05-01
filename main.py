"""Точка входа.

Запускает Flask-сервер для health-check (нужен Render Web Service)
и поднимает VK-бота в фоновом потоке.

Запуск через gunicorn:
    gunicorn main:app --workers 1 --threads 4 --timeout 120 --bind 0.0.0.0:$PORT

Локально:
    python main.py
"""
import logging

from flask import Flask

from src.config import PORT
from src.vk_bot import start_bot_in_background

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("main")

app = Flask(__name__)


@app.route("/")
def root():
    return "Credit calculator VK bot is running.", 200


@app.route("/health")
def health():
    return {"status": "ok"}, 200


# стартуем бота при импорте — gunicorn делает один импорт на воркер
log.info("Starting VK bot in background...")
start_bot_in_background()


if __name__ == "__main__":
    # локальный запуск (без gunicorn)
    app.run(host="0.0.0.0", port=PORT)
