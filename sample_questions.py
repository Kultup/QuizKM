from models import Question
from database import get_session
from sqlalchemy import select

SAMPLE_QUESTIONS = [
    {
        "category": "Сервіс",
        "text": "Як правильно сервірувати вино?",
        "correct_answer": "Спочатку наливаємо невелику кількість для дегустації",
        "explanation": "Сервірування вина починається з наливання невеликої кількості для дегустації. "
                     "Після схвалення клієнтом наливаємо повний бокал на 1/3."
    },
    {
        "category": "Меню",
        "text": "Які страви входять до постного меню?",
        "correct_answer": "Грибна юшка, овочеві салати, рибні страви",
        "explanation": "Постне меню включає страви без м'яса та молочних продуктів. "
                     "Дозволені овочі, гриби, риба та морепродукти."
    },
    {
        "category": "Безпека",
        "text": "Що робити при пожежі в ресторані?",
        "correct_answer": "Викликати пожежну службу та евакуювати відвідувачів",
        "explanation": "При виявленні пожежі необхідно негайно викликати пожежну службу (101), "
                     "сповістити адміністратора та почати евакуацію відвідувачів."
    },
    {
        "category": "Кулінарія",
        "text": "Яка температура для приготування стейку medium rare?",
        "correct_answer": "54-57°C",
        "explanation": "Стейк medium rare готується при температурі 54-57°C. "
                     "При цій температурі м'ясо має червоно-рожевий колір всередині."
    },
    {
        "category": "Етикет",
        "text": "Як правильно вітати відвідувачів?",
        "correct_answer": "Доброго дня! Раді вас бачити!",
        "explanation": "Вітання має бути щирим та дружнім. Важливо зробити акцент на тому, "
                     "що ми раді бачити відвідувача в нашому ресторані."
    }
]

async def add_sample_questions():
    """Додавання прикладів питань до бази даних"""
    async for session in get_session():
        # Перевірка чи вже є питання
        existing = await session.execute(select(Question))
        if existing.scalar_one_or_none():
            return
            
        # Додавання питань
        for q in SAMPLE_QUESTIONS:
            question = Question(**q)
            session.add(question)
        await session.commit() 