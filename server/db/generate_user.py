import hashlib
import configparser

md5_pwd = hashlib.md5()
md5_pwd.update('112233'.encode('utf-8'))

userinfo = configparser.ConfigParser()

userinfo.add_section('alex')
userinfo['alex']['username'] = 'alex'
userinfo['alex']['password'] = md5_pwd.hexdigest()
userinfo['alex']['disk_size'] = '1073741824'

userinfo.add_section('egon')
userinfo['egon']['username'] = 'egon'
userinfo['egon']['password'] = md5_pwd.hexdigest()
userinfo['egon']['disk_size'] = '1073741824'

userinfo.add_section('wusir')
userinfo['wusir']['username'] = 'wusir'
userinfo['wusir']['password'] = md5_pwd.hexdigest()
userinfo['wusir']['disk_size'] = '1073741824'

userinfo.write(open('userinfo.ini', 'w'))
