# Optional Gertboard module

This module documents the legacy board marked **21 Oct 2012**, using the revision 2
Gertboard user manual and manufacturer chip documentation. It adds a schematic
connector atlas, the cropped 26-pin J1 view and LED/button instructions. It does
not automatically detect a board, wiring, jumpers, LED state or component variants.

J1 is the connector name, not a pin number. Use the pin-1 marking, not the position
of the “J1” text. Physical positions 1–26 bring 17 Raspberry Pi signals onto the
board. Pi header pins 27–40 are outside that connector.

Legacy labels `GP0`, `GP1`, `GP21` correspond to BCM GPIO2, GPIO3, GPIO27 on the
Pi 5. B1–B12 are buffer channels assigned by wires, not fixed GPIO numbers.
PB/PC/PD belong to the separate ATmega. Additional connector pins therefore do
not create additional Raspberry Pi GPIOs.

An unconnected buffer-side input can read HIGH through its pull-up and light its
LED. The app's Pi-level reading is not a measurement of that LED connection.
Follow the in-app LED and S1 instructions, including the specified IN/OUT jumpers.
A jumper bridges the two specified contacts; its second contact is not necessarily
ground. Disconnect all power before changing any bridge or wire.

The atlas explains ADC, DAC, ATmega, motor driver and load-driver connections.
This release does not control those devices. Old BCM2835 C examples are not a
Pi 5 driver.

[Original user manual](https://www.farnell.com/datasheets/1683444.pdf)
