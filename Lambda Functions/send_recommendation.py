import logging
import random

import boto3
from boto3.dynamodb.conditions import Key
from elasticsearch import Elasticsearch, RequestsHttpConnection
from requests_aws4auth import AWS4Auth

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)


def elastic_search(cuisine):
    # Search in Elasticsearch, return one business ID at random from all restaurants that fit the criteria
    credentials = boto3.Session().get_credentials()
    region = 'us-east-2'
    service = 'es'
    awsauth = AWS4Auth(credentials.access_key, credentials.secret_key, region, service, session_token=credentials.token)

    host = ''  # Elasticsearch URL
    es = Elasticsearch(hosts=[{"host": host, 'port': 443}],
                       http_auth=awsauth,
                       use_ssl=True,
                       verify_certs=True,
                       connection_class=RequestsHttpConnection)
    res = es.search(index="restaurants",
                    body={"query": {"match": {"cuisine": cuisine}}})

    try:
        raw_result = res["hits"]["hits"]
        print(raw_result)
    except KeyError:
        print("Not found in Elasticsearch")

    results = []
    for r in raw_result:
        results.append(r["_source"]["business_id"])

    business_id = random.choice(results)
    return business_id


def retrieve_from_dynamo(business_id, cuisine):
    dynamodb = boto3.resource('dynamodb', region_name='us-east-2')
    restaurants_table = dynamodb.Table('yelp-restaurants')
    result = restaurants_table.query(KeyConditionExpression=Key('business_id').eq(business_id))
    text_body = 'Here are my suggestions for {cuisine} food: \n'.format(cuisine=cuisine)

    for r in result['Items']:
        name = r['name']
        cuisine = r['cuisine']
        address = r['address']
        no_of_reviews = r['no_of_reviews']
        rating = r['rating']
        zip_code = r['zip_code']

        restaurant_info = "Name: {}\nCuisine: {}\nAddress: {}\nReviews: {}\nRating: {}\nZip-Code: {}" \
            .format(name, cuisine, address, no_of_reviews, rating, zip_code)
        text_body += restaurant_info
    return text_body


def send_message(text_body, phone_number):
    messaging_client = boto3.client('sns')
    response = messaging_client.publish(
        PhoneNumber=phone_number,
        Message=text_body,
        MessageStructure='string',
    )

    logger.debug("Message '%s' sent to %s" % (response, phone_number))

    return response


def extract_from_sqs():
    cuisine = None
    phone_number = None

    sqs = boto3.client('sqs')
    queue_url = ''   # SQS QUEUE URL
    response = sqs.receive_message(
        QueueUrl=queue_url,
        AttributeNames=[
            'SentTimestamp'
        ],
        MaxNumberOfMessages=1,
        MessageAttributeNames=[
            'All'
        ],
        VisibilityTimeout=0,
        WaitTimeSeconds=0
    )

    try:
        message = response['Messages'][0]
        receipt_handle = message['ReceiptHandle']
        sqs.delete_message(
            QueueUrl=queue_url,
            ReceiptHandle=receipt_handle
        )
        logger.debug('Received and deleted message: %s' % message)
    except KeyError:
        logger.debug("No message in SQS queue")
        return cuisine, phone_number

    if message is None:
        logger.debug("Message is empty")
        return cuisine, phone_number

    try:
        cuisine = message["MessageAttributes"]["Cuisine"]["StringValue"]
        phone_number = message["MessageAttributes"]["Phone"]["StringValue"]
    except KeyError:
        logger.debug("Missing fields in SQS message")
        return cuisine, phone_number

    return cuisine, phone_number


def lambda_handler(event, context):
    cuisine, phone_number = extract_from_sqs()

    

    if not cuisine or not phone_number:
        return
    
    cuisine = cuisine.capitalize()
    business_id = elastic_search(cuisine)

    text_body = retrieve_from_dynamo(business_id, cuisine)

    send_message(text_body, phone_number)
    return
