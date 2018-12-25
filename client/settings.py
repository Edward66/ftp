import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

SERVWR_ADDR = ('127.0.0.1', 8081)
DOWNLOAD_DIR = os.path.join(BASE_DIR, 'download')
UPLOAD_DIR = os.path.join(BASE_DIR, 'upload/')
