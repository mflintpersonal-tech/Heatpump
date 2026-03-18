#!/usr/bin/env python3
# daily run of repair_pending
#

from app.query_mysql import Heatpump_db

dbh = Heatpump_db()

dbh.repair_pending()
