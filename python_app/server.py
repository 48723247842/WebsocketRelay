import os
import redis
import json
import time

import asyncio
import uvloop
from pprint import pprint
import requests

from sanic import Sanic
from sanic.response import json as sanic_json
from sanic.response import file
from sanic import response
from sanic.websocket import ConnectionClosed

# https://github.com/huge-success/sanic/tree/master/examples
# https://github.com/huge-success/sanic/blob/master/examples/try_everything.py

# https://sanic.readthedocs.io/en/latest/sanic/blueprints.html

app = Sanic( name="Websocket Relay Server!" )

app.ws_clients = set()
asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

@app.route( "/" )
def hello( request ):
	return response.text( "You Found the Website Controller Server!\n" )

@app.route( "/ping" )
def ping( request ):
	return response.text( "pong\n" )

def ws_remove_closed_clients():
	try:
		clients = app.ws_clients
		closed_clients = []
		for index , client in enumerate( clients ):
			if str( client.state ) != "State.OPEN":
				closed_clients.append( client )
		#print( f'{ len( app.ws_clients ) } clients' )
		for index , client in enumerate( closed_clients ):
			#print( "Removing Closed WS Client" )
			#pprint( vars( client ) )
			app.ws_clients.remove( client )
	except Exception as e:
		print( e )
		return False

# https://stackoverflow.com/a/48614946
async def ws_broadcast(message):
	ws_remove_closed_clients()
	broadcasts = [ ws.send( message ) for ws in app.ws_clients ]
	for result in asyncio.as_completed(broadcasts):
		try:
			await result
		except ConnectionClosed:
			print("ConnectionClosed")
		except Exception as ex:
			template = "An exception of type {0} occurred. Arguments:\n{1!r}"
			message = template.format(type(ex).__name__, ex.args)
			print( message )

@app.websocket( "/ws" )
async def websocket( request , ws ):
	app.ws_clients.add( ws )
	await ws.send( json.dumps( { "message": "pong" } ) )
	while True:
		data = await ws.recv()
		print( 'Received: ' + data )
		ws_remove_closed_clients()
		try:
			data = json.loads( data )
			if "channel" in data:
				if data["channel"] == "disney_plus":
					post_result = requests.post( "http://127.0.0.1:11401/api/disney/ws/consumer" , data=data )
					post_result.raise_for_status()
					post_result = post_result.json()
					print( post_result )
		except Exception as e:
			print( e )

@app.route( "/broadcast" , methods=[ "POST" ] )
def broadcast( request ):
	result = { "message": "failed" }
	try:
		message = request.json.get( "json" )
		ws_broadcast( message )
		time.sleep( 1 )
		result["status"] = ""
		result["message"] = "success"
	except Exception as e:
		print( e )
		result["error"] = str( e )
	return json_result( result )

def redis_connect():
	try:
		redis_connection = redis.StrictRedis(
			host="127.0.0.1" ,
			port="6379" ,
			db=1 ,
			#password=ConfigDataBase.self[ 'redis' ][ 'password' ]
			)
		return redis_connection
	except Exception as e:
		return False

def get_config( redis_connection ):
	try:
		try:
			config = redis_connection.get( "CONFIG.WEBSOCKET_RELAY_SERVER" )
			config = json.loads( config )
			return config
		except Exception as e:
			try:
				config_path = os.path.join( os.path.dirname( os.path.abspath( __file__ ) ) , "config.json" )
				with open( config_path ) as f:
					config = json.load( f )
				redis_connection.set( "CONFIG.WEBSOCKET_RELAY_SERVER" , json.dumps( config ) )
				return config
			except Exception as e:
				config = {
					"port": 10081 ,
				}
				redis_connection.set( "CONFIG.WEBSOCKET_RELAY_SERVER" , json.dumps( config ) )
				return config
	except Exception as e:
		print( "Could't Get Config for Websocket Relay Server" )
		print( e )
		return False

def run_server():
	try:
		redis_connection = redis_connect()
		if redis_connection == False:
			return False
		config = get_config( redis_connection )
		if config == False:
			return False

		host = '0.0.0.0'
		port = config[ 'port' ]
		app.run( host=host , port=port , workers=1 , debug=False )

	except Exception as e:
		print( "Couldn't Start Websocket Relay Server" )
		print( e )
		return False

def try_run_block( options ):
	for i in range( options[ 'number_of_tries' ] ):
		attempt = options[ 'function_reference' ]()
		if attempt is not False:
			return attempt
		print( f"Couldn't Run '{ options[ 'task_name' ] }', Sleeping for { str( options[ 'sleep_inbetween_seconds' ] ) } Seconds" )
		time.sleep( options[ 'sleep_inbetween_seconds' ] )
	if options[ 'reboot_on_failure' ] == True:
		os.system( "reboot -f" )

try_run_block({
	"task_name": "Websocket Relay Server" ,
	"number_of_tries": 5 ,
	"sleep_inbetween_seconds": 5 ,
	"function_reference": run_server ,
	"reboot_on_failure": True
	})