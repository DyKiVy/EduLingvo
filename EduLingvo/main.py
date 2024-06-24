# -*- coding: utf-8 -*-
import telebot
import sqlite3
import logging
import random
import re

from groq import Groq
from telebot import types
from datetime import datetime, timedelta

bot = telebot.TeleBot("7001780457:AAGWAICphh-qbShJMFHlgJiTZO5QWqhNM8g")
client = Groq(api_key="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")

CHECK_TIME = False  # True False Флаг для включения/отключения проверки времени выполнения задачи


def read_instructions_from_file(filename):
    with open(filename, 'r', encoding='utf-8') as file:
        instructions = file.read()
    return instructions


welcom_massage = read_instructions_from_file('welcom_message.txt')
promt_positev = read_instructions_from_file('promt_positev.txt')
promt_negative = read_instructions_from_file('promt_negative.txt')
promt_1 = read_instructions_from_file('promt_1.txt')
promt_2 = read_instructions_from_file('promt_2.txt')
form_1 = read_instructions_from_file('form_1.txt')
form_2 = read_instructions_from_file('form_2.txt')
daily_task_analysis = read_instructions_from_file('daily_task_analysis.txt')\

chat_history = [{"role": 'user', "content": promt_positev + promt_negative}]
sys_text = [{"role": 'user', "content": " "}]

promt_gen = client.chat.completions.create(model='llama3-70b-8192', messages=chat_history, temperature=0)
print(promt_gen.choices[0].message.content)

user_state = {}


def set_user_state(user_id, state):
    user_state[user_id] = state


def get_user_state(user_id):
    return user_state.get(user_id)


def reset_user_state(user_id):
    user_state[user_id] = None


def init_db():
    conn = sqlite3.connect('translations.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS translations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                translated TEXT
              )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                level INTEGER DEFAULT 1,
                daily_last_completed TEXT,
                weekly_last_completed TEXT
              )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS user_topics (
                user_id INTEGER PRIMARY KEY,
                topics TEXT
              )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS generated_word_lists (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                word_list TEXT
              )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS user_languages (
                    user_id INTEGER PRIMARY KEY,
                    language TEXT
                  )''')
    conn.commit()
    conn.close()

    add_missing_columns()


def add_missing_columns():
    conn = sqlite3.connect('translations.db')
    cursor = conn.cursor()
    try:
        cursor.execute('ALTER TABLE users ADD COLUMN daily_last_completed TEXT')
    except sqlite3.OperationalError:
        pass  # Колонка уже существует

    try:
        cursor.execute('ALTER TABLE users ADD COLUMN weekly_last_completed TEXT')
    except sqlite3.OperationalError:
        pass  # Колонка уже существует

    conn.commit()
    conn.close()


# Функция для проверки, существует ли пользователь в БД
def user_exists(user_id):
    conn = sqlite3.connect('translations.db')
    cursor = conn.cursor()
    cursor.execute('SELECT user_id FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result is not None


# Функция для сохранения выбранного пользователем языка
def save_user_language(user_id, language):
    logging.info(f"Сохранение языка для пользователя {user_id}: {language}")
    conn = sqlite3.connect('translations.db')
    cursor = conn.cursor()
    cursor.execute('REPLACE INTO user_languages (user_id, language) VALUES (?, ?)', (user_id, language))
    conn.commit()
    conn.close()


# Функция для получения выбранного пользователем языка
def get_user_language(user_id):
    conn = sqlite3.connect('translations.db')
    cursor = conn.cursor()
    cursor.execute('SELECT language FROM user_languages WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    conn.close()
    if result:
        language = result[0]
        logging.info(f"Получен язык для пользователя {user_id}: {language}")
        return language
    else:
        logging.info(f"Язык не найден для пользователя {user_id}")
        return None


def insert_translation(user_id, translated):
    # Удаляем текст в скобках
    cleaned_translated = re.sub(r'\(.*?\)', '', translated).strip()
    conn = sqlite3.connect('translations.db')
    cursor = conn.cursor()
    cursor.execute('INSERT INTO translations (user_id, translated) VALUES (?, ?)', (user_id, cleaned_translated))
    conn.commit()
    conn.close()


def get_existing_words(user_id):
    conn = sqlite3.connect('translations.db')
    cursor = conn.cursor()
    cursor.execute('SELECT translated FROM translations WHERE user_id = ?', (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return [row[0] for row in rows]


def get_translations(user_id):
    conn = sqlite3.connect('translations.db')
    cursor = conn.cursor()
    cursor.execute('SELECT translated FROM translations WHERE user_id = ?', (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return rows


def insert_generated_word_list(user_id, word_list):
    conn = sqlite3.connect('translations.db')
    cursor = conn.cursor()
    cursor.execute('INSERT INTO generated_word_lists (user_id, word_list) VALUES (?, ?)', (user_id, word_list))
    conn.commit()
    conn.close()


def get_generated_word_lists(user_id):
    conn = sqlite3.connect('translations.db')
    cursor = conn.cursor()
    cursor.execute('SELECT word_list FROM generated_word_lists WHERE user_id = ?', (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return [row[0] for row in rows]


def is_unique_word_list(user_id, new_word_list):
    generated_word_lists = get_generated_word_lists(user_id)
    return new_word_list not in generated_word_lists


def clear_generated_word_lists(user_id):
    conn = sqlite3.connect('translations.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM generated_word_lists WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()


def save_user_topics(user_id, topics):
    logging.info(f"Сохранение тем для пользователя {user_id}: {topics}")
    conn = sqlite3.connect('translations.db')
    cursor = conn.cursor()
    cursor.execute('REPLACE INTO user_topics (user_id, topics) VALUES (?, ?)', (user_id, ','.join(topics)))
    conn.commit()
    conn.close()


def get_user_topics(user_id):
    conn = sqlite3.connect('translations.db')
    cursor = conn.cursor()
    cursor.execute('SELECT topics FROM user_topics WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    conn.close()
    if result:
        topics = result[0].split(',')
        logging.info(f"Получены темы для пользователя {user_id}: {topics}")
        return topics
    else:
        logging.info(f"Темы не найдены для пользователя {user_id}")
        return []


def add_user_topic(user_id, topic):
    topics = get_user_topics(user_id)
    if topic.lower() not in [t.lower() for t in topics]:
        topics.append(topic)
        save_user_topics(user_id, topics)


def remove_user_topic(user_id, topic):
    topics = get_user_topics(user_id)
    topics_lower = [t.lower() for t in topics]
    if topic.lower() in topics_lower:
        index = topics_lower.index(topic.lower())
        topics.pop(index)
        save_user_topics(user_id, topics)


# Исключение предложений
def create_tables():
    conn = sqlite3.connect('user_data.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS issued_offers (
                        user_id INTEGER,
                        offer_text TEXT
                      )''')
    conn.commit()
    conn.close()


def insert_issued_offer(user_id, offer_text):
    conn = sqlite3.connect('user_data.db')
    cursor = conn.cursor()
    cursor.execute('INSERT INTO issued_offers (user_id, offer_text) VALUES (?, ?)', (user_id, offer_text))
    conn.commit()
    conn.close()


def get_issued_offers(user_id):
    conn = sqlite3.connect('user_data.db')
    cursor = conn.cursor()
    cursor.execute('SELECT offer_text FROM issued_offers WHERE user_id = ?', (user_id,))
    issued_offers = cursor.fetchall()
    conn.close()
    return [offer[0] for offer in issued_offers]


# Функция для получения даты последнего выполненного ежедневного задания
def get_daily_last_completed(user_id):
    conn = sqlite3.connect('translations.db')
    cursor = conn.cursor()
    cursor.execute('SELECT daily_last_completed FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None


# Функция для обновления даты последнего выполненного ежедневного задания
def update_daily_last_completed(user_id):
    conn = sqlite3.connect('translations.db')
    cursor = conn.cursor()
    cursor.execute('INSERT OR REPLACE INTO users (user_id, daily_last_completed) VALUES (?, ?)',
                   (user_id, datetime.now().isoformat()))
    conn.commit()
    conn.close()


# Функция для получения даты последнего выполненного еженедельного задания
def get_weekly_last_completed(user_id):
    conn = sqlite3.connect('translations.db')
    cursor = conn.cursor()
    cursor.execute('SELECT weekly_last_completed FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    conn.close()
    if result and result[0]:
        return datetime.fromisoformat(result[0])
    return None


# Функция для обновления даты последнего выполненного еженедельного задания
def update_weekly_last_completed(user_id):
    conn = sqlite3.connect('translations.db')
    cursor = conn.cursor()
    cursor.execute('INSERT OR REPLACE INTO users (user_id, weekly_last_completed) VALUES (?, ?)',
                   (user_id, datetime.now().isoformat()))
    conn.commit()
    conn.close()


# Таблицы списка исключений для диалога
def insert_issued_first_message(user_id, message_text):
    conn = sqlite3.connect('user_data.db')
    cursor = conn.cursor()
    cursor.execute('INSERT INTO issued_first_messages (user_id, message_text) VALUES (?, ?)', (user_id, message_text))
    conn.commit()
    conn.close()


def get_issued_first_messages(user_id):
    conn = sqlite3.connect('user_data.db')
    cursor = conn.cursor()
    cursor.execute('SELECT message_text FROM issued_first_messages WHERE user_id = ?', (user_id,))
    issued_messages = cursor.fetchall()
    conn.close()
    return [msg[0] for msg in issued_messages]


def create_issued_first_messages_table():
    conn = sqlite3.connect('user_data.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS issued_first_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            message_text TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()


def create_users_table():
    conn = sqlite3.connect('translations.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            weekly_last_completed TEXT
        )
    ''')
    conn.commit()
    conn.close()


# Создаем таблицы при запуске
create_issued_first_messages_table()
create_users_table()
create_tables()
init_db()


@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, welcom_massage)
    main_menu(message)


def main_menu(message):
    user_id = message.from_user.id
    language = get_user_language(user_id)

    if not language:
        bot.send_message(message.chat.id, "Кажется Вы у нас новенький, давайте проведём первичную настройку в 2 этапа!")
        bot.send_message(user_id, "Этап 1\nВыберите язык в контекстном меню:", reply_markup=create_language_keyboard())
        set_user_state(user_id, 'changing_language')
        return

    topics = get_user_topics(user_id)

    if not topics:
        bot.send_message(message.chat.id, "Этап 2\nВведите через запятую темы, которые хотите добавить")
        set_user_state(user_id, 'adding_topic')
        return

    keyboard_1 = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
    button1 = types.KeyboardButton(text="Практика по предложениям")
    button2 = types.KeyboardButton(text="Практика по словам")
    button3 = types.KeyboardButton(text="Ежедневное задание")
    button4 = types.KeyboardButton(text="Еженедельное задание")
    button5 = types.KeyboardButton(text="Темы")
    button6 = types.KeyboardButton(text="Язык для обучения")
    keyboard_1.add(button1, button2, button3, button4, button5, button6)

    bot.send_message(message.chat.id, "Вы в главном меню\nВыберите действие:", reply_markup=keyboard_1)


@bot.message_handler(func=lambda message: message.text == "Назад")
def go_back(message):
    reset_user_state(message.from_user.id)
    main_menu(message)


# Обработчик команды "Перевести предложение"
@bot.message_handler(func=lambda message: message.text == "Практика по предложениям")
def menu_1(message):
    set_user_state(message.from_user.id, 'translate_menu')

    keyboard_2 = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
    button4 = types.KeyboardButton(text="Получить предложение")
    button5 = types.KeyboardButton(text="Назад")
    keyboard_2.add(button4, button5)

    bot.reply_to(message, "Начинаем практику с переводом предложений! Подождите немного, подберём для Вас задание.", reply_markup=keyboard_2)

    receiving_an_offer(message)


@bot.message_handler(func=lambda message: message.text == "Получить предложение")
def receiving_an_offer(message):
    set_user_state(message.from_user.id, 'translate')
    global sys_text, offer_text
    # Получаем список уже выданных предложений для текущего пользователя
    issued_offers = get_issued_offers(message.from_user.id)

    # Получаем темы пользователя
    user_topics = get_user_topics(message.from_user.id)

    language = get_user_language(message.from_user.id)



    # Добавляем условие исключения уже выданных предложений и темы пользователя в promt
    sys_text[0][
        "content"] ="The user selected the language " + language + promt_1 +", and set the following topics, randomly select one of them: " + ', '.join(
        user_topics)
    sys_text[0]["content"] += " Eliminate the following offers: " + ", ".join(issued_offers)

    # Логика для ОТПРАВКИ предложения
    res_eng_1 = client.chat.completions.create(model='llama3-70b-8192', messages=sys_text, temperature=0)
    offer_text = res_eng_1.choices[0].message.content
    print(sys_text)
    # Сохраняем новое предложение в базу данных
    insert_issued_offer(message.from_user.id, offer_text)

    # Отправляем предложение пользователю
    bot.send_message(message.chat.id, text=offer_text)
    sys_text[0]["content"] += offer_text

    bot.register_next_step_handler(message, translate_command_1)


def translate_command_1(message):
    global sys_text
    user_input = message.text
    language = get_user_language(message.from_user.id)
    sys_text[0][
        "content"] = "The user has selected the language " + language + "here are instructions for you on how to respond to the user. The text in $ symbols means a message template that you should follow in the situations described in them, the text in % symbols means that you need to enter it yourself instead " + form_1
    sys_text[0]["content"] += "Here is the sentence that needed to be translated:" + offer_text
    sys_text[0]["content"] += "Here is the user's translation:" + user_input
    print(sys_text)

    # Логика для перевода предложения
    res_otv_1 = client.chat.completions.create(model='llama3-70b-8192', messages=sys_text, temperature=0)
    response_text = res_otv_1.choices[0].message.content

    # Проверяем, содержится ли ключевая фраза в ответе
    keyword = "Вот список слов, над которыми Вам нужно поработать:"
    split_point = response_text.find(keyword)

    if split_point != -1:
        # Разделяем текст на две части
        first_part = response_text[:split_point + len(keyword)].strip()
        second_part = response_text[split_point + len(keyword):].strip()

        # Удаление части текста начинающейся с "Вот ваше следующее задание"
        next_task_keyword = "Вот ваше следующее задание"
        next_task_split = second_part.find(next_task_keyword)
        if next_task_split != -1:
            second_part = second_part[:next_task_split].strip()

        # Отправляем первое сообщение
        bot.send_message(message.chat.id, text=first_part)

        # Отправляем второе сообщение
        bot.send_message(message.chat.id, text=second_part)
        # Сохранение в базу данных
        insert_translation(message.from_user.id, second_part)
        bot.send_message(message.chat.id,
                         "Если вы готовы к следующему заданию, нажмите на кнопку Получить предложение в меню, чтобы получить новое задание или нажмите Назад, чтобы верниться в главное меню.")
    else:
        # Если ключевая фраза не найдена, отправляем один ответ целиком
        bot.send_message(message.chat.id, text=response_text)
        bot.send_message(message.chat.id,
                         "Если вы готовы к следующему заданию, нажмите на кнопку Получить предложение в меню, чтобы получить новое задание или нажмите Назад, чтобы вернуться в главное меню.")

    # Сброс состояния после выполнения перевода
    reset_user_state(message.from_user.id)


@bot.message_handler(func=lambda message: message.text == "Практика по словам")
def menu_2(message):
    keyboard_3 = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
    button6 = types.KeyboardButton(text="Получить слова")
    button7 = types.KeyboardButton(text="Назад")
    keyboard_3.add(button6, button7)

    bot.reply_to(message, "Давайте повторим слова, которые вызвали у Вас трудности! ", reply_markup=keyboard_3)

    send_translations(message)


@bot.message_handler(func=lambda message: message.text == "Получить слова")
def send_translations(message):
    global translated_words
    set_user_state(message.from_user.id, 'words')
    translations = get_translations(message.from_user.id)
    if translations:
        all_words = [word[0] for word in translations]

        max_attempts = 5
        attempts = 0
        unique_word_list = None

        while attempts < max_attempts:
            selected_words = random.sample(all_words, min(len(all_words), random.randint(4, 6)))
            combined_text = ". ".join(selected_words)
            if is_unique_word_list(message.from_user.id, combined_text):
                unique_word_list = combined_text
                break
            attempts += 1

        if unique_word_list:
            insert_generated_word_list(message.from_user.id, unique_word_list)
        else:
            clear_generated_word_lists(message.from_user.id)
            send_translations(message)  # Recursive call to retry after clearing
            return

        lines = unique_word_list.split('\n')
        words_and_translations = [line for line in lines if '-' in line]
        formatted_words = "\n".join(words_and_translations)

        sys_text[0]["content"] = promt_2 + ". Вот список слов: " + formatted_words + ". "
        print(sys_text)

        res_eng_2 = client.chat.completions.create(model='llama3-70b-8192', messages=sys_text, temperature=0)
        translated_words = res_eng_2.choices[0].message.content
        bot.send_message(message.chat.id, text=translated_words)
    else:
        bot.send_message(message.chat.id, "У вас нет сохраненных переводов.")

    bot.register_next_step_handler(message, translate_command_2)


def translate_command_2(message):
    user_input = message.text
    language = get_user_language(message.from_user.id)
    sys_text[0]["content"] = ".Here is the list of words that the user had to translate:" + translated_words
    sys_text[0]["content"] += ". Here are the words that the user translated:" + user_input
    sys_text[0][
        "content"] += "The user has selected the language " + language + ". Here are instructions on how you should respond. YOU MUST CHECK THE TRANSLATION OF ALL WORDS IN THE LIST!!! The text in the $ symbols means a message template that you should follow in the situations described in them , the text in % symbols says that you need to enter it yourself instead." + form_2
    print(sys_text)
    res_otv_2 = client.chat.completions.create(model='llama3-70b-8192', messages=sys_text, temperature=0)
    bot.send_message(message.chat.id, text=res_otv_2.choices[0].message.content)
    bot.send_message(message.chat.id,
                     "Если вы готовы повторить материал, нажмите на кнопку 'Получить слова' в меню, чтобы получить новое задание, или нажмите 'Назад'.")

    reset_user_state(message.from_user.id)


# Обработчик команды "Ежедневное задание"
@bot.message_handler(func=lambda message: message.text == "Ежедневное задание")
def daily_task(message):
    if CHECK_TIME:
        last_completed = get_daily_last_completed(message.from_user.id)
        if last_completed and datetime.fromisoformat(last_completed) > datetime.now() - timedelta(days=1):
            bot.send_message(message.chat.id, "Вы уже выполнили ежедневное задание сегодня.")
            return

    bot.send_message(message.chat.id,
                     "Суть ежедневного задания состоит в том, что Вам будет представлен небольшой список слов из тем, которые выбрали ранее, после чего нужно составить предложение на английском языке с одним или несколькими словами."
                     "\nДалее EduLingvo проанализирует его и сделает по нему отчет, чтобы Вы увидели свои преуспевания в изучении языка.")

    set_user_state(message.from_user.id, 'daily_task')
    generate_daily_task(message.from_user.id)


def generate_daily_task(user_id):
    global sys_text, daily_task_text
    user_topics = get_user_topics(user_id)
    language = get_user_language(user_id)
    sys_text = [{"role": "system", "content": ""}]

    # Чтение инструкции для ежедневного задания из файла
    daily_prompt = read_instructions_from_file('daily_task.txt')

    # Формирование запроса к ИИ
    existing_words = get_existing_words(user_id)
    sys_text[0][
        "content"] += "The user has selected a language " + language + daily_prompt + " The user has set the following topics, randomly select one of them: " + ', '.join(
        user_topics)
    sys_text[0][
        "content"] += ". Also here is a list of words that are already in the dictionary and do not need to be used: " + ", ".join(
        existing_words)

    res_eng_words = client.chat.completions.create(model='llama3-70b-8192', messages=sys_text, temperature=0)
    daily_words = res_eng_words.choices[0].message.content

    # Сохраняем слова в базе данных
    insert_translation(user_id, daily_words)

    # Отправляем список слов пользователю
    bot.send_message(user_id,
                     text="Вот ваше ежедневное задание!\nСоставьте одно предложение на английском, используя слова из списка:")
    daily_task_text = f"\n{daily_words}"
    bot.send_message(user_id, text=daily_task_text)

    # Регистрация следующего шага для проверки предложения
    bot.register_next_step_handler_by_chat_id(user_id, check_sentence)


# Анализ предложения
def check_sentence(message):
    global sys_text
    user_id = message.from_user.id
    user_input = message.text
    print(user_input)

    sys_text[0]["content"] = "All your explanations must be in Russian" + daily_task_analysis
    sys_text[0]["content"] += "Here is the user's suggestion:" + user_input
    sys_text[0]["content"] += "Here is the list of words that was given to the user:" + daily_task_text

    analysis = client.chat.completions.create(model='llama3-70b-8192', messages=sys_text, temperature=0)
    analysis_words = analysis.choices[0].message.content

    # Отправляем анализ предложения
    bot.send_message(user_id, text=analysis_words)

    # Обновляем дату последнего выполненного ежедневного задания
    update_daily_last_completed(user_id)

    bot.send_message(user_id, text="Вы завершили ежедневное задание! Отличная работа!")
    main_menu(message)


# Инициализация логирования
logging.basicConfig(level=logging.INFO)


@bot.message_handler(func=lambda message: message.text == "Еженедельное задание")
def weekly_task_menu(message):
    try:
        # Проверка даты последнего выполнения задания
        if CHECK_TIME:
            last_completed_date = get_weekly_last_completed(message.from_user.id)
            if last_completed_date and datetime.fromisoformat(last_completed_date) > datetime.now() - timedelta(
                    weeks=1):
                bot.send_message(message.chat.id,
                                 "Вы уже выполнили еженедельное задание на этой неделе. Попробуйте снова позже.")
                return

        user_id = message.from_user.id
        topics = get_user_topics(user_id)
        if not topics:
            bot.send_message(message.chat.id, "У вас нет сохранённых тем для диалога. Пожалуйста, добавьте темы.")
            return
        bot.send_message(message.chat.id,
                         "Отлично! Суть еженедельного задания заключается в диалоге длинной в 6 сообщений: 3 от EduLingvo и 3 от Вас.\nТут Вы можете проверить свои навыки в симуляции общения с человеком по интересующим Вас темам!")

        choose_topic(message)

        # После выполнения задания обновляем дату последнего выполненного еженедельного задания
        update_weekly_last_completed(user_id)

    except Exception as e:
        logging.error(f"Ошибка в weekly_task_menu: {e}")


def choose_topic(message):
    try:
        user_id = message.from_user.id
        topics = get_user_topics(user_id)
        if not topics:
            bot.send_message(message.chat.id, "У вас нет сохранённых тем для диалога. Пожалуйста, добавьте темы.")
            return

        bot.send_message(message.chat.id, "Диалог будет составляться на основе темы, которую Вы указывали ранее.")

        keyboard = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
        for topic in topics:
            keyboard.add(types.KeyboardButton(text=topic))
        keyboard.add(types.KeyboardButton(text="Назад"))

        bot.send_message(message.chat.id, "Пожалуйста, выберите тему в контекстном меню:", reply_markup=keyboard)
        bot.register_next_step_handler(message, start_weekly_task)

    except Exception as e:
        logging.error(f"Ошибка в choose_topic: {e}")


def start_weekly_task(message):
    global dialog_history
    try:
        set_user_state(message.from_user.id, 'dialogue')
        language = get_user_language(message.from_user.id)
        user_id = message.from_user.id
        selected_topic = message.text
        topics = get_user_topics(user_id)
        if selected_topic not in topics:
            bot.send_message(message.chat.id, "Пожалуйста, выберите корректную тему.")
            return choose_topic(message)

        # Получаем список уже выданных первых сообщений для текущего пользователя
        issued_first_messages = get_issued_first_messages(user_id)

        instruction_text = read_instructions_from_file('dialogue_promt.txt').format(topic=selected_topic)
        dialog_history = [{"role": "system", "content": "User selected language " + language + instruction_text}]

        # Добавляем исключение уже выданных первых сообщений в promt
        exclusion_prompt = " Dialogue should not begin with the following sentences: " + ", ".join(issued_first_messages)
        dialog_history.append({"role": "system", "content": exclusion_prompt})

        bot_reply = \
        client.chat.completions.create(model='llama3-70b-8192', messages=dialog_history, temperature=0).choices[
            0].message.content
        dialog_history.append({"role": "assistant", "content": bot_reply})
        bot.send_message(message.chat.id, bot_reply)

        # Сохраняем новое первое сообщение в базу данных
        insert_issued_first_message(user_id, bot_reply)

        def handle_user_message(user_message):
            global dialog_history
            try:
                user_input = user_message.text
                dialog_history.append({"role": "user", "content": user_input})

                bot_reply = \
                client.chat.completions.create(model='llama3-70b-8192', messages=dialog_history, temperature=0).choices[0].message.content
                dialog_history.append({"role": "assistant", "content": bot_reply})
                bot.send_message(user_message.chat.id, bot_reply)

                if len([msg for msg in dialog_history if msg["role"] == "user"]) < 3:
                    bot.register_next_step_handler(user_message, handle_user_message)
                else:
                    bot.send_message(user_message.chat.id, "Диалог завершен. Спасибо за участие!")
                    # Вызов функции перевода диалога
                    translation_result = translate_dialogue(dialog_history)
                    bot.send_message(user_message.chat.id, translation_result)
                    # Вызов функции анализа диалога
                    analysis_result = analyze_dialogue(dialog_history, user_message)
                    bot.send_message(user_message.chat.id, analysis_result)

                    # Обновляем дату последнего выполнения задания
                    update_weekly_last_completed(user_id)

            except Exception as e:
                logging.error(f"Ошибка в handle_user_message: {e}")

        bot.register_next_step_handler(message, handle_user_message)

    except Exception as e:
        logging.error(f"Ошибка в start_weekly_task: {e}")


def translate_dialogue(dialog_history):
    try:
        # Подготовка текста для перевода, исключая сообщения системы
        text_to_translate = "\n".join(
            [f"{msg['role'].capitalize()}: {msg['content']}" for msg in dialog_history if msg['role'] != 'system'])

        translation_response = client.chat.completions.create(
            model='llama3-70b-8192',
            messages=[{"role": 'user', "content": "Translate the following text into Russian:\n" + text_to_translate}],
            temperature=0
        )

        translated_text = translation_response.choices[0].message.content

        # Подготовка результата перевода
        translated_result = "Перевод вашего диалога:\n\n"
        for line in translated_text.split('\n'):
            if line.startswith("Пользователь:"):
                translated_result += f"Вы: {line.replace('Пользователь:', '').strip()}\n\n"
            elif line.startswith("Ассистент:"):
                translated_result += f"Собеседник: {line.replace('Ассистент:', '').strip()}\n\n"

        return translated_result.strip()

    except Exception as e:
        logging.error(f"Ошибка в translate_dialogue: {e}")
        return "Произошла ошибка при переводе диалога."


def analyze_dialogue(dialog_history, user_message):
    # Прочитать инструкции для анализа из файла
    analysis_instructions = read_instructions_from_file('dialogue_analysis_instructions.txt')

    # Добавить историю диалога к инструкциям, исключая сообщения системы
    analysis_instructions += "\n".join(
        [f"User: {msg['content']}" if msg['role'] == 'user' else f"Assistant: {msg['content']}" for msg in
         dialog_history if msg['role'] != 'system'])

    analysis_response = client.chat.completions.create(
        model='llama3-70b-8192',
        messages=[{"role": 'user', "content": analysis_instructions}],
        temperature=0
    )
    analysis_result = analysis_response.choices[0].message.content.strip()

    bot.send_message(user_message.chat.id, analysis_result)
    bot.send_message(user_message.chat.id, "Вы завершили еженедельное задание! Продолжайте в том же духе!")
    main_menu(user_message)


@bot.message_handler(func=lambda message: message.text == "Темы")
def show_topics_menu(message):
    user_id = message.from_user.id

    topics = get_user_topics(user_id)
    topic_list = '\n'.join(topics)
    bot.reply_to(message, f"Ваши темы:\n{topic_list}")

    keyboard_2 = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
    button_add = types.KeyboardButton(text="Добавить тему")
    button_remove = types.KeyboardButton(text="Удалить тему")
    button_back = types.KeyboardButton(text="Назад")
    keyboard_2.add(button_add, button_remove, button_back)

    bot.send_message(message.chat.id, "Выберите действие:", reply_markup=keyboard_2)


@bot.message_handler(func=lambda message: message.text == "Добавить тему")
def add_topic_prompt(message):
    set_user_state(message.from_user.id, 'adding_topic')
    bot.reply_to(message, "Введите темы, которые хотите добавить:")


@bot.message_handler(func=lambda message: get_user_state(message.from_user.id) == 'adding_topic')
def add_topic(message):
    user_id = message.from_user.id
    new_topics = [topic.strip() for topic in message.text.split(',')]
    current_topics = get_user_topics(user_id)

    for topic in new_topics:
        if topic not in current_topics:
            current_topics.append(topic)

    save_user_topics(user_id, current_topics)

    set_user_state(message.from_user.id, None)
    bot.send_message(message.chat.id, "Ваши темы сохранены! Теперь вы можете получить обучение по этим темам.")
    main_menu(message)


@bot.message_handler(func=lambda message: message.text == "Удалить тему")
def remove_topic_prompt(message):
    set_user_state(message.from_user.id, 'removing_topic')

    user_id = message.from_user.id
    topics = get_user_topics(user_id)
    if topics:
        keyboard = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
        for topic in topics:
            button = types.KeyboardButton(text=topic)
            keyboard.add(button)
        button_back = types.KeyboardButton(text="Назад")
        keyboard.add(button_back)
        bot.send_message(message.chat.id, "Выберите тему, которую хотите удалить:", reply_markup=keyboard)
    else:
        bot.reply_to(message, "У вас нет сохранённых тем.")
        reset_user_state(user_id)
        main_menu(message)


@bot.message_handler(func=lambda message: get_user_state(message.from_user.id) == 'removing_topic')
def handle_topic_removal(message):
    user_id = message.from_user.id
    topic_to_remove = message.text

    current_topics = get_user_topics(user_id)
    current_topics_lower = [t.lower() for t in current_topics]

    if topic_to_remove.lower() in current_topics_lower:
        index = current_topics_lower.index(topic_to_remove.lower())
        current_topics.pop(index)
        current_topics_lower.pop(index)

        save_user_topics(user_id, current_topics)
        bot.send_message(message.chat.id, f"Тема '{topic_to_remove}' удалена!")
    else:
        bot.send_message(message.chat.id, f"Тема '{topic_to_remove}' не найдена!")

    reset_user_state(user_id)
    main_menu(message)


@bot.message_handler(func=lambda message: message.text == "Язык для обучения")
def show_topics_menu(message):
    user_id = message.from_user.id
    language = get_user_language(user_id)
    bot.reply_to(message, f"Вы обучайтесь следующему языку: {language}")
    bot.reply_to(message,
                 "ВННИМАНИЕ! Вы можете изменить язык для обучения на другой в любой момент, но для корректной работы "
                 "нам придётся очистить историю ваших переводов и сохранённых слов, но выбранные Вами темы и прогресс "
                 "выполнения заданий сохранится. Если Вы готовы к этому то нажмите на кнопку Изменить язык.")

    keyboard_3 = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
    button_remove = types.KeyboardButton(text="Изменить язык")
    button_back = types.KeyboardButton(text="Назад")
    keyboard_3.add(button_remove, button_back)

    bot.send_message(message.chat.id, "Выберите действие:", reply_markup=keyboard_3)


# Обработчик кнопки "Изменить язык"
@bot.message_handler(func=lambda message: message.text == "Изменить язык")
def change_language(message):
    user_id = message.from_user.id
    set_user_state(user_id, 'changing_language')
    bot.send_message(user_id, "Выберите язык из списка:", reply_markup=create_language_keyboard())


# Список доступных языков
valid_languages = [
    "английский", "арабский", "испанский", "итальянский",
    "китайский", "корейский", "немецкий", "польский",
    "португальский", "французский", "хинди", "турецкий", "японский"
]


# Функция для создания клавиатуры с языками
def create_language_keyboard():
    keyboard = types.ReplyKeyboardMarkup(row_width=3, one_time_keyboard=True)
    buttons = [types.KeyboardButton(lang.capitalize()) for lang in valid_languages]
    keyboard.add(*buttons)
    return keyboard


# Обработчик изменения языка
@bot.message_handler(func=lambda message: get_user_state(message.from_user.id) == 'changing_language')
def set_language(message):
    user_id = message.from_user.id
    new_language = message.text.strip().lower()

    if new_language in valid_languages:
        save_user_language(user_id, new_language)
        set_user_state(user_id, None)
        bot.send_message(message.chat.id, f"Ваш изучаемый язык установлен на {new_language.capitalize()}.")
        clear_user_data(user_id)
        main_menu(message)


def clear_user_data(user_id):
    # Очистка данных из таблицы translations.db
    conn_translations = sqlite3.connect('translations.db')
    cursor_translations = conn_translations.cursor()

    # Очистка таблицы translations
    cursor_translations.execute('DELETE FROM translations WHERE user_id = ?', (user_id,))

    # Очистка таблицы generated_word_lists
    cursor_translations.execute('DELETE FROM generated_word_lists WHERE user_id = ?', (user_id,))

    conn_translations.commit()
    conn_translations.close()

    # Очистка данных из таблицы user_data.db
    conn_user_data = sqlite3.connect('user_data.db')
    cursor_user_data = conn_user_data.cursor()

    # Очистка таблицы issued_first_messages
    cursor_user_data.execute('DELETE FROM issued_first_messages WHERE user_id = ?', (user_id,))

    # Очистка таблицы issued_offers
    cursor_user_data.execute('DELETE FROM issued_offers WHERE user_id = ?', (user_id,))

    conn_user_data.commit()
    conn_user_data.close()

    # Очистка данных из таблицы users, кроме столбцов daily_last_completed и weekly_last_completed
    conn_users = sqlite3.connect('translations.db')
    cursor_users = conn_users.cursor()

    cursor_users.execute('DELETE FROM users WHERE user_id = ?', (user_id,))

    conn_users.commit()
    conn_users.close()


# Запускаем бота
bot.polling()
