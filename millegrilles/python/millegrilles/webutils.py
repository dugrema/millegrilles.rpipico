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


def reboot(e=None):
    """
    Redemarre. Conserve une trace dans les fichiers exception.log et reboot.log.
    """
    import time
    from sys import print_exception

    from machine import reset

    print("Rebooting")
    date_line = "Date %s (%s)" % (str(time.gmtime()), time.time())

    if e is not False:
        if e is not None:
            with open("exception.log", "w") as logfile:
                logfile.write("%s\n\n---\nCaused by:\n" % date_line)
                print_exception(e, logfile)
                logfile.write("\n")
        else:
            e = "N/A"

        with open("reboot.log", "a") as logfile:
            logfile.write("%s (Cause: %s)\n" % (date_line, str(e)))

    try:
        from millegrilles.wifi import disconnect_wifi

        disconnect_wifi()  # Disconnect wifi to ensure redetection on reboot
    except Exception:
        pass

    reset()
