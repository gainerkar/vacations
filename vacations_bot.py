from telegram import Update, BotCommand
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import datetime
import json
import os
import re

DATA_FILE = 'vacations.json'


def load_data() -> dict:
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def save_data(data: dict) -> None:
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def escape_markdown(text: str) -> str:
    return re.sub(r'([_\*\[\]\(\)\~\`\>\#\+\-\=\|\{\}\.\!])', r'\\\1', text)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(
        "🛫 Приветствую! Хочешь запланировать отпуск и по-настоящему отдохнуть? "
        "Введите <code>/otpusk YYYY-MM-DD ДНИ</code>, "
        "например <code>/otpusk 2025-08-01 10</code> — и вперед, навстречу приключениям! 🌴",
        parse_mode=ParseMode.HTML
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "<b>Инструкция по отпускному боту:</b>\n\n"
        "1️⃣ <code>/otpusk YYYY-MM-DD ДНИ</code> — добавить новый отпуск.\n"
        "2️⃣ <code>/myvacation</code> — показать ваши отпуска.\n"
        "3️⃣ <code>/delvacation YYYY-MM-DD</code> — удалить отпуск.\n"
        "4️⃣ <code>/allvacations</code> — список отпусков всех участников.\n\n"
        "Если что-то непонятно — задавайте вопросы! 😊"
    )
    await update.effective_message.reply_text(
        text,
        parse_mode=ParseMode.HTML
    )


async def set_vacation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    if len(context.args) < 2:
        await msg.reply_text(
            "⚠️ Формат команды: <code>/otpusk YYYY-MM-DD ДНИ</code>. Пожалуйста, укажи дату и количество дней.",
            parse_mode=ParseMode.HTML
        )
        return

    date_str, length_str = context.args[0], context.args[1]

    # Парсинг даты
    try:
        start_date = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        await msg.reply_text(
            "❗ Дата должна быть в формате YYYY-MM-DD, например <code>2025-08-01</code>.",
            parse_mode=ParseMode.HTML
        )
        return

    if start_date.year > 2099:
        await msg.reply_text(
            "🚀 Планировать отпуск дальше 2099 года — слишком смело, давай попроще.",
            parse_mode=ParseMode.HTML
        )
        return

    # Парсинг длины отпуска
    try:
        length = int(length_str)
        if length < 1 or length > 365:
            raise ValueError
    except ValueError:
        await msg.reply_text(
            "❗ Дни должны быть числом от 1 до 365. Проверь ввод.",
            parse_mode=ParseMode.HTML
        )
        return

    today = datetime.date.today()
    if start_date <= today:
        await msg.reply_text(
            "⏰ Отпуск можно начать не раньше, чем завтра.",
            parse_mode=ParseMode.HTML
        )
        return

    user = update.effective_user
    chat = update.effective_chat
    data = load_data()
    uid = str(user.id)

    if uid not in data:
        data[uid] = {
            "vacations": [],
            "chat_id": chat.id,
            "username": user.username or user.first_name
        }
    else:
        data[uid]["chat_id"] = chat.id
        data[uid].setdefault("vacations", [])

    # Проверка на повтор
    if any(v["start"] == start_date.isoformat() for v in data[uid]["vacations"]):
        await msg.reply_text(
            "✅ Ты уже добавлял отпуск на эту дату. Ничего не меняем.",
            parse_mode=ParseMode.HTML
        )
        return

    data[uid]["vacations"].append({
        "start": start_date.isoformat(),
        "length": length
    })
    data[uid]["vacations"].sort(key=lambda v: v["start"])
    save_data(data)

    await msg.reply_text(
        f"🎉 Ура! Отпуск с {start_date} на {length} дней успешно добавлен.",
        parse_mode=ParseMode.HTML
    )


async def my_vacation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    msg = update.effective_message
    data = load_data()
    vacs = data.get(str(user.id), {}).get("vacations", [])

    if not vacs:
        await msg.reply_text(
            "🤷 У тебя пока нет запланированных отпусков.",
            parse_mode=ParseMode.HTML
        )
        return

    today = datetime.date.today()
    response = f"✈️ Ваши отпуска, @{user.username or user.first_name}:\n"
    for v in vacs:
        start = datetime.datetime.strptime(v["start"], '%Y-%m-%d').date()
        length = int(v["length"])
        end = start + datetime.timedelta(days=length - 1)

        if start > today:
            days_to = (start - today).days
            response += f"• Начало: {start} (через {days_to} дн.), длительность {length} дн.\n"
        elif start <= today <= end:
            days_left = (end - today).days + 1
            response += f"• Сейчас в отпуске: осталось {days_left} дн. (с {start} по {end}).\n"
        else:
            response += f"• Завершён отпуск с {start} по {end}.\n"

    await msg.reply_text(response, parse_mode=ParseMode.HTML)


async def delete_vacation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message

    if not context.args:
        await msg.reply_text(
            "⚠️ Укажи дату удаления: <code>/delvacation YYYY-MM-DD</code>.",
            parse_mode=ParseMode.HTML
        )
        return

    try:
        date_iso = datetime.datetime.strptime(context.args[0], '%Y-%m-%d').date().isoformat()
    except ValueError:
        await msg.reply_text(
            "❗ Формат даты: YYYY-MM-DD, например <code>2025-08-01</code>.",
            parse_mode=ParseMode.HTML
        )
        return

    data = load_data()
    uid = str(update.effective_user.id)
    vacs = data.get(uid, {}).get("vacations", [])
    new_list = [v for v in vacs if v["start"] != date_iso]

    if len(new_list) == len(vacs):
        await msg.reply_text(
            "🔍 Отпуск на эту дату не найден.",
            parse_mode=ParseMode.HTML
        )
        return

    data[uid]["vacations"] = new_list
    save_data(data)
    await msg.reply_text(
        f"✅ Отпуск <code>{date_iso}</code> удалён.",
        parse_mode=ParseMode.HTML
    )


async def all_vacations(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    msg = update.effective_message
    data = load_data()
    today = datetime.date.today()
    users = []

    for uid, info in data.items():
        if info.get("chat_id") != chat.id:
            continue
        for v in info.get("vacations", []):
            start = datetime.datetime.strptime(v["start"], '%Y-%m-%d').date()
            length = int(v["length"])
            end = start + datetime.timedelta(days=length - 1)
            if end < today:
                continue
            days_to = (start - today).days
            users.append((info.get("username", "неизвестный"), days_to, start, length))

    if not users:
        await msg.reply_text(
            "🤷 Никто не запланировал отпуск в этом чате.",
            parse_mode=ParseMode.HTML
        )
        return

    users.sort(key=lambda x: x[1])
    response = "🏖️ Ближайшие отпуска участников:\n"
    for name, days_to, start, length in users:
        if days_to > 0:
            response += f"• {name}: через {days_to} дн., старт {start}, длительность {length} дн.\n"
        else:
            response += f"• {name}: сегодня стартует отпуск! Длительность {length} дн.\n"

    await msg.reply_text(response, parse_mode=ParseMode.HTML)


async def vacation_reminder(context: ContextTypes.DEFAULT_TYPE) -> None:
    data = load_data()
    today = datetime.date.today()
    updated = {}

    for uid, info in data.items():
        chat_id = info.get("chat_id")
        name = info.get("username", "друг")
        valid = []
        for v in info.get("vacations", []):
            start = datetime.datetime.strptime(v["start"], '%Y-%m-%d').date()
            length = int(v["length"])
            end = start + datetime.timedelta(days=length - 1)

            if (start - today).days == 7:
                try:
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text=(
                            f"🔔 Привет, {name}! Через 7 дней у тебя отпуск "
                            f"с {start} на {length} дн. Не забудь собрать чемодан!"
                        ),
                        parse_mode=ParseMode.HTML
                    )
                except Exception as e:
                    print(f"Ошибка при отправке напоминания: {e}")

            if end >= today:
                valid.append(v)

        if valid:
            info["vacations"] = valid
            updated[uid] = info

    save_data(updated)


async def on_startup(app):
    commands = [
        BotCommand("start",       "Запустить бота и узнать функционал"),
        BotCommand("help",        "Показать эту справку"),
        BotCommand("otpusk",      "Добавить отпуск: /otpusk YYYY-MM-DD ДНИ"),
        BotCommand("myvacation",  "Показать ваши отпуска"),
        BotCommand("delvacation", "Удалить отпуск: /delvacation YYYY-MM-DD"),
        BotCommand("allvacations","Показать отпуска всех участников"),
    ]
    await app.bot.set_my_commands(commands)


def main() -> None:
    TOKEN = 'token'
    builder = ApplicationBuilder().token(TOKEN)
    builder.post_init(on_startup)
    app = builder.build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("otpusk", set_vacation))
    app.add_handler(CommandHandler("myvacation", my_vacation))
    app.add_handler(CommandHandler("delvacation", delete_vacation))
    app.add_handler(CommandHandler("allvacations", all_vacations))

    app.job_queue.run_repeating(
        callback=vacation_reminder,
        interval=86400,
        first=0
    )

    app.run_polling()


if __name__ == '__main__':
    main()
