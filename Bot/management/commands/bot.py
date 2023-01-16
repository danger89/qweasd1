import os
import sys
from datetime import datetime
from time import sleep
import heroku3

import telebot
from binance import Client
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

from Bot.management.commands.fucn_trader import get_trader
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
            sleep(5)
            try:
                traders = Traders.objects.all()

                for trade in traders:
                    try:
                        get_trader(trade, admin)
                    except Exception as e:
                        # get_trader(trade, admins)
                        exc_type, exc_obj, exc_tb = sys.exc_info()
                        print(str(e) + 'line = ' + str(exc_tb.tb_lineno))

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
                    if delta >= 3:
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

            except IndexError as e:

                # Your Heroku API key

                api_key_heroku = os.environ.get("api_key_heroku")

                # The name of your app and dyno

                app_name = os.environ.get("app_name")

                heroku_conn = heroku3.from_key(api_key_heroku)

                app = heroku_conn.app(app_name)

                app.restart()

                exc_type, exc_obj, exc_tb = sys.exc_info()

                print(f'{e} line = {str(exc_tb.tb_lineno)}')

            except Exception as e:

                # Your Heroku API key

                api_key_heroku = os.environ.get("api_key_heroku")

                # The name of your app and dyno

                app_name = os.environ.get("app_name")

                heroku_conn = heroku3.from_key(api_key_heroku)

                app = heroku_conn.app(app_name)

                app.restart()

                exc_type, exc_obj, exc_tb = sys.exc_info()

                print(f'{e} line = {str(exc_tb.tb_lineno)}')

                sleep(15)
            sleep(5)
