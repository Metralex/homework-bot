import logging
import os
import sys
import time
from http import HTTPStatus
import requests
from telebot import TeleBot
from dotenv import load_dotenv
import json


load_dotenv()

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s %(levelname)s %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('main.log')
    ]
)

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


def send_message(bot, message: str) -> None:
    """Отправляет сообщение в Telegram чат."""
    logging.info('Начинаем отправку сообщения')
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.debug(f'Успешно отправлено сообщение: {message}')
    except ConnectionError as error:
        raise RuntimeError(f'Ошибка подключения: {error}')
    except TimeoutError as error:
        raise RuntimeError(f'Таймаут при отправке: {error}')
    except (ValueError, TypeError) as error:
        raise RuntimeError(f'Ошибка данных: {error}')
    except Exception as error:
        logging.error(f'Неожиданная ошибка при отправке сообщения: {error}')
        raise RuntimeError(f'Не удалось отправить сообщение: {error}')


def get_api_answer(timestamp):
    """Проверяем ответ API."""
    try:
        response = requests.get(
            ENDPOINT, headers=HEADERS, params={'from_date': timestamp}
        )
    except Exception as error:
        raise Exception(f"Сбой при запросе к эндпоинту API: {error}")
    if response.status_code != HTTPStatus.OK:
        raise requests.HTTPError(f"API вернул код {response.status_code}")
    try:
        return response.json()
    except json.JSONDecodeError as e:
        raise ValueError(f"API вернул некорректный JSON: {e}")


def check_response(response: dict) -> list:
    """Проверяем ответ на соответствие требованиям."""
    logging.info(f"Проверка ответа: {response}")
    if not isinstance(response, dict):
        raise TypeError('В качестве аргумента передан не словарь')
    homeworks = response.get('homeworks')
    current_date = response.get('current_date')
    if homeworks is None or current_date is None:
        raise KeyError('Ключи в ответе API не соответсвуют ожидаемым')
    if not isinstance(homeworks, list):
        raise TypeError('В списке домашних работ неверный тип данных')
    return homeworks


def parse_status(homework: dict) -> str:
    """Парсим статус домашки."""
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')

    if not homework_name:
        raise KeyError(f'Пустое значение по ключу {homework_name}')
    if homework_status not in HOMEWORK_VERDICTS:
        message = 'Недокументированный статус домашней работы.'
        raise ValueError(message)
    verdict = HOMEWORK_VERDICTS[homework_status]
    logging.info('Обновлен статус проверки работы.')
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Check that all required environment variables are available."""
    tokens = {
        'PRACTICUM_TOKEN': PRACTICUM_TOKEN,
        'TELEGRAM_TOKEN': TELEGRAM_TOKEN,
        'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID
    }
    missing_tokens = [name for name, value in tokens.items() if not value]
    if missing_tokens:
        for token in missing_tokens:
            logging.critical(
                f'Отсутствует обязательная переменная окружения: {token}'
            )
        return False
    return True


def main():
    """Основная логика работы бота."""
    bot = TeleBot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    if not check_tokens():
        logging.critical('Отсутствует переменная окружения')
        sys.exit('Бот завершил работу')

    while True:
        try:
            response = get_api_answer(current_timestamp)
            homeworks = check_response(response)
            if homeworks:
                status = parse_status(homeworks[0])
                send_message(bot, status)
            else:
                logging.debug(
                    'Отсутствие изменения статуса: нет новых домашних работ')
        except RuntimeError:
            logging.error('Ошибка отправки сообщения в Telegram')
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logging.error(message)
            send_message(bot, message)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s %(levelname)s %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('main.log')
        ]
    )

    main()
