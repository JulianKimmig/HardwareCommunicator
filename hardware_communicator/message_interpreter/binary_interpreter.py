import numpy as np

from hardware_communicator.message_interpreter.basic_interpreter import (
    AbstractInterpreter,
    SendItem,
)


def bytearray_to_dtype(byte_array, dtype):
    new = np.array(byte_array)
    if dtype == str:
        new = b"".join(new).decode("latin-1")
    else:
        target_size = np.dtype(dtype).itemsize
        size = len(new.tostring())
        new = np.zeros(size % target_size, dtype=np.uint8).tostring() + new.tostring()
        new = np.frombuffer(new, dtype=dtype)[0]
    return new


class BinaryInterpreter(AbstractInterpreter):
    def __init__(self):
        self.queries = {}

    def encode_data(self, data):
        return SendItem(data=bytearray(data))

    def decode_data(self, data, target):
        print(data, target)
        return data


class StartKeyDataEndInterpreter(BinaryInterpreter):
    def __init__(
        self,
        send_start_code,
        send_end_code,
        receive_start_code=None,
        receive_end_code=None,
    ):
        super().__init__()
        if receive_start_code is None:
            receive_start_code = send_start_code
        if receive_end_code is None:
            receive_end_code = send_end_code

        if isinstance(send_start_code, str):
            send_start_code = send_start_code.encode()
        if isinstance(send_end_code, str):
            send_end_code = send_end_code.encode()
        if isinstance(receive_start_code, str):
            receive_start_code = receive_start_code.encode()
        if isinstance(receive_end_code, str):
            receive_end_code = receive_end_code.encode()

        if isinstance(send_start_code, int):
            send_start_code = [send_start_code]
        if isinstance(send_end_code, int):
            send_end_code = [send_end_code]
        if isinstance(receive_start_code, int):
            receive_start_code = [receive_start_code]
        if isinstance(receive_end_code, int):
            receive_end_code = [receive_end_code]


        self.send_end_code = [x for x in send_end_code]
        self.send_start_code = [x for x in send_start_code]
        self.receive_start_code = [x for x in receive_start_code]
        self.receive_end_code = [x for x in receive_end_code]

    def encode_data(self, key, data=None):
        if data is None:
            data = []
        if isinstance(key, str):
            key = [x for x in key.encode()]
        if isinstance(data, str):
            data = [x for x in data.encode()]
        key = list(bytearray(key))

        d = super().encode_data(self.send_start_code + key + data + self.send_end_code)
        return d

    def add_query(
        self,
        name,
        key,
        send_size=0,
        receive_size=0,
        receive_function=None,
        max_receive_size=None,
        receive_dtype=None,
    ):
        if isinstance(key, str):
            key = key.encode()
        if isinstance(key, int):
            key = [key]

        if max_receive_size is None:
            max_receive_size = receive_size
        assert max_receive_size >= receive_size

        if receive_function is None:
            receive_function = print
        self.queries[name] = dict(
            key=key,
            send_size=send_size,
            receive_size=(receive_size, max_receive_size),
            receive_function=receive_function,
            receive_dtype=receive_dtype,
        )

    def prepare_query(self, name, data=None):
        if data is None:
            data = []
        assert name in self.queries, (
            str(name) + " not in queries (" + str(list(self.queries.keys())) + ")"
        )
        if self.queries[name]["send_size"] is not None:
            assert self.queries[name]["send_size"] == len(data)
        return self.encode_data(key=self.queries[name]["key"], data=data)

    def decode_data(self, data, target):
        num_data = [ord(x) for x in data]
        data_start_position = 0
        break_position = 0
        start_position=0
        if len(self.receive_start_code) > 0:
            try:
                start_position = num_data.index(self.receive_start_code[0])
                for i, c in enumerate(self.receive_start_code):
                    if c != num_data[i + start_position]:
                        data_start_position = -1
                        break_position = start_position
                        break
                if data_start_position > -1:
                    data_start_position = start_position + len(self.receive_start_code)
            except ValueError:
                return []
        if data_start_position > -1:
            data_end_position = -1
            break_position = start_position
            try:
                end_position = num_data.index(self.receive_end_code[0])
                for i, c in enumerate(self.receive_end_code):
                    if c != num_data[i + end_position]:
                        end_position = -1
                        break
                if end_position > -1:
                    data_end_position = end_position
            except:
                pass

            if data_end_position > -1:
                key_and_data = data[data_start_position:data_end_position]
                try:
                    for name, query in self.queries.items():
                        key = query["key"]
                        if key == b"".join(key_and_data[: len(key)]):
                            raw_data = key_and_data[len(key) :]
                            receive_size = query["receive_size"]
                            if receive_size[1] >= len(raw_data) >= receive_size[0]:
                                if query["receive_dtype"]:
                                    raw_data = bytearray_to_dtype(
                                        raw_data, query["receive_dtype"]
                                    )
                                try:
                                    query["receive_function"](target, raw_data)
                                except Exception as e:
                                    return data[data_end_position + 1 :]
                    return data[data_end_position + 1 :]
                except Exception as e:
                    raise e
        return data[break_position:]
