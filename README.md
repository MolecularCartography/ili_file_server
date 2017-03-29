# \`ili File Server
Lightweight web-service for external files retrieval by [the \`ili app](https://github.com/MolecularCartography/ili)

## What is it?

The file server is a small python-based server-side application that accepts requests in format `http://this.server.org/?<external_file_URL>` and forwards the requested file to the caller. External files can be acessible over HTTP(S) or FTP protocols. The remote resource should support cross-origin access.

The server is being developed by [Alexandrov Team](http://www.embl.de/research/units/scb/alexandrov/index.html) at EMBL Heidelberg ([contact information](http://www.embl.de/research/units/scb/alexandrov/contact/index.html)).

* Developer: Ivan Protsyuk
* Principal investigator: Theodore Alexandrov

## How to run it?

Prerequisite: Python 3.6

`git clone https://https://github.com/iprotsyuk/ili_file_server ./ili_file_server`

`cd ili_file_server`

`python server.py <port>`

If `port` is not specified, the server will use 8080.

## License

The content of this project is licensed under the Apache 2.0 licence, see LICENSE.md.
