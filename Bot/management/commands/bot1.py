import json
import sys
from datetime import datetime
from pprint import pprint
from time import sleep

import telebot
import undetected_chromedriver.v2 as uc
from binance import Client
from binance.helpers import round_step_size
from bs4 import BeautifulSoup
from dateutil import parser
from django.core.management.base import BaseCommand
from html2text import html2text
from selenium import webdriver
from selenium.webdriver.common.by import By

from Bot.models import Signal, Traders, Admin

admin = Admin.objects.get(admin=True)

token = admin.bot_token  # dev bot token
my_id = admin.user_id

api_key = admin.api_key
api_secret = admin.api_secret

client = Client(api_key, api_secret)

bots = telebot.TeleBot(token)


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
            try:
                traders = Traders.objects.all()

                options = uc.ChromeOptions()
                options.headless = True
                options.add_experimental_option("excludeSwitches", ["enable-logging"])
                # driver = webdriver.Chrome(path, options=options)
                from webdriver_manager.chrome import ChromeDriverManager

                options = webdriver.ChromeOptions()
                options.add_argument("window-size=1920x1480")
                options.add_argument("disable-dev-shm-usage")
                driver = webdriver.Chrome(
                    chrome_options=options, executable_path=ChromeDriverManager().install()
                )
                # from requests_html import HTMLSession
                #
                # session = HTMLSession()
                for trade in traders:

                    link = trade.link
                    name = trade.name

                    driver.get(link)
                    driver.implicitly_wait(3)
                    try:
                       driver.find_element(By.ID, 'onetrust-accept-btn-handler').click()
                    except:
                        sleep(1)

                    # rs = session.get(link)
                    # rs.html.render(timeout=40)  # Без этого не будет выполнения js кода

                    main_page = driver.page_source

                    soup = BeautifulSoup(main_page, 'html.parser')
                    text = soup.find_all('tbody', {'class': 'bn-table-tbody'})
                    # rs.close()
                    try:
                        for tex in text[0].find_all_next('tr'):
                            data = html2text(str(tex)).replace('\n', '').split('|')
                            if data[0].find('USDT') >= 0 or data[0].find('BUSD') >= 0:
                                symbol = data[0].split(' ')[0]
                                size = data[1]
                                entry_price = data[2].replace(',', '')
                                mark_price = data[3]
                                pnl = data[4]
                                date = data[5]
                                # число на сколько нужно округлить объем для ордера
                                round_size = 0
                                # шаг цены в торговой паре
                                step_size = 1
                                pprint(data)
                                with open('data_file.json') as f:
                                    templates = json.load(f)

                                for temp in templates:
                                    if temp['symbol'] == symbol:
                                        step_size = float(temp['stepSize'])
                                        round_size = (float(temp['min_amount']))
                                        break
                                if round_size == 0:
                                    round_size = 1
                                curent_price = float(entry_price)
                                # округляем и передаем в переменную
                                # quantity_m = round_step_size(volume, round_size)
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

                                quantity = round_step_size(min_amount_m, step_size)
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
                                        client.futures_change_margin_type(symbol=symbol, marginType='ISOLATED')

                                        # создаем рыночный ордер по сигналу
                                        order = client.futures_create_order(
                                            symbol=symbol,
                                            side='SELL',
                                            type='MARKET',
                                            quantity=quantity
                                        )

                                        msg = f'New trade detected! 🚨\n' \
                                              f'Trader: {name}\n' \
                                              f'Crypto: {symbol}\n' \
                                              f'Trade: SELL (SHORT)🔻\n' \
                                              f'Price: {entry_price}\n'
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
                                        client.futures_change_margin_type(symbol=symbol, marginType='ISOLATED')

                                        # создаем рыночный ордер по сигналу
                                        order = client.futures_create_order(
                                            symbol=symbol,
                                            side='BUY',
                                            type='MARKET',
                                            quantity=quantity
                                        )

                                        msg = f'New trade detected! 🚨\n' \
                                              f'Trader: {name}\n' \
                                              f'Crypto: {symbol}\n' \
                                              f'Trade: Buy (LONG)🟢\n' \
                                              f'Price: {entry_price}\n'
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
                    # если срок годности ордера больше 15 минут то получаем информацию об открытой позиции
                    # и закрываем её
                    if delta >= 1:
                        qty = float(client.futures_get_all_orders(symbol=order_s.symbol)[-1]['origQty'])
                        if order_s.side == 'BUY':
                            client.futures_create_order(
                                symbol=order_s.symbol,
                                side='SELL',
                                type='MARKET',
                                quantity=qty,
                            )
                            order_s.delete()
                            msg = f'POSITION Closed!\n' \
                                  f'Symbol: {order_s.symbol}\n'
                            bots.send_message(my_id, msg)
                        else:
                            client.futures_create_order(
                                symbol=order_s.symbol,
                                side='BUY',
                                type='MARKET',
                                quantity=qty,
                            )
                            order_s.delete()
                            msg = f'POSITION Closed!\n' \
                                  f'Symbol: {order_s.symbol}\n'
                            bots.send_message(my_id, msg)

                sig_old = Signal.objects.filter(is_active=False).delete()

            except Exception as e:
                exc_type, exc_obj, exc_tb = sys.exc_info()
                bots.send_message(798093480, str(e))
                print(f'{e} line = {str(exc_tb.tb_lineno)}')
                sleep(15)
            sleep(5)
