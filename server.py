#!/usr/bin/python
from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer
import os
import sys
import urllib2


LOCAL_DATA_DIR = './data'
DATA_CHUNK_BYTES = 16384
REMOTE_REQUEST_TIMEOUT_S = 30
DEFAULT_PORT_NUMBER = 8080


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        requested_file_path = os.path.join(LOCAL_DATA_DIR, self.path)
        if os.path.isfile(requested_file_path):
            file_size = os.stat(requested_file_path).st_size
            self.send_response(200)
            self.send_header('Content-Type', Handler._detectmimetype(requested_file_path))
            self.send_header('Content-Length', file_size)
            self.end_headers()
            with open(requested_file_path, 'rb') as requested_file:
                Handler._streamfile(requested_file, self.wfile)
        else:
            requested_file_url = self.path
            try:
                request = urllib2.urlopen(url=requested_file_url, timeout=REMOTE_REQUEST_TIMEOUT_S)
                self.send_response(200)
                metadata = request.info()
                for header in metadata.keys():
                    self.send_headers(header, metadata.getheader(header))
                self.end_headers()
                Handler._streamfile(request, self.wfile)
            except Exception as e:
                error_text = unicode(e)
                self.send_error(404, error_text if error_text else 'Problem with accessing file: %s' % requested_file_url)

    @staticmethod
    def _streamfile(file_handler, output):
        while True:
            data = file_handler.read(DATA_CHUNK_BYTES)
            if data:
                output.write(data)
            else:
                break

    @staticmethod
    def _detectmimetype(path):
        path = path.lower()
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
    port = DEFAULT_PORT_NUMBER
    if len(sys.argv) > 1:
        port = int(sys.argv[1])
    server = HTTPServer(('', port), Handler)
    print('Started httpserver on port %d' % port)
    server.serve_forever()
except KeyboardInterrupt:
    print '^C received, shutting down the web server'
    server.socket.close()
