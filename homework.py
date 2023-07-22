import logging
import os
import sys
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler(stream=sys.stdout)
logger.addHandler(handler)
formatter = logging.Formatter(
    '{asctime}, {levelname}, {name}, {message}', style='{'
)
handler.setFormatter(formatter)


def check_tokens():
    """Проверка переменных окружения."""
    return all((PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID))


def send_message(bot, message):
    """Отправка сообщения в чат."""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logger.debug(f'Отправлено сообщение: {message}')
    except telegram.error.TelegramError as error:
        logger.error(f'Ошибка отправки сообщения: {error}')


def get_api_answer(timestamp):
    """Отправка запроса к API."""
    payload = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=payload)
    except requests.RequestException as error:
        logger.error(
            f'Сбой при запросе к API-сервису: {error}'
        )
    if response.status_code != HTTPStatus.OK:
        error_message = (
            f'Не удалось выполнить успешный запрос.'
            f'Код ответа: {response.status_code}')
        logger.error(error_message)
        raise requests.RequestException(error_message)
    return response.json()


def check_response(response):
    """Проверка ответа API."""
    if not isinstance(response, dict):
        raise TypeError('Ожидается ответ в формате dict')
    if 'homeworks' not in response or 'current_date' not in response:
        error_message = ('Ответ не содержит обязательный(е) ключ(и)')
        logger.error(error_message)
        raise KeyError(error_message)
    homeworks = response.get('homeworks')
    if not isinstance(homeworks, list):
        raise TypeError('Ожидается ответ в формате list')
    if len(homeworks) == 0:
        logging.error('Получен пустой список работ')
        raise IndexError('Получен пустой список работ')
    return homeworks[0]


def parse_status(homework):
    """Получение данных из ответа API."""
    if 'homework_name' not in homework:
        error_message = ('Не был получен ключ {homework_name}')
        logger.error(error_message)
        raise KeyError(error_message)
    homework_name = homework.get('homework_name')
    if 'status' not in homework:
        error_message = ('Не был получен ключ {homework_status}')
        logger.error(error_message)
        raise KeyError(error_message)
    homework_status = homework.get('status')
    if homework_status not in HOMEWORK_VERDICTS:
        error_message = (
            f'Получен неожиданный статус работы: {homework_status}'
        )
        logger.error(error_message)
        raise KeyError(error_message)
    verdict = HOMEWORK_VERDICTS[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logger.critical(
            'Переменная(ые) окружения не найдена(ы). Бот остановлен.'
        )
        sys.exit()

    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    last_message = None

    while True:
        try:
            response = get_api_answer(timestamp)
            homework = check_response(response)
            if homework:
                new_message = parse_status(homework)
                if new_message == last_message:
                    logger.debug(
                        'Статус не изменился. '
                        'Повторный запрос через 10 минут.'
                    )
                else:
                    last_message != new_message
                    send_message(bot, new_message)

        except Exception as error:
            error_message = f'Сбой в работе программы: {error}'
            logger.error(error_message)
            send_message(bot, error_message)

        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
