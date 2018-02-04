
import requests
import json
import hashlib
import hmac
from time import time
try:
    #python2
    from urllib import urlencode
except ImportError:
    #python3
    from urllib.parse import urlencode
import logging
logger = logging.getLogger("deal")
class poloniexUtil:
	def __init__(self):
		pass
	access_key=None
	secret_key=None

	
		
	def handleRequest(self,command,params={}):
		try:

			payload = {
				'command': command,
				'nonce': int(time() * 1000),
			}
			for key in params.keys():
				payload[key]=params[key]
			paybytes = urlencode(payload).encode('utf8')
			sign = hmac.new(self.secret_key, paybytes, hashlib.sha512).hexdigest()
			headers = {'Key': self.access_key,'Sign': sign,'Content-Type':'application/x-www-form-urlencoded'}
			url = 'https://poloniex.com/tradingApi'
			r = requests.post(url, headers=headers, data=paybytes)
			return json.loads(r.text)
		except Exception as e:
			logger.error('[poloniex] error happen in request:{}'.format(e))
			return None
	def getWallet(self):
		res=self.handleRequest('returnCompleteBalances',{})
		logger.debug('[poloniex]requst wallet result:{}'.format(res))
		if res is not None:
			data={}
			data['ETC']={'free':float(res['ETC']['available']),'locked':float(res['ETC']['onOrders'])}
			data['USDT']={'free':float(res['USDT']['available']),'locked':float(res['USDT']['onOrders'])}
			return data
		else:
			return None
	def buy(self,pair,rate,amount):
		params={'currencyPair':pair,'rate':rate,'amount':amount}

		res=self.handleRequest('buy',params)
		logger.debug('[poloniex] buy requst{}|{}|{}.get result:{}'.format(pair,rate,amount,res))
		if res is not None:
			return res
		else:
			return None
	def sell(self,pair,rate,amount):
		params={'currencyPair':pair,'rate':rate,'amount':amount}
		res=self.handleRequest('sell',params)
		logger.debug('[poloniex] sell requst{}|{}|{}.get result:{}'.format(pair,rate,amount,res))
		if res is not None:
			return res
		else:
			return None
