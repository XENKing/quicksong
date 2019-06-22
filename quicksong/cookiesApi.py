import pickle
from pathlib import Path

import requests
import requests.cookies

import config as cfg


def check_expires_cookies(cookies):
    import time
    timestamp = time.time()
    expires = None
    for cookie in cookies:
        if cookie.name == 'osu_session':
            expires = cookie.expires
    if expires < timestamp + 86400 * 3:
        return True
    return False


class CookiesApi(object):
    def __init__(self, config_file=None, cookies_file=None):
        if isinstance(config_file, cfg.Config):
            self._config = config_file
        else:
            self._config = cfg.Config(config_file)
        if cookies_file:
            self._config.update({'cookies_file': cookies_file})
        self._cookies = self.load()

    @property
    def cookies(self):
        return self._cookies

    @cookies.getter
    def get_cookies(self):
        return self._cookies

    def save(self, cookies):
        with open(self._config['cookies_file'], 'wb') as file:
            file.truncate()
            pickle.dump(cookies._cookies, file)

    def load(self):
        if 'cookies_file' not in self._config or not Path(self._config['cookies_file']).exists():
            self._config.update({'cookies_file': "osu.cookies"})
            print('Cookies file not provided, using default: {}'.format(self._config['cookies_file']))
            try:
                path: Path = Path(self._config['cookies_file']).resolve(strict=True)
            except FileNotFoundError:
                return self.get()
            else:
                if not (path.exists() and path.is_file()):
                    return self.get()

        with open(self._config['cookies_file'], "rb") as file:
            cookies = pickle.load(file)
            if cookies:
                jar = requests.cookies.RequestsCookieJar()
                jar._cookies = cookies
                if check_expires_cookies(jar):
                    print("Your cookies has been expired")
                    return self.get()
                return jar
        return False

    def get(self):
        session = requests.Session()

        url = "https://osu.ppy.sh/session"

        payload = "username=" + self._config['username'] + "&password=" + self._config['password']
        headers = {
            'authorization': "Basic eGVua2luZzoxOTI4Mzc0NjUwYXNk",
            'content-type': "application/x-www-form-urlencoded",
            'charset': "UTF-8",
        }
        print("Getting cookies from osu!site")
        request = requests.Request("POST", url, data=payload, headers=headers)
        prepared_request = session.prepare_request(request)

        settings = session.merge_environment_settings(prepared_request.url, None, None, None, None)
        response = session.send(prepared_request, **settings)

        self.save(response.cookies)
        return response.cookies
