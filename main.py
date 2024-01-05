import os
import json
import subprocess
import holidays
import base64

from datetime import date, datetime, timedelta
from config_loader import ConfigLoader
from email_notifier import EmailNotifier
from slack_notifier import SlackNotifier
from calendar_manager import CalendarManager


MEETING_SIGNATURE = "\n\nLooking Forward to it 🤩,\nLFL Bot."
SERVICE_SIGNATURE = "\n\nThank you for your service 🫡,\nLFL Bot."

def create_reminder(instruction):
    check_symbol = "-"
    # check_symbol = "-"
    return "{} {}\n".format(check_symbol, instruction)

def create_step(reminder):
    check_symbol = "☐"
    # check_symbol = "-"
    return "{} {}\n".format(check_symbol, reminder)

def get_header(name, date_maintenance):
    header = "Hi {},\n\nThis is a reminder that tomorrow ({}) is your turn to do the LFL Lab Maintenance. Please refer to the following checklist.\n\n".format(name, date_maintenance)
    return header

def get_signature(bot_name="LFL Bot"):
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

def create_email_content(name, date_maintenance, instructions, reminders, bot_name="LFL Bot"):
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
    def __init__(self, presentation_day, presentation_time, maintenance_day):
        self.lab_members = ConfigLoader('lab_members.json').load_config()
        self.gmail_username = os.environ.get('GMAIL_USERNAME')
        self.gmail_password = os.environ.get('GMAIL_PASSWORD')
        self.slack_token = os.environ.get('SLACK_TOKEN')
        self.google_calendar_service_key = load_google_service_key('service_key.json')


        self.maintenance_day = chosen_day(maintenance_day)
        self.presentation_day = chosen_day(presentation_day)
        self.presentation_time = presentation_time
        self.us_holidays = holidays.US()


        self.email_notifier = EmailNotifier(self.gmail_username, self.gmail_password)
        self.calendar_manager = CalendarManager(self.email_notifier)
        self.slack_notifier = SlackNotifier(self.slack_token)

    def run(self):
        self.send_presentation_reminders()
        self.send_lab_maintenance_reminders()
        self.send_lab_snacks_reminders()

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
        self.commit_and_push_changes()

    def commit_and_push_changes(self):
        subprocess.run(['git', 'add', 'duty_tracker.json'], check=True)
        subprocess.run(['git', 'commit', '-m', 'Update duty tracker'], check=True)
        subprocess.run(['git', 'push'], check=True)

    def no_meeting(self, today):
        # Check if today is a national holiday
        if today in self.us_holidays:
            self.slack_notifier.send_message('#test-gpt', f"Reminder: No lab meeting today due to a national holiday - {self.us_holidays.get(today)}")
            return True
        # Check if today is the first presentation day of the month
        elif today.day == self.presentation_day:
            self.slack_notifier.send_message('#test-gpt', "Reminder: Today is 'Lab Citizen Day'")
            return True
        # All else case
        else:
            return False

    def send_presentation_reminders(self):
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

                pres_date = today + timedelta(days=7)
                pres_date = pres_date

                # Handle group presentation for undergraduates
                if is_group_presentation:
                    for presenter_info in presenters:
                        subject = "LFL Lab Meeting Presentation"
                        message = f"Hello {presenter_info['name']},\n\nYou are scheduled to present at next week's lab meeting." + MEETING_SIGNATURE
                        self.email_notifier.send_email([presenter_info['email']], subject, message)

                    # Slack notification for group presentation
                    self.slack_notifier.send_message('#test-gpt', "This week's presentation will be given by our undergrads.")

                    # Create Google Calendar event for group presentation
                    self.calendar_manager.create_timed_event(
                        title="Undergraduate Group Presentation",
                        date=pres_date,
                        start_time_str=self.presentation_time,
                        attendees=[member['email'] for member in presenters]
                    )

                # Handle individual presentation
                else:
                    presenter_info = presenters[0]  # Only one presenter
                    subject = "LFL Lab Meeting Presentation"
                    message = f"Hello {presenter_info['name']},\n\nYou are scheduled to present at next week's lab meeting." + MEETING_SIGNATURE
                    self.email_notifier.send_email([presenter_info['email']], subject, message)

                    # Slack notification for individual presentation
                    self.slack_notifier.send_message('#test-gpt', f"This week's presentation will be given by {presenter_info['name']}.")

                    # Create Google Calendar event for individual presentation
                    self.calendar_manager.create_timed_event(
                        title="Group Meeting Presentation by " + presenter_info['name'],
                        date=pres_date,
                        start_time_str=self.presentation_time,
                        attendees=[member['email'] for member in presenters]
                    )

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
                message = f"Hello {maintainer_info['name']},\n\nThis is a reminder that you are on lab maintenance duty next week." + maintenance_message + SERVICE_SIGNATURE
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
                    all_day=True
                )

            # Update the duty tracker
            self.update_duty_tracker('maintenance', next_maintenance_id)

    def send_lab_snacks_reminders(self):
        print("Today's weekday: ", datetime.today().weekday())
        if datetime.today().weekday() == self.presentation_day - 1:
            print("Sending lab snacks reminders...")
            tracker = self.load_duty_tracker()
            current_snacks_id = tracker.get('snacks', None)
            eligible_members = [member for member in self.lab_members.values() if member['role'] != 'Undergraduate Student']
            next_snacks_id = self.get_next_member(eligible_members, current_snacks_id)

            # Send email reminder
            snack_person_info = next((member for member in eligible_members if member['id'] == next_snacks_id), {})
            if snack_person_info:
                subject = "Lab Snacks Reminder"
                message = f"Hello {snack_person_info['name']},\n\nThis is a reminder for you to bring snacks for the lab meeting on {presentation_day}."
                self.email_notifier.send_email([snack_person_info['email']], subject, message)

            # Update the duty tracker
            self.update_duty_tracker('snacks', next_snacks_id)

if __name__ == "__main__":
    presentation_day = "Thursday"
    presentation_time = "2:00 PM"
    maintenance_day = "Thursday"

    system = LabNotificationSystem(presentation_day, presentation_time, maintenance_day)
    system.run()
