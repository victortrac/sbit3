# S3 connector

import boto

import settings

class S3Connection(object):
    def __init__(self, aws_access_id=None, aws_secret_key=None):
        if not (aws_access_id and aws_secret_key):
            aws_access_id = settings.aws_access_id
            aws_secret_key = settings.aws_secret_key
        try:
            self.conn = boto.connect_s3(aws_access_id, aws_secret_key)
            self.bucket = self.conn.get_bucket(settings.bucket)
        except Exception, e:
            raise(e)

    def get_url(self, key_name):
        _key = self.bucket.get_key(key_name)
        _url = _key.generate_url(60)
        return _url
