import asyncio
import glob
import sys

import serial

from hardware_communicator.abstract_communicator import AbstractCommunicator


def get_avalable_serial_ports(ignore=None):
    if ignore is None:
        ignore = []
    if sys.platform.startswith("win"):
        ports = ["COM%s" % (i + 1) for i in range(256)]
    elif sys.platform.startswith("linux") or sys.platform.startswith("cygwin"):
        # this excludes your current terminal "/dev/tty"
        ports = glob.glob("/dev/tty[A-Za-z]*")
    elif sys.platform.startswith("darwin"):
        ports = glob.glob("/dev/tty.*")
    else:
        raise EnvironmentError("Unsupported platform")

    ports = set(ports)

    result = []
    for port in ports.difference(ignore):
        try:
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

    def __init__(self, port=None, auto_port=True, async=True, use_asyncio=None):
        super().__init__(use_asyncio=use_asyncio)
        self.connection_checks = []
        self.port = port
        self.connected = False
        self.serial_connection = None
        self.is_open = False
        self.read_buffer = []
        if not hasattr(self, "on_connect"):
            self.on_connect = None
        if self.port:
            self.connect_to_port(port)

        if not self.connected:
            if auto_port and self.interpreter:
                self.find_port()

    def find_port(self, blocking=False, excluded_ports=None, retries=3):
        self.run_task(
            target=self._find_port,
            blocking=blocking,
            excluded_ports=excluded_ports,
            retries=retries,
        )

    async def _find_port(self, excluded_ports=None, retries=3):
        if excluded_ports is None:
            excluded_ports = []
        for port in get_avalable_serial_ports(ignore=excluded_ports):
            await self.connect_to_port(port, retries=retries)
            if self.connected:
                return port

    def add_connection_check(self, function):
        self.connection_checks.append(function)

    async def connect_to_port(self, port, retries=3):
        for i in range(retries):
            self.logger.debug(f'try connecting to port "{port} try {i + 1}/{retries}"')
            for baud in self.POSSIBLE_BAUD_RATES:
                self.logger.debug(f'try connecting to port "{port} with baud {baud}"')
                try:
                    self._open_port(port=port, baud=baud)
                    check = True
                    for func in self.connection_checks:
                        r = func()
                        if asyncio.iscoroutine(r):
                            r = await r
                        if not r:
                            check = False
                            break
                    if check:
                        self.connected = True
                        break
                    else:
                        self.stop_read(permanently=True)
                except serial.serialutil.SerialException:
                    await asyncio.sleep(1)
            if self.connected:
                self.port = port
                self.logger.info(f'successfully connected to "{port} with baud {baud}"')
                if self.on_connect:
                    self.on_connect()
                return port

    def _close_port(self):
        self.port = None
        port = None
        if self.serial_connection:
            port = self.serial_connection.port
            self.serial_connection.close()
        if self.is_open:
            self.logger.info("port closed " + port)
        self.serial_connection = None
        self.is_open = False

    def _open_port(self, port, baud):
        self.port = port
        if self.serial_connection or self.is_open:
            self._close_port()
        self.serial_connection = serial.Serial(port, baudrate=baud, timeout=0)
        self.is_open = True
        self.run_task(self.work_port, blocking=False)

    async def work_port(self):
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
            except Exception as e:
                self.logger.exception(e)
                break
            await asyncio.sleep(PORT_READ_TIME)
        self.logger.error("work_port stopped")
        self.stop_read()

    def stop_read(self, permanently=False):
        port = None
        baud = None
        if self.serial_connection:
            port = self.serial_connection.port
            baud = self.serial_connection.baudrate
        self._close_port()
        if not permanently and port:
            self._open_port(port=port, baud=baud)

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
