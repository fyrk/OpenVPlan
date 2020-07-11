from datetime import datetime

from aiohttp import web
import asyncio
import logging

logger = logging.getLogger(__name__)

async def hello(request):
    logger.info('Started processing request')
    t = str(datetime.now().isoformat())
    await asyncio.sleep(5)
    logger.info('Doing something')
    await asyncio.sleep(5)
    return web.Response(text=t)

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s %(name)-14s %(levelname)s: %(message)s')

app = web.Application()
app.add_routes([web.get('/', hello)])
web.run_app(app)
