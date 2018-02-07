import RPi.GPIO as GPIO
import spidev
import threading
import time

FXOSC = 32E6
FSTEP = FXOSC / (1<<19)


#------ Raspberry RFM Module connection -----
# Connect RaspyRFM module to pins 17-26 on raspberry pi
#-------------------------------------------------#
# Raspi | Raspi | Raspi | RFM69 | RFM12 | PCB con #
# Name  | GPIO  | Pin   | Name  |  Name |  Pin    #
#-------------------------------------------------#
# 3V3   |   -   |  17   | 3.3V  | VDD   |   1     #
#  -    |  24   |  18   | DIO1  | FFIT  |   2     # only when PCB jumper closed, DIO0/nIRQ on 2nd modul!
# MOSI  |  10   |  19   | MOSI  | SDI   |   3     #
# GND   |   -   |  20   | GND   | GND   |   4     #
# MISO  |   9   |  21   | MISO  | SDO   |   5     #
#  -    |  25   |  22   | DIO0  | nIRQ  |   6     #
# SCKL  |  11   |  23   | SCK   | SCK   |   7     #
# CE0   |   8   |  24   | NSS   | nSEL  |   8     #
# CE1   |   7   |  26   | DIO2  | nFFS  |  10     # only when PCB jumper closed, NSS/nFFS on 2nd modul!
#-------------------------------------------------#

#RFM69 registers
RegFifo = 0x00
RegOpMode = 0x01
RegDataModul = 0x02
RegBitrateMsb = 0x03
RegBitrateLsb = 0x04
RegFdevMsb = 0x05
RegFdevLsb = 0x06
RegFrfMsb = 0x07
RegFrfMid = 0x08
RegFrfLsb = 0x09
RegOsc1 = 0x0A
RegAfcCtrl = 0x0B
RegListen1 = 0x0D
RegListen2 = 0x0E
RegListen3 = 0x0F
RegVersion = 0x10
RegPaLevel = 0x11
RegPaRamp = 0x12
RegOcp = 0x13
RegLna = 0x18
RegRxBw = 0x19
RegAfcBw = 0x1A
RegOokPeak = 0x1B
RegOokAvg = 0x1C
RegOokFix = 0x1D
RegAfcFei = 0x1E
RegAfcMsb = 0x1F
RegAfcLsb = 0x20
RegFeiMsb = 0x21
RegFeiLsb = 0x22
RegRssiConfig = 0x23
RegRssiValue = 0x24
RegDioMapping1 = 0x25
RegDioMapping2 = 0x26
RegIrqFlags1 = 0x27
RegIrqFlags2 = 0x28
RegRssiThresh = 0x29
RegRxTimeout1 = 0x2A
RegRxTimeout2 = 0x2B
RegPreambleMsb = 0x2C
RegPreambleLsb = 0x2D
RegSyncConfig = 0x2E
RegSyncValue1 = 0x2F
RegPacketConfig1 = 0x37
RegPayloadLength = 0x38
RegNodeAdrs = 0x39
RegBroadcastAdrs = 0x3A
RegAutoModes = 0x3B
RegFifoThresh = 0x3C
RegPacketConfig2 = 0x3D
RegTemp1 = 0x4E
RegTemp2 = 0x4F
RegTestLna = 0x58
RegTestDagc = 0x6F
RegTestAfc = 0x71

InterPacketRxDelay = 4 #Bitposition
RestartRx = 2
AutoRxRestartOn = 1
AesOn = 0


#Modulation type
OOK = 1
FSK = 0

#RFM69 modes
MODE_SLEEP = 0
MODE_STDBY = 1
MODE_FS = 2
MODE_TX = 3
MODE_RX = 4

class Rfm69:
    def __init__(self, cs = 0, gpio_int = 25):
        self.__event = threading.Event()
        self.__spi = spidev.SpiDev()
        self.__spi.open(0, cs)
        self.__spi.max_speed_hz=int(5E6)
        self.__gpio_int = gpio_int
        
        #Testing presence of module
        err = False
        for i in range(0, 8):
            self.__WriteReg(RegSyncValue1 + i, 0x55)
            if self.ReadReg(RegSyncValue1 + i) != 0x55:
                err = True
                break
            self.__WriteReg(RegSyncValue1 + i, 0xAA)
            if self.ReadReg(RegSyncValue1 + i) != 0xAA:
                err = True
                break
        if err == True:
            print "ERROR! RFM69 not found!"
            return

        print "RFM69 found!"
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(gpio_int, GPIO.IN)
        GPIO.add_event_detect(gpio_int, GPIO.RISING, callback=self.__RfmIrq)

        self.__SetMode(MODE_STDBY)
        config = {}
        
        #SET DEFAULTS
        config[RegOpMode] = 0x04
        config[RegDataModul] = 0x00
        config[RegBitrateMsb] = 0x1A
        config[RegBitrateMsb + 1] = 0x0B
        config[RegFdevMsb] = 0x00
        config[RegFdevMsb + 1] = 0x52
        config[RegFrfMsb] = 0xE4
        config[RegFrfMsb + 1] = 0xC0
        config[RegFrfMsb + 2] = 0x00
        config[RegOsc1] = 0x41
        config[RegAfcCtrl] = 0x00
        config[0x0C] = 0x02
        config[RegListen1] = 0x92
        config[RegListen2] = 0xF5
        config[RegListen3] = 0x20
        config[RegVersion] = 0x24
        config[RegPaLevel] = 0x9F
        config[RegPaRamp] = 0x09
        config[RegOcp] = 0x1A
        config[0x17] = 0x9B
        config[RegLna] = 0x88
        config[RegRxBw] = 0x55
        config[RegAfcBw] = 0x8B
        config[RegOokPeak] = 0x40  
        config[RegOokAvg] = 0x80
        config[RegOokFix] = 0x06
        config[RegAfcFei] = 1<<3 | 1<<2
        config[RegAfcMsb] = 0x00
        config[RegAfcLsb] = 0x00
        config[RegFeiMsb] = 0x00
        config[RegFeiLsb] = 0x00
        config[RegRssiConfig] = 0x02
        config[RegDioMapping1] = 0x00
        config[RegDioMapping2] = 0x05
        config[RegIrqFlags1] = 0x80
        config[RegIrqFlags2] = 0x10
        config[RegRssiThresh] = 0xE4
        config[RegRxTimeout1] = 0x00
        config[RegRxTimeout2] = 0x00
        config[RegPreambleMsb] = 0x00
        config[RegPreambleLsb] = 0x00
        config[RegSyncConfig] = 0x98
        config[RegPacketConfig1] = 0x10
        config[RegPayloadLength] = 0x40
        config[RegNodeAdrs] = 0x00
        config[RegBroadcastAdrs] = 0x00
        config[RegAutoModes] = 0x00
        config[RegFifoThresh] = 0x8F
        config[RegPacketConfig2] = 0x02
        config[RegTemp1] = 0x01
        config[RegTemp2] = 0x00
        config[RegTestLna] = 0x1B
        config[RegTestDagc] = 0x30
        config[RegTestAfc] = 0x00

        config[RegPacketConfig1] = 0x00 #Fixed length, CRC off, no adr
        config[RegPacketConfig2] = 0 #1<<AutoRxRestartOn
        
        for key in config:
            self.__WriteReg(key, config[key])
        
        self.__SetMode(MODE_STDBY)

        print("INIT COMPLETE")
    
    def __RfmIrq(self, ch):
        self.__event.set();
    
    def __WriteReg(self, reg, val):
        temp = self.__spi.xfer2([(reg & 0x7F) | 0x80, val & 0xFF])

    def __WriteRegWord(self, reg, val):
        self.__WriteReg(reg, (val >> 8) & 0xFF)
        self.__WriteReg(reg + 1, val & 0xFF)
    
    def __SetReg(self, reg, mask, val):
        temp = self.ReadReg(reg) & (~mask)
        temp |= val & mask
        self.__WriteReg(reg, temp)
        
    def __SetDioMapping(self, dio, mapping):
        if ((dio >= 0) and (dio <=3)):
            self.__SetReg(RegDioMapping1, 0xC0 >> (dio * 2), mapping << (6 - dio * 2))
        elif (dio == 5):
            self.__SetReg(RegDioMapping2, 0x03 << 4, mapping << 4)

    def __SetMode(self, mode):
        self.__WriteReg(RegOpMode, mode << 2)
        while ((self.ReadReg(RegIrqFlags1) & (1<<7)) == 0):
            pass

    def ReadReg(self, reg):
        temp = self.__spi.xfer2([reg & 0x7F, 0x00])
        return temp[1]
        
    def ReadRegWord(self, reg):
        temp = self.__spi.xfer2([reg & 0x7F, 0x00, 0x00])
        return (temp[1] << 8) | (temp[2])
        
    def ReadRssiValue(self):
        self.__WriteReg(RegRssiConfig, 1)
        while ((self.ReadReg(RegRssiConfig) & (1<<1)) == 0):
            pass
        return self.ReadReg(RegRssiValue)
    
    def SetParams(self, **params):
        for key in params:
            value = params[key]
            if key == "Freq":
                fword = int(round(value * 1E6 / FSTEP))
                self.__WriteReg(RegFrfMsb, fword >> 16)
                self.__WriteReg(RegFrfMid, fword >> 8)
                self.__WriteReg(RegFrfLsb, fword)
            
            elif key == "TXPower":
                pwr = int(value + 18)
                self.__WriteReg(RegPaLevel, 0x80 | (pwr & 0x1F))
                
            elif key == "Datarate":
                rate = int(round(FXOSC / (value * 1000)))
                self.__WriteRegWord(RegBitrateMsb, rate)
                
            elif key == "Deviation":
                dev = int(round(value * 1000 / FSTEP))
                self.__WriteRegWord(RegFdevMsb, dev)
                
            elif key == "ModulationType":
                self.__SetReg(RegDataModul, 0x18, value << 3)
                
            elif key == "ModulationsShaping":
                self.__SetReg(RegDataModul, 0x03, value)
                
            elif key == "SyncPattern":
                conf = 0
                if (len(value)) > 0:
                    conf = ((len(value) - 1) & 0x07) << 3
                    conf |= 1<<7
                else:
                    conf = 1<<6
                self.__WriteReg(RegSyncConfig,  conf)
                for i, d in enumerate(value):
                    self.__WriteReg(RegSyncValue1 + i, d)
                    
            elif key == "Bandwidth":
                RxBw = FXOSC / value / 1000 / 4
                e = 0
                while (RxBw > 32) and (e < 7):
                    e += 1
                    RxBw /= 2
                RxBw = RxBw / 4 - 4
                RxBw = max(RxBw, 0)
                m = int(RxBw)
                self.__SetReg(RegRxBw, 0x1F, m<<3 | e)
                
            elif key == "AfcBandwidth":
                RxBw = FXOSC / value / 1000 / 4
                e = 0
                while (RxBw > 32) and (e < 7):
                    e += 1
                    RxBw /= 2
                RxBw = RxBw / 4 - 4
                RxBw = max(RxBw, 0)
                m = int(RxBw)
                self.__SetReg(RegAfcBw, 0x1F, m<<3 | e)

            elif key == "Preamble":
                self.__WriteRegWord(RegPreambleMsb, value)
                
            elif key == "LnaGain":
                self.__SetReg(RegLna, 0x03, value)

            elif key == "RssiThresh":
                th = -(value * 2)
                self.__WriteReg(RegRssiThresh, th)

            elif key == "Dagc":
                self.__WriteReg(RegDagc, value)
                
            elif key == "AfcFei":
              self.__WriteReg(RegAfcFei, value)

            else:
                print("Unrecognized option >>" + key + "<<")

    def __WaitInt(self):
        self.__event.clear()
        if not GPIO.input(self.__gpio_int):
            while not self.__event.wait(0.2):
                pass

                
    def SendPacket(self, data):
        self.__SetMode(MODE_STDBY)
        
        #flush FIFO
        status = self.ReadReg(RegIrqFlags2)
        while (status & 0x40 == 0x40):
            self.ReadReg(RegFifo)
            status = self.ReadReg(RegIrqFlags2)
            
        self.__WriteReg(RegPayloadLength, 0)
        self.__SetDioMapping(0, 0) # DIO0 -> PacketSent        
        self.__WriteReg(RegOpMode, MODE_TX << 2) #TX Mode
        
        for i, d in enumerate(data):
            self.__WriteReg(RegFifo, d)
            if i>60:
                status = self.ReadReg(RegIrqFlags2)
                #check FifoFull
                while (status & 0x80) == 0x80:
                    status = self.ReadReg(RegIrqFlags2)    

        #wait packet sent
        self.__WaitInt()
        self.__SetMode(MODE_STDBY)
                
    def ReceivePacket(self, length):
        self.__WriteReg(RegPayloadLength, length)
        
        self.__SetDioMapping(0, 2) #DIO0 -> SyncAddress
        self.__SetDioMapping(1, 3)
        self.__SetMode(MODE_RX)

        self.__WaitInt()
        self.__SetDioMapping(0, 1) #DIO0 -> PayloaReady

        rssi = -self.ReadReg(RegRssiValue) / 2
        self.__WaitInt()

        result = []
        for x in range(length):
            result.append(self.ReadReg(RegFifo))

        afc = self.ReadReg(RegAfcMsb) << 8
        afc = afc | self.ReadReg(RegAfcLsb)
        if afc >= 0x8000:
            afc = afc - 0x10000

        
        self.__SetMode(MODE_STDBY)
        
        return (result, rssi, afc)
