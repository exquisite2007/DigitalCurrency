#!/usr/bin/python
# encoding: utf-8
from apscheduler.scheduler import Scheduler
import sqlite3
import time
from datetime import datetime
from os.path import isfile
import requests
import json
import re
import os
import logging
from  logging.handlers import TimedRotatingFileHandler
logger = logging.getLogger("apscheduler.scheduler")
logger.setLevel(logging.DEBUG)
ch = TimedRotatingFileHandler('orderbook.log', when='D', interval=1, backupCount=2)
ch.setLevel(logging.DEBUG)

# create formatter
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# add formatter to ch
ch.setFormatter(formatter)

# add ch to logger
logger.addHandler(ch)

#BTC_ETH
#BTC_LTC
#BTC_BCH
#BTC_USDT
#ETH_LTC
# COIN_PAIR_LIST=['BTC_ETH','BTC_LTC','BTC_USDT','ETH_LTC']
COIN_PAIR_LIST=['BTC_ETH','BTC_LTC','ETH_LTC','BTC_USDT']
INSERT_SQL='insert into  bookOrder (pair,ask1,bid1,timestamp,exchange) values(?,?,?,?,?)'
CREATE_SQL='CREATE TABLE IF NOT EXISTS bookOrder (id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT UNIQUE,pair text,ask1 real,bid1 real,timestamp INTEGER,exchange text)'

def OKEXTask(pair):
	try:
		exchange = 'okex'
		coinMap={'BTC_ETH':'eth_btc','BTC_LTC':'ltc_btc','BTC_USDT':'btc_usdt','ETH_LTC':'ltc_eth'}
		coinMap={'BTC_ETH':'eth_btc','BTC_LTC':'ltc_btc','BTC_USDT':'btc_usdt','ETH_LTC':'ltc_eth','ETC_USDT':'etc_usdt','ETC_USDT':'etc_usdt'}
		ok_url='https://www.okex.com/api/v1/depth.do?size=5&symbol='+coinMap[pair]
		ok_res = json.loads(requests.get(ok_url).text)
		return ok_res['asks'][0][0],ok_res['bids'][0][0]
	except Exception as e:
		logger.error(e)
		return None,None

def poloniex(pair):
	try:
		coinMap={'BTC_ETH':'BTC_ETH','BTC_LTC':'BTC_LTC','BTC_USDT':'USDT_BTC','ETC_USDT':'USDT_ETC'}	
		url='https://poloniex.com/public?command=returnOrderBook&depth=5&currencyPair='+coinMap[pair]
		res_text=requests.get(url).text
		poloniex_res=json.loads(res_text)

		return poloniex_res['asks'][0][0],poloniex_res['bids'][0][0]
	except Exception as e:
		logger.error(e)
		return None,None




def cronTask():
	logger.info('enter task') 
	dbFile = 'orderbook_'+datetime.now().strftime("%Y-%m-%d")+'.db'
	conn = sqlite3.connect(dbFile)
	cursor = conn.cursor()
	cursor.execute(CREATE_SQL)
	pair='ETC_USDT'
	askBook1,bidBook1=OKEXTask(pair)
	askBook2,bidBook2=poloniex(pair)
	lst=[]
	ts= int(time.time()*1000)
	lst.append((pair,askBook1,bidBook1,ts,'okex'))
	lst.append((pair,askBook2,bidBook2,ts,'poloniex'))
	cursor.executemany(INSERT_SQL,lst)
	cursor.connection.commit()
	conn.close()
	logger.info('end task')



if __name__ == '__main__':
	sched = Scheduler(standalone=True,misfire_grace_time=5)
	
	sched.add_interval_job(cronTask , seconds=5,coalesce=True)
	try:
		sched.start()
	except (KeyboardInterrupt, SystemExit):
		pass

