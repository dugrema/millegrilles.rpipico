import time


class TendanceBarometrique:

    INTERVALLE_LECTURES_SECS = const(300)  # Ignorer les lectures si plus recent que cette valeur
    MAX_LECTURES = const(19)

    def __init__(self):
        self.__derniere_lecture = 0
        # Pre-initialiser la liste
        self.__lectures: list = [None] * TendanceBarometrique.MAX_LECTURES

    def ajouter(self, lecture: float):
        now = int(time.time())
        if self.__derniere_lecture + TendanceBarometrique.INTERVALLE_LECTURES_SECS < now:
            self.__derniere_lecture = now
            self.rotation_lectures(lecture)

    def rotation_lectures(self, lecture: float):
        # Deplacer toutes les lectures i vers i+1 (commencer par la fin de la liste)
        for i in range(len(self.__lectures)-1, 0, -1):
            self.__lectures[i] = self.__lectures[i-1]

        # Placer la plus recente lecture en tete de la liste
        self.__lectures[0] = lecture

    def get_lectures(self, device_id: str):

        # print("barometre liste lectures %s" % self.__lectures)

        if self.__lectures[1] is not None:
            tendance_5m = self.__lectures[0] - self.__lectures[1]
        else:
            tendance_5m = None

        if self.__lectures[2] is not None:
            tendance_10m = self.__lectures[0] - self.__lectures[2]
        else:
            tendance_10m = None

        if self.__lectures[3] is not None:
            tendance_15m = self.__lectures[0] - self.__lectures[3]
        else:
            tendance_15m = None

        if self.__lectures[6] is not None:
            tendance_30m = self.__lectures[0] - self.__lectures[6]
        else:
            tendance_30m = None

        if self.__lectures[12] is not None:
            tendance_60m = self.__lectures[0] - self.__lectures[12]
        else:
            tendance_60m = None

        if self.__lectures[18] is not None:
            tendance_90m = self.__lectures[0] - self.__lectures[18]
        else:
            tendance_90m = None

        return {
            '%s/pression_tendance_05m' % device_id: {
                'valeur': tendance_5m,
                'type': 'pression_tendance',
            },
            '%s/pression_tendance_10m' % device_id: {
                'valeur': tendance_10m,
                'type': 'pression_tendance',
            },
            '%s/pression_tendance_15m' % device_id: {
                'valeur': tendance_15m,
                'type': 'pression_tendance',
            },
            '%s/pression_tendance_30m' % device_id: {
                'valeur': tendance_30m,
                'type': 'pression_tendance',
            },
            '%s/pression_tendance_60m' % device_id: {
                'valeur': tendance_60m,
                'type': 'pression_tendance',
            },
            '%s/pression_tendance_90m' % device_id: {
                'valeur': tendance_90m,
                'type': 'pression_tendance',
            }
        }
