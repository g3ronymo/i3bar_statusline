#!/usr/bin/env python3
"""
Simple Python script implementing the
`i3bar-protocol <https://i3wm.org/docs/i3bar-protocol.html>`_.
"""
import time
import zoneinfo
import datetime
import json
import abc
import subprocess
import signal


class Block(metaclass=abc.ABCMeta):
    """Base class for all Statusline blocks"""

    def __init__(self, name, update_interval):
        """"
        ``update_interval`` is the periode in seconds after which the block
        should update its cache before returning its attributes.
        """
        self.update_interval = update_interval
        self.last_update = time.time()
        self._attr = {
            "full_text": None,
            #"short_text": None,
            #"color": "#00ff00",
            #"background": "#1c1c1c",
            #"border": "#ee0000",
            #"border_top": 1,
            #"border_right": 0,
            #"border_bottom": 3,
            #"border_left": 1,
            #"min_width": 300,
            #"align": "right",
            #"urgent": False,
            "name": name,
            #"instance": None,
            #"separator": True,
            #"separator_block_width": 9,
            #"markup": "none",
        }
        self.update()

    @abc.abstractmethod
    def update(self):
        """
        Update the attributes in the dictonary *self._attr*.
        Should be implemented by every subclass of Block.
        """

    def get_attributes(self) -> dict:
        """
        Calls the *update* method if needed and returns a dictonary with
        the attributes of this block.
        """
        if time.time() - self.last_update >= self.update_interval:
            self.update()
            self.last_update = time.time()
        return self._attr


class TimeBlock(Block):
    """Get the current time"""
    def update(self):
        tz = zoneinfo.ZoneInfo('Europe/Berlin')
        now = datetime.datetime.now(tz)
        self._attr['full_text'] = now.strftime('%H:%M')

class DateBlock(Block):
    """Get the current date"""
    def update(self):
        tz = zoneinfo.ZoneInfo('Europe/Berlin')
        now = datetime.datetime.now(tz)
        self._attr['full_text'] = now.strftime('%d.%m.%Y')

class IwdStatusBlock(Block):
    """Get wifi status from iwd"""
    def update(self):
        iwctl_output = subprocess.run(
                ['iwctl', 'station', 'wlan0', 'show'],
                capture_output=True)
        iwctl_output = iwctl_output.stdout.strip().splitlines()
        connected_network = b'No wlan connection'
        for line in iwctl_output:
            if b'network' in line:
                line_parts = line.strip().split()
                connected_network = line_parts[2]
        self._attr['full_text'] = str(connected_network, encoding='utf-8')

class NetworkManagerWIFIBlock(Block):
    """Get wifi status from NetworkManager""" 
    def update(self):
        nmcli_output = subprocess.run(
                'nmcli -f GENERAL.CONNECTION device show wlan0'.split(),
                capture_output=True)
        connected_network = nmcli_output.stdout.split()
        if len(connected_network) == 0:
            connected_network = b"No wlan connection"
        else:
            connected_network = connected_network[-1]
        self._attr['full_text'] = str(connected_network, encoding='utf-8')

class AudioBlock(Block):
    """Get audio with pamixer"""
    def update(self):
        try:
            volume = subprocess.run(
                    ['pamixer', '--get-volume'], text=True, capture_output=True,
                    check=True
            )
        except subprocess.CalledProcessError:
            self._attr['full_text'] = 'Could not find audio'
            return
        mute = subprocess.run(
                ['pamixer', '--get-mute'], text=True, capture_output=True,
        )
        mute = mute.stdout.strip().upper() == 'TRUE'
        volume = volume.stdout.strip()
        if mute:
            self._attr['full_text'] = '\U0001F507 ' + volume + '%'
        elif int(volume) < 33.3:
            self._attr['full_text'] = '\U0001F508 ' + volume + '%'
        elif int(volume) < 66.3:
            self._attr['full_text'] = '\U0001F509 ' + volume + '%'
        else:
            self._attr['full_text'] = '\U0001F50A ' + volume + '%'


class CpuBlock(Block):
    """Get average cpu usage"""
    def update(self):
        mhz_cpu = []
        with open('/proc/cpuinfo') as cpuinfo:
            temp = cpuinfo.read()
            temp = temp.splitlines()
            for line in temp:
                if line.find('cpu MHz') > -1:
                    mhz = line.split()
                    mhz = mhz[len(mhz)-1]
                    mhz_cpu.append(float(mhz))
        average = int(sum(mhz_cpu) / len(mhz_cpu))
        self._attr['full_text'] = str(average) + ' MHz'

class RamBlock(Block):
    """
    Get ram usage.
    ram_usage = MemTotal - MemFree - Buffers - Cached - SReclaimable
    """
    def update(self):
        d_meminfo = {}
        with open('/proc/meminfo') as meminfo:
            lines = meminfo.readlines()
        for line in lines:
            line = line.split()
            key = line[0]
            value = int(line[1])
            d_meminfo[key] = value
        # trailing ':' is already there in /proc/meminfo and removing it is
        # not realy necessary
        ram_usage_kb = (d_meminfo['MemTotal:']
                        - d_meminfo['MemFree:']
                        - d_meminfo['Buffers:']
                        - d_meminfo['Cached:']
                        - d_meminfo['SReclaimable:'])
        # convert ram_usage from kB to Gb
        ram_usage = round((ram_usage_kb / 1000000), 2)
        self._attr['full_text'] = str(ram_usage) + ' Gb'


class XkbLayoutState(Block):
    """
    Get name of current keyboard layout.
    Depends on: `xkblayout-state <https://github.com/nonpop/xkblayout-state>`_
    """
    def update(self):
        output = subprocess.run(['xkblayout-state', 'print', '%n'],
                text=True, capture_output=True)
        self._attr['full_text'] = output.stdout.strip()



class StatusLine:
    """
    Used to build the statusline.
    *__init__* expects Block objects as arguments.
    """
    def __init__(self, *blocks):
        for elem in blocks:
            if not isinstance(elem, Block):
                raise ValueError(f'"{elem}" is not a subclass of "Block"')
        self.blocks = blocks

    def print(self):
        """Print one statusline"""
        statusline = []
        for elem in self.blocks:
            statusline.append(elem.get_attributes())
        print(json.dumps(statusline) + ",")

def handle_stop_signal(signal_num, frame):
    """
    Handle the *stop_signal* defined in the i3bar-protocol header block.
    """
    sig_set = set()
    sig_set.add(signal.SIGCONT)
    signal.sigwait(sig_set)

def handle_cont_signal(signal_num, frame):
    """
    Handle the *cont_signal* defined in the i3bar-protocol header block.
    """
    pass


def main():
    """Main function"""
    HEADER = {
            "version": 1,
            "stop_signal": int(signal.SIGUSR1),
            "cont_signal": int(signal.SIGCONT),
            "click_events": True,
    }
    signal.signal(signal.SIGUSR1, handle_stop_signal)
    signal.signal(signal.SIGCONT, handle_cont_signal)
    statusline1 = StatusLine(
            # Blocks go here
    )
    print(json.dumps(HEADER))
    print('[')
    while True:
        statusline1.print()
        time.sleep(0.1)

if __name__ == '__main__':
    main()
