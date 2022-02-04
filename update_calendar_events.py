from __future__ import print_function
from audioop import add
from time import sleep
import math
import random
import re
import datetime
import os.path
from pprint import pprint

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

OLYMPIC_CALENDAR_ID = 'icn02kf62d26hurpro3qksjhjc@group.calendar.google.com'
service=None
CREDENTIALS_DIR='credentials'

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/calendar']


def update_event(event):
    print("Updating event: " + event.get('summary'))
    # Implelmentation of exponential backoff; Ref: https://cloud.google.com/storage/docs/retry-strategy#exponential-backoff
    max_retry_time = 60
    max_retries = math.log(max_retry_time + 1, 2)
    retry_count = 0
    while True:
        try:
            service.events().update(calendarId=OLYMPIC_CALENDAR_ID, eventId=event['id'], body=event).execute()
        except HttpError as e:
            if e.reason == "Rate Limit Exceeded":
                print("Retry count: " + str(retry_count + 1))
                if retry_count <= max_retries:
                    sleep_time = 2**retry_count - 1
                    if sleep_time > 0.5:
                        sleep_time += random.uniform(0, 1)
                    print("Retrying in " + str(sleep_time) + " seconds")
                    sleep(sleep_time)                
                    retry_count += 0.1
                else:
                    # print("Error: " + str(e))
                    # print("Exceeded maximum number of retries")
                    raise
            break
    print("Event updated successfully")

def print_calendar_info(calendar):
    print("Calendar: " + calendar.get('summary') + " (" + calendar.get('id') + ")")


def get_events_from_calendar(calendar):
    id = calendar.get('id')
    print("Getting events from calendar:")
    print_calendar_info(calendar)

    now = datetime.datetime.utcnow().isoformat() + 'Z'  # 'Z' indicates UTC time
    events_result = service.events().list(calendarId=id, timeMin=now,
                                            maxResults=999, singleEvents=True,
                                            orderBy='startTime').execute()
    events = events_result.get('items', [])
    return events


def get_calendar_by_id(id):
    return service.calendars().get(calendarId=id).execute()

def get_calendar_by_name(name):
    id = None 
    page_token = None
    while True:
            calendar_list = service.calendarList().list(pageToken=page_token).execute()
            for calendar_list_entry in calendar_list['items']:
                if calendar_list_entry['summary'] == name:
                    id = calendar_list_entry.get('id')
            page_token = calendar_list.get('nextPageToken')
            if not page_token:
                break
    return get_calendar_by_id(id)

def remove_events(events):    
    if len(events) > 0:
        for event in events:
            user_input = input("Would you like to remove event: " + event.get('summary') + "? (y/n)")
            if user_input =='y' or user_input == 'Y':
                service.events().delete(calendarId=OLYMPIC_CALENDAR_ID, eventId=event.get('id')).execute()
                print("Removed event: " + event.get('summary'))
    else:
        print("No events to remove")


def remove_notifications(event):
    if event.get('reminders').get('useDefault') == False:
        print("Removing notifications for event: " + event.get('summary'))
        event['reminders'] = {'useDefault': True}   
        update_event(event)

def notification_already_exists(event, minutes):
    if event.get('reminders').get('useDefault') is True or event.get('reminders').get('overrides') is None:
        return False
    for override in event.get('reminders').get('overrides'):
        if override.get('minutes') == minutes:
            return True
    return False


def add_notification(event, minutes):
    if notification_already_exists(event, minutes):
        print("Notification already exists for event: " + event.get('summary'))
    else: 
        print(f"Adding {minutes} minute notification for event: " + event.get('summary'))
        event['reminders'] = {'useDefault': False, 'overrides': [{'method': 'popup', 'minutes': minutes}]}
        update_event(event)

def main():
    # Google Calendar API Reference: https://developers.google.com/calendar/api
    # Google App Dashboard: https://console.cloud.google.com/apis/dashboard?project=wesnicol-calendar-testing
    """Shows basic usage of the Google Calendar API.
    Prints the start and name of the next 10 events on the user's calendar.
    """
    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                CREDENTIALS_DIR + '/credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    try:
        global service
        service = build('calendar', 'v3', credentials=creds)

        olympics_calendar = get_calendar_by_name('NBC Sports')
        olympic_events = get_events_from_calendar(olympics_calendar)

        reair_events = list(filter( lambda event: 'Re-Air' in event.get('summary') or 're-air' in event.get('summary') or 'Re-air' in event.get('summary'), olympic_events))

        usa_events = list(filter(lambda event: bool(re.match(".*USA.*", event.get('summary'))), olympic_events))
        gold_medal_events = list(filter(lambda event: bool(re.match(".*🏅.*", event.get('summary'))), olympic_events))
        non_gold_medal_events = list(filter(lambda event: not bool(re.match(".*🏅.*", event.get('summary'))), olympic_events))
        bronze_medal_events = list(filter(lambda event: bool(re.match(".*🥉.*", event.get('summary'))), olympic_events))

        notification_events = list()
        notification_events.extend(gold_medal_events)
        notification_events.extend(usa_events)

        non_notification_evetns = list()
        non_notification_evetns.extend(list(filter(lambda event: event not in notification_events, olympic_events)))

        
        for event in non_notification_evetns:
            remove_notifications(event)
        
        for event in notification_events:
            add_notification(event, 10)
        
        for event in gold_medal_events:
            add_notification(event, 60 * 24)
        remove_events(reair_events)

    except HttpError as error:
        print('An error occurred: %s' % error)


if __name__ == '__main__':
    main()