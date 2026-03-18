import base64
import os

from hashlib import sha3_512
from pbkdf2 import PBKDF2

class SecurePassword:
    ITERATIONS = 1000
    PWD_BYTES = 32

    @classmethod
    def create(cls, password):

      salt = os.urandom(24)
      base64_salt = base64.b64encode(salt)
      base64_salt = base64_salt.decode("ascii")

      pwd = PBKDF2(password, base64_salt, iterations=cls.ITERATIONS, digest_module=sha3_512)

      base64_bytes = base64.b64encode(pwd.read(cls.PWD_BYTES))
      base64_string = base64_bytes.decode("ascii")

      response = ":".join(["sha3", str(cls.ITERATIONS), base64_salt, base64_string])

      return response

    @classmethod
    def check(cls, full_key, password):

      base64_salt, base64_hash = full_key.split(':')[-2::]
      hash_bytes = base64.b64decode(base64_hash)

      chk = PBKDF2(password, base64_salt, iterations=cls.ITERATIONS, digest_module=sha3_512)

      return (hash_bytes == chk.read(cls.PWD_BYTES))

"""
c = SecurePassword.create('Vc5fe#%a')
print(c)

d = SecurePassword.check(c, 'Vc5fe#%a')
print('match in sp:')
print(d)
"""
