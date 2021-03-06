import base64
import urllib
import urllib.parse
import urllib.request
import requests
import json
import hashlib
import hmac
import asyncio
import websockets
from time import time
import gzip
import sys
import os
import datetime
from optparse import OptionParser
import math
try:
	#python2
	from urllib import urlencode
except ImportError:
	#python3
	from urllib.parse import urlencode
import logging
logger = logging.getLogger("deal")
def http_get_request(url, params, add_to_headers=None):

	headers = {
		"Content-type": "application/x-www-form-urlencoded",
		'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.71 Safari/537.36',
	}
	if add_to_headers:
		headers.update(add_to_headers)
	postdata = urllib.parse.urlencode(params)
	response = requests.get(url, postdata, headers=headers, timeout=10) 
	try:
		
		if response.status_code == 200:
			return response.json()
		else:
			return
	except BaseException as e:
		print("httpGet failed, detail is:%s,%s" %(response.text,e))
		return


def http_post_request(url, params, add_to_headers=None):
	headers = {
		"Accept": "application/json",
		'Content-Type': 'application/json'
	}
	if add_to_headers:
		headers.update(add_to_headers)
	postdata = json.dumps(params)
	response = requests.post(url, postdata, headers=headers, timeout=10)
	try:
		if response.status_code == 200:
			return response.json()
		else:
			return
	except BaseException as e:
		print("httpPost failed, detail is:%s,%s" %(response.text,e))
		return

def createSign(pParams, method, host_url, request_path, secret_key):
	sorted_params = sorted(pParams.items(), key=lambda d: d[0], reverse=False)
	encode_params = urllib.parse.urlencode(sorted_params)
	payload = [method, host_url, request_path, encode_params]
	payload = '\n'.join(payload)
	payload = payload.encode(encoding='UTF8')
	secret_key = secret_key.encode(encoding='UTF8')

	digest = hmac.new(secret_key, payload, digestmod=hashlib.sha256).digest()
	signature = base64.b64encode(digest)
	signature = signature.decode()
	return signature





class huobiUtil:
	def __init__(self,pair):
		self.name='huobi'
		self.PAIR_MAP={'BTC_ETH':'ethbtc','BTC_LTC':'ltcbtc','BTC_USDT':'btcusdt','ETC_USDT':'etcusdt'}	
		self.CURRENT_PAIR=self.PAIR_MAP[pair]
		self.CURRENCY=[self.CURRENT_PAIR[:3],self.CURRENT_PAIR[3:]]
		self.WALLET={}
		self.ORDER_BOOK={}
		self.TAKER_FEE=0.002
		self.BUY_PATCH=(1+self.TAKER_FEE)*self.TAKER_FEE
		self.ask_head_all=None
		self.bid_head_all=None
		self.ticker_value=None
		self.account_id=0
		self.NEED_RECONNECT=False
	access_key=None
	secret_key=None
	def api_key_get(self,params, request_path):
		method = 'GET'
		timestamp = datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S')
		params.update({'AccessKeyId': self.access_key,
			'SignatureMethod': 'HmacSHA256',
			'SignatureVersion': '2',
			'Timestamp': timestamp})	

		host_url = 'https://api.huobi.pro'
		host_name = urllib.parse.urlparse(host_url).hostname
		host_name = host_name.lower()
		params['Signature'] = createSign(params, method, host_name, request_path, self.secret_key)	

		url = host_url + request_path
		return http_get_request(url, params)


	def api_key_post(self,params, request_path):
		method = 'POST'
		timestamp = datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S')
		params_to_sign = {'AccessKeyId': self.access_key,
			'SignatureMethod': 'HmacSHA256',
			'SignatureVersion': '2',
			'Timestamp': timestamp}	

		host_url = 'https://api.huobi.pro'
		host_name = urllib.parse.urlparse(host_url).hostname
		host_name = host_name.lower()
		params_to_sign['Signature'] = createSign(params_to_sign, method, host_name, request_path, self.secret_key)
		url = host_url + request_path + '?' + urllib.parse.urlencode(params_to_sign)
		return http_post_request(url, params)
	async def order_book(self,trade_handler):
		while True:
			async with websockets.connect('wss://api.huobi.pro/ws') as websocket:
				try:
					param={'sub':'market.'+self.CURRENT_PAIR+'.depth.step0','id':'5201314'}
					await websocket.send(json.dumps(param))	
					self.NEED_RECONNECT=False
					while not self.NEED_RECONNECT:
						msg=await websocket.recv()
						message = json.loads(gzip.decompress(msg).decode("utf-8"))	
						if 'ping' in message:
							await websocket.send(json.dumps({'pong':message['ping']}))
						elif 'tick' in message:
							ask_head_all=str(message['tick']['asks'][0][0])+':'+str(message['tick']['asks'][0][1])
							bid_head_all=str(message['tick']['bids'][0][0])+':'+str(message['tick']['bids'][0][1])
							if ask_head_all != self.ask_head_all or bid_head_all != self.bid_head_all:
								self.ask_head_all=ask_head_all
								self.bid_head_all=bid_head_all
								await trade_handler()
				except Exception as e:
					self.ORDER_BOOK={}
					self.ask_head_all=None
					self.bid_head_all=None
					logger.error('ERROR happen in {} connection:{}'.format(huobiUtil.__name__,e))
					websocket.close()
	async def ticker(self,trade_handler):
		while True:
			try:
				async with websockets.connect('wss://api.huobi.pro/ws') as websocket:
					param={'sub':'market.'+self.CURRENT_PAIR+'.depth.step0','id':'5201314'}
					await websocket.send(json.dumps(param))	
					while True:
						msg=await websocket.recv()
						message = json.loads(gzip.decompress(msg).decode("utf-8"))	
						if 'ping' in message:
							await websocket.send(json.dumps({'pong':message['ping']}))
						elif 'tick' in message:
							ask_head_all=str(message['tick']['asks'][0][0])+':'+str(message['tick']['asks'][0][1])
							bid_head_all=str(message['tick']['bids'][0][0])+':'+str(message['tick']['bids'][0][1])
							
							self.ticker_value=(message['tick']['asks'][0][0],message['tick']['bids'][0][0],None)
							await trade_handler()
						else:
							print(message)
			except Exception as e:
				self.ticker_value=None
				logger.error('ERROR happen in {} connection:{}'.format(huobiUtil.__name__,e))
				websocket.close()

	def get_orderbook_head(self):
		if self.ask_head_all is None or self.bid_head_all is None:
			raise Exception(self.name,'Error in get_orderbook_head')
		else:
			ask_heads=self.ask_head_all.split(':')
			bid_heads=self.bid_head_all.split(':')
			return (float(ask_heads[0]),float(ask_heads[1]),float(bid_heads[0]),float(bid_heads[1]))
	def get_sell_info(self,rate):
		if len(self.WALLET)<=0:
			raise Exception(self.name,'Error in get_sell_info')
		else:
			avaliable_amount=self.WALLET[self.CURRENCY[0]]['free']
			cost=self.TAKER_FEE*rate
			return(avaliable_amount,cost)
	def get_buy_info(self,rate):
		if len(self.WALLET)<=0:
			raise Exception(self.name,'Error in get_buy_info')
		else:
			avaliable_amount=self.WALLET[self.CURRENCY[1]]['free']/rate/(1+self.BUY_PATCH)
			cost=self.TAKER_FEE*rate*(1+self.BUY_PATCH)
			return(avaliable_amount,cost)

	async def buy(self,rate,amount,is_market=False):
		patch_amount=math.ceil(amount*(1+self.BUY_PATCH)*10000)/10000
		rate=math.ceil(rate*100)/100
		self.WALLET[self.CURRENCY[1]]['free']-=patch_amount*rate
		self.WALLET[self.CURRENCY[1]]['locked']+=patch_amount*rate
		if self.account_id==0:
			await self.get_account()
		params={}
		if is_market:
			params={"account-id": self.account_id,"amount": patch_amount, "symbol": self.CURRENT_PAIR,"type": 'buy-market'}
		else:
			params={"account-id": self.account_id,"amount": patch_amount, "symbol": self.CURRENT_PAIR,"type": 'buy-limit',"price":rate}
		loop=asyncio.get_event_loop()
		res = await loop.run_in_executor(None,self.api_key_post,params,'/v1/order/orders/place')
		logger.debug('[huobi] buy request {}|{}|{}.get result:{}'.format(self.CURRENT_PAIR,rate,patch_amount,res))
		return res['data']


		
	async def sell(self,rate,amount,is_market=False):
		amount=math.ceil(amount*(1+self.BUY_PATCH)*10000)/10000
		rate=math.ceil(rate*100)/100
		if self.WALLET is not None:
			self.WALLET[self.CURRENCY[0]]['free']-=amount
			self.WALLET[self.CURRENCY[0]]['locked']+=amount
		if self.account_id==0:
			await self.get_account()
		params={}
		if is_market:
			params={"account-id": self.account_id,"amount": amount, "symbol": self.CURRENT_PAIR,"type": 'sell-market'}
		else:
			params={"account-id": self.account_id,"amount": amount, "symbol": self.CURRENT_PAIR,"type": 'sell-limit',"price":rate}
		loop=asyncio.get_event_loop()
		res = await loop.run_in_executor(None,self.api_key_post,params,'/v1/order/orders/place')
		logger.debug('[huobi] sell request {}|{}|{}get result:{}'.format(self.CURRENT_PAIR,rate,amount,res))
		return res['data']
	async def unfinish_order(self):
		raise Exception(self.name,'not implemented')

	async def cancel_order(self,orderId):
		# if self.account_id==0:
		# 	await self.get_account()
		loop=asyncio.get_event_loop()
		
		res = await loop.run_in_executor(None, self.api_key_post,{},"/v1/order/orders/{0}/submitcancel".format(orderId))
		if res is not None and res['status']=='ok':
			return res
		else:
			raise Exception(self.name,'Error happen in cancel order {}'.format(orderId))

	async def get_account(self):
		loop=asyncio.get_event_loop()
		res = await loop.run_in_executor(None, self.api_key_get,{},'/v1/account/accounts')
		self.account_id=res['data'][0]['id']


	async def init_wallet(self):
		if self.account_id==0:
			await self.get_account()
		loop=asyncio.get_event_loop()
		res = await loop.run_in_executor(None, self.api_key_get,{},'/v1/account/accounts/{0}/balance'.format(self.account_id))
		self.WALLET={}
		if res is not None and res['status']=='ok':
			for item in res['data']['list']:
				for cur in self.CURRENCY:
					if cur not in self.WALLET:
						self.WALLET[cur]={}
					if item['currency']== cur:
						if item['type']=='trade':
							self.WALLET[cur]['free']=float(item['balance'])
						elif item['type'] == 'frozen':
							self.WALLET[cur]['locked']=float(item['balance'])
			logger.info('Finish load huobi wallet:{}'.format(self.WALLET))
		else:
			raise Exception(self.name,'Error in init_wallet')
	async def health_check(self):
		huobi_ask_head_all='begin'
		huobi_bid_head_all='begin'
		while True:
			await asyncio.sleep(300)
			if huobi_bid_head_all == self.bid_head_all or huobi_ask_head_all== self.ask_head_all:
				logger.error("huobi order head update die !!!")
				self.NEED_RECONNECT=True
			else:
				huobi_bid_head_all = self.bid_head_all
				huobi_ask_head_all = self.ask_head_all
			#
async def test():
	print('nothing here:{}'.format('larla'))
def main(argv=None):
	parser = OptionParser()
	parser.add_option("-p", "--pair", dest="pair", help="pair")
	parser.add_option("-m", "--mode", dest="mode", help="0-ticker,1-buy,2-sell,3-wallet")
	parser.set_defaults(pair='ETC_USDT',mode=0)
	
	util = huobiUtil('ETC_USDT')
	util.access_key=os.environ['huobi_access_key']
	util.secret_key=os.environ['huobi_secret_key']
	(opts, args) = parser.parse_args(argv)
	loop=asyncio.get_event_loop()
	if int(opts.mode)==0:
		loop.run_until_complete(util.order_book(test))
	if int(opts.mode)==1:
		loop.run_until_complete(util.buy(1,0.1))
	if int(opts.mode)==2:
		loop.run_until_complete(util.sell(100,0.1))
	elif int(opts.mode)==3:
		loop.run_until_complete(util.init_wallet())
	elif int(opts.mode)==4:
		loop.run_until_complete(util.unfinish_order())
	elif int(opts.mode)==5:
		loop.run_until_complete(util.cancel_order('2631428446'))
if __name__ == "__main__":
	sys.exit(main())

