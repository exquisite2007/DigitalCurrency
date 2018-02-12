from aiohttp import web
import asyncio
import json
async def handle(request):
    name = request.match_info.get('name', "Anonymous")
    text = "Hello, " + name
    return web.Response(text=text)
async def test(app):
	while True:
		await asyncio.sleep(5)
		print('Test')
async def test_handler(app):
	app.loop.create_task(test(app))

async def get_wallet(request):
	return  web.json_response({})
async def change_threshold(request):
	# ok_buy=request.match_info['okbuy']
	# poloniex_buy=request.match_info['poloniexbuy']
	body = await request.json()
	print(request.transport.get_extra_info('peername'))
	print('{!r}'.format(body))
	return  web.json_response({})

app = web.Application()
app.router.add_get('/wallet', get_wallet)
app.router.add_post('/update', change_threshold)
app.on_startup.append(test_handler)
# print('here')
web.run_app(app)
