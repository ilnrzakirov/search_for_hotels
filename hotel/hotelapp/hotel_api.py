import requests
import json
import telebot
from .models import Profile
from django.conf import settings
from .management.commands.bot import logger
import datetime
import re


@logger.catch()
def get_city_id(message: telebot.types.Message):
    """
    Функция для получения id города по API rapidaipi. После получения ID функция записывает результат в БД
    :param message: types.Message
    """
    url = "https://hotels4.p.rapidapi.com/locations/search"
    querystring = {"query": f"{Profile.objects.get(extr_id=message.chat.id).city}", "locale": "ru_RU"}
    logger.info(f"Selected city {Profile.objects.get(extr_id=message.chat.id).city}")
    headers = {
        'x-rapidapi-key': settings.API_KEY,
        'x-rapidapi-host': "hotels4.p.rapidapi.com"
    }
    try:
        response = requests.request("GET", url, headers=headers, params=querystring)
        data = json.loads(response.text)
    except Exception as err:
        logger.error(f"Ошибка API {err}")
    with open('data.txt', 'w', encoding='UTF-8') as file:
         json.dump(data, file, indent=4, ensure_ascii=False)
    result_dict = list()
    for item in data['suggestions']:
        if item['group'] == 'CITY_GROUP':
            for i_item in item['entities']:
                city = i_item['name']
                caption = re.sub('<[^>]*>', '', i_item['caption'])
                destination_id = i_item['destinationId']
                result_dict.append({"city": city, "caption": caption, "city_id": destination_id})
    logger.debug(f'List city {result_dict}')
    return result_dict


@logger.catch()
def get_list_hotel(message: telebot.types.Message, page_size: int, sort: str, price_min=0,
                   price_max=9999999, dist_min=0, dist_max=999) -> list:
    url = "https://hotels4.p.rapidapi.com/properties/list"
    headers = {
        'x-rapidapi-key': settings.API_KEY,
        'x-rapidapi-host': "hotels4.p.rapidapi.com"
    }
    logger.info("This is get list")
    page_number = 1
    check_out = (datetime.datetime.now() + datetime.timedelta(days=1)).strftime('%Y-%m-%d')
    check_in = datetime.datetime.now().strftime('%Y-%m-%d')
    city_id = Profile.objects.get(extr_id=message.chat.id).city_id
    querystring = {"destinationId": f"{city_id}", "pageNumber": f"{page_number}",
                   "pageSize": "25", "checkIn": check_in,
                   "checkOut": check_out, "adults1": "1", "sortOrder": sort, "currency": "RUB",
                   "locale": "ru_RU", "priceMin": f"{price_min}", "priceMax": f"{price_max}"}
    if dist_max != 999 and float(dist_min) and float(dist_max):
        querystring['landmarkIds'] = 'Центр города'
        if float(dist_min) > float(dist_max):
            dist_min, dist_max = dist_max, dist_min
            logger.info("Added distance parameters")
    else:
        dist_min = 0
        dist_max = 999
    result_list = list()
    while True:
        logger.info("GET requests")
        try:
            response = requests.request("GET", url, headers=headers, params=querystring)
            data = json.loads(response.text)
        except Exception as err:
            logger.error(f"API (ERROR) GET_LIST {err}")
        with open('data_list.txt', 'w', encoding='UTF-8') as file:
             json.dump(data, file, indent=4, ensure_ascii=False)
        for hotel in data['data']['body']['searchResults']['results']:
            hotel_name = f'Отель: {hotel["name"]}'
            address = f'Адрес: {hotel["address"]["countryName"]}, {hotel["address"]["locality"]}, ' \
                      f'{"" if "streetAddress" not in hotel["address"] else hotel["address"]["streetAddress"]}'
            price = f'Цена за сутки: ' \
                    f'{"Цена не указана" if "ratePlan" not in hotel else hotel["ratePlan"]["price"]["current"]}'
            dist_center = re.sub(r"[^0-9.,]", "", hotel['landmarks'][0]['distance']).replace(',', '.')
            dist_center_fin = f'Удаленность от центра города {dist_center} км.'
            try:
                rating = hotel['guestReviews']['rating']
            except Exception as err:
                rating = "Без рейтинга"
                logger.info(f"Нет рейтинга {err}")
            if dist_max != 999:
                if float(dist_min) > float(dist_center) or float(dist_center) > float(dist_max):
                    logger.info(f'the distance is not observed {dist_center} min: {dist_min}, max {dist_max}')
                    continue
                else:
                    if len(result_list) < page_size:
                        result_list.append(f'{hotel_name}\nРейтинг: {rating}\n{price}\n{address}\n{dist_center_fin}')
            else:
                if len(result_list) < page_size:
                    result_list.append(f'{hotel_name}\nРейтинг: {rating}\n{price}\n{address}\n{dist_center_fin}\n'
                                       f'Ссылка на страницу бронирования:\nhttps://ru.hotels.com/ho{hotel["id"]}/')
        if len(result_list) < page_size:
            if "pagination" in data['data']['body']['searchResults']:
                if "nextPageNumber" in data['data']['body']['searchResults']["pagination"]:
                    logger.info(f"Next_list : Yes, "
                                f" page_number: {page_number}")
                    page_number += 1
                    querystring["pageNumber"] = f"{page_number}"
                    logger.info(f"The transition to the page has been prepared {page_number}. Param: "
                                f"page_size {page_size} len(list): {len(result_list)}")
                    logger.info(f'Data result_list {result_list}')
            else:
                return result_list
        else:
            return result_list
