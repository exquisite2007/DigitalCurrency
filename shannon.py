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
ch = TimedRotatingFileHandler('shannon.log', when='D', interval=1, backupCount=3)
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


	global BUY_RATE_THRESHOLD
	global SELL_RATE_THRESHOLD
	if TRADE_LOCK:
		logger.debug('Ignore ticker')
		return
	TRADE_LOCK = True
	if DIGITAL_COIN_NUM is None or FIAT_COIN_NUM is None:
		await util.init_wallet()
		DIGITAL_COIN_NUM = util.WALLET[util.CURRENCY[0]]['free']
		FIAT_COIN_NUM = util.WALLET[util.CURRENCY[1]]['free']
		logger.info('re-fetch wallet info,DIGITAL_COIN_NUM :{},FIAT_COIN_NUM:{}'.format(DIGITAL_COIN_NUM,FIAT_COIN_NUM))
		
	total_value = DIGITAL_COIN_NUM * last + FIAT_COIN_NUM
	diff = FIAT_COIN_NUM -total_value/2
	diff_rate = 1-DIGITAL_COIN_NUM * last/(FIAT_COIN_NUM+0.000000000001) 
	state=None
	logger.info('CURRENCY diff: {},diff_rate:{},DIGITAL_COIN_NUM :{},FIAT_COIN_NUM:{}'.format(diff,diff_rate,DIGITAL_COIN_NUM,FIAT_COIN_NUM))
	if  diff_rate > BUY_RATE_THRESHOLD:#下段，法币远多于数字币，不平衡状态
		if ORDER_ID is None:#
			TRADE_LOCK=True
			amount=diff/ask1
			res =await util.buy(ask1,amount,is_market=True)
			logger.info('buy {} at marcket price to start,order_id is {}'.format(amount,res))
			DIGITAL_COIN_NUM = None
			FIAT_COIN_NUM = None
		else:#从中下段 进入下段
			ORDER_ID = None
			last_balance_price = FIAT_COIN_NUM/DIGITAL_COIN_NUM
			balance_diff = DIGITAL_COIN_NUM*last_balance_price*BUY_RATE_THRESHOLD/2
			predict_balance_diff = (FIAT_COIN_NUM - DIGITAL_COIN_NUM*last_balance_price*(1-BUY_RATE_THRESHOLD))/2
			FIAT_COIN_NUM-=predict_balance_diff
			DIGITAL_COIN_NUM+=predict_balance_diff/(last_balance_price*(1-BUY_RATE_THRESHOLD))
			state='dark_red'
			logger.info('trade buy {} at {}'.format(predict_balance_diff/(last_balance_price*(1-BUY_RATE_THRESHOLD)),last_balance_price*(1-BUY_RATE_THRESHOLD)))
			logger.info('state <dark red>:{},{},{}'.format(FIAT_COIN_NUM,DIGITAL_COIN_NUM,FIAT_COIN_NUM/DIGITAL_COIN_NUM))

	elif diff_rate > BUY_RATE_THRESHOLD /2 and diff_rate < BUY_RATE_THRESHOLD:#中下段，法币多，数字币少
		if ORDER_ID is None: 
			last_balance_price = FIAT_COIN_NUM/DIGITAL_COIN_NUM
			predict_balance_diff = (FIAT_COIN_NUM - DIGITAL_COIN_NUM*last_balance_price*(1-BUY_RATE_THRESHOLD))/2

			ORDER_ID = await  util.buy(last_balance_price*(1-BUY_RATE_THRESHOLD),predict_balance_diff/(last_balance_price*(1-BUY_RATE_THRESHOLD)))
			state='light_red'
			logger.info('state <light red>:{},{},{}'.format(FIAT_COIN_NUM,DIGITAL_COIN_NUM,FIAT_COIN_NUM/DIGITAL_COIN_NUM))
	elif (diff_rate>= 0 and diff_rate <= BUY_RATE_THRESHOLD /2) or(diff_rate<0 and -diff_rate <= SELL_RATE_THRESHOLD /2):
		if ORDER_ID is not None:
			await util.cancel_order(ORDER_ID)
			ORDER_ID=None
			state='white'
			logger.info('state <white>:{},{},{}'.format(FIAT_COIN_NUM,DIGITAL_COIN_NUM,FIAT_COIN_NUM/DIGITAL_COIN_NUM))
			#TODO:平衡	
	elif -diff_rate >  SELL_RATE_THRESHOLD/2 and - diff_rate <= SELL_RATE_THRESHOLD:#中上段，法币少，数字币多
		if ORDER_ID is None: 
			last_balance_price = FIAT_COIN_NUM/DIGITAL_COIN_NUM
			predict_balance_diff=(DIGITAL_COIN_NUM*last_balance_price*(1+SELL_RATE_THRESHOLD)-FIAT_COIN_NUM)/2
			ORDER_ID = await  util.sell(last_balance_price*(1+SELL_RATE_THRESHOLD),predict_balance_diff/(last_balance_price*(1+SELL_RATE_THRESHOLD)))
			state='light_green'
			logger.info('state <light green>:{},{},{}'.format(FIAT_COIN_NUM,DIGITAL_COIN_NUM,FIAT_COIN_NUM/DIGITAL_COIN_NUM))
	elif -diff_rate >SELL_RATE_THRESHOLD: #上段，数字币远多于法币
		if ORDER_ID is None:#
			amount=-diff/bid1
			res =await util.sell(bid1,amount,is_market=True)
			logger.info('sell {} at marcket price to start,order_id is {}'.format(amount,res))
			DIGITAL_COIN_NUM = None
			FIAT_COIN_NUM = None
		else:#从中上段 进入上段
			ORDER_ID = None
			last_balance_price = FIAT_COIN_NUM/DIGITAL_COIN_NUM
			predict_balance_diff=(DIGITAL_COIN_NUM*last_balance_price*(1+SELL_RATE_THRESHOLD)-FIAT_COIN_NUM)/2
			FIAT_COIN_NUM+=predict_balance_diff
			DIGITAL_COIN_NUM-=predict_balance_diff/(last_balance_price*(1+SELL_RATE_THRESHOLD))
			state='dark_green'
			logger.info('trade sell {} at {}'.format(predict_balance_diff/(last_balance_price*(1+SELL_RATE_THRESHOLD)),(last_balance_price*(1+SELL_RATE_THRESHOLD))))
			logger.info('state <dark green>:{},{},{}'.format(FIAT_COIN_NUM,DIGITAL_COIN_NUM,FIAT_COIN_NUM/DIGITAL_COIN_NUM))
	TRADE_LOCK = False
	return state
async def health_check():
	while True:
		await asyncio.sleep(30)
		await okexUtil.ping()
async def deal_handler():
	return await asyncio.wait([okexUtil.ticker(trade),health_check()])
loop=asyncio.get_event_loop()
# loop.run_until_complete(deal_handler())
async def test():
	init_value =16.0
	# count = 100
	# direction=-1
	# while count>0:
	# 	count-=1
	# 	okexUtil.ticker_value=(init_value,init_value,init_value)
	# 	state=await trade()
	# 	print(count)
	# 	if state=='dark_green' or state == 'dark_red':
	# 		direction*=-1
	# 	init_value+=direction*0.01

	while init_value < 20:
		init_value+=0.01
		okexUtil.ticker_value=(init_value,init_value,init_value)
		await trade()

	while init_value>13:
		init_value-=0.01
		okexUtil.ticker_value=(init_value,init_value,init_value)
		await trade()

loop.run_until_complete(test())

