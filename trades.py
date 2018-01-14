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
from qiniu import Auth, put_file, etag
import logging
from  logging.handlers import TimedRotatingFileHandler
logger = logging.getLogger("apscheduler.scheduler")
logger.setLevel(logging.DEBUG)
ch = TimedRotatingFileHandler('data.log', when='D', interval=1, backupCount=5)
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
INSERT_SQL='insert into trades values(?,?,?,?,?,?,?)'
CREATE_SQL='CREATE TABLE IF NOT EXISTS trades (tid INTEGER,pair text, amount real,  price real,type text,timestamp INTEGER,exchange text)'
SELECT_SQL='select tid from trades where exchange=? and pair=? order by tid desc limit 1'

def OKEXTask(cursor):
	try:
		exchange = 'okex'
		coinMap={'BTC_ETH':'eth_btc','BTC_LTC':'ltc_btc','BTC_USDT':'btc_usdt','ETH_LTC':'ltc_eth'}
		lst =[]
		
		for pair in COIN_PAIR_LIST:
			cursor.execute(SELECT_SQL, (exchange,pair))
			last = cursor.fetchone()
			url='https://www.okex.com/api/v1/trades.do?symbol='+coinMap[pair]
			if last is not None:
				url+='&since='+str(last[0])
			res = requests.get(url).text
			if res is not None:
				for item in json.loads(res):			
					lst.append((int(item['tid']),pair,item['amount'],item['price'],item['type'],int(item['date_ms']),exchange))
					logger.debug(lst[-1])
		if len(lst)>0:
			cursor.executemany(INSERT_SQL,lst)
			cursor.connection.commit()
		logger.info( 'finish okex:'+str(len(lst)))
	except Exception as e:
		logger.error(e)

def bittrexTask(cursor):
	try:
		exchange='bittrex'
		coinMap={'BTC_ETH':'BTC-ETH','BTC_LTC':'BTC-LTC','BTC_USDT':'USDT-BTC','ETH_LTC':'ETH-LTC'}	

		lst=[]
		for pair in COIN_PAIR_LIST:
			cursor.execute(SELECT_SQL, (exchange,pair))
			last = cursor.fetchone()
			url='https://bittrex.com/api/v1.1/public/getmarkethistory?market='+coinMap[pair]
			res = requests.get(url).text
			epoch = datetime.fromtimestamp(0)
			if res is not None:
				for item in json.loads(res)['result']:
					if last is  None or int(item['Id']) > int(last[0]):
						ts=item['TimeStamp']
						if ts.find('.')<0:
							ts+='.00'
						timestamp=int(((datetime.strptime(ts, "%Y-%m-%dT%H:%M:%S.%f")-epoch).total_seconds()-3600*5)*1000)
						lst.append((int(item['Id']),pair,item['Quantity'],item['Price'],item['OrderType'].lower(),timestamp,exchange))
						logger.debug(lst[-1])
		if len(lst)>0:
			cursor.executemany(INSERT_SQL,lst)
			cursor.connection.commit()
		logger.info('finish bittrex:'+str(len(lst)))
	except Exception as e:
		logger.error(e)


def bitfinexTask(cursor):
	try:
		exchange = 'bitfinex'
		coinMap={'BTC_ETH':'ethbtc','BTC_LTC':'ltcbtc','BTC_USDT':'btcusd'}	

		lst=[]
		for pair in COIN_PAIR_LIST:
			if coinMap.has_key(pair):
				cursor.execute(SELECT_SQL, (exchange,pair))
				last = cursor.fetchone()
				url='https://api.bitfinex.com/v1/trades/'+coinMap[pair]+'?limit_trades=1000'
				res = json.loads(requests.get(url).text)
				if type(res)==type([]):
					for item in res:
						if last is  None or int(item['tid']) > int(last[0]):
							ts=item['timestamp']*1000
							lst.append((item['tid'],pair,float(item['amount']),float(item['price']),item['type'],ts,exchange))
							logger.debug(lst[-1])
		if len(lst)>0:
			cursor.executemany(INSERT_SQL,lst)
			cursor.connection.commit()
		logger.info('finish bitfinex:'+str(len(lst)))
	except Exception as e:
		logger.error(e)
	
def poloniex(cursor):
	try:
		exchange = 'poloniex'
		coinMap={'BTC_ETH':'BTC_ETH','BTC_LTC':'BTC_LTC','BTC_USDT':'USDT_BTC'}	

		lst=[]
		epoch = datetime.fromtimestamp(0)
		for pair in COIN_PAIR_LIST:
			if coinMap.has_key(pair):
				cursor.execute(SELECT_SQL, (exchange,pair))
				last = cursor.fetchone()
				now = int(time.time())
				fromP = str(now-100)
				toP = str(now)
				url='https://poloniex.com/public?command=returnTradeHistory&currencyPair='+coinMap[pair]+'&start='+fromP+'&end='+toP
				res = requests.get(url).text
				if res is not None:
					for item in json.loads(res):
						if last is  None or item['globalTradeID'] > int(last[0]):
							ts=int(((datetime.strptime(item['date'], "%Y-%m-%d %H:%M:%S")-epoch).total_seconds()-5*3600)*1000)
							lst.append((item['globalTradeID'],pair,float(item['amount']),float(item['rate']),item['type'],ts,exchange))
							logger.debug(lst[-1])
		if len(lst)>0:
			cursor.executemany(INSERT_SQL,lst)
			cursor.connection.commit()
		logger.info('finish poloniex:'+str(len(lst)))
	except Exception as e:
		logger.error(e)




def cronTask():
	logger.info('enter task') 
	dbFile = 'trades_'+datetime.now().strftime("%Y-%m-%d")+'.db'
	conn = sqlite3.connect(dbFile)
	cursor = conn.cursor()
	cursor.execute(CREATE_SQL)
	OKEXTask(cursor)
	bittrexTask(cursor)
	bitfinexTask(cursor)
	poloniex(cursor)
	conn.close()
	regex = re.compile('trades_.*.db')
	files = sorted(filter(regex.match,os.listdir('.')),reverse=True)

	if len(files) >1 and os.environ.has_key('access_key'):
		access_key = os.environ['access_key']
		secret_key = os.environ['secret_key']
		q = Auth(access_key, secret_key)
		bucket_name = 'stock'
		for item in files[1:]:
			token = q.upload_token(bucket_name, item, 60)
			ret, info =put_file(token, item, item)
			print info
			if ret['hash'] == etag(item):
				os.remove(item)
	logger.info('leave task')
cronTask()
if __name__ == '__main__':
	sched = Scheduler(standalone=True,misfire_grace_time=5)
	
	sched.add_interval_job(cronTask , seconds=5,coalesce=True)
	try:
		sched.start()
	except (KeyboardInterrupt, SystemExit):
		pass

