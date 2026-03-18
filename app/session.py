#!/usr/bin/env python3

#
# Session class
#

import uuid

from . import query_mysql as db

class Session:

  def __init__(self, user=None, session=None, dbh=None):
      self.user = user
      self.session_id = session
      if dbh is None:
          dbh = db.Heatpump_db()
      self.dbh = dbh
      self.message_id = None

  # create a brand new user session
  def new_session(self):
      self.session_id = str(uuid.uuid4())
      self.message_id = str(uuid.uuid4())
      #print(f"new session has msg id: {self.message_id}")
      self.dbh.insertsession(self.user, self.session_id, self.message_id)

  # update session trail
  def trail(self):
      self.message_id = str(uuid.uuid4())
      #print(f"trail has has msg id: {self.message_id}")
      self.dbh.updatesession(self.user, self.session_id, self.message_id)

  def valid(self, message_id):
      return self.dbh.checksession(self.user, self.session_id, message_id)

  # get session data
  def data(self):
      return self.dbh.readsessiondata(self.user, self.session_id)

  # update session data
  def update(self, hash):
      self.dbh.updatesessiondata(self.user, self.session_id, hash)

  # tidy sessions
  def clean(self, frm):
      self.dbh.deletesessions(frm)

