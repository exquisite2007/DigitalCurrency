import asyncio
import requests

class test1:
	def __init__(self):
		pass
	def haha(self,param2):
		print('param2:{}'.format(param2))
	async def main(self,parma1):
		print(parma1)
		self.haha(567)
		loop = asyncio.get_event_loop()
		future1 = loop.run_in_executor(None, requests.get, 'http://www.baidu.com')
		future2 = loop.run_in_executor(None, requests.get, 'http://www.126.com')
		response1 = await future1
		response2 = await future2
		print('Fiish')
test=test1()
loop = asyncio.get_event_loop()
loop.run_until_complete(test.main(123))