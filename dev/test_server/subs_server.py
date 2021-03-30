from aiohttp import web


app = web.Application()
app.add_routes([web.static("/", "subs")])

web.run_app(app, host="localhost", port=8081)
