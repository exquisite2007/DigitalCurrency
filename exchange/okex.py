
import requests
import json
import hashlib
class okexUtil:
	def __init__(self):
		pass
	access_key=None
	secret_key=None

	def generateOkParam(self,paramDict,secret_key):
		res= None
		for key in sorted(paramDict.iterkeys()):
			if res is  None:
				res=key+'='+str(paramDict[key])
			else:
				res+='&'+key+'='+str(paramDict[key])
		m=hashlib.md5()
		m.update(res+'&secret_key='+secret_key)
		sign=m.hexdigest().upper()
		paramDict['sign'] = sign
	def OkRequest(self,params):
		try:
			req_param={'api_key':self.access_key}
			self.generateOkParam(req_param,self.secret_key)
			url="https://www.okex.com/api/v1/userinfo.do"
			return json.loads(requests.post(url,data=req_param).text)
		except Exception as e:
			print(e)
			return None
	def getWallet(self):
		res=self.OkRequest(None)
		if res is not None:
			data={}
			data['ETC']=float(res['info']['funds']['free']['etc'])
			data['USDT']=float(res['info']['funds']['free']['usdt'])
			return data
		else:
			return None
