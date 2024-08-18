import time
import threading

PARAM_TX35 = {"duration": 15, "baudrate": 9.579,  "sync": [0x2d, 0xd4], "rxlen": 14} # LaCrosse TX35, EMT7110
PARAM_TX29  = {"duration": 15, "baudrate": 17.241, "sync": [0x2d, 0xd4], "rxlen": 5} # LaCrosse TX29
PARAM_BRESSER = {"duration": 15, "baudrate": 8.000, "sync": [0x2d, 0xd4], "rxlen": 25} # Bresser 7in1 weather
PARAM_EC3K = {"duration": 15, "baudrate": 20.0, "sync": [0x13, 0xF1, 0x85, 0xD3, 0xAC], "rxlen": 56} # Energy Count 3000

class ParamChanger(threading.Thread):
    def __init__(self, rfm, event, mutex, params):
        self.__rfm = rfm
        self.__event = event
        self.__mutex = mutex
        self.__params = params
        self.__rxlen = 0
        threading.Thread.__init__(self)
        self.daemon = True
        self.start()

    def run(self):
        global rxlen
        i = 0
        while True:
            self.__event.clear()
            self.__rfm.receive_stop()

            bd = self.__params[i]["baudrate"]
            self.__rxlen = self.__params[i]["rxlen"]
            sync = self.__params[i]["sync"]

            print("Switch baudrate to " + str(bd) + " kbit/s")
            self.__mutex.acquire()
            self.__rfm.set_params(Datarate = bd)
            self.__rfm.set_params(SyncPattern = sync)
            self.__mutex.release()
            self.__event.set()
            time.sleep(self.__params[i]["duration"])
            i += 1
            if i == len(self.__params):
                i = 0

    def rxLen(self):
        return self.__rxlen
