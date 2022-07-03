# -*- coding: utf-8 -*-

'''A replacement transport for Python xmlrpc library.

pyfldigi note:  Shamelessly borrowed from:

https://github.com/astraw/stdeb/blob/master/stdeb/transport.py

..with a few modifications, mainly to make it python 3 friendly, and to get rid of vestigial cruft.
Oh, and I made it HTTP only because fldigi doesn't support HTTPS as far as I know.
The file was originally released under the MIT license'''

from xmlrpc.client import Transport, ProtocolError
import requests
import requests.utils


class RequestsTransport(Transport):
    """Drop in Transport for xmlrpclib that uses Requests instead of httplib.

    Inherits xml.client.Transport and is meant to be passed directly to xmlrpc.ServerProxy constructor.

    :example:

    >>> import xmlrpc.client
    >>> from transport import RequestsTransport
    >>> s = xmlrpc.client.ServerProxy('http://yoursite.com/xmlrpc', transport=RequestsTransport())
    >>> s.demo.sayHello()
    Hello!

    """
    # change our user agent to reflect Requests
    user_agent = 'Python-xmlrpc with Requests (python-requests.org)'

    def request(self, host, handler, request_body, verbose):
        '''Make an xmlrpc request.'''
        headers = {'User-Agent': self.user_agent, 'Content-Type': 'text/xml'}
        url = self._build_url(host, handler)
        with open('/dev/shm/requests.log', 'a') as f:
            f.write('----- New request ---------\n\n')
            f.write(request_body.decode())
        resp = requests.post(url, data=request_body, headers=headers)
        with open('/dev/shm/requests.log', 'a') as f:
            f.write('\n----- New Reply ---------\n\n')
            try:
                f.write(resp.text)
            except UnicodeEncodeError as ex:
                print(ex)
            f.write('\n----- End Reply ---------\n\n')

        try:
            resp.raise_for_status()
        except requests.RequestException as e:
            print(request_body)
            raise ProtocolError(url, resp.status_code, str(e), resp.headers)
        else:
            return self.parse_response(resp)

    def parse_response(self, resp):
        '''Parse the xmlrpc response.'''
        p, u = self.getparser()  # returns (parser, target)
        p.feed(resp.text)
        p.close()
        return u.close()

    def _build_url(self, host, handler):
        '''Build a url for our request based on the host, handler and use_http property'''
        return 'http://{}{}'.format(host, handler)
