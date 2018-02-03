
import requests
import json
import hashlib

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
		m.update((param_str+'&secret_key='+self.secret_key).encode('utf-8'))
		sign=m.hexdigest().upper()
		params['sign'] = sign
		try:
			url="https://www.okex.com/api/v1/"+command
			return json.loads(requests.post(url,data=params).text)
		except Exception as e:
			return None


	def getWallet(self):
		res=self.handleRequest('userinfo.do')
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
		return res


		
	def sell(self,pair,rate,amount):
		params={'symbol':pair,'type':'sell','price':rate,'amount':amount}
		res=self.handleRequest('trade.do',params)
		
		return res
