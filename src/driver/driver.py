import asyncio
import mido
from pedal_adapter import PedalAdapter


async def main():
    with mido.open_output('Pedal', virtual=True) as mido_port:
        await PedalAdapter(
            'COM10',
            on_key_down=lambda key: print(
                'down', mido_port.send(mido.Message('note_on', note=key.index + 36, channel=1))),
            on_key_up=lambda key: print(
                'up', mido_port.send(mido.Message('note_off', note=key.index + 36, channel=1)))
        ).run()


if __name__ == "__main__":
    asyncio.run(main())
