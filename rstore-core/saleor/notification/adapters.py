import json

from saleor import settings
from saleor.notification.interfaces import PushManager
import requests

URL_ALL = 'https://api.webpushr.com/v1/notification/send/all'
URL_SEGMENT = 'https://api.webpushr.com/v1/notification/send/segment'
URL_ATTRIBUTE = 'https://api.webpushr.com/v1/notification/send/attribute'


class Webpushr(PushManager):
    def __init__(self):
        self.webpushr_config = settings.WEBPUSHR_CONFIG
        self.headers = {
            'webpushrKey': self.webpushr_config['WEBPUSHR_KEY'],
            'webpushrAuthToken': self.webpushr_config['WEBPUSHR_AUTH_TOKEN'],
            'Content-Type': 'application/json',
        }

    def send_to_all(self, data):
        notification = {
            "title": data.title,
            "message": data.message,
            "target_url": data.target_url
        }
        return self.notify(URL_ALL, notification)

    def send_to_segment(self, data):
        notification = {
            "title": data.title,
            "message": data.message,
            "target_url": data.target_url,
            "segment": data.segments
        }
        return self.notify(URL_SEGMENT, notification)

    def send_to_target_audience(self, data):
        notification = {
            "title": data.title,
            "message": data.message,
            "target_url": data.target_url,
            "attribute": data.users
        }
        return self.notify(URL_ATTRIBUTE, notification)

    def notify(self, url, notification):
        try:
            response = requests.post(url, headers=self.headers, data=json.dumps(notification))
            return response
        except requests.exceptions.RequestException as e:
            raise e

