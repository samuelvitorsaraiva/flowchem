from flowchem.components.valves.solenoid import SolenoidValve


class BioChemSolenoidValveComponent(SolenoidValve):

    async def open(self):
        """
        Open the solenoid valve.

        This method energises the solenoid if it is normally closed, or de-energises it if it is normally open, switching the valve to the
        'open' state, which allows flow through the channel.
        """
        return await self.hw_device.open()  # type:ignore[attr-defined]

    async def close(self):
        """
        Close the solenoid valve.

        This method de-energizes the solenoid, switching the valve to
        the "closed" state, stopping flow through the channel.
        """
        return await self.hw_device.close()  # type:ignore[attr-defined]

    async def is_open(self) -> bool:
        """
        Get the current valve status.

        Returns
        -------
        bool
            `True` if the valve is open, `False` if closed.
        """
        return await self.hw_device.is_open()  # type:ignore[attr-defined]