__author__ = "Sadman Ahmed Shanto"
__email__ = "shanto@usc.edu"

import os
import os.path
import pickle
from datetime import datetime, timedelta

from dateutil.parser import parse
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


class CalendarManager:
    def __init__(self, email_notifier, client_secret_file="client_secret.json", token_file='token.pickle', scopes=['https://www.googleapis.com/auth/calendar']):
        self.credentials = None
        self.email_notifier = email_notifier
        self.client_secret_file = client_secret_file
        self.token_file = token_file
        self.scopes = scopes
        
        if os.path.exists(token_file):
            with open(token_file, 'rb') as token:
                self.credentials = pickle.load(token)

        # If there are no valid credentials available, let the user log in.
        self.__athenticate_via_browser() #old method

        self.service = build('calendar', 'v3', credentials=self.credentials)
    
    def __athenticate_via_browser(self):
        if not self.credentials or not self.credentials.valid:
            if self.credentials and self.credentials.expired and self.credentials.refresh_token:
                self.credentials.refresh(Request())
            else:
                self.email_notifier.send_email([__email__], 'Re-authentication Required', 'Please re-authenticate your app.')
                self.initiate_new_authentication_flow()
    
    def initiate_new_authentication_flow(self):
        flow = InstalledAppFlow.from_client_secrets_file(self.client_secret_file, scopes=self.scopes)
        self.credentials = flow.run_local_server(port=0)
        with open(self.token_file, 'wb') as token:
            pickle.dump(self.credentials, token)

    def create_event(self, title, description, start_date, end_date, attendees, all_day=False, location="SSC 319"):
        """Create a calendar event without attendees."""
        time_zone = 'America/Los_Angeles'
        if all_day:
            #* For all-day events, use 'date' instead of 'dateTime'
            start = {'date': start_date}
            end = {'date': end_date}
            colorId = "2"
        else:
            #* For timed events, use 'dateTime'
            start = {'dateTime': start_date, 'timeZone': time_zone}
            end = {'dateTime': end_date, 'timeZone': time_zone}
            colorId = "4"
        #* Add location if provided
        event_body = {
            'summary': title,
            'description': description,
            'colorId': colorId,  # '2' for all-day, '4' for timed
            'start': start,
            'end': end,
            'attendees': [{'email': attendee} for attendee in attendees],
            'location': location,
            'reminders': {
                'useDefault': False,
                'overrides': [{'method': 'email', 'minutes': 24 * 60},
                              {'method': 'popup', 'minutes': 10}],
            },
        }
        try:
            event = self.service.events().insert(calendarId='primary', body=event_body).execute()
            print('Event created: %s' % (event.get('htmlLink')))
        except HttpError as e:
            error_message = f"An error occurred in CalendarManager: {e}"
            self.email_notifier.send_email([__email__], "CalendarManager Error", error_message)
            print(error_message)
            raise


    def create_timed_event(self, title, date, start_time_str, attendees, calendar_id='primary', location="SSC 319"):
        """Create a calendar event based on a start time string."""
        time_zone = 'America/Los_Angeles'
        
        # Parse the start time string and set it to the provided date
        start_time = parse(start_time_str)
        start_datetime = datetime.combine(date.date(), start_time.time())

        # Add one hour to get the end time
        end_datetime = start_datetime + timedelta(hours=1)

        event_body = {
            'summary': title,
            "colorId": "10",
            'start': {'dateTime': start_datetime.isoformat(), 'timeZone': time_zone},
            'end': {'dateTime': end_datetime.isoformat(), 'timeZone': time_zone},
            'attendees': [{'email': attendee} for attendee in attendees],
            'location': location,
            'reminders': {
                'useDefault': False,
                'overrides': [{'method': 'email', 'minutes': 24 * 60}, {'method': 'popup', 'minutes': 10}],
            },
        }
        try:
            event = self.service.events().insert(calendarId=calendar_id, body=event_body).execute()
            print('Event created: %s' % (event.get('htmlLink')))
        except HttpError as e:
            error_message = f"An error occurred in CalendarManager: {e}"
            self.email_notifier.send_email([__email__], "CalendarManager Error", error_message)
            print(error_message)
            raise

    def get_calendar_events(self, date):
        """Shows basic usage of the Google Calendar API.
        Lists the start and name of the next 10 events on the user's calendar.
        """
        creds = None
        # The file token.pickle stores the user's access and refresh tokens, and is
        # created automatically when the authorization flow completes for the first
        # time.
        if os.path.exists('token.pickle'):
            with open('token.pickle', 'rb') as token:
                creds = pickle.load(token)
        # If there are no (valid) credentials available, let the user log in.
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    'credentials.json', self.scopes)
                creds = flow.run_local_server(port=0)
            # Save the credentials for the next run
            with open('token.pickle', 'wb') as token:
                pickle.dump(creds, token)

        service = build('calendar', 'v3', credentials=creds)

        # Call the Calendar API
        now = datetime.utcnow().isoformat() + 'Z' # 'Z' indicates UTC time
        print('Getting the upcoming 10 events')
        events_result = service.events().list(calendarId='hutzlerlab@gmail.com', timeMin=now,
                                            maxResults=10, singleEvents=True,
                                            orderBy='startTime').execute()
        events = events_result.get('items', [])

        if not events:
            print('No upcoming events found.')
        for event in events:
            start = event['start'].get('dateTime', event['start'].get('date'))
            print(start, event['summary'])

    def get_calendar_event_for(self, date):
        """Shows basic usage of the Google Calendar API.
        Lists the events on the user's calendar for a given day.
        """
        # Convert the date to the correct format
        timeMin = date.replace(hour=0, minute=0, second=0, microsecond=0).isoformat() + 'Z'
        timeMax = (date + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0).isoformat() + 'Z'

        # Call the Calendar API
        print(f'Getting the events for {date}')
        events_result = self.service.events().list(
            calendarId='hutzlerlab@gmail.com', 
            timeMin=timeMin,
            timeMax=timeMax,
            singleEvents=True,
            orderBy='startTime',
            timeZone='America/Los_Angeles'
        ).execute()
        events = events_result.get('items', [])

        if not events:
            print('No events found.')
        for event in events:
            start = event['start'].get('dateTime', event['start'].get('date'))
            print(start, event['summary'])

    def change_event_name(self, date, event_name, new_event_name):
        """Changes the name of an event on a given date."""
        # Set timeMin to the start of the day and timeMax to the end of the day
        timeMin = date.replace(hour=0, minute=0, second=0, microsecond=0).isoformat() + 'Z'
        timeMax = (date + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0).isoformat() + 'Z'

        # Call the Calendar API to get the events for the given date
        events_result = self.service.events().list(
            calendarId='hutzlerlab@gmail.com', 
            timeMin=timeMin,
            timeMax=timeMax,
            singleEvents=True,
            orderBy='startTime',
            timeZone='America/Los_Angeles'
        ).execute()
        events = events_result.get('items', [])

        # Iterate over the events
        for event in events:
            # If the event name matches the given event name
            if event['summary'] == event_name:
                # Change the event name
                event['summary'] = new_event_name
                # Update the event
                updated_event = self.service.events().update(
                    calendarId='hutzlerlab@gmail.com', 
                    eventId=event['id'], 
                    body=event
                ).execute()
                print(f"Event updated: {updated_event.get('htmlLink')}")
                return

        print(f"No event found with the name {event_name} on {date}") 

    def check_event_existence(self, date, event_name):
        """Checks if an event exists on a given date."""
        # Set timeMin to the start of the day and timeMax to the end of the day
        timeMin = date.replace(hour=0, minute=0, second=0, microsecond=0).isoformat() + 'Z'
        timeMax = (date + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0).isoformat() + 'Z'

        # Call the Calendar API to get the events for the given date
        events_result = self.service.events().list(
            calendarId='hutzlerlab@gmail.com', 
            timeMin=timeMin,
            timeMax=timeMax,
            singleEvents=True,
            orderBy='startTime',
            timeZone='America/Los_Angeles'
        ).execute()
        events = events_result.get('items', [])

        # Iterate over the events
        for event in events:
            # If the event name matches the given event name
            if event['summary'] == event_name:
                print(f"Event found: {event_name} on {date.date()}")
                return True

        print(f"No event found with the name {event_name} on {date.date()}")
        return False

    def add_attendees_to_event(self, date, event_name, attendees):
        """Adds attendees to an event on a given date."""
        # Set timeMin to the start of the day and timeMax to the end of the day
        timeMin = date.replace(hour=0, minute=0, second=0, microsecond=0).isoformat() + 'Z'
        timeMax = (date + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0).isoformat() + 'Z'

        # Call the Calendar API to get the events for the given date
        events_result = self.service.events().list(
            calendarId='hutzlerlab@gmail.com', 
            timeMin=timeMin,
            timeMax=timeMax,
            singleEvents=True,
            orderBy='startTime',
            timeZone='America/Los_Angeles'
        ).execute()
        events = events_result.get('items', [])

        # Iterate over the events
        for event in events:
            # If the event name matches the given event name
            if event['summary'] == event_name:
                # Add the attendees to the event
                if 'attendees' in event:
                    event['attendees'].extend(attendees)
                else:
                    event['attendees'] = attendees
                # Update the event
                updated_event = self.service.events().patch(
                    calendarId='hutzlerlab@gmail.com', 
                    eventId=event['id'], 
                    body={'attendees': event['attendees']}
                ).execute()
                print(f"Attendees added to event: {updated_event.get('htmlLink')}")
                return

        print(f"No event found with the name {event_name} on {date.date()}")