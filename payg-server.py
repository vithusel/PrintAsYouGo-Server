import os
import time
import configparser
import subprocess
import logging
import shutil
import smtplib
import threading  # Import the 'thread' module
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Define the folder to monitor
MONITOR_FOLDER = "Enter Directory"
# Define the CUPS printer name
PRINTER_NAME = "PDF"
# Define SMTP email configuration
SMTP_SERVER = "MailServer
SMTP_PORT = 587
SMTP_USERNAME = "Sender Address"
SMTP_PASSWORD = "Password"
EMAIL_FROM = "Send As Address"
EMAIL_SUBJECT = "Print Job Completed - {file_name}"

SITE_LOCATION = "Location of Server"

# Configure logging
log_file = "print_log.txt"
logging.basicConfig(filename=log_file, level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

class PrintHandler(FileSystemEventHandler):
    def on_created(self, event):
        print(f"Detected event: {event.event_type} - File: {event.src_path}")
        if not event.is_directory:
            file_path = event.src_path
            print(f"Detected file: {file_path}")

            # Check if the file is in the root of the folder
            if os.path.dirname(file_path) == MONITOR_FOLDER:
                if file_path.endswith(".pdf") and not file_path.endswith(".ini"):
                    # Start a new thread to process the file
                    thread = threading.Thread(target=self.process_file, args=(file_path,))
                    thread.start()

    def process_file(self, file_path):
        try:
            # Introduce a 4-second delay before checking for the INI file
            time.sleep(4)

            print(f"Processing file: {file_path}")

            # Check if the file has an associated INI file
            ini_file = f"{file_path}.ini"
            if os.path.exists(ini_file):
                print(f"INI file found: {ini_file}")

                # Read INI settings
                config = configparser.ConfigParser()
                config.read(ini_file)
                page_size = config['PrintSettings'].get('PageSize', 'Letter')
                orientation = config['PrintSettings'].get('Orientation', 'Portrait')
                md5_hash = config['PrintSettings'].get('MD5Hash', '').lstrip('0x')
                color = config['AdvancedSettings'].get('Color', 'Color')
                delay_print_time = config['AdvancedSettings'].get('DelayPrintTime', '')
                full_name = config['Submitter'].get('FullName', '')
                email_address = config['Submitter'].get('EmailAddress', '')

                print(f"Page size: {page_size}")
                print(f"Orientation: {orientation}")
                print(f"MD5 hash: {md5_hash}")
                print(f"Color: {color}")
                print(f"Delay print time: {delay_print_time}")
                print(f"Full name: {full_name}")
                print(f"Email address: {email_address}")

                # Delayed printing if specified
                # if delay_print_time:
                #     current_time = time.strftime("%H:%M:S")
                #     if current_time < delay_print_time:
                #         print(f"File {file_path} will be printed at {delay_print_time}.")
                #         return

                # Set CUPS printing options
                cups_options = [f"-o PageSize={page_size}", f"-o Orientation={orientation}"]
                if color == 'Black and white':
                    cups_options.append("-o ColorModel=Gray")

                # Verify MD5 hash (skip if MD5Hash is not provided)
                if md5_hash:
                    calculated_md5 = subprocess.check_output(["md5sum", file_path]).decode("utf-8").split()[0]
                    if md5_hash.lower() != calculated_md5.lower():
                        error_message = f"MD5 hash mismatch for {file_path}. Skipping print."
                        print(error_message)

                        # Update the .ini file with the error message and status (or create the 'Status' section if it doesn't exist)
                        if 'Status' not in config:
                            config['Status'] = {}
                        config['Status']['error'] = error_message
                        with open(ini_file, 'w') as configfile:
                            config.write(configfile)

                        # Update the .ini file with the error message and status
                        config.set('Status', 'error', error_message)
                        with open(ini_file, 'w') as configfile:
                            config.write(configfile)

                        # Move files to the 'error' subfolder
                        error_folder = os.path.join(MONITOR_FOLDER, 'Error')
                        os.makedirs(error_folder, exist_ok=True)
                        shutil.move(file_path, os.path.join(error_folder, os.path.basename(file_path)))
                        shutil.move(ini_file, os.path.join(error_folder, os.path.basename(ini_file)))

                        # Send an error email to the user
                        if email_address:
                            send_error_email(full_name, email_address, os.path.basename(file_path), SITE_LOCATION, PRINTER_NAME, error_message)

                        return

                # Print the file
                print(f"Printing file: {file_path}")
                try:
                    print_command = ["lp", "-d", PRINTER_NAME] + cups_options + [file_path]
                    subprocess.run(print_command)
                except subprocess.CalledProcessError as print_error:
                    # Handle printing errors here
                    error_message = f"Printing error: {str(print_error)}"
                    print(error_message)

                    # Move files to the 'error' subfolder
                    error_folder = os.path.join(MONITOR_FOLDER, 'Error')
                    os.makedirs(error_folder, exist_ok=True)
                    shutil.move(file_path, os.path.join(error_folder, os.path.basename(file_path)))
                    shutil.move(ini_file, os.path.join(error_folder, os.path.basename(ini_file)))

                    # Update the .ini file with the error message and status
                    config.set('Status', 'error', error_message)
                    with open(ini_file, 'w') as configfile:
                        config.write(configfile)

                    # Send an error email to the user
                    if email_address:
                        send_error_email(full_name, email_address, os.path.basename(file_path), SITE_LOCATION, PRINTER_NAME, error_message)

                    return

                # Move files to the 'complete' subfolder
                complete_folder = os.path.join(MONITOR_FOLDER, 'Complete')
                os.makedirs(complete_folder, exist_ok=True)
                shutil.move(file_path, os.path.join(complete_folder, os.path.basename(file_path)))
                shutil.move(ini_file, os.path.join(complete_folder, os.path.basename(ini_file)))

                # Send email notification for successful printing
                if email_address:
                    send_email_notification(full_name, email_address, os.path.basename(file_path), SITE_LOCATION, PRINTER_NAME)

            else:
                # No associated INI file found
                print(f"No INI file found for {file_path}. Skipping print.")
        except Exception as e:
            # Error occurred during processing
            error_message = str(e)
            print(f"Error processing file {file_path}: {error_message}")

            # Send an error email to the user
            if email_address:
                send_error_email(full_name, email_address, os.path.basename(file_path), SITE_LOCATION, PRINTER_NAME, error_message)


def send_email_notification(full_name, email_address, file_name, location, printer_name):
    try:
        msg = MIMEMultipart()
        msg['From'] = EMAIL_FROM
        msg['To'] = email_address
        msg['Subject'] = EMAIL_SUBJECT.format(file_name=file_name)

        # HTML email template
        html_template = f"""
<html>
<head>
</head>
<body style="font-family: Arial, sans-serif;">
    <div style="text-align: center;">
        <img src="https://vithuselservices.co.uk/images/output-onlinepngtools-p-500.png" alt="Icon" width="100" height="100"> <!-- Replace ICON_URL with the URL of your icon -->
    </div>
    <p style="text-align: center; font-size: 18px;">Hi {full_name},</p>
    <p style="text-align: center; font-size: 16px;">
        Your file <strong>'{file_name}'</strong> has been successfully printed at <strong>{location}</strong> on printer <strong>'{printer_name}'</strong>.
    </p>
    <p style="text-align: center; font-size: 16px;">This is an automated message sent from Print As You Go.</p>
    <p style="text-align: center; font-size: 16px;">If you encounter any issues, please email <a href="mailto:support@vithuselservices.co.uk">support@vithuselservices.co.uk</a></p>
    <p style="text-align: center; font-size: 16px;">Print As You Go is a licensed service provided by Vithusel Services.</p>
</body>
</html>
"""

        body = MIMEText(html_template, 'html')
        msg.attach(body)

        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SMTP_USERNAME, SMTP_PASSWORD)
        server.sendmail(EMAIL_FROM, email_address, msg.as_string())
        server.quit()
        print(f"Email sent to {email_address} for print job.")
    except Exception as e:
        print(f"Error sending email: {str(e)}")

def send_error_email(full_name, email_address, file_name, location, printer_name, error_message):
    try:
        msg = MIMEMultipart()
        msg['From'] = EMAIL_FROM
        msg['To'] = email_address
        msg['Subject'] = f"Print Job Error - {file_name}"

        # HTML email template
        html_template = f"""
<html>
<head>
</head>
<body style="font-family: Arial, sans-serif;">
    <div style="text-align: center;">
        <img src="https://vithuselservices.co.uk/images/output-onlinepngtools-p-500.png" alt="Icon" width="100" height="100"> <!-- Replace ICON_URL with the URL of your icon -->
    </div>
    <p style="text-align: center; font-size: 18px;">Hi {full_name},</p>
    <p style="text-align: center; font-size: 16px;">
        There was an error while processing your file <strong>'{file_name}'</strong> for printing at <strong>{location}</strong> on printer <strong>'{printer_name}'</strong>.
    </p>
    <p style="text-align: center; font-size: 16px;">
        Error Message: <strong>{error_message}</strong>
    </p>
    <p style="text-align: center; font-size: 16px;">This is an automated message sent from Print As You Go.</p>
    <p style="text-align: center; font-size: 16px;">If you encounter any issues, please email <a href="mailto:support@vithuselservices.co.uk">support@vithuselservices.co.uk</a></p>
    <p style="text-align: center; font-size: 16px;">Print As You Go is a licensed service provided by Vithusel Services.</p>
</body>
</html>
"""

        body = MIMEText(html_template, 'html')
        msg.attach(body)

        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SMTP_USERNAME, SMTP_PASSWORD)
        server.sendmail(EMAIL_FROM, email_address, msg.as_string())
        server.quit()
        print(f"Error email sent to {email_address} for print job.")
    except Exception as e:
        print(f"Error sending error email: {str(e)}")

if __name__ == "__main__":
    try:
        print(f"Monitoring folder: {MONITOR_FOLDER}")
        event_handler = PrintHandler()
        observer = Observer()
        observer.schedule(event_handler, path=MONITOR_FOLDER, recursive=False)
        observer.start()

        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
