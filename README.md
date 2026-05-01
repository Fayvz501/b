# 💰 Finance Pro — Credit Calculator VK Bot

VK-бот: расчёт кредита по двум схемам (аннуитет / дифференцированный),
графики, банковский PDF-отчёт, история расчётов, сложный процент.

## 🚀 Возможности

- **Кредит:** аннуитет vs дифф., 4 графика на matplotlib, PDF на ReportLab
- **Сложный процент:** капитализация для вкладов
- **История:** последние 5 расчётов на пользователя
- **Callback-кнопки VK:** переключение между графиками без перезапуска диалога

## 📁 Структура

```
credit-bot/
├── main.py                # точка входа: Flask + бот в фоновом потоке
├── requirements.txt
├── Procfile
├── runtime.txt
├── .python-version
├── .gitignore
├── .env.example
├── README.md
├── fonts/
│   ├── DejaVuSans.ttf
│   └── DejaVuSans-Bold.ttf
└── src/
    ├── __init__.py
    ├── config.py          # переменные окружения
    ├── finance.py         # формулы аннуитета и дифф.
    ├── charts.py          # matplotlib графики
    ├── pdf_engine.py      # ReportLab PDF
    ├── db_manager.py      # SQLite: история + состояние диалога
    ├── keyboards.py       # клавиатуры VK
    └── vk_bot.py          # VkBotLongPoll + Callback API
```

## 🛠️ Деплой на Render (Free Tier, ручной Web Service)

### 1. Группа ВК

1. https://vk.com/groups → создать сообщество.
2. **Управление → Сообщения** → включить.
3. **Управление → Работа с API → Ключи доступа** → создать токен с правами:
   *Сообщения сообщества*, *Управление*, *Фото*, *Документы*. Это `VK_TOKEN`.
4. **Работа с API → Long Poll API** → включить, версия **5.199**, отметить:
   - `Входящее сообщение`
   - `Callback-кнопки: ответ`  ← **обязательно, без этого callback-кнопки молчат!**
5. ID сообщества (цифры в URL `vk.com/club...`) — это `VK_GROUP_ID`.

### 2. GitHub

```bash
cd credit-bot
git init
git add .
git commit -m "init"
git branch -M main
git remote add origin https://github.com/<логин>/credit-bot.git
git push -u origin main
```

### 3. Render

https://dashboard.render.com → **New + → Web Service** → подключи репо. Заполни:

| Поле | Значение |
|---|---|
| **Name** | `credit-bot` (любое) |
| **Region** | `Frankfurt` |
| **Branch** | `main` |
| **Root Directory** | (пусто) |
| **Runtime / Language** | `Python 3` |
| **Build Command** | `pip install --upgrade pip && pip install -r requirements.txt` |
| **Start Command** | `gunicorn main:app --workers 1 --threads 4 --timeout 120 --bind 0.0.0.0:$PORT` |
| **Instance Type** | `Free` |

### 4. Environment Variables

В разделе **Environment Variables** добавь:

| Key | Value |
|---|---|
| `VK_TOKEN` | твой токен сообщества |
| `VK_GROUP_ID` | числовой ID группы (без `club`) |
| `PYTHON_VERSION` | `3.11.9` |
| `DB_PATH` | `/tmp/credit_bot.db` |

`PORT` **не задавай** — Render выставит автоматически.

### 5. Health Check

**Advanced → Health Check Path** → `/health`.

### 6. Create Web Service

Жми кнопку. Сборка ~3 минуты. Когда статус **Live**, открой
`https://<твой-сервис>.onrender.com/health` — должен вернуться `{"status":"ok"}`.
Затем напиши боту в группу.

### 7. Чтобы сервис не засыпал

Free-тариф усыпляет процесс после 15 минут без HTTP-трафика. Long Poll
к ВК — исходящее соединение, оно не считается. Решение:
https://uptimerobot.com → бесплатный аккаунт → **Add New Monitor**:

- Type: **HTTP(s)**
- URL: `https://<твой-сервис>.onrender.com/health`
- Interval: **5 minutes**

Бот будет онлайн 24/7.

## 💻 Локальный запуск

```bash
cp .env.example .env
# отредактируй .env
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Linux/Mac
export $(grep -v '^#' .env | xargs)
python main.py
```

Открой `http://localhost:10000/health` — там `ok`. Параллельно бот слушает
ВК и отвечает в группе.

## 🔧 Стек

- Python 3.11
- vk_api 11.9.9 (**VkBotLongPoll** + Callback API)
- matplotlib 3.8.4
- reportlab 4.2.0
- Flask 3.0 + gunicorn (health-check для Render Web Service)
- SQLite (стандартная библиотека)

## ⚠️ Известные особенности

- **Callback-кнопки требуют VkBotLongPoll** (для сообществ), а не VkLongPoll.
  В этом коде используется правильный.
- **БД эфемерная** на Render Free (`/tmp` обнуляется при рестарте) — это ок
  для истории на 5 записей; для долговременной нужен Render PostgreSQL.
- **VK API версии 5.130+** обязательна для Callback API.
