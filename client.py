import socket
import struct
import threading
import queue
import os
from urllib.parse import urlparse  # Not used here, but for consistency

OFFSHORE_HOST = os.getenv('OFFSHORE_HOST', 'localhost')
OFFSHORE_PORT = 9000

def processor_thread(offshore_conn, request_queue):
    while True:
        client_sock, full_req = request_queue.get()
        try:
            req_len = len(full_req)
            offshore_conn.send(struct.pack('>I', req_len))
            offshore_conn.send(full_req)

            len_bytes = offshore_conn.recv(4)
            if len(len_bytes) != 4:
                break
            resp_len = struct.unpack('>I', len_bytes)[0]
            resp_data = b''
            received = 0
            while received < resp_len:
                chunk = offshore_conn.recv(resp_len - received)
                if not chunk:
                    break
                resp_data += chunk
                received += len(chunk)
            if received == resp_len:
                client_sock.send(resp_data)
        except Exception as e:
            print(f"Error processing request: {e}")
        finally:
            client_sock.close()
            request_queue.task_done()

def handle_client(client_sock):
    try:
        # Read headers
        data = b''
        while b'\r\n\r\n' not in data:
            chunk = client_sock.recv(1024)
            if not chunk:
                return
            data += chunk
        header_end = data.find(b'\r\n\r\n') + 4
        headers_raw = data[:header_end]
        body = b''

        # Parse Content-Length
        cl_str = headers_raw.decode('utf-8', errors='ignore')
        lines = cl_str.split('\r\n')
        cl = 0
        for line in lines[1:]:
            if line.lower().startswith('content-length:'):
                cl = int(line.split(':', 1)[1].strip())
                break

        # Read body
        bytes_read = 0
        while bytes_read < cl:
            chunk = client_sock.recv(cl - bytes_read)
            if not chunk:
                return
            body += chunk
            bytes_read += len(chunk)

        full_req = headers_raw + b'\r\n\r\n' + body
        request_queue.put((client_sock, full_req))
    except Exception as e:
        print(f"Error handling client: {e}")
        client_sock.close()

if __name__ == "__main__":
    request_queue = queue.Queue()
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_sock.bind(('0.0.0.0', 8080))
    server_sock.listen(5)
    print("Ship proxy listening on port 8080")

    # Connect to offshore
    offshore_conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        offshore_conn.connect((OFFSHORE_HOST, OFFSHORE_PORT))
        print(f"Connected to offshore proxy at {OFFSHORE_HOST}:{OFFSHORE_PORT}")
    except Exception as e:
        print(f"Failed to connect to offshore: {e}")
        exit(1)

    # Start processor thread
    proc_thread = threading.Thread(target=processor_thread, args=(offshore_conn, request_queue), daemon=True)
    proc_thread.start()

    # Accept clients
    while True:
        client_sock, addr = server_sock.accept()
        client_thread = threading.Thread(target=handle_client, args=(client_sock,))
        client_thread.daemon = True
        client_thread.start()