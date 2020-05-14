import logging

from json_dict import JsonDict

from hardware_communicator.usb_commmunicator import SerialCommunicator

def put_device_property_receive_function(name,parsefunc=None):
    def f(target, data):
        if parsefunc:
            data = parsefunc(data)
        target.set_device_property(name, data)

    return f


class USBDevice(SerialCommunicator):
    AVAILABLE_QUERIES = {}

    def __init__(self, port=None, auto_port=True, interpreter=None, **kwargs):
        SerialCommunicator.__init__(
            self, port=port, auto_port=auto_port, interpreter=interpreter, **kwargs
        )
        if not hasattr(self, "config"):
            self.config = JsonDict()

    def set_device_property(self, name, value):
        self.config.put("device", "properties", name, value=value)

    def get_device_property(self, name):
        return self.config.get("device", "properties", name, autosave=False)

    def set_device_status(self, name, value):
        self.config.put("device", "status", name, value=value)

    def get_device_status(self, name):
        return self.config.get("device", "status", name, autosave=False)


SerialDevice = USBDevice
