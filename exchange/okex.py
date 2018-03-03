
import requests
import json
import hashlib
import sys
import os
from optparse import OptionParser
import logging
import asyncio
import websockets

logger = logging.getLogger("deal")

class okexUtil:
	def __init__(self,pair):
		self.name='OKEX'
		self.PAIR_MAP={'BTC_ETH':'eth_btc','BTC_LTC':'ltc_btc','BTC_USDT':'btc_usdt','ETH_LTC':'ltc_eth','ETC_USDT':'etc_usdt'}
		self.CURRENT_PAIR=self.PAIR_MAP[pair]
		self.CURRENCY=self.CURRENT_PAIR.split('_')
		self.WALLET={}
		self.ORDER_BOOK={}
		self.TAKER_FEE=0.002
		# 补偿，买一个币，只能得到（1-self.TAKER_FEE）个币，为了保证两边币的数量一致，增加一个补偿量
		self.BUY_PATCH=(1+self.TAKER_FEE)*self.TAKER_FEE
		self.ask_head_all=None
		self.bid_head_all=None
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
			raise Exception(self.name,'Error in handleRequest:{}|{}'.format(command,params))


	async def buy(self,rate,amount):
		patch_amount=amount*(1+self.BUY_PATCH)	
		self.WALLET[self.CURRENCY[1]]['free']-=patch_amount*rate
		self.WALLET[self.CURRENCY[1]]['locked']+=patch_amount*rate
		params={'symbol':self.CURRENT_PAIR,'type':'buy','price':rate,'amount':patch_amount}
		loop=asyncio.get_event_loop()
		res = await loop.run_in_executor(None,self.handleRequest,'trade.do',params)
		logger.debug('[OKEX] buy request {}|{}|{}.get result:{}'.format(self.CURRENT_PAIR,rate,patch_amount,res))
		return res['order_id']


		
	async def sell(self,rate,amount):
		self.WALLET[self.CURRENCY[0]]['free']-=amount
		self.WALLET[self.CURRENCY[0]]['locked']+=amount
		params={'symbol':self.CURRENT_PAIR,'type':'sell','price':rate,'amount':amount}
		loop=asyncio.get_event_loop()
		res = await loop.run_in_executor(None,self.handleRequest,'trade.do',params)
		logger.debug('[OKEX] sell request {}|{}|{}get result:{}'.format(self.CURRENT_PAIR,rate,amount,res))
		return res['order_id']
	async def unfinish_order(self):
		loop=asyncio.get_event_loop()
		res = await loop.run_in_executor(None, self.handleRequest,'order_info.do',{'symbol':self.CURRENT_PAIR,'order_id':-1})
		logger.debug('[OKEX] unfinished order get result:{}'.format(res))
		if res is not None and res['result']==True:
			return res['orders']
		else:
			raise Exception(self.name,'Error in unfinish_order')

	async def cancel_order(self,orderId,pair):
		loop=asyncio.get_event_loop()
		params={'order_id':orderId,'symbol':pair}
		res = await loop.run_in_executor(None, self.handleRequest,'cancel_order.do',params)
		if res is not None and res['result']==True:
			return res
		else:
			raise Exception(self.name,'Error happen in cancel order {}|{}'.format(orderId,pair))

	async def init_wallet(self):
		loop=asyncio.get_event_loop()
		res = await loop.run_in_executor(None, self.handleRequest,'userinfo.do',{})
		self.WALLET={}
		if res is not None and res['result']==True:
			self.WALLET[self.CURRENCY[0]]={'free':float(res['info']['funds']['free'][self.CURRENCY[0]]),'locked':float(res['info']['funds']['freezed'][self.CURRENCY[0]])}
			self.WALLET[self.CURRENCY[1]]={'free':float(res['info']['funds']['free'][self.CURRENCY[1]]),'locked':float(res['info']['funds']['freezed'][self.CURRENCY[1]])}
			logger.info('Finish load okex wallet:{}'.format(self.WALLET))
		else:
			raise Exception(self.name,'Error in init_wallet')

	async def order_book(self,trade_handler):
		channel='ok_sub_spot_'+self.CURRENT_PAIR+'_depth_5'
		while True:
			try:
				logger.info('OKEX BOOK start to connect')
				async with websockets.connect('wss://real.okex.com:10441/websocket') as websocket:

					logger.info('OKEX enter communication')
					param={'event':'addChannel','channel':channel}
					await websocket.send(json.dumps(param))
					while True:
						message = await websocket.recv()
						res=json.loads(message)
						if type(res) is list and res[0]['channel'].startswith('ok'):
							ask_map={}
							for item in res[0]['data']['asks']:
								ask_map[item[0]]=float(item[1])
							self.ORDER_BOOK['ask']=ask_map
							bid_map={}
							for item in res[0]['data']['bids']:
								bid_map[item[0]]=float(item[1])
							self.ORDER_BOOK['bid']=bid_map

							ask_head=min(self.ORDER_BOOK['ask'],key=lambda subItem:float(subItem))
							ask_head_volume=self.ORDER_BOOK['ask'][ask_head]
							ask_head_all=ask_head+':'+str(ask_head_volume)
							bid_head=max(self.ORDER_BOOK['bid'],key=lambda subItem:float(subItem))
							bid_head_volume=self.ORDER_BOOK['bid'][bid_head]
							bid_head_all=bid_head+':'+str(bid_head_volume)
							if ask_head_all != self.ask_head_all or bid_head_all != self.bid_head_all:
								self.ask_head_all=ask_head_all
								self.bid_head_all=bid_head_all
								await trade_handler()
			except Exception as le:
				logger.error('OKEX BOOK connect:{}'.format(le))
				self.ORDER_BOOK={}
				self.ask_head_all=None
				self.bid_head_all=None

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

	async def unfinish_order_handler(self):
		res = await self.unfinish_order()
		# if res is not None and len(res)>0:
		# 	for item in res:
		# 		head_res=self.get_orderbook_head()
		# 		if head_res is not None and item['type']=='sell' and head_res[2]-item['price']*1.001>0:
		# 			cancel_res= await self.cancel_order(item['order_id'],item['symbol'])
		# 			if cancel_res is not None and cancel_res['result']==True:
		# 				await self.sell(head_res[2],item['amount'])

		# 		if head_res is not None and item['type']=='buy' and item['price']*0.-head_res[0]*1.001>0:
		# 			cancel_res= await self.cancel_order(item['order_id'],item['symbol'])
		# 			if cancel_res is not None and cancel_res['result']==True:
		# 				await self.buy(head_res[0],item['amount'])


def main(argv=None):
	parser = OptionParser()
	parser.add_option("-m", "--mode", dest="mode", help="0-wallet,1-buy,2-sell")
	parser.add_option("-r", "--rate", dest="rate", help="rate")
	parser.add_option("-a", "--amount", dest="amount", help="amount")
	parser.set_defaults(mode=0)
	util=okexUtil('ETC_USDT')
	loop=asyncio.get_event_loop()

	
	if 'ok_access_key' not in os.environ:
		return
	util.access_key=os.environ['ok_access_key']
	util.secret_key=os.environ['ok_secret_key']
	(opts, args) = parser.parse_args(argv)

	if int(opts.mode) == 0:
		loop.run_until_complete(util.unfinish_order())

if __name__ == "__main__":
	sys.exit(main())
