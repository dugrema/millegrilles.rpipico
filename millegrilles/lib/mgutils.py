from collections import OrderedDict


def comparer_dict(d1, d2):
    """
    Deep compare de 2 dicts
    """
    if d1 == d2:
        return True

    if d1 is None or d2 is None:
        return False

    if not isinstance(d1, dict) or not isinstance(d2, dict):
        raise Exception('Mauvais type')

    if len(d1) != len(d2):
        return False

    try:
        for k, v1 in d1.items():
            v2 = d2[k]

            if v1 == v2:
                pass
            elif isinstance(v1, dict) or isinstance(v1, OrderedDict):
                if comparer_dict(v1, v2) is False:
                    print("Dict diff key %s" % k)
                    return False
            elif isinstance(v1, list) and isinstance(v2, list):
                if len(v1) != len(v2):
                    print("list diff len sur %s : %d / %d" % (k, len(v1), len(v2)))
                    return False

                for i in range(0, len(v1)):
                    l1 = v1[i]
                    l2 = v2[i]
                    if isinstance(l1, dict):
                        if comparer_dict(l1, l2) is False:
                            print("list diff idx %s" % i)
                            return False
                    elif l1 != l2:
                        print("list diff idx %s" % i)
                        return False
            else:
                print("Dict diff key %s" % k)
                return False

    except (KeyError, IndexError):
        return False

    return True
