import asyncio
import datetime
import json
import os
import random
import threading
import keyboard
import aiohttp
import aiofiles
import re
import configparser
import pyfiglet
from colorama import Fore, Style
from termcolor import colored
from concurrent.futures import ThreadPoolExecutor
from web3 import Web3
from web3.exceptions import TransactionNotFound, Web3Exception
infura_api_active = True
infura_limit_reached_time = None
INFURA_RATE_LIMIT_RESET_HOUR = 1 
guarda_api_active = True
guarda_limit_reached_time = None
GUARDA_RATE_LIMIT_RESET_HOUR = 1  
etherscan_api_active = True  # Переменная для отслеживания активности Etherscan API
etherscan_limit_reached_time = None  # Переменная для хранения времени достижения лимита запросов
ETHERSCAN_RATE_LIMIT_RESET_HOUR = 1  # Час сброса лимита Etherscan API (например, 1 час ночи)
pause_event = asyncio.Event()
pause_event.set() 
used_keys = set()
ascii_art = pyfiglet.figlet_format("ETH keys generator", font="standard")
colored_art = colored(ascii_art, 'cyan') 
print(colored_art)
print(Fore.CYAN + "")
print()
config = configparser.ConfigParser()
config.read('API.ini')
INFURA_URL = config['API']['INFURA_URL']
ETHERSCAN_API_KEY = config['API']['ETHERSCAN_API_KEY']
web3 = Web3(Web3.HTTPProvider(INFURA_URL))
SUCCESS_FILE = 'successful_wallets.txt'
BAD_FILE = 'bad_wallets.txt'
BALANCE_FILE = 'successful_wallets_balance.txt'
STATE_FILE = 'state.json'
ETHERSCAN_RATE_LIMIT = 5
ETHERSCAN_REQUEST_INTERVAL = 1 / ETHERSCAN_RATE_LIMIT
GROUP_RANGES = {
    'A': (0x0000000000000000000000000000000000000000000000000000000000000001, 0x00000000000000000000000000000000000000000000000000000000FFFFFFFF),
    'B': (0x0000000000000000000000000000000000000000000000000000000100000000, 0x000000000000000000000000000000000000000000000000FFFFFFFF00000000),
    'C': (0x0000000000000000000000000000000000000000000000010000000000000000, 0x0000000000000000000000000000000000000000FFFFFFFF0000000000000000),
    'D': (0x0000000000000000000000000000000000000001000000000000000000000000, 0x00000000000000000000000000000000FFFFFFFF000000000000000000000000),
    'E': (0x0000000000000000000000000000000100000000000000000000000000000000, 0x000000000000000000000000FFFFFFFF00000000000000000000000000000000),
    'F': (0x0000000000000000000000010000000000000000000000000000000000000000, 0x0000000000000000FFFFFFFF0000000000000000000000000000000000000000),
    'G': (0x0000000000000000000000000000000000000000000000000000000000000000, 0x00000000FFFFFFFF000000000000000000000000000000000000000000000000),
    'H': (0x0000000100000000000000000000000000000000000000000000000000000000, 0xFFFFFFFF00000000000000000000000000000000000000000000000000000000),
}
def toggle_pause():
    if pause_event.is_set():
        pause_event.clear()
        print(Fore.CYAN + "Код приостановлен." + Style.RESET_ALL)
    else:
        pause_event.set()
        print(Fore.CYAN + "Код продолжен." + Style.RESET_ALL)
def listen_for_pause():
    keyboard.add_hotkey('page down', toggle_pause)
    keyboard.add_hotkey('page up', toggle_pause)
def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'r') as f:
            return json.load(f)
    return {'start_index': 0}
def save_state(index):
    with open(STATE_FILE, 'w') as f:
        json.dump({'start_index': index}, f)
async def check_internet():
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get('http://www.google.com', timeout=5) as response:
                return response.status == 200
    except (aiohttp.ClientError, asyncio.TimeoutError):
        return False
async def check_all_apis(address):
    while True:
        has_transactions = await check_transactions(address)
        if has_transactions is not None:
            return has_transactions
        else:
            print(Fore.YELLOW + "Все API недоступны. Ожидание до следующего сброса лимита..." + Style.RESET_ALL)
            now = datetime.datetime.now()
            reset_time = now.replace(hour=1, minute=0, second=0, microsecond=0)
            if reset_time <= now:
                reset_time += datetime.timedelta(days=1)
            wait_time = (reset_time - now).total_seconds()
            print(f"Ожидание {wait_time} секунд до следующего сброса лимита.")
            await asyncio.sleep(wait_time)  # Ждем до часа ночи    
def can_use_guarda():
    global guarda_api_active
    if guarda_api_active:
        return True
    else:
        return False  # Guarda не активен
def can_use_infura():
    global infura_api_active, infura_limit_reached_time
    now = datetime.datetime.now()
    if infura_limit_reached_time is None:
        infura_api_active = True
        return infura_api_active
    if now >= infura_limit_reached_time:
        infura_api_active = True
        infura_limit_reached_time = None
    return infura_api_active
def can_use_etherscan():
    global etherscan_api_active, etherscan_limit_reached_time
    now = datetime.datetime.now()
    if etherscan_limit_reached_time is None:
        etherscan_api_active = True
        return etherscan_api_active
    if now >= etherscan_limit_reached_time:
        etherscan_api_active = True
        etherscan_limit_reached_time = None
    return etherscan_api_active
async def check_transactions(address):
    global guarda_api_active, infura_api_active, etherscan_api_active
    if can_use_guarda():
        print(Fore.CYAN + f"Проверка транзакций через Guarda для адреса: {address}" + Style.RESET_ALL)
        has_transactions_guarda = await check_transactions_guarda(address)
        if has_transactions_guarda is not None:
            if has_transactions_guarda:
                return has_transactions_guarda
            else:
                guarda_api_active = False  # Устанавливаем флаг неактивности для Guarda
                print(Fore.YELLOW + "Guarda недоступен, переключаемся на Infura." + Style.RESET_ALL)
    if can_use_infura():
        print(Fore.CYAN + f"Проверка транзакций через Infura для адреса: {address}" + Style.RESET_ALL)
        has_transactions_infura = await check_transactions_infura(address)
        if has_transactions_infura is not None:
            if has_transactions_infura:
                return has_transactions_infura
            else:
                infura_api_active = False  # Устанавливаем флаг неактивности для Infura
                print(Fore.YELLOW + "Infura недоступен, переключаемся на Etherscan." + Style.RESET_ALL)
    if can_use_etherscan():
        print(Fore.CYAN + f"Проверка транзакций через Etherscan для адреса: {address}" + Style.RESET_ALL)
        has_transactions_etherscan = await check_transactions_etherscan(address)
        if has_transactions_etherscan is not None:
            return has_transactions_etherscan
        else:
            etherscan_api_active = False  # Устанавливаем флаг неактивности для Etherscan
            print(Fore.YELLOW + "Etherscan недоступен." + Style.RESET_ALL)
    print(Fore.RED + f"Ошибка: ни Guarda, ни Infura, ни Etherscan, не смогли обработать запрос для адреса: {address}" + Style.RESET_ALL)
    return None
async def check_transactions_guarda(address):
    global guarda_api_active, guarda_limit_reached_time
    if not can_use_guarda():
        return None  # Если Guarda не доступен, сразу выходим
    try:
        if can_use_guarda():
            async with aiohttp.ClientSession() as session:
                async with session.get(f'https://ethbook.guarda.co/api/v2/address/{address}', timeout=10) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data.get('transactions_count', 0) > 0
                    elif resp.status == 429:
                        print(Fore.YELLOW + "Достигнут лимит Guarda API. Переключение на другой API..." + Style.RESET_ALL)
                        guarda_api_active = False
                        guarda_limit_reached_time = datetime.datetime.now()
                        return None
                    else:
                        print(Fore.RED + f"Ошибка при получении данных для {address} через Guarda: {resp.status}" + Style.RESET_ALL)
                        return None
        else:
            return None
    except (aiohttp.ClientError, asyncio.TimeoutError) as e:
        print(Fore.RED + f"Ошибка: {e}" + Style.RESET_ALL)
        return None   
async def check_transactions_infura(address):
    global infura_api_active, infura_limit_reached_time
    if not can_use_infura():
        return None  # Если Infura не доступен, сразу выходим
    try:
        if can_use_infura():
            loop = asyncio.get_running_loop()
            transactions = await loop.run_in_executor(ThreadPoolExecutor(), web3.eth.get_transaction_count, address)
            return transactions > 0
        else:
            print("Infura API неактивен.")
            return None
    except Web3Exception as e:
        if '429' in str(e):
            print("Лимит запросов Infura превышен. Переключение на Etherscan...")
            infura_api_active = False
            infura_limit_reached_time = datetime.datetime.now() + datetime.timedelta(hours=1)  # Установите время сброса
            return None
        else:
            print(f"Ошибка подключения к Infura API: {e}")
            return None
    except Exception as e:
        print(f"Ошибка в Infura: {e}")
        return None
async def check_transactions_etherscan(address):
    global etherscan_api_active, etherscan_limit_reached_time
    now = datetime.datetime.now()
    if not can_use_etherscan():
        print("Etherscan API временно недоступен. Попробуем Infura...")
        if can_use_infura():
            print("Переключаемся на Infura...")
            return await check_transactions_infura(address)  # Переход на Infura
        else:
            print("Infura тоже недоступен. Попробуем Guarda...")
            if can_use_guarda():
                print("Переключаемся на Guarda...")
                return await check_transactions_guarda(address)  # Переход на Guarda
            else:
                print("Все API недоступны.")
                return None
    api_key = ETHERSCAN_API_KEY
    url = f'https://api.etherscan.io/api?module=account&action=txlist&address={address}&startblock=0&endblock=99999999&sort=desc&apikey={api_key}'
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data['status'] == '1':
                        transactions = data['result']
                        return transactions  # Возвращаем список транзакций
                    else:
                        print(f"Ошибка Etherscan: {data['message']}")
                elif resp.status == 429:  # Превышен лимит запросов
                    print("Достигнут лимит Etherscan API. Устанавливаю время сброса...")
                    etherscan_api_active = False  # Деактивируем API
                    etherscan_limit_reached_time = now
                    etherscan_limit_reached_time = etherscan_limit_reached_time.replace(hour=ETHERSCAN_RATE_LIMIT_RESET_HOUR, minute=0, second=0, microsecond=0)
                    if etherscan_limit_reached_time <= now:
                        etherscan_limit_reached_time += datetime.timedelta(days=1)
                    print("API будет снова доступен после", etherscan_limit_reached_time)
                    print("Переключаемся на Infura...")
                    return await check_transactions_infura(address)  # Переход на Infura
                else:
                    print(f"Ошибка: {resp.status}")
    except (aiohttp.ClientError, asyncio.TimeoutError) as e:
        print(Fore.RED + f"Ошибка при запросе к Etherscan: {e}" + Style.RESET_ALL)
    return None  # Если ничего не сработало, возвращаем None
async def get_balance_etherscan(address):
    global etherscan_api_active, etherscan_limit_reached_time
    try:
        if can_use_etherscan():
            async with aiohttp.ClientSession() as session:
                async with session.get(f'https://api.etherscan.io/api?module=account&action=balance&address={address}&tag=latest&apikey={ETHERSCAN_API_KEY}', timeout=10) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        balance = int(data['result'])  
                        return web3.from_wei(balance, 'ether') 
                    elif resp.status == 429:
                        print(Fore.YELLOW + "Достигнут лимит Etherscan API. Переключение на Infura API..." + Style.RESET_ALL)
                        etherscan_api_active = False
                        etherscan_limit_reached_time = datetime.datetime.now()
                        return None
                    else:
                        print(Fore.RED + f"Ошибка при получении баланса для {address}: {resp.status}" + Style.RESET_ALL)
                        return None
        else:
            return None
    except (aiohttp.ClientError, asyncio.TimeoutError) as e:
        print(Fore.RED + f"Ошибка: {e}" + Style.RESET_ALL)
        return None
async def check_transactions(address):
    if can_use_guarda():
        print(Fore.CYAN + f"Проверка транзакций через Guarda для адреса: {address}" + Style.RESET_ALL)
        has_transactions_guarda = await check_transactions_guarda(address)
        if has_transactions_guarda is not None:
            return has_transactions_guarda
    if can_use_infura():
        print(Fore.CYAN + f"Проверка транзакций через Infura для адреса: {address}" + Style.RESET_ALL)
        has_transactions_infura = await check_transactions_infura(address)
        if has_transactions_infura is not None:
            return has_transactions_infura  
        else:
            infura_api_active = False
            print(Fore.YELLOW + "Infura недоступен, переключаемся на Etherscan." + Style.RESET_ALL)
    if can_use_etherscan():
        print(Fore.CYAN + f"Проверка транзакций через Etherscan для адреса: {address}" + Style.RESET_ALL)
        has_transactions_etherscan = await check_transactions_etherscan(address)
        if has_transactions_etherscan is not None:
            return has_transactions_etherscan 
        else:
            etherscan_api_active = False
            print(Fore.YELLOW + "Etherscan недоступен." + Style.RESET_ALL)
    print(Fore.RED + f"Ошибка: ни Infura, ни Etherscan, ни Guarda не смогли обработать запрос для адреса: {address}" + Style.RESET_ALL)
    return None
def generate_private_key():
    return Web3.keccak(os.urandom(32)).hex()
def get_address_from_private_key(private_key):
    account = web3.eth.account.from_key(private_key)
    return account.address
def is_valid_eth_address(address):
    return Web3.is_address(address)
def get_balance(address):
    try:
        balance = web3.eth.get_balance(address)
        return web3.from_wei(balance, 'ether')
    except (web3.exceptions.InvalidAddress, Web3Exception) as e:
        print(Fore.RED + f"Ошибка при получении баланса для {address}: {e}" + Style.RESET_ALL)
        return None
    except Exception as e:
        print(Fore.RED + f"Ошибка: {e}" + Style.RESET_ALL)
        return None
def generate_weak_private_key():
    weak_patterns = [
        b'\x00' * 31 + b'\x01',  
        b'\x01' * 32,             
        b'\xff' * 32,            
        b'\x12' * 16 + b'\x34' * 16,
        b'\x56' * 32,            
        b'\x00' * 30 + b'\xFF\xFF',
    ]
    pattern = random.choice(weak_patterns)
    random_byte_position = random.randint(0, 31)  
    random_byte_value = random.randint(0, 64)  # Случайное значение байта (0-255)
    pattern = bytearray(pattern)
    pattern[random_byte_position] = random_byte_value  # Вносим изменение
    return Web3.keccak(bytes(pattern)).hex()
def generate_vanity_address(prefix=None, suffix=None):
    while True:
        private_key = generate_private_key()
        address = get_address_from_private_key(private_key)
        address_lower = address.lower()
        if prefix and suffix:
            if address_lower.startswith(prefix.lower()) and address_lower.endswith(suffix.lower()):
                return private_key, address
        elif prefix:
            if address_lower.startswith(prefix.lower()):
                return private_key, address
        elif suffix:
            if address_lower.endswith(suffix.lower()):
                return private_key, address
def choose_vanity_pattern():
    print(Fore.CYAN + "Выберите шаблон для Vanity-адреса:" + Style.RESET_ALL)
    while True:
        prefix = input(Fore.CYAN + "Введите префикс (A-F,0-9) - желательно не больше 4 символов '0xABDC, 0xA1B2' (оставьте пустым, если не нужен): " + Style.RESET_ALL)
        if re.match(r'^(0x)?[a-fA-F0-9]{0,4}$', prefix):
            if prefix and not prefix.startswith('0x'):
                prefix = '0x' + prefix
            break
        else:
            print(Fore.RED + "Ошибка: префикс может содержать только латинские буквы (0-9, a-f) и, при желании, '0x' в начале." + Style.RESET_ALL)
    while True:
        suffix = input(Fore.CYAN + "Введите суффикс (A-F,0-9) - желательно не больше 4 символов 'ABDC, A1B2' (оставьте пустым, если не нужен): " + Style.RESET_ALL)
        if re.match(r'^[a-fA-F0-9]{0,4}$', suffix):
            break
        else:
            print(Fore.RED + "Ошибка: суффикс может содержать только латинские буквы (0-9, a-f) и цифры." + Style.RESET_ALL)
    if not prefix and not suffix:
        print(Fore.RED + "Необходимо указать хотя бы префикс или суффикс." + Style.RESET_ALL)
        return choose_vanity_pattern()
    return prefix, suffix
def choose_generation_method():
    while True:
        print(Fore.CYAN + "Выберите метод генерации:" + Style.RESET_ALL)
        print(Fore.CYAN + "1. Стандартная" + Style.RESET_ALL)
        print(Fore.CYAN + "2. Низкая энтропия" + Style.RESET_ALL)
        print(Fore.CYAN + "3. Брутфорс Vanity-адресов" + Style.RESET_ALL)
        print(Fore.CYAN + "4. Генерация в пределах группы, разбиение ключа на 32-битные части (A,B,C,D,E,F,G,H)" + Style.RESET_ALL)
        print(Fore.CYAN + "Для паузы нажмите 'PgDN', для возобновления работы нажмите 'PgUp'" + Style.RESET_ALL)
        choice = input(Fore.CYAN + "Введите номер метода (1-4): " + Style.RESET_ALL)
        if choice in ['1', '2', '3', '4']: 
            return int(choice)
        else:
            print(Fore.RED + "Неверный выбор метода. Пожалуйста, попробуйте снова." + Style.RESET_ALL)
def choose_group():
    print(Fore.CYAN + "Выберите группу (A,B,C,D,E,F,G,H):" + Style.RESET_ALL)
    group = input(Fore.CYAN + "Введите букву группы: " + Style.RESET_ALL).upper()
    if group in GROUP_RANGES:
        return group
    else:
        print(Fore.RED + "Неверный выбор группы. Попробуйте снова." + Style.RESET_ALL)
        return choose_group()
def generate_private_key_in_group(group):
    start_range, end_range = GROUP_RANGES[group]
    private_key_int = random.randint(start_range, end_range)
    private_key_bytes = private_key_int.to_bytes(32, byteorder='big')
    return Web3.keccak(private_key_bytes).hex()
def generate_private_key_by_method(method, used_keys):
    while True:
        if method == 1:
            private_key = generate_private_key() 
        elif method == 2:
            private_key = generate_weak_private_key()  
        elif method == 3:
            return None
        else:
            raise ValueError("Неверный выбор метода.")
        if private_key not in used_keys:
            used_keys.add(private_key)
            return private_key
        else:
            print(Fore.RED + "Этот ключ уже был сгенерирован, пробуем снова..." + Style.RESET_ALL)
pause = False
vanity_pattern = None 
def toggle_pause():
    global pause
    pause = not pause
    state = "приостановлен" if pause else "продолжен"
    print(Fore.CYAN + f"Код {state}." + Style.RESET_ALL)
def listen_for_pause():
    keyboard.add_hotkey('page down', toggle_pause)
    keyboard.add_hotkey('page up', toggle_pause)
async def main():
    global vanity_pattern, infura_api_active, etherscan_api_active
    infura_api_active = True
    etherscan_api_active = True
    state = load_state()
    start_index = state['start_index']
    success_wallets = set()
    bad_wallets = set()
    success_wallets_balance = set()
    method = choose_generation_method()
    if method in [1, 2, 3, 4]:
        print(Fore.CYAN + f"Начата генерация с использованием метода {method}" + Style.RESET_ALL)
    threading.Thread(target=listen_for_pause, daemon=True).start()
    group = None 
    if method == 4:
        group = choose_group()
        print(Fore.CYAN + f"Начинается генерация в группе {group}." + Style.RESET_ALL)       
    try:
        while True:
            if pause:
                await asyncio.sleep(0.1)
                continue
            if method == 4:
                await handle_group_generation(group, success_wallets, bad_wallets, success_wallets_balance, start_index)
            elif method == 3:
                await handle_vanity_generation(success_wallets, bad_wallets, success_wallets_balance, start_index)
            else:
                await handle_standard_generation(method, success_wallets, bad_wallets, success_wallets_balance, start_index, used_keys)
    except KeyboardInterrupt:
        print(Fore.RED + "Программа остановлена пользователем." + Style.RESET_ALL)
    except Exception as e:
        print(Fore.RED + f"Произошла ошибка: {e}" + Style.RESET_ALL)
    finally:
        save_state(start_index)
        print(Fore.GREEN + "Завершение программы..." + Style.RESET_ALL)
async def handle_group_generation(group, success_wallets, bad_wallets, success_wallets_balance, start_index):
    private_key = generate_private_key_in_group(group)
    address = get_address_from_private_key(private_key)
    print(Fore.CYAN + f"Сгенерированный ключ: {private_key}, адрес: {address}" + Style.RESET_ALL)
    if not is_valid_eth_address(address):
        print(Fore.RED + f"Неверный адрес Ethereum: {address}" + Style.RESET_ALL)
        return
    has_transactions = await check_transactions(address)
    if has_transactions is None:
        return
    if has_transactions:
        print(Fore.GREEN + f"Адрес с транзакциями: {address}" + Style.RESET_ALL)
        success_wallets.add(address)
        await write_to_file(SUCCESS_FILE, f"{address} {private_key}\n")
        balance = await get_balance_etherscan(address)
        if balance > 0:
            success_wallets_balance.add(address)
            await write_to_file(BALANCE_FILE, f"{address} {balance}\n")
    else:
        print(Fore.RED + f"Нет транзакций на адресе: {address}" + Style.RESET_ALL)
        bad_wallets.add(address)
        await write_to_file(BAD_FILE, f"{address} {private_key}\n")
    start_index += 1
    save_state(start_index)
    await asyncio.sleep(ETHERSCAN_REQUEST_INTERVAL)
async def handle_vanity_generation(success_wallets, bad_wallets, success_wallets_balance, start_index):
    prefix, suffix = choose_vanity_pattern()
    print(Fore.CYAN + f"Начата генерация Vanity-адресов с паттерном: {prefix}...{suffix}" + Style.RESET_ALL)
    while True:
        private_key, address = generate_vanity_address(prefix, suffix)
        print(Fore.CYAN + f"Сгенерирован Vanity-адрес: {address}, Приватный ключ: {private_key}" + Style.RESET_ALL)
        if not is_valid_eth_address(address):
            print(Fore.RED + f"Неверный адрес Ethereum: {address}" + Style.RESET_ALL)
            continue
        has_transactions = await check_transactions(address)
        if has_transactions is None:
            continue
        if has_transactions:
            print(Fore.GREEN + f"Адрес с транзакциями: {address}" + Style.RESET_ALL)
            success_wallets.add(address)
            await write_to_file(SUCCESS_FILE, f"{address} {private_key}\n")
            balance = await get_balance_etherscan(address)
            if balance > 0:
                success_wallets_balance.add(address)
                await write_to_file(BALANCE_FILE, f"{address} {balance}\n")
        else:
            print(Fore.RED + f"Нет транзакций на адресе: {address}" + Style.RESET_ALL)
            bad_wallets.add(address)
            await write_to_file(BAD_FILE, f"{address} {private_key}\n")
        start_index += 1
        save_state(start_index)
        await asyncio.sleep(ETHERSCAN_REQUEST_INTERVAL)
async def handle_standard_generation(method, success_wallets, bad_wallets, success_wallets_balance, start_index, used_keys):
    private_key = generate_private_key_by_method(method, used_keys)
    if not private_key:
        print(Fore.RED + "Не удалось сгенерировать ключ. Попробуйте снова." + Style.RESET_ALL)
        return
    address = get_address_from_private_key(private_key)
    print(Fore.CYAN + f"Сгенерированный ключ: {private_key}, адрес: {address}" + Style.RESET_ALL)
    if not is_valid_eth_address(address):
        print(Fore.RED + f"Неверный адрес Ethereum: {address}" + Style.RESET_ALL)
        return
    has_transactions = await check_transactions(address)
    if has_transactions is None:
        return
    if has_transactions:
        print(Fore.GREEN + f"Адрес с транзакциями: {address}" + Style.RESET_ALL)
        success_wallets.add(address)
        await write_to_file(SUCCESS_FILE, f"{address} {private_key}\n")
        balance = await get_balance_etherscan(address)
        if balance > 0:
            success_wallets_balance.add(address)
            await write_to_file(BALANCE_FILE, f"{address} {balance}\n")
    else:
        print(Fore.RED + f"Нет транзакций на адресе: {address}" + Style.RESET_ALL)
        bad_wallets.add(address)
        await write_to_file(BAD_FILE, f"{address} {private_key}\n")
    start_index += 1
    await asyncio.sleep(ETHERSCAN_REQUEST_INTERVAL)
async def write_to_file(filename, content):
    async with aiofiles.open(filename, 'a') as f:
        await f.write(content)
if __name__ == "__main__":
    asyncio.run(main())