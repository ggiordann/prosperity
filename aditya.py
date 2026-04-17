import requests
import json

def retrieve_messages(channel_id):
    headers = {
        'authorization': 'a',
        'User-Agent': 'Mozilla/5.0 (compatible; MyApp/1.0)'
    }
    url = f'https://discord.com/api/v10/channels/{channel_id}/messages?limit=100'
    r = requests.get(url, headers=headers)
    # print(f"Status: {r.status_code}, Response: {r.text}") ---> big ass block
    if r.status_code == 200:
        jsonn = r.json()
        for msg in jsonn:
            print(f"{msg['author']['username']}: {msg['content']}", '\n')

retrieve_messages('1476867246000177162')

# prosperity discord channel ID's

# general: 1476867246000177162
# algo-trading: 1476867343068958781
# manual-trading: 1476867369186885653
# programming: 1476867406906527784
# find-teammates: 1476867465601355851
# bugs: 1476867431615168634
# announcements: 1476867503652208680
# open-source: 1476867549181513851