import emoji_data_python
import json
import logging
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
        res = process_incoming_slack(event.body)
        return res
    elif event.method == 'POST' and event.path == '/incoming/twilio':
        res = send_sms_to_slack(event.body)
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


def send_sms_to_slack(body):
    data = urllib.parse.parse_qs(str(body))
    from_number = data['From'][0]
    sms_message = data['Body'][0]
    try:
        slack_client.chat_postMessage(
            channel='#hack-time',
            # channel='#q-and-a',
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
        # str like 'invalid_auth', 'channel_not_found'
        assert e.response["error"]
        response_to_twilio = MessagingResponse()
        return {
            "statusCode": 500,
            "headers": {
                "Content-Type": "text/html"
            },
            "body": response_to_twilio.to_xml()
        }


def process_incoming_slack(body):
    data = json.loads(body)
    if 'challenge' in data:
        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "text/plain",
            },
            "body": str(data['challenge'])
        }

    incoming_slack_message_id, slack_message, channel = parse_message(
        data)

    if incoming_slack_message_id and slack_message:
        destination = get_to_destination(incoming_slack_message_id, channel)
        formatted_body = emoji_data_python.replace_colons(slack_message)

        if destination and destination['type'] == 'phone_number':
            twilio_client.messages.create(
                to=destination['number'],
                from_=twilio_number,
                body=formatted_body)
        elif destination and destination['type'] == 'email_address':
            logging.warning('An email would have been sent' +
                            destination['address'])
        return {"statusCode": 200}
    return {"statusCode": 200}


def parse_message(data):
    if 'event' in data and 'thread_ts' in data['event']:
        ts = data['event']['thread_ts']
        text = data['event']['text']
        channel = data['event']['channel']
        return ts, text, channel
    return None, None, None


def get_to_destination(incoming_slack_message_id, channel):
    data = slack_client.conversations_history(
        channel=channel, latest=incoming_slack_message_id, limit=1, inclusive=1)
    logging.warning(json.dumps(data['messages'][0]))

    msg = data['messages'][0]
    txt = data['messages'][0]['blocks'][0]['text']['text']
    if 'bot_id' in msg and txt == ':phone: Text message':
        text = data['messages'][0]['blocks'][1]['text']['text']
        logging.warning('text: ' + text)
        phone_number = extract_phone_number(text)
        return phone_number
    elif 'bot_id' in msg and txt == ':mailbox_with_mail: Emailed message':
        text = data['messages'][0]['blocks'][1]['text']['text']
        logging.warning('text: ' + text)
        email_address = extract_email_address(text)
        return email_address
    return None


def extract_phone_number(text):
    # *From*: +15556667777
    data = text.split(' ')
    if data[1].startswith('+'):
        num = data[1].replace('+', '')
        if num.isnumeric() and len(num) >= 11:
            return {
                'type': 'phone_number',
                'number': data[1]
            }
    return None


def extract_email_address(text):
    # *From*: <mailto:jdoe@example.com|Jane Doe>
    if 'mailto' in text:
        address = text.split(':')[2].split('|')[0]
        if len(address) > 4:
            return {
                'type': 'email_address',
                'address': address
            }
    return None
