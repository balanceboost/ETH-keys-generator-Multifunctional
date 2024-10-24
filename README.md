# ETH-keys-generator-Multifunctional
![ETH MULTI](https://github.com/user-attachments/assets/1877fb0f-f740-4b0c-a3d9-fcd557d4695b)
Данный скрипт позволяет:
1. Генерировать Ethereum-адреса с помощью различных методов(Стандартная генерация, Низкая энтропия, Брутфорс Vanity-адресов, Генерация в пределах группы (разбиение ключа на 32-битные части (A,B,C,D,E,F,G,H))
2. Проверять, есть ли у сгенерированных адресов транзакции.
3. Получать и записывать баланс адресов.

Описание методов генерации ключа ETH:
1. Стандартная генерация:
Создается случайный ключ на основе криптографической функции хеширования Keccak.
- Преимущества:
Высокая степень энтропии и безопасность.
Подходит для использования в реальных приложениях и для создания безопасных кошельков.
- Недостатки:
Не подходит для тестирования безопасности т.к имеет максимально маленький шанс генерации уже существующего ключа.

2. Низкая энтропия:
Приватный ключ генерируется с использованием функции, которая создает ключи с предсказуемыми шаблонами (например, последовательности из нулей или одинаковых байтов).
- Преимущества:
Быстрое создание ключей, что может быть полезно для целей тестирования или обучения.
- Недостатки:
Ключи с низкой энтропией небезопасны и не должны использоваться для реальных транзакций или хранения ценностей. В этом методе наибольший шанс генерации уже существующего ключа.

3. Брутфорс Vanity-адресов:
Этот метод не генерирует ключи напрямую, а создает адреса с определёнными паттернами (префиксами и/или суффиксами). Используется функция, которая создает адреса до тех пор, пока не будет найдено совпадение с заданным шаблоном. 
- Преимущества:
Как бонус можете использовать для генерации себе красивых ключей, наподобие "0xDEAD6F0e71b9BEDa715cAa128D4D001d98F21666" и подобных.
- Недостатки:
Время генерации может быть непредсказуемым, особенно для сложных шаблонов, из-за необходимости перебора большого числа адресов. Так же ключи не являются безопасными. Большой шанс генерации одинаковых ключей. 

4. Генерация в пределах группы:
Генерация ключей производится в определенных диапазонах, заданных группами (A, B, C, D, E, F, G, H). Ключ разбивается на 8 частей и генерируется только 1\8 его часть.
- Преимущества:
Ограничение диапазона генерации ключей может быть полезно для создания ключей, соответствующих определенным критериям или для целей тестирования. Так же имеет большой шанс найти небезопасные ключи.
- Недостатки:
Генерируемые ключи могут быть менее разнообразными по сравнению с полностью случайными.

Запуск и использование:
1. Запустите код в среде Python с установите все необходимые библиотеки из файла ```"requirements.txt"``` командой ```"pip install -r requirements.txt"```.
2. Выберите один из методов, который вам нужен, и вызовите соответствующую функцию.
3. Используется три API для проверки транзакций: Guarda, Infura и Etherscan, с автоматическим переключением при превышении лимита запросов.
4. Результаты записываются в файлы: ```successful_wallets.txt```(адреса с транзакциями), ```bad_wallets.txt```(адреса без транзакций), и ```successful_wallets_balance.txt```(адреса с балансом).

Скрипт использует файл конфигурации API.ini, который должен содержать следующие ключи:
```
INFURA_URL: URL Infura API.
ETHERSCAN_API_KEY: ключ API для Etherscan.
```
Файл API.ini находится рядом с исполняемым файлом, добавьте свои API для каждого сервиса. 

    Для поддержки автора: TFbR9gXb5r6pcALasjX1FKBArbKc4xBjY8
-------------------------------------------------------------------------------------------
# ETH-keys-generator-Multifunctional
![ETH MULTI](https://github.com/user-attachments/assets/1877fb0f-f740-4b0c-a3d9-fcd557d4695b)
This script allows you to:
1. Generate Ethereum addresses using various methods (Standard generation, Low entropy generation, Vanity address brute-force, Generation within groups by splitting the key into 32-bit parts (A, B, C, D, E, F, G, H)).
2. Check if the generated addresses have any transactions.
3. Retrieve and log the balance of the addresses.

Description of ETH key generation methods:
1. Standard Generation:
A random key is created based on the cryptographic hashing function Keccak.
- Advantages:
High entropy and security.
Suitable for real-world applications and creating secure wallets.
- Disadvantages:
Not suitable for security testing as it has a very low chance of generating an existing key.

2. Low Entropy Generation:
The private key is generated using a function that creates keys with predictable patterns (e.g., sequences of zeros or identical bytes).
- Advantages:
Quick key generation, useful for testing or educational purposes.
- Disadvantages:
Low-entropy keys are insecure and should not be used for real transactions or storing assets. This method has the highest chance of generating an existing key.

3. Vanity Address Brute-Force:
This method doesn't generate keys directly but creates addresses with specific patterns (prefixes and/or suffixes). It keeps generating addresses until a match with the desired pattern is found.
- Advantages:
Allows generating custom, "vanity" addresses like "0xDEAD6F0e71b9BEDa715cAa128D4D001d98F21666".
- Disadvantages:
The generation time can be unpredictable, especially for complex patterns due to the need to brute-force many addresses. The keys may also be less secure with a higher chance of duplicates.

4. Generation Within Groups:
Keys are generated within specific ranges defined by groups (A, B, C, D, E, F, G, H). The key is split into 8 parts, and only one part of it is generated.
- Advantages:
Limiting the key generation range can be useful for creating keys that meet specific criteria or for testing purposes. There is also a higher chance of finding insecure keys.
- Disadvantages:
The generated keys may be less diverse compared to fully random keys.

Running and Usage:
1. Run the code in a Python environment and install all required libraries from the ```requirements.txt file``` using the command: ```pip install -r requirements.txt```
2. Choose the desired generation method and call the corresponding function.
3. The script uses three APIs for transaction checking: Guarda, Infura, and Etherscan, with automatic switching when the request limit is reached.
4. Results are saved into the following files: ```successful_wallets.txt``` (addresses with transactions),
```bad_wallets.txt``` (addresses without transactions) and
```successful_wallets_balance.txt```(addresses with balances).

The script uses a configuration file API.ini that must contain the following keys:
```
INFURA_URL: URL for the Infura API.
ETHERSCAN_API_KEY: API key for Etherscan.
```
The API.ini file should be located alongside the script, and you need to add your API keys for each service.

    To support the author: TFbR9gXb5r6pcALasjX1FKBArbKc4xBjY8

