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

    try:
        for k, v1 in d1.items():
            v2 = d2[k]

            if isinstance(v1, dict):
                if comparer_dict(v1, v2) is False:
                    return False
            else:
                if v1 != v2:
                    return False
    except KeyError:
        return False