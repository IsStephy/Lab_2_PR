import socket
import os
import sys
import mimetypes
import urllib.parse
import threading
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

HOST = "0.0.0.0"
PORT = 8080

# Global counter for requests (no lock)
request_counter = defaultdict(int)

# Rate limiting data structures (still needs lock for correctness)
rate_limit_data = defaultdict(list)
rate_limit_lock = threading.Lock()
MAX_REQUESTS_PER_SECOND = 5


def normalize_path(path):
    return os.path.normpath(path)


def check_rate_limit(client_ip):
    """Rate limiting still thread-safe"""
    with rate_limit_lock:
        current_time = time.time()
        rate_limit_data[client_ip] = [
            ts for ts in rate_limit_data[client_ip] if current_time - ts < 1.0
        ]

        if len(rate_limit_data[client_ip]) >= MAX_REQUESTS_PER_SECOND:
            return False

        rate_limit_data[client_ip].append(current_time)
        return True


def increment_counter(file_path):
    """Increment request counter WITHOUT lock (race condition possible)."""
    file_path = normalize_path(file_path)
    current = request_counter[file_path]
    time.sleep(0.001)  # Force interleaving to expose race conditions
    request_counter[file_path] = current + 1


def generate_directory_listing(directory, request_path):
    """Generate HTML listing showing number of requests."""
    directory = normalize_path(directory)
    entries = os.listdir(directory)
    entries.sort(key=str.lower)

    dir_count = request_counter[directory]

    html = f"<html><head><title>Index of {request_path}</title></head><body>"
    html += f"<h1>Index of {request_path}</h1>"
    html += f"<p><em>Request counts shown in parentheses. This directory: {dir_count} requests</em></p>"
    html += "<ul>"

    if request_path != "/":
        parent_path = os.path.dirname(request_path.rstrip("/"))
        if not parent_path:
            parent_path = "/"
        if parent_path == "/":
            html += '<li><a href="/">Parent Directory</a></li>'
        else:
            html += f'<li><a href="{urllib.parse.quote(parent_path)}/">Parent Directory</a></li>'

    for entry in entries:
        full_path = normalize_path(os.path.join(directory, entry))
        display_name = entry + "/" if os.path.isdir(full_path) else entry
        link_path = os.path.join(request_path, entry).replace("\\", "/")

        count = request_counter[full_path]

        if os.path.isdir(full_path):
            link_path += "/"
            html += f'<li><a href="{urllib.parse.quote(link_path)}">{display_name}</a> <span style="color:#666;">({count} requests)</span></li>'
        else:
            html += f'<li><a href="{urllib.parse.quote(link_path)}">{display_name}</a> <span style="color:#666;">({count} requests)</span></li>'

    html += "</ul></body></html>"
    return html.encode("utf-8")


def handle_client(conn, addr, base_dir, add_delay=False):
    """Handle client connection."""
    client_ip = addr[0]

    try:
        # Check rate limit
        if not check_rate_limit(client_ip):
            response = (
                b"HTTP/1.1 429 Too Many Requests\r\n"
                b"Content-Type: text/html\r\n\r\n"
                b"<html><body><h1>429 Too Many Requests</h1>"
                b"<p>Rate limit exceeded. Please slow down.</p></body></html>"
            )
            conn.sendall(response)
            return

        if add_delay:
            time.sleep(1.0)

        request = conn.recv(2048).decode("utf-8", errors="ignore")
        if not request:
            return

        request_line = request.splitlines()[0]
        method, path, _ = request_line.split()

        if method != "GET":
            conn.sendall(b"HTTP/1.1 405 Method Not Allowed\r\n\r\n")
            return

        path = urllib.parse.unquote(path)
        file_path = normalize_path(os.path.join(base_dir, path.lstrip("/")))

        # Directory
        if os.path.isdir(file_path):
            increment_counter(file_path)
            body = generate_directory_listing(file_path, path)
            header = (
                "HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n"
                f"Content-Length: {len(body)}\r\n\r\n"
            )
            conn.sendall(header.encode("utf-8") + body)
            return

        # File not found
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

        increment_counter(file_path)

        with open(file_path, "rb") as f:
            body = f.read()

        header = f"HTTP/1.1 200 OK\r\nContent-Type: {mime_type}\r\nContent-Length: {len(body)}\r\n\r\n"
        conn.sendall(header.encode("utf-8") + body)

    except Exception as e:
        print(f"Error handling request from {client_ip}:", e)
    finally:
        conn.close()


def run_server_threaded(base_dir, use_thread_pool=True, max_workers=10, add_delay=False):
    """Run multithreaded server without locks."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind((HOST, PORT))
        server_socket.listen(10)

        mode = "thread pool" if use_thread_pool else "thread per request"
        delay_status = "with 1s delay" if add_delay else "no delay"

        print(f"Multithreaded server ({mode}, WITHOUT locks, {delay_status})")
        print(f"Serving directory '{base_dir}' on http://localhost:{PORT}")
        print(f"Rate limit: {MAX_REQUESTS_PER_SECOND} requests/second per IP")

        if use_thread_pool:
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                while True:
                    conn, addr = server_socket.accept()
                    executor.submit(handle_client, conn, addr, base_dir, add_delay)
        else:
            while True:
                conn, addr = server_socket.accept()
                thread = threading.Thread(
                    target=handle_client, args=(conn, addr, base_dir, add_delay)
                )
                thread.daemon = True
                thread.start()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python server_multithreaded_no_lock.py <directory_to_serve> [options]")
        print("Options:")
        print("  --no-pool    Use thread-per-request instead of thread pool")
        print("  --delay      Add 1s delay to simulate work")
        sys.exit(1)

    directory = sys.argv[1]
    if not os.path.isdir(directory):
        print(f"Error: '{directory}' is not a directory")
        sys.exit(1)

    use_pool = "--no-pool" not in sys.argv
    add_delay = "--delay" in sys.argv

    run_server_threaded(directory, use_thread_pool=use_pool, add_delay=add_delay)
