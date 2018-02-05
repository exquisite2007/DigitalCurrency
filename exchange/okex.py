
import requests
import json
import hashlib
import sys
import os
from optparse import OptionParser
import logging
logger = logging.getLogger("deal")

class okexUtil:
	def __init__(self):
		pass
	access_key=None
	secret_key=None

	def handleRequest(self,command,params={}):
		params['api_key']=self.access_key
		param_str=None
		for key in sorted(params.keys()):
			if param_str is  None:
				param_str=key+'='+str(params[key])
			else:
				param_str+='&'+key+'='+str(params[key])
		m=hashlib.md5()
		param_str+='&secret_key='+self.secret_key
		m.update(param_str.encode('utf-8'))
		sign=m.hexdigest().upper()
		params['sign'] = sign
		try:
			url="https://www.okex.com/api/v1/"+command
			return json.loads(requests.post(url,data=params).text)
		except Exception as e:
			logger.error('[OKEX] request error happen:{}'.format(e))
			return None


	def getWallet(self):
		res=self.handleRequest('userinfo.do',{})
		logger.debug('[OKEX]requst wallet result:{}'.format(res))

		if res is not None and res['result'] is True:
			data={}
			data['ETC']={'free':float(res['info']['funds']['free']['etc']),'locked':float(res['info']['funds']['freezed']['etc'])}
			data['USDT']={'free':float(res['info']['funds']['free']['usdt']),'locked':float(res['info']['funds']['freezed']['usdt'])}
			return data
		else:
			return None
	def buy(self,pair,rate,amount):
		params={'symbol':pair,'type':'buy','price':rate,'amount':amount}
		res=self.handleRequest('trade.do',params)
		logger.debug('[OKEX] buy requst{}|{}|{}.get result:{}'.format(pair,rate,amount,res))
		return res


		
	def sell(self,pair,rate,amount):
		params={'symbol':pair,'type':'sell','price':rate,'amount':amount}
		res=self.handleRequest('trade.do',params)
		logger.debug('[OKEX] sell requst {}|{}|{}get result:{}'.format(pair,rate,amount,res))
		return res
def main(argv=None):
	parser = OptionParser()
	parser.add_option("-m", "--mode", dest="mode", help="0-wallet,1-buy,2-sell")
	parser.add_option("-r", "--rate", dest="rate", help="rate")
	parser.add_option("-a", "--amount", dest="amount", help="amount")
	parser.set_defaults(mode=0)
	util=okexUtil()
	
	if 'ok_access_key' not in os.environ or 'poloniex_access_key' not in os.environ:
		return
	util.access_key=os.environ['ok_access_key']
	util.secret_key=os.environ['ok_secret_key']
	(opts, args) = parser.parse_args(argv)
	print(opts)
	if int(opts.mode)==0:
		print(util.getWallet())
	elif int(opts.mode)==1:
		if opts.amount is None or opts.rate is None:
			return
		print(util.buy('etc_usdt',float(opts.rate),float(opts.amount)))
	elif int(opts.mode)==2:
		if opts.amount is None or opts.rate is None:
			return
		print(util.sell('etc_usdt',float(opts.rate),float(opts.amount)))



if __name__ == "__main__":
	sys.exit(main())
