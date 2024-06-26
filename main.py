"""
This script is used to send reminders to lab members about their duties.
The script is run every day at 7:00 AM PST.
"""
import base64
import json
import os
import subprocess
import sys
import traceback
from datetime import date, datetime, timedelta

import holidays

from calendar_manager import CalendarManager
from config_loader import ConfigLoader
from email_notifier import EmailNotifier
from slack_notifier import SlackNotifier

__author__ = "Madison Howard"
__email__ = "mihoward@caltech.edu"

MEETING_SIGNATURE = "\n\nBest,\nMadison Howard"
SERVICE_SIGNATURE = "\n\nThank you for your service,\nMadison Howard"


def is_meeting_scheduled(date, calendar_manager, search_word="Group Meeting"):
    """
    Checks the Google Calendar to see if there is a meeting scheduled for the given date.

    Parameters:
    - date (datetime.date): The date to check for a scheduled meeting.
    - calendar_manager (CalendarManager): An instance of the CalendarManager class that provides access to the Google Calendar.
    - search_word (str, optional): The keyword to search for in the event title. Defaults to "Group Meeting".

    Returns:
    - bool: True if no meeting is scheduled, False otherwise.
    """
    return not calendar_manager.check_event_existence(date, search_word)
    

def create_reminder(instruction):
    check_symbol = "-"
    # check_symbol = "-"
    return "{} {}\n".format(check_symbol, instruction)

def create_step(reminder):
    check_symbol = "☐"
    # check_symbol = "-"
    return "{} {}\n".format(check_symbol, reminder)

def get_header(name, date_maintenance):
    header = "Hi {},\n\nThis is a reminder that next week it is your turn to do the Hutzler Lab Maintenance. Please refer to the following checklist.\n\n".format(name)
    return header

def get_signature(bot_name="Hutzler Lab Bot"):
    salute = "🫡 "
    # salute = ""
    return "\n\nThank you for your service {},\n{}".format(salute, bot_name)

def get_reminders(reminders_list):
    reminders = []
    for reminder_string in reminders_list:
        reminders.append(create_reminder(reminder_string))
    prompt = "\n\nSome safety considerations from EH&S:\n"
    reminders = "".join(reminders)
    return prompt + reminders + "\n"

def create_email_content(name, date_maintenance, instructions, reminders, bot_name="Hutzler Lab Bot"):
    header = get_header(name, date_maintenance)
    steps = []
    for instruction in instructions:
        steps.append(create_step(instruction))
    body = "".join(steps)
    reminders = get_reminders(reminders)
    signature = get_signature(bot_name)
    return header + body + reminders + signature

def chosen_day(day_name):
    days = {
        "Monday": 0,
        "Tuesday": 1,
        "Wednesday": 2,
        "Thursday": 3,
        "Friday": 4,
        "Saturday": 5,
        "Sunday": 6
    }
    return days.get(day_name, -1)  # Returns -1 if the day name is not valid

def get_decoded_service_key(base64_key):
    if base64_key:
        decoded_key = base64.b64decode(base64_key).decode('utf-8')
        return json.loads(decoded_key)
    else:
        raise ValueError("GOOGLE_CALENDAR_SERVICE_KEY is not set or is invalid")

def load_google_service_key(file_path):
        try:
            with open(file_path, 'r') as file:
                return json.load(file)
        except Exception as e:
            raise ValueError(f"Failed to load Google service key: {e}")




class LabNotificationSystem:
    def __init__(self, presentation_day, presentation_time, maintenance_day, location):
        self.lab_members = ConfigLoader('lab_members.json').load_config()
        self.gmail_username = os.environ.get('GMAIL_USERNAME')
        self.gmail_password = os.environ.get('GMAIL_PASSWORD')
        self.slack_token = os.environ.get('SLACK_TOKEN')
        self.google_calendar_service_key = load_google_service_key('service_key.json')


        self.maintenance_day = chosen_day(maintenance_day)
        self.presentation_day = chosen_day(presentation_day)
        self.presentation_time = presentation_time
        self.location = location
        self.us_holidays = holidays.US()


        self.email_notifier = EmailNotifier(self.gmail_username, self.gmail_password)
        self.calendar_manager = CalendarManager(self.email_notifier)
        self.slack_notifier = SlackNotifier(self.slack_token)

    def run(self):
        print("=====================================")
        print("Running the lab notification system...")
        print(f"Date: {date.today()} | Time: {datetime.now().strftime('%H:%M:%S')} | OS: {os.name}")
        print("=====================================")
        self.send_presentation_reminders()
        print("Handling Presentation reminders...")
        print("=====================================")
        print("\n")

    def get_next_member(self, members, current_member_id):
        current_index = members.index(next((m for m in members if m['id'] == current_member_id), None))
        next_index = (current_index + 1) % len(members)
        return members[next_index]['id']

    def update_duty_tracker(self, duty_type, next_member_id):
        with open('duty_tracker.json', 'r') as file:
            tracker = json.load(file)
        tracker[duty_type] = next_member_id
        with open('duty_tracker.json', 'w') as file:
            json.dump(tracker, file, indent=4)
        #self.commit_and_push_changes()

    def commit_and_push_changes(self):
        subprocess.run(['git', 'add', 'duty_tracker.json'], check=True)
        subprocess.run(['git', 'commit', '-m', 'Update duty tracker'], check=True)
        subprocess.run(['git', 'push'], check=True)

    def no_meeting(self, today):
        # Check if next week today is a national holiday
        next_week = today + timedelta(days=14) # !TODO: change back to 7
        if next_week in self.us_holidays:
            #self.slack_notifier.send_message('#lfl-general', f"Reminder: No lab meeting next week due to a national holiday - {self.us_holidays.get(today)}")
            return True
        # Check if next week has a calendar entry
        else:
            return is_meeting_scheduled(next_week, self.calendar_manager)

    def send_presentation_reminders(self, search_word="Group Meeting"):
        today = datetime.today()
        tracker = self.load_duty_tracker()

        if today.weekday() == self.presentation_day:  
            if self.no_meeting(today):
                pass
            else:
                print("Sending presentation reminders...")
                print("tracker: ", tracker)
                current_presenter_id = tracker.get('presentation', None)
                presenters, next_presenter_id, is_group_presentation = self.get_next_presenter(current_presenter_id)

                pres_date = today + timedelta(days=14) # !TODO: change back to 7
                pres_datestring = pres_date.date()

                # Handle group presentation for undergraduates
                if is_group_presentation:
                    print("Group Presentation by undergrads")
                    for presenter_info in presenters:
                        subject = "Hutzler Lab Group Meeting Presentation"
                        message = f"Hi {presenter_info['name']},\n\nYou are scheduled to present at Wednesday group meeting in two weeks on - {pres_datestring}." + MEETING_SIGNATURE
                        self.email_notifier.send_email([presenter_info['email']], subject, message)

                    # Slack notification for group presentation
                    # self.slack_notifier.send_message('#general', "Next week's presentation will be given by our undergrads.")

                    # Create Google Calendar event for group presentation
                    """
                    self.calendar_manager.create_timed_event(
                        title="Undergraduate Group Presentation",
                        date=pres_date,
                        start_time_str=self.presentation_time,
                        attendees=[member['email'] for member in presenters]
                    )
                    """
                    # Update the Google Calendar event for the group presentation
                    new_event_name = "Group Meeting - Undergraduate Group Presentation"
                    self.calendar_manager.change_event_name(pres_date, search_word, new_event_name)

                # Handle individual presentation
                else:
                    presenter_info = presenters[0]  # Only one presenter
                    print(f"Group Presentation by {presenter_info['name']}")
                    subject = "Hutzler Lab Group Meeting Presentation"
                    message = f"Hi {presenter_info['name']},\n\nYou are scheduled to present at Wednesday group meeting in two weeks on - {pres_datestring}." + MEETING_SIGNATURE
                    self.email_notifier.send_email([presenter_info['email']], subject, message)

                    # Slack notification for individual presentation
                    # self.slack_notifier.send_message('#general', f"Next week's presentation will be given by {presenter_info['name']}.")

                    # Create Google Calendar event for individual presentation
                    """
                    self.calendar_manager.create_timed_event(
                        title="Group Meeting Presentation by " + presenter_info['name'],
                        date=pres_date,
                        start_time_str=self.presentation_time,
                        attendees=[member['email'] for member in presenters],
                        location=self.location
                    )
                    """
                    # Update the Google Calendar event for the group presentation
                    new_event_name = f"Group Meeting - {presenter_info['name']} Presents"
                    self.calendar_manager.change_event_name(pres_date, search_word, new_event_name)

                    # Send out calendar invites
                    self.calendar_manager.add_attendees_to_event(pres_date, new_event_name, [{'email': presenter_info['email']}])

                # Update the duty tracker
                self.update_duty_tracker('presentation', next_presenter_id)

    def load_duty_tracker(self):
        with open('duty_tracker.json', 'r') as file:
            return json.load(file)

    def get_next_presenter(self, current_presenter_id):
        members_list = list(self.lab_members.values())
        current_index = members_list.index(next((member for member in members_list if member['id'] == current_presenter_id), members_list[0]))

        next_index = (current_index + 1) % len(members_list)
        next_presenter = members_list[next_index]

        if next_presenter['role'] == 'Undergraduate Student':
            # Find all undergraduates
            undergrads = [member for member in members_list if member['role'] == 'Undergraduate Student']

            # Return the list of undergraduates and set the next presenter to the first non-undergraduate
            next_non_undergrad_index = (members_list.index(undergrads[-1]) + 1) % len(members_list)
            next_non_undergrad_id = members_list[next_non_undergrad_index]['id']

            return undergrads, next_non_undergrad_id, True
        else:
            # Next presenter is not an undergraduate
            return [next_presenter], next_presenter['id'], False

    def lab_maintance_email(self, recipient_name, date_maintenance):

        ln2_instruction = "Please schedule a Liquid Nitrogen Fill Up with Jivin (jseward@usc.edu) and refill our tank"

        instructions = [ln2_instruction, "Check Lab Inventory: napkins, water filters, gloves, masks, printing supply, compressed air", "Check Chemical Inventory", "Assess Water Filter Status", "Check cooling water temperature and pressure", "Fill up traps and dewars with LN2", "General Cleanup of the Lab (call people out if needed)","Monitor waste labels and complete them if they are missing any information", "Issue a Waste Pick Up Request with EH&S if Accumulation Date on a label is almost 9 months or if you need to dispose of the waste ASAP", "Version Control and Back Up Code Base on GitHub"]

        reminders = ["🌳 Wear O2 monitor while doing LN2 fill up","🚪 Keep Back Room Door open while doing LN2 fill up","🪤 Don't position yourself such that you are trapped by the dewar","👖 Wear full pants on Lab Maintenance Day", "🚫 Don't reuse gloves", "🦠 Don't touch non-contaminated items with gloves", "🧤 Wear thermal gloves when working with LN2", "🥼🥽 Wear safety coat and goggles", "👥 Use the buddy system if not comfortable doing a task alone"]


        return create_email_content(recipient_name, date_maintenance, instructions, reminders)


    
    def send_lab_maintenance_reminders(self):
        if datetime.today().weekday() == self.maintenance_day:
            tracker = self.load_duty_tracker()
            current_maintenance_id = tracker.get('maintenance', None)
            eligible_members = [member for member in self.lab_members.values() if member['role'] in ['PhD Student', 'Post-Doc']]
            next_maintenance_id = self.get_next_member(eligible_members, current_maintenance_id)

            # Send email reminder
            maintainer_info = next((member for member in eligible_members if member['id'] == next_maintenance_id), {})
            
            # Create email content
            date_maintenance = (date.today() + timedelta(days=1)).isoformat()
            maintenance_message = self.lab_maintance_email(maintainer_info['name'], date_maintenance)

            if maintainer_info:
                subject = "Lab Maintenance Reminder"
                message = maintenance_message
                print(f"Maintenance week by - {maintainer_info['name']}")
                self.email_notifier.send_email([maintainer_info['email']], subject, message)

                # Create a calendar event for the maintenance week
                start_date = (date.today() + timedelta(days=3)).isoformat()  # Start from next Monday
                end_date = (date.today() + timedelta(days=7)).isoformat()    # End on next Friday
                self.calendar_manager.create_event(
                    title=f"Lab Maintenance by {maintainer_info['name']}",
                    description=maintenance_message,
                    start_date=start_date,
                    end_date=end_date,
                    attendees=[maintainer_info['email']],
                    location=self.location,
                    all_day=True
                )

            # Update the duty tracker
            self.update_duty_tracker('maintenance', next_maintenance_id)

    def send_lab_snacks_reminders(self):
        # Send reminders on the day before the presentation including edgecase of sunday
        if datetime.today().weekday() == self.presentation_day - 1 or (datetime.today().weekday() == 6 and self.presentation_day == 0):
            print("Sending lab snacks reminders...")
            tracker = self.load_duty_tracker()
            current_snacks_id = tracker.get('snacks', None)
            eligible_members = [member for member in self.lab_members.values() if member['role'] != 'Undergraduate Student']
            next_snacks_id = self.get_next_member(eligible_members, current_snacks_id)

            # Send email reminder
            snack_person_info = next((member for member in eligible_members if member['id'] == next_snacks_id), {})
            if snack_person_info:
                subject = "Lab Snacks Reminder"
                message = f"Hello {snack_person_info['name']},\n\nThis is a reminder for you to bring snacks for the lab meeting on {presentation_day}." + SERVICE_SIGNATURE
                self.email_notifier.send_email([snack_person_info['email']], subject, message)

            print("Snacks bought by - ", snack_person_info['name'])
            # Update the duty tracker
            self.update_duty_tracker('snacks', next_snacks_id)

def alert_developer(e):
    gmail_username = os.environ.get('GMAIL_USERNAME')
    gmail_password = os.environ.get('GMAIL_PASSWORD')
    email_notifier = EmailNotifier(gmail_username, gmail_password)
    token_error_msg = "('invalid_grant: Token has been expired or revoked.', {'error': 'invalid_grant', 'error_description': 'Token has been expired or revoked.'})"
    resolution_msg = f"If error message is\n`{token_error_msg}`\nresoultion is:\n\n1) Delete the `token.pickle` file\n2) Run the script again"
    bar = "=" * 30
    content = f"System Generated Error Message:\n{bar}\n\n{str(e)}\n\nResolutions:\n{bar}\n\n{resolution_msg}"
    email_notifier.send_email([__email__], "Lab Notification System Error", content)

if __name__ == "__main__":
    presentation_day = "Wednesday"
    presentation_time = "9:30 AM"
    maintenance_day = "Friday"
    location = "Kellog Library"

    system = LabNotificationSystem(presentation_day, presentation_time, maintenance_day, location)
    system.run()
    """
    system = None
    try:
        system = LabNotificationSystem(presentation_day, presentation_time, maintenance_day, location)
    except Exception as e:
        print(f"Caught exception during initialization: {e}")
        alert_developer(e)
        sys.exit(1)
    try:
        system.run()
    except Exception as e:
        print(f"Caught exception during execution: {e}")
        alert_developer(e)
        sys.exit(1)
    """