import smtplib
from email.mime.text import MIMEText
SMTP_SERVER = "smtp.mail.yahoo.com"
SMTP_PORT = 587
SMTP_USERNAME = "xiagao1234@yahoo.com"
SMTP_PASSWORD = "88161732@yahoo"
async def send_email(title,message):
    msg = MIMEText(message)
    msg['Subject'] = title
    msg['From'] = "xiagao1234@yahoo.com"
    msg['To'] = "lhongwei_2005@126.com"
    debuglevel = True
    mail = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
    # mail.set_debuglevel(debuglevel)
    mail.starttls()
    mail.login(SMTP_USERNAME, SMTP_PASSWORD)
    mail.sendmail(EMAIL_FROM, EMAIL_TO, msg.as_string())
    mail.quit()
