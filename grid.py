#!/usr/bin/env python

import asyncio
import websockets
import json
import requests
from aiohttp import web
import hmac
import hashlib
import random
import logging
from  logging.handlers import TimedRotatingFileHandler
logger = logging.getLogger("deal")
logger.setLevel(logging.DEBUG)
ch = TimedRotatingFileHandler('grid.log', when='D', interval=1, backupCount=5)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
logger.addHandler(ch)
import sqlite3
import os
import sys
from exchange.fake import fakeUtil
from exchange.okex import okexUtil
import time

SUPPOR_PAIR='ETC_USDT'
okexUtil=okexUtil(SUPPOR_PAIR)
util=fakeUtil(SUPPOR_PAIR)

util.WALLET[util.CURRENCY[0]]={'free':0}
util.WALLET[util.CURRENCY[1]]={'free':1200}

CREATE_SYSTEM_SQL='CREATE TABLE IF NOT EXISTS `system` ( `id` INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT UNIQUE, `key` TEXT NOT NULL, `value` TEXT NOT NULL )'
SELECT_SYSTEM_SQL='SELECT * from system'
UPDATE_SYSTEM_SQL='update system set value=? where key=?'
INSERT_SYSTEM_SQL='insert into system (key,value) values(?,?)'
conn = sqlite3.connect('trade.db')
DIGITAL_COIN_NUM=None
FIAT_COIN_NUM=None
LAST_TRADE_PRICE=None
BASE_TRADE_AMOUNT=10
TRADE_LOCK=False


BUY_RATE_THRESHOLD=0.0196
SELL_RATE_THRESHOLD=0.02
# BUY_RATE_THRESHOLD=0.04761904762
# SELL_RATE_THRESHOLD=0.05
# BUY_RATE_THRESHOLD=0.04761904762
# SELL_RATE_THRESHOLD=0.05
# BUY_RATE_THRESHOLD=0.0909
# SELL_RATE_THRESHOLD=0.1
# BUY_RATE_THRESHOLD=0.16668
# SELL_RATE_THRESHOLD=0.2
ORDER_ID=None #为空表示没有挂单，非空表示有挂单
IS_INTITIAL_FINISH=False


async def trade():
	(ask1,bid1,last) = okexUtil.ticker_value
	logger.info('{},{},{}'.format(ask1,bid1,last))
	global TRADE_LOCK
	global ORDER_ID
	global DIGITAL_COIN_NUM
	global FIAT_COIN_NUM
	global LAST_TRADE_PRICE
	if LAST_TRADE_PRICE is None:
		LAST_TRADE_PRICE=last

	global BUY_RATE_THRESHOLD
	global SELL_RATE_THRESHOLD
	if TRADE_LOCK:
		logger.debug('Ignore ticker')
		return
	TRADE_LOCK = True
	diff_rate = (last -LAST_TRADE_PRICE)/LAST_TRADE_PRICE
	if diff_rate >SELL_RATE_THRESHOLD: #上段，数字币远多于法币
		if ORDER_ID is None:#
			pass#TODO:处理上涨太快
		else:#从中上段 进入上段
			ORDER_ID = None
			LAST_TRADE_PRICE=(1+SELL_RATE_THRESHOLD)*LAST_TRADE_PRICE
			FIAT_COIN_NUM+=BASE_TRADE_AMOUNT*LAST_TRADE_PRICE
			DIGITAL_COIN_NUM-=BASE_TRADE_AMOUNT
			state='dark_green'
			logger.info('state <dark green>:{},{},{}'.format(FIAT_COIN_NUM,DIGITAL_COIN_NUM,LAST_TRADE_PRICE))
	elif diff_rate >  SELL_RATE_THRESHOLD/2 and  diff_rate <= SELL_RATE_THRESHOLD:#中上段，法币少，数字币多
		if ORDER_ID is None: 
			ORDER_ID = await  util.sell(LAST_TRADE_PRICE*(1+SELL_RATE_THRESHOLD),BASE_TRADE_AMOUNT)
			state='light_green'
			logger.info('state <light green>:{},{},{}'.format(FIAT_COIN_NUM,DIGITAL_COIN_NUM,last))
	elif (diff_rate< 0 and -diff_rate <= BUY_RATE_THRESHOLD /2) or(diff_rate>=0 and diff_rate <= SELL_RATE_THRESHOLD /2):
		if ORDER_ID is not None:
			await util.cancel_order(ORDER_ID)
			ORDER_ID=None
			state='white'
			logger.info('state <white>:{},{},{}'.format(FIAT_COIN_NUM,DIGITAL_COIN_NUM,last))
			#TODO:平衡		
	elif -diff_rate > BUY_RATE_THRESHOLD /2 and -diff_rate < BUY_RATE_THRESHOLD:#中下段，法币多，数字币少
		if ORDER_ID is None: 
			ORDER_ID = await  util.buy(LAST_TRADE_PRICE*(1-BUY_RATE_THRESHOLD),BASE_TRADE_AMOUNT)
			state='light_red'
			logger.info('state <light red>:{},{},{}'.format(FIAT_COIN_NUM,DIGITAL_COIN_NUM,LAST_TRADE_PRICE))	
	elif  -diff_rate > BUY_RATE_THRESHOLD:#下段，法币远多于数字币，不平衡状态
		if ORDER_ID is None:#
			pass#TODO:处理下跌太快
		else:#从中下段 进入下段
			ORDER_ID = None
			LAST_TRADE_PRICE=(1-BUY_RATE_THRESHOLD)*LAST_TRADE_PRICE
			FIAT_COIN_NUM-=LAST_TRADE_PRICE*BASE_TRADE_AMOUNT
			DIGITAL_COIN_NUM+=BASE_TRADE_AMOUNT
			state='dark_red'
			logger.info('state <dark red>:{},{},{}'.format(FIAT_COIN_NUM,DIGITAL_COIN_NUM,LAST_TRADE_PRICE))

	
	
	
	TRADE_LOCK = False

async def deal_handler():
	return await asyncio.wait([okexUtil.ticker(trade),okexUtil.health_check()])
loop=asyncio.get_event_loop()
loop.run_until_complete(deal_handler())


