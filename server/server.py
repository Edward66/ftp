import os
import socket
import struct
import json
import configparser
import hashlib

from settings import USERINFO, SHARE_DIR, SERVWR_ADDR


class FtpServer:
    addr_family = socket.AF_INET
    socket_type = socket.SOCK_STREAM
    allow_resue_address = False
    max_packet_size = 8096
    coding = 'utf-8'
    listen_num = 5

    def __init__(self, server_addr, connect=True):
        self.server_addr = server_addr
        self.server = socket.socket(self.addr_family, self.socket_type)

    def server_bind(self):
        if self.allow_resue_address:
            self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server.bind(self.server_addr)
        self.server.listen(self.listen_num)

    def server_close(self):
        self.server.close()

    def get_request(self):
        return self.server.accept()

    def close_request(self, request):
        request.close()

    @staticmethod
    def convert_md5(bytes):
        md5 = hashlib.md5()
        md5.update(bytes)
        swiched = md5.hexdigest()
        return swiched

    def user_verify(self, conn):
        while True:
            user_obj = conn.recv(4)
            pwd_obj = conn.recv(4)
            if not user_obj or not pwd_obj:
                print('客户端挂断')
                break
            if user_obj.decode(self.coding) == '8888' or pwd_obj.decode(self.coding) == '8888':
                print('客户端挂断')
                break
            user_len = struct.unpack('i', user_obj)[0]
            pwd_len = struct.unpack('i', pwd_obj)[0]
            username = conn.recv(user_len).decode(self.coding)
            pwd_bytes = conn.recv(pwd_len)
            password = self.convert_md5(pwd_bytes)
            userinfo = configparser.ConfigParser()
            userinfo.read(USERINFO)
            try:
                if username == userinfo[username]['username'] and password == userinfo[username]['password']:
                    conn.send('1000'.encode(self.coding))  # 1000 登陆成功
                    self.current_path = os.path.join(SHARE_DIR, username)
                    return username
                else:
                    conn.send('1001'.encode(self.coding))  # 密码错误
            except KeyError:
                conn.send('1002'.encode(self.coding))  # 用户名不存在

    def send_file(self, conn, username, filename, has_size=0):
        try:
            with open(os.path.join(SHARE_DIR, '%s/%s' % (username, filename)), 'rb') as f:
                f.seek(has_size)
                for line in f:
                    conn.send(line)
        except BrokenPipeError:
            print('用户%s下载断开' % username)

    def verify_md5(self, conn, client_md5, recv_size):
        server_md5 = hashlib.md5()
        server_md5.update(str(recv_size).encode(self.coding))
        if not server_md5.hexdigest() == client_md5:
            conn.send('3001'.encode(self.coding))  # 文件上传成功但md5校验失败
        else:
            conn.send('3000'.encode(self.coding))  # 文件上传成功

    @staticmethod
    def getSize(user_path, size=0):
        for root, dirs, files in os.walk(user_path):
            for f in files:
                size += os.path.getsize(os.path.join(root, f))
            return size

    def verify_amount(self, conn, username, filesize):
        filesize = int(filesize)
        user_path = os.path.join(SHARE_DIR, username)
        used_size = self.getSize(user_path, 0)
        userinfo = configparser.ConfigParser()
        userinfo.read(USERINFO)
        disk_size = int(userinfo[username]['disk_size'])
        if (filesize + used_size) > disk_size:
            conn.send('4001'.encode(self.coding))
            return False
        else:
            return True

    def recv_file(self, conn, username, filename, filesize, client_md5, has_size=0):
        with open(os.path.join(SHARE_DIR, "%s/%s" % (username, filename)), 'wb') as f:
            f.seek(has_size)
            while has_size < filesize:
                line = conn.recv(self.max_packet_size)
                if not line:
                    print('客户%s断开' % username)
                    return
                f.write(line)
                has_size += len(line)
        self.verify_md5(conn, client_md5, has_size)

    def run(self):
        self.server_bind()
        print('服务器开启')
        while True:
            conn, client_addr = self.get_request()
            print(client_addr)
            username = self.user_verify(conn)
            if username is None: continue
            while True:
                try:
                    res = conn.recv(self.max_packet_size)
                except ConnectionResetError:
                    print('用户%s异常断开' % username)
                else:
                    if not res: break
                    cmds = res.decode(self.coding)
                    cmd = cmds.split()[0]
                    if hasattr(self, cmd):
                        func = getattr(self, cmd)
                        func(conn, username, cmds)

    def put(self, conn, username, cmds):
        filename = cmds.split()[1]
        header_struct = conn.recv(4)
        header_size = struct.unpack('i', header_struct)[0]
        header_bytes = conn.recv(header_size)
        header_json = header_bytes.decode(self.coding)
        header_dict = json.loads(header_json)
        filesize = header_dict['filesize']
        client_md5 = header_dict['md5']

        disk_status = self.verify_amount(conn, username, filesize)
        if disk_status is True:
            if os.path.exists(os.path.join(SHARE_DIR, '%s/%s' % (username, filename))):
                conn.send('5001'.encode(self.coding))  # 文件已存在
                is_reupload = conn.recv(1).decode(self.coding)
                if is_reupload == '1':
                    has_size = os.path.getsize(os.path.join(SHARE_DIR, '%s/%s' % (username, filename)))
                    size_dict = {'has_size': has_size}
                    size_json = json.dumps(size_dict)
                    size_bytes = size_json.encode(self.coding)
                    conn.send(struct.pack('i', len(size_bytes)))
                    conn.send(size_bytes)
                    self.recv_file(conn, username, filename, filesize, client_md5, has_size=has_size)

                if is_reupload == '2':
                    self.recv_file(conn, username, filename, filesize, client_md5, has_size=0)

            else:
                conn.send('6000'.encode(self.coding))  # 文件不存在，直接开始下载
                self.recv_file(conn, username, filename, filesize, client_md5, has_size=0)

    def get(self, conn, username, cmds):
        filename = cmds.split()[1]
        if not os.path.isfile(os.path.join(SHARE_DIR, '%s/%s' % (username, filename))):
            conn.send('2001'.encode(self.coding))  # 2001 文件不存在
        else:
            filesize = os.path.getsize(os.path.join(SHARE_DIR, '%s/%s' % (username, filename)))
            filesize_bytes = str(filesize).encode(self.coding)
            file_md5 = self.convert_md5(filesize_bytes)
            header_dict = {
                'filename': filename,
                'md5': file_md5,
                'filesize': filesize
            }
            header_json = json.dumps(header_dict)
            header_bytes = header_json.encode(self.coding)
            conn.send(struct.pack('i', len(header_bytes)))
            conn.send(header_bytes)

            is_exsits = conn.recv(1).decode(self.coding)
            if is_exsits == '1':
                bytes_len = struct.unpack('i', conn.recv(4))[0]
                size_bytes = conn.recv(bytes_len)
                size_json = size_bytes.decode(self.coding)
                size_dict = json.loads(size_json)
                has_size = size_dict['has_size']
                self.send_file(conn, username, filename, has_size=has_size)
            else:
                self.send_file(conn, username, filename)

    def ls(self, conn, username, cmds):
        file_list = os.listdir(self.current_path)
        file_str = '\n'.join(file_list)
        if not file_list:
            conn.send('目录不存在'.encode(self.coding))  # 目录不存在
        conn.send(file_str.encode(self.coding))

    def cd(self, conn, username, cmds):

        dirname = cmds.split()[1]
        if not os.path.exists(os.path.join(self.current_path, dirname)):
            conn.send('7001'.encode(self.coding))
            return
        user_path = os.path.join(SHARE_DIR, username)
        if dirname == '..':
            if self.current_path == user_path:
                conn.send('7002'.encode(self.coding))  # 到顶层了
            else:
                self.current_path = os.path.dirname(self.current_path)
                basename = os.path.basename(self.current_path)
                conn.send(basename.encode(self.coding))
        else:
            self.current_path = os.path.join(self.current_path, dirname)
            conn.send(dirname.encode(self.coding))


server = FtpServer(SERVWR_ADDR)
server.allow_resue_address = True
server.run()
