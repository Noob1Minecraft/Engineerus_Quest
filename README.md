# Engineerus Quest 
Геймификация + ИИ-помощник для студентов-инженеров

##  Запуск
1. `cp .env.example .env` и заполни токены
2. `cd backend && pip install -r requirements.txt && uvicorn main:app --reload --port 8000`
3. `cd bot && pip install -r requirements.txt && python main.py`
4. Сайт: http://localhost:8000 | Бот: Telegram

##  Архитектура
- Backend (FastAPI) управляет SQLite и AI
- Frontend и Bot общаются с Backend через REST API
- Общая БД: `data/engineerus.db` (WAL режим)

# 🚀 Engineerus Quest

**Gamified AI-powered learning platform for engineering students in Kazakhstan**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)](https://fastapi.tiangolo.com/)

---

## 🎯 Overview

Engineerus Quest is an innovative educational platform that combines **artificial intelligence**, **gamification**, and **local context** to help engineering students in Kazakhstan master complex subjects like mechanics, thermodynamics, and materials science.

### ✨ Key Features

- 🤖 **5 AI-Powered Modules**
  - **TUTOR AI** — Personal engineering tutor with detailed explanations
  - **MaterialSwap** — Material selection assistant with Kazakhstan pricing
  - **PatentCraft** — Patent application guidance
  - **EngiLegal** — Engineering documentation and legal compliance
  - **EngiMatch** — Team matching for engineering projects

- 🎮 **Gamification System**
  - XP points and leveling system
  - Daily quests with streak rewards
  - Achievements and badges
  - Leaderboard competition
  - Progress tracking

- 🌍 **Multilingual Support**
  - 🇷🇺 Russian
  - 🇰🇿 Kazakh
  - 🇬🇧 English

- 🇰🇿 **Kazakhstan Context**
  - Prices in Kazakhstani tenge (₸)
  - Local cities and examples (Almaty, Astana, Shymkent)
  - Regional engineering standards

- 📱 **Multi-Platform**
  - Telegram bot with inline keyboards
  - Web application with responsive design
  - Onboarding tour for new users

---

## 🛠 Tech Stack

### Backend
- **FastAPI** — Modern async web framework
- **SQLite** — Lightweight database with aiosqlite
- **Ollama** — Local AI inference (no API costs)
- **Python 3.10+** — Async/await support

### Telegram Bot
- **aiogram 3.x** — Modern Telegram bot framework
- **FSM** — Finite state machine for conversations
- **httpx** — Async HTTP client

### Frontend
- **HTML5/CSS3** — Semantic markup with CSS variables
- **Vanilla JavaScript** — No framework dependencies
- **Responsive Design** — Mobile-first approach

---

## 📦 Installation

### Prerequisites

- Python 3.10 or higher
- [Ollama](https://ollama.ai/) installed and running
- Telegram Bot Token (from [@BotFather](https://t.me/BotFather))

### Setup Steps

1. **Clone the repository**
```bash
git clone https://github.com/YOUR_USERNAME/Engineerus-Quest.git
cd Engineerus-Quest

#  Engineerus Quest

Геймифицированная платформа для студентов-инженеров Казахстана с ИИ-помощником.

##  Фичи
-  5 инженерных модулей + локальный ИИ (Ollama)
-  3 языка: RU / KZ / EN
-  Квесты, XP, ачивки, стрики, лидерборд
-  Telegram-бот + веб-сайт
- 🇰🇿 Казахстанский контекст (тенге, города, реалии)

##  Стек
- Backend: FastAPI + SQLite + Ollama
- Bot: aiogram 3.x
- Frontend: HTML/CSS/JS

##  Roadmap
- v1.0.1: Notebook LLM (контекст пользователя)
- v1.0.2: Scopus AI (анализ научных статей)
- v1.0.3: Система подсказок вместо готовых ответов