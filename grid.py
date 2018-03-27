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
from exchange.okex import okexUtil
import time

SUPPOR_PAIR='ETC_USDT'
util=okexUtil(SUPPOR_PAIR)


CREATE_SYSTEM_SQL='CREATE TABLE IF NOT EXISTS `system` ( `id` INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT UNIQUE, `key` TEXT NOT NULL, `value` TEXT NOT NULL )'
SELECT_SYSTEM_SQL='SELECT * from system'
UPDATE_SYSTEM_SQL='update system set value=? where key=?'
INSERT_SYSTEM_SQL='insert into system (key,value) values(?,?)'
conn = sqlite3.connect('trade.db')
LAST_TRADE_PRICE_KEY='GRID_LAST_TRADE_PRICE'
LAST_TRADE_PRICE=None
BASE_TRADE_AMOUNT=1
TRADE_LOCK=False


BUY_RATE_THRESHOLD=0.0099
SELL_RATE_THRESHOLD=0.01
# BUY_RATE_THRESHOLD=0.0196
# SELL_RATE_THRESHOLD=0.02
# BUY_RATE_THRESHOLD=0.04761904762
# SELL_RATE_THRESHOLD=0.05
# BUY_RATE_THRESHOLD=0.04761904762
# SELL_RATE_THRESHOLD=0.05
# BUY_RATE_THRESHOLD=0.0909
# SELL_RATE_THRESHOLD=0.1
# BUY_RATE_THRESHOLD=0.16668
# SELL_RATE_THRESHOLD=0.2
ORDER_ID=None #为空表示没有挂单，非空表示有挂单

def initAll():
	logger.debug('start init all')
	if 'okex_access_key' in os.environ:
		util.access_key=os.environ['okex_access_key']
		util.secret_key=os.environ['okex_secret_key']
	else:
		logger.error('please check you exchange access key exist in your environment')
		sys.exit()
	cursor = conn.cursor()
	cursor.execute(CREATE_SYSTEM_SQL)
	cursor.execute(SELECT_SYSTEM_SQL)
	sysMap={}
	for item in cursor.fetchall():
		sysMap[item[1]]=item[2]
	global LAST_TRADE_PRICE
	global LAST_TRADE_PRICE_KEY
	if LAST_TRADE_PRICE_KEY in sysMap:
		LAST_TRADE_PRICE = float(sysMap[LAST_TRADE_PRICE_KEY])

async def trade():
	(ask1,bid1,last) = util.ticker_value
	logger.info('{},{},{}'.format(ask1,bid1,last))
	global TRADE_LOCK
	global ORDER_ID
	global LAST_TRADE_PRICE
	if LAST_TRADE_PRICE is None:
		LAST_TRADE_PRICE=last

	global BUY_RATE_THRESHOLD
	global SELL_RATE_THRESHOLD
	if TRADE_LOCK:
		logger.debug('Ignore ticker')
		return
	TRADE_LOCK = True
	try:
		diff_rate = (last -LAST_TRADE_PRICE)/LAST_TRADE_PRICE
		if diff_rate >SELL_RATE_THRESHOLD: #上段，数字币远多于法币
			if ORDER_ID is None:#
				pass#TODO:处理上涨太快
			else:#从中上段 进入上段
				order_res = await util.order_info(ORDER_ID)
				if len(order_res)>0 and order_res[0]['status']==2:
					LAST_TRADE_PRICE=(1+SELL_RATE_THRESHOLD)*LAST_TRADE_PRICE
					ORDER_ID = None
					logger.info('state <dark green>:{},{}'.format(util.WALLET,LAST_TRADE_PRICE))
				else:
					logger.error('error for confirm ordier:{}'.format(ORDER_ID))
		elif diff_rate >  SELL_RATE_THRESHOLD/2 and  diff_rate <= SELL_RATE_THRESHOLD:#中上段，法币少，数字币多
			if ORDER_ID is None: 
				(ok_avaliable_sell,ok_sell_one_cost)=util.get_sell_info(LAST_TRADE_PRICE*(1+SELL_RATE_THRESHOLD))
				if ok_avaliable_sell> BASE_TRADE_AMOUNT:
					ORDER_ID = await  util.sell(LAST_TRADE_PRICE*(1+SELL_RATE_THRESHOLD),BASE_TRADE_AMOUNT)
					logger.info('state <light green>:{},{}'.format(diff_rate,last))
				else:
					logger.info('no enough to sell')
		elif (diff_rate< 0 and -diff_rate <= BUY_RATE_THRESHOLD /2) or(diff_rate>=0 and diff_rate <= SELL_RATE_THRESHOLD /2):
			if ORDER_ID is not None:
				await util.cancel_order(ORDER_ID)
				ORDER_ID=None
				logger.info('state <white>:{},{}'.format(diff_rate,last))
		elif -diff_rate > BUY_RATE_THRESHOLD /2 and -diff_rate < BUY_RATE_THRESHOLD:#中下段，法币多，数字币少
			if ORDER_ID is None: 
				(ok_avaliable_buy,ok_buy_one_cost)=util.get_buy_info(LAST_TRADE_PRICE*(1-BUY_RATE_THRESHOLD))
				if ok_avaliable_buy >BASE_TRADE_AMOUNT:
					ORDER_ID = await  util.buy(LAST_TRADE_PRICE*(1-BUY_RATE_THRESHOLD),BASE_TRADE_AMOUNT)
					logger.info('state <light red>:{},{}'.format(diff_rate,last))
				else:
					logger.info('no enough to buy')
		elif  -diff_rate > BUY_RATE_THRESHOLD:#下段，法币远多于数字币，不平衡状态
			if ORDER_ID is None:#
				pass#TODO:处理下跌太快
			else:#从中下段 进入下段
				order_res = await util.order_info(ORDER_ID)
				if len(order_res)>0 and order_res[0]['status']==2:
					LAST_TRADE_PRICE=(1-BUY_RATE_THRESHOLD)*LAST_TRADE_PRICE
					ORDER_ID = None
					logger.info('state <dark green>:{},{}'.format(util.WALLET,LAST_TRADE_PRICE))
				else:
					logger.error('error for confirm ordier:{}'.format(ORDER_ID))
	except Exception as e:
		logger.error("Trade_handler_error:{}".format(e))
	TRADE_LOCK = False

async def params_check():
	while True:
		await asyncio.sleep(60)
		global LAST_TRADE_PRICE
		global LAST_TRADE_PRICE_KEY
		cursor = conn.cursor()
		cursor.executemany(UPDATE_SYSTEM_SQL,[(LAST_TRADE_PRICE,LAST_TRADE_PRICE_KEY)])
		cursor.connection.commit()
		cursor.close()
		logger.info('Finish params check')

async def deal_handler():
	initAll()
	return await asyncio.wait([util.ticker(trade),util.health_check(),util.refresh_wallet()])


async def backgroud(app):
	app.loop.create_task(deal_handler())
async def get_sysconfig(request):
	res={}
	global LAST_TRADE_PRICE
	global LAST_TRADE_PRICE_KEY
	res[LAST_TRADE_PRICE_KEY]=LAST_TRADE_PRICE
	return web.json_response(res)
async def change_sysconfig(request):
	peername = request.transport.get_extra_info('peername')
	if peername is None:
		return web.json_response({'msg':'unknown source request'})
	if not (peername[0]=='45.62.107.169' or peername[0] =='172.96.18.216'or peername[0] == '127.0.0.1') :
		return  web.json_response({'msg':'you are forbidden!!!'})
	params = await request.json()
	global LAST_TRADE_PRICE
	global LAST_TRADE_PRICE_KEY
	cursor = conn.cursor()
	cursor.executemany(UPDATE_SYSTEM_SQL,[(params[LAST_TRADE_PRICE_KEY],LAST_TRADE_PRICE_KEY)])
	cursor.connection.commit()
	cursor.close()

	LAST_TRADE_PRICE=float(params[LAST_TRADE_PRICE_KEY])
	logger.info('position changed. key:{},value:{}'.format(LAST_TRADE_PRICE_KEY,LAST_TRADE_PRICE))
app = web.Application()
app.router.add_get('/sys_config', get_sysconfig)
app.router.add_post('/sys_config', get_sysconfig)
app.on_startup.append(backgroud)
web.run_app(app,host='0.0.0.0',port=20184)
