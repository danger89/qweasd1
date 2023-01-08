import json
from datetime import datetime
from time import sleep
from binance import Client

import telebot
from bs4 import BeautifulSoup
from ccxt.base.decimal_to_precision import DECIMAL_PLACES  # noqa F401
from ccxt.base.decimal_to_precision import NO_PADDING  # noqa F401
from ccxt.base.decimal_to_precision import PAD_WITH_ZERO  # noqa F401
from ccxt.base.decimal_to_precision import ROUND  # noqa F401
from ccxt.base.decimal_to_precision import SIGNIFICANT_DIGITS  # noqa F401
from ccxt.base.decimal_to_precision import TICK_SIZE  # noqa F401
from ccxt.base.decimal_to_precision import TRUNCATE  # noqa F401
from ccxt.base.decimal_to_precision import decimal_to_precision  # noqa F401
from html2text import html2text
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

from Bot.management.commands.bot import get_count
from Bot.models import Signal


def get_orders(name_trader, symbol, date):
    """Делает запрос в базу и проверяет есть ли пользователь в базе"""
    try:
        Signal.objects.get(
            symbol=symbol,
        )
        Signal.objects.filter(symbol=symbol).update(upd=datetime.now())
        return True
    except:
        return False


def get_trader(trade, admin):
    link = trade.link
    name = trade.name
    options = Options()
    options.add_experimental_option("excludeSwitches", ["enable-logging"])
    options.add_argument("window-size=1920x1480")
    options.add_argument('--disable-dev-shm-usage')
    options.add_experimental_option('useAutomationExtension', False)
    options.add_argument('--no-sandbox')
    options.add_argument('--headless')
    options.add_experimental_option('extensionLoadTimeout', 600000)
    options.add_argument('--disable-extensions')
    options.add_argument('--single-process')
    options.add_argument('--disable-gpu')
    options.add_argument('--ignore-certificate-errors')
    options.add_argument('--remote-debugging-port=9222')
    options.page_load_strategy = 'eager'
    driver = webdriver.Chrome(
        options=options, service=Service(ChromeDriverManager().install()),
    )
    driver.get(link)

    driver.set_page_load_timeout(6000)
    driver.set_script_timeout(30)
    driver.implicitly_wait(5)
    try:
        driver.find_element(By.ID, 'onetrust-accept-btn-handler').click()
    except:
        sleep(1)

    main_page = driver.page_source
    soup = BeautifulSoup(main_page, 'html.parser')
    text = soup.find_all('tbody', {'class': 'bn-table-tbody'})
    driver.implicitly_wait(5)

    token = admin.bot_token  # dev bot token
    my_id = admin.user_id
    bots = telebot.TeleBot(token)
    api_key = admin.api_key
    api_secret = admin.api_secret

    client = Client(api_key, api_secret)
    # driver.close()
    for tex in text[0].find_all_next('tr'):
        data = html2text(str(tex)).replace('\n', '').split('|')
        if data[0].find('USDT') >= 0 or data[0].find('BUSD') >= 0:
            symbol = data[0].split(' ')[0]
            size = data[1]
            entry_price = data[2].replace(',', '')
            mark_price = data[3]
            pnl = data[4].split(' ')
            date = data[5]
            # число на сколько нужно округлить объем для ордера
            round_size = 0
            # шаг цены в торговой паре
            step_size = 1
            with open('data_file.json') as f:
                templates = json.load(f)

            for temp in templates:
                if temp['symbol'] == symbol:
                    step_size = float(temp['stepSize'])
                    break

            if step_size >= 1:
                step_size = round(step_size)
            round_size = get_count(step_size) - 1
            if round_size <= 0:
                round_size = 0

            curent_price = float(entry_price)
            # округляем и передаем в переменную
            wa = (float(admin.balance) * float(admin.admin_leverage))
            print('wa ' + str(wa))
            # минимальный объем для ордера
            while True:
                min_amount_m = float(wa) / float(curent_price) // float(
                    step_size) * float(step_size)
                if min_amount_m <= 0:
                    wa += 1
                else:
                    break

            if min_amount_m >= 10:
                quantity = float(decimal_to_precision(min_amount_m,
                                                      ROUND,
                                                      0,
                                                      DECIMAL_PLACES))
            else:
                quantity = float(decimal_to_precision(min_amount_m,
                                                      ROUND,
                                                      round_size,
                                                      DECIMAL_PLACES))
            print(quantity)

            if not get_orders(name, symbol, date):
                if str(data[0]).find('Short') >= 0:
                    # инициализируем дату и добавляем в базу
                    signal = Signal(
                        name_trader=name,
                        symbol=symbol,
                        side='SELL',
                        size=size,
                        entry_price=entry_price,
                        mark_price=mark_price,
                        pnl=pnl,
                        date=date,
                        upd=datetime.now()
                    )
                    signal.save()
                    client.futures_change_leverage(symbol=symbol, leverage=admin.admin_leverage)
                    # создаем рыночный ордер по сигналу
                    client.futures_create_order(
                        symbol=symbol,
                        side='SELL',
                        type='MARKET',
                        quantity=quantity
                    )

                    msg = f'🚨 *{name}* OPEN position\n' \
                          f'🪙 Coin : {symbol}\n' \
                          f'🚀 Trade : SELL (SHORT) 🔻\n\n' \
                          f'💰 ROE :  {pnl[1]}%\n' \
                          f'💰 PNL :  {pnl[0]}$\n\n' \
                          f'✅ Entry : {entry_price} $\n' \
                          f'✅ Exit :  $\n' \
                          f'📅 Time : {date}'
                    print(msg)
                    bots.send_message(my_id, msg)

                else:
                    signal = Signal(
                        name_trader=name,
                        symbol=symbol,
                        side='BUY',
                        size=size,
                        entry_price=entry_price,
                        mark_price=mark_price,
                        pnl=pnl,
                        date=date,
                        upd=datetime.now()
                    )
                    signal.save()
                    client.futures_change_leverage(symbol=symbol, leverage=admin.admin_leverage)
                    # создаем рыночный ордер по сигналу
                    client.futures_create_order(
                        symbol=symbol,
                        side='BUY',
                        type='MARKET',
                        quantity=quantity
                    )

                    msg = f'🚨 *{name}* OPEN position\n' \
                          f'🪙 Coin : {symbol}\n' \
                          f'🚀 Trade : Buy (LONG)🟢\n\n' \
                          f'💰 ROE :  {pnl[1]}%\n' \
                          f'💰 PNL :  {pnl[0]}$\n\n' \
                          f'✅ Entry : {entry_price} $\n' \
                          f'✅ Exit :  $\n' \
                          f'📅 Time : {date}'
                    print(msg)
                    bots.send_message(my_id, msg)
