# Hutzler Lab Manager

This project serves as a lab manager for the [Hutzler Lab](https://www.hutzlerlab.com) at Caltech. It automates reminders for maintenance, snacks, and manages lab meeting schedules through emails, Slack, and Google Calendar.

## Project Structure

- `.github/`: Contains GitHub workflows for automation.
- `calendar_manager.py`: Manages Google Calendar integration.
- `config_loader.py`: Loads configuration from JSON files.
- `email_notifier.py`: Handles email notifications.
- `main.py`: The main script for managing notifications.
- `slack_notifier.py`: Manages Slack notifications.
- `duty_tracker.json`: Tracks the rotation of lab duties.
- `trigger.sh`: Script for running `main.py` in a scheduled manner.
- `check_and_trigger.sh`: Checks for missed executions and triggers `main.py` if needed.
- `markers/`: Directory where the marker file emissions are stored.
-
## Setup and Operation

### Local Setup

1. Install dependencies from `requirements.txt`.
2. Set up environment variables for Gmail, Slack, and Google Calendar credentials.
    ```bash
    export GMAIL_USER=<email>
    export GMAIL_PASSWORD=<password>
    export SLACK_TOKEN=<token>
    export LAB_MEMBERS_INFO=<json file | base64>
    export GOOGLE_CALENDAR_SERVICE_KEY=<calendar service key | base64>
    ```
3. Move/Generate the `token.pickle` for Google Calendar API on the local machine.

### PythonAnywhere Setup

1. Upload the script files to PythonAnywhere.
2. Set up a scheduled task to run `main.py` daily at 7 AM using cron.
    - Cron file:
      ```bash
      0 7 * * * /home/<username>/lfl-lab-manager/venv/bin/python /home/<username>/lfl-lab-manager/main.py
      ```
3. Ensure `client_secret.json` and `token.pickle` are safely uploaded and handled.

### Handling Authentication

- The script checks the validity of `token.pickle`.
- If re-authentication is required, it sends an email notification.
- Manually update `token.pickle` on PythonAnywhere after re-authenticating locally.

### Mac Setup for Scheduled Execution

For Mac users, a method is provided to ensure `trigger.sh` runs even if the Mac is asleep at the scheduled time:

1. **Marker System**: The `trigger.sh` script creates a daily marker file upon successful execution, indicating the script has run for that day.

2. **Missed Execution Check**: `check_and_trigger.sh` checks for the presence of this marker file. If it's missing (indicating a missed execution), it runs `trigger.sh`.

3. **`launchd` Daemon**: A `launchd` service is set up to run `check_and_trigger.sh` every time the Mac wakes up, ensuring missed executions are caught.

   - Create `com.user.checkandtrigger.plist` in `~/Library/LaunchAgents/` with the following content:
     ```xml
     <?xml version="1.0" encoding="UTF-8"?>
     <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
     <plist version="1.0">
     <dict>
         <key>Label</key>
         <string>com.user.checkandtrigger</string>
         <key>ProgramArguments</key>
         <array>
             <string>/path/to/check_and_trigger.sh</string>
         </array>
         <key>WatchPaths</key>
         <array>
             <string>/var/log/powermanagement</string>
         </array>
         <key>RunAtLoad</key>
         <true/>
     </dict>
     </plist>
     ```
   - Load the `launchd` job:
     ```bash
     launchctl load ~/Library/LaunchAgents/com.user.checkandtrigger.plist
     ```

**Note**: For security, never store sensitive information like lab members' details and service keys in the repository.

## GitHub Actions

The project _can_ be configured to use the GitHub Action defined in `.github/workflows/main.yml` to automate reminders.

## Security

Sensitive information is handled securely, and environment variables are used to store credentials.

---

**Remember to keep the `token.pickle` and `client_secret.json` files secure and handle them carefully during deployment and updates.**
