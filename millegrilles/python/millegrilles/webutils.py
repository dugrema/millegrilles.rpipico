def parse_url(url):
    try:
        proto, dummy, host, path = url.split("/", 3)
    except:
        proto, dummy, host = url.split("/", 2)
        path = None

    try:
        host, port = host.split(":", 2)
    except:
        port = None

    return proto, host, port, path
