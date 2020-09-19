# FBC Slackbot

This repository contains everything needed to deploy a Slackbot on Digital Ocean with Terraform that runs in [faasd](https://github.com/openfaas/faasd). The bot was initially created to facilitate remote question and answer sessions at my church by allowing viewers of our live stream to text or email questions in, have a staff member ask their question in the room, and then allow the staff member to send a response back to the sender. The texting is facilitated by Twilio while the email is done by interacting with a Gmail account via IMAP and SMTP.

- [Architecture](#architecture)
  - [Text messages](#text-messages)
  - [Email](#email)
- [System requirements](#system-requirements)
- [Deployment](#deployment)
  - [Deployment of faasd](#deployment-of-faasd)
  - [Twilio configuration](#twilio-configuration)
  - [q-and-a channel](#q-and-a-channel)
  - [Slack app, part 1](#slack-app-part-1)
  - [Configure Gmail](#configure-gmail)
  - [Deploying needed secrets](#deploying-needed-secrets)
  - [Deploying the functions](#deploying-the-functions)
  - [Slack app, part 2](#slack-app-part-2)
  - [Checking for emails](#checking-for-emails)
- [Try it out](#try-it-out)
- [Limitations](#limitations)
- [Planned Improvements](#planned-improvements)
- [Credit](#credit)

## Architecture

There are two ways in which data flows through this system. 

### Text messages

1. Person with question sends a text message
2. Twilio receives the text message
3. Twilio sends the message's content via a webhook
4. the Slackbot function receives the webhook
5. the Slackbot function sends a formatted message to the q-and-a Slack channel
6. a staff member asks the person's question
7. a staff member sends the response via a threaded reply in Slack
8. the Slackbot function observes the Slack reply event
9. the Slackbot function determines the original message was submitted via text
10. the Slackbot function converts Slack emoji into standard emoji
11. the Slackbot function sends the parsed response to Twilio's API
12. Twilio delivers the response via text to the person who asked it

### Email

1. Person with question sends an email
2. Gmail receives the email message
3. the email to Slack function checks for new messages and finds the emailed question
4. the email to Slack function sends a formatted message to the q-and-a Slack channel
5. a staff member asks the person's question
6. a staff member sends the response via a threaded reply in Slack
7. the Slackbot function observes the Slack reply event
8. the Slackbot function determines the original message was submitted via email
9. the Slackbot function converts Slack emoji into standard emoji
10. the Slackbot function formats the response into an email to the person who asked it
11. the Slackbot function sends the email via Gmail's SMTP server
12. the Slackbot function copies the email into Gmail's sent folder and marks it read

This process is facilitated by the email to Slack function being triggered once a minute via cron.

## System requirements

To use this setup you will need the following:

- A [Digital Ocean](https://www.digitalocean.com/?refcode=2962aa9e56a1&utm_campaign=Referral_Invite&utm_medium=Referral_Program&utm_source=CopyPaste) account *Note: this is a referral link from the faasd docs that get's you some free credits*
- A [Twilio account](https://www.twilio.com/referral/x1111z) *Note: this is a referral link from me that gets us both $10*
- A [Slack workspace](https://slack.com/)
- Git
- [Terraform](https://www.terraform.io/)
- A domain in which you can create records
- A Gmail account

The cost will depend on how much you use Twilio. So far a $5 / month Digital Ocean Droplet is working for me. The referral links from above should provide enough credits to try this out for free though.

## Deployment

Though most of the work needed for this setup is handled by the "fbc-slackbot-python" function, there is also a second function called "email-to-slack" that handles checking Gmail. The process here will deploy both functions along with all the infrastructure needed to run them.

### Deployment of faasd

Use [this tutorial from OpenFaaS](https://www.openfaas.com/blog/faasd-tls-terraform/) to get up and running. The exceptions to the tutorial are:

- clone this repository instead of the faasd one and then
- `cd` into the `digitalocean-terraform` folder
- edit `main.tfvars` to suit your needs (it's been modified from the original one)
- stop when you get to "Deploy a function" unless you just want to follow along for the learnings

### Twilio configuration

Before moving forward you will need to setup your Twilio account. Follow the "Setting up Twilio" section of [this](https://www.twilio.com/blog/build-sms-slack-bridge-python-twilio) tutorial. Instead of the URL it talks about using you will need to enter your OpenFaaS URL followed by `/function/fbc-slackbot-python/incoming/twilio`. For example: `https://faasd.example.com/function/fbc-slackbot-python/incoming/twilio`

The page where you enter that URL can be gotten to via [https://www.twilio.com/console/phone-numbers/incoming](https://www.twilio.com/console/phone-numbers/incoming) and then clicking on the number you want to use.

### q-and-a channel

Go to your Slack workspace and create a channel named `q-and-a` as that is the room that the functions expect to post to.

### Slack app, part 1

1. Create a bot as described in [Create a bot for your workspace](https://slack.com/help/articles/115005265703-Create-a-bot-for-your-workspace)
2. Go to "Basic Information" on the left side bar and click "Add features and functionality"
3. Select "Permissions"
4. Add the following OAuth scopes under "Bot Token Scopes":
   - channels:history
   - channels:join
   - channels:read
   - chat:write
   - chat:write.customize
   - chat:write.public
5. Add the following OAuth scopes under "User Token Scopes":
   - channels:history
6. Go to "Basic Information" on the left side bar and click "Add features and functionality" again.
7. Go to "OAuth & Permissions" on the left side bar and make note of the "Bot User OAuth Access Token."

### Configure Gmail

To use IMAP with a Gmail account you must first go to your settings page and click on "Forwarding and POP/IMAP." On that page you will need to toggle on "Enable IMAP." You will then need to follow the instructions on [Less secure apps & your Google Account](https://support.google.com/accounts/answer/6010255) to either enable less secure apps or create an app password.

### Deploying needed secrets

The functions in this repository's `functions` folder need a few secrets to work:

- `email-account`: the Gmail account that will be interacted with
- `email-password`: the password for the Gmail account
- `imap-server`: the IMAP server to interact with (`imap.gmail.com`)
- `slack-bot-token`: the "Bot user OAuth Access Token" from your Slack app
- `smtp-server`: the SMTP server to interact with (`smtp.gmail.com`)
- `twilio-account-sid`: the "Account SID" from Twilio
- `twilio-auth-token`: the "Auth Token" from Twilio
- `twilio-number`: the phone number from Twilio used for texts

Deploy each secret via a command such as this:

```bash
faas-cli secret create imap-server --from-literal imap.gmail.com
```

### Deploying the functions

- Change into the `functions` folder from the `digitalocean-terraform` folder via `cd ../functions`
- Once in that folder, run the following commands:
  ```bash
  # Log into your Docker registry
  docker login

  # Build and deploy the functions
  faas-cli up -f stack.yml
  ```

### Slack app, part 2

Once the `fbc-slackbot-python` function is running go back to your Slack app and select "Basic Information" on the left side bar again. Click "Add features and functionality" and select "Event Subscriptions" and then toggle on "Enable Events."

In the "Request URL" field enter your OpenFaaS URL followed by `/function/fbc-slackbot-python/incoming/slack`. For example: `https://faasd.example.com/function/fbc-slackbot-python/incoming/slack`.

If all goes well, you will see "Verified" in green next to the "Request URL" heading. Once you do, select "Subscribe to events on behalf of users" and click "Add Workspace Event". Select "message.channels" from the available options.

### Checking for emails

A couple of minutes after creating your Droplet on Digital Ocean you should get an email containing information about how to ssh into it. Once you have this information, ssh to your new host and run `crontab -e` so that you can create a new cron job. Press `i`, and enter this:

```bash
* * * * * curl -sS https://faasd.example.com/function/email-to-slack >/dev/null 2>&1
```

After you enter this line, press the escape key to exit the editing mode and then press `:wq` to write and quit.

This will cause the "email-to-slack" to be called once a minute. Each run will deliver any new emails to Slack.

## Try it out

At this point you should have a working bot! Test it out by sending a text to the Twilio number. You should see it arrive in `#q-and-a`. Click on the message and start a thread. In the thread enter a reply and it should show up on your phone. Next, send an email to the address you specified earlier and then respond in the same way.

## Limitations

Currently, there are a few known limitations of this setup:

- MMS messages are not handled (aka photos and videos)
- Email attachments are not handled
- Complex HTML will be lost in the Slack version of a message
- Images and other similar items in Slack are not sent back to the sender
- Reactions to the original message are not sent to the sender

## Planned Improvements

I am planning to deal with attachments and images going both directions. I am also considering doing something with select reactions to the original message.

I also want to update the Terraform code to store state in Terraform Cloud since doing so is free.

## Credit

The code here was developed by combining bits and pieces from these sources and random web searches:

- [Bring a lightweight Serverless experience to DigitalOcean with Terraform and faasd](https://www.openfaas.com/blog/faasd-tls-terraform/)
- [How to build a SMS-to-Slack Bridge with Python and Twilio](https://www.twilio.com/blog/build-sms-slack-bridge-python-twilio)
- [Bootstrap faasd with TLS support on Digitalocean](https://github.com/openfaas/faasd/tree/16a8d2ac6ce861bea64e218359764c8ae238ca19/docs/bootstrap/digitalocean-terraform)
