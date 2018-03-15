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

util.WALLET[util.CURRENCY[0]]={'free':30}
util.WALLET[util.CURRENCY[1]]={'free':0}

CREATE_SYSTEM_SQL='CREATE TABLE IF NOT EXISTS `system` ( `id` INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT UNIQUE, `key` TEXT NOT NULL, `value` TEXT NOT NULL )'
SELECT_SYSTEM_SQL='SELECT * from system'
UPDATE_SYSTEM_SQL='update system set value=? where key=?'
INSERT_SYSTEM_SQL='insert into system (key,value) values(?,?)'
conn = sqlite3.connect('trade.db')
DIGITAL_COIN_NUM=None
FIAT_COIN_NUM=None

TRADE_LOCK=False
CHANGE_RATE_THRESHOLD=0.02
ORDER_ID=None #为空表示没有挂单，非空表示有挂单
IS_INTITIAL_FINISH=False
def init():
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

async def trade():
	(ask1,bid1,last) = okexUtil.ticker_value
	logger.info('{},{},{}'.format(ask1,bid1,last))
	global TRADE_LOCK
	global ORDER_ID
	global DIGITAL_COIN_NUM
	global FIAT_COIN_NUM


	global CHANGE_RATE_THRESHOLD
	if TRADE_LOCK:
		logger.debug('Ignore ticker')
		return
	if DIGITAL_COIN_NUM is None or FIAT_COIN_NUM is None:
		TRADE_LOCK = True
		await util.init_wallet()
		DIGITAL_COIN_NUM = util.WALLET[util.CURRENCY[0]]['free']
		FIAT_COIN_NUM = util.WALLET[util.CURRENCY[1]]['free']
		logger.info('re-fetch wallet info,DIGITAL_COIN_NUM :{},FIAT_COIN_NUM:{}'.format(DIGITAL_COIN_NUM,FIAT_COIN_NUM))
		TRADE_LOCK = False
	total_value = DIGITAL_COIN_NUM * last + FIAT_COIN_NUM
	diff = FIAT_COIN_NUM -total_value/2
	diff_rate = 1-DIGITAL_COIN_NUM * last/(FIAT_COIN_NUM+0.000000000001) 
	last_price= FIAT_COIN_NUM/(DIGITAL_COIN_NUM+0.00000000000001)
	logger.info('CURRENCY diff: {},diff_rate:{},DIGITAL_COIN_NUM :{},FIAT_COIN_NUM:{},last balance:{}'.format(diff,diff_rate,DIGITAL_COIN_NUM,FIAT_COIN_NUM,last_price))
	if  diff_rate > CHANGE_RATE_THRESHOLD:#下段，法币远多于数字币，不平衡状态
		if ORDER_ID is None:#
			TRADE_LOCK=True
			amount=diff/ask1
			res =await util.buy(ask1,amount,is_market=True)
			logger.info('buy {} at marcket price to start,order_id is {}'.format(amount,res))
			DIGITAL_COIN_NUM = None
			FIAT_COIN_NUM = None
			TRADE_LOCK=False
		else:#从中下段 进入下段
			ORDER_ID = None
			last_balance_price = FIAT_COIN_NUM/DIGITAL_COIN_NUM
			balance_diff = DIGITAL_COIN_NUM*last_balance_price*CHANGE_RATE_THRESHOLD/2
			FIAT_COIN_NUM-=balance_diff
			DIGITAL_COIN_NUM+=balance_diff/(last_balance_price*(1+CHANGE_RATE_THRESHOLD))
			logger.info('state <dark red>:{},{},{}'.format(FIAT_COIN_NUM,DIGITAL_COIN_NUM,last_balance_price))

	elif diff_rate > CHANGE_RATE_THRESHOLD /2 and diff_rate < CHANGE_RATE_THRESHOLD:#中下段，法币多，数字币少
		if ORDER_ID is None: 
			TRADE_LOCK = True
			last_balance_price = FIAT_COIN_NUM/DIGITAL_COIN_NUM
			ORDER_ID = await  util.buy(last_balance_price*(1-CHANGE_RATE_THRESHOLD),diff/(last_balance_price*(1+CHANGE_RATE_THRESHOLD)))
			logger.info('state <light red>')
			TRADE_LOCK = False
	elif  abs(diff_rate) <= CHANGE_RATE_THRESHOLD /2: #中段，进似平衡
		if ORDER_ID is not None:
			TRADE_LOCK = True
			await util.cancel_order(ORDER_ID)
			ORDER_ID=None
			logger.info('state <white>')
			#TODO:平衡		
			TRADE_LOCK = False
	elif -diff_rate >  CHANGE_RATE_THRESHOLD /2 and - diff_rate <= CHANGE_RATE_THRESHOLD:#中上段，法币少，数字币多
		if ORDER_ID is None: 
			TRADE_LOCK = True
			last_balance_price = FIAT_COIN_NUM/DIGITAL_COIN_NUM
			ORDER_ID = await  util.sell(last_balance_price*(1+CHANGE_RATE_THRESHOLD),diff/(last_balance_price*(1-CHANGE_RATE_THRESHOLD)))
			TRADE_LOCK = False
			logger.info('state <light green>')
	elif -diff_rate >CHANGE_RATE_THRESHOLD: #上段，数字币远多于法币
		if ORDER_ID is None:#
			TRADE_LOCK=True
			amount=-diff/bid1
			res =await util.sell(bid1,amount,is_market=True)
			logger.info('sell {} at marcket price to start,order_id is {}'.format(amount,res))
			DIGITAL_COIN_NUM = None
			FIAT_COIN_NUM = None
			TRADE_LOCK=False
		else:#从中上段 进入上段
			ORDER_ID = None
			last_balance_price = FIAT_COIN_NUM/DIGITAL_COIN_NUM
			balance_diff = DIGITAL_COIN_NUM*last_balance_price*CHANGE_RATE_THRESHOLD/2
			FIAT_COIN_NUM-=balance_diff
			DIGITAL_COIN_NUM+=balance_diff/(1-CHANGE_RATE_THRESHOLD)
			logger.info('state <dark green>:{},{},{}'.format(FIAT_COIN_NUM,DIGITAL_COIN_NUM,last_balance_price))


loop=asyncio.get_event_loop()
loop.run_until_complete(okexUtil.ticker(trade))


