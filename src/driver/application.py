import asyncio
import threading
import mido
import serial
import json
from pathlib import Path
import numpy as np
from p3ui import *

from key_view import KeyView

device = 'COM4'
plot_size = 512


class Configuration:

    def __init__(self, path):
        self.doc = {}
        self.path = Path(path)
        if self.path.exists():
            with open(self.path.as_posix(), 'r') as f:
                self.doc = json.load(f)

    def _save(self):
        with open(self.path.as_posix(), 'w') as f:
            json.dump(self.doc, f, indent=2)

    @property
    def key_mapping(self):
        return self.doc['key_mapping'] if 'key_mapping' in self.doc else None

    @key_mapping.setter
    def key_mapping(self, key_mapping):
        self.doc['key_mapping'] = key_mapping


class MainView(Row):

    def __init__(self, mido_port):
        self.mido_port = mido_port
        self.board: serial.Serial = None
        self.keys = [KeyView(self, i) for i in range(20)]

        super().__init__(
            justify_content=Justification.SpaceBetween,
            align_items=Alignment.Stretch,
            children=[
                Column(
                    width=(20 | em, 1, 0),
                    height=(auto, 0, 0),
                    align_items=Alignment.Stretch,
                    justify_content=Justification.Start,
                    children=[
                        Row(
                            height=(auto, 0, 0),
                            width=(auto, 1, 0),
                            justify_content=Justification.Start,
                            children=[
                                Text(device),
                                connected_text := Text(''),
                                version_text := Text(''),
                                hz_text := Text('')
                            ]
                        ),
                        plot := Plot(x_label='Voltage [V]', y_label='Time [s]', legend_location=Location.East),
                        Text('Key Mapping:'),
                        Row(
                            padding=(0 | em, 0 | em),
                            height=(auto, 0, 0),
                            children=[
                                Button(label='-', on_click=self._decrement_mapping),
                                Button(label='reset', on_click=self._reset_mapping),
                                Button(label='+', on_click=self._increment_mapping)
                            ]
                        ),
                        debug_checkbox := CheckBox(width=(auto, 0, 0), label='Live Data', on_change=self.on_debug),
                        Button(label='Calibrate', on_click=self.on_calibrate),
                        Button(label='Save Thresholds to EEPROM', on_click=self.on_store_calibration),
                    ]
                ),
                Row(
                    height=(auto, 1, 0),
                    justify_content=Justification.SpaceAround,
                    align_items=Alignment.Stretch,
                    children=self.keys
                )
            ]
        )

        self.version_text: Text = version_text
        self.connected_text: Text = connected_text
        self.hz_text: Text = hz_text
        self.debug_checkbox: CheckBox = debug_checkbox
        self.plot = plot
        self.series = [Plot.LineSeriesDouble(f'k{i}') for i in range(20)]
        for s in self.series:
            self.plot.add(s)

        self.thread_event: threading.Event = threading.Event()
        self.thread: threading.Thread = None
        self.task: asyncio.Task = asyncio.get_event_loop().create_task(self.run())

        self.update_gui()

    def _increment_mapping(self):
        for key in self.keys:
            key.mapped_key = key.mapped_key + 1

    def _reset_mapping(self):
        for index, key in enumerate(self.keys):
            key.mapped_key = index + 36

    def _decrement_mapping(self):
        for key in self.keys:
            key.mapped_key = key.mapped_key - 1

    def on_calibrate(self):
        if self.board is not None:
            self.board.write(b'c\n')

    def on_store_calibration(self):
        if self.board is not None:
            self.board.write(b'w\n')

    def on_debug(self, value):
        if self.board is not None:
            self.board.write(b'd\n')

    def update_gui(self):
        if self.board:
            self.connected_text.value = 'connected'
            self.connected_text.color = 'green'
        else:
            self.connected_text.value = 'disconnected'
            self.connected_text.color = 'black'

    def process(self, command, parameters):
        # 36
        if command == 'p':
            key_index = int(parameters)
            key = self.keys[key_index]
            key.state = True
            self.mido_port.send(mido.Message('note_on', note=key.mapped_key, channel=1))
            return
        if command == 'r':
            key_index = int(parameters)
            key = self.keys[key_index]
            key.state = False
            self.mido_port.send(mido.Message('note_off', note=key.mapped_key, channel=1))
            return
        if command == 'v':
            values = [int(p) for p in parameters.split(' ')]
            time = values[0]
            values = values[1:]
            for index, value in enumerate(values):
                self.keys[index].value = value
                s = self.series[index]
                y = np.append(s.y, time / 1000.0)
                x = np.append(s.x, value / 1024.0 * 5.0)
                if x.shape[0] > plot_size:
                    x = x[1:]
                    y = y[1:]
                s.y = y
                s.x = x
                self.plot.y_axis.inverted = True
                self.plot.x_axis.limits = (0, 5)
                self.plot.x_axis.auto_fit = False
                self.plot.x_axis.fixed = True
            return
        if command == 't':
            thresholds = [int(p) for p in parameters.split(' ')]
            for index, value in enumerate(thresholds):
                self.keys[index].threshold = value
            return
        if command == 'd':
            debug = bool(int(parameters))
            self.debug_checkbox.value = debug
        if command == 'h':
            self.hz_text.value = f'{int(parameters)}Hz'
            return
        if command == 'i':
            self.version_text.value = f'v{parameters}'
            return

    def on_thread_terminated(self):
        self.board = None
        self.thread.join()
        self.thread = None
        self.update_gui()

    def _input_thread(self, loop: asyncio.BaseEventLoop, event):
        try:
            while True:
                line = self.board.readline().decode('utf8')
                if not line:
                    continue
                command = line[0]
                parameters = line[1:-1].strip()
                # print(command, parameters)
                loop.call_soon_threadsafe(self.process, command, parameters)
        except serial.SerialException as e:
            pass
        except:
            pass
        finally:
            loop.call_soon_threadsafe(self.on_thread_terminated)

    async def run(self):
        while True:
            if self.board is None:
                try:
                    self.board = serial.Serial(port=device, baudrate=500000, timeout=.1)
                    self.thread = threading.Thread(
                        target=self._input_thread,
                        args=[asyncio.get_event_loop(), self.thread_event]
                    )
                    self.thread.start()
                except Exception as e:
                    print(e)
                    self.board = None
                finally:
                    self.update_gui()
            else:
                self.board.write(b'h\n')
            await asyncio.sleep(1)

    async def shutdown(self):
        self.task.cancel()
        if self.board is not None:
            self.board.close()
            self.thread_event.set()
            self.thread.join()
        await self.task


async def main():
    #
    # assumes that virtual port is already active
    outputs = mido.get_output_names()
    output_name = [o for o in outputs if str(o).startswith('Pedal')][0]
    mido_port = mido.open_output(output_name)

    #
    # create window
    window = Window(title='Pedal', size=(1280, 600))

    main_view = MainView(mido_port)
    window.user_interface.content = main_view
    window.user_interface.theme.make_light()

    await window.closed
    await main_view.shutdown()


run(main())
