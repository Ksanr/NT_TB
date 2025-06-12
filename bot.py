import random
from telebot import types, TeleBot, State
from telebot.states import StatesGroup
from telebot.storage import StateMemoryStorage
from models import SessionLocal, User, Word
from dotenv import load_dotenv
from sqlalchemy import distinct
import os, json

load_dotenv()
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
bot = TeleBot(TOKEN)
session = SessionLocal()

state_storage = StateMemoryStorage()
buttons = []


def show_hint(*lines):
    return '\n'.join(lines)


def show_target(data):
    return f"{data['target_word']} -> {data['translate_word']}"


class Command:
    ADD_WORD = 'Добавить слово ➕'
    DELETE_WORD = 'Удалить слово🔙'
    NEXT = 'Дальше ⏭'


class MyStates(StatesGroup):
    target_word = State()
    translate_word = State()
    another_words = State()


def get_user(message):
    """Получаем пользователя по ID"""
    return session.query(User).filter_by(telegram_id=str(message.from_user.id)).first()


def add_word(user, new_word, translation):
    """Добавляем новое слово в словарь пользователя"""
    if not any(word.word.lower() == new_word.lower() for word in user.words):
        new_entry = Word(word=new_word, translation=translation, user=user)
        session.add(new_entry)
        session.commit()
        bot.send_message(user.telegram_id, f"Слово '{new_word}' успешно добавлено!")
    else:
        bot.send_message(user.telegram_id, f"Слово '{new_word}' уже существует.")


def get_random_word(user_id):
    active_words = session.query(Word).filter_by(user_id=user_id).all()

    russian_words = []
    translates = []
    for rw in active_words:
        russian_words.extend([rw.word] * rw.freq)
        translates.extend([rw.translation] * rw.freq)
    if not russian_words:
        return None

    rnd = random.randint(0, len(russian_words) - 1)
    russian_word = russian_words[rnd]
    target_word = translates[rnd]
    return russian_word, target_word


def get_another_words(active_word):
    another_words = [word[0] for word in session.query(distinct(Word.translation)).all()]
    if active_word in another_words:
        another_words.remove(active_word)
    random.shuffle(another_words)
    return another_words[:3]


def guess_word(message):
    user_id = message.from_user.id
    markup = types.ReplyKeyboardMarkup(row_width=2)
    bd_words = get_random_word(user_id)
    global buttons

    if bd_words:
        russian_word, target_word = bd_words
        other_words = get_another_words(target_word)
        target_word_btn = types.KeyboardButton(target_word)
        other_words_btns = [types.KeyboardButton(word) for word in other_words]

        buttons = [target_word_btn] + other_words_btns
        random.shuffle(buttons)

        next_btn = types.KeyboardButton(Command.NEXT)
        add_word_btn = types.KeyboardButton(Command.ADD_WORD)
        delete_word_btn = types.KeyboardButton(Command.DELETE_WORD)
        buttons.extend([next_btn, add_word_btn, delete_word_btn])

        markup.add(*buttons)
        bot.send_message(message.chat.id, f'Угадай слово "{russian_word}"', reply_markup=markup)

        bot.set_state(message.from_user.id, MyStates.target_word, message.chat.id)
        with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
            data['target_word'] = target_word
            data['translate_word'] = russian_word
            data['other_words'] = other_words
    else:
        buttons = [types.KeyboardButton(Command.ADD_WORD)]
        markup.add(*buttons)
        bot.send_message(message.chat.id, f'Отсутствуют слова для повторения', reply_markup=markup)


def create_new_user(user_id):
    new_user = User(telegram_id=user_id)
    session.add(new_user)
    session.commit()

    with open("BaseWord.json", "r") as json_file:
        data = json.load(json_file)
    for en_word, ru_word in data.items():
        new_entry = Word(word=ru_word, translation=en_word, user_id=user_id)
        session.add(new_entry)
        session.commit()


@bot.message_handler(commands=['cards', 'start'])
def start_command(message):
    """Команда /start"""
    user = get_user(message)

    if not user:
        create_new_user(message.from_user.id)
        bot.reply_to(message, "Привет! Ты новый пользователь. Давай начнем изучение новых слов.")
    else:
        bot.reply_to(message, "Привет снова! Продолжим изучать английский.")
    guess_word(message)


@bot.message_handler(func=lambda message: message.text == Command.NEXT)
def next_cards(message):
    """Команда для вывода следующего слова"""
    guess_word(message)


@bot.message_handler(func=lambda message: message.text == Command.DELETE_WORD)
def delete_word(message):
    with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
        word = session.query(Word).filter_by(user_id=message.from_user.id, word=data['translate_word']).first()

        word.freq = 0
        session.commit()


@bot.message_handler(commands=['ADD_WORD'])
def add_word_command(message):
    """Команда добавления нового слова"""
    try:
        _, word, translation = message.text.split(maxsplit=2)
        user = get_user(message)
        add_word(user, word.strip(), translation.strip())
    except ValueError:
        bot.reply_to(message, "Используйте команду правильно: /ADD_WORD your_word your_translation")


@bot.message_handler(func=lambda message: message.text == Command.ADD_WORD)
def add_word_command(message):
    msg = bot.reply_to(message, 'Введите слово на русском языке:')
    bot.register_next_step_handler(msg, process_add_word_step_2)


def process_add_word_step_2(message):
    ru_word = message.text.strip().lower()
    word = session.query(Word).filter_by(user_id=message.from_user.id, word=ru_word).first()
    if word:
        word.freq = 10
        session.commit()
        markup = types.ReplyKeyboardMarkup(row_width=2)
        next_btn = types.KeyboardButton(Command.NEXT)
        add_word_btn = types.KeyboardButton(Command.ADD_WORD)
        # delete_word_btn = types.KeyboardButton(Command.DELETE_WORD)
        buttons = [next_btn, add_word_btn]

        markup.add(*buttons)
        bot.reply_to(message, f"Частота вывода слова '{ru_word}' восстановлена на исходное значение!",
                     reply_markup=markup)
    else:
        msg = bot.reply_to(message, "Теперь введите перевод на английский язык:")
        bot.register_next_step_handler(msg, lambda m: save_new_word(m, ru_word))


def save_new_word(message, ru_word):
    translation = message.text.strip().lower()
    new_word = Word(user_id=message.from_user.id, word=ru_word, translation=translation)
    session.add(new_word)
    session.commit()
    markup = types.ReplyKeyboardMarkup(row_width=2)
    next_btn = types.KeyboardButton(Command.NEXT)
    add_word_btn = types.KeyboardButton(Command.ADD_WORD)
    # delete_word_btn = types.KeyboardButton(Command.DELETE_WORD)
    buttons = [next_btn, add_word_btn]

    markup.add(*buttons)
    bot.send_message(message.chat.id, f"Слово '{ru_word}' успешно добавлено!", reply_markup=markup)


@bot.message_handler(func=lambda message: True, content_types=['text'])
def message_reply(message):
    text = message.text
    user_id = message.from_user.id
    markup = types.ReplyKeyboardMarkup(row_width=2)

    with bot.retrieve_data(user_id, message.chat.id) as data:
        target_word = data['target_word']
        russian_word = data['translate_word']
        word = session.query(Word).filter_by(user_id=user_id, word=russian_word).first()
        freq = word.freq
        if text == target_word:
            hint = show_target(data)
            hint_text = ["Отлично!❤", hint]

            word.total_cnt_guessed += 1
            cnt_guessed = word.cnt_guessed + 1
            cnt_error = 0
            if (freq > 9 and cnt_guessed >= 3) or (freq and cnt_guessed >= 3 * (11 - freq)):
                cnt_guessed = 0
                freq -= 1
            # next_btn = types.KeyboardButton(Command.NEXT)
            # add_word_btn = types.KeyboardButton(Command.ADD_WORD)
            # delete_word_btn = types.KeyboardButton(Command.DELETE_WORD)
            # buttons.extend([next_btn, add_word_btn, delete_word_btn])
            hint = show_hint(*hint_text)
        else:

            word.total_cnt_error += 1
            cnt_error = word.cnt_error + 1
            cnt_guessed = 0
            if cnt_error >= 3 * freq:
                cnt_error = 0
                freq += 1

            for btn in buttons:
                if btn.text == text:
                    if '❌' not in btn.text:
                        btn.text = text + '❌'
                    break
            hint = show_hint("Допущена ошибка!",
                             f"Попробуй ещё раз вспомнить слово 🇷🇺{russian_word}")
    word.freq = freq
    word.cnt_error = cnt_error
    word.cnt_guessed = cnt_guessed

    session.commit()

    markup.add(*buttons)
    bot.send_message(message.chat.id, hint, reply_markup=markup)


if __name__ == '__main__':
    print("Запускаю бот...")
    bot.polling(none_stop=True)
