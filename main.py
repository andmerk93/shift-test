'''
Структура сервиса

Есть файлы users.csv и tokens.csv (имитация 2-х таблиц БД).
В users есть поля login, password, salary, salary_date,
в tokens - login, token, token_date.
Файл users должен быть заранее заполнен какими-то данными.
Users.csv считывается функцией csv_reader
и пишется в переменную users. В переменной лежат словари вида

{
  "john": {
    "login": "john",
    "password": "pass",
    "salary": "100",
    "salary_date": "2023-06-04",
    "token": "passjohn111",
    "token_date": "2023-06-05 02:05:33.218894"
  },
}

Затем создаётся экземпляр FastAPI, который слушает эндпоинты.

На эндпоинте '/' стоит заглушка, можно отправить GET-запрос,
но ничего не придёт в ответ.

На эндпоинте '/login' сервис ожидает POST-запрос JSON'a с параметрами вида
{
  "login": "",
  "password": ""
}
Функция проверяет правильность логина и пароля, обновляет
список токенов в паямти (считывает из словаря), проверяет
актуальность токена, при необходимости - обновляет,
записывает обновленные токены в базу (в csv-файл).
Актуальный токен появляется в памяти сервиса и в базе.
Токен актуален в течение суток.

На эндпоинт '/salary' нужно отправить
GET-запрос с query-параметрами 'login' и 'token'. 
Функция  обновляет список токенов в паямти (считывает из словаря),
проверяет правильность логина и токена, в случае ошибки - возвращает None.
При выполнение всех условий возвращает JSON с искомыми значениями:
{
  "login": "john",
  "salary": "100",
  "salary_date": "2023-06-04"
}

Описание работы функций есть в docstring самих функций.

Описание полей объекта user, с которыми работает программа:
    login: str = ''
    password: str = ''
    salary: float = 0.0
    salary_date: str = ''
    token: str = ''
    token_date: str = ''

Изначально палнировалось сделать pydantic-модель,
но не понадобилось, внутренние функции работают
с обычным списком словарей,
модель одного пользователя - словарь.
ТЗ и реализация простые, pydantic здесь избыточен.

Для запуска потребуются FastAPI и uvicorn.
'''

import csv
from datetime import datetime

from fastapi import FastAPI
import uvicorn

from pydantic import BaseModel

USERS = 'users.csv'
TOKENS = 'tokens.csv'


class LoginModel(BaseModel):
    login: str = ''
    password: str = ''


def csv_reader(file, users):
    '''
    Функция получения/обновления данных пользователей из CSV.
    По идее, список пользователей обычно получают из БД,
    но в данном случае, по ТЗ этого не требовалось,
    сделал максимально просто.
    Выбирал между JSON и CSV, взял CSV, потому что
    его удобнее отлаживать и тестировать.
    '''
    with open(file, 'r') as file:
        reader = csv.DictReader(file)
        for row in reader:
            if row['login'] in users:
                users[row['login']].update(row)
            else:
                users[row['login']] = row


def csv_writer(file, users):
    '''
    Простая функция записи в CSV.
    Переделано строго для сохранения токенов в отдельную таблицу.
    Если потребуется сохранять все данные, нужно раскомментировать
    первую и вторую строки и закомментировать третью.
    '''
    with open(file, 'w', newline='') as file:
#        anykey = [*users.keys()][0]
#        headers = users[anykey].keys()
        headers = ['login', 'token', 'token_date']
        writer = csv.DictWriter(file, headers,
                                restval='Unknown',
                                extrasaction='ignore')
        writer.writeheader()
        for user in users.values():
            writer.writerow(user)


def make_token(user):
    '''
    Механизм создания токена
    Сейчас он максимально простой,
    но технически здесь может быть
    любая сложная логика,
    либо сторонний модуль, заработает.

    '''
    password = user['password']
    login = user['login']
    secret_text = password + login + '111'
    return secret_text


def update_token(user):
    '''Простая функция обновления токена в объекте пользователя'''
    user['token'] = make_token(user)
    user['token_date'] = str(datetime.now())


def token_is_actual(user):
    '''
    Функция проверки токена на актуальность:
    1. Проверяется, создавался ли токен вообще (проверка поля с датой)
    2. Проверяется, актуален ли токен (дата создания - не позже прошлых суток)
    3. Проверяется, совпадает ли механизм шифрования
    '''
    if not user['token_date']:
        return False
    got_date = datetime.strptime(user['token_date'], '%Y-%m-%d %H:%M:%S.%f')
    if (datetime.now() - got_date).days > 1:
        return False
    if user['token'] != make_token(user):
        return False
    return True


def check_or_update_token(user):
    '''Собрал три предыдущие функции в одну для удобства'''
    if not token_is_actual(user):
        update_token(user)


app = FastAPI()
# Правильно было бы задать параметры
# docs_url=None, redoc_url=None, openapi_url=None
# но я оставил их для более удобного теста запросов

users = dict()
csv_reader(USERS, users)  # на старте программы


@app.get('/')
def index():
    '''Главная страница ничего не возвращает'''
    return None


@app.post('/login')
def login(current_login: LoginModel):
    '''
    Функция получает логин и пароль POST-запросом в форме JSON,
    проверяет на актуальность, возвращает актуальный токен.
    '''
    if current_login.login not in users:
        return None
    if users[current_login.login]['password'] != current_login.password:
        return None
    csv_reader(TOKENS, users)
    check_or_update_token(users[current_login.login])
    csv_writer(TOKENS, users)
    return users[current_login.login]['token']


@app.get('/salary')
def salary(login: str, token: str):
    '''
    Функция сделана как GET + Query-параметры, для разнообразия.
    Проверяет на актуальность токен, возвращает искомые значения.
    '''
    csv_reader(TOKENS, users)
    if login not in users:
        return None
    if users[login]['token'] != token:
        return None
    return {
        'login': users[login]['login'],
        'salary': users[login]['salary'],
        'salary_date': users[login]['salary_date'],
    }


if __name__ == '__main__':
    uvicorn.run('main:app', reload=True)
