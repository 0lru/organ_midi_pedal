import asyncio
import mido
from pedal_adapter import PedalAdapter


#
# linux mint:
# 1.) place the whole driver-folder into /opt
# 2.) create /etc/systemd/system/organ_pedal.service containing:
#
#    [Unit]
#    Description=Pedal
#
#    [Service]
#    ExecStart=/usr/bin/python3 /opt/organ/driver2.py
#
#    [Install]
#    WantedBy=multi-user.target
#
# 3.) restart the systemctl daemon: systemctl daemon-reload
# 4.) enable service: systemctl enable organ_pedal.service

async def main():
    #
    # use one virtual midi port and forward both serial inputs
    with mido.open_output('Pedal', virtual=True) as mido_port:
        adapter1 = PedalAdapter(
            '/dev/ttyUSB0',
            on_key_down=lambda key: print(
                'down', mido_port.send(mido.Message('note_on', note=key.index + 36, channel=1))),
            on_key_up=lambda key: print(
                'up', mido_port.send(mido.Message('note_off', note=key.index + 36, channel=1)))
        )

        adapter2 = PedalAdapter(
            '/dev/ttyUSB1',
            on_key_down=lambda key: print(
                'down', mido_port.send(mido.Message('note_on', note=key.index + 36 + 16, channel=1))),
            on_key_up=lambda key: print(
                'up', mido_port.send(mido.Message('note_off', note=key.index + 36 + 16, channel=1)))
        )

        task1 = asyncio.create_task(adapter1.run())
        task2 = asyncio.create_task(adapter2.run())

        await asyncio.gather(task1, task2)


if __name__ == "__main__":
    asyncio.run(main())
