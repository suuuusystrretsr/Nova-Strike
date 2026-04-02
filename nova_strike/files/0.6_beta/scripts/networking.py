import json
import os
import socket
import errno
from collections import deque
from typing import Deque, Dict, List, Optional, Tuple

from scripts.net_state import PlayerSyncState


class SocketNetBridge:
    """
    Minimal non-blocking socket layer for multiplayer preparation.

    This is intentionally small and beginner-friendly:
    - server/client transport only
    - newline-delimited JSON packets
    - non-blocking IO with graceful error handling
    """

    MODE_OFFLINE = "offline"
    MODE_SERVER = "server"
    MODE_CLIENT = "client"

    def __init__(self) -> None:
        self.mode = self.MODE_OFFLINE
        self.server_socket: Optional[socket.socket] = None
        self.client_socket: Optional[socket.socket] = None
        self.clients: Dict[Tuple[str, int], socket.socket] = {}
        self.recv_buffers: Dict[socket.socket, str] = {}
        self.outbox: Deque[Dict] = deque(maxlen=512)
        self.inbox: Deque[Dict] = deque(maxlen=512)
        self.last_error: str = ""
        self.bind_host = "127.0.0.1"
        self.bind_port = 7777
        # Safety caps to prevent a single network poll from stalling the frame.
        self.max_accept_per_poll = 12
        self.max_outbox_packets_per_poll = 96
        self.max_recv_loops_per_socket = 24
        self.max_decoded_packets_per_socket_poll = 96
        self.max_buffer_chars = 262144

    @property
    def is_active(self) -> bool:
        return self.mode in (self.MODE_SERVER, self.MODE_CLIENT)

    def start_server(self, host: str = "127.0.0.1", port: int = 7777, max_clients: int = 8) -> bool:
        self.stop()
        try:
            srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            srv.setblocking(False)
            srv.bind((host, int(port)))
            srv.listen(max(1, int(max_clients)))
            self.server_socket = srv
            self.mode = self.MODE_SERVER
            self.bind_host = host
            self.bind_port = int(port)
            self.last_error = ""
            return True
        except OSError as exc:
            self.last_error = self._format_server_start_error(exc, host=host, port=port)
            self.stop()
            return False

    def start_client(self, host: str = "127.0.0.1", port: int = 7777) -> bool:
        self.stop()
        try:
            cli = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            cli.setblocking(False)
            target_port = int(port)
            connect_code = int(cli.connect_ex((host, target_port)))
            pending_codes = {
                0,
                int(getattr(errno, "EINPROGRESS", 115)),
                int(getattr(errno, "EWOULDBLOCK", 11)),
                int(getattr(errno, "EALREADY", 114)),
                int(getattr(errno, "WSAEWOULDBLOCK", 10035)),
                int(getattr(errno, "WSAEINPROGRESS", 10036)),
                int(getattr(errno, "WSAEALREADY", 10037)),
            }
            if connect_code not in pending_codes:
                self.last_error = self._format_connect_error(connect_code, host=host, port=target_port)
                self._safe_close(cli)
                return False
            self.client_socket = cli
            self.recv_buffers[cli] = ""
            self.mode = self.MODE_CLIENT
            self.bind_host = host
            self.bind_port = target_port
            self.last_error = ""
            return True
        except OSError as exc:
            self.last_error = self._format_client_start_error(exc, host=host, port=port)
            self.stop()
            return False

    def stop(self) -> None:
        for sock in list(self.clients.values()):
            self._safe_close(sock)
        self.clients.clear()

        if self.server_socket:
            self._safe_close(self.server_socket)
            self.server_socket = None

        if self.client_socket:
            self._safe_close(self.client_socket)
            self.client_socket = None

        self.recv_buffers.clear()
        self.outbox.clear()
        self.inbox.clear()
        self.mode = self.MODE_OFFLINE

    def queue_packet(self, packet: Dict) -> None:
        if not isinstance(packet, dict):
            return
        self.outbox.append(packet)

    def queue_player_state(self, player_state: PlayerSyncState) -> None:
        self.queue_packet({"type": "player_state", "payload": player_state.to_dict()})

    def poll(self) -> List[Dict]:
        if not self.is_active:
            self.inbox.clear()
            return []

        if self.mode == self.MODE_SERVER:
            self._accept_clients_non_blocking()

        self._flush_outbox_non_blocking()
        self._recv_non_blocking()

        packets = list(self.inbox)
        self.inbox.clear()
        return packets

    def _accept_clients_non_blocking(self) -> None:
        if not self.server_socket:
            return
        accepted = 0
        while accepted < max(1, int(self.max_accept_per_poll)):
            try:
                client_sock, addr = self.server_socket.accept()
            except BlockingIOError:
                break
            except OSError as exc:
                self.last_error = self._format_runtime_socket_error("accept", exc)
                break
            client_sock.setblocking(False)
            self.clients[addr] = client_sock
            self.recv_buffers[client_sock] = ""
            accepted += 1

    def _flush_outbox_non_blocking(self) -> None:
        if not self.outbox:
            return
        targets: List[socket.socket] = []
        if self.mode == self.MODE_CLIENT and self.client_socket:
            targets = [self.client_socket]
        elif self.mode == self.MODE_SERVER:
            targets = [sock for sock in self.clients.values() if sock]
        if not targets:
            self.outbox.clear()
            return

        sent_packets = 0
        while self.outbox and sent_packets < max(1, int(self.max_outbox_packets_per_poll)):
            packet = self.outbox.popleft()
            try:
                data = (json.dumps(packet, separators=(",", ":")) + "\n").encode("utf-8")
            except (TypeError, ValueError):
                continue
            for sock in list(targets):
                self._send_bytes(sock, data)
            sent_packets += 1

    def _recv_non_blocking(self) -> None:
        sockets: List[socket.socket] = []
        if self.mode == self.MODE_CLIENT and self.client_socket:
            sockets = [self.client_socket]
        elif self.mode == self.MODE_SERVER:
            sockets = [sock for sock in self.clients.values() if sock]
        for sock in sockets:
            self._recv_from_socket(sock)

    def _recv_from_socket(self, sock: socket.socket) -> None:
        recv_loops = 0
        decoded_budget = max(1, int(self.max_decoded_packets_per_socket_poll))
        while recv_loops < max(1, int(self.max_recv_loops_per_socket)) and decoded_budget > 0:
            recv_loops += 1
            try:
                chunk = sock.recv(4096)
            except BlockingIOError:
                break
            except OSError as exc:
                self.last_error = self._format_runtime_socket_error("receive", exc)
                self._drop_socket(sock)
                break
            if not chunk:
                if self.client_socket is sock:
                    self.last_error = "Disconnected from server"
                else:
                    self.last_error = "A client disconnected"
                self._drop_socket(sock)
                break
            buffer = self.recv_buffers.get(sock, "") + chunk.decode("utf-8", errors="ignore")
            if len(buffer) > self.max_buffer_chars:
                buffer = buffer[-self.max_buffer_chars :]
            while "\n" in buffer and decoded_budget > 0:
                line, buffer = buffer.split("\n", 1)
                line = line.strip()
                if not line:
                    continue
                try:
                    packet = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(packet, dict):
                    self.inbox.append(packet)
                    decoded_budget -= 1
            self.recv_buffers[sock] = buffer

    def _send_bytes(self, sock: socket.socket, data: bytes) -> None:
        if not sock:
            return
        try:
            sock.sendall(data)
        except BlockingIOError:
            # Drop packet under backpressure for stability.
            return
        except OSError as exc:
            self.last_error = self._format_runtime_socket_error("send", exc)
            self._drop_socket(sock)

    def _drop_socket(self, sock: socket.socket) -> None:
        if not sock:
            return
        if self.client_socket is sock:
            self._safe_close(sock)
            self.client_socket = None
            self.mode = self.MODE_OFFLINE
        else:
            for addr, client in list(self.clients.items()):
                if client is sock:
                    self._safe_close(client)
                    del self.clients[addr]
                    break
        if sock in self.recv_buffers:
            del self.recv_buffers[sock]

    def _safe_close(self, sock: socket.socket) -> None:
        if not sock:
            return
        try:
            sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        try:
            sock.close()
        except OSError:
            pass

    def _format_connect_error(self, code: int, host: str, port: int) -> str:
        code_int = int(code)
        code_map = {
            61: "connection refused (server not running or blocked)",
            111: "connection refused (server not running or blocked)",
            10061: "connection refused (server not running or blocked)",
            110: "connection timed out",
            10060: "connection timed out",
            113: "no route to host",
            10065: "no route to host",
            11001: "invalid host or DNS lookup failed",
            10049: "invalid IP address",
        }
        detail = code_map.get(code_int)
        if not detail:
            try:
                detail = os.strerror(code_int)
            except ValueError:
                detail = "unknown socket error"
        return f"Could not connect to {host}:{port}: {detail} (code {code_int})"

    def _format_server_start_error(self, exc: OSError, host: str, port: int | str) -> str:
        err_no = int(getattr(exc, "errno", 0) or 0)
        if err_no in (98, 10048):
            return f"Could not start server on {host}:{port}: address/port already in use"
        if err_no in (13, 10013):
            return f"Could not start server on {host}:{port}: permission denied"
        if err_no in (49, 10049):
            return f"Could not start server on {host}:{port}: invalid bind address"
        detail = str(exc).strip() or "unknown error"
        return f"Could not start server on {host}:{port}: {detail}"

    def _format_client_start_error(self, exc: OSError, host: str, port: int | str) -> str:
        err_no = int(getattr(exc, "errno", 0) or 0)
        if err_no in (-2, 11001):
            return f"Could not resolve host '{host}'"
        if err_no in (49, 10049):
            return f"Invalid IP address '{host}'"
        detail = str(exc).strip() or "unknown error"
        return f"Client start failed for {host}:{port}: {detail}"

    def _format_runtime_socket_error(self, operation: str, exc: OSError) -> str:
        err_no = int(getattr(exc, "errno", 0) or 0)
        if err_no in (10054, 104):
            return "Connection lost: remote host closed the connection"
        if err_no in (10057,):
            return "Connection is not established"
        if err_no in (10061, 61, 111):
            return "Connection refused by server"
        detail = str(exc).strip() or "unknown error"
        return f"Network {operation} error: {detail}"
