from pprint import pprint
from time import sleep

import requests
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

from Bot.models import Signal, Traders, Admin, Orders


api_key = 'z8aUw8ydvRh6Q2jWFbEBbSd1YumD5qodJjeLltFmSEk8sYmWLPBEXR1yJHmINdgQ'
api_secret = 'wy0QhSkUkqiYPEjgwBRp9as7RFKXE2pxF34c5T0apTSfT7G3sNbMsQBnGdZDzfNo'

client = Client(api_key, api_secret)

qtr = float(client.futures_get_all_orders(symbol='BTCUSDT')[-1]['origQty'])

pprint(qtr)
