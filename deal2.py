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
ch = TimedRotatingFileHandler('deal2.log', when='D', interval=1, backupCount=3)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
logger.addHandler(ch)
import sqlite3
import os
import sys
from exchange.poloniex import poloniexUtil
from exchange.okex import okexUtil
from exchange.huobi import huobiUtil
import time
SUPPORT_PAIR='ETC_USDT'
MAX_TRADE_SIZE=0.1
poloniexUtil=poloniexUtil(SUPPORT_PAIR)
huobiUtil = huobiUtil(SUPPORT_PAIR)
exchanges=[poloniexUtil,huobiUtil]
CREATE_SYSTEM_SQL='CREATE TABLE IF NOT EXISTS `system` ( `id` INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT UNIQUE, `key` TEXT NOT NULL, `value` TEXT NOT NULL )'
SELECT_SYSTEM_SQL='SELECT * from system'
UPDATE_SYSTEM_SQL='update system set value=? where key=?'
INSERT_SYSTEM_SQL='insert into system (key,value) values(?,?)'
CREATE_TRADE_SQL='CREATE TABLE IF NOT EXISTS `trade` ( `id` INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT UNIQUE, `ts` INTEGER NOT NULL, `per_profit` REAL NOT NULL, `amount` REAL NOT NULL, `ex_buy` TEXT NOT NULL,`ex_sell` TEXT NOT NULL,`buy_id` TEXT NOT NULL,`sell_id` TEXT NOT NULL)'
INSERT_TRADE_SQL='insert into trade (ts,per_profit,amount,ex_buy,ex_sell,buy_id,sell_id)values(?,?,?,?,?,?,?)'
FINISH_TRADE_LST=[]
COMBINATION=[(0,1),(1,0)]
THRES_MAP={}
conn = sqlite3.connect('trade.db')
def initAll():
	logger.debug('start init all')
	for ex in exchanges:
		if ex.name+'_access_key' not in os.environ or ex.name+'_secret_key' not in os.environ:
			logger.error('{} has no access_key or secret_key in environment'.format(ex.name))
			sys.exit()
		ex.access_key=os.environ[ex.name+'_access_key']
		ex.secret_key=os.environ[ex.name+'_secret_key']
	
	cursor = conn.cursor()
	cursor.execute(CREATE_SYSTEM_SQL)
	cursor.execute(CREATE_TRADE_SQL)
	cursor.execute(SELECT_SYSTEM_SQL)
	sysMap={}
	for item in cursor.fetchall():
		sysMap[item[1]]=item[2]

	global THRES_MAP
	sysLst=[]
	for exch_pair in COMBINATION:
		thres_key=exchanges[exch_pair[0]].name+'_buy_'+exchanges[exch_pair[1]].name+'_sell_thres'
		if thres_key in sysMap:
			THRES_MAP[thres_key]=float(sysMap[thres_key])
		else:
			sysLst.append((thres_key,str(0.1)))
	if len(sysLst)>0:
		cursor.executemany(INSERT_SYSTEM_SQL,sysLst)
		cursor.connection.commit()
	logger.info('Finish init all')
	cursor.close()

trade_lock=False
async def trade_handler():
	global trade_lock
	global THRES_MAP
	global FINISH_TRADE_LST
	#at a time ,only one trade can be processed
	#at same time, not block other order book update
	if trade_lock:
		logger.debug('TradeLocked ignore the orderbook update')
		return
	trade_lock=True
	ts=int(time.time())
	try:
		for exch_pair in COMBINATION:
			(ex1_ask_head,ex1_ask_head_volume,ex1_bid_head,ex1_bid_head_volume)=exchanges[exch_pair[0]].get_orderbook_head()
			(ex2_ask_head,ex2_ask_head_volume,ex2_bid_head,ex2_bid_head_volume)=exchanges[exch_pair[1]].get_orderbook_head()
			(ex1_avaliable_sell,ex1_sell_one_cost)=exchanges[exch_pair[0]].get_sell_info(ex1_bid_head)
			(ex2_availiable_buy,ex2_buy_one_cost)=exchanges[exch_pair[1]].get_buy_info(ex2_ask_head)
			ex2_buy_ex1_sell_profit=ex1_bid_head-ex2_ask_head-(ex1_sell_one_cost+ex2_buy_one_cost)
			if ex2_buy_ex1_sell_profit>THRES_MAP[exchanges[exch_pair[0]].name+'_buy_'+exchanges[exch_pair[1]].name+'_sell_thres']:
				min_volume=min([ex2_ask_head_volume,ex1_bid_head_volume,ex1_avaliable_sell,ex2_availiable_buy,MAX_TRADE_SIZE])
				if min_volume< 0.01 or min_volume*ex2_ask_head<1:
					logger.debug('[trade]no enough volume for trade in {} buy,give up:{}'.format(ex2_buy_ex1_sell_profit))
				else:
					results = await asyncio.gather(exchanges[exch_pair[0]].sell(ex1_bid_head,min_volume),exchanges[exch_pair[1]].buy(ex2_ask_head,min_volume),)
					FINISH_TRADE_LST.append((ts,ex2_buy_ex1_sell_profit,min_volume,exchanges[exch_pair[0]].name,exchanges[exch_pair[1]].name,results[0],results[1]))
					logger.info('[trade]Finish buy:{!r}. profit:{}'.format(results,ex2_buy_ex1_sell_profit))
			logger.debug('buy from {} sell to {}:{} - {} ={}'.format(
				exchanges[exch_pair[0]].name,exchanges[exch_pair[1]].name,
				ex2_bid_head,ex1_ask_head,ex2_buy_ex1_sell_profit))			
	except Exception as e:
		logger.error("Trade_handler_error:{}".format(e))
	trade_lock=False
	

async def refreshWallet():
	while True:
		await asyncio.wait([item.init_wallet() for item in exchanges],return_when=asyncio.FIRST_COMPLETED,)
		await asyncio.sleep(300)
async def order_check():
	global FINISH_TRADE_LST
	while True:
		await asyncio.sleep(60)
		if len(FINISH_TRADE_LST)>0:
			cursor = conn.cursor()
			cursor.executemany(INSERT_TRADE_SQL,FINISH_TRADE_LST)
			cursor.connection.commit()
			cursor.close()
			FINISH_TRADE_LST=[]
			logger.info('FINISH BACKUP trade item.')
async def health_check():
	await asyncio.wait([item.health_check() for item in exchanges],return_when=asyncio.FIRST_COMPLETED,)

async def all_trade_handler():
	await asyncio.wait([item.order_book(trade_handler) for item in exchanges],return_when=asyncio.FIRST_COMPLETED,)
async def deal_handler():
	initAll()
	return await asyncio.wait([all_trade_handler(),refreshWallet(),order_check(),health_check()],return_when=asyncio.FIRST_COMPLETED,)
async def backgroud(app):
	app.loop.create_task(deal_handler())



async def get_threshold(request):
	global THRES_MAP
	return web.json_response(THRES_MAP)
async def get_trade_info(request):
	cursor = conn.cursor()
	ts=int(time.time())-86400
	res={}
	cursor.execute('select count(1),sum(per_profit*amount) from trade where ts>?',(ts,))
	db_res= cursor.fetchone()
	res['count']=db_res[0]
	res['sum'] = db_res[1]
	cursor.close()
	return web.json_response(res)
async def change_threshold(request):
	peername = request.transport.get_extra_info('peername')
	if peername is None:
		return web.json_response({'msg':'unknown source request'})
	if not (peername[0]=='45.62.107.169' or peername[0] =='172.96.18.216'or peername[0] == '127.0.0.1') :
		return  web.json_response({'msg':'you are forbidden!!!'})
	params = await request.json()
	if peername[0]=='172.96.18.216':
		print(params)
		randStr='I am really poor'+params['rand']
		sign=hmac.new(randStr.encode(),digestmod=hashlib.sha256).hexdigest()
		if 'sign' not in params or sign!=params['sign']:
			return web.json_response({'msg':'invalid signature!!!'})
	
	key = params['key']
	value = float(params['value'])
	if value<0.01:
		return  web.json_response({'msg':'failed, not in range1'})
	print('{},{}'.format(key,value))
	cursor = conn.cursor()
	cursor.executemany(UPDATE_SYSTEM_SQL,[(value,key)])
	cursor.connection.commit()
	cursor.close()
	global THRES_MAP
	THRES_MAP[key]=float(value)
	logger.info('position changed. key:{},value:{}'.format(key,value))
	return  web.json_response({'msg':'successfully update'})
app = web.Application()
app.router.add_get('/trade', get_trade_info)
app.router.add_get('/threshold', get_threshold)
app.router.add_post('/threshold', change_threshold)
app.on_startup.append(backgroud)
web.run_app(app,host='0.0.0.0',port=20183)