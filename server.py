from http.server import SimpleHTTPRequestHandler, HTTPServer
import os

class StaticServer(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory="Static", **kwargs)

def run(server_class=HTTPServer, handler_class=StaticServer, port=8000):
    server_address = ('', port)
    httpd = server_class(server_address, handler_class)
    print(f"Serving on port {port} from the 'Static' folder...")
    httpd.serve_forever()

if __name__ == "__main__":
    os.makedirs("Static", exist_ok=True)  # Ensure the Static folder exists
    run()