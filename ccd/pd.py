##
## This file is part of the libsigrokdecode project.
##
## Copyright (C) 2017 Marek Wodzinski <majek@mamy.to>
##
## This program is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published by
## the Free Software Foundation; either version 2 of the License, or
## (at your option) any later version.
##
## This program is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with this program; if not, write to the Free Software
## Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301 USA
##

import sigrokdecode as srd
from math import floor, ceil

'''
OUTPUT_PYTHON format:

TO DO!!!!!!!!!!
Packet:
'''


class SamplerateError(Exception):
    pass



# main decoder class
class Decoder(srd.Decoder):
    # api keys
    api_version = 2
    id = 'ccd'
    name = 'CCD'
    longname = 'CCD (Crysler Collision Detection) Data Bus'
    desc = "CCD (Crysler Collision Detection) Data Bus."
    license = 'gplv2+'
    inputs = ['logic']
    outputs = ['ccd']
    channels = (
        {'id': 'bus', 'name': 'bus', 'desc': 'CCD bidirectional shared data bus'},
    )
    options = (
	{'id': 'ignoreerrors', 'desc': "Ignore checksum and frame errors", 'default': 'no',
	    'values': ('yes', 'no')},
        {'id': 'format', 'desc': 'Data format', 'default': 'hex',
            'values': ('ascii', 'dec', 'hex', 'oct', 'bin')},
        {'id': 'invert_bus', 'desc': 'Invert bus?', 'default': 'no',
            'values': ('yes', 'no')},
    )
    annotations = (
        ('bus-bits', 'Bus data bits'),
        ('bus', 'Bus data'),
        ('idle', 'Bus idle'),
        ('frame-error', 'Frame errors'),
        ('checksum', 'Message checksum errors'),
        ('bus-decoded','Decoded bus message'),
    )
    annotation_rows = (
        ('bus-bits', 'Bus bits', (0,)),
        ('idle', 'Idle', (2,)),
        ('bus-warnings', 'Bus warnings', (3,4)),
        ('bus-data', 'Bus', (1,)),
        ('bus-decoded', 'BUS', (5,)),
    )
    #binary = (
    #    ('message', 'CCD dump'),
    #)
    # end of api keys
    

    # Object initialization
    def __init__(self):
        self.samplerate = None
        self.samplenum = 0
        self.startsample = -1
        self.state = 'WAIT FOR START BIT'
        self.idle = 'IDLE'
        self.idletime = -1
        self.busystart = -1
        self.oldbus = 1
        self.ccd_message = []
        self.databit=0
        self.databyte=0
        self.framestart=-1
        self.waitfotime=-1
        self.errors=0
        self.vin='_________________'


    # API function called before decoding
    def start(self):
        #self.out_python = self.register(srd.OUTPUT_PYTHON)
        #self.out_binary = self.register(srd.OUTPUT_BINARY)
        self.out_ann = self.register(srd.OUTPUT_ANN)


    # API metadata (to get samplerate)
    def metadata(self, key, value):
        if key == srd.SRD_CONF_SAMPLERATE:
            self.samplerate = value
            # The width of one UART bit in number of samples.
            # CCD bus speed is 7812.5 bps, so it can be hardcoded here
            self.bit_width = ceil(float(self.samplerate) / 7812.5)


    # emit annotation in CCD decoded bus row
    def ccd_ann(self,annotation):
        self.put(self.busystart, self.samplenum-1, self.out_ann, [5, annotation ])
    

    # real stuff here
    def decode_ccd_message(self):
        
        if self.ccd_message[0] == 0x24:
            # speed
            # 4 bytes total
            # 0x24, AA, BB, checksum
            # AA = speed miles/h
            # BB - spedd km/h
            kmh = str(self.ccd_message[2])
            mph = str(self.ccd_message[1])
            self.ccd_ann(['Speed: '+kmh + ' km/h, '+mph+' mph', kmh + 'km/h'])

        elif self.ccd_message[0] == 0xE4:
            # rpm+map
            # 4 bytes total
            # 0xe4, AA, BB, checksum
            # rpm = AA*32 rpm
            # map = BB*0.41 kPa / BB
            rpm = str(self.ccd_message[1]*32)
            mapsensor = str(round(self.ccd_message[2]*0.41))
            self.ccd_ann(['RPM: '+rpm+' rpm, MAP: '+mapsensor+' kPa', 'RPM='+rpm+',MAP='+mapsensor,'R'+rpm+',M'+mapsensor])

        elif self.ccd_message[0] == 0x6D:
            # VIN
            # 4 bytes total
            # 0x6d, AA, BB, checksum
            # one character at a time, VIN[AA] = BB
            pos = self.ccd_message[1]
            char = chr(self.ccd_message[2])
            self.vin = self.vin[:pos-1]+char+self.vin[pos:]
            self.ccd_ann(['VIN character '+str(pos)+': '+char+', VIN: '+self.vin,'VIN['+str(pos)+']:'+char+',VIN:'+self.vin,'VIN['+str(pos)+']:'+char])

        elif self.ccd_message[0] == 0x86:
            # (un)lock doors, alarm
            # CHECK THIS
            if self.ccd_message[1] == 128:
                #message from DDM to PDM
                self.ccd_ann(['DDM: ' + hex(self.ccd_message[2]),'DDM:' + hex(self.ccd_message[2])[2:],'DDM:' + hex(self.ccd_message[2])[2:]])
            elif self.ccd_message[1] == 129:
                self.ccd_ann(['PDM: ' + hex(self.ccd_message[2]),'PDM:' + hex(self.ccd_message[2])[2:],'PDM:' + hex(self.ccd_message[2])[2:]])
            else:
                self.ccd_ann(['unknown message from DDM/PDM: ' + hex(self.ccd_message[1]) + ' ' + hex(self.ccd_message[2]),'UNK DDM/PDM:' + hex(self.ccd_message[1])[2:]+ hex(self.ccd_message[2])[2:], 'UNK DDM/PDM:' + hex(self.ccd_message[1])[2:]+ hex(self.ccd_message[2])[2:]])
        
        elif self.ccd_message[0] == 0x42:
            # TPS/Cruise
            # not tested
            tps = str(self.ccd_message[1])
            cruise = str(self.ccd_message[2])
            self.ccd_ann(['TPS: ' + tps + ', CRUISE: '+cruise,'TPS:'+tps+',CRUISE:'+cruise])
            
        elif self.ccd_message[0] == 0x35:
            # Ingition switch status bits
            # 4 bytes total
            # 0x35, AA, BB, checksum
            # bits:
            # AA:
            # 0 - interior lamps, 1=switched on
            # 1 - always 1
            # 2 - key in accesory position
            # 3
            # 4 - key in run position
            # 5 - key in start position
            # 6
            # 7
            # BB: unknown (always 0x00 in my dumps)
            # 2 - engine warm?
            # CHECK THIS
            ign = self.ccd_message[1]
            ignstr = "{0:08b}".format(ign) + ' '+str(self.ccd_message[2])
            self.ccd_ann(['Ignition switch: ' + ignstr, 'IGN:'+ignstr, 'IGN:'+ignstr])

        elif self.ccd_message[0] == 0xA4:
            # Instrumental cluster lamps
            # 4 bytes total
            # 0xa4, AA, BB, checksum
            # AA:
            # 0
            # 1 - 1 if car is accelerating
            # 2 - brake pressed
            # 3 - A/C compressor clutch (1 - idle, 0 - engaged)
            # 4 - overdrive clutch
            # 5
            # 6 - not in P or N
            # 7
            # BB: always 0x00?
            lamps = self.ccd_message[1]
            lampsstr = "{0:08b}".format(lamps) + ' '+hex(self.ccd_message[2])
            self.ccd_ann(['Instrumental cluster lamps: ' + lampsstr, 'LAMPS:'+lampsstr])

        elif self.ccd_message[0] == 0x8C:
            # Temperatures
            # not tested
            engtemp = str(self.ccd_message[1]-128)
            battemp = str(self.ccd_message[2]-128)
            self.ccd_ann(['Engine temperature: '+engtemp+', battery temperature: '+battemp,'EngTemp='+engtemp+',BatTemp='+battemp])
        
        elif self.ccd_message[0] == 0x84:
            # Increment odometer
            # resoluton 0.000125 mi/bit? ~20cm?
            # 4 bytes total
            # 0x84, AA, BB, checksum
            # increment = 256*AA+BB
            self.ccd_ann(['Increment odometer: '+str(256*self.ccd_message[1]+self.ccd_message[2])])

        elif self.ccd_message[0] == 0x7B:
            # Ambient temperature
            # 3 bytes total
            # 0x7b, AA, checksum
            # temp (F) = AA-70
            ambientf=str(self.ccd_message[1]-70)
            ambientc=str(floor((self.ccd_message[1]-70-32)*5/9))
            self.ccd_ann(['Ambient temperature: '+ambientf+' F ('+ambientc+' C)','AmbTemp:'+ambientf])
        
        elif self.ccd_message[0] == 0x82:
            # Steering wheel keys for radio
            # 5 bytes total
            # 0x82, AA, BB, CC, checksum
            # in my car always 0x20, 0x00, 0x00
            volume=hex(self.ccd_message[1])[2:]+' '+hex(self.ccd_message[2])[2:]+' '+hex(self.ccd_message[3])[2:]
            self.ccd_ann(['Steering wheel volume buttons: '+volume, 'volume: '+volume])
            
        elif self.ccd_message[0] == 0x8E:
            # Doors
            # 3 bytes total
            # 0x8e, AA, checksum
            # 0 - Left Front (1=open)
            # 1 - Right Front
            # 2 - Left Rear
            # 3 - Right Rear
            # 4 - Liftgate
            # 5
            # 6
            # 7 - set only during kick-start
            doors = self.ccd_message[1]
            doorsdec = ''
            doorsstr = "{0:08b}".format(doors)
            if doors & 0x01:
                doorsdec += ' LeftFront'
            if doors & 0x02:
                doorsdec += ' RightFront'
            if doors & 0x04:
                doorsdec += ' LeftRear'
            if doors & 0x08:
                doorsdec += ' RightRear'
            if doors & 0x10:
                doorsdec += ' Liftgate'
            if doors & 0xe0:
                doorsdec += ' unknown:'+doorsstr
            self.ccd_ann(['Doors:' + doorsdec])
        
        elif self.ccd_message[0] == 0xFE:
            # PWM pannel lamp dim
            # 3 bytes total
            # 0xfe, AA, checksum
            # AA - pwm value (0-255)
            pwm = floor(self.ccd_message[1]/2.56)
            self.ccd_ann(['Pannel lamp dim: ' + str(pwm) + '%'])

        elif self.ccd_message[0] == 0xEE:
            # trip distance
            # 5 bytes total
            # 0xee, AA, BB, CC, checksum
            # distance = 0xAABBCC/4971 km
            trip = round(((65536*self.ccd_message[1]+256*self.ccd_message[2]+self.ccd_message[3])*128)/4971,1)
            self.ccd_ann(['Trip distance: ' + str(trip) + ' km'])
            
        elif self.ccd_message[0] == 0x50:
            # airbag lamp
            # 3 bytes total
            # 0x50, AA, checksum
            # AA=0: OK
            # AA=1: PROBLEM
            if self.ccd_message[1] == 0:
                airbag = 'OFF'
            else:
                airbag = 'PROBLEM'
            self.ccd_ann(['Airbag lamp: ' + airbag])

        elif self.ccd_message[0] == 0x25:
            # fuel level
            # 3 bytes total
            # 0x25, AA, checksum
            # fuel level = AA (0-255 scale)
            pwm = floor(self.ccd_message[1]/2.56)
            self.ccd_ann(['Fuel level: ' + str(pwm) + '%'])

        elif self.ccd_message[0] == 0x0c:
            # voltage+temperatures+oil pressure
            # 6 bytes total
            # 0x0c, AA, BB, CC, DD, checksum
            # - battery voltage = AA/8 V
            # - oil pressure = BB/32 ?
            # - engine temperature = CC - 64 C
            # - battery temperature = DD -64 C
            voltage = str(self.ccd_message[1]/8)
            oil = str(self.ccd_message[2]/32)
            engtemp = str(self.ccd_message[3]-64)
            battemp = str(self.ccd_message[4]-64)
            self.ccd_ann(['Engine temperature: '+engtemp+' C, battery temperature: '+battemp+' C, battery voltage: '+voltage +' V, oil pressure: '+oil,'EngTemp='+engtemp+',BatTemp='+battemp])
            
        elif self.ccd_message[0] == 0xda:
            # check engine lamp
            # 3 bytes total
            # 0xda, AA, checksum
            # AA:
            # 0 - always 0?
            # 1 - always 0?
            # 2 - always 0?
            # 3 - always 0?
            # 4 - always 0?
            # 5 - always 1?
            # 6 - check engine lamp (1=lit)
            # 7 - always 0?
            if self.ccd_message[1] & 0x40 == 0:
                mil = 'OFF'
            else:
                mil = 'PROBLEM'
            self.ccd_ann(['Check engine lamp: ' + mil])
            
        elif self.ccd_message[0] == 0xCE:
            # Odometer
            # 6 bytes total
            # 0xce, AA, BB, CC, DD, checksum
            # odo = 0xAABBCCDD / 4971 km
            odo = (16777216*self.ccd_message[1]+65536*self.ccd_message[2]+256*self.ccd_message[3]+self.ccd_message[4])//4971
            self.ccd_ann(['Odo: ' + str(odo) + ' km'])
            
        elif self.ccd_message[0] == 0x62:
            # electric doors/mirrors
            # 4 bytes total
            # 0x62, AA, BB, checksum
            # AA: electric windows control (idle state: 1)
            # 0 - left front down
            # 1 - left front up
            # 2 - right front down
            # 3 - right front up
            # 4 - left rear down
            # 5 - left rear up
            # 6 - right rear down
            # 7 - right rear up
            # bits 7-2 = 0 if windows lock activated
            # BB: electric mirrors (idle state = 0)
            # 0 - left mirror up
            # 1 - left mirror down
            # 2 - left mirror left
            # 3 - left mirror right
            # 4 - right mirror up
            # 5 - right mirror down
            # 6 - right mirror left
            # 7 - right mirror right
            
            # windows
            dmess=''
            if self.ccd_message[1] & 0x01 == 0:
                dmess += " LF_up"
            if self.ccd_message[1] & 0x02 == 0:
                dmess += " LF_down"
            if self.ccd_message[1] & 0xfc == 0:
                dmess += " windows locked"
            else:
                if self.ccd_message[1] & 0x04 == 0:
                    dmess += " RF_down"
                if self.ccd_message[1] & 0x08 == 0:
                    dmess += " RF_up"
                if self.ccd_message[1] & 0x10 == 0:
                    dmess += " LR_down"
                if self.ccd_message[1] & 0x20 == 0:
                    dmess += " LR_up"
                if self.ccd_message[1] & 0x40 == 0:
                    dmess += " RR_down"
                if self.ccd_message[1] & 0x80 == 0:
                    dmess += " RR_up"
            #mirrors
            mmess=''
            if self.ccd_message[2] & 0x01:
                mmess += " L_up"
            if self.ccd_message[2] & 0x02:
                mmess += " L_down"
            if self.ccd_message[2] & 0x04:
                mmess += " L_left"
            if self.ccd_message[2] & 0x08:
                mmess += " L_right"
            if self.ccd_message[2] & 0x10:
                mmess += " R_up"
            if self.ccd_message[2] & 0x20:
                mmess += " R_down"
            if self.ccd_message[2] & 0x40:
                mmess += " R_left"
            if self.ccd_message[2] & 0x80:
                mmess += " R_right"

            self.ccd_ann(['Windows:'+dmess+', mirrors:'+mmess])

        else:
            # not decoded yet
            message=''
            for byte in self.ccd_message:
                message += hex(byte)[2:] + ' '
            self.ccd_ann(['Unknown CCD message: '+message, 'CCD: '+message , message])


    # Main decode function called by API
    def decode(self, ss, es, data):
	# check if samplerate is set
        if not self.samplerate:
            raise SamplerateError('Cannot decode without samplerate.')
        
        # iterate through sample data (samplenum, channels)
        for (self.samplenum, channels) in data:

            bus = int.from_bytes(channels, byteorder='little')

	    # invert input if requested
            if self.options['invert_bus'] == 'yes':
                bus = 1-bus
            
            # IDLE handling
            if self.oldbus != bus:
        	# bus changed
                if self.idle == 'BUSY':
        	    # for busy only update idletime
                    self.idletime = self.samplenum
                else:
        	    # for idle: emit annotation and change state
                    self.put(self.idletime, self.samplenum-1, self.out_ann, [2, ['Idle', 'Id', 'I']])
                    self.idle = 'BUSY'
                    self.idletime = self.samplenum
                    self.busystart = self.samplenum
            else:
        	# bus not changed
                if self.idle == 'BUSY' and bus and self.samplenum-self.idletime > self.bit_width*10:
        	    # idle for more than 10 bits - change state
                    self.put(self.busystart, self.samplenum-1, self.out_ann, [2, ['Busy', 'Bsy', 'B']])
                    self.idle = 'IDLE'
                    self.idletime = self.samplenum
                    
                    # BUSY ended, time to decode collected bytes
                    
                    # check message checksum
                    chksum = 0
                    for byte in self.ccd_message:
                        chksum += byte
                    chksum -= byte
                    chksum = chksum % 256;
                    if byte != chksum:
                        # emit annotation for bad checksum
                        self.put(self.busystart, self.samplenum-1, self.out_ann, [4, ['Checksum error', 'Bad sum', 'CHK']])
                        self.errors =+ 1
                        
                    if self.errors == 0 or self.options['ignoreerrors'] == 'yes':
                        # process frame only if no errors
                        self.decode_ccd_message()

                    # clear at the end
                    self.ccd_message = []
                    self.errors = 0


            # serial protocol handling
            if self.state == 'WAIT FOR START BIT':
                if self.oldbus and not bus:
                    # initialize byte
                    self.databit = 0
                    self.databyte = 0
                    self.framestart = self.samplenum
                    # set next sampling point
                    self.waitfortime = self.samplenum+ceil(1.5*self.bit_width)
                    # change state
                    self.state = 'GET DATA BITS'
                    # emit annotation
                    self.put(self.samplenum, self.samplenum+self.bit_width-1, self.out_ann, [0, ['Start bit', 'Start', 'S']])
                    
            elif self.state == 'GET DATA BITS':
                if self.samplenum >= self.waitfortime:
                    # calculate new byte value
                    self.databyte = self.databyte // 2
                    if bus:
                        self.databyte += 128
                    # annotation: bit
                    self.put(self.samplenum-ceil(self.bit_width/2), self.samplenum+floor(self.bit_width/2)-1, self.out_ann, [0, [str(bus), str(bus), str(bus)]])
                    # set next sample point
                    self.waitfortime = self.samplenum+self.bit_width
                    # next bit
                    self.databit += 1
                    if self.databit == 8:
                        # full byte acquired, append it to ccd message
                        self.ccd_message.append(self.databyte)
                        # next state
                        self.state = 'GET STOP BIT'
                        # emit byte to annotation
                        self.put(self.framestart+self.bit_width, self.samplenum+floor(self.bit_width/2), self.out_ann, [1, [hex(self.databyte), hex(self.databyte)[2:], hex(self.databyte)[2:] ]])
            elif self.state == 'GET STOP BIT':
                if self.samplenum >= self.waitfortime:
                    if not bus:
                        # frame error
                        self.errors += 1
                        self.put(self.framestart, self.samplenum+floor(self.bit_width/2), self.out_ann, [3, ['Frame error', 'Fr.ERR', 'FE' ]])
                    # emit annotation for stop bit
                    self.put(self.samplenum-ceil(self.bit_width/2), self.samplenum+floor(self.bit_width/2)-1, self.out_ann, [0, ['Stop bit', 'Stop', 'E']])
                    # change next state
                    self.state = 'WAIT FOR START BIT'
                    # extend idle (a must for bytes like 0xff)
                    self.idletime = self.samplenum
                    
    	    # update old status
            self.oldbus = bus
