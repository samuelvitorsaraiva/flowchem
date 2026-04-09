"""
Integration tests for flowchem-sim server.

Starts the sim server with test_config_sim.toml via a subprocess and checks
that every simulated device is reachable via HTTP.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pytest
import requests

OK = 200
NOT_FOUND = 404

BASE = "http://127.0.0.1:8000"


# ---------------------------------------------------------------------------
# Fixture: start flowchem-sim server
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def sim_server():
    """Start flowchem-sim with the simulation TOML and wait until ready."""
    config_file = Path(__file__).parent / "test_config_sim.toml"
    repo_root = Path(__file__).parent.parent.parent
    log_handle = tempfile.NamedTemporaryFile(
        mode="w+",
        encoding="utf-8",
        prefix="flowchem-sim-",
        suffix=".log",
        delete=False,
    )
    process = subprocess.Popen(
        [sys.executable, "-m", "flowchem.sim", str(config_file)],
        cwd=repo_root,
        env=os.environ | {"PYTHONUNBUFFERED": "1"},
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        text=True,
    )

    deadline = time.monotonic() + 45
    try:
        while time.monotonic() < deadline:
            if process.poll() is not None:
                log_handle.flush()
                raise RuntimeError(
                    "flowchem-sim exited before becoming ready.\n"
                    + Path(log_handle.name).read_text(encoding="utf-8")
                )

            try:
                response = requests.get(f"{BASE}/", timeout=1, allow_redirects=True)
            except requests.RequestException:
                time.sleep(0.5)
                continue

            if response.status_code == OK:
                break

            time.sleep(0.5)
        else:
            raise RuntimeError("flowchem-sim did not become ready within 45 seconds.")

    except Exception:
        process.terminate()
        process.wait(timeout=10)
        log_handle.flush()
        log_handle.close()
        raise

    yield

    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=10)
    finally:
        log_handle.close()
        try:
            Path(log_handle.name).unlink(missing_ok=True)
        except PermissionError:
            pass


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def get_device(device_name: str) -> dict:
    """GET /{device_name}/ and return the parsed JSON body."""
    r = requests.get(f"{BASE}/{device_name}/", timeout=5)
    assert r.status_code == OK, (
        f"Expected 200 for /{device_name}/, got {r.status_code}: {r.text}"
    )
    return r.json()


# ---------------------------------------------------------------------------
# Tests — one per device family
# ---------------------------------------------------------------------------

class TestSimServerDeviceRoutes:
    """Every device registered in test_config_sim.toml must respond at its root endpoint."""

    def test_server_root_redirects(self, sim_server):
        r = requests.get(f"{BASE}/", timeout=5, allow_redirects=True)
        assert r.status_code == OK
        assert "Flowchem" in r.text

    # --- Hamilton ---

    def test_ml600_device_info(self, sim_server):
        info = get_device("sim-ml600")
        assert info["manufacturer"] == "Hamilton"

    def test_ml600_pump_component_reachable(self, sim_server):
        r = requests.get(f"{BASE}/sim-ml600/pump/", timeout=5)
        assert r.status_code == OK

    def test_ml600_infuse_endpoint(self, sim_server):
        r = requests.put(
            f"{BASE}/sim-ml600/pump/infuse",
            params={"rate": "1 ml/min", "volume": "1 ml"},
            timeout=5,
        )
        assert r.status_code == OK

    def test_ml600_valve_position_endpoint(self, sim_server):
        r = requests.get(f"{BASE}/sim-ml600/valve/position", timeout=5)
        assert r.status_code == OK

    # --- Knauer ---

    def test_azura_device_info(self, sim_server):
        info = get_device("sim-azura")
        assert "knauer" in info["manufacturer"].lower()

    def test_azura_pump_infuse(self, sim_server):
        r = requests.put(
            f"{BASE}/sim-azura/pump/infuse",
            params={"rate": "0.5 ml/min"},
            timeout=5,
        )
        assert r.status_code == OK

    def test_knauer_valve_device_info(self, sim_server):
        info = get_device("sim-knauer-valve")
        assert "knauer" in info["manufacturer"].lower()

    def test_knauer_valve_position(self, sim_server):
        r = requests.get(
            f"{BASE}/sim-knauer-valve/distribution-valve/position", timeout=5
        )
        assert r.status_code == OK

    def test_knauer_autosampler_device_info(self, sim_server):
        info = get_device("sim-knauer-autosampler")
        assert "knauer" in info["manufacturer"].lower()

    def test_knauer_autosampler_injection_valve_position(self, sim_server):
        r = requests.get(
            f"{BASE}/sim-knauer-autosampler/injection_valve/monitor_position",
            timeout=5,
        )
        assert r.status_code == OK

    def test_knauer_dad_device_info(self, sim_server):
        info = get_device("sim-knauer-dad")
        assert "knauer" in info["manufacturer"].lower()

    def test_knauer_dad_channel_signal(self, sim_server):
        r = requests.get(
            f"{BASE}/sim-knauer-dad/channel1/acquire-signal",
            timeout=5,
        )
        assert r.status_code == OK

    # --- Huber ---

    def test_huber_device_info(self, sim_server):
        info = get_device("sim-huber")
        assert info["manufacturer"] == "Huber"

    def test_huber_temperature_get(self, sim_server):
        r = requests.get(
            f"{BASE}/sim-huber/temperature-control/temperature", timeout=5
        )
        assert r.status_code == OK

    def test_huber_temperature_set(self, sim_server):
        r = requests.put(
            f"{BASE}/sim-huber/temperature-control/temperature",
            params={"temp": "30 degC"},
            timeout=5,
        )
        assert r.status_code == OK

    # --- Harvard Apparatus ---

    def test_elite11_device_info(self, sim_server):
        info = get_device("sim-elite11")
        assert info["manufacturer"] == "HarvardApparatus"

    def test_elite11_pump_infuse(self, sim_server):
        r = requests.put(
            f"{BASE}/sim-elite11/pump/infuse",
            params={"volume": "1 ml"},
            timeout=5,
        )
        assert r.status_code == OK

    # --- Vacuubrand ---

    def test_cvc3000_device_info(self, sim_server):
        info = get_device("sim-cvc3000")
        assert info["manufacturer"] == "Vacuubrand"

    def test_cvc3000_pressure_get(self, sim_server):
        r = requests.get(
            f"{BASE}/sim-cvc3000/pressure-control/pressure", timeout=5
        )
        assert r.status_code == OK

    # --- Manson ---

    def test_manson_device_info(self, sim_server):
        info = get_device("sim-manson")
        assert info["manufacturer"] == "Manson"

    def test_manson_voltage_get(self, sim_server):
        r = requests.get(f"{BASE}/sim-manson/power-control/voltage", timeout=5)
        assert r.status_code == OK

    # --- Bronkhorst ---

    def test_mfc_device_info(self, sim_server):
        r = requests.get(f"{BASE}/sim-mfc/", timeout=5)
        assert r.status_code == OK

    def test_epc_device_info(self, sim_server):
        r = requests.get(f"{BASE}/sim-epc/", timeout=5)
        assert r.status_code == OK

    # --- Runze ---

    def test_runze_valve_device_info(self, sim_server):
        r = requests.get(f"{BASE}/sim-runze/", timeout=5)
        assert r.status_code == OK

    # --- Vici Valco ---

    def test_vici_valve_device_info(self, sim_server):
        r = requests.get(f"{BASE}/sim-vici/", timeout=5)
        assert r.status_code == OK

    # --- Phidgets ---

    def test_phidget_pressure_device_info(self, sim_server):
        r = requests.get(f"{BASE}/sim-phidget-pressure/", timeout=5)
        assert r.status_code == OK

    def test_phidget_bubble_device_info(self, sim_server):
        info = get_device("sim-phidget-bubble")
        assert info["manufacturer"] == "Phidget"

    def test_phidget_bubble_read_voltage(self, sim_server):
        r = requests.get(
            f"{BASE}/sim-phidget-bubble/bubble-sensor/read-voltage",
            timeout=5,
        )
        assert r.status_code == OK

    def test_phidget_power_source_device_info(self, sim_server):
        info = get_device("sim-phidget-5v")
        assert info["manufacturer"] == "Phidget"

    def test_phidget_power_source_power_on(self, sim_server):
        r = requests.put(f"{BASE}/sim-phidget-5v/5V/power-on", timeout=5)
        assert r.status_code == OK

    # --- Mettler-Toledo ---

    def test_icir_device_info(self, sim_server):
        info = get_device("sim-icir")
        assert info["manufacturer"] == "Mettler-Toledo"

    # --- Magritek ---

    def test_spinsolve_device_info(self, sim_server):
        info = get_device("sim-spinsolve")
        assert info["manufacturer"] == "Magritek"

    # --- Waters ---

    def test_waters_ms_device_info(self, sim_server):
        r = requests.get(f"{BASE}/sim-waters-ms/", timeout=5)
        assert r.status_code == OK

    # --- DataApex ---

    def test_clarity_device_info(self, sim_server):
        r = requests.get(f"{BASE}/sim-clarity/", timeout=5)
        assert r.status_code == OK

    # --- Custom MPIKG Switch Box ---

    def test_switchbox_device_info(self, sim_server):
        info = get_device("sim-switchbox")
        assert info["manufacturer"] == "Custom"

    def test_switchbox_relay_reachable(self, sim_server):
        r = requests.get(f"{BASE}/sim-switchbox/relay-A/", timeout=5)
        assert r.status_code == OK

    def test_switchbox_relay_on(self, sim_server):
        r = requests.put(f"{BASE}/sim-switchbox/relay-A/power-on", timeout=5)
        assert r.status_code == OK

    def test_switchbox_relay_off(self, sim_server):
        r = requests.put(f"{BASE}/sim-switchbox/relay-A/power-off", timeout=5)
        assert r.status_code == OK

    # --- Custom Peltier Cooler ---

    def test_peltier_device_info(self, sim_server):
        info = get_device("sim-peltier")
        assert info["manufacturer"] == "Custom"

    def test_peltier_temperature_get(self, sim_server):
        r = requests.get(
            f"{BASE}/sim-peltier/temperature_control/temperature", timeout=5
        )
        assert r.status_code == OK

    def test_peltier_temperature_set(self, sim_server):
        r = requests.put(
            f"{BASE}/sim-peltier/temperature_control/temperature",
            params={"temperature": "-10 degC"},
            timeout=20,
        )
        assert r.status_code == OK

    # --- Bio-Chem Solenoid Valve ---

    def test_solenoid_device_info(self, sim_server):
        r = requests.get(f"{BASE}/sim-solenoid/", timeout=5)
        assert r.status_code == OK

    def test_solenoid_open(self, sim_server):
        r = requests.put(f"{BASE}/sim-solenoid/valve/open", timeout=5)
        assert r.status_code == OK

    def test_solenoid_close(self, sim_server):
        r = requests.put(f"{BASE}/sim-solenoid/valve/close", timeout=5)
        assert r.status_code == OK

    def test_solenoid_2way_device_info(self, sim_server):
        r = requests.get(f"{BASE}/sim-solenoid-2way/", timeout=5)
        assert r.status_code == OK

    # --- Vapourtec ---

    def test_r4_device_info(self, sim_server):
        info = get_device("sim-r4")
        assert info["manufacturer"] == "Vapourtec"

    def test_r4_reactor_temperature_get(self, sim_server):
        r = requests.get(f"{BASE}/sim-r4/reactor1/temperature", timeout=5)
        assert r.status_code == OK

    # --- Infrastructure ---

    def test_startup_config_reflects_toml(self, sim_server):
        """The /startup_config endpoint should list all configured devices."""
        r = requests.get(f"{BASE}/startup_config", timeout=5)
        assert r.status_code == OK
        config = r.json()
        assert "device" in config
        assert "sim-ml600" in config["device"]
        assert "sim-knauer-autosampler" in config["device"]
        assert "sim-knauer-dad" in config["device"]
        assert "sim-phidget-bubble" in config["device"]
        assert "sim-phidget-5v" in config["device"]
        assert "sim-switchbox" in config["device"]
        assert "sim-solenoid" in config["device"]
        assert "sim-r4" in config["device"]

    def test_unknown_device_returns_404(self, sim_server):
        r = requests.get(f"{BASE}/does-not-exist/", timeout=5)
        assert r.status_code == NOT_FOUND
