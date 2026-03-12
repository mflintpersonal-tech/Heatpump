#!/usr/bin/env python3

#
# Admin function to add a new user
#

import user as u
import securepassword as sp

username = input("Enter user: ")
username = username.lower()

pwd1 = input("Enter password: ")
pwd1 = pwd1.lower()

pwd2 = input("Re-enter password: ")
pwd2 = pwd2.lower()

print("Adding user...")

error = False
if pwd1 == pwd2:
  if len(pwd1.strip()) < 5:
    error = 'Please use a larger password'
  else:
    hash = sp.SecurePassword.create(pwd1)
    u.User(username).add_user(hash)
    print("User created.")
else:
  error = "Passwords do not match!"

print(error) if error else print("Finished.")
