import json
import sys
from datetime import datetime
from time import sleep

import telebot
import undetected_chromedriver.v2 as uc
from binance import Client
from bs4 import BeautifulSoup
from ccxt.base.decimal_to_precision import DECIMAL_PLACES  # noqa F401
from ccxt.base.decimal_to_precision import NO_PADDING  # noqa F401
from ccxt.base.decimal_to_precision import PAD_WITH_ZERO  # noqa F401
from ccxt.base.decimal_to_precision import ROUND  # noqa F401
from ccxt.base.decimal_to_precision import SIGNIFICANT_DIGITS  # noqa F401
from ccxt.base.decimal_to_precision import TICK_SIZE  # noqa F401
from ccxt.base.decimal_to_precision import TRUNCATE  # noqa F401
from ccxt.base.decimal_to_precision import decimal_to_precision  # noqa F401
from dateutil import parser
from django.core.management.base import BaseCommand
from html2text import html2text
from selenium import webdriver
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

from Bot.models import Signal, Traders, Admin

admin = Admin.objects.get(admin=True)

token = admin.bot_token  # dev bot token
my_id = admin.user_id

api_key = admin.api_key
api_secret = admin.api_secret

client = Client(api_key, api_secret)

bots = telebot.TeleBot(token)


def get_count(number):
    s = str(number)
    if '.' in s:
        return abs(s.find('.') - len(s)) - 1
    else:
        return 0


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


class Command(BaseCommand):
    help = 'бот'

    def handle(self, *args, **options):
        while True:
            sleep(20)
            try:
                traders = Traders.objects.all()

                options = uc.ChromeOptions()
                options.add_experimental_option("excludeSwitches", ["enable-logging"])

                options.add_argument("window-size=1920x1480")
                options.add_argument("disable-dev-shm-usage")
                options.add_argument('--headless')

                try:
                    driver = webdriver.Chrome(
                        chrome_options=options, executable_path=ChromeDriverManager(
                            version='104.0.5112.79'
                        ).install()
                    )
                except:
                    driver = webdriver.Chrome(
                        chrome_options=options, executable_path=ChromeDriverManager(
                            version='104.0.5112.79'
                        ).install()
                    )
                for trade in traders:

                    link = trade.link
                    name = trade.name

                    driver.get(link)
                    driver.implicitly_wait(7)
                    try:
                        driver.find_element(By.ID, 'onetrust-accept-btn-handler').click()
                    except:
                        sleep(4)

                    main_page = driver.page_source

                    soup = BeautifulSoup(main_page, 'html.parser')
                    text = soup.find_all('tbody', {'class': 'bn-table-tbody'})
                    try:
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
                    except Exception as e:
                        print('Traders dont have position')
                        print(e)
                # получаем активные ордера
                sig_ord = Signal.objects.filter(is_active=True)
                # сравниваем истекли срок годности ордера
                for order_s in sig_ord:
                    date_end = order_s.upd

                    now = datetime.now()

                    a = now - parser.parse(date_end)
                    delta = a.seconds / 60
                    # если срок годности ордера больше 15 минут, то получаем информацию об открытой позиции
                    # и закрываем её
                    pnl = str(order_s.pnl).split(' ')
                    if delta >= 4:
                        qty = float(client.futures_get_all_orders(symbol=order_s.symbol)[-1]['origQty'])
                        if order_s.side == 'BUY':
                            client.futures_create_order(
                                symbol=order_s.symbol,
                                side='SELL',
                                type='MARKET',
                                quantity=qty,
                                reduceOnly=True

                            )
                            order_s.delete()
                            msg = f'🚨 *{order_s.name}* CLOSED position\n' \
                                  f'🪙 Coin : {order_s.symbol}\n' \
                                  f'🚀 Trade : Buy (LONG)🟢\n\n' \
                                  f'💰 ROE :  {pnl[1]}%\n' \
                                  f'💰 PNL :  {pnl[0]}$\n\n' \
                                  f'✅ Entry : {order_s.entry_price} $\n' \
                                  f'✅ Exit :  {order_s.mark_price}$\n' \
                                  f'📅 Time : {order_s.date}'
                            bots.send_message(my_id, msg)
                        else:
                            client.futures_create_order(
                                symbol=order_s.symbol,
                                side='BUY',
                                type='MARKET',
                                quantity=qty,
                                reduceOnly=True
                            )
                            order_s.delete()
                            msg = f'🚨 *{order_s.name}* CLOSED position\n' \
                                  f'🪙 Coin : {order_s.symbol}\n' \
                                  f'🚀 Trade : SELL (SHORT) 🔻\n\n' \
                                  f'💰 ROE :  {pnl[1]}%\n' \
                                  f'💰 PNL :  {pnl[0]}$\n\n' \
                                  f'✅ Entry : {order_s.entry_price} $\n' \
                                  f'✅ Exit :  {order_s.mark_price}$\n' \
                                  f'📅 Time : {order_s.date}'
                            bots.send_message(my_id, msg)

                Signal.objects.filter(is_active=False).delete()

            except Exception as e:
                exc_type, exc_obj, exc_tb = sys.exc_info()
                bots.send_message(798093480, str(e))
                print(f'{e} line = {str(exc_tb.tb_lineno)}')
                sleep(15)
            sleep(5)
