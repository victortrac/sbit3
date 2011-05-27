#/usr/bin/env python

import json
import datetime
import base64
import hmac, hashlib
import uuid

import tornado.ioloop
import tornado.web

import settings

class MainHandler(tornado.web.RequestHandler):
    def get(self):
        self.write("sbit3 is a webservice that allows you to upload a file from any OSX/Linux machine into S3 and provides a time-limited short URL for access.")

class PostHandler(tornado.web.RequestHandler):
    def _generate_policy_doc(self, conditions, expiration=None):
        if not expiration:
            # Sets a policy of 15 minutes to upload file
            expiration = datetime.datetime.today() + datetime.timedelta(minutes=15)
        conditions = [ { "bucket" : conditions["bucket"] },
                       [ "starts-with", "$key", "uploads/"],
                       { "acl" : conditions["acl"] },
                       { "success_action_redirect" : conditions["success_action_redirect"] } ]
        conditions_json = json.dumps({ "expiration" : expiration.strftime("%Y-%m-%dT%M:%H:%SZ"),
                                       "conditions" : conditions })
        return base64.b64encode(conditions_json)

    def _sign_policy(self, policy):
        signature = base64.b64encode(hmac.new(settings.aws_secret_key, policy, hashlib.sha1).digest())
        return signature

    def get(self, expiration):
        try:
            expiration = int(expiration)
            # Set max expiration to 7200 minutes (5 days)
            if not 0 < expiration < 7200:
                raise tornado.web.HTTPError(403)
            _expireTimestamp = datetime.datetime.now() + datetime.timedelta(minutes=expiration)
        except ValueError:
            raise tornado.web.HTTPError(403)

        # Associate _uuid to expiration in sdb
        from simpledb import SimpleDBConnection
        self.sdb_conn = SimpleDBConnection()

        _uuid = uuid.uuid4().hex
        self.sdb_conn.add_item(_uuid, expireTimestamp=_expireTimestamp)

        conditions = { "bucket" : settings.bucket,
                       "acl" : settings.acl,
                       "success_action_redirect" : settings.site_url + "/f/" + _uuid }
        policy_document = self._generate_policy_doc(conditions)
        signature = self._sign_policy(policy_document)

        self.render("post.html", conditions=conditions,
                                 aws_access_id=settings.aws_access_id,
                                 policy_document=policy_document,
                                 signature=signature)

class GenerateUrlHandler(tornado.web.RequestHandler):
    def __init__(self, application, request, **kwargs):
        super(GenerateUrlHandler, self).__init__(application, request, **kwargs)
        from simpledb import SimpleDBConnection
        self.sdb_conn = SimpleDBConnection()

    def get(self, _uuid):
        # Check uuid
        if _uuid.isalnum() and len(_uuid) == 32:
            item = self.sdb_conn.get_uuid(_uuid)
        else:
            raise tornado.web.HTTPError(403)

        _bucket = self.get_argument('bucket')
        _key = self.get_argument('key')
        _etag = self.get_argument('etag')

        _short_url = self.sdb_conn.add_file(item, _bucket, _key, _etag)
        self.write(settings.site_url + '/d/' + _short_url)

class DownloadHandler(tornado.web.RequestHandler):
    def __init__(self, application, request, **kwargs):
        super(DownloadHandler, self).__init__(application, request, **kwargs)
        from simpledb import SimpleDBConnection
        from s3 import S3Connection
        self.sdb_conn = SimpleDBConnection()
        self.s3_conn = S3Connection()
        self.bucket = settings.bucket

    def get(self, shortUrl):
        s3info = self.sdb_conn.get_key(shortUrl)
        if s3info:
            s3_key_name = s3info[1]['key']
            s3_expiration = s3info[1]['expireTimestamp']
            if datetime.datetime.now() < datetime.datetime.strptime(s3_expiration, "%Y-%m-%d %H:%M:%S.%f"):
                self.redirect(self.s3_conn.get_url(s3_key_name))
            else:
                raise tornado.web.HTTPError(403)
        else:
            raise tornado.web.HTTPError(404)

application = tornado.web.Application([
    (r"/", MainHandler),
    (r"/u/(\d+)", PostHandler),
    (r"/f/(.*)", GenerateUrlHandler),
    (r"/d/(.*)", DownloadHandler),
])


if __name__ == "__main__":
    application.listen(settings.site_url)
    tornado.ioloop.IOLoop.instance().start()
