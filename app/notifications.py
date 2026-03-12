#
# Send a notification to user
#
from datetime import datetime
import os
import redis
import subprocess

from redmail import EmailSender

from app import app

NOTIFY_FORMAT = '%Y%m%d %H%M'

# only message once every 10 minutes at most
MSG_RATE = 60 * 10

class Notifications:

    def __init__(self):

        self.email = EmailSender(
                         host     = app.config['MAIL']['host'],
                         port     = app.config['MAIL']['port'],
                         username = app.config['MAIL']['username'],
                         password = app.config['MAIL']['password']
                     )

    def send(self, types, title, message, urgent=False, key=False, rate=MSG_RATE):
        permitted_types = []

        # don't drown me out with messages!

        with redis.Redis(decode_responses = True) as r:
            rtypes = r.get('Notification:Types') or ''
            permitted_types = set(rtypes.split(','))

            if key:
                msg_key = "NOTIFY_TIME:" + key
            else:
                msg_key = "NOTIFY_TIME:" + ''.join([ s[0] for s in message.split() ])
            if msg_time := r.get(msg_key):
                msg_time = datetime.strptime(msg_time, NOTIFY_FORMAT)        # this is a double-check as redis should expire the key anyway
                if (datetime.now() - msg_time).seconds < rate: return False
            r.set(msg_key, datetime.now().strftime(NOTIFY_FORMAT), ex=rate)

        types = permitted_types & set(types)

        if 'email' in types:
            self.email.headers = {
                                  "X-Mailer": "Home Monitor",
                                  "X-Auto-Response-Suppress": "OOF,DR,AutoReply"
                                 }
            if urgent:
                self.email.headers["Importance"] = "High"
                self.email.headers["X-Priority"] = "1"

            self.email.send(
                            subject   = title,
                            sender    = "Home Monitor <heating_monitor@hardsolutions.co.uk>",
                            receivers = ['mflint@hardsolutions.co.uk'],
                            text      = message
           )

        if 'alexa' in types:
            with redis.Redis(db=15, decode_responses = True) as r:
                token = r.get('ALEXA_TOKEN')

            #os.environ['REFRESH_TOKEN'] = "Atnr|EwICIEP5l1SIHtRzMiBhR2pM7oK2C4W14w0T8EW5CvvvQCDvyLSIzZxukGTS9rdjqJ-dd0r1MJVuRRgcPKyz0ScVCHaj2sYkl75KLOzrEcPqfuoeoMwlRURKkOsaYFWAOgTOOM4CJ2MJX-5m7ogsJkkflx389AjKftjQvDV5rrWDurfwOVuI5aVD5FL6Gmh9QAxKJ-NxterFCo0ZF0C4qfhtFXHfntMM0rFolH3bVx2nlvPol8L_pftAdyqz67msbKzjL--On4uUURJxWz0ndR-kMBRrhyzzC0IyOCdGiT0E0EDMV0otk3zpx67aNAVg29maMeg"
            os.environ['REFRESH_TOKEN'] = token
            os.environ['SPEAKVOL'] = '33'

            msg = message
            if urgent:
                os.environ['SPEAKVOL'] = '45'
                msg = f"URGENT - {message}"
            else:
                # don't announce non-urgent things overnight
                hr = datetime.now().hour
                if (hr >= 23) or (hr <= 6):
                    return True

            #response = subprocess.run(['./sbin/alexa_remote_control.sh', '-d', 'Everywhere', '-e', f'speak:"{msg}"'], stdout=subprocess.PIPE).stdout.decode('utf-8')
            response = subprocess.run(['./sbin/alexa_remote_control.sh', '-d', 'Lounge', '-e', f'speak:"{msg}"'], stdout=subprocess.PIPE).stdout.decode('utf-8')
            #print(response)
            with open("/var/www/heatpump/alexa.log", "a") as f:
                f.write(datetime.now().strftime('%Y-%m-%d %H:%M:%S')+"\n")
                f.write(msg+"\n")
                f.write(response+"\n")


if __name__ == "__main__":
    x = Notifications()
    #x.send('email', 'My Subject', 'Something bad has happened', urgent=True)
    #x.send('email', 'My Other Subject', 'Something dull has happened')
    x.send(['alexa'], 'Ignored bit', "Send flowers to them all", urgent=True)
