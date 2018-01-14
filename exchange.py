#!/usr/bin/python
# encoding: utf-8
from apscheduler.scheduler import Scheduler
import time
from datetime import datetime
import requests
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

def getOKEXLatestPrice(pair):
	coinMap={'BTC_ETH':'eth_btc','BTC_LTC':'ltc_btc','BTC_USDT':'btc_usdt','ETH_LTC':'ltc_eth'}
	ok_url='https://www.okex.com/api/v1/ticker.do?symbol='+coinMap[pair]
	ok_res = json.loads(requests.get(ok_url).text)
	ok_buy_price=float(ok_res['ticker']['buy'])
	ok_sell_price=float(ok_res['ticker']['sell'])
	return (ok_buy_price+ok_sell_price)/2

def getPoloniexLatestPrice(pair):
	coinMap={'BTC_ETH':'BTC_ETH','BTC_LTC':'BTC_LTC','BTC_USDT':'USDT_BTC'}	
	url='https://poloniex.com/public?command=returnOrderBook&depth=5&currencyPair=all'
	resMap=json.loads(requests.get(url).text)

def BTCTask():
	try:
		ok_url='https://www.okex.com/api/v1/ticker.do?symbol=btc_usdt'
		ok_res = json.loads(requests.get(ok_url).text)
		ok_buy_price=float(ok_res['ticker']['buy'])
		ok_sell_price=float(ok_res['ticker']['sell'])
		ok_price=(ok_buy_price+ok_sell_price)/2
		bittrex_url='https://api.bitfinex.com/v1/pubticker/BTCUSD'
		bittrex_res = json.loads(requests.get(bittrex_url).text)
		bittrex_price=float(bittrex_res['last_price'])
		delta_price=ok_price-bittrex_price	

		profit= abs(delta_price)-(ok_price*0.001+bittrex_price*0.0025)
		if profit>5:
			if delta_price>0:
				logger.debug('okex_btc_buy:'+str(profit))
			else:
				logger.debug('okex_btc_sell:'+str(profit))
		else:
			logger.debug('execute btctask no profit:'+ str(delta_price))
	except Exception as e:
		logger.error('btc  '+str(e))
def ETHTask():
	try:
		ok_url='https://www.okex.com/api/v1/ticker.do?symbol=ETH_usdt'
		ok_res = json.loads(requests.get(ok_url).text)
		ok_buy_price=float(ok_res['ticker']['buy'])
		ok_sell_price=float(ok_res['ticker']['sell'])
		ok_price=(ok_buy_price+ok_sell_price)/2	

		bittrex_url='https://api.bitfinex.com/v1/pubticker/ETHUSD'
		bittrex_res = json.loads(requests.get(bittrex_url).text)
		bittrex_price=float(bittrex_res['last_price'])
		delta_price=ok_price-bittrex_price
		profit= abs(delta_price)-(ok_price*0.001+bittrex_price*0.0025)
		if profit>5:
			if delta_price>0:
				logger.debug('okex_eth_buy:'+str(profit))
			else:
				logger.debug('okex_eth_sell:'+str(profit))
		else:
			logger.debug('execute ethtask no profit:'+ str(delta_price))
	except Exception as e:
		logger.error('eth  '+str(e))

	
if __name__ == '__main__':
	sched = Scheduler(standalone=True,misfire_grace_time=5)
	
	sched.add_interval_job(BTCTask , seconds=3,coalesce=True)
	sched.add_interval_job(ETHTask , seconds=6,coalesce=True)
	try:
		sched.start()
	except (KeyboardInterrupt, SystemExit):
		pass