#!/usr/bin/python
# encoding: utf-8
from apscheduler.scheduler import Scheduler
import time
from datetime import datetime
import requests
import sqlite3
import json
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
# 返回买一价 ask，卖一价 bid
def getOKEXLatestPrice(pair):
	try:
		coinMap={'BTC_ETH':'eth_btc','BTC_LTC':'ltc_btc','BTC_USDT':'btc_usdt','ETH_LTC':'ltc_eth','ETC_USDT':'etc_usdt'}
		ok_url='https://www.okex.com/api/v1/depth.do?size=5&symbol='+coinMap[pair]
		ok_res = json.loads(requests.get(ok_url).text)
		print(requests.get(ok_url).text)
		return ok_res['asks'],ok_res['bids']
	except Exception as e:
		logger.error(e)
		return None,None

def getPoloniexLatestPrice(pair):
	try:
		coinMap={'BTC_ETH':'BTC_ETH','BTC_LTC':'BTC_LTC','BTC_USDT':'USDT_BTC','ETC_USDT':'USDT_ETC'}	
		url='https://poloniex.com/public?command=returnOrderBook&depth=5&currencyPair='+coinMap[pair]
		res_text=requests.get(url).text
		print(res_text)
		poloniex_res=json.loads(res_text)

		return poloniex_res['asks'],poloniex_res['bids']
	except Exception as e:
		logger.error(e)
		return None,None

def getWallet(cursor):
	cursor.execute("select exchange,ETC,USDT  from wallet")
	res = cursor.fetchall()
	mapRes={}
	for item in res:
		mapRes[item[0]]={'ETC':item[1],'USDT':item[2]}
	return mapRes
def ETCTask():
	try:

		# conn = sqlite3.connect(dbFile)
		# cursor = conn.cursor()
		# WALLET=getWallet(cursor)
		pair='ETC_USDT'
		askBook1,bidBook1=getOKEXLatestPrice(pair)
		askBook2,bidBook2=getPoloniexLatestPrice(pair)
		# print(askBook1,askBook2,bidBook1,bidBook2)
		if askBook1 is None or askBook2 is None or bidBook1 is None or bidBook2 is None:
			logger.error("exchange Failed to get info")
			return
		if float(bidBook2[0][0])-askBook1[0][0]> 1.9*(askBook1[0][0]*0.001+float(bidBook2[0][0])*0.0015):
			logger.info("exchange happy okex buy:"+str(askBook1[0][0]) +" poloniex sell:"+str(float(bidBook2[0][0])))
		elif bidBook1[0][0]-float(askBook2[0][0])> 1.9*(float(askBook2[0][0])*0.001+bidBook1[0][0]*0.0015):
			logger.info("exchange happy sell:"+str(bidBook1[0][0]) +" poloniex buy:"+str(float(askBook2[0][0])))
		else:
			logger.info("exchange no change okex:"+str(askBook1[0][0])+' '+str(bidBook1[0][0])+' poloniex:'+askBook2[0][0]+' '+bidBook2[0][0])
		
		
	except Exception as e:
		logger.error('etc  '+str(e))
	
if __name__ == '__main__':
	sched = Scheduler(standalone=True,misfire_grace_time=5)
	
	sched.add_interval_job(ETCTask , seconds=6,coalesce=True)
	try:
		sched.start()
	except (KeyboardInterrupt, SystemExit):
		pass