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
from exchange.poloniex import poloniexUtil
from exchange.okex import okexUtil
import time
CREATE_SYSTEM_SQL='CREATE TABLE IF NOT EXISTS `system` ( `id` INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT UNIQUE, `key` TEXT NOT NULL, `value` TEXT NOT NULL )'
SELECT_SYSTEM_SQL='SELECT * from system'
UPDATE_SYSTEM_SQL='update system set value=? where key=?'
INSERT_SYSTEM_SQL='insert into system (key,value) values(?,?)'
conn = sqlite3.connect('trade.db')
LAST_BALANCE_PRICE=None
DIGITAL_COIN_NUM=None
FIAT_COIN_NUM=None
TRADE_LOCK=False
CHANGE_RATE_THRESHOLD=0.02
ORDER_ID=None #为空表示没有挂单，非空表示有挂单
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

def trade(ask1,bid1,last):
	global TRADE_LOCK
	global ORDER_ID
	global DIGITAL_COIN_NUM
	global FIAT_COIN_NUM
	global LAST_BALANCE_PRICE

	if None in[DIGITAL_COIN_NUM,FIAT_COIN_NUM,LAST_BALANCE_PRICE]:
		logger.info('Not ready to trade')
	if not TRADE_LOCK:#交易没有被锁，空闲状态
		if abs(DIGITAL_COIN_NUM*last - FIAT_COIN_NUM)<1:
			logger.info('比较平衡，不做改变')
			return
		change_rate =( LAST_BALANCE_PRICE- last)/LAST_BALANCE_PRICE
		if abs(change_rate)<=CHANGE_RATE_THRESHOLD/2.0:#小于一倍区间
			if ORDER_ID is not None:
				TRADE_LOCK = True
				await util.cancel_order(ORDER_ID)
				#TODO:平衡
				
				TRADE_LOCK = True
				#取消所有定单,并且检查是否平衡
		else if change_rate > 0:
			PREDICT_BALANCE_PRICE=(1+CHANGE_RATE_THRESHOLD)*LAST_BALANCE_PRICE
			PREDICT_FIAT_NUM_CHANGE=( DIGITAL_COIN_NUM*PREDICT_BALANCE_PRICE - FIAT_COIN_NUM)/2
			if change_rate < CHANGE_RATE_THRESHOLD : #一倍到二倍区间
				if ORDER_ID is None:
					#下卖单
					TRADE_LOCK = True
					res=await util.sell(PREDICT_BALANCE_PRICE,PREDICT_FIAT_NUM_CHANGE/PREDICT_BALANCE_PRICE)
					logger.info('PREPARE HIGER')
					TRADE_LOCK=False
				else if change_rate>CHANGE_RATE_THRESHOLD:#向上大于二倍区间，平衡
					ORDER_ID = None
					LAST_BALANCE_PRICE=(1+CHANGE_RATE_THRESHOLD)*LAST_BALANCE_PRICE
					MODIFY_FIAT_NUM=(DIGITAL_COIN_NUM*LAST_BALANCE_PRICE-FIAT_COIN_NUM)/2
					FIAT_COIN_NUM+=MODIFY_FIAT_NUM
					DIGITAL_COIN_NUM-=MODIFY_FIAT_NUM/LAST_BALANCE_PRICE
					logger.info('UPPER BALANCE:{},{},{}'.format(FIAT_COIN_NUM,DIGITAL_COIN_NUM,LAST_BALANCE_PRICE))
		else if change_rate< 0:
			PREDICT_BALANCE_PRICE=(1-CHANGE_RATE_THRESHOLD)*LAST_BALANCE_PRICE
			PREDICT_FIAT_NUM_CHANGE=(FIAT_COIN_NUM -DIGITAL_COIN_NUM*PREDICT_BALANCE_PRICE)/2
			if -change_rate < CHANGE_RATE_THRESHOLD:#向下一倍到二倍区间
				if ORDER_ID is  None:
					#下买单
					TRADE_LOCK = True
					ORDER_ID = await  util.buy(PREDICT_BALANCE_PRICE,PREDICT_FIAT_NUM_CHANGE/PREDICT_BALANCE_PRICE)
					logger.info('PREPARE LOWER')
					TRADE_LOCK = False
			
				else if  -change_rate > CHANGE_RATE_THRESHOLD:#向下大于二倍区间
					ORDER_ID = None
					FIAT_COIN_NUM-=MODIFY_FIAT_NUM
					DIGITAL_COIN_NUM+=MODIFY_FIAT_NUM/PREDICT_BALANCE_PRICE
					LAST_BALANCE_PRICE = PREDICT_BALANCE_PRICE
					logger.info('LOWER BALANCE:{},{},{}'.format(FIAT_COIN_NUM,DIGITAL_COIN_NUM,LAST_BALANCE_PRICE))

		
	else:
		logger.info('in trade,ignore update')




