import socket
import os
import hashlib
import struct
import json

from settings import SERVWR_ADDR, DOWNLOAD_DIR, UPLOAD_DIR


class FtpClient:
    addr_family = socket.AF_INET
    addr_type = socket.SOCK_STREAM
    max_packet_size = 8096
    coding = 'utf-8'

    def __init__(self, server_addr, bind_and_activate=True):
        self.server_addr = server_addr
        self.client = socket.socket(self.addr_family, self.addr_type)

    def client_connect(self):
        self.client.connect(self.server_addr)

    def clinet_close(self):
        self.client.close()

    def user_verify(self):
        while True:
            # 发送用户名和密码
            print('请输入用户名或密码，退出请按q')
            username = input('username:').strip()
            if not username: continue
            if username.lower() == 'q':
                self.client.send('8888'.encode(self.coding))
                break
            password = input('password:').strip()
            if not password: continue
            if password.lower() == 'q':
                self.client.send('8888'.encode(self.coding))
                break
            user_header = struct.pack('i', len(username))
            pwd_header = struct.pack('i', len(password))
            self.client.send(user_header)
            self.client.send(pwd_header)
            self.client.send(username.encode(self.coding))
            self.client.send(password.encode(self.coding))

            # 接收是否验证成功
            verify_status = self.client.recv(4).decode(self.coding)
            if verify_status == '1000':  # 1000 登陆成功
                print('登陆成功')
                self.current_path = username
                return True
            elif verify_status == '1001':
                print('密码错误')
            else:
                print('用户名不存在')  # 1001 用户名或密码错误

    def show_progress(self, has, total):
        rate = float(has) / float(total)
        rate_num = int(rate * 100)
        print('\r%s%% %s' % (rate_num, '#' * rate_num), end='')

    def md5_verify(self, server_md5, recv_size):
        client_md5 = hashlib.md5()
        client_md5.update(str(recv_size).encode(self.coding))

        if not client_md5.hexdigest() == server_md5:
            return '文件校验失败，文件已被篡改或下载的文件不完整'
        else:
            return 'ok'

    @staticmethod
    def convert_md5(words):
        md5 = hashlib.md5()
        md5.update(words)
        swiched = md5.hexdigest()
        return swiched

    def recv_file(self, filename, filesize, server_md5, has_size=0):
        with open('%s/%s' % (DOWNLOAD_DIR, filename), 'wb') as f:
            f.seek(has_size)
            while has_size < filesize:
                line = self.client.recv(self.max_packet_size)
                f.write(line)
                has_size += len(line)
                self.show_progress(has_size, filesize)
            print('\r下载完成')
        md5_status = self.md5_verify(server_md5, has_size)
        if md5_status is not 'ok':
            print(md5_status)

    def upload_file(self, filename, filesize, has_size=0):
        with open(os.path.join(UPLOAD_DIR, filename), 'rb') as f:
            f.seek(has_size)
            for line in f:
                self.client.send(line)
                has_size += len(line)
                self.show_progress(has_size, filesize)
        put_status = self.client.recv(4).decode(self.coding)
        if put_status == '3000':
            print('\r文件上传成功')
        else:
            print('文件校验失败，文件已被篡改或上传的文件不完整')

    def run(self):
        self.client_connect()
        status = self.user_verify()
        if status:
            while True:
                inp = input('[%s]' % self.current_path).strip()
                if not inp: continue
                cmds = inp.split()
                cmd = cmds[0]
                if hasattr(self, cmd):
                    func = getattr(self, cmd)
                    func(inp)
                else:
                    print('指令有误')

    def put(self, cmds):
        filename = cmds.split()[1]
        if not os.path.isfile(os.path.join(UPLOAD_DIR, filename)):
            print('上传的文件%s不存在' % filename)
        else:
            self.client.send(cmds.encode(self.coding))
            filesize = os.path.getsize(os.path.join(UPLOAD_DIR, filename))
            filesize_bytes = str(filesize).encode(self.coding)
            filesize_md5 = self.convert_md5(filesize_bytes)
            header_dict = {
                'filename': filename,
                'md5': filesize_md5,
                'filesize': filesize
            }

            header_json = json.dumps(header_dict)
            header_bytes = header_json.encode(self.coding)
            self.client.send(struct.pack('i', len(header_bytes)))
            self.client.send(header_bytes)

            server_info = self.client.recv(4).decode(self.coding)
            if server_info == '4001':
                print('空间不足')
            elif server_info == '5001':
                while True:
                    choice = input('文件已存在\n继续以前的上传请按 1\n重新上传请按 2\n>>>').strip()
                    if not choice: continue
                    if choice.isdigit() and choice == '1':
                        self.client.send(choice.encode(self.coding))
                        dict_len = struct.unpack('i', self.client.recv(4))[0]
                        size_json = self.client.recv(dict_len).decode('utf-8')
                        size_dict = json.loads(size_json)
                        has_size = size_dict['has_size']
                        self.upload_file(filename, filesize, has_size)
                        break
                    elif choice.isdigit() and choice == '2':
                        self.client.send(choice.encode(self.coding))
                        self.upload_file(filename, filesize)
                        break
                    else:
                        print('指令有误，请重新输入')
            else:
                self.upload_file(filename, filesize)

    def get(self, cmds):
        filename = cmds.split()[1]
        self.client.send(cmds.encode(self.coding))
        server_info = self.client.recv(4)
        if server_info.decode(self.coding) == '2001':
            print('要下载的文件%s不存在' % filename)
            return

        header_size = struct.unpack('i', server_info)[0]
        header_json = self.client.recv(header_size).decode(self.coding)
        header_dict = json.loads(header_json)
        filesize = header_dict['filesize']
        server_md5 = header_dict['md5']

        while True:
            if os.path.exists(os.path.join(DOWNLOAD_DIR, filename)):
                choice = input('文件已存在\n继续以前的下载请按 1\n重新下载请按 2\n>>>').strip()
                if not choice: continue
                if choice.isdigit() and choice == '1':
                    has_size = os.path.getsize(os.path.join(DOWNLOAD_DIR, filename))
                    size_dict = {'has_size': has_size}
                    size_json = json.dumps(size_dict)
                    size_bytes = size_json.encode(self.coding)
                    self.client.send(choice.encode(self.coding))
                    self.client.send(struct.pack('i', len(size_bytes)))
                    self.client.send(size_bytes)
                    self.recv_file(filename, filesize, server_md5, has_size=has_size)
                    break

                elif choice.isdigit() and choice == '2':
                    self.client.send(choice.encode(self.coding))
                    self.recv_file(filename, filesize, server_md5)
                    break
                else:
                    print('输入不合法请重新输入')
            else:
                self.client.send('3'.encode(self.coding))  # 文件不存在
                self.recv_file(filename, filesize, server_md5)
                break

    def ls(self, cmds):
        self.client.send(cmds.encode(self.coding))
        info = self.client.recv(self.max_packet_size).decode(self.coding)
        print(info)

    def cd(self, cmds):
        self.client.send(cmds.encode(self.coding))
        server_info = self.client.recv(self.max_packet_size).decode(self.coding)
        if server_info == '7001':
            print('目录不存在')
        elif server_info == '7002':
            print('到顶层了')
        else:
            self.current_path = server_info


client = FtpClient(SERVWR_ADDR)
client.run()
