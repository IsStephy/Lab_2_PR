import socket
import sys
import os
BUFFER_SIZE = 4096

def http_get(host, port, filename, save_dir):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((host, int(port)))
        request = f"GET {filename} HTTP/1.1\r\nHost: {host}\r\nConnection: close\r\n\r\n"
        s.sendall(request.encode("utf-8"))
        response = b""
        while b"\r\n\r\n" not in response:
            chunk = s.recv(BUFFER_SIZE)
            if not chunk:
                break
            response += chunk
        header, _, rest = response.partition(b"\r\n\r\n")
        header_str = header.decode("utf-8", errors="ignore")
        content_type = None
        for line in header_str.split("\r\n"):
            if line.lower().startswith("content-type:"):
                content_type = line.split(":", 1)[1].strip().split(";")[0]
                break
        if content_type == "text/html":
            body = rest + s.recv(BUFFER_SIZE)
            print(body.decode("utf-8", errors="ignore"))
            return
        if content_type in ["application/pdf", "image/png"]:
            os.makedirs(save_dir, exist_ok=True)
            filename_local = filename.strip("/").split("/")[-1] or "index.html"
            file_path = os.path.join(save_dir, filename_local)
            with open(file_path, "wb") as f:
                f.write(rest) 
                while True:
                    data = s.recv(BUFFER_SIZE) 
                    if not data:
                        break 
                    f.write(data)
            print(f"Saved {content_type} file to {file_path}") 
        else:
            print(f"Unsupported or missing content type: {content_type}")
if __name__ == "__main__":
    if len(sys.argv) != 5:
        print("Usage: python client.py <server_host> <server_port> <filename> <save_directory>")
        sys.exit(1)
    host = sys.argv[1]
    port = sys.argv[2]
    filename = sys.argv[3]
    save_dir = sys.argv[4]
    http_get(host, port, filename, save_dir)
