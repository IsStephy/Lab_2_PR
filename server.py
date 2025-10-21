import socket
import os
import sys
import mimetypes
import urllib.parse

HOST = "0.0.0.0"
PORT = 8080

def generate_directory_listing(directory, request_path):
    """Generate a simple HTML page listing directory contents."""
    entries = os.listdir(directory)
    entries.sort(key=str.lower)

    html = f"<html><head><title>Index of {request_path}</title></head><body>"
    html += f"<h1>Index of {request_path}</h1><ul>"

    if request_path != "/":
        parent_path = os.path.dirname(request_path.rstrip("/"))
        if not parent_path:
            parent_path = "/"
        if parent_path == "/":
            html += '<li><a href="/">Parent Directory</a></li>'
        else:
            html += f'<li><a href="{urllib.parse.quote(parent_path)}/">Parent Directory</a></li>'


    for entry in entries:
        full_path = os.path.join(directory, entry)
        display_name = entry + "/" if os.path.isdir(full_path) else entry
        link_path = os.path.join(request_path, entry).replace("\\", "/")
        if os.path.isdir(full_path):
            link_path += "/"
        html += f'<li><a href="{urllib.parse.quote(link_path)}">{display_name}</a></li>'

    html += "</ul></body></html>"
    return html.encode("utf-8")

def handle_client(conn, base_dir):
    try:
        request = conn.recv(2048).decode("utf-8", errors="ignore")
        if not request:
            return
        request_line = request.splitlines()[0]
        method, path, _ = request_line.split()
        if method != "GET":
            conn.sendall(b"HTTP/1.1 405 Method Not Allowed\r\n\r\n")
            return
        path = urllib.parse.unquote(path)
        file_path = os.path.join(base_dir, path.lstrip("/"))
        if os.path.isdir(file_path):
            body = generate_directory_listing(file_path, path)
            header = (
                "HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n"
                f"Content-Length: {len(body)}\r\n\r\n"
            )
            conn.sendall(header.encode("utf-8") + body)
            return
        if not os.path.exists(file_path):
            conn.sendall(
                b"HTTP/1.1 404 Not Found\r\nContent-Type: text/html\r\n\r\n"
                b"<html><body><h1>404 Not Found</h1></body></html>"
            )
            return

        mime_type, _ = mimetypes.guess_type(file_path)
        if mime_type not in ["text/html", "image/png", "application/pdf"]:
            conn.sendall(
                b"HTTP/1.1 404 Not Found\r\nContent-Type: text/html\r\n\r\n"
                b"<html><body><h1>404 Not Found</h1></body></html>"
            )
            return

        with open(file_path, "rb") as f:
            body = f.read()

        header = f"HTTP/1.1 200 OK\r\nContent-Type: {mime_type}\r\nContent-Length: {len(body)}\r\n\r\n"
        conn.sendall(header.encode("utf-8") + body)

    except Exception as e:
        print("Error handling request:", e)
    finally:
        conn.close()

def run_server(base_dir):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
        server_socket.bind((HOST, PORT))
        server_socket.listen(10)
        print(f"Serving directory '{base_dir}' on http://localhost:{PORT}")

        while True:
            conn, addr = server_socket.accept()
            handle_client(conn, base_dir)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python server.py <directory_to_serve>")
        sys.exit(1)
    directory = sys.argv[1]
    if not os.path.isdir(directory):
        print(f"Error: '{directory}' is not a directory")
        sys.exit(1)
    run_server(directory)
