import os
import logging
from datetime import datetime, time
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from apscheduler.schedulers.asyncio import AsyncIOScheduler
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
    keyboard = [
        [InlineKeyboardButton("Реєстрація", callback_data='register')],
        [InlineKeyboardButton("Щоденний тест", callback_data='daily_test')],
        [InlineKeyboardButton("Статистика", callback_data='stats')],
        [InlineKeyboardButton("База знань", callback_data='knowledge_base')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "Вітаю! Я бот для навчання персоналу Країна Мрій. "
        "Оберіть опцію:",
        reply_markup=reply_markup
    )

async def register_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обробник реєстрації користувача"""
    query = update.callback_query
    await query.answer()
    
    await query.message.reply_text(
        "Будь ласка, введіть ваші дані у форматі:\n"
        "ПІБ, Місто, Посада"
    )
    context.user_data['state'] = 'waiting_registration'

async def handle_registration(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обробник введених даних реєстрації"""
    if context.user_data.get('state') != 'waiting_registration':
        return

    try:
        full_name, city, position = [x.strip() for x in update.message.text.split(',')]
        async for session in get_session():
            user = User(
                telegram_id=update.effective_user.id,
                full_name=full_name,
                city=city,
                position=position
            )
            session.add(user)
            await session.commit()
            
        await update.message.reply_text(
            "Реєстрація успішна! Тепер ви можете проходити щоденні тести."
        )
        context.user_data['state'] = None
    except Exception as e:
        await update.message.reply_text(
            "Помилка при реєстрації. Будь ласка, перевірте формат введення даних."
        )

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
    query = update.callback_query
    await query.answer()
    
    async for session in get_session():
        # Отримання випадкових питань
        questions = await session.execute(
            select(Question).order_by(func.random()).limit(5)
        )
        questions = questions.scalars().all()
        
        # Підготовка питань для гри
        game_questions = []
        for q in questions:
            game_questions.append({
                'text': q.text,
                'correct_answer': q.correct_answer,
                'explanation': q.explanation
            })
        
        # Створення кнопки для запуску гри
        keyboard = [[InlineKeyboardButton("Почати гру", web_app=WebAppInfo(url="https://kultup.github.io/QuizKM/game.html"))]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.message.reply_text(
            "Натисніть кнопку, щоб почати гру:",
            reply_markup=reply_markup
        )
        
        # Збереження питань в контексті користувача
        context.user_data['game_questions'] = game_questions

async def handle_game_result(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обробка результатів гри"""
    if not update.message or not update.message.web_app_data:
        return
    
    data = json.loads(update.message.web_app_data.data)
    
    if data['type'] == 'game_complete':
        score = data['score']
        
        async for session in get_session():
            user = await session.execute(select(User).filter(User.telegram_id == update.effective_user.id))
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

async def main():
    """Запуск бота"""
    # Ініціалізація бази даних
    await init_db()
    
    # Створення додатку
    application = Application.builder().token(TOKEN).build()
    
    # Додавання обробників
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(register_user, pattern='^register$'))
    application.add_handler(CallbackQueryHandler(handle_answer, pattern='^answer_'))
    application.add_handler(CallbackQueryHandler(show_explanation, pattern='^explain_'))
    application.add_handler(CallbackQueryHandler(show_stats, pattern='^stats$'))
    application.add_handler(CallbackQueryHandler(show_knowledge_base, pattern='^knowledge_base$'))
    application.add_handler(CallbackQueryHandler(show_knowledge_category, pattern='^kb_'))
    application.add_handler(CallbackQueryHandler(start_feedback, pattern='^feedback$'))
    application.add_handler(CallbackQueryHandler(handle_feedback, pattern='^feedback_'))
    application.add_handler(CallbackQueryHandler(start_game, pattern='^start_game$'))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_registration))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_suggestion))
    application.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, handle_game_result))
    
    # Налаштування планувача
    scheduler = AsyncIOScheduler()
    scheduler.add_job(send_daily_questions, 'cron', hour=12)
    scheduler.start()
    
    # Запуск бота
    await application.run_polling()

if __name__ == '__main__':
    import asyncio
    asyncio.run(main()) 