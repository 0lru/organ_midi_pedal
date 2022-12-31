from p3ui import *


class KeyView(Column):

    def __init__(self, main_view: 'MainView', key_index: int):
        self.main_view: 'MainView' = main_view

        super().__init__(
            align_items=Alignment.Stretch,
            children=[
                key_state_rect := Row(
                    width=(auto, 0, 0),
                    height=(2 | em, 0, 0),
                    background_color='white',
                    align_items=Alignment.Center,
                    justify_content=Justification.Center,
                    children=[Text(f'{key_index:02d}')]
                ),
                key_map_input := InputU16(width=(1 | em, 0, 0), value=key_index + 36),
                Row(
                    padding=(0 | em, 0 | em),
                    height=(auto, 0, 0),
                    justify_content=Justification.SpaceAround,
                    children=[
                        value_text := Text(f'')
                    ]
                ),
                threshold_slider := SliderU16(
                    height=(auto, 1, 1),
                    min=0, max=512,
                    direction=Direction.Vertical,
                    on_change=self._on_slider_value_changed
                )
            ]
        )
        self._key_index = key_index
        self._key_map_input = key_map_input
        self._key_state_rect = key_state_rect
        self._value_text = value_text
        self._threshold_slider = threshold_slider

    @property
    def mapped_key(self):
        return self._key_map_input.value

    @mapped_key.setter
    def mapped_key(self, value):
        self._key_map_input.value = value

    @property
    def threshold(self):
        return self._threshold_slider.value

    @threshold.setter
    def threshold(self, value):
        self._threshold_slider.value = value

    @property
    def value(self):
        return int(self._value_text.value)

    @value.setter
    def value(self, value):
        self._value_text.value = str(value)

    @property
    def state(self):
        return self._key_state_rect.background_color == 'green'

    @state.setter
    def state(self, value):
        self._key_state_rect.background_color = 'green' if value else 'white'

    def _on_slider_value_changed(self, value):
        """ whenever the value changed, update the value on the board"""
        if self.main_view.board is not None:
            command = f'm{self._key_index} {value}\n'.encode('utf8')
            self.main_view.board.write(command)
