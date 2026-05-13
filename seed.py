import json
from datetime import datetime, timedelta
import random
from sqlalchemy.orm import Session
import models
from auth import get_password_hash

REVIEWS_PRELEST = [
    ("Анна К.", 5, "Настоящий пломбир как в детстве! Натуральный вкус, чувствуется молоко. Берём постоянно, дочка в восторге.", "positive", "качество,вкус"),
    ("Дмитрий В.", 5, "Один из немногих, где состав без пальмового масла. Рекомендую всем кто ценит качество.", "positive", "качество"),
    ("Светлана М.", 4, "Очень вкусный, нежный крем. Упаковка красивая. Цена чуть выше конкурентов, но оно того стоит.", "positive", "вкус,упаковка,цена"),
    ("Игорь П.", 5, "Лучший пломбир из всех что я пробовал на WB. Заказываем ящиками.", "positive", "качество"),
    ("Мария Н.", 4, "Хороший продукт, натуральный состав. Доставили быстро, всё целое.", "positive", "качество,доставка"),
    ("Олег Т.", 5, "Супер! Дети едят с удовольствием. Никаких красителей, всё честно.", "positive", "качество,вкус"),
    ("Юлия Р.", 4, "Отличное мороженое, вкус насыщенный. Брала в подарок, все оценили.", "positive", "вкус"),
    ("Павел С.", 5, "Нежный, тает во рту. Теперь только этот заказываю.", "positive", "вкус,качество"),
    ("Вера Ф.", 2, "Упаковка приехала мятой, мороженое подтаяло. Расстроена, ждала другого.", "negative", "упаковка,доставка"),
    ("Николай Б.", 3, "В этот раз вкус немного другой, не такой сливочный как обычно. Надеюсь это разовое.", "neutral", "вкус"),
    ("Тамара Г.", 2, "Заказала три пачки — одна была открыта. Возврат оформили, но осадок остался.", "negative", "упаковка,сервис"),
    ("Артём Д.", 3, "Нормальное мороженое, ничего особенного. За эту цену ожидала большего.", "neutral", "цена,вкус"),
    ("Ксения А.", 5, "Беру в Пятёрочке постоянно. Свежий, вкусный.", "positive", "качество,вкус"),
    ("Роман Е.", 4, "На Яндекс.Маркете быстро пришло, упаковка нормальная.", "positive", "доставка,упаковка"),
    ("Алина З.", 5, "В Магните всегда есть в наличии. Любимое мороженое.", "positive", "качество"),
]

REVIEWS_ARCTIC = [
    ("Владимир К.", 3, "Среднее мороженое, ничего выдающегося. Цена соответствует качеству.", "neutral", "качество,цена"),
    ("Екатерина Л.", 4, "Нормально, дети едят. Не лучшее, но и не плохое.", "neutral", "качество"),
    ("Сергей Ш.", 2, "Не понравился вкус. Слишком сладко и чувствуется химия.", "negative", "вкус,качество"),
    ("Ольга Ч.", 4, "Вполне приличное, беру когда нет другого.", "positive", "вкус"),
    ("Андрей Ю.", 3, "Упаковка простая, зато цена ниже. На любителя.", "neutral", "упаковка,цена"),
    ("Наталья М.", 2, "Разочарована. Состав оставляет желать лучшего.", "negative", "качество"),
    ("Иван П.", 3, "Обычное мороженое, ничего особенного. Ем если другого нет.", "neutral", "вкус"),
    ("Людмила В.", 4, "Хорошо, детям нравится. Главное — цена доступная.", "positive", "цена"),
]

REVIEWS_SNEGUROCHKA = [
    ("Алексей Ф.", 5, "Восторг! Нежнейший крем, тает быстро. Это мой любимый пломбир.", "positive", "вкус,качество"),
    ("Ирина С.", 5, "Покупаю каждую неделю. Состав отличный, без лишнего.", "positive", "качество"),
    ("Кирилл О.", 5, "Лучше не видел. Насыщенный молочный вкус, прям как домашнее.", "positive", "вкус,качество"),
    ("Галина Н.", 4, "Очень вкусное, но цена чуть кусается.", "positive", "вкус,цена"),
    ("Фёдор Б.", 5, "Брал на день рождения — гости спрашивали где взял. Супер!", "positive", "вкус"),
    ("Тая Р.", 5, "Уже год только это беру. Никогда не разочаровывало.", "positive", "качество"),
    ("Максим К.", 4, "Отличное, чуть дороже конкурентов но стоит того.", "positive", "цена,качество"),
    ("Вика Д.", 3, "Один раз упаковка была слегка повреждена, но мороженое нормальное.", "neutral", "упаковка"),
    ("Степан Л.", 5, "Настоящее качественное мороженое! Дочери очень понравилось.", "positive", "качество,вкус"),
    ("Надежда Ю.", 4, "Хорошее, но иногда встречается чуть меньше объёма чем написано.", "neutral", "качество"),
]

REVIEWS_BERESTA = [
    ("Анастасия К.", 5, "Атмосфера уютная, персонал вежливый. Борщ — просто объедение!", "positive", "сервис,качество"),
    ("Михаил В.", 4, "Хорошее место, кухня добротная. Рыбное ассорти понравилось.", "positive", "качество,сервис"),
    ("Татьяна Ш.", 5, "Ходим сюда семьёй, всегда рады. Детское меню есть, официанты внимательные.", "positive", "сервис,качество"),
    ("Борис Н.", 2, "Ждали заказ 50 минут, суп принесли холодным. Разочарование.", "negative", "сервис,доставка"),
    ("Валерия П.", 4, "Нормально, но цены выросли. Раньше было соотношение лучше.", "neutral", "цена,качество"),
    ("Константин Е.", 5, "Отмечали юбилей — всё на высшем уровне. Спасибо персоналу!", "positive", "сервис,качество"),
    ("Елена Б.", 3, "Кухня хорошая, но шумно в выходные. Берите бронь заранее.", "neutral", "сервис"),
    ("Роман Ж.", 4, "Рыба свежая, готовят вкусно. Место знаковое.", "positive", "качество"),
]

REVIEWS_ZERNO = [
    ("Полина В.", 5, "Лучший кофе в районе! Зерно всегда свежее, бариста умелые.", "positive", "качество,сервис"),
    ("Артём К.", 5, "Флэт вайт — просто мечта. Уютная атмосфера, всегда приятно работать здесь.", "positive", "вкус,сервис"),
    ("Дарья М.", 5, "Сюда хожу каждое утро. Персонал уже знает мой заказ наизусть :)", "positive", "сервис,качество"),
    ("Игорь С.", 4, "Хороший кофе, выпечка свежая. Немного тесно, но уютно.", "positive", "качество,вкус"),
    ("Катя Ф.", 3, "Кофе вкусный, но подождала минут 15. Многовато для небольшой чашки.", "neutral", "сервис"),
    ("Никита Б.", 5, "Завтраки тут — огонь. Гранола, яйца бенедикт, всё отлично.", "positive", "качество,вкус"),
    ("Оксана Д.", 4, "Очень стильно оформлено, кофе на уровне. Цены чуть выше среднего.", "positive", "качество,цена"),
]

REWARDS_DATA = [
    ("Скидка 300₽ на Wildberries", "Промокод на заказ от 1000₽. Действует 30 дней.", "Wildberries", 150, "discount", "🛒", "bg-purple-100 text-purple-700"),
    ("Яндекс Плюс на 3 месяца", "Подписка с музыкой, кино и кешбэком за любые покупки.", "Яндекс", 300, "subscription", "🎵", "bg-yellow-100 text-yellow-700"),
    ("10 бесплатных доставок на Ozon", "Бесплатная доставка без минимальной суммы заказа.", "Ozon", 200, "delivery", "📦", "bg-blue-100 text-blue-700"),
    ("Скидка 10% в Пятёрочке", "Промокод в мобильном приложении Пятёрочки на 1 покупку.", "Пятёрочка", 100, "discount", "🏪", "bg-green-100 text-green-700"),
    ("Промокод 15% в ресторанах-партнёрах", "Скидка в сети ресторанов Береста и партнёрских заведениях.", "Береста", 200, "discount", "🍽️", "bg-orange-100 text-orange-700"),
    ("Абонемент «Фитнес Плюс» на 1 месяц", "Безлимитное посещение любого зала сети Фитнес Плюс.", "Фитнес Плюс", 400, "subscription", "💪", "bg-red-100 text-red-700"),
    ("СберПрайм на 2 месяца", "Подписка с кешбэком, скидками и привилегиями СберБанка.", "СберБанк", 250, "subscription", "💚", "bg-emerald-100 text-emerald-700"),
]


def seed_database(db: Session):
    if db.query(models.User).count() > 0:
        return

    print("Seeding database...")

    b2b_user = models.User(
        email="demo_b2b@ratescan.ru", username="Прелесть Компани",
        hashed_password=get_password_hash("Demo123!"), user_type="b2b",
        company_name="Пломбир «Прелесть»", company_category="FMCG / Мороженое", points=0,
    )
    b2b_user2 = models.User(
        email="beresta_b2b@ratescan.ru", username="Береста Групп",
        hashed_password=get_password_hash("Demo123!"), user_type="b2b",
        company_name="Ресторан «Береста»", company_category="HoReCa", points=0,
    )
    b2c_user = models.User(
        email="demo_b2c@ratescan.ru", username="Анна Петрова",
        hashed_password=get_password_hash("Demo123!"), user_type="b2c", points=120,
    )
    for u in [b2b_user, b2b_user2, b2c_user]:
        db.add(u)
    db.flush()

    profile1 = models.BusinessProfile(user_id=b2b_user.id, brand_name="Пломбир «Прелесть»",
                                       category="мороженое", description="Производитель натурального пломбира с 2005 года")
    profile2 = models.BusinessProfile(user_id=b2b_user2.id, brand_name="Ресторан «Береста»",
                                       category="ресторан", description="Ресторан русской кухни в центре города")
    db.add(profile1); db.add(profile2); db.flush()

    p1 = models.Product(name="Пломбир «Прелесть» классический", category="мороженое", brand="Прелесть",
                         business_id=profile1.id, description="Натуральный пломбир по ГОСТу. Без пальмового масла.",
                         rating_wb=4.1, rating_ozon=3.9, rating_ym=4.3, price_wb=89, price_ozon=85, price_ym=92)
    p2 = models.Product(name="Мороженое «Арктик» пломбир", category="мороженое", brand="Арктик",
                         description="Классический пломбир в вафельном стаканчике.",
                         rating_wb=3.8, rating_ozon=4.0, rating_ym=3.7, price_wb=69, price_ozon=72, price_ym=75)
    p3 = models.Product(name="Пломбир «Снегурочка» премиум", category="мороженое", brand="Снегурочка",
                         description="Премиальный пломбир из фермерского молока.",
                         rating_wb=4.5, rating_ozon=4.4, rating_ym=4.6, price_wb=119, price_ozon=115, price_ym=125)
    p4 = models.Product(name="Ресторан «Береста»", category="ресторан", brand="Береста",
                         business_id=profile2.id, description="Ресторан русской кухни. Живая музыка по пятницам.",
                         rating_gmaps=4.2, rating_2gis=4.0, rating_zoon=4.1)
    p5 = models.Product(name="Кофейня «Зерно»", category="кофейня", brand="Зерно",
                         description="Specialty кофе и авторские завтраки.",
                         rating_gmaps=4.7, rating_2gis=4.6, rating_zoon=4.5)
    for p in [p1, p2, p3, p4, p5]:
        db.add(p)
    db.flush()

    platforms_fmcg = ["wb", "ozon", "ym", "ratescan", "wb", "ozon"]
    platforms_horeca = ["gmaps", "2gis", "zoon", "ratescan", "gmaps"]

    def add_reviews(product, review_data, platforms, start_days_ago=180):
        step = max(start_days_ago // max(len(review_data), 1), 1)
        for i, (name, rating, text, sentiment, topics) in enumerate(review_data):
            days_ago = max(start_days_ago - i * step - random.randint(0, max(step - 1, 1)), 0)
            db.add(models.Review(product_id=product.id, author_name=name, text=text, rating=rating,
                                  platform=platforms[i % len(platforms)], sentiment=sentiment,
                                  topics=topics, is_verified=True,
                                  created_at=datetime.utcnow() - timedelta(days=days_ago)))

    add_reviews(p1, REVIEWS_PRELEST, platforms_fmcg)
    add_reviews(p2, REVIEWS_ARCTIC, platforms_fmcg)
    add_reviews(p3, REVIEWS_SNEGUROCHKA, platforms_fmcg)
    add_reviews(p4, REVIEWS_BERESTA, platforms_horeca)
    add_reviews(p5, REVIEWS_ZERNO, platforms_horeca)

    # ===== REWARDS =====
    for name, desc, partner, pts, cat, icon, badge_color in REWARDS_DATA:
        db.add(models.Reward(name=name, description=desc, partner=partner, points_cost=pts,
                              category=cat, icon=icon, badge_color=badge_color))

    # ===== SURVEYS =====
    db.flush()
    survey1 = models.Survey(
        title="Помогите нам стать лучше!",
        description="Расскажите о вашем опыте с нашим мороженым. Займёт 2–3 минуты.",
        business_id=profile1.id, category="мороженое", points_reward=30,
        estimated_minutes=3, gradient="from-blue-500 to-indigo-600",
    )
    survey2 = models.Survey(
        title="Изучаем ваши предпочтения",
        description="Помогите нам понять что важно для наших гостей при выборе ресторана.",
        business_id=profile2.id, category="ресторан", points_reward=25,
        estimated_minutes=2, gradient="from-orange-400 to-rose-500",
    )
    db.add(survey1); db.add(survey2); db.flush()

    questions1 = [
        (1, "Как часто вы покупаете пломбир?", "choice",
         json.dumps(["Каждую неделю", "Несколько раз в месяц", "Иногда", "Очень редко"])),
        (2, "Что важнее всего при выборе мороженого?", "choice",
         json.dumps(["Вкус", "Натуральный состав", "Цена", "Красивая упаковка"])),
        (3, "Оцените вкус нашего пломбира:", "rating", None),
        (4, "Что хотели бы улучшить в продукте?", "choice",
         json.dumps(["Объём порции", "Упаковку", "Вкус", "Цену", "Всё устраивает!"])),
        (5, "Порекомендуете наш пломбир друзьям?", "choice",
         json.dumps(["Да, однозначно!", "Скорее да", "Не уверен(а)", "Вряд ли"])),
    ]
    questions2 = [
        (1, "Как часто вы посещаете рестораны?", "choice",
         json.dumps(["Несколько раз в неделю", "Раз в неделю", "Несколько раз в месяц", "Редко"])),
        (2, "Что важнее при выборе ресторана?", "choice",
         json.dumps(["Кухня и блюда", "Цены", "Атмосфера и интерьер", "Локация"])),
        (3, "Откуда вы узнаёте о новых заведениях?", "choice",
         json.dumps(["Яндекс.Карты / 2ГИС", "Instagram / Telegram", "Советы друзей", "Случайно проходил(а)"])),
        (4, "Хотели бы получать персональные предложения?", "choice",
         json.dumps(["Да, в Telegram", "Да, на email", "Да, в приложении", "Нет, спасибо"])),
    ]
    for order, text, qtype, options in questions1:
        db.add(models.SurveyQuestion(survey_id=survey1.id, order=order,
                                      question_text=text, question_type=qtype, options=options))
    for order, text, qtype, options in questions2:
        db.add(models.SurveyQuestion(survey_id=survey2.id, order=order,
                                      question_text=text, question_type=qtype, options=options))

    # ===== DEMO CONVERSATION =====
    db.flush()
    conv = models.Conversation(
        b2c_user_id=b2c_user.id, business_id=profile1.id, product_id=p1.id,
        subject="Вопрос о составе пломбира",
        created_at=datetime.utcnow() - timedelta(days=3),
        last_message_at=datetime.utcnow() - timedelta(days=2),
        is_read_b2b=True, is_read_b2c=True,
    )
    db.add(conv); db.flush()
    msgs = [
        ("b2c", b2c_user.username,
         "Здравствуйте! Хочу уточнить — в составе используется только коровье молоко, "
         "или есть растительные жиры? Я покупаю для ребёнка с непереносимостью сои.",
         datetime.utcnow() - timedelta(days=3)),
        ("b2b", f"Представитель {profile1.brand_name}",
         "Добрый день, Анна! Благодарим за вопрос. Наш Пломбир «Прелесть» классический "
         "производится исключительно из цельного коровьего молока и сливок — никаких "
         "растительных жиров и сои в составе нет. Продукт прошёл сертификацию по ГОСТ. "
         "Для детей полностью безопасен. Если нужен полный состав — могу выслать.",
         datetime.utcnow() - timedelta(days=2)),
    ]
    for stype, sname, text, created_at in msgs:
        db.add(models.ConversationMessage(conversation_id=conv.id, sender_type=stype,
                                           sender_name=sname, text=text, created_at=created_at))

    db.commit()
    print("Database seeded successfully!")
