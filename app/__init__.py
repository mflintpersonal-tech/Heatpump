from flask import Flask
from flask_talisman import Talisman

from . import config

csp = {
       'default-src': " 'self' ",
       'img-src': " 'self' data: w3.org/svg/2000 ",
       'script-src': " 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://code.jquery.com ",
       'style-src': " 'self' 'unsafe-inline' https://cdn.jsdelivr.net "
      }

app = Flask(__name__)
talisman = Talisman(
                    app,
                    content_security_policy=csp,
                    force_https=False,
                    session_cookie_secure=False,
                    strict_transport_security=False,
                   )

app.config.from_object(config.Config)

app.jinja_env.trim_blocks = True
app.jinja_env.lstrip_blocks = True

from app import routes




