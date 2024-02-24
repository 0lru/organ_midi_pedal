import serial
import threading
import asyncio


class Key:

    def __init__(self, pedal, index):
        self.threshold = None
        self.state = False
        self.pedal = pedal
        self.index = index


class PedalAdapter:
    """
    asynchronous pedal adapter.
    """

    def __init__(self, serial_id: str, on_key_down, on_key_up):
        self.serial_id = serial_id
        self.on_key_down = on_key_down
        self.on_key_up = on_key_up
        self._serial: serial.Serial = None
        self._keys = [Key(self, i) for i in range(20)]
        self._thread = None

        self.connected: bool = False
        self.version: str = None
        self.debug: bool = False
        self.hz: float = 0.0

    def _input_thread(self, loop: asyncio.BaseEventLoop):
        try:
            while True:
                line = self._serial.readline().decode('utf8')
                if not line:
                    continue
                command = line[0]
                parameters = line[1:-1].strip()
                loop.call_soon_threadsafe(self._process_command, command, parameters)
        except serial.SerialException as e:
            print(e)
        finally:
            loop.call_soon_threadsafe(self._on_thread_exit)

    def _process_command(self, command, parameters):
        print(command, parameters)
        if command == 'p':
            key_index = int(parameters)
            key = self._keys[key_index]
            key.state = True
            if self.on_key_down:
                self.on_key_down(key)
#            self.mido_port.send(mido.Message('note_on', note=key.mapped_key, channel=1))
            return
        if command == 'r':
            key_index = int(parameters)
            key = self._keys[key_index]
            key.state = False
            if self.on_key_up:
                self.on_key_up(key)
#            self.mido_port.send(mido.Message('note_off', note=key.mapped_key, channel=1))
            return
        if command == 'v':
            values = [int(p) for p in parameters.split(' ')]
            time = values[0]
            values = values[1:]
            print(f'Time: {time}, Values: {values}')
        if command == 't':
            thresholds = [int(p) for p in parameters.split(' ')]
            for index, value in enumerate(thresholds):
                self._keys[index].threshold = value
            return
        if command == 'd':
            debug = bool(int(parameters))
            self.debug = debug
        if command == 'h':
            self.hz = f'{int(parameters)}Hz'
            return
        if command == 'i':
            self.version = f'v{parameters}'
            return

    def _on_thread_exit(self):
        self.connected = False

    async def run(self):
        while True:
            if self._serial is None:
                try:
                    self._serial = serial.Serial(port='/dev/ttyUSB0', baudrate=500000, timeout=.1)
                    self.connected = True
                    self._thread = threading.Thread(target=self._input_thread, args=[asyncio.get_event_loop()])
                    self._thread.start()
                except Exception as e:
                    print(e)
                    self._serial = None
            else:
                self._serial.write(b'h\n')
            await asyncio.sleep(1)
        print('loop exited')
