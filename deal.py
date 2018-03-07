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
ch = TimedRotatingFileHandler('deal.log', when='D', interval=1, backupCount=3)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
logger.addHandler(ch)
import sqlite3
import os
import sys
from exchange.poloniex import poloniexUtil
from exchange.okex import okexUtil
import time
SUPPOR_PAIR='ETC_USDT'
MAX_TRADE_SIZE=3
okexUtil=okexUtil(SUPPOR_PAIR)
poloniexUtil=poloniexUtil(SUPPOR_PAIR)
OK_BUY_THRES=0.1
POLO_BUY_THRES=0.1
CREATE_SYSTEM_SQL='CREATE TABLE IF NOT EXISTS `system` ( `id` INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT UNIQUE, `key` TEXT NOT NULL, `value` TEXT NOT NULL )'
SELECT_SYSTEM_SQL='SELECT * from system'
UPDATE_SYSTEM_SQL='update system set value=? where key=?'
INSERT_SYSTEM_SQL='insert into system (key,value) values(?,?)'
CREATE_TRADE_SQL='CREATE TABLE IF NOT EXISTS `trade` ( `id` INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT UNIQUE, `ts` INTEGER NOT NULL, `per_profit` REAL NOT NULL, `amount` REAL NOT NULL, `type` INTEGER NOT NULL )'
INSERT_TRADE_SQL='insert into trade (ts,per_profit,amount,type)values(?,?,?,?)'
HEALTH_CHECK_INTERVAL=60*4
FINISH_TRADE_LST=[]
conn = sqlite3.connect('trade.db')
def initAll():
	logger.debug('start init all')
	if 'ok_access_key' in os.environ and 'poloniex_access_key' in os.environ:
		okexUtil.access_key=os.environ['ok_access_key']
		okexUtil.secret_key=os.environ['ok_secret_key']
		poloniexUtil.access_key=os.environ['poloniex_access_key'].encode()
		poloniexUtil.secret_key=os.environ['poloniex_secret_key'].encode()
	else:
		logger.error('please check you exchange access key exist in your environment')
		sys.exit()
	cursor = conn.cursor()
	cursor.execute(CREATE_SYSTEM_SQL)
	cursor.execute(CREATE_TRADE_SQL)
	cursor.execute(SELECT_SYSTEM_SQL)
	sysMap={}
	for item in cursor.fetchall():
		sysMap[item[1]]=item[2]
	global OK_BUY_THRES
	sysLst=[]
	if 'OK_BUY_THRES' in sysMap:
		OK_BUY_THRES=float(sysMap['OK_BUY_THRES'])
	else:
		sysLst.append(('OK_BUY_THRES',str(OK_BUY_THRES)))
	global POLO_BUY_THRES
	if 'POLO_BUY_THRES' in sysMap:
		POLO_BUY_THRES=float(sysMap['POLO_BUY_THRES'])
	else:
		sysLst.append(('POLO_BUY_THRES',str(POLO_BUY_THRES)))
	if len(sysLst)>0:
		cursor.executemany(INSERT_SYSTEM_SQL,sysLst)
		cursor.connection.commit()

	logger.info('Finish init all')
	cursor.close()

trade_lock=False
async def trade_handler():
	global trade_lock
	global OK_BUY_THRES
	global POLO_BUY_THRES
	global FINISH_TRADE_LST
	#at a time ,only one trade can be processed
	#at same time, not block other order book update
	if trade_lock:
		logger.debug('TradeLocked ignore the orderbook update')
		return
	try:
		(ok_ask_head,ok_ask_head_volume,ok_bid_head,ok_bid_head_volume)=okexUtil.get_orderbook_head()
		(poloniex_ask_head,poloniex_ask_head_volume,poloniex_bid_head,poloniex_bid_head_volume)=poloniexUtil.get_orderbook_head()
		
		(ok_avaliable_buy,ok_buy_one_cost)=okexUtil.get_buy_info(ok_ask_head)
		(ok_avaliable_sell,ok_sell_one_cost)=okexUtil.get_sell_info(ok_bid_head)
		(poloniex_availiable_buy,poloniex_buy_one_cost)=poloniexUtil.get_buy_info(poloniex_ask_head)
		(poloniex_availiable_sell,poloniex_sell_one_cost)=poloniexUtil.get_sell_info(poloniex_bid_head)

		ok_buy_profit=poloniex_bid_head-ok_ask_head -(poloniex_sell_one_cost+ok_buy_one_cost)
		ts=int(time.time())
		if ok_buy_profit>OK_BUY_THRES:
			min_volume=min([poloniex_bid_head_volume,ok_ask_head_volume,ok_avaliable_buy,poloniex_availiable_sell,MAX_TRADE_SIZE])
			if min_volume< 0.01 or min_volume*poloniex_bid_head<1:
				logger.debug('[trade]no enough volume for trade in ok buy,give up:{}'.format(ok_buy_profit))
			else:
				trade_lock=True
				results = await asyncio.gather(okexUtil.buy(ok_ask_head,min_volume),poloniexUtil.sell(poloniex_bid_head,min_volume),)
				logger.info('[trade]Finish okex buy:{!r}. profit:{}'.format(results,ok_buy_profit))
				FINISH_TRADE_LST.append((ts,ok_buy_profit,min_volume,0))
				trade_lock=False
		poloniex_buy_profit=ok_bid_head-poloniex_ask_head-(ok_sell_one_cost+poloniex_buy_one_cost)
		if poloniex_buy_profit>POLO_BUY_THRES:
			min_volume=min([poloniex_ask_head_volume,ok_bid_head_volume,ok_avaliable_sell,poloniex_availiable_buy,MAX_TRADE_SIZE])
			if min_volume< 0.01 or min_volume*poloniex_ask_head<1:
				logger.debug('[trade]no enough volume for trade in poloniex buy,give up:{}'.format(poloniex_buy_profit))
			else:
				trade_lock=True
				results = await asyncio.gather(okexUtil.sell(ok_bid_head,min_volume),poloniexUtil.buy(poloniex_ask_head,min_volume),)
				FINISH_TRADE_LST.append((ts,poloniex_buy_profit,min_volume,1))
				trade_lock=False
				logger.info('[trade]Finish poloniex buy:{!r}. profit:{}'.format(results,poloniex_buy_profit))
		logger.debug('buy_profit:{}:{}|{}:{}|{}|{}:{}|{}:{}|{}'.format(
			poloniex_bid_head,poloniex_bid_head_volume,
			ok_ask_head,ok_ask_head_volume,
			ok_buy_profit,
			ok_bid_head,ok_bid_head_volume,
			poloniex_ask_head,poloniex_ask_head_volume,
			poloniex_buy_profit))
	except Exception as e:
		logger.error("Trade_handler_error:{}".format(e))
		trade_lock=False
	

async def refreshWallet():
	while True:
		await asyncio.wait([poloniexUtil.init_wallet(),okexUtil.init_wallet()],return_when=asyncio.FIRST_COMPLETED,)
		await asyncio.sleep(300)
async def order_check():
	global FINISH_TRADE_LST
	while True:
		await asyncio.sleep(60)
		await asyncio.wait([poloniexUtil.unfinish_order_handler(),okexUtil.unfinish_order_handler()],return_when=asyncio.FIRST_COMPLETED,)
		if len(FINISH_TRADE_LST)>0:
			cursor = conn.cursor()
			cursor.executemany(INSERT_TRADE_SQL,FINISH_TRADE_LST)
			cursor.connection.commit()
			cursor.close()
			FINISH_TRADE_LST=[]
			logger.info('FINISH BACKUP trade item.')
async def health_check():
	global HEALTH_CHECK_INTERVAL
	poloniex_ask_head_all='begin'
	poloniex_bid_head_all='begin'
	while True:
		await asyncio.sleep(HEALTH_CHECK_INTERVAL)
		if poloniex_bid_head_all == poloniexUtil.bid_head_all or poloniex_ask_head_all== poloniexUtil.ask_head_all:
			logger.error("poloniex order head update die !!!")
			sys.exit(-1)
		else:
			poloniex_bid_head_all = poloniexUtil.bid_head_all
			poloniex_ask_head_all = poloniexUtil.ask_head_all

async def deal_handler():
	initAll()
	return await asyncio.wait([poloniexUtil.order_book(trade_handler),okexUtil.order_book(trade_handler),refreshWallet(),order_check(),health_check()],return_when=asyncio.FIRST_COMPLETED,)
async def backgroud(app):
	app.loop.create_task(deal_handler())


async def get_wallet(request):
	res={}
	res['ok']=okexUtil.WALLET
	res['poloniex']=poloniexUtil.WALLET
	return  web.json_response(res)
async def get_threshold(request):
	res={}
	res['OK_BUY_THRES'] = OK_BUY_THRES
	res['POLO_BUY_THRES'] = POLO_BUY_THRES
	return web.json_response(res)
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
	if peername[0]=='172.96.18.216' or peername[0]=='127.0.0.1':
		print(params)
		randStr='I am really poor'+params['rand']
		sign=hmac.new(randStr.encode(),digestmod=hashlib.sha256).hexdigest()
		if 'sign' not in params or sign!=params['sign']:
			return web.json_response({'msg':'invalid signature!!!'})
	
	ok_buy_thres = params['ok_buy_thres']
	poloniex_buy_thres = params['poloniex_buy_thres']
	if ok_buy_thres+poloniex_buy_thres <0.04:
		return  web.json_response({'msg':'failed, not in range'})
	if ok_buy_thres<-0.01 or poloniex_buy_thres<-0.01:
		return  web.json_response({'msg':'failed, not in range2'})
	if abs(ok_buy_thres)>0.5 or abs(poloniex_buy_thres)>0.5:
		return  web.json_response({'msg':'failed, not in range1'})
	global OK_BUY_THRES
	global POLO_BUY_THRES
	OK_BUY_THRES=ok_buy_thres
	POLO_BUY_THRES=poloniex_buy_thres
	cursor = conn.cursor()
	cursor.executemany(UPDATE_SYSTEM_SQL,[(ok_buy_thres,'OK_BUY_THRES'),(poloniex_buy_thres,'POLO_BUY_THRES')])
	cursor.connection.commit()
	cursor.close()
	logger.info('position changed. okex:{},poloniex:{}'.format(OK_BUY_THRES,POLO_BUY_THRES))
	return  web.json_response({'msg':'successfully update'})
app = web.Application()
app.router.add_get('/wallet', get_wallet)
app.router.add_get('/trade', get_trade_info)
app.router.add_get('/threshold', get_threshold)
app.router.add_post('/threshold', change_threshold)
app.on_startup.append(backgroud)
web.run_app(app,host='0.0.0.0',port=20183)