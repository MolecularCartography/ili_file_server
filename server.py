from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path, PurePath
from urllib.request import urlopen
from urllib.parse import urlsplit
from os import environ
import sys


LOCAL_DATA_DIR = Path('.') / 'data'
DATA_CHUNK_BYTES = 16384
REMOTE_REQUEST_TIMEOUT_S = 30
ENV_PORT_NAME = 'PORT'
DEFAULT_PORT_NUMBER = 8080
QUERY_SEP = '?'


class Handler(BaseHTTPRequestHandler):
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
        except Exception as e:
            error_text = str(e)
            self.send_error(e.code if hasattr(e, 'code') else 404, error_text if error_text else 'Problem with accessing file: %s' % requested_file_url)

    def _stream_local_file(self, file_path):
        self.send_response(200)
        self.send_header('Content-Type', Handler._detect_mime_type(file_path))
        self.send_header('Content-Length', file_path.stat().st_size)
        self.send_header('Content-Disposition', 'attachment; filename=%s' % file_path.name)
        self.end_headers()
        with open(file_path, 'rb') as requested_file:
            Handler._stream_file(requested_file, self.wfile)

    def _stream_external_file(self, file_url):
        request = urlopen(url=file_url, timeout=REMOTE_REQUEST_TIMEOUT_S)
        self.send_response(200)
        for key, value in request.headers.items():
            self.send_header(key, value)
        if not request.headers.get_content_disposition():
            remote_path = PurePath(urlsplit(file_url).path)
            self.send_header('Content-Disposition', 'attachment; filename=%s' % remote_path.name)
        self.end_headers()
        Handler._stream_file(request, self.wfile)

    def _get_requested_file_url(self):
        try:
            query_sep_pos = self.path.index(QUERY_SEP)
            return self.path[query_sep_pos + 1:]
        except ValueError as e:
            return str()

    @staticmethod
    def _stream_file(file_handler, output):
        while True:
            data = file_handler.read(DATA_CHUNK_BYTES)
            if data:
                output.write(data)
            else:
                break

    @staticmethod
    def _detect_mime_type(path):
        path = path._str.lower()
        if path.endswith(".jpg"):
            mimetype = 'image/jpg'
        elif path.endswith(".png"):
            mimetype = 'image/png'
        elif path.endswith(".csv"):
            mimetype = 'text/csv'
        elif path.endswith('.json'):
            mimetype = 'application/json'
        else:
            mimetype = 'application/octet-stream'
        return mimetype


try:
    port = int(environ.get(ENV_PORT_NAME, DEFAULT_PORT_NUMBER))
    if not ENV_PORT_NAME in environ.keys() and len(sys.argv) > 1:
        port = int(sys.argv[1])
    server = HTTPServer(('', port), Handler)
    print('Started HTTP server on port %d' % port)
    server.serve_forever()
except KeyboardInterrupt:
    print('^C received, shutting down the web server')
    server.socket.close()
