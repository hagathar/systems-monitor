#!/usr/bin/env python3
"""Read AS5600 angle sensors connected through a PCA9548A I2C multiplexer."""

import argparse
import sys
import time

AS5600_DEFAULT_ADDRESS = 0x36
AS5600_STATUS_REGISTER = 0x0B
AS5600_RAW_ANGLE_REGISTER = 0x0C
PCA9548A_DEFAULT_ADDRESS = 0x70


def parse_i2c_address(value):
    try:
        address = int(value, 0)
    except ValueError as error:
        raise argparse.ArgumentTypeError(f"Invalid I2C address: {value}") from error
    if not 0 <= address <= 0x7F:
        raise argparse.ArgumentTypeError("I2C addresses must be between 0x00 and 0x7f")
    return address


def parse_channels(value):
    try:
        channels = [int(channel.strip()) for channel in value.split(",")]
    except ValueError as error:
        raise argparse.ArgumentTypeError("Channels must be comma-separated integers") from error
    if not channels or any(channel < 0 or channel > 7 for channel in channels):
        raise argparse.ArgumentTypeError("Each PCA9548A channel must be between 0 and 7")
    if len(set(channels)) != len(channels):
        raise argparse.ArgumentTypeError("Each channel may appear only once")
    return channels


def parse_args():
    parser = argparse.ArgumentParser(
        description="Test AS5600 sensors on a PCA9548A I2C multiplexer."
    )
    parser.add_argument("--bus", type=int, default=1, help="I2C bus number (default: 1)")
    parser.add_argument("--mux-address", type=parse_i2c_address, default=PCA9548A_DEFAULT_ADDRESS, help="PCA9548A I2C address (default: 0x70)")
    parser.add_argument("--sensor-address", type=parse_i2c_address, default=AS5600_DEFAULT_ADDRESS, help="AS5600 I2C address (default: 0x36)")
    parser.add_argument("--channels", type=parse_channels, default=[0, 1, 2], help="PCA9548A channels holding sensors (default: 0,1,2)")
    parser.add_argument("--interval", type=float, default=0.5, help="Seconds between samples (default: 0.5)")
    parser.add_argument("--count", type=int, default=1, help="Samples to take; 0 runs continuously")
    return parser.parse_args()


def decode_status(value):
    if value & 0x20:
        return "magnet OK"
    if value & 0x10:
        return "magnet too weak"
    if value & 0x08:
        return "magnet too strong"
    return "magnet not detected"


def select_channel(bus, mux_address, channel):
    bus.write_byte(mux_address, 1 << channel)


def read_sensor(bus, sensor_address):
    status = bus.read_byte_data(sensor_address, AS5600_STATUS_REGISTER)
    high, low = bus.read_i2c_block_data(sensor_address, AS5600_RAW_ANGLE_REGISTER, 2)
    raw_angle = ((high & 0x0F) << 8) | low
    return raw_angle, raw_angle * 360.0 / 4096, decode_status(status)


def main():
    args = parse_args()
    if args.interval <= 0:
        raise SystemExit("--interval must be greater than zero")
    if args.count < 0:
        raise SystemExit("--count cannot be negative")

    try:
        from smbus2 import SMBus
    except ImportError as error:
        raise SystemExit("Missing smbus2. Run ./update.sh, or install the project's requirements.txt.") from error

    print(f"Testing AS5600 sensors on I2C bus {args.bus}, PCA9548A 0x{args.mux_address:02X}, channels {', '.join(map(str, args.channels))}. Press Ctrl-C to stop.")
    sample = 0
    try:
        with SMBus(args.bus) as bus:
            while args.count == 0 or sample < args.count:
                sample += 1
                print(f"\nSample {sample}")
                for channel in args.channels:
                    try:
                        select_channel(bus, args.mux_address, channel)
                        raw_angle, degrees, magnet_status = read_sensor(bus, args.sensor_address)
                        print(f"  channel {channel}: {degrees:7.2f} degrees (raw {raw_angle:4d}/4095, {magnet_status})")
                    except OSError as error:
                        print(f"  channel {channel}: ERROR - {error}")
                if args.count == 0 or sample < args.count:
                    time.sleep(args.interval)
    except FileNotFoundError as error:
        raise SystemExit(f"Could not open /dev/i2c-{args.bus}. Enable I2C in raspi-config and reboot.") from error
    finally:
        try:
            with SMBus(args.bus) as bus:
                bus.write_byte(args.mux_address, 0x00)
        except (OSError, UnboundLocalError):
            pass


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nTest stopped.")
        sys.exit(0)
