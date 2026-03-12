#!/usr/bin/env python3

#
# User class
#

from . import query_mysql as db

class User:
    INVALID_LIMIT = 3

    def __init__(self, name=None, dbh=None):
      self.name = name
      self.details = None
      self.dbh = dbh or db.Heatpump_db()

    # retrieve user details
    def settings(self):
      if self.details is None:
          self.get_settings()
      return self.details

    # update the user's password with the (valid/secure) hash passed
    def update_password(self, hash):
        self.dbh.updateusershash(self.name, hash)

    def valid_password(self, password):
        shash = self.dbh.usershash(self.name)
        if shash is None:
            return False

        # this user exists ...
        from . import securepassword as sp
        valid = sp.SecurePassword.check(shash, password.lower())

        if valid:
            self.dbh.resetinvalidpwd(self.name)
        else:
            count = self.dbh.userinvalidpwdinc(self.name)
            if count >= self.INVALID_LIMIT:
                raise RuntimeError(f"User {self.name} guessed password wrong too much!")

        return valid

    # add a new user
    def add_user(self, hash):
        self.dbh.adduser(self.name, hash)

    def get_settings(self):
        self.details = self.dbh.usersettings(self.name)


"""
x = User(name='mike')
y = x.valid_password('password')
z = x.valid_password('pafddssword')

print('should be true then false')
print(y)
print(z)
"""
