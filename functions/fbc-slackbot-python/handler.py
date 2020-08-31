import emoji_data_python
import json
import logging
import re
import urllib.parse
from slack import WebClient
from slack.errors import SlackApiError
from twilio.rest import Client
from twilio.twiml.messaging_response import MessagingResponse

with open('/var/openfaas/secrets/slack-bot-token') as secrets_file:
    slack_token = secrets_file.read().replace('\n', '')

slack_client = WebClient(slack_token)

with open('/var/openfaas/secrets/twilio-account-sid') as secrets_file:
    twilio_account_sid = secrets_file.read().replace('\n', '')

with open('/var/openfaas/secrets/twilio-auth-token') as secrets_file:
    twilio_auth_token = secrets_file.read().replace('\n', '')

twilio_client = Client(twilio_account_sid, twilio_auth_token)

with open('/var/openfaas/secrets/twilio-number') as secrets_file:
    twilio_number = secrets_file.read().replace('\n', '')


def handle(event, context):
    if event.method == 'POST' and event.path == '/incoming/slack':
        res = incoming_slack(event.body)
        return res
    elif event.method == 'POST' and event.path == '/incoming/twilio':
        res = send_to_slack(event.body)
        return res
    elif event.method == 'POST':
        return {
            "statusCode": 404,
            "body": str(event.path) + " was not found"
        }
    else:
        return {
            "statusCode": 405,
            "body": "Method not allowed"
        }


def send_to_slack(body):
    data = urllib.parse.parse_qs(str(body))
    from_number = data['From'][0]
    sms_message = data['Body'][0]
    try:
        slack_client.chat_postMessage(
            channel='#q-and-a',
            blocks=[
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": ":phone: Text message",
                        "emoji": True
                    }
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*From*: {from_number}"
                    }
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": sms_message
                    }
                }
            ])
        response_to_twilio = MessagingResponse()
        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "text/html"
            },
            "body": response_to_twilio.to_xml()
        }
    except SlackApiError as e:
        # You will get a SlackApiError if "ok" is False
        assert e.response["error"]  # str like 'invalid_auth', 'channel_not_found'
        response_to_twilio = MessagingResponse()
        return {
            "statusCode": 500,
            "headers": {
                "Content-Type": "text/html"
            },
            "body": response_to_twilio.to_xml()
        }


def incoming_slack(body):
    attributes = json.loads(body)
    if 'challenge' in attributes:
        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "text/plain",
            },
            "body": str(attributes['challenge'])
        }
    incoming_slack_message_id, slack_message, channel = parse_message(
        attributes)
    if incoming_slack_message_id and slack_message:
        to_number = get_to_number(incoming_slack_message_id, channel)
        formatted_body = emoji_data_python.replace_colons(slack_message)
        if to_number:
            twilio_client.messages.create(
                to=to_number, from_=twilio_number, body=formatted_body)
        return {"statusCode": 200}
    return {"statusCode": 200}


def parse_message(attributes):
    if 'event' in attributes and 'thread_ts' in attributes['event']:
        return attributes['event']['thread_ts'], attributes['event']['text'], attributes['event']['channel']
    return None, None, None


def get_to_number(incoming_slack_message_id, channel):
    data = slack_client.conversations_history(
        channel=channel, latest=incoming_slack_message_id, limit=1, inclusive=1)
    logging.warning(json.dumps(data['messages'][0]))
    if 'bot_id' in data['messages'][0] and data['messages'][0]['blocks'][0]['text']['text'] == ':phone: Text message':
        text = data['messages'][0]['blocks'][1]['text']['text']
        logging.warning('text: ' + text)
        phone_number = extract_phone_number(text)
        return phone_number
    return None


def extract_phone_number(text):
    data = re.findall(r'\w+', text)
    if len(data) == 2:
        return data[1]
    return None
