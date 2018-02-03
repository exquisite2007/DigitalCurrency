#!/usr/bin/env python

import asyncio
import websockets
import json
import requests
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

wallet={}
BOOK_LIMIT=5
poloniex_book={}
okex_book={}
okexUtil=okexUtil()
poloniexUtil=poloniexUtil()
async def okex():
	global okex_book
	while True:
		try:
			async with websockets.connect('wss://real.okex.com:10441/websocket') as websocket:
				param={'event':'addChannel','channel':'ok_sub_spot_etc_usdt_depth_5'}
				await websocket.send(json.dumps(param))
				while True:
					message = await websocket.recv()
					res=json.loads(message)
					if type(res) is list and res[0]['channel'].startswith('ok'):
						ask_map={}
						for item in res[0]['data']['asks']:
							ask_map[item[0]]=item[1]
						okex_book['ask']=ask_map
						bid_map={}
						for item in res[0]['data']['bids']:
							bid_map[item[0]]=item[1]
						okex_book['bid']=bid_map
					makeDecision()
		except  Exception as e:
			okex_book={}
			logger.error(e)

async def poloniex():
	async with websockets.connect('wss://api2.poloniex.com/') as websocket:
		param={'command':'subscribe','channel':173}

		await websocket.send(json.dumps(param))

		while True:
			message = await websocket.recv()
			res=json.loads(message)
			if len(res)<2:
				continue
			for item in res[2]:
				if item[0] == 'i':
					book_size=0
					ask_map={}
					for key in sorted(item[1]['orderBook'][0],key=lambda subItem:float(subItem))[:BOOK_LIMIT]:
						ask_map[key]=item[1]['orderBook'][0][key]
					poloniex_book['ask']=ask_map
					bid_map={}
					for key  in sorted(item[1]['orderBook'][1],key=lambda subItem:float(subItem),reverse=True)[:BOOK_LIMIT]:
						bid_map[key]=item[1]['orderBook'][1][key]
					poloniex_book['bid']=bid_map
				elif item[0] == 'o':
					# ['o', 1, '26.54474428', '0.00000000']
					if item[1] == 0:#ask
						if float(item[3])==0 and item[2] in  poloniex_book['ask']:
							del poloniex_book['ask'][item[2]]
						elif float(item[3])>0:
							poloniex_book['ask'][item[2]]=item[3]
					elif item[1] == 1:#bid
						if float(item[3])==0 and item[2] in  poloniex_book['bid']:
							del poloniex_book['bid'][item[2]]
						elif float(item[3])>0:
							poloniex_book['bid'][item[2]]=item[3]
			makeDecision()
async def handler():
	return await asyncio.wait([okex(),poloniex()],return_when=asyncio.FIRST_COMPLETED,)
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
def initWallet():
	wallet['okex']=okexUtil.getWallet()
	wallet['poloniex']=poloniexUtil.getWallet()
	logger.info('Finish load wallet:{}'.format(str(wallet)))
def makeDecision():
	print(str(poloniex_book))
	if len(okex_book)>0 and len(poloniex_book)>0:
		ok_ask_head=min(okex_book['ask'],key=lambda subItem:float(subItem))
		ok_bid_head=max(okex_book['bid'],key=lambda subItem:float(subItem))
		logger.debug("okex < ask {}:{} ,bid {}:{}".format(ok_ask_head,okex_book['ask'][ok_ask_head],ok_bid_head,okex_book['bid'][ok_bid_head]))
		poloniex_ask_head=min(poloniex_book['ask'],key=lambda subItem:float(subItem))
		poloniex_bid_head=max(poloniex_book['bid'],key=lambda subItem:float(subItem))
		logger.debug("poloniex< ask {}:{} ,bid {}:{}".format(poloniex_ask_head,poloniex_book['ask'][poloniex_ask_head],poloniex_bid_head,poloniex_book['bid'][poloniex_bid_head]))
	else:
		logger.error('some error happen in orderbook monitor')



initAll()
initWallet()
loop=asyncio.get_event_loop()
loop.run_until_complete(handler())
