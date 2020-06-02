import glob
import logging
import sys
import threading
import time

import serial

from hardware_communicator.abstract_communicator import AbstractCommunicator
import serial.tools.list_ports


def get_avalable_serial_ports(ignore=None, with_connection_check=True):
    if ignore is None:
        ignore = []
    # if sys.platform.startswith("win"):
    #    ports = ["COM%s" % (i + 1) for i in range(256)]
    # elif sys.platform.startswith("linux") or sys.platform.startswith("cygwin"):
    # this excludes your current terminal "/dev/tty"
    #   ports = glob.glob("/dev/tty[A-Za-z]*")
    # elif sys.platform.startswith("darwin"):
    #    ports = glob.glob("/dev/tty.*")
    # else:
    #    raise EnvironmentError("Unsupported platform")

    ports = set([p.device for p in serial.tools.list_ports.comports()])

    result = []
    for port in ports.difference(ignore):
        try:
            if with_connection_check:
                s = serial.Serial(port)
                s.close()
            result.append(port)
        except (OSError, serial.SerialException):
            pass
    return set(result)


PORT_READ_TIME = 0.01


class SerialCommunicator(AbstractCommunicator):
    POSSIBLE_BAUD_RATES = [
        460800,
        230400,
        115200,
        57600,
        38400,
        19200,
        14400,
        9600,
        4800,
        2400,
        1200,
    ]

    def __init__(self, interpreter, port=None, auto_port=True, baud=None, **kwargs):
        super().__init__(interpreter=interpreter, **kwargs)
        self.port = port

        self.serial_connection = None
        self.is_open = False
        self.read_buffer = []
        self._work_port_task = None
        self._in_finding = False
        self._in_connecting = False
        self.auto_reconnect = True
        self.connected = False
        self.possible_baud_rates = ([baud] if baud is not None else []) + [pb for pb in self.POSSIBLE_BAUD_RATES if
                                                                           pb != baud]

        if self.port:
            def ap():
                time.sleep(0.5)
                self.connect_to_port(port)

            threading.Thread(target=ap, daemon=True).start()

        if not self.connected:
            if auto_port and self.interpreter:
                def ap():
                    time.sleep(0.7)
                    self.find_port()

                threading.Thread(target=ap, daemon=True).start()

    def stop_finding(self):
        self._in_finding = False
        self._in_connecting = False

    def find_port(
            self, excluded_ports=None, retries=3, start_ports=None, start_bauds=None
    ):
        if start_bauds is None:
            start_bauds = []
        if start_ports is None:
            start_ports = []
        if self.connected:
            return self.port
        if self._in_finding:
            return None
        self._in_finding = True

        if excluded_ports is None:
            excluded_ports = []

        ports = start_ports + list(
            get_avalable_serial_ports(ignore=list(excluded_ports) + start_ports)
        )
        self.logger.info("Check ports" + str(ports))
        for port in ports:
            if self._in_finding:
                self.connect_to_port(port, retries=retries, baud_rates=start_bauds)
            if self.connected:
                self._in_finding = False
                return self.port
        self._in_finding = False

    def try_to_connect(
            self, excluded_ports=None, retries=3, port=None, baud=None, **kwargs
    ):
        if baud is None:
            baud = []
        if not isinstance(baud, list):
            baud = [baud]
        if port is None:
            port = []
        if not isinstance(port, list):
            port = [port]

        return self.find_port(
            excluded_ports=excluded_ports,
            retries=retries,
            start_ports=port,
            start_bauds=baud,
        )

    def connect_to_port(self, port, retries=3, baud_rates=None):
        if baud_rates is None:
            baud_rates = []
        ini_arc = self.auto_reconnect
        self.auto_reconnect = False
        self._in_connecting = True
        for i in range(max(1, retries)):
            if not self._in_connecting:
                break
            self.logger.debug(f'try connecting to port "{port} try {i + 1}/{retries}"')
            for baud in set(baud_rates + self.possible_baud_rates):
                if not self._in_connecting:
                    break
                self.logger.debug(f'try connecting to port "{port} with baud {baud}"')
                try:
                    self._start_work_port_thread(port,baud)
                    time.sleep(0.1)
                    check = True
                    for func in self.connection_checks:
                        r = False
                        if self._in_connecting:
                            r = func()
                        if not r:
                            check = False
                            break
                    if check:
                        self.connected = True
                        break
                    else:
                        self.stop_read(permanently=True)
                        time.sleep(0.5)
                except serial.serialutil.SerialException:
                    time.sleep(0.5)
            if self.connected:
                self.port = port
                self.logger.info(f'successfully connected to "{port} with baud {baud}"')
                if self.on_connect:
                    self.on_connect()
                self.auto_reconnect = ini_arc
                self._in_connecting = False
                return port
        self.auto_reconnect = ini_arc
        self._in_connecting = False
        return None

    def _close_port(self):
        self.port = None
        port = None
        self.is_open = False
        time.sleep(PORT_READ_TIME * 2)
        if self.serial_connection:
            port = self.serial_connection.port
            try:
                self.serial_connection.close()
            except:
                pass
        if self.is_open:
            self.logger.info("port closed " + port)
        self.serial_connection = None

    def _open_port(self, port, baud):
        self.port = port
        if self.serial_connection or self.is_open:
            self._close_port()
        self.serial_connection = serial.Serial(port, baudrate=baud, timeout=0)
        self.read_buffer = []
        self.is_open = True
        self.work_port()

    def work_port(self):
        while self.is_open:
            try:
                if self.is_open:
                    self._write_to_port()
                    try:
                        c = self.serial_connection.read()
                    except AttributeError as e:
                        c = ""
                    while len(c) > 0:
                        # print(ord(c),c)
                        self.read_buffer.append(c)
                        self.validate_buffer()
                        if not self.is_open:
                            break
                        try:
                            c = self.serial_connection.read()
                        except AttributeError as e:
                            c = ""
                time.sleep(PORT_READ_TIME)
            except Exception as e:
                self.logger.exception(e)
                self.stop_read()
        self.logger.error("work_port stopped")
        self.stop_read(permanently=True)

    def stop_read(self, permanently=None):
        port = None
        baud = None
        if self.serial_connection:
            port = self.serial_connection.port
            baud = self.serial_connection.baudrate

        self._close_port()
        if permanently is None:
            permanently = not self.auto_reconnect
        if not permanently and port:
            if threading.current_thread().name == "work_port_thread":
                self._open_port(port=port, baud=baud)
            else:
                self._start_work_port_thread(port,baud)

    def detatch(self):
        self.stop_read(permanently=True)

    def write_to_port(self, send_item):
        return self.send_queue.append(send_item)

    def _write_to_port(self):
        #   if(len(self.send_queue)>0):
        # print(self.port, self.send_queue)
        for item in self.send_queue:
            try:
                self.serial_connection.write(list(item.data))
            except Exception as e:
                self.logger.error(f"cannot write {item}")
                raise e
            item.sended(self)

    def validate_buffer(self):
        self.read_buffer = self.interpreter.decode_data(self.read_buffer, self)

    def get_connection_info(self):
        d = super().get_connection_info()
        try:
            d["port"] = self.serial_connection.port
            d["baud"] = self.serial_connection.baudrate
        except:
            pass
        return d

    def _start_work_port_thread(self,port,baud):
        self._work_port_task = threading.Thread(target=self._open_port, kwargs={'port': port, 'baud': baud},
                                                daemon=True)
        self._work_port_task.name = "work_port_thread"
        self._work_port_task.start()
