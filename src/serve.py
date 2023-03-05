# dummy web server to keep repl alive with uptimerobot pings

from flask import Flask
from threading import Thread
app = Flask('')

@app.route('/')
def home():
    return "Running..."

def run():
  app.run(host='0.0.0.0',port=8080)

def serve():
    t = Thread(target=run)
    t.start()