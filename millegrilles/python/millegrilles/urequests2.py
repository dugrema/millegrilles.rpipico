import usocket
from uasyncio import sleep_ms
from uerrno import EINPROGRESS
from gc import collect
from json import loads

class Response:
    def __init__(self, f):
        self.raw = f
        self.encoding = "utf-8"
        self._cached = None
        print("Response init")

    def close(self):
        if self.raw:
            self.raw.close()
            self.raw = None
            print("Response.close() Raw 1")
        self._cached = None

    async def content(self):
        if self._cached is None:
            try:
                await sleep_ms(10)  # Attendre download
                self._cached = self.raw.read()
                #if self._cached is None:
                #    await sleep_ms(250)  # Attendre download, tenter a nouveau
                #    self._cached = self.raw.read()
            finally:
                self.raw.close()
                self.raw = None
                print("Response.close() Raw 2")
        return self._cached

    async def text(self):
        return str(await self.content(), self.encoding)

    async def json(self):
        return loads(await self.content())
    
    async def read_text_into(self, buffer):
        content = await self.content()
        buffer.set_text(await self.text())

async def request(
    method,
    url,
    data=None,
    json=None,
    headers={},
    stream=None,
    auth=None,
    timeout=None,
    parse_headers=True,
    lock=None,
):
    redirect = None  # redirection url, None means no redirection
    chunked_data = data and getattr(data, "__iter__", None) and not getattr(data, "__len__", None)

    if auth is not None:
        import ubinascii

        username, password = auth
        formated = b"{}:{}".format(username, password)
        formated = str(ubinascii.b2a_base64(formated)[:-1], "ascii")
        headers["Authorization"] = "Basic {}".format(formated)

    try:
        proto, dummy, host, path = url.split("/", 3)
    except ValueError:
        proto, dummy, host = url.split("/", 2)
        path = ""
    if proto == "http:":
        port = 80
    elif proto == "https:":
        import ussl

        port = 443
    else:
        raise ValueError("Unsupported protocol: " + proto)

    if ":" in host:
        host, port = host.split(":", 1)
        port = int(port)

    ai = usocket.getaddrinfo(host, port, 0, usocket.SOCK_STREAM)
    await sleep_ms(1)  # Yield
    #else:
    #    ai = await thread_executor(usocket.getaddrinfo, host, port, 0, usocket.SOCK_STREAM)
    ai = ai[0]

    resp_d = None
    if parse_headers is not False:
        resp_d = {}

    print("open socket")
    s = usocket.socket(ai[0], usocket.SOCK_STREAM, ai[2])
    print("Socket init")
    s.setblocking(False)

    if timeout is not None:
        # Note: settimeout is not supported on all platforms, will raise
        # an AttributeError if not available.
        s.settimeout(timeout)

    try:
        try:
            await sleep_ms(1)  # Yield
            s.connect(ai[-1])
            # print("Socket connect")
            await sleep_ms(1)  # Yield
        except OSError as er:
            if er.errno != EINPROGRESS:
                raise er        
        
        if proto == "https:":
            # print("https init")
            try:
                if lock is not None:
                    await lock.acquire()
                    # print("https lock acquired")
                s = ussl.wrap_socket(s, server_hostname=host)
            finally:
                if lock is not None:
                    # print("https release lock")
                    lock.release()
            # print("https init done")
            await sleep_ms(1)  # Yield
        
        s.write(b"%s /%s HTTP/1.0\r\n" % (method, path))
        
        if not "Host" in headers:
            s.write(b"Host: %s\r\n" % host)
        # Iterate over keys to avoid tuple alloc
        for k in headers:
            s.write(k)
            s.write(b": ")
            s.write(headers[k])
            s.write(b"\r\n")
        if json is not None:
            assert data is None
            import ujson

            data = ujson.dumps(json)
            s.write(b"Content-Type: application/json\r\n")
        if data:
            if chunked_data:
                s.write(b"Transfer-Encoding: chunked\r\n")
            else:
                s.write(b"Content-Length: %d\r\n" % len(data))
        s.write(b"Connection: close\r\n\r\n")
        await sleep_ms(1)  # Yield
        if data:
            if chunked_data:
                for chunk in data:
                    s.write(b"%x\r\n" % len(chunk))
                    s.write(chunk)
                    s.write(b"\r\n")
                    await sleep_ms(1)  # Yield
                s.write("0\r\n\r\n")
            else:
                s.write(data)
                await sleep_ms(1)  # Yield

        # Simuler non-blocking
        await sleep_ms(1)
        while True:
            l = s.readline()
            if l is not None:
                break
            await sleep_ms(500)
        
        l = l.split(None, 2)
        if len(l) < 2:
            # Invalid response
            raise ValueError("HTTP error: BadStatusLine:\n%s" % l)
        status = int(l[1])
        reason = ""
        if len(l) > 2:
            reason = l[2].rstrip()
        while True:
            l = s.readline()
            if not l:
                # Donner une chance, on est en non blocking io
                await sleep_ms(250)
                l = s.readline()
            if not l or l == b"\r\n":
                break
            # print(l)
            if l.startswith(b"Transfer-Encoding:"):
                if b"chunked" in l:
                    raise ValueError("Unsupported " + str(l, "utf-8"))
            elif l.startswith(b"Location:") and not 200 <= status <= 299:
                if status in [301, 302, 303, 307, 308]:
                    redirect = str(l[10:-2], "utf-8")
                else:
                    raise NotImplementedError("Redirect %d not yet supported" % status)
            if parse_headers is False:
                pass
            elif parse_headers is True:
                l = str(l, "utf-8")
                k, v = l.split(":", 1)
                resp_d[k] = v.strip()
            else:
                parse_headers(l, resp_d)
    except OSError:
        s.close()
        print("Closing socket")
        raise

    if redirect:
        s.close()
        print("Closing socket")
        if status in [301, 302, 303]:
            return request("GET", redirect, None, None, headers, stream)
        else:
            return request(method, redirect, data, json, headers, stream)
    else:
        resp = Response(s)
        resp.status_code = status
        resp.reason = reason
        if resp_d is not None:
            resp.headers = resp_d
        return resp


async def head(url, **kw):
    return await request("HEAD", url, **kw)


async def get(url, **kw):
    return await request("GET", url, **kw)


async def post(url, **kw):
    return await request("POST", url, **kw)


async def put(url, **kw):
    return await request("PUT", url, **kw)


async def patch(url, **kw):
    return await request("PATCH", url, **kw)


async def delete(url, **kw):
    return await request("DELETE", url, **kw)



