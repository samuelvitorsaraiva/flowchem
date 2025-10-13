"""Component of the Electronic Box Control MPIKG."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pint.errors import UndefinedUnitError, DimensionalityError
from flowchem.components.technical.MultiChannels import (
    MultiChannelADC,
    MultiChannelDAC,
    MultiChannelRelay
)
from flowchem import ureg
from loguru import logger

if TYPE_CHECKING:
    from .mpikg_switch_box import SwitchBoxMPIKG


class SwitchBoxDAC(MultiChannelDAC):

    def __init__(self, name: str, hw_device: "SwitchBoxMPIKG"):

        super().__init__(name=name, hw_device=hw_device)

        self.hw_device: SwitchBoxMPIKG

    async def read(self, channel: str) -> float:  # type:ignore[override]
        """
        Read the DAC output of a channel.

        Args:
            channel (str): DAC channel index (1 or 2).

        Returns:
            float: DAC output in volts.
        """
        return await self.hw_device.get_dac(channel=int(channel), volts=True)

    async def set(self, channel: str = "1", value: str = "0 V") -> bool:  # type:ignore[override]
        """
        Set the DAC output voltage for a given channel.

        Args:
            channel (str, optional): DAC channel index. Must be a digit string
                (e.g., "1", "2"). Defaults to "1".
            value (str, optional): Target voltage with unit, expressed as a string
                parsable by the unit registry (e.g., "2.5 V", "500 mV").
                Defaults to "0 V".

        Returns:
            bool:
                - True if the voltage command was successfully sent to the hardware.
                - False if the channel argument is invalid or if the value cannot be parsed.

        Notes:
            - The channel must be convertible to an integer.
            - The voltage string is parsed using the unit registry (`ureg`).
            - Any parsing or hardware errors are logged via `logger`.
        """
        if not channel.isdigit():
            logger.error("The argument channel of the DAC should be a digit (1, 2, ...)")
            return False
        try:
            volts = ureg(value)
        except (UndefinedUnitError, DimensionalityError, Exception) as e:
            logger.error(
                f"Invalid DAC value '{value}' for channel {channel}: {e}"
            )
            return False
        return await self.hw_device.set_dac(  # type:ignore[call-arg]
            channel=int(channel), value=volts
        )


class SwitchBoxADC(MultiChannelADC):

    async def read(self, channel: str) -> float:  # type:ignore[override]
        """
        Read ADC (Analog-to-Digital Converter) channel (1 to 8).

        Returns:
            voltage value in volts.
        """
        asw = await self.read_all()
        value = asw.get(f"ADC{channel}")
        if value:
            return value
        raise Exception(f"There is no channel '{channel} in ADC ports!'")

    async def read_all(self) -> dict[str, float]:
        """
        Read all ADC (Analog-to-Digital Converter) channels.

        Returns:
            dict[str, float]: Mapping of channel IDs (e.g. "ADC1", "ADC2") to measured
            voltage values in volts.
        """
        self.hw_device: SwitchBoxMPIKG
        return await self.hw_device.get_adc()


class SwitchBoxRelay(MultiChannelRelay):
    """
    Interface for controlling a multi-channel relay module within a SwitchBox device.

    The `SwitchBoxRelay` class provides asynchronous control over relay ports ("a", "b", "c", or "d"),
    where each port manages up to 8 relay channels. It allows powering individual channels ON/OFF,
    setting multiple channels simultaneously, and reading the current state of specific channels.

    Each channel can operate in three modes:
        * 0 → OFF
        * 1 → Half power (~12 V)
        * 2 → Full power (~24 V)

    The `identify` parameter determines which port (a–d) this relay instance controls:
        - Port "a" → channels 1–8
        - Port "b" → channels 9–16
        - Port "c" → channels 17–24
        - Port "d" → channels 25–32

    Args:
        name (str): Name of the relay device instance.
        hw_device (SwitchBoxMPIKG): Reference to the connected SwitchBox hardware device.
        identify (str): Port identifier ("a", "b", "c", or "d") corresponding to the relay module.

    Methods:
        power_on(channel: str) -> bool:
            Power ON a specific relay channel.
        power_off(channel: str) -> bool:
            Power OFF a specific relay channel.
        multiple_channel(values: str, switch_to_low_after: float = -1) -> bool:
            Set states for all 8 channels at once.
        read_channel_set_point(channel: str) -> int | None:
            Read the current relay state of a specific channel.
        set_channel(channel: str, value: str, keep_port_status: bool = True, switch_to_low_after: float = -1) -> bool:
            Internal helper to change the state of a single relay channel.
    """
    def __init__(self, name: str, hw_device: "SwitchBoxMPIKG", identify: str):

        super().__init__(name=name, hw_device=hw_device)

        self.hw_device: SwitchBoxMPIKG

        self.identify = identify # Port identifier ("a", "b", "c", or "d")

    async def power_on(self, channel: str) -> bool:  # type:ignore[override]
        """
        Power ON a single relay channel.

        Sends a command to set the given channel to the "Full power" state (2).

        Args:
            channel (str): Relay channel index (1–8) or (1–32) depending on port mapping:
                - Port a → channels 1–8
                - Port b → channels 9–16
                - Port c → channels 17–24
                - Port d → channels 25–32

        Returns:
            bool: True if the device acknowledged the command, False otherwise.
        """
        return await self.set_channel(channel, value="2")

    async def power_off(self, channel: str) -> bool:  # type:ignore[override]
        """
        Power OFF a single relay channel.

        Sends a command to set the given channel to the "OFF" state (0).

        Args:
            channel (str): Relay channel index (1–8) or (1–32) depending on port mapping:
                - Port a → channels 1–8
                - Port b → channels 9–16
                - Port c → channels 17–24
                - Port d → channels 25–32

        Returns:
            bool: True if the device acknowledged the command, False otherwise.
        """
        return await self.set_channel(channel, value="0")

    async def multiple_channel(self, values: str, switch_to_low_after: float = -1):
        """
        Set the relay states of all 8 channels on the current port.

        Each character in `values` represents a relay channel state:
            * 0 → OFF
            * 1 → Half power (~12 V)
            * 2 → Full power (~24 V)

        Args:
            values (str): String of up to 8 digits (0, 1, or 2).
                Example: "00010012"
                - If shorter than 8, remaining channels are set to 0.
                - If longer than 8, extra values are ignored.
            switch_to_low_after (float, optional):
                Delay in seconds after which channels set to 2 are automatically
                switched to 1 (half power). Default is -1 (disabled).

        Returns:
            bool: True if the device acknowledged the command, False otherwise.
        """
        return await self.hw_device.set_relay_port(
            values=[int(c) for c in values],
            switch_to_low_after=switch_to_low_after,
            port=self.identify
        )

    async def read_channel_set_point(self, channel: str) -> int | None:
        """
        Read the current relay state of a single channel.

        Channel states:
            * 0 → OFF
            * 1 → Half power (power1 only, ~12 V)
            * 2 → Full power (power1 + power2, ~24 V)

        Args:
            channel (str): Relay channel index (1–8).

        Returns:
            int | bool:
                - 0, 1, or 2 → valid relay state.
                - None → if the channel index is invalid.
        """
        ch = int(channel)
        if not 0 < ch <= 8:
            logger.error(f"There is not channel {ch} in device {self.name} at port-{self.identify}!")
            return None
        if ch > 8:
            if 8 < ch <= 16 and self.identify == "b":
                ch = ch - 8
            elif 16 < ch <= 24 and self.identify == "c":
                ch = ch - 16
            elif 24 < ch <= 32 and self.identify == "d":
                ch = ch - 24
            logger.error(f"There is not channel {ch} in device {self.hw_device.name} at port-{self.identify}!")
            return None
        asw = await self.hw_device.get_relay_channels()
        return asw[self.identify][ch - 1]

    async def read_channels_set_point(self) -> list[int]:
        """
        Read the current relay state of a single channel.

        Channel states:
            * 0 → OFF
            * 1 → Half power (power1 only, ~12 V)
            * 2 → Full power (power1 + power2, ~24 V)

        Returns:
            list[int]:
                - 0, 1, or 2 → valid relay state.
        """
        asw = await self.hw_device.get_relay_channels()
        return asw[self.identify]

    """ Auxiliar methods """

    async def set_channel(
            self,
            channel: str,
            value: str,
            keep_port_status: bool = True,
            switch_to_low_after: float = -1) -> bool:
        """
        Set the state of a single relay channel.

        Args:
            channel (str): Relay channel index (1–8) or (1-32) if the channel match with the correspodent port.
            value (str): Desired channel state:
                * 0 → OFF
                * 1 → Half power (~12 V)
                * 2 → Full power (~24 V)
            keep_port_status (str, optional):
                If true (default), preserves the state of other channels
                in the same port (module).
                If false, all other channels in the port are reset to 0.
            switch_to_low_after (float, optional):
                If >0 and value=2, automatically switches the channel
                to 1 (half power) after the given delay in seconds.
                Useful to reduce heat generation.
                Default = -1 (disabled).

        Returns:
            bool: True if the device acknowledged the command, False otherwise.
        """
        return await self.hw_device.set_relay_single_channel(
            channel=int(channel),
            value=int(value),
            keep_port_status=keep_port_status,
            switch_to_low_after=switch_to_low_after,
            port_identify=self.identify
        )
