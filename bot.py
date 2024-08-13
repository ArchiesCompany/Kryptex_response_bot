import json
import logging
import os
from datetime import datetime
from telegram import Update
from telegram.ext import Updater, CommandHandler, Filters, MessageHandler, CallbackContext

# Настройка логирования с созданием нового файла лога при каждом запуске.
if not os.path.exists('logs'):
    os.makedirs('logs')

log_filename = f"logs/bot_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.log"
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler(log_filename),  # Логи будут сохраняться в новый файл при каждом запуске
        logging.StreamHandler()  # Также логи будут выводиться в консоль
    ]
)
logger = logging.getLogger(__name__)

# Загрузка конфигурационного файла, который содержит токен и другие настройки
with open('config.json', 'r', encoding='utf-8') as f:
    config = json.load(f)
    BOT_TOKEN = config['bot_token']

# Загружаем список администраторов и модераторов из отдельных файлов
with open('admins.json', 'r', encoding='utf-8') as f:
    ADMINS = json.load(f)

with open('mods.json', 'r', encoding='utf-8') as f:
    MODERATORS = json.load(f)

# Загружаем список команд из конфигурационного файла
with open('commands.json', 'r', encoding='utf-8') as f:
    COMMANDS = json.load(f)

def is_admin(user_id: int) -> bool:
    """Проверка, является ли пользователь администратором."""
    return user_id in ADMINS

def is_moderator(user_id: int) -> bool:
    """Проверка, является ли пользователь модератором."""
    return user_id in MODERATORS

def handle_command(update: Update, context: CallbackContext):
    """Обработка команд от администраторов и модераторов."""
    user_id = update.effective_user.id
    command = update.message.text.split()[0]  # Извлечение команды

    # Проверка прав пользователя
    if is_admin(user_id) or is_moderator(user_id):
        response = COMMANDS.get(command)
        if response:
            context.bot.send_message(chat_id=update.effective_chat.id, text=response, parse_mode='Markdown')
            context.bot.delete_message(chat_id=update.effective_chat.id, message_id=update.message.message_id)  # Удаление команды из чата
            logger.info(f"Command {command} executed by user {user_id}")
    else:
        logger.warning(f"Unauthorized command attempt by user {user_id}")
        return

def add_command(update: Update, context: CallbackContext):
    """Добавление новой команды (только для администраторов)."""
    user_id = update.effective_user.id

    if not is_admin(user_id):
        logger.warning(f"Unauthorized add_command attempt by user {user_id}")
        return

    if len(context.args) < 2:
        update.message.reply_text('Usage: /add_command <command> <response>')
        return

    command = context.args[0]
    response = ' '.join(context.args[1:])  # Собираем весь текст сообщения как ответ

    # Сохраняем команду и её ответ
    COMMANDS[command] = response

    # Обновление конфигурационного файла с командами
    with open('commands.json', 'w', encoding='utf-8') as f:
        json.dump(COMMANDS, f, ensure_ascii=False, indent=4)
    
    update.message.reply_text(f'Command {command} added.')
    logger.info(f"Command {command} added by admin {user_id}")

def remove_command(update: Update, context: CallbackContext):
    """Удаление существующей команды (только для администраторов)."""
    user_id = update.effective_user.id

    if not is_admin(user_id):
        logger.warning(f"Unauthorized remove_command attempt by user {user_id}")
        return

    if len(context.args) != 1:
        update.message.reply_text('Usage: /remove_command <command>')
        return

    command = context.args[0]

    if command in COMMANDS:
        del COMMANDS[command]

        # Обновление конфигурационного файла с командами
        with open('commands.json', 'w', encoding='utf-8') as f:
            json.dump(COMMANDS, f, ensure_ascii=False, indent=4)
        
        update.message.reply_text(f'Command {command} removed.')
        logger.info(f"Command {command} removed by admin {user_id}")
    else:
        update.message.reply_text(f'Command {command} does not exist.')

def list_commands(update: Update, context: CallbackContext):
    """Вывод списка всех доступных команд (доступно для администраторов и модераторов)."""
    user_id = update.effective_user.id

    if is_admin(user_id) or is_moderator(user_id):
        commands_list = "\n".join([
            "/add_command <command> <response> - Add a new command (Admins only)",
            "/remove_command <command> - Remove an existing command (Admins only)",
            "/assign <admin|moderator> <add|remove> <user_id> - Assign roles (Admins only)",
            "/help - Show this help message",
            "Custom Commands:\n" + "\n".join(f"{cmd} - {resp}" for cmd, resp in COMMANDS.items())
        ])
        update.message.reply_text(f"Available commands:\n{commands_list}")
        logger.info(f"Command list requested by user {user_id}")
    else:
        logger.warning(f"Unauthorized help command attempt by user {user_id}")

def view_roles(update: Update, context: CallbackContext):
    """Вывод списка администраторов и модераторов (доступно только для администраторов)."""
    user_id = update.effective_user.id

    if is_admin(user_id):
        admins_list = "\n".join(str(admin) for admin in ADMINS) or "No admins."
        moderators_list = "\n".join(str(moderator) for moderator in MODERATORS) or "No moderators."

        response = (f"Admins:\n{admins_list}\n\n"
                    f"Moderators:\n{moderators_list}")
        update.message.reply_text(response)
        logger.info(f"Roles list requested by user {user_id}")
    else:
        logger.warning(f"Unauthorized view_roles command attempt by user {user_id}")

def assign_role(update: Update, context: CallbackContext):
    """Назначение роли (администратор или модератор) пользователю (доступно только для администраторов)."""
    user_id = update.effective_user.id

    if not is_admin(user_id):
        logger.warning(f"Unauthorized assign_role attempt by user {user_id}")
        return

    if len(context.args) != 3:
        update.message.reply_text('Usage: /assign <admin|moderator> <add|remove> <user_id>')
        return

    role, action, target_id = context.args[0], context.args[1], int(context.args[2])

    if role == 'admin':
        if action == 'add':
            if target_id not in ADMINS:
                ADMINS.append(target_id)
                with open('admins.json', 'w', encoding='utf-8') as f:
                    json.dump(ADMINS, f, ensure_ascii=False, indent=4)
                update.message.reply_text(f'User {target_id} added as admin.')
                logger.info(f"User {target_id} added as admin by {user_id}")
            else:
                update.message.reply_text(f'User {target_id} is already an admin.')
        elif action == 'remove':
            if target_id in ADMINS:
                ADMINS.remove(target_id)
                with open('admins.json', 'w', encoding='utf-8') as f:
                    json.dump(ADMINS, f, ensure_ascii=False, indent=4)
                update.message.reply_text(f'User {target_id} removed from admins.')
                logger.info(f"User {target_id} removed from admins by {user_id}")
            else:
                update.message.reply_text(f'User {target_id} is not an admin.')
        else:
            update.message.reply_text('Invalid action. Use "add" or "remove".')
    elif role == 'moderator':
        if action == 'add':
            if target_id not in MODERATORS:
                MODERATORS.append(target_id)
                with open('mods.json', 'w', encoding='utf-8') as f:
                    json.dump(MODERATORS, f, ensure_ascii=False, indent=4)
                update.message.reply_text(f'User {target_id} added as moderator.')
                logger.info(f"User {target_id} added as moderator by {user_id}")
            else:
                update.message.reply_text(f'User {target_id} is already a moderator.')
        elif action == 'remove':
            if target_id in MODERATORS:
                MODERATORS.remove(target_id)
                with open('mods.json', 'w', encoding='utf-8') as f:
                    json.dump(MODERATORS, f, ensure_ascii=False, indent=4)
                update.message.reply_text(f'User {target_id} removed from moderators.')
                logger.info(f"User {target_id} removed from moderators by {user_id}")
            else:
                update.message.reply_text(f'User {target_id} is not a moderator.')
        else:
            update.message.reply_text('Invalid action. Use "add" or "remove".')
    else:
        update.message.reply_text('Invalid role. Use "admin" or "moderator".')

def main():
    """Основная функция для запуска бота."""
    updater = Updater(token=BOT_TOKEN, use_context=True)
    dp = updater.dispatcher

    # Обработчики команд
    dp.add_handler(CommandHandler('add_command', add_command, Filters.user(user_id=ADMINS)))
    dp.add_handler(CommandHandler('remove_command', remove_command, Filters.user(user_id=ADMINS)))
    dp.add_handler(CommandHandler('help', list_commands, Filters.user(user_id=ADMINS + MODERATORS)))
    dp.add_handler(CommandHandler('assign', assign_role, Filters.user(user_id=ADMINS)))
    dp.add_handler(CommandHandler('view_roles', view_roles, Filters.user(user_id=ADMINS)))

    # Обработчик для всех команд
    dp.add_handler(MessageHandler(Filters.command, handle_command))

    # Запуск бота
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
