import threading
import socket
import json

clients = []
lock = threading.Lock()

class clientthread(threading.Thread):
    def __init__(self, socket, cb):
        self.__socket = socket
        self.__cb = cb
        threading.Thread.__init__(self)

    def send(self, data):
        self.__socket.sendall(data)

    def run(self):
        buf = ""
        while True:
            chunk = self.__socket.recv(32)
            if len(chunk) == 0:
                del self.__socket
                break
            lock.acquire()
            try:
                chunk = chunk.decode()
                buf += chunk
                while "\n" in buf:
                    line = buf[:buf.find("\n")]
                    buf = buf[buf.find("\n") + 1:]
                    d = json.loads(line)
                    if self.__cb:
                        self.__cb(d)
                    #rctrx.send(d["protocol"], d["params"])
            except:
                print("Exception")
                pass
            lock.release()

        lock.acquire()
        clients.remove(self)
        lock.release()

class ApiServer(threading.Thread):
    def __init__(self, port, cb = None):
        self.__srvsock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.__srvsock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.__srvsock.bind(('', port))
        print("API listening on port", port)
        self.__srvsock.listen(5)
        self.__cb = cb
        threading.Thread.__init__(self)
        self.daemon = True
        self.start()

    def run(self):
        while True:
            (client, address) = self.__srvsock.accept()
            print("API connect from", address)
            ct = clientthread(client, self.__cb)
            ct.daemon = True
            ct.start()
            lock.acquire()
            clients.append(ct)
            lock.release()

    def send(self, dict):
        data = (json.dumps(dict) + "\n").encode()
        lock.acquire()
        for client in clients:
            client.send(data)
        lock.release()
