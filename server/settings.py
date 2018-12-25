import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
print(BASE_DIR)

USERINFO = os.path.join(BASE_DIR, 'db/userinfo.ini')

SHARE_DIR = os.path.join(BASE_DIR, 'share/')

SERVWR_ADDR = ('127.0.0.1', 8081)

