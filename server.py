import socket
import struct
import http.client
from urllib.parse import urlparse
import sys

def main():
    if len(sys.argv) != 2:
        print("Usage: python server.py <port>")
        sys.exit(1)
    port = int(sys.argv[1])

    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_sock.bind(('0.0.0.0', port))
    server_sock.listen(1)
    print(f"Offshore proxy listening on port {port}")

    conn, addr = server_sock.accept()
    print(f"Connected from ship: {addr}")

    while True:
        try:
            # Read request length
            len_bytes = conn.recv(4)
            if len(len_bytes) != 4:
                break
            req_len = struct.unpack('>I', len_bytes)[0]

            # Read full request exactly
            req_data = b''
            received = 0
            while received < req_len:
                chunk = conn.recv(req_len - received)
                if not chunk:
                    break
                req_data += chunk
                received += len(chunk)
            if received < req_len:
                print(f"Warning: Incomplete request received ({received}/{req_len})")
                continue  # Skip instead of break for robustness

            # Find header end
            header_end = req_data.find(b'\r\n\r\n')
            if header_end == -1:
                print("Invalid request: No header end")
                continue
            header_end += 4
            headers_raw = req_data[:header_end]
            remaining = req_data[header_end:]

            # Parse headers for Content-Length
            cl_str = headers_raw.decode('utf-8', errors='ignore')
            lines = cl_str.split('\r\n')
            if not lines or len(lines[0].split()) < 3:
                print("Invalid request line")
                continue
            parts = lines[0].split()
            method = parts[0]
            url = parts[1]

            headers = {}
            cl = 0
            has_cl = False
            for line in lines[1:]:
                if ': ' in line:
                    k, v = line.split(': ', 1)
                    headers[k] = v
                    if k.lower() == 'content-length':
                        cl = int(v)
                        has_cl = True
                # Skip if Transfer-Encoding: chunked for now (add de-chunking if needed)

            # Read body exactly based on Content-Length (from remaining data)
            body = b''
            if has_cl and cl > 0:
                if len(remaining) >= cl:
                    body = remaining[:cl]
                    # Ignore extra data after body for now
                else:
                    print(f"Body too short: {len(remaining)} < {cl}")
                    continue
            elif not has_cl:
                # No Content-Length: assume 0 body
                cl = 0
                body = b''
            else:
                cl = 0  # Fallback

            if len(body) != cl:
                print(f"Body length mismatch: expected {cl}, got {len(body)}")
                print(f"Headers: {cl_str[:200]}...")  # Debug: Print partial headers
                continue  # Skip instead of raise for better error handling

            full_req = headers_raw + b'\r\n\r\n' + body  # Reconstruct for logging if needed

            # Parse URL
            parsed = urlparse(url)
            if parsed.scheme not in ('http', 'https'):
                print("Unsupported scheme")
                continue
            host = parsed.hostname
            port = parsed.port or (443 if parsed.scheme == 'https' else 80)
            path = parsed.path or '/'
            if parsed.query:
                path += '?' + parsed.query

            # Upstream headers (clean proxy-specific)
            upstream_headers = {k: v for k, v in headers.items() if k.lower() not in ('proxy-connection', 'proxy-authorization', 'connection')}
            if 'Host' not in upstream_headers:
                upstream_headers['Host'] = host
            # Add explicit Content-Length if present
            if has_cl:
                upstream_headers['Content-Length'] = str(cl)

            # Forward request
            try:
                if parsed.scheme == 'http':
                    upstream_conn = http.client.HTTPConnection(host, port)
                else:
                    upstream_conn = http.client.HTTPSConnection(host, port)
                upstream_conn.request(method, path, body=body if cl > 0 else None, headers=upstream_headers)
                res = upstream_conn.getresponse()
                response_data = res.read()

                # Build response
                status_line = f"HTTP/1.1 {res.status} {res.reason}\r\n".encode('utf-8')
                header_lines = [f"{k}: {v}\r\n".encode('utf-8') for k, v in res.getheaders()]
                headers_block = b''.join(header_lines)
                full_response = status_line + headers_block + b"\r\n" + response_data

                upstream_conn.close()

                # Send response
                resp_len = len(full_response)
                conn.send(struct.pack('>I', resp_len))
                conn.send(full_response)
                print(f"Successfully proxied: {method} {url} -> {res.status}")
            except Exception as upstream_e:
                print(f"Upstream error: {upstream_e}")
                full_response = b"HTTP/1.1 502 Bad Gateway\r\n\r\nError forwarding request"
                resp_len = len(full_response)
                conn.send(struct.pack('>I', resp_len))
                conn.send(full_response)
        except Exception as e:
            print(f"General error: {e}")
            full_response = b"HTTP/1.1 502 Bad Gateway\r\n\r\n"
            resp_len = len(full_response)
            conn.send(struct.pack('>I', resp_len))
            conn.send(full_response)

    conn.close()
    server_sock.close()

if __name__ == "__main__":
    main()