import logging
import urllib3
import certifi
import json

logger = logging.getLogger('watchtower.common.utils.requests')

class HTTPError(Exception):
    """An error status was returned from the http request"""
    pass

class RequestsUtil:
    def get_multiple(self, urls):
        responses = []
        for url in urls:
            try:
                response = http.get(url, retries=2)
                responses.append(response)
            except:
                pass

        return responses

    def get_multiple_from_dictionary(self, dict):
        for key in dict:
            dict[key]['response'] = http.get(dict[key]['url'], retries=2)
        return dict

class Http:
    def __init__(self):
        self.http = urllib3.PoolManager(cert_reqs='CERT_REQUIRED', ca_certs=certifi.where())

    def get(self, url, params={}, headers={}, retries=urllib3.Retry(3)):
        return self._request('GET', url, params=params, headers=headers, retries=retries)

    def post(self, url, params={}, headers={}, body=None, retries=urllib3.Retry(3)):
        return self._request('POST', url, params=params, headers=headers, body=body, retries=retries)

    def _request(self, method, url, params={}, headers={}, body=None, retries=urllib3.Retry(3)):
        payload = body
        if payload and not isinstance(payload, str):
            payload = json.dumps(payload)

        response = self.http.request(method, url, fields=params, body=payload, retries=retries, headers=headers)
        content_type = response.headers.get('Content-Type')

        # Check for http error
        if response.status < 200 or response.status >= 400:
            r_data = response.data.decode('utf-8').rstrip()

            http_error_msg = ''
            if 400 <= response.status < 500:
                logger.warn(u'%d Client Error: %s for url: %s' % (response.status, r_data, url))
                http_error_msg = u'%d Client Error: %s' % (response.status, r_data)
            elif 500 <= response.status < 600:
                logger.error(u'%d Server Error: %s for url: %s' % (response.status, r_data, url))
                http_error_msg = u'%d Server Error: %s' % (response.status, r_data)

            if http_error_msg:
                raise HTTPError(http_error_msg)

        # Decode json response
        if isinstance(content_type, str) and content_type.startswith('application/json'):
            response.json_data = json.loads(response.data.decode('utf-8'))

        return response

requests_util = RequestsUtil()
http = Http()
