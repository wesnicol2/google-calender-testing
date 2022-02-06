from __future__ import print_function
from time import sleep
import math
import random
import re
import datetime
import os.path
import copy
import json
import logging

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
STD_NOTIFICATION_TIME = 5
ONE_DAY_NOTIFICATION_TIME = 1440
LOG_DATE_FORMAT = '%Y_%m_%d_%H_%M_%S'
LOG_DIR='./logs'
LOG_FILENAME = "update_calendar_events_" + datetime.datetime.now().strftime(LOG_DATE_FORMAT) + ".log"


# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/calendar']

def initialize_colors():
    # Reference this page: https://lukeboyle.com/blog/posts/google-calendar-api-color-id
    global COLORS
    COLORS['light purple'] = '1'
    COLORS['light green'] = '2'
    COLORS['purple'] = '3'
    COLORS['pink'] = '4'
    COLORS['yellow'] = '5'
    COLORS['orange'] = '6'
    COLORS['light blue'] = '7'
    COLORS['gray'] = '8'
    COLORS['dark blue'] = '9'
    COLORS['green'] = '10'
    COLORS['red'] = '11'


def setup_logging(log_filepath=LOG_DIR+'/'+LOG_FILENAME):
    # Create log path if it doesn't exist
    if not os.path.exists(os.path.dirname(log_filepath)):
        os.makedirs(os.path.dirname(log_filepath))

    logging.basicConfig(
        level=logging.INFO,
        encoding='utf-8',
        filename=log_filepath,
        format='%(asctime)s [%(levelname)s]: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )


def setup():
    global service
    setup_logging()
    logging.info("Setting up Google Calendar API")
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
    logging.info("Setup complete")


def update_event(event):
    logging.info("Updating event: " + event.get('summary'))
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
                logging.info("Retry count: " + str(progress * rate))
                if progress <= max_retries:
                    sleep_time = 2**progress - 1
                    if sleep_time > 0.5:
                        sleep_time += random.uniform(0, 1)
                    logging.info("Retrying in " + str(sleep_time) + " seconds")
                    sleep(sleep_time)                
                else:
                    # logging.info("Error: " + str(e))
                    # logging.info("Exceeded maximum number of retries")
                    raise e
            progress += progress_increment
            
        break
    logging.info("Event updated successfully")

def print_calendar_info(calendar):
    logging.info("Calendar: " + calendar.get('summary') + " (" + calendar.get('id') + ")")


def get_events_from_calendar(calendar, start_date=datetime.datetime(2022, 2, 1)):
    id = calendar.get('id')
    logging.info("Getting events from calendar:")
    print_calendar_info(calendar)
    start_date = start_date.isoformat() + 'Z'  # 'Z' indicates UTC time
    events_result = service.events().list(calendarId=id, timeMin=start_date,
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
                logging.info("Removed event: " + event.get('summary'))
    else:
        logging.info("No events to remove")

# Returns true if an update is made (Meaning a call to update_event will be required to submit the changes)
def remove_notifications(event):
    if event.get('reminders').get('useDefault') == False:
        logging.info("Removing notifications for event: " + event.get('summary'))
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
        logging.info("Notification already exists for event: " + event.get('summary'))
    else: 
        logging.info(f"Setting {minutes} minute notification for event: " + event.get('summary'))
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
            logging.info("Notification already exists for event: " + event.get('summary'))
        else:
            logging.info(f"Adding {minutes} minute notification for event: " + event.get('summary'))
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
        logging.info(f"Invalid color: {color}")
    elif event.get('colorId') == COLORS[color]:
        logging.info(f"Color already set to {color} for event: {event.get('summary')}")
    else:
        logging.info(f"Setting {color} color for event: {event.get('summary')}")
        event['colorId'] = str(COLORS[color])
        # update_event(event)
        return True
    return False


def event_reminders_are_equal(event1, event2):
    if event1.get('reminders') == event2.get('reminders'):
        return True

    # Make sure use default is equal
    if event1.get('reminders').get('useDefault') != event2.get('reminders').get('useDefault'):
        return False

    if event1.get('reminders').get('useDefault') is True:
        return True

    # Make sure overrides are effectivly equal
    overrides_set_1 = set()
    for override in event1.get('reminders').get('overrides'):
        overrides_set_1.add(json.dumps(override, sort_keys=True))


    overrides_set_2 = set()
    for override in event2.get('reminders').get('overrides'):
        overrides_set_2.add(json.dumps(override, sort_keys=True))

    if overrides_set_1 != overrides_set_2:
        return False

    return True
  

# Returns true if events are effectivly the same. Add any comprisons that should be included in that determination here
def events_are_equal(event1, event2):
    if str(event1.get('id')) != str(event2.get('id')):
        return False

    if str(event1.get('summary')) != str(event2.get('summary')):
        return False

    if str(event1.get('start').get('dateTime')) != str(event2.get('start').get('dateTime')):
        return False

    if str(event1.get('end').get('dateTime')) != str(event2.get('end').get('dateTime')):
        return False

    if event1.get('location') != event2.get('location'):
        return False

    if str(event1.get('description')) != str(event2.get('description')):
        return False

    if not event_reminders_are_equal(event1, event2):
        return False

    if str(event1.get('colorId')) != str(event2.get('colorId')):
        return False

    return True


def execute_updates(olympics_calendar):
    olympic_events = get_events_from_calendar(olympics_calendar)
    olympic_events = delete_unwanted_events(olympic_events)
    original_olympic_events = copy.deepcopy(olympic_events)

    for event in olympic_events:
        # Set all events to least importance. Notifications and color will be added to specific events with if statements
        # TODO: Figure out how to remove notifications from everything but what has notifications added so that all those with notifications will not be marked for update if they start with notifications
        remove_notifications(event)
        set_color(event, 'gray')

        # Gold Medal Events
        if bool(re.match(".*🏅.*", event.get('summary'))):
            set_color(event, 'yellow')
            add_notifications(event, [STD_NOTIFICATION_TIME, ONE_DAY_NOTIFICATION_TIME])
        
        # USA Events
        if bool(re.match(".*USA.*", event.get('summary'))):
            set_color(event, 'light blue')
            add_notifications(event, STD_NOTIFICATION_TIME)

        # Curling events
        if bool(re.match(".*Curling.*", event.get('summary'))):
            # USA Curling matches
            if bool(re.match(".*USA.*", event.get('summary'))):
                add_notifications(event, [ONE_DAY_NOTIFICATION_TIME, 30])

            # Non-Round Robin Curling matches
            if not bool(re.match("(?i)(.*Round Robin.*)", event.get('summary'))):
                set_color(event, 'dark blue')
                add_notifications(event, [STD_NOTIFICATION_TIME, ONE_DAY_NOTIFICATION_TIME])

        # Snowboarding events
        if bool(re.match(".*Snowboarding.*", event.get('summary'))):
            set_color(event, 'green')

        # Skiiing events
        if bool(re.match("(?i)(.*Skiing.*|.*Super-G.*|.*Downhill.*|.*Alpine.*)", event.get('summary'))) or bool(re.match(".*Super G.*", event.get('summary'))):
            set_color(event, 'green')
            add_notifications(event, [STD_NOTIFICATION_TIME])

        # Hockey events 
        if bool(re.match(".*Hockey.*", event.get('summary'))):
            set_color(event, 'gray')
            remove_notifications(event)

    events_to_update = []
    for event in olympic_events:
        original_event = next(original_event for original_event in original_olympic_events if original_event.get('id') == event.get('id'))
        if events_are_equal(event, original_event):
            logging.info("Event already up to date: " + event.get('summary'))
        else: 
            events_to_update.append(event)

    updated_events_count = 0
    for event in events_to_update:
        logging.info("Events left to update: " + str(len(events_to_update) - updated_events_count))
        update_event(event)
        updated_events_count += 1
        
    logging.info("Events updated: " + str(updated_events_count))

def delete_unwanted_events(olympic_events):
    events_to_delete = list(filter( lambda event: 
        'Re-Air' in event.get('summary') or 
        're-air' in event.get('summary') or 
        'Re-air' in event.get('summary') or
        re.match(".*Success! You're connected to NBC Olympics.*", event.get('summary')) or
        re.match(".*The 2022 Olympic Winter Games are here!️.*", event.get('summary')), 
    olympic_events))
    
    olympic_events = [event for event in olympic_events if event not in events_to_delete]
    remove_events(events_to_delete)
    return olympic_events


def main():
    # TODO: Remove images from events so the color will always show through
    # Google Calendar API Reference: https://developers.google.com/calendar/api
    # Google App Dashboard: https://console.cloud.google.com/apis/dashboard?project=wesnicol-calendar-testing
    setup() # Run setup first
    try:
        olympics_calendar = get_calendar_by_name('NBC Sports')
        execute_updates(olympics_calendar)

        

    except HttpError as error:
        logging.info('An error occurred: %s' % error)


if __name__ == '__main__':
    main()