import smtplib
from email.mime.text import MIMEText
SMTP_SERVER = "smtp.mail.yahoo.com"
SMTP_PORT = 587
SMTP_USERNAME = "xiagao1234"
SMTP_PASSWORD = "88161732@yahoo"
EMAIL_FROM = "xiagao1234@yahoo.com"
EMAIL_TO = "lhongwei_2005@126.com"
EMAIL_SUBJECT = "REMINDER:"
co_msg = """
Hello, [username]! Just wanted to send a friendly appointment
reminder for your appointment:
[Company]
Where: [companyAddress]
Time: [appointmentTime]
Company URL: [companyUrl]
Change appointment?? Add Service??
change notification preference (text msg/email)
"""
def send_email():
    msg = MIMEText(co_msg)
    msg['Subject'] = EMAIL_SUBJECT + "Company - Service at appointmentTime"
    msg['From'] = EMAIL_FROM 
    msg['To'] = EMAIL_TO
    debuglevel = True
    mail = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
    mail.set_debuglevel(debuglevel)
    mail.starttls()
    mail.login(SMTP_USERNAME, SMTP_PASSWORD)
    mail.sendmail(EMAIL_FROM, EMAIL_TO, msg.as_string())
    mail.quit()

if __name__=='__main__':
    send_email()