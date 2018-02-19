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
ch = TimedRotatingFileHandler('calculate.log', when='D', interval=1, backupCount=5)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
logger.addHandler(ch)
import os
import sys
from exchange.poloniex import poloniexUtil
from exchange.okex import okexUtil
SUPPOR_PAIR='ETC_USDT'
okexUtil=okexUtil(SUPPOR_PAIR)
poloniexUtil=poloniexUtil(SUPPOR_PAIR)



async def trade_handler():

	#at a time ,only one trade can be processed
	#at same time, not block other order book update
	if trade_lock:
		logger.debug('TradeLocked ignore the orderbook update')
		return
	try:
		(ok_ask_head,ok_ask_head_volume,ok_bid_head,ok_bid_head_volume)=okexUtil.get_orderbook_head()
		(poloniex_ask_head,poloniex_ask_head_volume,poloniex_bid_head,poloniex_bid_head_volume)=poloniexUtil.get_orderbook_head()
		
		
	except Exception as e:
		logger.error("Trade_handler_error:{}".format(e))
async def deal_handler():
	return await asyncio.wait([poloniexUtil.order_book(trade_handler),okexUtil.order_book(trade_handler)],return_when=asyncio.FIRST_COMPLETED,)	
loop=asyncio.get_event_loop()
loop.run_until_complete(deal_handler())
