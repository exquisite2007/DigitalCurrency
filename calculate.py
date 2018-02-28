#!/usr/bin/env python

import asyncio
import websockets
import json
import requests
from aiohttp import web
import logging
from  logging.handlers import TimedRotatingFileHandler
import time
import numpy as np
logger = logging.getLogger("deal")
logger.setLevel(logging.DEBUG)
ch = TimedRotatingFileHandler('calculate.log', when='D', interval=1, backupCount=3)
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
MINIST_VALUE=-999999
exch1_exch2_max=MINIST_VALUE
exch2_exch1_max=MINIST_VALUE
exch1_exch2_lst=[]
exch2_exch1_lst=[]
SAMPLE_INTERVAL=1
PERIORD=3600*4
REPORT_INTERVAL=1800


async def trade_handler():
	try:
		global exch1_exch2_max
		global exch2_exch1_max
		(ok_ask_head,ok_ask_head_volume,ok_bid_head,ok_bid_head_volume)=okexUtil.get_orderbook_head()
		(poloniex_ask_head,poloniex_ask_head_volume,poloniex_bid_head,poloniex_bid_head_volume)=poloniexUtil.get_orderbook_head()
		

		ok_buy_profit=poloniex_bid_head-ok_ask_head -(poloniex_bid_head*0.0025+ok_ask_head*0.002)
		poloniex_buy_profit=ok_bid_head-poloniex_ask_head-(ok_bid_head*0.002+poloniex_ask_head*0.0025)
		exch1_exch2_max=max(ok_buy_profit,exch1_exch2_max)
		exch2_exch1_max=max(poloniex_buy_profit,exch2_exch1_max)		
	except Exception as e:
		logger.error("Trade_handler_error:{}".format(e))
async def sampler():
	global exch1_exch2_max
	global exch2_exch1_max
	global MINIST_VALUE
	while True:

		await asyncio.sleep(SAMPLE_INTERVAL)
		exch1_exch2_lst.append(exch1_exch2_max)
		exch2_exch1_lst.append(exch2_exch1_max)
		exch1_exch2_max=MINIST_VALUE
		exch2_exch1_max=MINIST_VALUE

async def percentile():
	while True:
		global exch1_exch2_lst
		global exch2_exch1_lst
		await asyncio.sleep(REPORT_INTERVAL)
		if len(exch1_exch2_lst)> PERIORD:
			exch1_exch2_lst=exch1_exch2_lst[-PERIORD:]
		if len(exch2_exch1_lst) > PERIORD:
			exch2_exch1_lst=exch2_exch1_lst[-PERIORD:]
		exch1_exch2_threshold= np.percentile(exch1_exch2_lst,80)
		exch2_exch1_threshold= np.percentile(exch2_exch1_lst,80)
		logger.info('REPORT RES exch1_buy:{}, exch2_buy:{}'.format(exch1_exch2_threshold,exch2_exch1_threshold))
async def deal_handler():
	return await asyncio.wait([poloniexUtil.order_book(trade_handler),okexUtil.order_book(trade_handler),sampler(),percentile()],return_when=asyncio.FIRST_COMPLETED,)

loop=asyncio.get_event_loop()
loop.run_until_complete(deal_handler())
