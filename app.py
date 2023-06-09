from __future__ import unicode_literals
import string
from flask import Flask, request, abort, render_template
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import *
import requests
import re
import json
import configparser
import os
from urllib import parse
import string
import pymysql
import pandas as pd
import openpyxl
from googlemaps import Client
from function import *
from database import deposit,withdraw, check_balance

app = Flask(__name__, static_url_path='/static')
UPLOAD_FOLDER = 'static'
ALLOWED_EXTENSIONS = set(['pdf', 'png', 'jpg', 'jpeg', 'gif'])

config = configparser.ConfigParser() #讀取config檔案
config.read('config.ini')

line_bot_api = LineBotApi(config.get('line-bot', 'channel_access_token'))
handler = WebhookHandler(config.get('line-bot', 'channel_secret'))
# my_line_id = config.get('line-bot', 'my_line_id')
# end_point = config.get('line-bot', 'end_point')
# line_login_id = config.get('line-bot', 'line_login_id')
# line_login_secret = config.get('line-bot', 'line_login_secret')
# my_phone = config.get('line-bot', 'my_phone')
google_map_key = config.get('line-bot', 'google_map_key')
# google_map_url = config.get('line-bot', 'google_map_url')
# id_file_name = './recommendation/id_list.xlsx' # File name
# sheet_name = 'worksheet1' # 4th sheet
# sheet_header = 0 # The header is the 2nd row
gmaps = Client(key=google_map_key)


#http的HEADER
HEADER = {  
    'Content-type': 'application/json',
    'Authorization': F'Bearer {config.get("line-bot", "channel_access_token")}'
}
state, account, stime, etime, customer_list = {}, None , None, None, []
@app.route("/", methods=['POST', 'GET'])
def index():
    # state = None
    global customer_list
    if request.method == 'GET':
        return 'ok'
    body = request.json
    events = body["events"]
    if request.method == 'POST' and len(events) == 0:
        return 'ok'
    print(body)
    if "replyToken" in events[0]:
        payload = dict()
        replyToken = events[0]["replyToken"]
        payload["replyToken"] = replyToken
        userid = events[0]["source"]["userId"]
        payload["to"] = userid
        if events[0]["type"] == "message":
            
            # 處理文字訊息
            if events[0]["message"]["type"] == "text":
                text = events[0]["message"]["text"]

                if text == "匯率查詢":
                    state[userid] = {"status": "getdollar"}
                    payload["messages"] = [get_dollar_name()]
                elif state.get(userid) and state[userid]["status"] == "getdollar":
                    payload["messages"] = [get_dollar(text)]
                    del state[userid]
                elif text == "天氣查詢":
                    state[userid] = {"status": "getweather"}
                    payload["messages"] = [{"type": "text","text": "請輸入要查詢的縣市名稱 (ex.臺北市):"}]
                elif state.get(userid) and state[userid]["status"] == "getweather":
                    payload["messages"] = [get_weather(text)]
                    del state[userid]
                elif text == "我的功能":
                     payload["messages"] = [store_information()]
                elif text == "股價查詢":
                    state[userid] = {"status": "getstock"}
                    payload["messages"] = [{"type": "text","text": "請輸入要查詢的股票代號 (ex.2330):"}]
                elif state.get(userid) and state[userid]["status"] == "getstock":
                    payload["messages"] = [get_stock(text)]
                    del state[userid]

                elif text == "記帳":
                    state[userid] = {"status": "bookkeeping"}
                    payload["messages"] = [{"type": "text","text": "請輸入要執行的動作 (查詢餘額、提款、存款):"}]
                elif state.get(userid) and state[userid]["status"] == "bookkeeping":
                    if text == "查詢餘額":
                        payload["messages"] = [{"type": "text", "text": "請輸入要查詢的帳戶 :"}]
                        state[userid]["status"] = "check_balance"
                    elif text == "提款":
                        payload["messages"] = [{"type": "text", "text": "請輸入要提款的帳戶 :"}]
                        state[userid]["status"] = "withdraw"
                    elif text == "存款":
                        payload["messages"] = [{"type": "text", "text": "請輸入要存入的帳戶 :"}]
                        state[userid]["status"] = "addmoney"

                elif state.get(userid) and state[userid]["status"] == "withdraw":
                    account = text
                    state[userid]["account"] = account
                    payload["messages"] = [{"type": "text", "text": "請輸入提款金額 :"}]
                    state[userid]["status"] = "withdraw_amount"
                elif state.get(userid) and state[userid]["status"] == "withdraw_amount":
                    amount = float(text)
                    account = state[userid]["account"]
                    result = withdraw(account, amount)
                    payload["messages"] = [{"type": "text", "text": result}]
                    del state[userid]
                elif state.get(userid) and state[userid]["status"] == "check_balance":
                    account = text
                    result = check_balance(account)
                    payload["messages"] = [{"type": "text", "text": result}]
                    del state[userid]
                elif state.get(userid) and state[userid]["status"] == "addmoney":
                    account = text
                    state[userid]["account"] = account
                    payload["messages"] = [{"type": "text", "text": "請輸入要存入金額 :"}]
                    state[userid]["status"] = "addmoney_amount"
                elif state.get(userid) and state[userid]["status"] == "addmoney_amount":
                    amount = float(text)
                    account = state[userid]["account"]
                    result = deposit(account, amount)
                    payload["messages"] = [{"type": "text", "text": result}]
                    del state[userid]
                    
                replyMessage(payload)
            
            # 處理座標訊息
            elif events[0]["message"]["type"] == "location":
                latitude = events[0]["message"]["latitude"]
                longitude = events[0]["message"]["longitude"]
                payload["messages"] = [get_parking_lots(latitude, longitude)]
                replyMessage(payload)
        
        elif events[0]["type"] == "postback":
            if events[0]["postback"]["data"] == "store_info":
                payload["messages"] = [store_information()]
            elif events[0]["postback"]["data"] == "search":
                payload["messages"] = [customer()]
            elif "params" in events[0]["postback"]:
                reservedTime = events[0]["postback"]["params"]["datetime"].replace("T", " ")
                payload["messages"] = [
                        {
                            "type": "text",
                            "text": F"已完成預約於{reservedTime}的訂位服務 請輸入日期"
                        }
                    ]
                replyMessage(payload)
            else:
                data = json.loads(events[0]["postback"]["data"])
                action = data["action"]
                if action == "get_near":
                    data["action"] = "get_detail"
                    payload["messages"] = [getCarouselMessage(data)]
                elif action == "get_detail":
                    del data["action"]
                    payload["messages"] = [function_one()]
                replyMessage(payload)

    return 'OK'

def replyMessage(payload):
    print(payload)
    response = requests.post("https://api.line.me/v2/bot/message/reply",headers=HEADER,json=payload)
    print(response.text)
    return 'OK'
def pushMessage(payload):
    print(payload)
    response = requests.post("https://api.line.me/v2/bot/message/push",headers=HEADER,json=payload)
    print(response.text)
    return 'OK'

def get_navigation(latitude, longitude):
    # 目標地址，這裡可以自己設定
    target_address = "新北市板橋區雙十路二段130巷2弄80號"

    # 使用 Google Maps Platform 的 Geocoding API 將目標地址轉換為座標
    target_location = gmaps.geocode(target_address)[0]['geometry']['location']
    target_latitude = target_location['lat']
    target_longitude = target_location['lng']

    # 使用 Google Maps Platform 的 Distance Matrix API 計算當前使用者座標和目標座標之間的距離和時間
    directions_result = gmaps.directions(
        (latitude, longitude),
        (target_latitude, target_longitude),
        mode="driving",
        language="zh-TW"
    )
    # 獲取路線總長度和總時間
    distance_km = directions_result[0]['legs'][0]['distance']['text']
    duration_min = directions_result[0]['legs'][0]['duration']['text']

    # 取得導航連結
    navi_link = f"https://www.google.com/maps/dir/?api=1&destination={target_address}"

    # 回傳導航訊息
    message = {
        "type": "text",
        "text": f"請點擊以下連結開啟 Google 導航：\n{navi_link}\n預計距離：{distance_km}，預計行車時間：{duration_min}"
    }
    return message

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature'] #在request.headers拿到X-Line-Signature
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)

    try:
        handler.handle(body, signature)

    except InvalidSignatureError:
        abort(400)

    return 'OK'

if __name__ == "__main__":
    app.debug = True
    app.run()