import json
import datetime
import time
import os
import dateutil.parser
import logging
import boto3
import re

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)


# --- Helpers that build all of the responses ---


def elicit_slot(session_attributes, intent_name, slots, slot_to_elicit, message):
    return {
        'sessionAttributes': session_attributes,
        'dialogAction': {
            'type': 'ElicitSlot',
            'intentName': intent_name,
            'slots': slots,
            'slotToElicit': slot_to_elicit,
            'message': message
        }
    }


def confirm_intent(session_attributes, intent_name, slots, message):
    return {
        'sessionAttributes': session_attributes,
        'dialogAction': {
            'type': 'ConfirmIntent',
            'intentName': intent_name,
            'slots': slots,
            'message': message
        }
    }


def close(session_attributes, fulfillment_state, message):
    response = {
        'sessionAttributes': session_attributes,
        'dialogAction': {
            'type': 'Close',
            'fulfillmentState': fulfillment_state,
            'message': message
        }
    }

    return response


def delegate(session_attributes, slots):
    return {
        'sessionAttributes': session_attributes,
        'dialogAction': {
            'type': 'Delegate',
            'slots': slots
        }
    }


# --- Helper Functions ---


def safe_int(n):
    """
    Safely convert n value to int.
    """
    if n is not None:
        return int(n)
    return n


def try_ex(func):
    """
    Call passed in function in try block. If KeyError is encountered return None.
    This function is intended to be used to safely access dictionary.

    Note that this function would have negative impact on performance.
    """

    try:
        return func()
    except KeyError:
        return None


def isvalid_city(city):
    valid_cities = ['manhattan', 'bronx', 'brooklyn', 'queens', 'staten island']
    return city.lower() in valid_cities


def isvalid_cuisine(cuisine):
    valid_cuisines = ['chinese', 'indian', 'american', 'italian', 'mexican', 'korean']
    return cuisine.lower() in valid_cuisines


def isvalid_phone(phone):
    return re.match(r"^([+][1][0-9]{10}|[0-9]{10})$", phone)


def build_validation_result(isvalid, violated_slot, message_content):
    return {
        'isValid': isvalid,
        'violatedSlot': violated_slot,
        'message': {'contentType': 'PlainText', 'content': message_content}
    }


def validate_restaurant(slots):

    location = try_ex(lambda: slots['Location'])
    cuisine = try_ex(lambda: slots['Cuisine'])
    guests = safe_int(try_ex(lambda: slots['Guests']))
    phone = try_ex(lambda: slots['Phone'])

    if location and not isvalid_city(location):
        return build_validation_result(
            False,
            'Location',
            'We currently do not support {} as a valid destination.  Can you try a different city?'.format(location)
        )

    if cuisine and not isvalid_cuisine(cuisine):
        return build_validation_result(
            False,
            'Cuisine',
            'We currently can only recommend Chinese, Indian, Mexican, Korean, American, and Italian food. Can you try a different cuisine type?'
        )

    if guests and guests <= 0:
        return build_validation_result(
            False,
            'Guests',
            "We can't do a non positive number of guests you #$%$#!"
        )

    if phone and not isvalid_phone(phone):
        return build_validation_result(
            False,
            'Phone',
            "That's not a real phone number you #$%$^&!"
        )
    return {'isValid': True}


""" --- Functions that control the bot's behavior --- """
def suggest_restaurant(intent_request):
    """
    Performs dialog management.

    Beyond fulfillment, the implementation for this intent demonstrates the following:
    1) Use of elicitSlot in slot validation and re-prompting
    2) Use of sessionAttributes to pass information that can be used to guide conversation
    """

    location = try_ex(lambda: intent_request['currentIntent']['slots']['Location'])
    cuisine = try_ex(lambda: intent_request['currentIntent']['slots']['Cuisine'])
    time = try_ex(lambda: intent_request['currentIntent']['slots']['Time'])
    guests = safe_int(try_ex(lambda: intent_request['currentIntent']['slots']['Guests']))
    phone = try_ex(lambda: intent_request['currentIntent']['slots']['Phone'])
    session_attributes = intent_request['sessionAttributes'] if intent_request['sessionAttributes'] is not None else {}


    if intent_request['invocationSource'] == 'DialogCodeHook':
        # Validate any slots which have been specified.  If any are invalid, re-elicit for their value
        validation_result = validate_restaurant(intent_request['currentIntent']['slots'])
        if not validation_result['isValid']:
            slots = intent_request['currentIntent']['slots']
            slots[validation_result['violatedSlot']] = None

            return elicit_slot(
                session_attributes,
                intent_request['currentIntent']['name'],
                slots,
                validation_result['violatedSlot'],
                validation_result['message']
            )

        return delegate(session_attributes, intent_request['currentIntent']['slots'])

    if not phone.startswith('+'):
        phone = "+1" + phone

    cuisine = cuisine.capitalize()

    # Create SQS client
    sqs = boto3.client('sqs')
    queue_url = ''  # SQS QUEUE URL

    # Send message to SQS queue
    response = sqs.send_message(
        QueueUrl=queue_url,
        DelaySeconds=10,
        MessageAttributes={
            'Location': {
                'DataType': 'String',
                'StringValue': location
            },
            'Cuisine': {
                'DataType': 'String',
                'StringValue': cuisine
            },
            'Phone': {
                'DataType': 'String',
                'StringValue': phone
            }
        },
        MessageBody=(
            'Recommendation Request'
        )
    )

    return close(
        session_attributes,
        'Fulfilled',
        {
            'contentType': 'PlainText',
            'content': "We will send your recommendation in a bit! Is there anything else you'd like me to do?"
        }
    )


# --- Intents ---


def dispatch(intent_request):
    """
    Called when the user specifies an intent for this bot.
    """

    logger.debug('dispatch userId={}, intentName={}'.format(intent_request['userId'], intent_request['currentIntent']['name']))

    intent_name = intent_request['currentIntent']['name']

    # Dispatch to your bot's intent handlers
    if intent_name == 'BookHotel':
        return suggest_restaurant(intent_request)

    raise Exception('Intent with name ' + intent_name + ' not supported')


# --- Main handler ---


def lambda_handler(event, context):
    """
    Route the incoming request based on intent.
    The JSON body of the request is provided in the event slot.
    """
    # By default, treat the user request as coming from the America/New_York time zone.
    os.environ['TZ'] = 'America/New_York'
    time.tzset()
    logger.debug('event.bot.name={}'.format(event['bot']['name']))

    return dispatch(event)
