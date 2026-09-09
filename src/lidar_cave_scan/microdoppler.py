"""Experimental coherent SAR micro-motion analysis."""

from __future__ import annotations

import json
from pathlib import Path

C = 299792458.0


def velocity_from_phase(samples, times, wavelength_m, reference=None, detrend=True):
    import numpy as np
    from scipy import signal

    z = np.asarray(samples, dtype=np.complex128).reshape(-1)
    t = np.asarray(times, dtype=float).reshape(-1)
    if len(z) != len(t) or len(t) < 8 or not np.all(np.isfinite(t)) or np.any(np.diff(t) <= 0):
        raise ValueError("At least 8 samples with strictly increasing matching timestamps required.")
    if not np.all(np.isfinite(z)) or wavelength_m <= 0:
        raise ValueError("Invalid samples or wavelength.")
    if reference is not None:
        ref = np.asarray(reference, dtype=np.complex128).reshape(-1)
        if ref.shape != z.shape or np.any(np.abs(ref) < 1e-12):
            raise ValueError("Invalid reference.")
        z = z * np.conj(ref) / np.abs(ref)
    phase = np.unwrap(np.angle(z))
    displacement = phase * wavelength_m / (4 * np.pi)
    if detrend:
        displacement = signal.detrend(displacement, type="linear")
    velocity = np.gradient(displacement, t)
    return displacement, velocity


def analyze(samples, times, wavelength_m, reference=None, min_frequency=0.1, max_frequency=None):
    import numpy as np
    from scipy import signal

    t = np.asarray(times, dtype=float)
    dt = np.diff(t)
    fs = 1 / np.median(dt)
    if np.max(np.abs(dt - np.median(dt))) > 0.01 * np.median(dt):
        raise ValueError("Nonuniform timing: resample with a calibrated method first.")
    displacement, velocity = velocity_from_phase(samples, t, wavelength_m, reference)
    duration = t[-1] - t[0]
    if max_frequency is None:
        max_frequency = 0.8 * fs / 2
    if not 0 < min_frequency < max_frequency < fs / 2:
        raise ValueError("Invalid frequency limits or Nyquist violation.")
    frequencies, power = signal.periodogram(
        displacement,
        fs=fs,
        window="hann",
        detrend="constant",
        scaling="spectrum",
    )
    band = (frequencies >= min_frequency) & (frequencies <= max_frequency)
    if not band.any():
        raise ValueError("Acquisition too short for requested frequency band.")
    peak = np.where(band)[0][np.argmax(power[band])]
    noise = np.median(power[band])
    peak_to_median = 10 * np.log10(max(power[peak], 1e-30) / max(noise, 1e-30))
    metrics = {
        "frequency_hz": float(frequencies[peak]),
        "frequency_resolution_hz": float(fs / len(t)),
        "duration_s": float(duration),
        "sample_rate_hz": float(fs),
        "nyquist_hz": float(fs / 2),
        "los_displacement_rms_mm": float(np.std(displacement) * 1000),
        "los_velocity_rms_mm_s": float(np.std(velocity) * 1000),
        "peak_to_median_db": float(peak_to_median),
        "wavelength_m": float(wavelength_m),
        "reference_used": reference is not None,
        "status": "experimental_unvalidated",
        "warning": "Surface/structure motion only. Not a cave detection, depth estimate, or safety assessment.",
    }
    return metrics, displacement, velocity, frequencies, power


def make_synthetic_demo():
    import numpy as np

    rng = np.random.default_rng(42)
    fs = 100
    times = np.arange(0, 20, 1 / fs)
    wavelength = 0.031
    displacement = 0.002 * np.sin(2 * np.pi * 1.25 * times)
    drift = 0.0004 * times
    reference = np.exp(1j * 4 * np.pi * drift / wavelength)
    samples = np.exp(1j * 4 * np.pi * (displacement + drift) / wavelength)
    samples *= np.exp(1j * rng.normal(0, 0.012, len(times)))
    truth = {"synthetic_frequency_hz": 1.25, "synthetic_amplitude_mm": 2.0}
    return times, samples, reference, wavelength, truth


def run_microdoppler(
    input_path: str | None = None,
    demo: bool = False,
    out_dir: str = "outputs/microdoppler",
    min_frequency: float = 0.1,
    max_frequency: float | None = None,
) -> Path:
    import matplotlib
    import numpy as np

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    if demo:
        times, samples, reference, wavelength, truth = make_synthetic_demo()
        np.savez_compressed(out / "synthetic_samples.npz", time_s=times, samples=samples, reference=reference, wavelength_m=wavelength)
    elif input_path:
        with np.load(input_path, allow_pickle=False) as data:
            times = data["time_s"]
            samples = data["samples"]
            wavelength = float(data["wavelength_m"])
            reference = data["reference"] if "reference" in data else None
        truth = {}
    else:
        raise ValueError("Supply --input or --demo.")

    metrics, displacement, velocity, frequencies, power = analyze(
        samples,
        times,
        wavelength,
        reference,
        min_frequency,
        max_frequency,
    )
    metrics.update(truth)
    (out / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    np.savetxt(
        out / "motion.csv",
        np.column_stack([times, displacement * 1000, velocity * 1000]),
        delimiter=",",
        header="time_s,los_displacement_mm,los_velocity_mm_s",
        comments="",
    )
    np.savetxt(
        out / "spectrum.csv",
        np.column_stack([frequencies, power]),
        delimiter=",",
        header="frequency_hz,displacement_spectrum_m2",
        comments="",
    )

    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(times, displacement * 1000)
    ax.set(xlabel="Time (s)", ylabel="LOS displacement (mm)", title="Experimental micro-motion")
    fig.tight_layout()
    fig.savefig(out / "motion.png", dpi=160)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(frequencies, power)
    ax.set(xlabel="Frequency (Hz)", ylabel="Displacement spectrum (m^2)", title="Experimental frequency spectrum")
    ax.set_xlim(0, min(10, max(frequencies)))
    fig.tight_layout()
    fig.savefig(out / "spectrum.png", dpi=160)
    plt.close(fig)

    print(json.dumps(metrics, indent=2))
    return out
