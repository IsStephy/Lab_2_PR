FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir requests

COPY server.py /app/
COPY multithreaded_server.py /app/
COPY server_multithreaded_no_lock.py /app/
COPY test_concurent.py /app/
COPY client.py /app/
COPY content /app/content/

EXPOSE 8080

CMD ["python", "server.py", "content"]
