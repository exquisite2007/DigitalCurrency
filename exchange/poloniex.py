
import requests
import json
import hashlib
import hmac
import asyncio
import websockets
from time import time
try:
    #python2
    from urllib import urlencode
except ImportError:
    #python3
    from urllib.parse import urlencode
import logging
logger = logging.getLogger("deal")
BOOK_LIMIT=10
class poloniexUtil:
	def __init__(self,pair):
		self.name='poloniex'
		self.PAIR_MAP={'BTC_ETH':'BTC_ETH','BTC_LTC':'BTC_LTC','BTC_USDT':'USDT_BTC','ETC_USDT':'USDT_ETC'}
		self.CURRENT_PAIR=self.PAIR_MAP[pair]
		self.CURRENCY=pair.split('_')
		self.WALLET={}
		self.ORDER_BOOK={}
		self.TAKER_FEE=0.0025
		# 补偿，买一个币，只能得到（1-self.TAKER_FEE）个币，为了保证两边币的数量一致，增加一个补偿量
		self.BUY_PATCH=(1+self.TAKER_FEE)*self.TAKER_FEE
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
			raise Exeption(self.name,'Error in handleRequest:{},{}'.format(command,params))
		
	async def buy(self,rate,amount):
		patch_amount=amount(1+self.BUY_PATCH)
		self.WALLET[self.CURRENCY[1]]['free']-=patch_amount*rate
		self.WALLET[self.CURRENCY[1]]['locked']+=patch_amount*rate
		params={'currencyPair':self.CURRENT_PAIR,'rate':rate,'amount':patch_amount}
		loop=asyncio.get_event_loop()
		res = await loop.run_in_executor(None, self.handleRequest,'buy',params)
		logger.debug('[poloniex] buy request {}|{}|{}.get result:{}'.format(self.CURRENT_PAIR,rate,patch_amount,res))
		if res is not None:
			return res
		else:
			raise Exeption(self.name,'Error in buy:{}|{}'.format(rate,amount))
	async def sell(self,rate,amount):
		self.WALLET[self.CURRENCY[0]]['free']-=amount
		self.WALLET[self.CURRENCY[0]]['locked']+=amount
		params={'currencyPair':self.CURRENT_PAIR,'rate':rate,'amount':amount}
		loop=asyncio.get_event_loop()
		res = await loop.run_in_executor(None, self.handleRequest,'sell',params)
		logger.info('[poloniex] sell request {}|{}|{}.get result:{}'.format(self.CURRENT_PAIR,rate,amount,res))
		if res is not None:
			return res
		else:
			raise Exeption(self.name,'Error in sell:{}|{}'.format(rate,amount))

	async def unfinish_order(self,pair):
		params={'currencyPair':self.CURRENT_PAIR}
		loop=asyncio.get_event_loop()
		res = await loop.run_in_executor(None, self.handleRequest,'returnOpenOrders',params)
		if res is not None:
			logger.debug('[poloniex] unfinish_order :{}.get result:{}'.format(pair,res))
			return res
		else:
			raise Exeption(self.name,'Error in unfinish_order')
	async def move_order(self,orderId,rate):
		params={'orderNumber':orderId}
		loop=asyncio.get_event_loop()
		res = await loop.run_in_executor(None, self.handleRequest,'moveOrder',params)
		if res is not None:
			logger.debug('[poloniex] move order:{}|{}.get result:{}'.format(orderId,rate,res))
			return res
		else:
			raise Exeption(self.name,'Error in move_order:{}|{}'.format(orderId,rate))
	def cancel_order(self,orderId):
		params={'orderNumber':orderId}
		res=self.handleRequest('cancelOrder',params)
		if res is not None:
			return res
		else:
			raise Exeption(self.name,'Error in cancel_order:{orderId}'.format(orderId))

	async def init_wallet(self):
		loop=asyncio.get_event_loop()
		res = await loop.run_in_executor(None, self.handleRequest,'returnCompleteBalances',{})
		self.WALLET={}
		if res is not None:
			self.WALLET[self.CURRENCY[0]]={'free':float(res[self.CURRENCY[0]]['available']),'locked':float(res[self.CURRENCY[0]]['onOrders'])}
			self.WALLET[self.CURRENCY[1]]={'free':float(res[self.CURRENCY[1]]['available']),'locked':float(res[self.CURRENCY[1]]['onOrders'])}
			logger.info('Finish load poloniex wallet:{}'.format(self.WALLET))
		else:
			raise Exeption(self.name,'Error in init_wallet')

	async def order_book(self,trade_handler):
		while True:
			async with websockets.connect('wss://api2.poloniex.com/') as websocket:
				try:
					param={'command':'subscribe','channel':self.CURRENT_PAIR}
					await websocket.send(json.dumps(param))	
					while True:
						message = await websocket.recv()
						res=json.loads(message)
						if len(res)<2:
							continue
						logger.debug('poloniex:{}'.format(res))
						for item in res[2]:
							if item[0] == 'i':
								book_size=0
								ask_map={}
								for key in sorted(item[1]['orderBook'][0],key=lambda subItem:float(subItem))[:BOOK_LIMIT]:
									ask_map[key]=float(item[1]['orderBook'][0][key])
								self.ORDER_BOOK['ask']=ask_map
								bid_map={}
								for key  in sorted(item[1]['orderBook'][1],key=lambda subItem:float(subItem),reverse=True)[:BOOK_LIMIT]:
									bid_map[key]=float(item[1]['orderBook'][1][key])
								self.ORDER_BOOK['bid']=bid_map
							elif item[0] == 'o':
								# ['o', 1, '26.54474428', '0.00000000']
								if item[1] == 0:#ask
									if float(item[3])==0 and item[2] in  self.ORDER_BOOK['ask']:
										del self.ORDER_BOOK['ask'][item[2]]
									elif float(item[3])>0:
										self.ORDER_BOOK['ask'][item[2]]=float(item[3])
								elif item[1] == 1:#bid
									if float(item[3])==0 and item[2] in  self.ORDER_BOOK['bid']:
										del self.ORDER_BOOK['bid'][item[2]]
									elif float(item[3])>0:
										self.ORDER_BOOK['bid'][item[2]]=float(item[3])

						await trade_handler()
				except Exception as e:
					self.ORDER_BOOK={}
					logger.error(e)
					websocket.close()
	def get_orderbook_head(self):
		if len(self.ORDER_BOOK)>0:
			ask_head=min(self.ORDER_BOOK['ask'],key=lambda subItem:float(subItem))
			ask_head_volume=self.ORDER_BOOK['ask'][ask_head]
			ask_head=float(ask_head)
			bid_head=max(self.ORDER_BOOK['bid'],key=lambda subItem:float(subItem))
			bid_head_volume=self.ORDER_BOOK['bid'][bid_head]
			bid_head=float(bid_head)
			return (ask_head,ask_head_volume,bid_head,bid_head_volume)
		else:
			return None


	def get_sell_info(self,rate):
		if len(self.WALLET)<=0:
			raise Exeption(self.name,'Error in get_sell_info')
		else:
			avaliable_amount=self.WALLET[self.CURRENCY[0]]['free']
			cost=self.TAKER_FEE*rate
			return(avaliable_amount,cost)
	def get_buy_info(self,rate):
		if len(self.WALLET)<=0:
			raise Exeption(self.name,'Error in get_buy_info')
		else:
			avaliable_amount=self.WALLET[self.CURRENCY[1]]['free']/rate/(1+self.BUY_PATCH)
			cost=self.TAKER_FEE*rate*(1+self.BUY_PATCH)
			return(avaliable_amount,cost)

	async def unfinish_order_handler(self):
		res = await self.unfinish_order(self.CURRENT_PAIR)
		# head=self.get_orderbook_head()
		# if res is not None and head is not None:
		# 	lst=[]
		# 	for item in res:
		# 		if item['type']=='sell' and float(item['rate'])<head[2]:
		# 			lst.append(self.move_order(item['orderNumber'],head[2]))
		# 		if item['type']=='buy' and float(item['rate'])>head[0]:
		# 			lst.append(self.move_order(item['orderNumber'],head[0]))
		# 	if len(lst)>0:
		# 		await asyncio.wait(lst,return_when=asyncio.FIRST_COMPLETED,)

