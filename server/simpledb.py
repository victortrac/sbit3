# SimpleDB connector
import boto
import datetime
import hashlib

from random import random

import settings

class SimpleDBConnection(object):
    def __init__(self, aws_access_id=None, aws_secret_key=None):
        # Used to validate short URLs
        self.charSpace = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
        if not (aws_access_id and aws_secret_key):
            aws_access_id = settings.aws_access_id
            aws_secret_key = settings.aws_secret_key
        try:
            self.conn = boto.connect_sdb(aws_access_id, aws_secret_key)
            self.domain = self._get_domain(settings.sdb_domain)
        except Exception, e:
            raise(e)

    def add_file(self, item, bucket, key, etag):
        try:
            item.add_value('bucket', bucket)
            item.add_value('key', key)
            item.add_value('etag', etag)
            item.add_value('shortUrl', self._make_short_url())
            item.add_value('createTimestamp', datetime.datetime.now())
            item.add_value('downloadCount', 0)
            item.save()
            return item['shortUrl']
        except Exception, e:
            raise(e)

    def add_item(self, item, **values):
        try:
            item = self.domain.new_item(item)
            for _key, _value in values.iteritems():
                item.add_value(_key, _value)
            item.save()
            return item
        except Exception, e:
            raise(e)

    def get_uuid(self, uuid):
        try:
            return self.domain.get_item(uuid)
        except Exception, e:
            raise(e)

    def get_key(self, _url):
        try:
            # Validate url against charspace
            if filter(lambda x: x not in self.charSpace, _url):
                raise Exception("Invalid characters in short URL")
            rs = self.domain.select("SELECT * FROM `%s` where `shortUrl` = '%s'" %
                            (settings.sdb_domain, _url))
            results = []
            for item in rs:
                results.append((item.name, item))
            if len(results) is 1:
                # We only expect one matching result
                return results[0]
            elif len(results) is 0:
                return None
            else:
                raise Exception("More than one matching result found. Possible shortURL collision.")
        except Exception, e:
            raise(e)

    def _get_domain(self, domain):
        try:
            self.domain = self.conn.get_domain(domain)
        except:
            self.domain = self.conn.create_domain(domain)
        finally:
            return self.domain

    def _make_short_url(self):
        try:
            for length in range(4,10):
                tries = 0
                while (tries <= 5):
                    _url = ""
                    while (len(_url) <= length):
                        _url = _url + self.charSpace[int(random() * len(self.charSpace))]
                    _key = self.get_key(_url)
                    if _key == None:
                        return _url
                    else:
                        tries += 1
            raise Exception("Unable to find unique short url")
        except Exception, e:
            raise e

