from __future__ import print_function
import re
from time import sleep
import datetime
import os.path
import logging
import sys
import codecs
sys.stdout = codecs.getwriter('utf8')(sys.stdout) # To support unicode characters on windows

from lifxlan.common_functions import *
from lifxlan.common_constants import *

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

OLYMPIC_CALENDAR_ID = 'icn02kf62d26hurpro3qksjhjc@group.calendar.google.com'
service=None
CREDENTIALS_DIR='./credentials' # TODO: figure out how to make this credentials directory generic if calling this script from somewhere other than script dir
APP_NAME = "olympic_colors"
OLYMPIC_CALENDAR_NAME='NBC Sports'
LOG_DATE_FORMAT = '%Y_%m_%d_%H_%M_%S'
LOG_DIR='./logs'
LOG_FILENAME = f"{APP_NAME}" + datetime.now().strftime(LOG_DATE_FORMAT) + ".log" 

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/calendar']


def setup_logging(log_filepath=LOG_DIR+'/'+LOG_FILENAME):
    # Create log path if it doesn't exist
    if not os.path.exists(os.path.dirname(log_filepath)):
        os.makedirs(os.path.dirname(log_filepath))

    format='%(asctime)s [%(levelname)s]: %(message)s'
    datefmt='%Y/%m/%d %H:%M:%S' # TODO: Change this to %Y-%m-%d %H:%M:%S once it has been confirmed that this format is being used 
    # Create a logger which will send info and debug messages to console only
    # Create formatter to be used with both handlers
    formatter = logging.Formatter(fmt=format, datefmt=datefmt)

    # Create handler for log file and set handler level to INFO
    file_handler = logging.FileHandler(log_filepath)
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)
    # Create handler for console and set handler level to DEBUG
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(formatter)

    
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)



def setup():
    global service
    setup_logging()
    logging.debug("Setting up Google Calendar API")
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
    logging.debug("Setup complete")


def get_events_from_calendar(calendar, start_date=datetime(2022, 2, 1)):
    id = calendar.get('id')
    logging.debug("Getting events from calendar:")
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


def execute_updates(olympics_calendar):
    olympic_events = get_events_from_calendar(olympics_calendar)
    logging.debug("Checking for events currently happening")
    active_event = False
    for event in olympic_events:
        # Only address events which are currently happening
        now = datetime.utcnow().isoformat() + 'Z' # 'Z' indicates UTC time
        start_time = event.get('start').get('dateTime')
        end_time = event.get('end').get('dateTime')
        if start_time < now and end_time > now:
            logging.debug(f"Event {event.get('summary')} is currently happening")
            active_event = True
            # USA events
            if bool(re.match(".*USA.*", event.get('summary'))):
                # If event is currently happening, set light color
                logging.info("Setting light color to blue")
                set_color_all(LIFX_COLORS['blue'], MAX_VALUE * 0.75)

            # Gold Medal Events
            if bool(re.match(".*🏅.*", event.get('summary'))):
                # If event is currently happening, set light color
                logging.info("Setting light color to gold")
                set_color_all(LIFX_COLORS['gold'], MAX_VALUE * 0.75)

    return active_event
        


def main():
    # TODO: Remove images from events so the color will always show through
    # Google Calendar API Reference: https://developers.google.com/calendar/api
    # Google App Dashboard: https://console.cloud.google.com/apis/dashboard?project=wesnicol-calendar-testing
    try:
        setup() # Run setup first
        while True:
            olympics_calendar = get_calendar_by_name('NBC Sports')
            if execute_updates(olympics_calendar):
                # Turn light on
                set_color_all(LIFX_COLORS['green'], MAX_VALUE * 0.25)
            else:
                # Turn lighs off
                set_color_all(LIFX_COLORS['red'], 0)
            sleep(60)
    except Exception as error:
        logging.exception('\n%s' % error)


if __name__ == '__main__':
    main()