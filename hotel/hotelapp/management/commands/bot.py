import telebot

from django.conf import settings
from django.core.management.base import BaseCommand
from geopy.geocoders import Nominatim
from telebot import types
from loguru import logger

from ...models import Profile, Message
from ...hotel_api import get_list_hotel, get_city_id

logger.add("logging.log", format="{time}, {level}, {message}", level="DEBUG", encoding="UTF-8")

bot = telebot.TeleBot(settings.TOKEN, parse_mode="HTML")


@logger.catch()
def registration(message, city=None, city_id=0):
    """
    Функция для записи пользователя и сообщений в бд. В случае, если пользователь уже имеется в бд,
    то данные только обновляются. В БД пользователи проверяются по уникальному ключу extr_id, котрая
    является переменная chat_id социальной сети телеграмм
    :param message: telebot.message
    :param city: str (default = None)
    :param city_id: int (default = 0)
    """
    p, flag = Profile.objects.get_or_create(
        extr_id=message.chat.id,
        defaults={
            'city': city,
            'name': message.chat.username,
            'city_id': city_id,
        }
    )
    Message(
        profile=p,
        text=message.text
    ).save()


@logger.catch()
class Command(BaseCommand):
    help: 'Телеграм чат бот'

    @logger.catch()
    def handle(self, *args, **options):
        """
        Функция запуска бота. При вызове команды bot запускается данная функция
        """
        @bot.message_handler(commands=['start'])
        @logger.catch()
        def start_bot(message: telebot.types.Message):
            """
            Функция приветствие. Функция предлагает выбор полльзователю по поиску отелей по геопозиции или набрать
            наименование гороа ручками.
            :param message: telebot.types.Message
            :return: None
            """
            bot.send_message(message.chat.id, "Добро пожаловать! Бот предназначан для поиска отелей по местоположению, "
                                              "либо по выбранному городу. Бот выполнен в виде интерактивное меню."
                                              " Для работы с ботом требуется лишь: ")
            registration(message)
            keyboard = types.InlineKeyboardMarkup(row_width=1)
            button_geo = types.InlineKeyboardButton("Поиск по геопозиции", callback_data="geo")
            button_search = types.InlineKeyboardButton("Выбрать город", callback_data="search_geo")
            keyboard.row(button_geo)
            keyboard.row(button_search)
            bot.send_message(message.chat.id, "Следовать по подсказкам бота", reply_markup=keyboard)

        @bot.callback_query_handler(func=lambda call: True)
        @logger.catch()
        def callback_query(call: types.CallbackQuery):
            """
            Функция отлавливает нажатия на Inline кнопки пользователем и распределяет по функциям в зависимости
            от нажатой кнопки.
            :param call: types.CallbackQuery
            :return: None
            """
            call.message.text = call.data
            registration(call.message)
            logger.info("callback_query run")
            if call.data == "geo":
                keyboard = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
                button_geo = types.KeyboardButton(text="Отправить местоположение", request_location=True)
                keyboard.add(button_geo)
                bot.send_message(call.message.chat.id, "Для продолжения работы бота требуется доступ к геопозиции",
                                 reply_markup=keyboard)
            if call.data == "search_geo":
                bot.send_message(call.message.chat.id, "Введите название города, "
                                                       "допускается добавлять в поиск название страны, региона итд."
                                                       " Например (Россия Москва) ")
            if "CITY" in call.data:
                city_id = call.data.split()[1]
                logger.info(f'Выбран город: {Profile.objects.get(extr_id=call.message.chat.id).city} id: {city_id}')
                Profile.objects.filter(extr_id=call.message.chat.id).update(city_id=int(city_id))
                navigaton(call.message)

            if call.data == "/lowprice":
                bot.send_message(call.message.chat.id, "Сколько отелей найти? (максимум 10)")
                bot.register_next_step_handler(call.message, get_page_size, "PRICE")

            if call.data == "/highprice":
                bot.send_message(call.message.chat.id, "Сколько отелей найти? (максимум 10)")
                bot.register_next_step_handler(call.message, get_page_size, "PRICE_HIGHEST_FIRST")

            if call.data == "/bestdeal":
                bot.send_message(call.message.chat.id, "Сколько отелей найти? (максимум 10)")
                bot.register_next_step_handler(call.message, get_page_size_best)

        @logger.catch()
        def get_page_size_best(message: types.Message):
            """
            Функция заправшивает у пользователя минимальную стоимость, и записывает данные page_size
            :param message: types.Message
            :return: None
            """
            try:
                if int(message.text) > 0 and int(message.text) <= 10:
                    page_size = int(message.text)
                    Profile.objects.filter(extr_id=message.chat.id).update(page_size=page_size)
                    bot.send_message(message.chat.id, "Минимальная цена номера за сутки в рублях: ")
                    bot.register_next_step_handler(message, get_min_price)
                else:
                    raise ValueError
            except ValueError:
                logger.error("ERROR data page_size (bestdeal)")
                bot.send_message(message.chat.id, "Попробуйте еще раз")
                bot.register_next_step_handler(message, get_page_size_best)

        @logger.catch()
        def get_min_price(message: types.Message):
            """
            Функция запрашивает у пользователя максимальную стоимость отеля и записывет данные о минимальной стоимости
            :param message: types.Message
            :return: None
            """
            try:
                if int(message.text):
                    Profile.objects.filter(extr_id=message.chat.id).update(price_min=int(message.text))
                    bot.send_message(message.chat.id, "Максимальная цена номера за сутки в рублях: ")
                    bot.register_next_step_handler(message, get_max_price)
                else:
                    raise ValueError
            except ValueError:
                logger.debug("Error data min_price")
                bot.send_message(message.chat.id, "Неккоректно введена минимальная цена")
                bot.register_next_step_handler(message, get_min_price)

        @logger.catch()
        def get_max_price(message: types.Message):
            """
            Функция запрашивает расстояние от центра города и записывет данные о макисмальной стоимости отеля
            :param message: types.Message
            :return: None
            """
            try:
                if int(message.text):
                    Profile.objects.filter(extr_id=message.chat.id).update(price_max=int(message.text))
                    bot.send_message(message.chat.id, "Минимальное расстояние от центра города: ")
                    bot.register_next_step_handler(message, get_min_dist)
                else:
                    raise ValueError
            except ValueError:
                logger.debug("Error data max_price")
                bot.send_message(message.chat.id, "Неккоректно введена максимальная цена")
                bot.register_next_step_handler(message, get_max_price)

        @logger.catch()
        def get_min_dist(message: types.Message):
            """
            Функция записывает минимальное расстояние и запрашивает максимальное
            :param message: types.Message
            :return: None
            """
            try:
                if float(message.text) < 1:
                    Profile.objects.filter(extr_id=message.chat.id).update(dist_min=0)
                    bot.send_message(message.chat.id, "Максимальное расстояние от центра города: ")
                    bot.register_next_step_handler(message, get_max_dist)
                elif int(message.text):
                    Profile.objects.filter(extr_id=message.chat.id).update(dist_min=int(message.text))
                    bot.send_message(message.chat.id, "Максимальное расстояние от центра города: ")
                    bot.register_next_step_handler(message, get_max_dist)
                else:
                    raise ValueError
            except ValueError:
                logger.debug("Error data dist_min")
                bot.send_message(message.chat.id, "Неккоректно введена минимальная дистанция")
                bot.register_next_step_handler(message, get_min_dist)

        @logger.catch()
        def get_max_dist(message: types.Message):
            """
            Функция записывает максимальное расстояние от центра города, и запускает функцию get_result_list_best
            :param message: types.Message
            :return: None
            """
            try:
                if int(message.text):
                    Profile.objects.filter(extr_id=message.chat.id).update(dist_max=int(message.text))
                    bot.send_message(message.chat.id, "Подождите, это займет некоторое время")
                    logger.info("run get_result")
                    get_result_list_for_best(message)
                else:
                    raise ValueError
            except ValueError:
                logger.debug("Error data dist_max")
                bot.send_message(message.chat.id, "Неккоректно введена максимальная дистанция")
                bot.register_next_step_handler(message, get_max_dist)

        @logger.catch()
        def get_result_list_for_best(message: types.Message):
            """
            Функция для получения словаря со списком отелей.
            :param message: types.Message
            :return: None
            """
            logger.info("run get_list_hotel")
            page_size = Profile.objects.get(extr_id=message.chat.id).page_size
            dist_min = Profile.objects.get(extr_id=message.chat.id).dist_min
            dist_max = Profile.objects.get(extr_id=message.chat.id).dist_max
            price_min = Profile.objects.get(extr_id=message.chat.id).price_min
            price_max = Profile.objects.get(extr_id=message.chat.id).price_max
            result_list = get_list_hotel(message, page_size=page_size, sort='PRICE', price_min=price_min,
                                         price_max=price_max, dist_min=dist_min, dist_max=dist_max)
            logger.info("Run send_result")
            send_result(message, result_list)
            keyboard = types.InlineKeyboardMarkup(row_width=1)
            button = types.InlineKeyboardButton(text="Начать заново", callback_data='search_geo')
            keyboard.row(button)
            bot.send_message(message.chat.id, "Что бы изменить параметры, нажми: ", reply_markup=keyboard)

        @bot.message_handler(content_types=["location"])
        @logger.catch()
        def location(message: telebot.types.Message):
            """
            Функция отлавливает location
            :param message: types.Message
            :return: None
            """
            if message.location is not None:
                latitude = message.location.latitude
                longitude = message.location.longitude
                geolocator = Nominatim(user_agent='hotel')
                loc = geolocator.reverse(f'{latitude}, {longitude}', exactly_one=True)
                address = loc.raw['address']
                city = address.get('city', '')
                if city == '':
                    city = address.get('town', '')
                logger.info(f"Your address {loc}")
                message.text = city
                Profile.objects.filter(extr_id=message.chat.id).update(city=city)
                registration(message, city)
                bot.send_message(message.chat.id, "Подождите, это займет некоторое время")
                rst_dct = get_city_id(message)
                keyboard = create_keyboard(rst_dct)
                bot.send_message(message.chat.id, "Выберите точку поиска: ", reply_markup=keyboard)
            else:
                bot.send_message(message.chat.id, "Не удается загрузить геоданные")

        @logger.catch()
        def navigaton(message):
            """
                Функция навигация по методу поиска города. lowprice - поиск самых дешевых отелей в выбранном городе.
                highprice - поиск самых дорогих отелей в выбранном городе. bestdeal - гибкий поиск (выбор отдаленности
                от центра города, диапазон цен) В функции используется inline кнопки. При нажатии запускается
                соответсвующая функция.
                :param message: telebot.message
                """
            keyboard = types.InlineKeyboardMarkup(row_width=1)
            button_low = types.InlineKeyboardButton(text="Топ самых дешевых отелей", callback_data='/lowprice')
            button_high = types.InlineKeyboardButton(text="Топ самых дорогих отелей", callback_data='/highprice')
            button_user = types.InlineKeyboardButton(text="Гибкий поиск", callback_data='/bestdeal')
            keyboard.row(button_low)
            keyboard.row(button_high)
            keyboard.row(button_user)
            bot.send_message(message.chat.id, "Выберите метод поиска",
                             reply_markup=keyboard)

        @bot.message_handler(content_types=['text'])
        def get_city(message: telebot.types.Message):
            """
            Функция получает текст с названием города. Далее библеотекой geopy проверятся валидность и находится
            на карте координаты города. В случае не обнаружения города выводится соответсвующее сообшение.
            Ответ с геолокатора поступает на русском языке (если даже пользователь ввел город не на русском языке)
            На экран пользователя передается название города и страна нахождения города на русском языке.
            Если найденный город пользователя не устраивает, то пользователь имеет возможность набрать город еще
            раз, после получения текста, текст отлавливает фунция user_city, и данные снова передаются в функцию
            get_city. В случае ввода не города, а населенный пункт или деревню то, в качестве города, будет
            использован значение населенного пункта или деревни. Полученный результат обнавляет локацию в БД.
            :param message: telebot.message
            """
            registration(message)
            city = message.text
            geolocator = Nominatim(user_agent='hotel')
            if geolocator.geocode(city):
                loc = geolocator.geocode(city, exactly_one=True, language="ru")
                logger.info(f'{loc}')
                loc = geolocator.reverse(f'{loc.latitude}, {loc.longitude}', exactly_one=True, language="en")
                logger.info(f'{loc.raw}')
                address = loc.raw['address']
                city = address.get('city', '')
                if city == '':
                    city = address.get('town', '')
                    if city == '':
                        city = address.get('village', '')
                        if city == '':
                            city = address.get('state', '').split()[0]
                Profile.objects.filter(extr_id=message.chat.id).update(city=city)
                bot.send_message(message.chat.id, "Подождите, это займет некоторое время")
                rst_dct = get_city_id(message)
                keyboard = create_keyboard(rst_dct)
                bot.send_message(message.chat.id, "Найденные города: ", reply_markup=keyboard)
            else:
                bot.send_message(message.chat.id, "Такого города не существует, попробуйте еще раз")

        @logger.catch()
        def create_keyboard(dct: list) -> types.InlineKeyboardMarkup:
            """
            Функция созадает inline клавиатуру с полученного списка городов
            :param dct: list
            :return: types.InlineKeyboardMarkup
            """
            keyboard = types.InlineKeyboardMarkup(row_width=1)
            for number, item in enumerate(dct):
                number = types.InlineKeyboardButton(text=f'{item["caption"]}',
                                                    callback_data=f"CITY {item['city_id']}")
                keyboard.row(number)
            return keyboard

        @logger.catch()
        def get_page_size(message: types.Message, sort: str):
            """
            Функция получает на вход количество отелей, проверяет и запускает функцию get_list_hotel, а затем
            функцию send_result
            :param message: types.Message
            :param sort: str
            :return: None
            """
            flag = False
            try:
                if int(message.text) > 0 and int(message.text) <= 10:
                    page_size = int(message.text)
                    Profile.objects.filter(extr_id=message.chat.id).update(page_size=page_size)
                    logger.debug(f"Количество отелей: {Profile.objects.get(extr_id=message.chat.id).page_size} "
                                 f"func: get_page_size")
                    bot.send_message(message.chat.id, "Подождите, это займет некоторое время")
                    result_list = get_list_hotel(message, page_size, sort)
                    send_result(message, result_list)
                    flag = True
                else:
                    raise ValueError
            except ValueError:
                bot.send_message(message.chat.id, "Попробуйте еще раз")
                bot.register_next_step_handler(message, get_page_size, sort)
                logger.debug("ERROR data page_size")
            if flag:
                keyboard = types.InlineKeyboardMarkup(row_width=1)
                button = types.InlineKeyboardButton(text="Начать заново", callback_data='search_geo')
                keyboard.row(button)
                bot.send_message(message.chat.id, "Что бы изменить параметры, нажми: ", reply_markup=keyboard)

        @logger.catch()
        def send_result(message: types.Message, result_list: list):
            """
            Функция для отсылки результата пользователю
            :param message: types.Message
            :param result_list: list
            :return: None
            """
            if not result_list:
                bot.send_message(message.chat.id, "Ничего не найдено, пожалуйста измените параметры поиска!")
            else:
                for item in result_list:
                    bot.send_message(message.chat.id, f'{item}')
                    message.text = item
                    registration(message)

        try:
            bot.polling()
        except Exception as err:
            logger.error(f"Не запустился бот {err}")
