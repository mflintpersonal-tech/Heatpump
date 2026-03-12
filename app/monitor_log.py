#!/usr/bin/env python3

import logging

from . import app

FORMAT = '[%(asctime)s#%(process)d] %(levelname)s -- : [%(module)s:%(lineno)03d] %(message)s'
    
loggr = logging
loggr.basicConfig(
            format = FORMAT,
            level=logging.INFO,
            filename = app.config['APP_LOG'])
