import os
import logging
import asyncio
from datetime import datetime, time
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from database import init_db, get_session
from models import User, Question, UserAnswer
from sqlalchemy import select, func
import random
import json

# Налаштування логування
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Завантаження змінних середовища
load_dotenv()
TOKEN = os.getenv('TELEGRAM_TOKEN')

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обробник команди /start"""
    # Перевіряємо чи користувач вже зареєстрований
    async for session in get_session():
        user = await session.execute(select(User).filter(User.telegram_id == update.effective_user.id))
        user = user.scalar_one_or_none()
        
        if user:
            # Якщо користувач вже зареєстрований, показуємо головне меню
            keyboard = [
                ["📝 Щоденний тест"],
                ["📊 Статистика", "📚 База знань"],
                ["🎮 Почати гру"]
            ]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            await update.message.reply_text(
                "Вітаю! Я бот для навчання персоналу Країна Мрій. Оберіть опцію:",
                reply_markup=reply_markup
            )
        else:
            # Якщо користувач не зареєстрований, починаємо реєстрацію
            await update.message.reply_text(
                "Вітаю! Для початку роботи потрібно зареєструватися.\n"
                "Будь ласка, введіть ваше ім'я:"
            )
            context.user_data['registration_step'] = 'name'

async def handle_registration(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обробник покрокової реєстрації"""
    step = context.user_data.get('registration_step')
    
    if not step:
        return
        
    if step == 'name':
        context.user_data['name'] = update.message.text
        await update.message.reply_text("Тепер введіть ваше прізвище:")
        context.user_data['registration_step'] = 'surname'
        
    elif step == 'surname':
        context.user_data['surname'] = update.message.text
        await update.message.reply_text("Введіть вашу посаду:")
        context.user_data['registration_step'] = 'position'
        
    elif step == 'position':
        context.user_data['position'] = update.message.text
        await update.message.reply_text("Введіть назву закладу:")
        context.user_data['registration_step'] = 'establishment'
        
    elif step == 'establishment':
        try:
            # Зберігаємо всі дані в базу
            full_name = f"{context.user_data['name']} {context.user_data['surname']}"
            async for session in get_session():
                user = User(
                    telegram_id=update.effective_user.id,
                    full_name=full_name,
                    city=update.message.text,  # Використовуємо назву закладу як місто
                    position=context.user_data['position']
                )
                session.add(user)
                await session.commit()
            
            # Показуємо головне меню
            keyboard = [
                ["📝 Щоденний тест"],
                ["📊 Статистика", "📚 База знань"],
                ["🎮 Почати гру"]
            ]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            await update.message.reply_text(
                "Реєстрація успішна! Тепер ви можете користуватися всіма функціями бота.",
                reply_markup=reply_markup
            )
            
            # Очищаємо дані реєстрації
            context.user_data.clear()
        except Exception as e:
            await update.message.reply_text(
                "Помилка при реєстрації. Будь ласка, спробуйте ще раз, використовуючи команду /start"
            )
            context.user_data.clear()

async def send_daily_questions():
    """Відправка щоденних питань"""
    async for session in get_session():
        users = await session.execute(select(User))
        for user in users.scalars():
            # Отримання випадкових питань
            questions = await session.execute(
                select(Question).order_by(func.random()).limit(5)
            )
            questions = questions.scalars().all()
            
            # Відправка питань користувачу
            for i, question in enumerate(questions, 1):
                keyboard = [
                    [InlineKeyboardButton(question.correct_answer, callback_data=f'answer_{question.id}_correct')],
                    [InlineKeyboardButton("Показати пояснення", callback_data=f'explain_{question.id}')]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                # TODO: Відправка повідомлення користувачу через бота
                # await context.bot.send_message(
                #     chat_id=user.telegram_id,
                #     text=f"Питання {i}/5:\n{question.text}",
                #     reply_markup=reply_markup
                # )

async def handle_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обробник відповіді на питання"""
    query = update.callback_query
    await query.answer()
    
    # Отримання ID питання з callback_data
    question_id = int(query.data.split('_')[1])
    
    async for session in get_session():
        question = await session.execute(select(Question).filter(Question.id == question_id))
        question = question.scalar_one_or_none()
        
        if question:
            # Збереження відповіді
            user = await session.execute(select(User).filter(User.telegram_id == update.effective_user.id))
            user = user.scalar_one_or_none()
            
            if user:
                answer = UserAnswer(
                    user_id=user.id,
                    question_id=question.id,
                    answer=query.data,
                    is_correct=True
                )
                session.add(answer)
                await session.commit()
                
                # Оновлення статистики
                user.daily_score += 1
                user.total_score += 1
                await session.commit()
                
                await query.message.reply_text("Правильно! +1 бал")
            else:
                await query.message.reply_text("Будь ласка, зареєструйтесь спочатку")

async def show_explanation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показ пояснення до відповіді"""
    query = update.callback_query
    await query.answer()
    
    question_id = int(query.data.split('_')[1])
    
    async for session in get_session():
        question = await session.execute(select(Question).filter(Question.id == question_id))
        question = question.scalar_one_or_none()
        
        if question:
            await query.message.reply_text(f"Пояснення: {question.explanation}")

async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показ статистики користувача"""
    query = update.callback_query
    await query.answer()
    
    async for session in get_session():
        user = await session.execute(select(User).filter(User.telegram_id == update.effective_user.id))
        user = user.scalar_one_or_none()
        
        if user:
            stats_text = (
                f"Статистика користувача {user.full_name}:\n"
                f"Щоденний рахунок: {user.daily_score}\n"
                f"Загальний рахунок: {user.total_score}\n"
                f"Місто: {user.city}\n"
                f"Посада: {user.position}"
            )
            await query.message.reply_text(stats_text)
        else:
            await query.message.reply_text("Будь ласка, зареєструйтесь спочатку")

async def show_knowledge_base(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показ бази знань"""
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("Сервіс", callback_data='kb_service')],
        [InlineKeyboardButton("Меню", callback_data='kb_menu')],
        [InlineKeyboardButton("Безпека", callback_data='kb_safety')],
        [InlineKeyboardButton("Кулінарія", callback_data='kb_cooking')],
        [InlineKeyboardButton("Етикет", callback_data='kb_etiquette')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.message.reply_text(
        "Оберіть категорію для перегляду:",
        reply_markup=reply_markup
    )

async def show_knowledge_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показ інформації з обраної категорії"""
    query = update.callback_query
    await query.answer()
    
    category = query.data.split('_')[1]
    
    # TODO: Додати інформацію для кожної категорії
    category_info = {
        'service': "Інформація про сервіс...",
        'menu': "Інформація про меню...",
        'safety': "Інформація про безпеку...",
        'cooking': "Інформація про кулінарію...",
        'etiquette': "Інформація про етикет..."
    }
    
    await query.message.reply_text(category_info.get(category, "Інформація відсутня"))

async def start_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Початок процесу зворотного зв'язку"""
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("Оцінити навчання", callback_data='feedback_learning')],
        [InlineKeyboardButton("Оцінити оновлення меню", callback_data='feedback_menu')],
        [InlineKeyboardButton("Запропонувати покращення", callback_data='feedback_suggest')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.message.reply_text(
        "Оберіть тип зворотного зв'язку:",
        reply_markup=reply_markup
    )

async def handle_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обробка зворотного зв'язку"""
    query = update.callback_query
    await query.answer()
    
    feedback_type = query.data.split('_')[1]
    
    if feedback_type == 'learning':
        keyboard = [
            [InlineKeyboardButton("1", callback_data='rate_1'), InlineKeyboardButton("2", callback_data='rate_2'),
             InlineKeyboardButton("3", callback_data='rate_3'), InlineKeyboardButton("4", callback_data='rate_4'),
             InlineKeyboardButton("5", callback_data='rate_5')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text("Оцініть якість навчання (1-5):", reply_markup=reply_markup)
    
    elif feedback_type == 'menu':
        keyboard = [
            [InlineKeyboardButton("1", callback_data='rate_menu_1'), InlineKeyboardButton("2", callback_data='rate_menu_2'),
             InlineKeyboardButton("3", callback_data='rate_menu_3'), InlineKeyboardButton("4", callback_data='rate_menu_4'),
             InlineKeyboardButton("5", callback_data='rate_menu_5')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text("Оцініть оновлення меню (1-5):", reply_markup=reply_markup)
    
    elif feedback_type == 'suggest':
        await query.message.reply_text("Будь ласка, введіть ваші пропозиції щодо покращення:")
        context.user_data['state'] = 'waiting_suggestion'

async def handle_suggestion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обробка пропозицій щодо покращення"""
    if context.user_data.get('state') != 'waiting_suggestion':
        return
    
    suggestion = update.message.text
    
    # TODO: Зберегти пропозицію в базі даних
    
    await update.message.reply_text("Дякуємо за ваші пропозиції! Ми їх обов'язково розглянемо.")
    context.user_data['state'] = None

async def start_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Запуск HTML5 гри"""
    # Отримуємо випадкові питання з бази даних
    async for session in get_session():
        questions = await session.execute(
            select(Question).order_by(func.random()).limit(5)
        )
        questions = questions.scalars().all()
        
        # Формуємо дані для гри
        game_data = {
            "questions": [
                {
                    "text": q.text,
                    "correct_answer": q.correct_answer,
                    "explanation": q.explanation
                } for q in questions
            ]
        }
        
        # Створюємо кнопку для запуску гри
        keyboard = [[KeyboardButton(
            text="🎮 Почати гру",
            web_app=WebAppInfo(url="https://kultup.github.io/QuizKM/index.html")
        )]]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        
        # Відправляємо повідомлення з кнопкою та даними для гри
        await update.message.reply_text(
            "Натисніть кнопку нижче, щоб почати гру:",
            reply_markup=reply_markup
        )
        
        # Зберігаємо дані гри в контексті користувача
        context.user_data['game_data'] = game_data

async def handle_game_result(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обробка результатів гри"""
    if not update.message or not update.message.web_app_data:
        return
    
    try:
        data = json.loads(update.message.web_app_data.data)
        
        if data['type'] == 'game_complete':
            score = data['score']
            
            async for session in get_session():
                user = await session.execute(
                    select(User).filter(User.telegram_id == update.effective_user.id)
                )
                user = user.scalar_one_or_none()
                
                if user:
                    # Оновлення статистики
                    user.daily_score = score
                    user.total_score += score
                    await session.commit()
                    
                    await update.message.reply_text(
                        f"Гра завершена! Ваш рахунок: {score}/5\n"
                        f"Загальний рахунок: {user.total_score}"
                    )
                else:
                    await update.message.reply_text(
                        "Помилка: користувач не знайдений. Будь ласка, зареєструйтесь спочатку."
                    )
    except Exception as e:
        logger.error(f"Помилка при обробці результатів гри: {e}")
        await update.message.reply_text(
            "Виникла помилка при обробці результатів гри. Будь ласка, спробуйте ще раз."
        )

async def send_daily_questions_periodically():
    """Періодична відправка щоденних питань"""
    while True:
        now = datetime.now().time()
        target_time = time(hour=12, minute=0)
        
        if now.hour == target_time.hour and now.minute == target_time.minute:
            await send_daily_questions()
            # Чекаємо 24 години
            await asyncio.sleep(24 * 60 * 60)
        else:
            # Перевіряємо кожну хвилину
            await asyncio.sleep(60)

def main():
    """Запуск бота"""
    # Створення додатку
    application = Application.builder().token(TOKEN).build()
    
    # Додавання обробників
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_registration))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, handle_game_result))
    
    # Запуск бота
    application.run_polling(allowed_updates=Update.ALL_TYPES)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обробник текстових повідомлень"""
    text = update.message.text
    
    if text == "📝 Щоденний тест":
        # Логіка для щоденного тесту
        await send_daily_questions()
    elif text == "📊 Статистика":
        # Показ статистики
        async for session in get_session():
            user = await session.execute(select(User).filter(User.telegram_id == update.effective_user.id))
            user = user.scalar_one_or_none()
            
            if user:
                stats_text = (
                    f"Статистика користувача {user.full_name}:\n"
                    f"Щоденний рахунок: {user.daily_score}\n"
                    f"Загальний рахунок: {user.total_score}\n"
                    f"Заклад: {user.city}\n"
                    f"Посада: {user.position}"
                )
                await update.message.reply_text(stats_text)
    elif text == "📚 База знань":
        # Показ категорій бази знань
        keyboard = [
            ["🍽️ Сервіс", "📋 Меню"],
            ["🛡️ Безпека", "👨‍🍳 Кулінарія"],
            ["🎭 Етикет", "⬅️ Назад"]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text("Оберіть категорію:", reply_markup=reply_markup)
    elif text == "🎮 Почати гру":
        # Запуск гри
        await start_game(update, context)
    elif text == "⬅️ Назад":
        # Повернення до головного меню
        keyboard = [
            ["📝 Щоденний тест"],
            ["📊 Статистика", "📚 База знань"],
            ["🎮 Почати гру"]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text("Головне меню:", reply_markup=reply_markup)

if __name__ == '__main__':
    try:
        # Ініціалізація бази даних
        asyncio.run(init_db())
        
        # Запуск періодичної відправки питань в окремому потоці
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.create_task(send_daily_questions_periodically())
        
        # Запуск бота
        main()
    except KeyboardInterrupt:
        print('Бот зупинений') 