import hmac
import hashlib
import json
import requests
import random
params={}
params['ok_buy_thres']=0.035
params['poloniex_buy_thres']=0.04
params['rand']=str(random.randint(1000000,2000000))
randStr='I am really poor'+params['rand']
params['sign']=hmac.new(randStr.encode(),digestmod=hashlib.sha256).hexdigest()
r = requests.post("http://127.0.0.1:20183/threshold", data=json.dumps(params))
print(r.text)