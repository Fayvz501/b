"""Конфигурация: всё через переменные окружения.

На Render Free Tier нет persistent disk, поэтому БД живёт в /tmp.
Это нормально: история обнуляется при рестарте, но за время сессии
все расчёты пользователя сохраняются.
"""
import os

VK_TOKEN = os.environ.get("VK_TOKEN", "")
VK_GROUP_ID = os.environ.get("VK_GROUP_ID", "")
DB_PATH = os.environ.get("DB_PATH", "/tmp/credit_bot.db")
PORT = int(os.environ.get("PORT", "10000"))
