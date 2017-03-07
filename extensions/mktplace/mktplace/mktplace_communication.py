# Copyright 2016 Intel Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ------------------------------------------------------------------------------
"""
A class to canonicalize communication with the marketplace
"""

import base64
import logging
import urllib2

from gossip.common import json2dict, cbor2dict, dict2json, dict2cbor
from gossip.common import pretty_print_dict
from sawtooth.exceptions import InvalidTransactionError

logger = logging.getLogger(__name__)


class MessageException(Exception):
    """
    A class to capture communication exceptions when accessing the marketplace
    """
    pass


class MarketPlaceCommunication(object):
    """
    A class to encapsulate communication with the market place servers
    """

    GET_HEADER = {"Accept": "application/cbor"}

    def __init__(self, baseurl):
        self.BaseURL = baseurl.rstrip('/').encode('utf-8')
        self.ProxyHandler = urllib2.ProxyHandler({})
        self._cookie = None

    def headrequest(self, path):
        """
        Send an HTTP head request to the validator. Return the result code.
        """

        url = "{0}/{1}".format(self.BaseURL, path.strip('/'))

        logger.debug('get content from url <%s>', url)

        try:
            request = urllib2.Request(url)
            request.get_method = lambda: 'HEAD'
            opener = urllib2.build_opener(self.ProxyHandler)
            if path == '/prevalidation':
                if self._cookie:
                    request.add_header('cookie', self._cookie)
                    self._cookie = None
                else:
                    return "Session is not enabled"
            response = opener.open(request, timeout=30)

        except urllib2.HTTPError as err:
            # in this case it isn't really an error since we are just looking
            # for the status code
            return err.code

        except urllib2.URLError as err:
            logger.warn('operation failed: %s', err.reason)
            raise MessageException('operation failed: {0}'.format(err.reason))

        except:
            logger.warn('no response from server')
            raise MessageException('no response from server')

        return response.code

    def _print_error_information_from_server(self, err):
        if err.code == 400:
            err_content = err.read()
            logger.warn('Error from server, detail information: %s',
                        err_content)

    def getmsg(self, path):
        """
        Send an HTTP get request to the validator. If the resulting content
        is in JSON form, parse it & return the corresponding dictionary.
        """

        url = "{0}/{1}".format(self.BaseURL, path.strip('/'))

        logger.debug('get content from url <%s>', url)

        try:
            request = urllib2.Request(url, headers=self.GET_HEADER)
            opener = urllib2.build_opener(self.ProxyHandler)

            if path == '/prevalidation':
                if self._cookie:
                    request.add_header('cookie', self._cookie)
            response = opener.open(request, timeout=10)

        except urllib2.HTTPError as err:
            logger.warn('operation failed with response: %s', err.code)
            self._print_error_information_from_server(err)
            raise MessageException(
                'operation failed with response: {0}'.format(err.code))

        except urllib2.URLError as err:
            logger.warn('operation failed: %s', err.reason)
            raise MessageException('operation failed: {0}'.format(err.reason))

        except:
            logger.warn('no response from server')
            raise MessageException('no response from server')

        content = response.read()
        headers = response.info()
        response.close()

        encoding = headers.get('Content-Type')

        if encoding == 'application/json':
            value = json2dict(content)
        elif encoding == 'application/cbor':
            value = cbor2dict(content)
        else:
            logger.debug('get content <%s> from url <%s>', content, url)
            return content

        logger.debug(pretty_print_dict(value))
        return value

    def postmsg(self, msgtype, info, path=''):
        """
        Post a transaction message to the validator, parse the returning CBOR
        and return the corresponding dictionary.
        """

        logger.debug(dict2json(info))

        data = dict2cbor(info)
        datalen = len(data)
        url = self.BaseURL + path + msgtype

        logger.debug('post transaction to %s with DATALEN=%d, '
                     'base64(DATA)=<%s>', url, datalen, base64.b64encode(data))

        try:
            request = urllib2.Request(url, data,
                                      {'Content-Type': 'application/cbor',
                                       'Content-Length': datalen})
            opener = urllib2.build_opener(self.ProxyHandler)

            if path == '/prevalidation':
                if self._cookie:
                    request.add_header('cookie', self._cookie)
                response = opener.open(request, timeout=10)
                if not self._cookie:
                    self._cookie = response.headers.get('Set-Cookie')
                    logger.debug('self._cookie %s', self._cookie)
            else:
                response = opener.open(request, timeout=10)

        except urllib2.HTTPError as err:
            logger.warn('operation failed with response: %s', err.code)
            self._print_error_information_from_server(err)
            if err.code == 400:
                err_content = err.read()
                if err_content.find("InvalidTransactionError"):
                    raise InvalidTransactionError("Error from server: {0}"
                                                  .format(err_content))

            raise MessageException(
                'operation failed with response: {0}'.format(err.code))

        except urllib2.URLError as err:
            logger.warn('operation failed: %s', err.reason)
            raise MessageException('operation failed: {0}'.format(err.reason))

        except:
            logger.warn('no response from server')
            raise MessageException('no response from server')

        content = response.read()
        headers = response.info()
        response.close()

        encoding = headers.get('Content-Type')

        if encoding == 'application/json':
            value = json2dict(content)
        elif encoding == 'application/cbor':
            value = cbor2dict(content)
        else:
            logger.info('server responds with message %s of type %s', content,
                        encoding)
            return None

        logger.debug(pretty_print_dict(value))
        return value