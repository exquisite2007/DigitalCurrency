#!/usr/bin/env python

import asyncio
import websockets
import json
import requests
from aiohttp import web
import logging
from  logging.handlers import TimedRotatingFileHandler
logger = logging.getLogger("deal")
logger.setLevel(logging.DEBUG)
ch = TimedRotatingFileHandler('deal.log', when='D', interval=1, backupCount=5)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
logger.addHandler(ch)
import os
import sys
from exchange.poloniex import poloniexUtil
from exchange.okex import okexUtil
SUPPOR_PAIR='ETC_USDT'
MAX_TRADE_SIZE=3
okexUtil=okexUtil(SUPPOR_PAIR)
poloniexUtil=poloniexUtil(SUPPOR_PAIR)
OK_BUY_THRES=0.01
POLO_BUY_THRES=0.1

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
trade_lock=False
async def trade_handler():
	global trade_lock
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
		if ok_buy_profit>OK_BUY_THRES:
			min_volume=min([poloniex_bid_head_volume,ok_ask_head_volume,ok_avaliable_buy,poloniex_availiable_sell,MAX_TRADE_SIZE])
			if min_volume< 0.01 or min_volume*poloniex_bid_head<1:
				logger.debug('[trade]no enough volume for trade in ok buy,give up:{}'.format(ok_buy_profit))
			else:
				trade_lock=True
				results = await asyncio.gather(okexUtil.buy(ok_ask_head,min_volume),poloniexUtil.sell(poloniex_bid_head,min_volume),)
				logger.info('[trade]Finish okex buy:{!r}. profit:{}'.format(results,ok_buy_profit))
				trade_lock=False
		poloniex_buy_profit=ok_bid_head-poloniex_ask_head-(ok_sell_one_cost+poloniex_buy_one_cost)
		if poloniex_buy_profit>POLO_BUY_THRES:
			min_volume=min([poloniex_ask_head_volume,ok_bid_head_volume,ok_avaliable_sell,poloniex_availiable_buy,MAX_TRADE_SIZE])
			if min_volume< 0.01 or min_volume*poloniex_ask_head<1:
				logger.debug('[trade]no enough volume for trade in poloniex buy,give up:{}'.format(poloniex_buy_profit))
			else:
				trade_lock=True
				results = await asyncio.gather(okexUtil.sell(ok_bid_head,min_volume),poloniexUtil.buy(poloniex_ask_head,min_volume),)
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
async def handle_unfinish_order():
	while True:
		await asyncio.sleep(60)
		await asyncio.wait([poloniexUtil.unfinish_order_handler(),okexUtil.unfinish_order_handler()],return_when=asyncio.FIRST_COMPLETED,)
async def deal_handler():
	initAll()
	return await asyncio.wait([poloniexUtil.order_book(trade_handler),okexUtil.order_book(trade_handler),refreshWallet(),handle_unfinish_order()],return_when=asyncio.FIRST_COMPLETED,)
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
async def change_threshold(request):
	peername = request.transport.get_extra_info('peername')
	if peername is not None:
		host, port = peername
	params = await request.json()
	ok_buy_thres = params['ok_buy_thres']
	poloniex_buy_thres = params['poloniex_buy_thres']
	if ok_buy_thres+poloniex_buy_thres <0:
		return  web.json_response({'msg':'failed, not in range'})
	if abs(ok_buy_thres)>0.5 or abs(poloniex_buy_thres)>0.5:
		return  web.json_response({'msg':'failed, not in range1'})
	OK_BUY_THRES=ok_buy_thres
	POLO_BUY_THRES=poloniex_buy_thres
	logger.info('position changed. okex:{},poloniex:{}'.format(OK_BUY_THRES,POLO_BUY_THRES))
	return  web.json_response({'msg':'successfully update'})
app = web.Application()
app.router.add_get('/wallet', get_wallet)
app.router.add_get('/threshold', get_threshold)
app.router.add_post('/threshold', change_threshold)
app.on_startup.append(backgroud)
web.run_app(app,host='127.0.0.1')