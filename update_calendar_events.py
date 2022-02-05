from __future__ import print_function
from audioop import add
from time import sleep
import math
import random
import re
import datetime
import os.path
from pprint import pprint
from enum import Enum

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

OLYMPIC_CALENDAR_ID = 'icn02kf62d26hurpro3qksjhjc@group.calendar.google.com'
service=None
CREDENTIALS_DIR='credentials'
COLORS = {}
OLYMPIC_CALENDAR_NAME='NBC Sports'

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/calendar']

def initialize_colors():
    # Reference this page: https://lukeboyle.com/blog/posts/google-calendar-api-color-id
    global COLORS
    COLORS['light purple'] = 1
    COLORS['light green'] = 2
    COLORS['purple'] = 3
    COLORS['pink'] = 4
    COLORS['yellow'] = 5
    COLORS['orange'] = 6
    COLORS['light blue'] = 7
    COLORS['gray'] = 8
    COLORS['dark blue'] = 9
    COLORS['green'] = 10
    COLORS['red'] = 11

def setup():
    global service
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
    service = build('calendar', 'v3', credentials=creds)
    initialize_colors()


def update_event(event):
    print("Updating event: " + event.get('summary'))
    # Implelmentation of exponential backoff; Ref: https://cloud.google.com/storage/docs/retry-strategy#exponential-backoff
    max_retry_time = 60
    rate = 10
    progress_increment = 1 / rate
    max_retries = math.log(max_retry_time + 1, 2)
    progress = 0
    while True:
        try:
            service.events().update(calendarId=OLYMPIC_CALENDAR_ID, eventId=event['id'], body=event).execute()
        except HttpError as e:
            if e.reason == "Rate Limit Exceeded":
                print("Retry count: " + str(progress * rate))
                if progress <= max_retries:
                    sleep_time = 2**progress - 1
                    if sleep_time > 0.5:
                        sleep_time += random.uniform(0, 1)
                    print("Retrying in " + str(sleep_time) + " seconds")
                    sleep(sleep_time)                
                else:
                    # print("Error: " + str(e))
                    # print("Exceeded maximum number of retries")
                    raise e
            progress += progress_increment
            
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

# Returns true if an update is made (Meaning a call to update_event will be required to submit the changes)
def remove_notifications(event):
    if event.get('reminders').get('useDefault') == False or event.get('reminders').get('overrides') is None:
        print("Removing notifications for event: " + event.get('summary'))
        event['reminders'] = {'useDefault': True}   
        # update_event(event)
        return True
    return False

def notification_already_exists(event, minutes):
    if event.get('reminders').get('useDefault') is True or event.get('reminders').get('overrides') is None:
        return False
    for override in event.get('reminders').get('overrides'):
        if override.get('minutes') == minutes:
            return True
    return False


def set_notification(event, minutes):
    if notification_already_exists(event, minutes):
        print("Notification already exists for event: " + event.get('summary'))
    else: 
        print(f"Adding {minutes} minute notification for event: " + event.get('summary'))
        event['reminders'] = {'useDefault': False, 'overrides': [{'method': 'popup', 'minutes': minutes}]}
        # update_event(event)
        return True
    return False

# Returns true if an update is made (Meaning a call to update_event will be required to submit the changes)
def add_notifications(event, minutes_list):
    update_made = False
    if type(minutes_list) is int or type(minutes_list) is str:
        minutes_list = [minutes_list]
    
    minutes_set = set(minutes_list)
    for minutes in minutes_set:
        if notification_already_exists(event, minutes):
            print("Notification already exists for event: " + event.get('summary'))
        else:
            print(f"Adding {minutes} minute notification for event: " + event.get('summary'))
            if event.get('reminders').get('overrides') is None or len(event.get('reminders').get('overrides')) == 0:
                set_notification(event, minutes)
            else:
                event.get('reminders').get('overrides').append({'method': 'popup', 'minutes': minutes})
            # update_event(event)
            update_made = True
    return update_made

# Returns true if an update is made (Meaning a call to update_event will be required to submit the changes)
def set_color(event, color):
    if color not in COLORS.keys():
        print(f"Invalid color: {color}")
    elif event.get('colorId') == COLORS[color]:
        print(f"Color already set to {color} for event: {event.get('summary')}")
    else:
        print(f"Setting {color} color for event: {event.get('summary')}")
        event['colorId'] = COLORS[color]
        # update_event(event)
        return True
    return False


def execute_updates(olympics_calendar):
    events_to_be_updated = set([])
    # TODO: Add events_to_be_updated set here, this set will be appended with all events that are to be updated
    olympic_events = get_events_from_calendar(olympics_calendar)
    reair_events = list(filter( lambda event: 'Re-Air' in event.get('summary') or 're-air' in event.get('summary') or 'Re-air' in event.get('summary'), olympic_events))
    # remove reair_events from olympic_events
    olympic_events = [event for event in olympic_events if event not in reair_events]
    remove_events(reair_events)

    for event in olympic_events:
        # Set all events to least importance. Notifications and color will be added to specific events with if statements
        # TODO: Figure out how to remove notifications from everything but what has notifications added so that all those with notifications will not be marked for update if they start with notifications
        if remove_notifications(event):

            events_to_be_updated.add(event.get('id'))

        if set_color(event, 'gray'):
            events_to_be_updated.add(event.get('id'))

        if bool(re.match(".*USA.*", event.get('summary'))):
            # USA Events
            if set_color(event, 'red'):
                events_to_be_updated.add(event.get('id'))

            if add_notifications(event, 5):
                events_to_be_updated.add(event.get('id'))


        if bool(re.match(".*🏅.*", event.get('summary'))):
            # Gold Medal Events
            if set_color(event, 'yellow'):
                events_to_be_updated.add(event.get('id'))

            if add_notifications(event, [5, 60*24]):
                events_to_be_updated.add(event.get('id'))


    for event in olympic_events:
        if event.get('id') in events_to_be_updated:
            update_event(event)
    


def main():
    # TODO: Remove images from events so the color will always show through
    # Google Calendar API Reference: https://developers.google.com/calendar/api
    # Google App Dashboard: https://console.cloud.google.com/apis/dashboard?project=wesnicol-calendar-testing
    setup() # Run setup first
    try:
        olympics_calendar = get_calendar_by_name('NBC Sports')
        execute_updates(olympics_calendar)

        

    except HttpError as error:
        print('An error occurred: %s' % error)


if __name__ == '__main__':
    main()