# ETH-keys-generator-Multifunctional
![1](https://github.com/user-attachments/assets/e72d5fe2-0be9-47bf-bf7d-6dc03c550047)

Данный скрипт позволяет:
    Данный скрипт предназначен для генерации ETH-адресов с использованием различных методов, проверки наличия транзакций на этих адресах и получения их баланса. Он предоставляет гибкий инструментарий для тестирования, обучения или поиска уязвимых ключей, но не рекомендуется для создания безопасных кошельков для реальных транзакций.

Возможности скрипта:
- Генерация ETH-адресов с использованием 12 различных методов, включая стандартную генерацию, методы с низкой энтропией, брутфорс vanity-адресов, генерацию в пределах групп (A–H) и другие.
- Проверка наличия транзакций на сгенерированных адресах через API.
- Получение и запись баланса адресов в ETH.
- Сравнение сгенерированных адресов с адресами из текстовых файлов.
- Сохранение результатов в файлы: successful_wallets.txt (адреса с транзакциями), successful_wallets_balance.txt (адреса с ненулевым балансом), bad_wallets.txt (адреса без транзакций).
- Отправка уведомлений в Telegram при нахождении активных кошельков.
- Асинхронная обработка запросов для повышения производительности.
- Поддержка паузы/возобновления работы с помощью клавиш Page Up/Page Down.

Описание методов генерации ключей для ETH:
1. Стандартная генерация
Создаётся случайный 32-байтный приватный ключ с использованием криптографически безопасного генератора (bitcoinlib).
Преимущества: Высокая энтропия, безопасность. Подходит для создания реальных кошельков.
Недостатки: Минимальный шанс сгенерировать существующий ключ, что делает метод неподходящим для поиска уязвимых адресов.
2. Брутфорс Vanity-адресов
Генерирует ключи, пока адрес не будет соответствовать заданному префиксу или суффиксу.
Преимущества: Позволяет создавать "красивые" адреса.
Недостатки: Время генерации зависит от сложности шаблона. Ключи менее безопасны, есть риск коллизий.
3. Генерация в пределах группы (A–H)
Приватный ключ генерируется в заданных числовых диапазонах, разбивая пространство ключей на 8 групп.
Преимущества: Ограничение диапазона упрощает тестирование и повышает шанс нахождения уязвимых ключей.
Недостатки: Ключи менее разнообразны, что снижает их безопасность.
4. Мнемонические фразы со слабым RNG
Генерирует мнемонические фразы (BIP-39) с использованием слабого генератора случайных чисел или из словаря, затем преобразует их в ключи (BIP-32).
Преимущества: Удобно для тестирования мнемоник. Высокий шанс нахождения уязвимых фраз.
Недостатки: Ключи крайне небезопасны из-за предсказуемости.
5. Уязвимые комбинированные ключи
Создаёт ключи с предсказуемыми паттернами (повторяющиеся байты, нулевые байты, последовательности).
Преимущества: Быстрая генерация для тестирования уязвимостей.
Недостатки: Небезопасны, не подходят для реальных транзакций.
6. Ключи на основе времени
Использует временные метки как основу для создания ключей.
Преимущества: Простота реализации, подходит для тестов.
Недостатки: Высокая предсказуемость, ключи уязвимы.
7. Ключи через Mersenne Twister
Применяет псевдослучайный генератор Mersenne Twister для создания ключей.
Преимущества: Быстрая генерация для тестирования.
Недостатки: Низкая энтропия, ключи небезопасны.
8. Конкатенация слабых источников
Комбинирует слабые источники (временные метки, PID, константы) для создания ключей.
Преимущества: Подходит для поиска уязвимых кошельков.
Недостатки: Ключи предсказуемы и небезопасны.
9. Ключи из паролей
Хэширует пароли (SHA-256) для создания приватных ключей.
Преимущества: Удобно для тестирования паролей из словаря.
Недостатки: Зависит от качества паролей, ключи уязвимы.
10. Ключи через устаревшие хэш-функции (MD5)
Использует MD5 для генерации ключей.
Преимущества: Быстрое создание для тестирования уязвимостей.
Недостатки: MD5 устарел, ключи предсказуемы.
11. Псевдослучайные последовательности (Xorshift)
Применяет алгоритм Xorshift для генерации ключей.
Преимущества: Быстрая генерация, подходит для тестов.
Недостатки: Низкая энтропия, ключи небезопасны.
12. Усечённые большие числа
Генерирует ключи, усекающие большие случайные числа.
Преимущества: Простота, подходит для тестирования.
Недостатки: Усечение снижает энтропию, ключи уязвимы.

Запуск и использование:
1. Запустите код в среде Python с установите все необходимые библиотеки из файла ```"requirements.txt"``` командой ```"pip install -r requirements.txt"```.
2. Выберите один из методов, который вам нужен, и вызовите соответствующую функцию.
3. Используется два API для проверки транзакций: Infura и Etherscan, с автоматическим переключением при превышении лимита запросов.
4. Результаты записываются в файлы: ```successful_wallets.txt```(адреса с транзакциями), ```bad_wallets.txt```(адреса без транзакций), и ```successful_wallets_balance.txt```(адреса с балансом).

Скрипт использует файл конфигурации API.ini, который должен содержать следующие ключи:
```
INFURA_URL: URL Infura API.
ETHERSCAN_API_KEY: ключ API для Etherscan.
TELEGRAM_BOT_TOKEN = 
TELEGRAM_CHAT_ID = 
```
Файл API.ini находится рядом с исполняемым файлом, добавьте свои API для каждого сервиса. 

    Для поддержки автора: TFbR9gXb5r6pcALasjX1FKBArbKc4xBjY8
-------------------------------------------------------------------------------------------
# ETH-keys-generator-Multifunctional
![1](https://github.com/user-attachments/assets/e72d5fe2-0be9-47bf-bf7d-6dc03c550047)

This script allows you to:
This script is designed to generate ETH addresses using various methods, check for transactions on these addresses and get their balance. It provides a flexible toolkit for testing, training or searching for vulnerable keys, but is not recommended for creating secure wallets for real transactions.

Script features:
- Generate ETH addresses using 12 different methods, including standard generation, low entropy methods, vanity address brute force, generation within groups (A-H) and others.
- Check for transactions on generated addresses via API.
- Get and write the balance of addresses in ETH.
- Compare generated addresses with addresses from text files.
- Saving results to files: successful_wallets.txt (addresses with transactions), successful_wallets_balance.txt (addresses with non-zero balance), bad_wallets.txt (addresses without transactions).
- Sending notifications to Telegram when active wallets are found.
- Asynchronous request processing to improve performance.
- Pause/resume support using Page Up/Page Down keys.

Description of key generation methods for ETH:
1. Standard generation
A random 32-byte private key is created using a cryptographically secure generator (bitcoinlib).
Advantages: High entropy, security. Suitable for creating real wallets.
Disadvantages: Minimal chance of generating an existing key, which makes the method unsuitable for finding vulnerable addresses.
2. Vanity Brute Force
Generates keys until the address matches the specified prefix or suffix.
Pros: Allows you to create "pretty" addresses.
Cons: Generation time depends on the complexity of the template. Keys are less secure, there is a risk of collisions.
3. Group Generation (A–H)
The private key is generated in the specified numeric ranges, dividing the key space into 8 groups.
Pros: Limiting the range simplifies testing and increases the chance of finding vulnerable keys.
Cons: Keys are less diverse, which reduces their security.
4. Mnemonic Phrases with Weak RNG
Generates mnemonic phrases (BIP-39) using a weak random number generator or from a dictionary, then converts them to keys (BIP-32).
Pros: Convenient for testing mnemonics. High chance of finding vulnerable phrases.
Disadvantages: Keys are highly insecure due to predictability.
5. Vulnerable Combined Keys
Generates keys with predictable patterns (repeated bytes, null bytes, sequences).
Advantages: Fast generation for vulnerability testing.
Disadvantages: Insecure, not suitable for real transactions.
6. Time-Based Keys
Uses timestamps as the basis for generating keys.
Advantages: Easy to implement, suitable for testing.
Disadvantages: Highly predictable, keys are vulnerable.
7. Mersenne Twister Keys
Uses the Mersenne Twister pseudo-random generator to generate keys.
Advantages: Fast generation for testing.
Disadvantages: Low entropy, keys are insecure.
8. Concatenation of Weak Sources
Combines weak sources (timestamps, PIDs, constants) to generate keys.
Pros: Suitable for searching vulnerable wallets.
Cons: Keys are predictable and insecure.
9. Keys from passwords
Hashes passwords (SHA-256) to create private keys.
Pros: Convenient for testing passwords from a dictionary.
Cons: Depends on the quality of the passwords, the keys are vulnerable.
10. Keys via obsolete hash functions (MD5)
Uses MD5 to generate keys.
Pros: Fast creation for vulnerability testing.
Cons: MD5 is obsolete, keys are predictable.
11. Pseudorandom sequences (Xorshift)
Uses the Xorshift algorithm to generate keys.
Pros: Fast generation, suitable for testing.
Cons: Low entropy, keys are insecure.
12. Truncated Large Numbers
Generates keys that truncate large random numbers.
Pros: Simple, suitable for testing.
Cons: Truncating reduces entropy, keys are vulnerable.

Running and usage:
1. Run the code in Python with ```"requirements.txt"``` install all the necessary libraries from ```"pip install -r requirements.txt"```.
2. Select one of the methods you need and call the corresponding function.
3. Uses two APIs for transaction verification: Infura and Etherscan, with automatic switching when the request limit is exceeded.
4. The results are written to the files: ```successful_wallets.txt``` (addresses with transactions), ```bad_wallets.txt``` (addresses without transactions), and ```successful_wallets_balance.txt``` (addresses with balance).

The script uses the API.ini configuration file, which must contain the following keys:
```
INFURA_URL: Infura API URL.
ETHERSCAN_API_KEY: Etherscan API key.
TELEGRAM_BOT_TOKEN =
TELEGRAM_CHAT_ID =
```
The API.ini file should be located alongside the script, and you need to add your API keys for each service.

    To support the author: TFbR9gXb5r6pcALasjX1FKBArbKc4xBjY8

