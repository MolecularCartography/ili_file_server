from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path, PurePath
from urllib.request import urlopen
from urllib.parse import urlsplit
from os import environ
from sys import argv
from tarfile import TarFile
from tempfile import TemporaryFile
from zipfile import ZipFile


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
            self._send_headers_for_external_file(response)
            self._stream_file(response)

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
        self.send_header('Content-Type', Handler._detect_mime_type(file_name))
        self.send_header('Content-Length', file_size)
        self.send_header('Content-Disposition', 'attachment; filename=%s' % file_name)
        self.end_headers()

    def _send_headers_for_external_file(self, remote_response):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        for key, value in remote_response.headers.items():
            self.send_header(key, value)
        if not remote_response.headers.get_content_disposition():
            remote_path = PurePath(urlsplit(remote_response.url).path)
            self.send_header('Content-Disposition', 'attachment; filename=%s' % remote_path.name)
        self.end_headers()

    def _get_requested_file_url(self):
        try:
            query_sep_pos = self.path.index(QUERY_SEP)
            return self.path[query_sep_pos + 1:]
        except ValueError as e:
            return str()

    def _stream_file(self, file_handler):
        while True:
            data = file_handler.read(DATA_CHUNK_BYTES)
            if data:
                self.wfile.write(data)
            else:
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
            mimetype = 'application/octet-stream'
        return mimetype


try:
    port = int(environ.get(ENV_PORT_NAME, DEFAULT_PORT_NUMBER))
    if not ENV_PORT_NAME in environ.keys() and len(argv) > 1:
        port = int(argv[1])
    server = HTTPServer(('', port), Handler)
    print('Started HTTP server on port %d' % port)
    server.serve_forever()
except KeyboardInterrupt:
    print('^C received, shutting down the web server')
    server.socket.close()
