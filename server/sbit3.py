#/usr/bin/env python

import json
import datetime
import base64
import hmac, hashlib
import pdb

import tornado.ioloop
import tornado.web

import settings

class MainHandler(tornado.web.RequestHandler):
    def get(self):
        self.write("sbit3 is a webservice that allows you to upload a file from any OSX/Linux machine into S3 and provides a time-limited short URL for access.")

class PostHandler(tornado.web.RequestHandler):
    def _generate_policy_doc(self, conditions, expiration=None):
        if not expiration:
            expiration = datetime.datetime.today() + datetime.timedelta(days=5)
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

    def get(self):
        # TODO: Accept an expiration timestamp on the file and store in sdb
        conditions = { "bucket" : settings.bucket,
                       "acl" : settings.acl,
                       "success_action_redirect" : settings.site_url + "/f" }
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

    def get(self, parameters):
        _key = self.get_argument('key')
        _etag = self.get_argument('etag')
        _short_url = self.sdb_conn.add_file(_key, _etag)
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
        # TODO: Validate request time with expiration in sdb before
        #       generating short URL
        s3_key_name = self.sdb_conn.get_key(shortUrl)[0]
        if s3_key_name:
            self.redirect(self.s3_conn.get_url(s3_key_name))
        else:
            raise tornado.web.HTTPError(404)

application = tornado.web.Application([
    (r"/", MainHandler),
    (r"/u", PostHandler),
    (r"/f(.*)", GenerateUrlHandler),
    (r"/d/(.*)", DownloadHandler),
])


if __name__ == "__main__":
    application.listen(8080)
    tornado.ioloop.IOLoop.instance().start()
