import requests
import json
import hashlib
import sys
import os
from optparse import OptionParser
import logging
import asyncio
import websockets
import random

logger = logging.getLogger("deal")

class fakeUtil:
	def __init__(self,pair):
		self.name='FAKE'
		self.PAIR_MAP={'BTC_ETH':'eth_btc','BTC_LTC':'ltc_btc','BTC_USDT':'btc_usdt','ETH_LTC':'ltc_eth','ETC_USDT':'etc_usdt','LTC_USDT':'ltc_usdt'}
		self.CURRENT_PAIR=self.PAIR_MAP[pair]
		self.CURRENCY=self.CURRENT_PAIR.split('_')
		self.WALLET={}
		self.ORDER_BOOK={}
		self.TAKER_FEE=0.002
		# 补偿，买一个币，只能得到（1-self.TAKER_FEE）个币，为了保证两边币的数量一致，增加一个补偿量
		self.BUY_PATCH=(1+self.TAKER_FEE)*self.TAKER_FEE
		self.ask_head_all=None
		self.bid_head_all=None
		self.ticker_value=None
	access_key=None
	secret_key=None



	async def buy(self,rate,amount,is_market=False):
		await asyncio.sleep(2)
		self.WALLET[self.CURRENCY[0]]['free']+=amount*0.998
		self.WALLET[self.CURRENCY[1]]['free']-=amount*rate
		return random.randrange(1000000,20000000)


		
	async def sell(self,rate,amount,is_market=False):
		await asyncio.sleep(2)
		self.WALLET[self.CURRENCY[0]]['free']-=amount
		self.WALLET[self.CURRENCY[1]]['free']+=amount*rate *0.998
		return random.randrange(1000000,20000000)
	async def unfinish_order(self):
		await asyncio.sleep(2)

	async def cancel_order(self,orderId):
		await asyncio.sleep(2)

	async def init_wallet(self):
		await asyncio.sleep(2)
		logger.info('current wallet info {!r}'.format(self.WALLET))

		



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

