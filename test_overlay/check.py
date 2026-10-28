"""Exercise the client against an independent loopback WebSocket peer."""
import base64
import concurrent.futures
import hashlib
import socket
import subprocess


def exact(sock, size):
    result = bytearray()
    while len(result) < size:
        part = sock.recv(size - len(result))
        if not part:
            raise EOFError("Client closed the connection")
        result.extend(part)
    return bytes(result)


def read_frame(sock):
    opcode, length = exact(sock, 2)
    assert opcode == 0x81 and length & 0x80
    length &= 0x7f
    assert length < 126
    mask = exact(sock, 4)
    return bytes(b ^ mask[i % 4] for i, b in enumerate(exact(sock, length)))


def peer(listener):
    with listener.accept()[0] as conn:
        conn.settimeout(15)
        request = bytearray()
        while not request.endswith(b"\r\n\r\n"):
            request.extend(exact(conn, 1))
            assert len(request) < 16384
        headers = dict(line.split(":", 1) for line in request.decode().split("\r\n")[1:] if ":" in line)
        key = next(value.strip() for name, value in headers.items() if name.lower() == "sec-websocket-key")
        accept = base64.b64encode(hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest()).decode()
        conn.sendall(("HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\n"
                      "Connection: Upgrade\r\nSec-WebSocket-Accept: " + accept + "\r\n\r\n").encode())
        # No frame reaches the canceled read; receipt synchronizes with cancellation.
        assert read_frame(conn) == b"after-cancel"
        conn.sendall(b"\x81\x08survived")
        assert read_frame(conn) == b"ack"
        conn.shutdown(socket.SHUT_WR)
        assert conn.recv(1) == b"", "Transport remained writable after EOF"


def verify(stage, prefix, suite, run):
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        listener.settimeout(20)
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            server = pool.submit(peer, listener)
            command = [*prefix, "dune", "exec", "--profile", "release", "./overlay_check/check.exe",
                       "--", str(listener.getsockname()[1])]
            print("+", " ".join(command), flush=True)
            with subprocess.Popen(command, cwd=stage, stdin=subprocess.PIPE,
                                  stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True) as process:
                try:
                    server.result(timeout=20)
                    output, _ = process.communicate("closed\n", timeout=15)
                    print(output, end="", flush=True)
                    assert process.returncode == 0, process.returncode
                except BaseException:
                    process.kill()
                    output, _ = process.communicate()
                    print(output, end="", flush=True)
                    raise
    print("Loopback WebSocket: cancel, receive, send, EOF and explicit close passed")
