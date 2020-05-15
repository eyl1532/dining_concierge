import json
import boto3
import datetime

def handler(event, context):
    client = boto3.client('lex-runtime')
    
    text = event["messages"][0]["unstructured"]["text"]
    
    response = client.post_text(
        botName = 'OrderFlowers',
        botAlias = '$LATEST',
        userId = 'LF0',
        sessionAttributes={},
        requestAttributes={},
        inputText= text
        #event['text']
        )
    return { 
        "messages": [
            {
            "type": "string",
            "unstructured": {
            "id":"200" ,
            "text": response['message'],
            "timestamp": datetime.datetime.now().isoformat()
                }
            }
        ]
    }         
    