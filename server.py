from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path, PurePath
from urllib.request import urlopen
from urllib.parse import quote, unquote, urlsplit
from os import environ
from socketserver import ThreadingMixIn
from sys import argv
from tarfile import TarFile
from tempfile import TemporaryFile
from traceback import print_exc
from zipfile import ZipFile


LOCAL_DATA_DIR = Path('.') / 'data'
DATA_CHUNK_BYTES = 16384
REMOTE_REQUEST_TIMEOUT_S = 30
ENV_PORT_NAME = 'PORT'
DEFAULT_PORT_NUMBER = 8080
QUERY_SEP = '?'
DEFAULT_FILE_TYPE = 'application/octet-stream'


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    pass


class WebRequestHandler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def do_GET(self):
        requested_file_url = self._get_requested_file_url()
        if not requested_file_url:
            self.send_error(400, 'No resource URL is provided')
            return

        requested_file_path = LOCAL_DATA_DIR / requested_file_url
        try:
           is_local_file = requested_file_path.is_file()
        except Exception:
            is_local_file = False

        try:
            if is_local_file:
                self._stream_local_file(requested_file_path)
            else:
                self._stream_external_file(requested_file_url)
        except ConnectionError as e:
            print('Connection error: %s' % e.strerror)
            WebRequestHandler._print_stack_trace()
        except Exception as e:
            error_text = str(e)
            self.send_error(e.code if hasattr(e, 'code') else 404, error_text if error_text else 'Problem with accessing file: %s' % requested_file_url)
            WebRequestHandler._print_stack_trace()

    def _stream_local_file(self, file_path):
        self._send_headers_for_local_file(file_path.name, file_path.stat().st_size)
        with open(file_path, 'rb') as requested_file:
            self._stream_file(requested_file)

    def _stream_external_file(self, file_url):
        response = urlopen(url=file_url, timeout=REMOTE_REQUEST_TIMEOUT_S)

        file_type = response.headers.get_content_type()
        if file_type == 'application/zip':
            self._stream_zipped_data(response.read())
        elif file_type == 'application/x-tar':
            self._stream_tarred_data(response.read())
        else:
            headers = self._send_headers_for_external_file(response)
            content_chunked = WebRequestHandler._is_chunked_transmission(headers)
            self._stream_file(response, content_chunked)

    def _stream_zipped_data(self, data):
        with TemporaryFile() as archive_file:
            archive_file.write(data)
            with ZipFile(archive_file) as zip_file:
                for file_info in zip_file.infolist():
                    if not file_info.is_dir():
                        self._send_headers_for_local_file(file_info.filename, file_info.file_size)
                        with zip_file.open(file_info.filename) as extracted_file:
                            self._stream_file(extracted_file)

    def _stream_tarred_data(self, data):
        with TemporaryFile() as archive_file:
            archive_file.write(data)
            with TarFile(fileobj=archive_file) as tar_file:
                for file_info in tar_file.getmembers():
                    if file_info.isfile():
                        self._send_headers_for_local_file(file_info.name, file_info.size)
                        with tar_file.extractfile(file_info.name) as extracted_file:
                            self._stream_file(extracted_file)

    def _send_headers_for_local_file(self, file_name, file_size):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Content-Type', WebRequestHandler._detect_mime_type(file_name))
        self.send_header('Content-Length', file_size)
        self.send_header('Content-Disposition', 'attachment; filename=%s' % file_name)
        self.end_headers()

    def _send_headers_for_external_file(self, remote_response):
        headers = {}

        header_handlers = {
            'Content-Type': WebRequestHandler._get_content_type_header
        }
        header_handler_keys = {key.lower(): key for key in header_handlers}

        self.send_response(200)
        for key, value in remote_response.headers.items():
            if key.lower() in header_handler_keys:
                value = header_handlers[header_handler_keys[key.lower()]](remote_response)
            self.send_header(key, value)
            headers[key] = value
        missing_headers = self._send_missing_headers_for_external_file(remote_response)
        headers.update(missing_headers)
        self.end_headers()
        return headers

    @staticmethod
    def _print_stack_trace():
        print('\nStack trace:\n')
        print_exc()

    @staticmethod
    def _is_chunked_transmission(headers):
        return any(h.lower() == 'transfer-encoding' and v.lower() == 'chunked' for h, v in headers.items())

    @staticmethod
    def _get_content_type_header(remote_response):
        remote_path = PurePath(urlsplit(remote_response.url).path)
        proposed_content_type = remote_response.headers.get_content_type()
        deduced_content_type = WebRequestHandler._detect_mime_type(remote_path.name)
        return deduced_content_type if deduced_content_type != proposed_content_type and deduced_content_type != DEFAULT_FILE_TYPE else proposed_content_type

    @staticmethod
    def _get_content_disposition_header(remote_response):
        remote_path = PurePath(urlsplit(remote_response.url).path)
        return 'attachment; filename=%s' % remote_path.name

    @staticmethod
    def _get_cors_header(remote_response):
        return '*'

    def _send_missing_headers_for_external_file(self, remote_response):
        missing_header_handlers = {
            'Content-Type': WebRequestHandler._get_content_type_header,
            'Content-Disposition': WebRequestHandler._get_content_disposition_header,
            'Access-Control-Allow-Origin': WebRequestHandler._get_cors_header,
        }
        headers = {}

        existing_keys = set([key.lower() for key in remote_response.headers.keys()])
        for header in missing_header_handlers:
            if not header.lower() in existing_keys:
                value = missing_header_handlers[header](remote_response)
                self.send_header(header, value)
                headers[header] = value
        return headers

    def _get_requested_file_url(self):
        try:
            query_sep_pos = self.path.index(QUERY_SEP)
            requested_url = self.path[query_sep_pos + 1:]
            url_parts = urlsplit(unquote(requested_url))
            scheme = url_parts.scheme + '://' if url_parts.scheme else url_parts.scheme
            query = '?' + url_parts.query if url_parts.query else url_parts.query
            return ''.join((scheme, url_parts.netloc, quote(url_parts.path), query))
        except ValueError as e:
            return str()

    def _stream_file(self, file_handler, chunked_transmission=False):
        while True:
            data = file_handler.read(DATA_CHUNK_BYTES)
            if data:
                payload = b'%X\r\n%s\r\n' % (len(data), data) if chunked_transmission else data
                self.wfile.write(payload)
            else:
                if chunked_transmission:
                    self.wfile.write(b'0\r\n\r\n')
                break

    @staticmethod
    def _detect_mime_type(file_name):
        file_name = file_name.lower()
        if file_name.endswith('.jpg'):
            mimetype = 'image/jpg'
        elif file_name.endswith('.png'):
            mimetype = 'image/png'
        elif file_name.endswith('.csv'):
            mimetype = 'text/csv'
        elif file_name.endswith('.json'):
            mimetype = 'application/json'
        else:
            mimetype = DEFAULT_FILE_TYPE
        return mimetype


try:
    port = int(environ.get(ENV_PORT_NAME, DEFAULT_PORT_NUMBER))
    if not ENV_PORT_NAME in environ.keys() and len(argv) > 1:
        port = int(argv[1])
    server = ThreadedHTTPServer(('', port), WebRequestHandler)
    print('Started HTTP server on port %d' % port)
    server.serve_forever()
except KeyboardInterrupt:
    print('^C received, shutting down the web server')
    server.socket.close()
