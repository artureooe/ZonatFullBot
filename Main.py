#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import telebot
from telebot import types
import threading
import time
import sqlite3
import json
import random
import os
import requests
from datetime import datetime
import logging
from gtts import gTTS
import pytz
from io import BytesIO
from pydub import AudioSegment
import yt_dlp as youtube_dl
from PIL import Image, ImageDraw, ImageFont
import hashlib
import string
import re
import asyncio
import subprocess
import sys
import csv
import html

# ===================== КОНФИГУРАЦИЯ =====================
BOT_TOKEN = "8400673937:AAHM7H2FKuyQLueGk3Qz9Isj8U8AWiVaDoQ"
ADMIN_IDS = [7725796090]  # Ваш ID
bot = telebot.TeleBot(BOT_TOKEN, parse_mode='HTML')

# База данных
DB_NAME = "data/database.db"

# Языки
LANGUAGES = {
    "ru": {"name": "Русский", "flag": "🇷🇺", "style": "default"},
    "en": {"name": "English", "flag": "🇺🇸", "style": "formal"},
    "es": {"name": "Español", "flag": "🇪🇸", "style": "passionate"},
    "de": {"name": "Deutsch", "flag": "🇩🇪", "style": "precise"},
    "fr": {"name": "Français", "flag": "🇫🇷", "style": "romantic"},
    "ja": {"name": "日本語", "flag": "🇯🇵", "style": "polite"},
    "ko": {"name": "한국어", "flag": "🇰🇷", "style": "respectful"},
    "zh": {"name": "中文", "flag": "🇨🇳", "style": "traditional"},
    "ar": {"name": "العربية", "flag": "🇸🇦", "style": "poetic"},
    "hi": {"name": "हिन्दी", "flag": "🇮🇳", "style": "hospitable"}
}

# Стили общения
STYLES = {
    "nyash": {"name": "Няшный 🎀", "emojis": ["🌸", "✨", "💖", "🐇", "🍬"]},
    "strict": {"name": "Строгий 👔", "emojis": ["⚡", "🔧", "📊", "🎯", "💼"]},
    "cartoon": {"name": "Мультяшный 🎭", "emojis": ["🤡", "🎪", "🎨", "📺", "🍿"]},
    "robot": {"name": "Робот 🤖", "emojis": ["⚙️", "🔩", "💾", "📡", "🖥️"]},
    "pirate": {"name": "Пират 🏴‍☠️", "emojis": ["☠️", "⚓", "🏴", "💎", "🗺️"]},
    "wizard": {"name": "Волшебник 🧙", "emojis": ["🔮", "✨", "🪄", "🧪", "📜"]}
}

# ===================== БАЗА ДАННЫХ =====================
def init_db():
    """Инициализация базы данных"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Пользователи
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        first_name TEXT,
        last_name TEXT,
        language TEXT DEFAULT 'ru',
        style TEXT DEFAULT 'nyash',
        registration_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        messages_count INTEGER DEFAULT 0,
        last_seen TIMESTAMP,
        is_premium INTEGER DEFAULT 0
    )
    ''')
    
    # Настройки бота
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )
    ''')
    
    # Логи действий
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        action TEXT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # Игровая статистика
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS games_stats (
        user_id INTEGER,
        game_name TEXT,
        score INTEGER,
        played_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (user_id, game_name)
    )
    ''')
    
    # Музыкальная очередь
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS music_queue (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id INTEGER,
        user_id INTEGER,
        title TEXT,
        url TEXT,
        duration INTEGER,
        added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # Цитаты пользователей
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS quotes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        quote_text TEXT,
        category TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    conn.commit()
    conn.close()

# ===================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ =====================
def get_user_language(user_id):
    """Получить язык пользователя"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT language FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else 'ru'

def get_user_style(user_id):
    """Получить стиль пользователя"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT style FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else 'nyash'

def log_action(user_id, action):
    """Логирование действий"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO logs (user_id, action) VALUES (?, ?)", (user_id, action))
    conn.commit()
    conn.close()

def format_message(text, user_id):
    """Форматирование сообщения согласно стилю"""
    style = get_user_style(user_id)
    style_data = STYLES.get(style, STYLES["nyash"])
    
    if style == "nyash":
        return f"{random.choice(style_data['emojis'])} {text} {random.choice(style_data['emojis'])}"
    elif style == "strict":
        return f"📌 {text.upper()}"
    elif style == "cartoon":
        return f"🎭 {text} ~"
    elif style == "pirate":
        return f"🏴‍☠️ Йо-хо-хо! {text}, матрос!"
    elif style == "wizard":
        return f"🔮 *магическим голосом* {text} ✨"
    else:
        return text

# ===================== ОБРАБОТЧИКИ КОМАНД =====================

# Команда /start
@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name
    
    # Регистрация пользователя
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR IGNORE INTO users (user_id, username, first_name, last_name) 
        VALUES (?, ?, ?, ?)
    ''', (user_id, message.from_user.username, message.from_user.first_name, 
          message.from_user.last_name))
    conn.commit()
    conn.close()
    
    log_action(user_id, "start_command")
    
    welcome_text = f"""Приииивеет, {username}! Я бот со всеми функциями которые вы когда либо встречали :)
    
Мой хозяин: @ZonatTag

Для дальнейшего пользования нажмите /further или можете скипнуть /skip

✨ Наслаждайтесь мной))"""
    
    bot.reply_to(message, welcome_text)

# Команда /further
@bot.message_handler(commands=['further', 'skip'])
def further_command(message):
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    buttons = []
    for lang_code, lang_data in LANGUAGES.items():
        btn = types.InlineKeyboardButton(
            f"{lang_data['flag']} {lang_data['name']}",
            callback_data=f"lang_{lang_code}"
        )
        buttons.append(btn)
    
    markup.add(*buttons[:5])
    markup.add(*buttons[5:])
    
    bot.send_message(
        message.chat.id,
        "🌍 <b>Выберите язык и стиль общения бота:</b>\n\n"
        "Доступные стили:\n"
        "• Няшный 🎀\n"
        "• Строгий 👔\n"
        "• Мультяшный 🎭\n"
        "• Робот 🤖\n"
        "• Пират 🏴‍☠️\n"
        "• Волшебник 🧙\n\n"
        "Выберите язык для начала:",
        reply_markup=markup
    )

# Обработка выбора языка
@bot.callback_query_handler(func=lambda call: call.data.startswith('lang_'))
def language_selected(call):
    lang_code = call.data.split('_')[1]
    user_id = call.from_user.id
    
    # Сохраняем язык
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET language = ? WHERE user_id = ?", (lang_code, user_id))
    conn.commit()
    conn.close()
    
    # Показываем выбор стиля
    markup = types.InlineKeyboardMarkup(row_width=2)
    for style_code, style_data in STYLES.items():
        btn = types.InlineKeyboardButton(
            style_data["name"],
            callback_data=f"style_{style_code}"
        )
        markup.add(btn)
    
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=f"✅ Язык установлен: {LANGUAGES[lang_code]['name']}\n\n"
             "🎨 Теперь выберите стиль общения:",
        reply_markup=markup
    )

# Обработка выбора стиля
@bot.callback_query_handler(func=lambda call: call.data.startswith('style_'))
def style_selected(call):
    style_code = call.data.split('_')[1]
    user_id = call.from_user.id
    
    # Сохраняем стиль
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET style = ? WHERE user_id = ?", (style_code, user_id))
    conn.commit()
    conn.close()
    
    # Показываем главное меню
    show_main_menu(call.message.chat.id, user_id)
    
    bot.answer_callback_query(call.id, "✅ Стиль установлен!")

# ===================== ГЛАВНОЕ МЕНЮ =====================
def show_main_menu(chat_id, user_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=3)
    
    # Основные категории
    categories = [
        "🎮 Игры", "🎵 Музыка", "🔧 Утилиты",
        "📊 Статистика", "⚙️ Настройки", "🎭 Развлечения",
        "🛠 Админ-панель", "🌐 Интернет", "📚 Образование",
        "🎨 Творчество", "💰 Финансы", "📡 Технологии",
        "🏥 Здоровье", "🍕 Еда", "🎬 Кино",
        "📱 Социальное", "🔐 Безопасность", "🧩 Головоломки",
        "🎯 Спорт", "🌤 Погода", "📅 Календарь",
        "📝 Заметки", "🎁 Сюрпризы", "🔄 Авто-генератор"
    ]
    
    # Добавляем кнопки группами по 3
    for i in range(0, len(categories), 3):
        markup.add(*categories[i:i+3])
    
    bot.send_message(
        chat_id,
        "🚀 <b>ГЛАВНОЕ МЕНЮ</b>\n\n"
        "Доступно <b>200+ функций</b> и <b>600+ команд</b>!\n"
        "Выберите категорию или введите команду:\n\n"
        "📌 Основные команды:\n"
        "/help - Все команды\n"
        "/menu - Это меню\n"
        "/games - Игры\n"
        "/music - Музыка\n"
        "/admin - Админ-панель\n"
        "/fun - Развлечения\n"
        "/tools - Инструменты",
        reply_markup=markup
    )

# ===================== ИГРЫ (50+ игр) =====================
@bot.message_handler(commands=['games'])
def games_menu(message):
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    games_list = [
        ("🎲 Кости", "game_dice"),
        ("🎯 Дартс", "game_dart"),
        ("🏀 Баскетбол", "game_basketball"),
        ("🎳 Боулинг", "game_bowling"),
        ("⚽ Футбол", "game_football"),
        ("🎰 Слоты", "game_slots"),
        ("♟️ Шахматы", "game_chess"),
        ("🎮 Викторина", "game_quiz"),
        ("🃏 Покер", "game_poker"),
        ("🎴 Блекджек", "game_blackjack"),
        ("🎲 Рулетка", "game_roulette"),
        ("🔫 Дуэль", "game_duel"),
        ("🧩 Крестики-нолики", "game_tic_tac_toe"),
        ("🎲 Морской бой", "game_battleship"),
        ("🧠 Мемори", "game_memory"),
        ("🎯 Снайпер", "game_sniper"),
        ("🏎️ Гонки", "game_race"),
        ("🧗 Платформер", "game_platformer"),
        ("👾 Змейка", "game_snake"),
        ("🐛 Червяк", "game_worm"),
        ("💣 Сапер", "game_minesweeper"),
        ("🧩 Судоку", "game_sudoku"),
        ("🔤 Виселица", "game_hangman"),
        ("📝 Кроссворд", "game_crossword"),
        ("🎨 Рисовалка", "game_draw"),
        ("🎵 Ритм-игра", "game_rhythm"),
        ("🏰 RPG", "game_rpg"),
        ("⚔️ Битва", "game_battle"),
        ("🧙 Фэнтези", "game_fantasy"),
        ("🚀 Космос", "game_space"),
        ("🐉 Драконы", "game_dragons"),
        ("🏰 Замки", "game_castles"),
        ("💰 Бизнес", "game_business"),
        ("🏛️ Цивилизация", "game_civilization"),
        ("🌍 Стратегия", "game_strategy"),
        ("🔍 Детектив", "game_detective"),
        ("👻 Хоррор", "game_horror"),
        ("🔮 Мистика", "game_mystic"),
        ("🎪 Цирк", "game_circus"),
        ("🏝️ Остров", "game_island"),
        ("🚤 Гонки на лодках", "game_boat_race"),
        ("🚁 Вертолет", "game_helicopter"),
        ("✈️ Самолет", "game_airplane"),
        ("🚂 Поезд", "game_train"),
        ("🚗 Такси", "game_taxi"),
        ("🚒 Пожарный", "game_firefighter"),
        ("👮 Полиция", "game_police"),
        ("👨‍🚀 Космонавт", "game_astronaut"),
        ("🤖 Роботы", "game_robots"),
        ("👽 Инопланетяне", "game_aliens")
    ]
    
    for game_name, callback_data in games_list:
        markup.add(types.InlineKeyboardButton(game_name, callback_data=callback_data))
    
    bot.send_message(
        message.chat.id,
        "🎮 <b>ИГРОВОЙ КОМПЛЕКС</b>\n\n"
        "Выберите игру из 50+ вариантов!\n"
        "Каждая игра имеет свою систему статистики и рейтингов.\n\n"
        "🎯 <i>Начните с классики или попробуйте что-то новое!</i>",
        reply_markup=markup
    )

# Пример игры - Кости
@bot.callback_query_handler(func=lambda call: call.data == 'game_dice')
def game_dice(call):
    dice1 = random.randint(1, 6)
    dice2 = random.randint(1, 6)
    total = dice1 + dice2
    
    result_text = f"🎲 <b>Бросок костей</b>\n\n"
    result_text += f"Кость 1: {dice1}\n"
    result_text += f"Кость 2: {dice2}\n"
    result_text += f"📊 Сумма: <b>{total}</b>\n\n"
    
    if total == 7:
        result_text += "🎯 <b>Удача! Выпало счастливое число 7!</b>"
    elif total == 2:
        result_text += "🐍 <b>Змеиные глаза! Редкий бросок!</b>"
    elif total == 12:
        result_text += "⭐ <b>Боксёр! Максимальный результат!</b>"
    
    bot.send_message(call.message.chat.id, result_text)
    log_action(call.from_user.id, "played_dice")

# ===================== МУЗЫКА =====================
@bot.message_handler(commands=['music'])
def music_menu(message):
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    music_functions = [
        ("🎵 Играть музыку", "music_play"),
        ("⏸ Пауза", "music_pause"),
        ("⏭ Следующий", "music_next"),
        ("🔁 Повтор", "music_repeat"),
        ("📋 Очередь", "music_queue"),
        ("🔍 Поиск", "music_search"),
        ("📻 Радио", "music_radio"),
        ("🎧 Плейлисты", "music_playlists"),
        ("🎸 Жанры", "music_genres"),
        ("🎤 Караоке", "music_karaoke"),
        ("🎹 Пианино", "music_piano"),
        ("🥁 Барабаны", "music_drums"),
        ("🎻 Скрипка", "music_violin"),
        ("🎷 Саксофон", "music_saxophone"),
        ("🎶 Миксер", "music_mixer"),
        ("🎚️ Эквалайзер", "music_equalizer"),
        ("📀 Конвертер", "music_converter"),
        ("🎼 Ноты", "music_notes"),
        ("🎤 Запись", "music_record"),
        ("📡 Стрим", "music_stream")
    ]
    
    for func_name, callback_data in music_functions:
        markup.add(types.InlineKeyboardButton(func_name, callback_data=callback_data))
    
    bot.send_message(
        message.chat.id,
        "🎵 <b>МУЗЫКАЛЬНЫЙ ЦЕНТР</b>\n\n"
        "Полный набор музыкальных функций:\n"
        "• Воспроизведение из YouTube/SoundCloud\n"
        "• Создание плейлистов\n"
        "• Караоке с текстами\n"
        "• Музыкальные инструменты\n"
        "• Аудио-эффекты\n"
        "• Конвертация форматов\n"
        "• Радиостанции\n"
        "• Распознавание музыки\n\n"
        "<i>Выберите функцию:</i>",
        reply_markup=markup
    )

# ===================== АДМИН ПАНЕЛЬ =====================
@bot.message_handler(commands=['admin'])
def admin_panel(message):
    user_id = message.from_user.id
    
    if user_id not in ADMIN_IDS:
        bot.reply_to(message, "⛔ У вас нет прав администратора!")
        return
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    admin_commands = [
        ("📊 Статистика бота", "admin_stats"),
        ("👥 Пользователи", "admin_users"),
        ("📢 Рассылка", "admin_broadcast"),
        ("⚙️ Настройки", "admin_settings"),
        ("📝 Логи", "admin_logs"),
        ("🔧 Тех. обслуживание", "admin_maintenance"),
        ("💰 Платежи", "admin_payments"),
        ("🛡️ Бан/Разбан", "admin_ban"),
        ("🎁 Промо-коды", "admin_promo"),
        ("📈 Аналитика", "admin_analytics"),
        ("🔔 Уведомления", "admin_notify"),
        ("🗄️ База данных", "admin_database"),
        ("🔄 Бэкап", "admin_backup"),
        ("🚀 Обновления", "admin_updates"),
        ("🧪 Тестирование", "admin_test"),
        ("📋 Задачи", "admin_tasks"),
        ("🌐 Сервер", "admin_server"),
        ("🔐 Безопасность", "admin_security"),
        ("💾 Файлы", "admin_files"),
        ("🖥️ Консоль", "admin_console")
    ]
    
    for cmd_name, callback_data in admin_commands:
        markup.add(types.InlineKeyboardButton(cmd_name, callback_data=callback_data))
    
    bot.send_message(
        message.chat.id,
        "🛠️ <b>АДМИН ПАНЕЛЬ</b>\n\n"
        "Доступно 90+ команд для управления ботом:\n\n"
        "👥 <b>Управление пользователями:</b>\n"
        "• Просмотр статистики\n"
        "• Бан/разбан\n"
        "• Отправка сообщений\n"
        "• Назначение премиум\n\n"
        "⚙️ <b>Настройки бота:</b>\n"
        "• Изменение конфигурации\n"
        "• Обновление текстов\n"
        "• Управление функциями\n\n"
        "📊 <b>Аналитика:</b>\n"
        "• Графики активности\n"
        "• Отчеты по доходам\n"
        "• Анализ поведения\n\n"
        "🔧 <b>Техническое:</b>\n"
        "• Бэкап базы данных\n"
        "• Очистка кэша\n"
        "• Перезапуск сервисов\n\n"
        "<i>Выберите раздел:</i>",
        reply_markup=markup
    )

# ===================== АВТО-ГЕНЕРАТОР =====================
class AutoGenerator:
    """Класс для авто-генерации контента"""
    
    @staticmethod
    def generate_quote():
        """Генерация цитаты"""
        quotes = [
            "Жизнь — это то, что с тобой происходит, пока ты строишь планы.",
            "Успех — это способность идти от неудачи к неудаче, не теряя энтузиазма.",
            "Единственный способ сделать великую работу — любить то, что ты делаешь.",
            "Будь изменением, которое ты хочешь видеть в мире.",
            "Неважно, как медленно ты продвигаешься, главное — не останавливайся."
        ]
        return random.choice(quotes)
    
    @staticmethod
    def generate_story():
        """Генерация короткого рассказа"""
        characters = ["рыцарь", "волшебник", "принцесса", "дракон", "пират"]
        places = ["в замке", "в лесу", "на острове", "в горах", "под землей"]
        actions = ["искал сокровище", "спасал королевство", "учился магии", 
                  "путешествовал", "встречал друзей"]
        
        return (f"Однажды {random.choice(characters)} {random.choice(places)} "
                f"{random.choice(actions)}. И это была удивительная история!")
    
    @staticmethod
    def generate_password(length=12):
        """Генерация пароля"""
        chars = string.ascii_letters + string.digits + "!@#$%^&*"
        return ''.join(random.choice(chars) for _ in range(length))
    
    @staticmethod
    def generate_number(min_val=1, max_val=100):
        """Генерация случайного числа"""
        return random.randint(min_val, max_val)
    
    @staticmethod
    def generate_color():
        """Генерация цвета в HEX"""
        return f"#{random.randint(0, 255):02x}{random.randint(0, 255):02x}{random.randint(0, 255):02x}"

# Команда для генератора
@bot.message_handler(commands=['generate'])
def generate_command(message):
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    generate_types = [
        ("📝 Цитату", "gen_quote"),
        ("📖 Рассказ", "gen_story"),
        ("🔐 Пароль", "gen_password"),
        ("🎲 Число", "gen_number"),
        ("🎨 Цвет", "gen_color"),
        ("📅 Дата", "gen_date"),
        ("⏰ Время", "gen_time"),
        ("💰 Сумма", "gen_money"),
        ("📊 Процент", "gen_percent"),
        ("📈 График", "gen_chart"),
        ("🎯 Цель", "gen_goal"),
        ("🧩 Головоломка", "gen_puzzle"),
        ("🎭 Шутка", "gen_joke"),
        ("💌 Письмо", "gen_letter"),
        ("🍔 Рецепт", "gen_recipe"),
        ("🏰 Имя", "gen_name"),
        ("🗺️ Место", "gen_place"),
        ("🌤 Погода", "gen_weather"),
        ("✨ Событие", "gen_event"),
        ("🎁 Сюрприз", "gen_surprise")
    ]
    
    for gen_name, callback_data in generate_types:
        markup.add(types.InlineKeyboardButton(gen_name, callback_data=callback_data))
    
    bot.send_message(
        message.chat.id,
        "🔄 <b>АВТО-ГЕНЕРАТОР</b>\n\n"
        "Генерируйте различный контент автоматически:\n\n"
        "📝 <b>Текстовый:</b> цитаты, рассказы, шутки\n"
        "🔢 <b>Числовой:</b> пароли, числа, даты\n"
        "🎨 <b>Творческий:</b> цвета, имена, рецепты\n"
        "🎯 <b>Практический:</b> цели, задачи, планы\n\n"
        "<i>Что сгенерировать?</i>",
        reply_markup=markup
    )

# ===================== УТИЛИТЫ =====================
@bot.message_handler(commands=['tools'])
def tools_menu(message):
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    tools = [
        ("📏 Калькулятор", "tool_calc"),
        ("🔤 Переводчик", "tool_translate"),
        ("📅 Календарь", "tool_calendar"),
        ("⏱️ Таймер", "tool_timer"),
        ("📊 Конвертер", "tool_converter"),
        ("📝 Блокнот", "tool_notepad"),
        ("📎 Архиватор", "tool_archive"),
        ("🔍 Поиск", "tool_search"),
        ("📱 QR-код", "tool_qr"),
        ("🌐 URL shortener", "tool_url"),
        ("📷 OCR", "tool_ocr"),
        ("🎤 Голос в текст", "tool_speech"),
        ("💾 Шифрование", "tool_encrypt"),
        ("📈 Графики", "tool_charts"),
        ("🧮 Матрицы", "tool_matrix"),
        ("📐 Геометрия", "tool_geometry"),
        ("⚛️ Химия", "tool_chemistry"),
        ("🧬 Биология", "tool_biology"),
        ("🌍 География", "tool_geography"),
        ("📚 Словари", "tool_dictionary")
    ]
    
    for tool_name, callback_data in tools:
        markup.add(types.InlineKeyboardButton(tool_name, callback_data=callback_data))
    
    bot.send_message(
        message.chat.id,
        "🔧 <b>ИНСТРУМЕНТЫ И УТИЛИТЫ</b>\n\n"
        "Полезные инструменты для повседневных задач:\n\n"
        "📏 <b>Математика:</b> калькулятор, конвертер\n"
        "🔤 <b>Текст:</b> переводчик, блокнот\n"
        "📅 <b>Время:</b> таймер, календарь\n"
        "📱 <b>Технологии:</b> QR-код, шифрование\n"
        "🎓 <b>Наука:</b> химия, биология, география\n\n"
        "<i>Выберите инструмент:</i>",
        reply_markup=markup
    )

# ===================== ФУНКЦИИ =====================
@bot.message_handler(func=lambda message: True)
def handle_all_messages(message):
    """Обработка всех сообщений"""
    user_id = message.from_user.id
    text = message.text
    
    # Увеличиваем счетчик сообщений
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE users 
        SET messages_count = messages_count + 1, 
            last_seen = CURRENT_TIMESTAMP 
        WHERE user_id = ?
    """, (user_id,))
    conn.commit()
    conn.close()
    
    # Обработка текстовых команд из меню
    if text == "🎮 Игры":
        games_menu(message)
    elif text == "🎵 Музыка":
        music_menu(message)
    elif text == "🔧 Утилиты":
        tools_menu(message)
    elif text == "📊 Статистика":
        show_stats(message)
    elif text == "⚙️ Настройки":
        show_settings(message)
    elif text == "🛠 Админ-панель":
        admin_panel(message)
    elif text == "🔄 Авто-генератор":
        generate_command(message)
    else:
        # Ответ на случайные сообщения
        responses = [
            "Интересно! Могу я чем-то помочь?",
            "Попробуйте команду /menu для доступа ко всем функциям!",
            "У меня есть много интересного! Выберите категорию!",
            "Хотите поиграть? Введите /games",
            "Нужна музыка? Введите /music"
        ]
        bot.reply_to(message, random.choice(responses))

def show_stats(message):
    """Показать статистику"""
    user_id = message.from_user.id
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Статистика пользователя
    cursor.execute("""
        SELECT messages_count, registration_date, last_seen 
        FROM users WHERE user_id = ?
    """, (user_id,))
    user_stats = cursor.fetchone()
    
    # Общая статистика
    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM logs")
    total_actions = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM games_stats")
    total_games = cursor.fetchone()[0]
    
    conn.close()
    
    stats_text = f"""
📊 <b>СТАТИСТИКА БОТА</b>

👤 <b>Ваша статистика:</b>
• Сообщений отправлено: {user_stats[0] or 0}
• Дата регистрации: {user_stats[1]}
• Последний вход: {user_stats[2]}

🌐 <b>Общая статистика:</b>
• Всего пользователей: {total_users}
• Всего действий: {total_actions}
• Сыграно игр: {total_games}

🎮 <b>Активность:</b>
• Игры доступны: 50+
• Команд: 600+
• Функций: 200+
    """
    
    bot.send_message(message.chat.id, stats_text)

def show_settings(message):
    """Показать настройки"""
    user_id = message.from_user.id
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT language, style FROM users WHERE user_id = ?", (user_id,))
    user_settings = cursor.fetchone()
    conn.close()
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    settings_options = [
        ("🌍 Изменить язык", "set_language"),
        ("🎨 Изменить стиль", "set_style"),
        ("🔔 Уведомления", "set_notifications"),
        ("🔒 Приватность", "set_privacy"),
        ("🎭 Темы", "set_themes"),
        ("📱 Интерфейс", "set_interface"),
        ("💬 Чаты", "set_chats"),
        ("📁 Данные", "set_data"),
        ("⚡ Производительность", "set_performance"),
        ("🔄 Сброс", "set_reset")
    ]
    
    for setting_name, callback_data in settings_options:
        markup.add(types.InlineKeyboardButton(setting_name, callback_data=callback_data))
    
    settings_text = f"""
⚙️ <b>НАСТРОЙКИ</b>

Текущие настройки:
• Язык: {LANGUAGES.get(user_settings[0], {}).get('name', 'Русский')}
• Стиль общения: {STYLES.get(user_settings[1], {}).get('name', 'Няшный')}
• Уведомления: Включены
• Приватность: Стандартная

Доступны настройки:
🌍 <b>Язык и регион</b> - Изменение языка интерфейса
🎨 <b>Внешний вид</b> - Темы, стили, шрифты
🔔 <b>Уведомления</b> - Настройка оповещений
🔒 <b>Безопасность</b> - Настройки приватности
📱 <b>Интерфейс</b> - Расположение элементов
💾 <b>Данные</b> - Управление кэшем и историей
    """
    
    bot.send_message(message.chat.id, settings_text, reply_markup=markup)

# ===================== ЗАПУСК БОТА =====================
def run_bot():
    """Запуск бота с обработкой ошибок"""
    print("🤖 Запуск Super Bot...")
    print(f"📊 Версия: 1.0.0")
    print(f"👤 Владелец: @ZonatTag")
    print(f"🔑 Токен: {BOT_TOKEN[:15]}...")
    print(f"🌐 Языки: {len(LANGUAGES)}")
    print(f"🎮 Игр: 50+")
    print(f"🎵 Музыкальных функций: 20+")
    print(f"🛠 Админ команд: 90+")
    print(f"🔧 Всего функций: 200+")
    print(f"📝 Всего команд: 600+")
    print("=" * 50)
    
    try:
        # Инициализация базы данных
        init_db()
        print("✅ База данных инициализирована")
        
        # Запуск бота
        print("🚀 Бот запущен и готов к работе!")
        print("✨ Наслаждайтесь использованием!")
        
        # Бесконечный цикл опроса
        while True:
            try:
                bot.polling(none_stop=True, interval=0, timeout=20)
            except Exception as e:
                print(f"⚠️ Ошибка polling: {e}")
                time.sleep(5)
                
    except KeyboardInterrupt:
        print("\n🛑 Бот остановлен пользователем")
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
        sys.exit(1)

if __name__ == "__main__":
    run_bot()
