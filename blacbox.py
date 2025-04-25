#version 1.0.1

import requests
import datetime
import time
import os
from bs4 import BeautifulSoup
from prometheus_client import Gauge, start_http_server

# Налаштування метрик для Prometheus
psl_lang = Gauge('psl_lang', 'Текст вкладених div з class="stats_col_mid data_row"',
                 ['index', 'value2', 'change', 'timestamp'])

# Функція для завантаження HTML-контенту
def fetch_html(url):
    try:
        response = requests.get(url, timeout=10)  # Додаємо таймаут
        response.raise_for_status()
        return response.text
    except requests.exceptions.Timeout:
        print(f"Помилка: Час очікування відповіді від {url} вичерпано.")
    except requests.exceptions.RequestException as e:
        print(f"Помилка запиту до сайту: {e}")
    return None

# Функція для пошуку вкладених div відповідно до типу класу
def find_divs_by_class(html, target_id):
    try:
        soup = BeautifulSoup(html, 'html.parser')
        target_div = soup.find('div', id=target_id)
        if not target_div:
            raise ValueError(f"Не вдалося знайти div з id='{target_id}'")
        lang_divs = target_div.find_all('div', class_="stats_col_mid data_row")
        percentage_divs = target_div.find_all('div', class_="stats_col_right data_row")
        change_divs = target_div.find_all('div', class_="stats_col_right2 data_row")
        return lang_divs, percentage_divs, change_divs
    except Exception as e:
        print(f"Помилка обробки HTML: {e}")
        return [], [], []

# Функція для витягування значення change
def extract_change_info(change_div):
    try:
        if change_div:
            span = change_div.find('span')  # Знаходимо span у div
            if span and 'stat_increase' in span.get('class', []):
                return "increase"
            elif span and 'stat_decrease' in span.get('class', []):
                return "decrease"
        return "neutral"  # Якщо змін немає або клас не знайдено
    except Exception as e:
        print(f"Помилка при обробці change: {e}")
        return "error"

# Оновлення дати запуску
def update_last_run():
    try:
        with open("last_run.txt", "w") as file:
            file.write(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    except IOError as e:
        print(f"Помилка запису до файлу: {e}")

# Основна функція для виконання логіки
def execute_logic():
    url = "https://store.steampowered.com/hwsurvey/"
    target_id = "cat7_details"  # ID основного div
    html_content = fetch_html(url)
    if html_content:
        # Знаходимо всі div за типами класів
        lang_divs, percentage_divs, change_divs = find_divs_by_class(html_content, target_id)
        current_timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        print(f"LANG метрики (class='stats_col_mid data_row'):")
        for idx, lang_div in enumerate(lang_divs):
            try:
                lang_text = lang_div.text.strip()

                # Витягуємо відповідний процент із class="stats_col_right data_row"
                percentage_div = percentage_divs[idx] if idx < len(percentage_divs) else None
                percentage_text = percentage_div.text.strip() if percentage_div else "0"
                percentage_text = percentage_text.replace('%', '').strip()  # Видалення % та пробілів

                # Витягуємо значення change із span у class="stats_col_right2 data_row"
                change_div = change_divs[idx] if idx < len(change_divs) else None
                value2 = change_div.text.strip() if change_div else ""
                change = extract_change_info(change_div)  # Змінене значення (increase/decrease/neutral)

                # Виводимо інформацію в консоль
                print(f"Lang: {lang_text}, Value1: {percentage_text}, Value2: {value2}, Change: {change}, Timestamp: {current_timestamp}")

                # Передаємо дані в метрики Prometheus
                psl_lang.labels(index=lang_text, value2=value2, change=change, timestamp=current_timestamp).set(float(percentage_text))
            except ValueError as e:
                print(f"Помилка конвертації даних для метрики: {e}")
            except Exception as e:
                print(f"Неочікувана помилка: {e}")
    else:
        print("Не вдалося отримати HTML-контент.")

# Функція для перевірки, чи варто запускати логіку
def should_run():
    last_run_file = "last_run.txt"
    try:
        # Запуск 3 числа місяця
        current_date = datetime.datetime.now()
        if current_date.day == 3:
            return True

        # Перевірка останнього запуску
        if not os.path.exists(last_run_file):
            return True  # Якщо файл не існує, запускаємо

        with open(last_run_file, "r") as file:
            last_run_date = datetime.datetime.strptime(file.read().strip(), "%Y-%m-%d %H:%M:%S")

        # Перевірка на 15 днів з останнього виконання
        return (datetime.datetime.now() - last_run_date).days >= 15
    except Exception as e:
        print(f"Помилка перевірки дати запуску: {e}")
        return True

# Циклічна робота програми
def main():
    try:
        # Старт сервера Prometheus на порту 8111
        start_http_server(8111)

        # Логіка виконується при кожному запуску програми
        execute_logic()
        update_last_run()

        # Циклічна перевірка для запуску раз на 15 днів або 3 числа місяця
        while True:
            if should_run():
                execute_logic()
                update_last_run()
            else:
                print("Пропускаємо виконання. Ще не настав час.")
            time.sleep(86400)  # Чекаємо 1 день перед наступною перевіркою
    except KeyboardInterrupt:
        print("\nПрограма зупинена користувачем.")
    except Exception as e:
        print(f"Критична помилка: {e}")

if __name__ == "__main__":
    main()