"""Simulated Waters Xevo MS (AutoLynx file-based interface)."""

from __future__ import annotations

from pathlib import Path
import tempfile
from loguru import logger

from flowchem.devices.waters.waters_ms import WatersMS


class WatersMSSim(WatersMS):
    """
    Simulated Waters Xevo MS.

    The real WatersMS writes a queue file to an AutoLynxQ folder that
    a running AutoLynx process monitors.  The sim writes to a temp
    directory and records calls so tests can assert on them.

    State
    -----
    _sim_records : list[dict]   log of all record_mass_spec calls
    """

    def __init__(
        self,
        name: str = "sim-waters-ms",
        path_to_AutoLynxQ: str = "",
        ms_exp_file: str = "",
        tune_file: str = "",
        inlet_method: str = "inlet_method",
    ):
        # Use a real temp dir so file-write logic can still run if desired.
        sim_queue = path_to_AutoLynxQ or tempfile.mkdtemp(prefix="sim_autolynxq_")
        super().__init__(
            name=name,
            path_to_AutoLynxQ=sim_queue,
            ms_exp_file=ms_exp_file,
            tune_file=tune_file,
            inlet_method=inlet_method,
        )
        self._sim_records: list[dict] = []
        logger.info(f"[SIM] WatersMS '{name}' — queue dir: {sim_queue}")

    @classmethod
    def from_config(cls, **config) -> "WatersMSSim":
        return cls(
            name=config.pop("name", "sim-waters-ms"),
            path_to_AutoLynxQ=config.pop("path_to_AutoLynxQ", ""),
            ms_exp_file=config.pop("ms_exp_file", ""),
            tune_file=config.pop("tune_file", ""),
            inlet_method=config.pop("inlet_method", "inlet_method"),
        )

    async def record_mass_spec(
        self,
        sample_name: str,
        run_duration: int = 0,
        queue_name: str = "next.txt",
        do_conversion: bool = False,
        output_dir: str = "",
    ):
        """Record the call without invoking subprocess conversion."""
        record = {
            "sample_name": sample_name,
            "run_duration": run_duration,
            "queue_name": queue_name,
        }
        self._sim_records.append(record)
        logger.info(f"[SIM] WatersMS record_mass_spec: {record}")
        # Still write the queue file so file-write logic is tested.
        file_path = self.queue_path / Path(queue_name)
        with open(file_path, "w") as f:
            f.write(self.fields)
            f.write(f"\n{sample_name}{self.rows}")
        # Skip do_conversion — never invoke subprocess in simulation.
