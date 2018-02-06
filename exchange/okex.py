
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
		self.PAIR_MAP={'BTC_ETH':'eth_btc','BTC_LTC':'ltc_btc','BTC_USDT':'btc_usdt','ETH_LTC':'ltc_eth','ETC_USDT':'etc_usdt'}
		self.CURRENT_PAIR=self.PAIR_MAP[pair]
		self.CURRENCY=pair.split('_')
		self.WALLET={}
		self.ORDER_BOOK={}
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


	async def buy(self,rate,amount):		
		self.WALLET[self.CURRENCY[1]]['free']-=amount*rate
		self.WALLET[self.CURRENCY[1]]['locked']+=amount*rate
		params={'symbol':self.CURRENT_PAIR,'type':'buy','price':rate,'amount':amount}
		loop=asyncio.get_event_loop()
		res = await loop.run_in_executor(None,self.handleRequest,'trade.do',params)
		logger.debug('[OKEX] buy requst{}|{}|{}.get result:{}'.format(self.CURRENT_PAIR,rate,amount,res))
		return res


		
	async def sell(self,rate,amount):
		self.WALLET[self.CURRENCY[0]]['free']-=amount
		self.WALLET[self.CURRENCY[0]]['locked']+=amount
		params={'symbol':self.CURRENT_PAIR,'type':'sell','price':rate,'amount':amount}
		loop=asyncio.get_event_loop()
		res = await loop.run_in_executor(None,self.handleRequest,'trade.do',params)
		logger.debug('[OKEX] sell requst {}|{}|{}get result:{}'.format(self.CURRENT_PAIR,rate,amount,res))
		return res
	async def unfinish_order(self):
		loop=asyncio.get_event_loop()
		res = await loop.run_in_executor(None, self.handleRequest,'order_info.do',{})
		logger.debug('[OKEX] unfinished order get result:{}'.format(res))
		return res
	async def cancel_order(self,orderId,pair):
		loop=asyncio.get_event_loop()
		params={'order_id':orderId,'symbol':pair}
		res = await loop.run_in_executor(None, self.handleRequest,'cancel_order.do',params)
		if res is not None:
			return res
		else:
			return None

	async def init_wallet(self):
		loop=asyncio.get_event_loop()
		res = await loop.run_in_executor(None, self.handleRequest,'userinfo.do',{})
		self.WALLET={}
		if res is not None:
			self.WALLET[self.CURRENCY[0]]={'free':float(res['info']['funds']['free'][self.CURRENCY[0]]),'locked':float(res['info']['funds']['freezed'][self.CURRENCY[0]])}
			self.WALLET[self.CURRENCY[1]]={'free':float(res['info']['funds']['free'][self.CURRENCY[1]]),'locked':float(res['info']['funds']['freezed'][self.CURRENCY[1]])}
			logger.info('Finish load poloniex wallet:{}'.format(self.WALLET))
		else:
			logger.error('Error for update poloniex wallet:{}'.format(res))

	async def order_book(self,trade_handler):
		channel='ok_sub_spot_'+self.CURRENT_PAIR+'_depth_5'
		while True:
			async with websockets.connect('wss://real.okex.com:10441/websocket') as websocket:
				try:	
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
						await trade_handler()
				except  Exception as e:
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
	def get_sell_avaliable_amount(self):
		if len(self.WALLET)>0:
			self.WALLET[self.CURRENCY[0]]['free']
		else:
			return 0
	def get_buy_avaliable_amount(self,rate):
		if len(self.WALLET)>0:
			self.WALLET[self.CURRENCY[1]]['free']/rate
		else:
			return 0
	async def unfinish_order_handler(self):
		res = await self.unfinish_order()
		logger.debug('REMOVE{}'.format(res))
		if res is not None and len(res)>0:
			for item in res:
				head_res=self.get_orderbook_head()

				if head_res is not None and item['type']=='sell' and head_res[2]-item['price']*1.001>0:
					cancel_res= await self.cancel_order(item['order_id'],item['symbol'])
					if cancel_res is not None and cancel_res['result']==True:
						await self.sell(head_res[2],item['amount'])

				if head_res is not None and item['type']=='buy' and item['price']*0.-head_res[0]*1.001>0:
					cancel_res= await self.cancel_order(item['order_id'],item['symbol'])
					if cancel_res is not None and cancel_res['result']==True:
						await self.buy(head_res[0],item['amount'])


		logger.info("TODO: handle okex unfinisehd order")
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



if __name__ == "__main__":
	sys.exit(main())
