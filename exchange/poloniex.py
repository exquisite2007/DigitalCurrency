
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
class poloniexUtil:
	def __init__(self):
		pass
	access_key=None
	secret_key=None

	
		
	def generatPoloniexParam(self,command):
		try:

			payload = {
				'command': command,
				'nonce': int(time() * 1000),
			}
			paybytes = urlencode(payload).encode('utf8')
			sign = hmac.new(self.secret_key, paybytes, hashlib.sha512).hexdigest()
			headers = {'Key': self.access_key,'Sign': sign,'Content-Type':'application/x-www-form-urlencoded'}
			url = 'https://poloniex.com/tradingApi'
			r = requests.post(url, headers=headers, data=paybytes)
			return json.loads(r.text)
		except Exception as e:
			print(e)
			return None
	def getWallet(self):
		res=self.generatPoloniexParam('returnBalances')
		if res is not None:
			data={}
			data['ETC']=float(res['ETC'])
			data['USDT']=float(res['USDT'])
			return data
		else:
			return None