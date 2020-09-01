import email
import imaplib
import json
from slack import WebClient
from slack.errors import SlackApiError

with open('/var/openfaas/secrets/imap-server') as secrets_file:
    imap_server = secrets_file.read().replace('\n', '')

with open('/var/openfaas/secrets/email-account') as secrets_file:
    email_account = secrets_file.read().replace('\n', '')

with open('/var/openfaas/secrets/email-password') as secrets_file:
    email_password = secrets_file.read().replace('\n', '')

with open('/var/openfaas/secrets/slack-bot-token') as secrets_file:
    slack_token = secrets_file.read().replace('\n', '')

slack_client = WebClient(token=slack_token)


def handle(event, context):
    data = get_unread_emails(email_account, email_password, imap_server)
    json_array = build_json_array(data)
    response = send_to_slack(json_array)
    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": "application/json"
        },
        "body": response
    }


def get_unread_emails(username, password, server):
    # create an IMAP4 class with SSL
    imap = imaplib.IMAP4_SSL(server)
    # authenticate
    imap.login(username, password)
    imap.select('INBOX')

    status, response = imap.uid('search', None, 'UNSEEN')
    if status == 'OK':
        unread_msg_nums = response[0].split()
    else:
        unread_msg_nums = []

    data_list = []

    for e_id in unread_msg_nums:
        data_dict = {}
        e_id = e_id.decode('utf-8')
        _, response = imap.uid('fetch', e_id, '(RFC822)')
        html = response[0][1].decode('utf-8')
        msg = email.message_from_string(html)
        data_dict['mail_subject'] = msg['Subject']
        data_dict['mail_from'] = email.utils.parseaddr(msg['From'])
        # data_dict['mail_from'] = msg.get("From")

        # if the email message is multipart
        if msg.is_multipart():
            # iterate over email parts
            for part in msg.walk():
                # extract content type of email
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition"))
                try:
                    # get the email body
                    body = part.get_payload(decode=True).decode()
                except:
                    pass
                if content_type == "text/plain" and "attachment" not in content_disposition:
                    # print text/plain emails and skip attachments
                    data_dict['body'] = body
        else:
            # extract content type of email
            content_type = msg.get_content_type()
            # get the email body
            body = msg.get_payload(decode=True).decode()
            if content_type == "text/plain" or content_type == "text/html":
                # print only text email parts
                data_dict['body'] = body

        data_list.append(data_dict)

    imap.close()
    imap.logout()
    return data_list


def build_json_array(data):
    response = []
    for msg in data:
        obj = {
            'Subject': msg['mail_subject'],
            'From': {
                'Name': msg['mail_from'][0],
                'Address': msg['mail_from'][1]
            },
            'Body': msg['body'],
        }
        response.append(obj)
    return json.dumps(response)


def send_to_slack(json_array):
    data = json.loads(json_array)
    for email_message in data:
        try:
            response = slack_client.chat_postMessage(
                channel='#hack-time',
                blocks=[
                    {
                        "type": "header",
                        "text": {
                            "type": "plain_text",
                            "text": ":mailbox_with_mail: Emailed message",
                            "emoji": True
                        }
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"*From*: <mailto:{email_message['From']['Address']}|{email_message['From']['Name']}>"
                        }
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"*Subject*: {email_message['Subject']}"
                        }
                    },
                    {
                        "type": "divider"
                    },
                    {
                        "type": "context",
                        "elements": [
                            {
                                "type": "plain_text",
                                "text": ":point_down: Message content in reply",
                                "emoji": True
                            }
                        ]
                    }
                ])

            slack_client.chat_postMessage(
                channel='#hack-time',
                thread_ts=response['ts'],
                # icon_emoji=':robot_face:',
                blocks=[
                    {
                        "type": "header",
                        "text": {
                            "type": "plain_text",
                            "text": ":page_facing_up: Message content",
                            "emoji": True
                        }
                    },
                    {
                        "type": "divider"
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": email_message['Body']
                        }
                    }
                ])

        except SlackApiError as e:
            # You will get a SlackApiError if "ok" is False
            assert e.response["error"]  # str like 'invalid_auth', 'channel_not_found'
    count = len(data)
    if count > 0:
        return str(count) + ' email(s) forwareded to Slack.'
    else:
        return ''
