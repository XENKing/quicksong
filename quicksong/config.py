import json
import platform
import re
import time
from base64 import b85encode, b85decode
from getpass import getpass
from pathlib import Path
from typing import MutableMapping

from secret import PROGRAM_SECRET, OFFSET_SECRET
from vinanti import Vinanti


def regex_file_check(value):
    check_str = r"^([^\x00-\x1F!\"$'\(\)*,\/:;<>\?\[\\\]\{\|\}\x7F]+)\.([a-zA-Z0-9]*)$"
    return re.match(check_str, value)


def default_dir(name):
    from inspect import getframeinfo, currentframe
    run_file = getframeinfo(currentframe()).filename
    path: Path = Path(run_file).resolve().parent

    return path.joinpath(name)


def get_ip():
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # doesn't even have to be reachable
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP


def get_sig():
    import hashlib
    info = platform.uname()
    sig = ''.join(str(el) for el in [info.node, info.machine, info.system, info.processor, get_ip(), PROGRAM_SECRET])
    return hashlib.md5(sig.encode('utf-8')).hexdigest()


def password_encode(password: str):
    from random import randint
    shift = randint(12, 24)
    secret_length = randint(10, 20)
    from secrets import token_hex
    secret = token_hex(secret_length)

    hashed_password = password.join([secret[:(len(secret) - shift)], secret[(len(secret) - shift):]])
    encode_str = str(str(len(secret)) + hashed_password + str(shift))
    return b85encode(str(
        encode_str[len(encode_str) - OFFSET_SECRET:] + encode_str[:len(encode_str) - OFFSET_SECRET]).encode()).decode()


def password_decode(password: str, sig: str):
    if sig != get_sig():
        return None
    decoded_str = b85decode(password.encode()).decode()
    decoded_password = str(decoded_str[OFFSET_SECRET:] + decoded_str[:OFFSET_SECRET])
    shift = int(decoded_password[-2:])
    secret_len = int(decoded_password[:2]) + 2

    return decoded_password[abs(secret_len - shift): - abs(secret_len - (secret_len - shift) + 2)]


class Config(MutableMapping):
    def __delitem__(self, key):
        del self.__dict__[key]

    def __len__(self):
        return len(self.__dict__)

    def __iter__(self):
        return iter(self.__dict__)

    def __init__(self, path=None):
        self.file = path
        self.open()

    def __getitem__(self, key):
        return self.__dict__[key] if key in self.__dict__ else None

    def __setitem__(self, key, value):
        value_path = self.if_path(self, key, value)
        if value_path:
            self.__dict__[key] = value_path
            self.dump()
            return
        del value_path
        value_file = self.if_file(self, key, value)
        if value_file:
            self.__dict__[key] = value_file
            self.dump()
            return
        del value_file
        if "path" not in key and "file" not in key and value:
            self.__dict__[key] = value
            self.dump()

    def path(self):
        return self.file

    def update(self, __m, **kwargs):
        for key, value in __m.items():
            self.__setitem__(key, value)

    def create(self):
        print("Enter your login and password to osu.ppy.sh")
        username = input("Login:")
        password = None
        while not password:
            password = getpass("Password:")
        self.update({'password': password, 'username': username})
        del username, password
        if self.dump():
            print("User config successfully created")
            return True
        return False

    def dump(self, encrypt_pass=True):
        config = {k: str(v) for k, v in self.__dict__.items()}

        if encrypt_pass:
            config["signature"] = get_sig()
            config.update({"password": password_encode(config['password'])})

        with open(self.file, 'w', encoding="utf8") as file:
            try:
                json.dump(config, file, ensure_ascii=False)
                del config
            except ValueError as e:
                print('Failed to write config: ', e)
                return False
            else:
                return True

    def open(self):
        if not self.file:
            path = default_dir("user.cfg")
            print('Config file not provided, using default: {}'.format(path))
            self.file = path
            if path.exists() and path.is_file():
                if self.load():
                    return True
            else:
                return self.create()

        path: Path = Path(self.file).resolve(strict=True)
        if path.exists():
            if path.is_file():
                self.file = path
                if self.load():
                    return True
            elif path.is_dir():
                self.file = path.joinpath("user.cfg")
                if self.load():
                    return True

        return False

    def load(self, decrypt_pass=True):
        with open(self.file, encoding="utf8") as file:
            try:
                config = json.load(file)
                if decrypt_pass:
                    config.update({'password': password_decode(config['password'], config['signature'])})
            except ValueError as e:
                print('Failed to load config: ', e)
                return False
            else:
                self.__dict__.update(config)
                return True

    def check_expires_cookie(self):
        timestamp = time.time()
        expires = self['cookie_exp_time']
        return expires and float(expires) > timestamp + 259200

    def set_cookie_callback(self, *args):
        self['osu_cookie'] = args[-1].session_cookies
        exp_date = re.search(r'expires=([^;]*);', args[-1].info._headers[10][1])
        self['cookie_exp_time'] = time.mktime(time.strptime(exp_date.group(1), "%a, %d-%b-%Y %H:%M:%S GMT"))

    def request_cookie(self):
        cookies_hdrs = {
            'authorization': "Basic eGVua2luZzoxOTI4Mzc0NjUwYXNk",
            'content-type': "application/x-www-form-urlencoded",
            'charset': "UTF-8",
        }
        payload = {'username': self['username'], 'password': self['password']}
        vnt_cookies = Vinanti(block=True, hdrs={"User-Agent": "Mozilla/5.0"}, multiprocess=True, session=True,
                              timeout=60)
        vnt_cookies.post('https://osu.ppy.sh/session', onfinished=self.set_cookie_callback, hdrs=cookies_hdrs,
                         data=payload)

    def get_cookie(self):
        if self.check_expires_cookie():
            return self['osu_cookie']
        else:
            self.request_cookie()
            return self.get_cookie()

    @staticmethod
    def if_path(config, key, value):
        if "path" not in key:
            return None
        path = None
        default_path = None
        if "songs" in key:
            default_path = Path.home().joinpath("AppData\\Local\\osu!\\Songs")
        else:
            default_path = Path.home().joinpath('Downloads')
        if value is None and key in config.__dict__ and Path(config.__dict__[key]).exists():
            return None
        if type(value) is str and Path(value).exists():
            path: Path = Path(value).resolve(strict=True)
            if path.is_dir():
                return str(path)
        if not path:
            return str(default_path)

    @staticmethod
    def if_file(config, key, value):
        if "file" not in key:
            return None

        default_path = default_dir('file.cfg')
        if value is None:
            if key in config.__dict__ and Path(config.__dict__[key]).exists():
                return None
        if type(value) is not str:
            return None
        file_path = None
        try:
            file_path: Path = Path(value).resolve(strict=True)
        except FileNotFoundError:
            if regex_file_check(value):
                file_path = default_dir(value)
                return str(file_path)
        else:
            if file_path.is_file():
                if regex_file_check(value):
                    file_path = default_dir(value)
                    return str(file_path)
                else:
                    file_path = None

        if not file_path:
            return str(default_path)
